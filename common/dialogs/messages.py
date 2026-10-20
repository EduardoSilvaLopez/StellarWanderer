"""Message dialogs: a message is built in code and queued with show_message, then shown by the main loop.

Game code builds a Message (title, text, buttons), with its text formatted by ordinary f-strings at the call site,
and calls show_message(message, on_result=...). It never opens a modal loop itself: the main loop opens pending
messages at the start of the next frame (next_pending_message) and then calls on_result with the pressed button's
index, or None when the player dismissed the message with Esc or a right-click.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List, Optional

DEFAULT_BUTTON = "OK"


@dataclass
class Message:
    """What a message dialog shows.

    title: the heading.
    text: the body. A blank line starts a new paragraph; each paragraph is wrapped by the dialog.
    buttons: the labels, in order. The callback is told which one was pressed by its position (first = 0).
    open_sound: the sound (common/audio.py) played when the message opens, for one with a sound of its own.
    """

    title: str
    text: str
    buttons: List[str] = field(default_factory=lambda: [DEFAULT_BUTTON])
    open_sound: str = 'ui_open'

    @property
    def paragraphs(self) -> List[str]:
        return _paragraphs(self.text)


def _paragraphs(text: str) -> List[str]:
    """Split on blank lines; the lines of a paragraph are joined into one string to be wrapped."""
    result: List[str] = []
    for block in text.replace('\r\n', '\n').split('\n\n'):
        joined = ' '.join(line.strip() for line in block.split('\n') if line.strip())
        if joined:
            result.append(joined)
    return result


# Called with the index of the pressed button (in the order of the message's buttons), or None when the
# message was dismissed with Esc or a right-click.
ResultCallback = Callable[[Optional[int]], None]


@dataclass
class PendingMessage:
    message: Message
    on_result: Optional[ResultCallback] = None


_pending: List[PendingMessage] = []


def show_message(message: Message, on_result: Optional[ResultCallback] = None) -> None:
    """Queue `message` to be shown at the start of the next frame.

    Because the message opens later, the answer cannot be returned: pass `on_result`, which is called with the
    index of the pressed button, or None if the player dismissed the message with Esc or a right-click."""
    _pending.append(PendingMessage(message, on_result))


def confirm(title: str, text: str, confirm_label: str, on_confirm: Callable[[], None]) -> None:
    """Queue a two-button message: `on_confirm` runs only when the first button (`confirm_label`) is pressed.
    Cancel and Esc do nothing."""
    def on_result(index: Optional[int]) -> None:
        if index == 0:
            on_confirm()
    show_message(Message(title, text, [confirm_label, 'Cancel']), on_result)


def next_pending_message() -> Optional[PendingMessage]:
    """Remove and return the oldest pending message, or None."""
    return _pending.pop(0) if _pending else None


def has_pending_messages() -> bool:
    return bool(_pending)
