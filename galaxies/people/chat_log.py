"""The chat of an outpost: what has been said with the person selected in the Chat option, as data (the lines, and the
replies the player is offered). common/dialogs/chat_view.py draws it; outpost_chat.py writes into it.

A text written for the chat marks its conversation tags with square brackets: "I came with my [family]". The marked
words are shown in the accent colour, and the tag ("family", lowercased) is one of the pilot's tags from then on
(`parse_marks`). A log belongs to one person: selecting another person starts a new log.

Replies are offered with a callback: `offer(labels, then)` shows the labels, and `choose(index)` keeps the chosen one as
a line of the pilot's, drops the other replies, and calls `then(index)`. Only one set of replies is open at a time."""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

if TYPE_CHECKING:
    from galaxies.people.person import Person

PLAYER = 'player'
NPC = 'npc'
MARK = re.compile(r'\[([^\[\]]+)\]')

Word = Tuple[str, Optional[str]]  # a word, and the conversation tag it is (lowercased), None if it is not one


def parse_marks(text: str) -> Tuple[List[List[Word]], List[str]]:
    """The paragraphs of `text` (split at blank lines), each as its words, each with the tag it is if it was inside square
    brackets; and the tags it marks: lowercased and stripped, one for each mark, in the order written. The brackets are
    not words."""
    paragraphs: List[List[Word]] = []
    tags: List[str] = []
    for paragraph in text.split('\n\n'):
        words: List[Word] = []
        position = 0
        for match in MARK.finditer(paragraph):
            words += [(word, None) for word in paragraph[position:match.start()].split()]
            tag = match.group(1).strip()
            if tag:
                tags.append(tag.lower())
                words += [(word, tag.lower()) for word in tag.split()]  # shown as written, the tag is the lowercase one
            position = match.end()
        words += [(word, None) for word in paragraph[position:].split()]
        if words:
            paragraphs.append(words)
    return paragraphs, tags


@dataclass(frozen=True)
class ChatLine:
    speaker: str  # PLAYER or NPC
    paragraphs: Tuple[Tuple[Word, ...], ...]


class ChatLog:
    """The lines of the chat with `person`, and the replies open now (None when there are none)."""

    def __init__(self, person: Person) -> None:
        self.person: Person = person
        self.lines: List[ChatLine] = []
        self.replies: Optional[List[str]] = None  # the labels the player may choose from, if any
        self._then: Optional[Callable[[int], object]] = None  # what the chosen reply starts

    def add(self, speaker: str, paragraphs: List[List[Word]]) -> None:
        self.lines.append(ChatLine(speaker, tuple(tuple(words) for words in paragraphs)))

    def offer(self, labels: List[str], then: Optional[Callable[[int], object]] = None) -> None:
        """Shows `labels` as replies from the player. Choosing one calls `then` with its index. No labels: no replies
        are open, and the conversation is over."""
        self.replies = list(labels) if labels else None
        self._then = then if labels else None

    def choose(self, index: int) -> None:
        """The player chooses reply `index`: it stays in the log as the player's line, the other replies go, and the
        callback of the replies is called with the index."""
        if self.replies is None:
            return
        label = self.replies[index]
        then = self._then
        self.replies = None
        self._then = None
        self.add(PLAYER, [[(word, None) for word in label.split()]])
        if then is not None:
            then(index)
