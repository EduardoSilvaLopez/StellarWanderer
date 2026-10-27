"""The pilot wants to leave the outpost. The Coordinator may have something to tell them before the departure. This
can change their opinion."""

from __future__ import annotations
from typing import Callable, List, Optional

from common.dialogs.messages import Message, ShowMessage, show_message
from galaxies.outpost import Outpost
from galaxies.people.player import Player
from galaxies.politics.political_entity import PoliticalEntity
from spaceships.ship_configurations.ths_miner import ThsMiner
from spaceships.ship_configurations.ths_shabby_miner import ShabbyThsMiner
from ..person import Person
from ..conversation import Conversation


class OutpostLeaving(Conversation):
    def __init__(self, player: Player, interlocutor: Person, outpost: Outpost, on_decided: Callable[[bool], object],
                 show: ShowMessage = show_message) -> None:
        super().__init__(player, interlocutor, show)
        self.outpost: Outpost = outpost
        self.on_decided: Callable[[bool], object] = on_decided

        entity: PoliticalEntity = self.player.those_who_share.entity
        if self.outpost.player_reputation_on_entering is None:
            raise Exception("No reputation recorded on entering.")
        self.old_rep: float = self.outpost.player_reputation_on_entering
        self.new_rep: float = self.player.those_who_share.reputation
        old_title: str = entity.title_for(self.old_rep)
        new_title: str = entity.title_for(self.new_rep)
        self.title_has_improved: bool = self.old_rep < self.new_rep and old_title != new_title

        self.title: str = "Good news" if self.title_has_improved else "Not ready yet"

    def start(self) -> None:
        if not self.title_has_improved and self.outpost.handling_due_at is None:
            self._decide(True)
            return

        it: str = self.generate_introduction_text()

        title_improved_text: str = self._higher_title_effects(self.old_rep) if self.title_has_improved else ''

        if self.outpost.dockmaster is None:
            raise Exception("No dockmaster.")
        not_ready_text: str = '' if self.outpost.handling_due_at is None \
            else (
                f"{self.outpost.dockmaster.role.name} {self.outpost.dockmaster.surname} says"
                " the ship is not ready yet. Do you want to leave anyway?"
                )

        text: str = it + (title_improved_text if self.title_has_improved else not_ready_text)

        buttons: List[str] = ['Ok'] if self.title_has_improved else ['Yes', 'No']

        self.show(Message(
                title=self.title,
                text=text,
                buttons=buttons,
                open_sound='radio_open'
                ), self._answered
            )

    def _higher_title_effects(self, old_rep: float) -> str:
        if old_rep < 10:
            self.player.ship.change_cargo_hold(ShabbyThsMiner.StandardHold)
            return (
                f"You have proven you can do the job without wasting mines.\n\n"
                f"We decided to repair your cargo hold... {self.interlocutor.get_player_title()}.\n\n"
                f"{"Long live the Community.\n\n" if self.interlocutor.loyalty100 > 5 else ''}"
                )
        elif old_rep < 20:
            # The effect is the availability of missions.
            return (
                "We have spoken about you and think can trust you to do something more than collect ore.\n\n"
                "Anytime you want, check the mission board of any outpost. But be careful you really can"
                "do the thing.\n\n"
                f"Long live the Community... {self.interlocutor.get_player_title()}\n\n" \
                   if self.interlocutor.loyalty100 > 5 else ''
                )
        elif old_rep < 50:
            self.player.ship.change_cargo_hold(ShabbyThsMiner.ExtendedHold)
            return (
                f"You are doing the best of your ship... {self.interlocutor.get_player_title()}. Really.\n\n"
                f"We found a cargo extension you could use.\n\n"
                f"Keep doing the good job.\n\n"
                f"{"Long live the Community.\n\n" if self.interlocutor.loyalty100 > 5 else ''}"
                )
        elif old_rep < 100:
            self.player.ship.upgrade_to(ThsMiner)
            return  (
                "People were asking why you still have to go around with that piece of..."
                f" no offense intended, {self.interlocutor.get_player_title()}.\n\n"
                "We consulted and the community thinks you deserve a modern THS miner.\n\n"
                "It has a thing for solar panels, you can recharge around the sun. If you dare.\n\n"
                "Take care of it, will you?\n\n"
                f"{"Long live the Community.\n\n" if self.interlocutor.loyalty100 > 5 else ''}"
                )
        return ""

    def _answered(self, chosen_button: Optional[int]) -> None:
        self._decide(chosen_button == 0)

    def _decide(self, leaves: bool) -> None:
        self.close()
        self.on_decided(leaves)
