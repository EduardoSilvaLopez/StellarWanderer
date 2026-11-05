"""The pilot wants to leave a settlement. Its coordinator (the Komisar, at a portal base) may have something to
tell them before the departure. This can change their opinion."""

from __future__ import annotations
from typing import Callable, List, Optional

from common.dialogs.messages import Message, ShowMessage, show_message
from galaxies.settlement import Settlement
from galaxies.people.player import Player
from galaxies.politics.political_entity import PoliticalEntity
from galaxies.missions.mission import DONE, Mission
from galaxies.missions.deliver_ore import DeliverOre
from spaceships.ship_configurations.ths_miner import TwsMiner
from spaceships.ship_configurations.ths_shabby_miner import ShabbyTwsMiner
from spaceships.ship_configurations.ths_versatile import TwsVersatile
from ..person import Person
from ..conversation import Conversation


class SettlementOnLeaving(Conversation):
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

        standing = self.player._standing()
        if standing is None:
            raise Exception("No standing available.")
        if self.settlement.player_reputation_on_entering is None:
            raise Exception("No reputation recorded on entering.")
        entity: PoliticalEntity = standing.entity
        self.old_rep: float = self.settlement.player_reputation_on_entering
        self.new_rep: float = self.player.reputation
        old_title: str = entity.title_for(self.old_rep)
        new_title: str = entity.title_for(self.new_rep)
        self.title_has_improved: bool = self.old_rep < self.new_rep and old_title != new_title

        self.title: str = "Good news" if self.title_has_improved else "Not ready yet"

    def start(self) -> None:
        if not self.title_has_improved and self.settlement.handling_due_at is None:
            self._decide(True)
            return

        it: str = self.generate_introduction_text()
        speaker: str = f"{self.interlocutor.role.name} {self.interlocutor.surname} speaks.\n\n"

        title_improved_text: str = self._higher_title_effects(self.old_rep) if self.title_has_improved else ''

        if self.settlement.dockmaster is None:
            raise Exception("No dockmaster.")
        not_ready_text: str = '' if self.settlement.handling_due_at is None \
            else (
                f"{self.settlement.dockmaster.role.name} {self.settlement.dockmaster.surname} says"
                " the ship is not ready yet. Do you want to leave anyway?"
                )

        text: str = speaker + it + (title_improved_text if self.title_has_improved else not_ready_text)

        buttons: List[str] = ['Ok'] if self.title_has_improved else ['Yes', 'No']

        self.show(Message(
                title=self.title,
                text=text,
                buttons=buttons,
                open_sound='radio_open'
                ), self._answered
            )

    def _higher_title_effects(self, old_rep: float) -> str:
        new_title: str = self.player.get_title()
        if old_rep < 10:
            self.player.ship.change_cargo_hold(ShabbyTwsMiner.StandardHold)
            return (
                f"You have proven you can do the job without wasting mines.\n\n"
                f"We decided to repair your cargo hold... {self.interlocutor.get_player_title()}.\n\n"
                f"{"Long live the Community.\n\n" if self.interlocutor.loyalty100 > 5 else ''}"
                )
        elif old_rep < 20 or isinstance(self.player.ship.cargo_hold, ShabbyTwsMiner.ShabbyHold):
            # The effect is the availability of missions.
            return (
                "We have spoken about you and think can trust you to do something more than collect ore.\n\n"
                "Anytime you want, check the mission board of any outpost. But be careful you really can"
                " do the thing.\n\n"
                f"Long live the Community... {self.interlocutor.get_player_title()}\n\n" \
                   if self.interlocutor.loyalty100 > 5 else ''
                )
        elif old_rep < 50 or isinstance(self.player.ship.cargo_hold, ShabbyTwsMiner.StandardHold):
            self.player.ship.change_cargo_hold(ShabbyTwsMiner.ExtendedHold)
            return (
                f"You are doing the best of your ship... {self.interlocutor.get_player_title()}. Really.\n\n"
                f"We found a cargo extension you could use.\n\n"
                f"Keep doing the good job.\n\n"
                f"{"Long live the Community.\n\n" if self.interlocutor.loyalty100 > 5 else ''}"
                )
        elif old_rep < 100 or isinstance(self.player.ship, ShabbyTwsMiner):
            self.player.ship.upgrade_to(TwsMiner)
            return  (
                "People were asking why you still have to go around with that piece of..."
                f" no offense intended, {self.interlocutor.get_player_title()}.\n\n"
                "We consulted and the Community thinks you deserve a modern THS miner.\n\n"
                "It has better batteries and a connector for solar panels, you can recharge around the sun."
                " If you dare.\n\n"
                "Take care of it, will you?\n\n"
                f"{"Long live the Community.\n\n" if self.interlocutor.loyalty100 > 5 else ''}"
                )
        elif old_rep < 200 and 'Versatile Asked' not in self.player.flags:
            self.player.flags.add('Versatile Asked')
            done: List[Mission] = [m for m in self.player.missions if m.status == DONE]
            ore_factor: float = sum(isinstance(m, DeliverOre) for m in done) / len(done) if done else 1.0
            if ore_factor <= 0.5:
                self.show(Message(
                    title=self.title,
                    text=(
                        f"If looks like you have been doing much more than just mining ore... {new_title}."
                        "All according to The Three Aspects, though. Very well!\n\n"
                        "Maybe you could use a... more versatile ship, Pilot? One with less cargo capacity, about"
                        " the half. But more acceleration and containers for life support. And a bit more robust.\n\n"
                        " You decide, Pilot, you know better how you can serve."
                    ),
                    buttons=['Yes, please', 'No, thanks.'],
                    ), self._versatile_answered
                )
            return f"{"Long live the Community.\n\n" if self.interlocutor.loyalty100 > 5 else ''}"

        return f"People are starting to call you {self.player.get_title()}..."

    def _answered(self, chosen_button: Optional[int]) -> None:
        self._decide(chosen_button == 0)

    def _versatile_answered(self, chosen_button: Optional[int]) -> None:
        if chosen_button == 0:
            self.player.ship.upgrade_to(TwsVersatile)
        self._decide(True)

    def _decide(self, leaves: bool) -> None:
        self.close()
        self.on_decided(leaves)
