"""The pilot wants to leave a settlement. The Dockmaster warns them of what they may want to settle first: that the ship
is not ready yet, and that the one who has the say (Settlement.officer_for_leaving, the Coordinator or the Komisar)
wants them to present themselves in their office while a promotion is due (see promotion.py; what it gives is in
SettlementChat.promotion_effects). Either way, the pilot may leave at once."""

from __future__ import annotations
from typing import Callable, List, Optional

from common.messages import Message, ShowMessage, show_message
from universe.artifacts.settlements.settlement import Settlement
from universe.society.people.player import Player
from universe.society.people import promotion
from ..person import Person
from ..conversation import Conversation


class SettlementOnLeaving(Conversation):
    """`interlocutor` is the Dockmaster, who speaks. `on_decided` is told whether the pilot leaves."""

    def __init__(
            self,
            player: Player,
            interlocutor: Person,
            settlement: Settlement,
            on_decided: Callable[[bool], object],
            show: ShowMessage = show_message
            ) -> None:
        super().__init__(player, interlocutor, show)
        self.settlement: Settlement = settlement
        self.on_decided: Callable[[bool], object] = on_decided

        self.has_promotion: bool = promotion.next_step(self.player) is not None

        self.title: str = "Not ready yet" if self.settlement.handling_due_at is not None else "Good news"

    def start(self) -> None:
        is_not_ready: bool = self.settlement.handling_due_at is not None
        if not self.has_promotion and not is_not_ready:
            self._decide(True)
            return

        paragraphs: List[str] = [self.generate_introduction_text().strip()]
        officer: Optional[Person] = self.settlement.officer_for_leaving
        if self.has_promotion and officer is not None:
            his: str = "her" if officer.gender_group is Person.GenderGroup.FEMALE else "his"
            paragraphs.append(f"The {officer.role.name} wants you to present yourself in {his} office.")
        if is_not_ready:
            paragraphs.append("The ship is not ready yet.")
        paragraphs.append("Do you want to leave anyway?")

        self.show(Message(
                title=self.title,
                text="\n\n".join(paragraph for paragraph in paragraphs if paragraph),
                buttons=['Yes', 'No'],
                open_sound='radio_open'
                ), self._answered
            )

    def _answered(self, chosen_button: Optional[int]) -> None:
        self._decide(chosen_button == 0)

    def _decide(self, leaves: bool) -> None:
        self.close()
        self.on_decided(leaves)
