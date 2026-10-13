"""Message texts for message dialogs, read from Resources/dialogs/messages.toml.

The file has one section per message: `title`, `text` (paragraphs separated by blank lines), and `button`, or a list `buttons`.
`{placeholders}` are filled from the game data passed to show_message. The file is re-read every time a message
opens, so editing it needs no restart. The messages in use are `welcome` (shown at the start of a new game) and the
outpost messages.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import logging
import os
import tomllib

logger = logging.getLogger(__name__)

MESSAGES_PATH = os.path.join(os.path.dirname(__file__), '..', 'Resources', 'dialogs', 'messages.toml')
DEFAULT_BUTTON = "OK"


@dataclass
class Message:
    title: str
    paragraphs: List[str]
    buttons: List[str] = field(default_factory=lambda: [DEFAULT_BUTTON])  # at least one


class _KeepUnknown(dict):
    """format_map helper: a placeholder without a value stays as written."""

    def __missing__(self, key: str) -> str:
        return '{' + key + '}'


def _fill(text: str, values: Dict[str, Any]) -> str:
    try:
        return text.format_map(_KeepUnknown(values))
    except (ValueError, IndexError, KeyError, AttributeError):
        return text  # a stray brace or an odd placeholder: show the text untouched


def _paragraphs(text: str) -> List[str]:
    """Split on blank lines; the lines of a paragraph are joined into one string to be wrapped."""
    result: List[str] = []
    for block in text.replace('\r\n', '\n').split('\n\n'):
        joined = ' '.join(line.strip() for line in block.split('\n') if line.strip())
        if joined:
            result.append(joined)
    return result


def load_message(key: str, values: Dict[str, Any] = None, path: str = MESSAGES_PATH) -> Message:
    """The message `key` with its placeholders filled in, read from disk now.

    Never raises: a missing file, a syntax error or a missing key give a message that explains
    the problem (so the author sees it in the game) and are logged."""
    values = values or {}
    try:
        with open(path, 'rb') as file:
            entries = tomllib.load(file)
    except FileNotFoundError:
        logger.error(f"Messages file not found: {path}")
        return Message("Missing messages file", [f"Could not find {os.path.normpath(path)}."])
    except tomllib.TOMLDecodeError as error:
        logger.error(f"Messages file is not valid TOML: {error}")
        return Message("Error in messages.toml", [f"The file has a syntax error: {error}"])

    entry = entries.get(key)
    if not isinstance(entry, dict):
        logger.error(f"No message '{key}' in {path}")
        return Message("Missing message", [f"There is no message called '{key}' in messages.toml."])

    # `buttons` is a list of labels; `button` is the shorthand for a single one.
    labels = entry.get('buttons')
    if not isinstance(labels, list) or not labels:
        labels = [entry.get('button', DEFAULT_BUTTON)]

    return Message(
        title=_fill(str(entry.get('title', '')), values),
        paragraphs=_paragraphs(_fill(str(entry.get('text', '')), values)),
        buttons=[_fill(str(label), values) for label in labels],
    )


# Called with the index of the pressed button (in the order of the message's buttons), or None when the
# message was dismissed with Esc.
ResultCallback = Callable[[Optional[int]], None]


@dataclass
class PendingMessage:
    key: str
    values: Dict[str, Any]
    on_result: Optional[ResultCallback] = None


_pending: List[PendingMessage] = []


def show_message(key: str, on_result: Optional[ResultCallback] = None, **values: Any) -> None:
    """Ask for message `key` to be shown. Game code calls this instead of opening a modal loop in the
    middle of an update; the main loop opens pending messages at the start of the next frame.

    Because the message opens later, the answer cannot be returned: pass `on_result`, which is called
    with the index of the pressed button (0 is the first one in messages.toml), or None if the player
    dismissed the message with Esc. The other keyword arguments fill the message's {placeholders}."""
    _pending.append(PendingMessage(key, values, on_result))


def next_pending_message() -> Optional[PendingMessage]:
    """Remove and return the oldest pending message, or None."""
    return _pending.pop(0) if _pending else None


def has_pending_messages() -> bool:
    return bool(_pending)
