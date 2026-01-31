"""Typing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class InboxMessage:
    """Message class."""

    by: str
    sender: str
    subject: str
    text: str
    raw: str
    real_sender: str


@dataclass(slots=True, frozen=True)
class Handler:
    """Обработчик."""

    func: any
    by: str | None = None
    sender: str | None = None
    subject: str | None = None
    text: str | None = None
    block: bool | None = True
