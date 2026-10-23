"""A conversation of the outpost's chat (the Chat option of the outpost screen): started by a conversation tag, with the
person selected in the list. It writes into the chat's log (chat_log.py), never into a dialog window.

The texts are written with `say` (the person's line, with its [marks] that make new tags) and the replies with `offer`
(the callback gets the index of the reply the player chose). The conversation dies out when it offers nothing more: the
player then starts the next one from a tag, in the same log. `start` says the tag as the pilot's line, then the answer
(for the presentation tag, the pilot's line is Player.present_yourself).
Each interaction is written into the person's record as it happens (`remember`), so the last time met is up to date
even while the chat is open.
"""

from __future__ import annotations
from typing import Callable, List, Optional

from galaxies.people.chat_log import NPC, PLAYER, ChatLog, parse_marks
from galaxies.people.conversation import Conversation
from galaxies.people.person import Person
from galaxies.people.player import Player


class OutpostChat(Conversation):
    def __init__(self, player: Player, interlocutor: Person, log: ChatLog, tag: str) -> None:
        super().__init__(player, interlocutor)
        self.log: ChatLog = log  # the chat of the outpost screen: the texts go there
        self.tag: str = tag  # the conversation tag that started this conversation
        self.reactions: map = self.reactions_index()
        # The lines of this time are the person's record from now on: the list is shared with `interactions`, so a
        # second conversation in the same visit (the same game time) adds to it instead of replacing it.
        self.interaction_lines = interlocutor.interactions.setdefault(self.date_time.replace(microsecond=0), [])
        self.remember()

    def start(self) -> None:
        """The tag is said by the pilot first, as a line of the chat, then the person answers it. The presentation tag
        is the exception: the pilot says what Player.present_yourself gives, not the tag."""
        pilot_line = self.player.present_yourself() if self.tag == Player.PRESENTATION_TAG else self.tag
        self.log.add(PLAYER, [(word, False) for word in pilot_line.split()])
        self.say(self.reactions[self.tag])

    def remember(self) -> None:
        """Writes the interaction into the person's record now, not only when the conversation closes, so a save made
        while the chat is open keeps it."""
        self.interlocutor.last_communication_at = self.date_time
        self.interlocutor.record()

    def say(self, generator: Callable[[OutpostChat], str]) -> None:
        """The person says `text` in the chat. Its [marks] become the pilot's conversation tags, from now on."""
        text: str = generator()
        words, tags = parse_marks(text)
        self.player.conversation_tags.update(tags)
        self.log.add(NPC, words)
        self.interaction_lines.append(text)
        self.remember()

    def offer(self, labels: List[str], then: Optional[Callable[[int], object]] = None) -> None:
        """Offers the player `labels` as replies. Choosing one calls `then` with its index; with no labels, the
        conversation has nothing more to say."""
        self.log.offer(labels, then)

    # region Talk
    def reactions_index(self) -> map:
        return {
            Player.PRESENTATION_TAG: self.talk_present_yourself
        }

    def talk_present_yourself(self) -> str:
        reply = "Fascinating."
        return reply
    # endregion

