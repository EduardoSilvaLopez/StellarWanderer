"""The chat of an outpost: what has been said with the person selected in the Chat option, as data (the lines, and the
replies the player is offered). common/dialogs/chat_view.py draws it; outpost_chat.py writes into it.

An expression of a text written for the chat is a conversation tag if, and only if, it is one of the known tags, present
case-insensitively as whole words: "I came with my family" has the tag "family" if that is known. The tag words are shown
in the accent colour, and the tag (as the reactions spell it) is one of the pilot's tags from then on (`parse_marks`). A log belongs to
one person: selecting another person starts a new log.

Replies are offered with a callback: `offer(labels, then)` shows the labels, and `choose(index)` keeps the chosen one as
a line of the pilot's, drops the other replies, and calls `then(index)`. Only one set of replies is open at a time."""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Iterable, List, Optional, Tuple

if TYPE_CHECKING:
    from galaxies.people.person import Person

PLAYER = 'player'
NPC = 'npc'
TOKEN = re.compile(r'\S+')

Word = Tuple[str, Optional[str]]  # a word, and the conversation tag it is (as spelled by the reactions), None if it is not one


def parse_marks(text: str, tags: Iterable[str]) -> Tuple[List[List[Word]], List[str]]:
    """The paragraphs of `text` (split at blank lines), each as its words, each with the tag it is if it is part of one of
    `tags` (case-insensitively, as whole words, the longest first); and the tags it says: spelled as in `tags`, one for
    each occurrence, in the order written."""
    spelling: dict[str, str] = {tag.lower(): tag for tag in tags}
    expressions: List[str] = sorted(spelling, key=len, reverse=True)
    paragraphs: List[List[Word]] = []
    found: List[str] = []
    for paragraph in text.split('\n\n'):
        spans: List[Tuple[int, int, str]] = []  # start, end and tag of each occurrence in `paragraph`
        for tag in expressions:
            pattern = r'(?<![\w-])' + r'\s+'.join(re.escape(part) for part in tag.split()) + r'(?![\w-])'
            for match in re.finditer(pattern, paragraph, re.IGNORECASE):
                if not any(match.start() < end and start < match.end() for start, end, _ in spans):
                    spans.append((match.start(), match.end(), spelling[tag]))
        spans.sort()
        found += [tag for _, _, tag in spans]

        words: List[Word] = []
        for token in TOKEN.finditer(paragraph):
            tag = next((tag for start, end, tag in spans if start < token.end() and token.start() < end), None)
            words.append((token.group(), tag))
        if words:
            paragraphs.append(words)
    return paragraphs, found


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
