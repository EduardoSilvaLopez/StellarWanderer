"""Message texts for message dialogs, read from Resources/dialogs/messages.toml."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
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
    button: str = DEFAULT_BUTTON


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

    return Message(
        title=_fill(str(entry.get('title', '')), values),
        paragraphs=_paragraphs(_fill(str(entry.get('text', '')), values)),
        button=_fill(str(entry.get('button', DEFAULT_BUTTON)), values),
    )


_pending: List[Tuple[str, Dict[str, Any]]] = []


def show_message(key: str, **values: Any) -> None:
    """Ask for message `key` to be shown. Game code calls this instead of opening a modal loop in the
    middle of an update; the main loop opens pending messages at the start of the next frame."""
    _pending.append((key, values))


def next_pending_message() -> Tuple[str, Dict[str, Any]] | None:
    """Remove and return the oldest pending (key, values), or None."""
    return _pending.pop(0) if _pending else None


def has_pending_messages() -> bool:
    return bool(_pending)
