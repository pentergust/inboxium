"""Main file of project."""

from __future__ import annotations

from email import policy
from email.header import decode_header, make_header
from email.parser import BytesParser
from typing import TYPE_CHECKING

from aiosmtpd.controller import Controller
from loguru import logger

from .types import Handler, InboxMessage

if TYPE_CHECKING:
    from collections.abc import Callable
    from email.message import Message

    from aiosmtpd.smtp import SMTP, Envelope, Session


def _get_body(msg: Message) -> str:
    """Get message body (text)."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(
                    part.get_content_charset("utf-8"),
                    errors="replace",
                )
    else:
        return msg.get_payload(decode=True).decode(
            msg.get_content_charset("utf-8"),
            errors="replace",
        )

    return ""


def _get_real_sender(host_name: str, peer: tuple[str]) -> str:
    if peer:
        return f"{host_name} (http://{peer[0]}:{peer[1]})"
    return ""


def _prepare_message(envelope: Envelope, session: Session) -> InboxMessage:
    """Prepare message."""
    msg = BytesParser(policy=policy.default).parsebytes(envelope.content)  # type: ignore  # noqa: PGH003
    real_sender = _get_real_sender(session.host_name, session.peer)

    return InboxMessage(
        by=envelope.rcpt_tos,
        sender=envelope.mail_from or "",
        subject=str(make_header(decode_header(msg.get("Subject", "")))),
        text=_get_body(msg),
        raw=msg.as_string(),
        real_sender=real_sender,
    )


class Inbox:
    """SMTP Inbox handler."""

    def __init__(self, address: str, port: int | str) -> None:
        """Init an inboxium email-server."""
        self.address = address
        self.port = int(port)

        self.handlers: list[Handler] = []

    async def handle_RCPT(  # noqa: N802
        self,
        _server: SMTP,
        _session: Session,
        envelope: Envelope,
        address: str,
        _rcpt_options: list[str],
    ) -> str:
        """Handle RCPT command."""
        envelope.rcpt_tos.append(address)
        return "250 OK"

    async def handle_DATA(  # noqa: N802
        self,
        _server: SMTP,
        session: Session,
        envelope: Envelope,
    ) -> str:
        """Handle DATA command."""
        try:
            msg = _prepare_message(envelope, session)

            for h in self.handlers:
                if not any((h.by, h.sender, h.subject, h.text)) or any(
                    (
                        h.by == msg.by,
                        h.sender == msg.sender,
                        h.subject == msg.subject,
                        h.text == msg.text,
                    ),
                ):
                    await h.func(msg)
                    if h.block:
                        break

        except Exception as e:  # noqa: BLE001
            logger.exception(e)
            return "500 Internal server error"

        return "250 Message accepted for delivery"

    def message(
        self,
        by: str | None = None,
        sender: str | None = None,
        subject: str | None = None,
        text: str | None = None,
        block: bool | None = True,  # noqa: FBT001, FBT002
    ) -> Callable[[Callable[[Message], None]], None]:
        """Set handler for incoming messages."""

        def decorator(func: Callable[[Message], None]) -> None:
            self.handlers.append(Handler(func, by, sender, subject, text, block))

        return decorator

    def serve(self) -> None:
        """Run the SMTP server."""
        logger.info("Starting SMTP server at {}:{}", self.address, self.port)
        controller = Controller(self, hostname=self.address, port=self.port)
        try:
            controller.start()
            if controller._thread is not None:  # noqa: SLF001
                controller._thread.join()  # noqa: SLF001
        finally:
            controller.stop()
