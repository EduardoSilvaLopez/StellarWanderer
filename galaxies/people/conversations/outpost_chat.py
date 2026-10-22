"""A conversation of the outpost's chat (the Chat option of the outpost screen): started by a conversation tag, with the
person selected in the list. It writes into the chat's log (chat_log.py), never into a dialog window.

The texts are written with `say` (the person's line, with its [marks] that make new tags) and the replies with `offer`
(the callback gets the index of the reply the player chose). The conversation dies out when it offers nothing more: the
player then starts the next one from a tag, in the same log. `start` is where the conversation begins: a stub for now.
"""

from __future__ import annotations
from typing import Callable, List, Optional

from galaxies.people.chat_log import NPC, ChatLog, parse_marks
from galaxies.people.conversation import Conversation
from galaxies.people.person import Person
from galaxies.people.player import Player


class OutpostChat(Conversation):
    def __init__(self, player: Player, interlocutor: Person, log: ChatLog, tag: str) -> None:
        super().__init__(player, interlocutor)
        self.log: ChatLog = log  # the chat of the outpost screen: the texts go there
        self.tag: str = tag  # the conversation tag that started this conversation

    def start(self) -> None:
        """Where the conversation begins. Nothing yet: the texts are to be written here."""
        pass

    def say(self, text: str) -> None:
        """The person says `text` in the chat. Its [marks] become the pilot's conversation tags, from now on."""
        words, tags = parse_marks(text)
        self.player.conversation_tags.update(tags)
        self.log.add(NPC, words)
        self.interaction_lines.append(text)

    def offer(self, labels: List[str], then: Optional[Callable[[int], object]] = None) -> None:
        """Offers the player `labels` as replies. Choosing one calls `then` with its index; with no labels, the
        conversation has nothing more to say."""
        self.log.offer(labels, then)
