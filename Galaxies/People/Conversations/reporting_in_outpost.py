from typing import List, Optional
from datetime import datetime

import logging

import game_environment as gem
from Dialogs.messages import show_message
from Galaxies.Politics.political_entity import PoliticalEntity
from Galaxies.outpost import Outpost
from Spaceships.ship import Ship
from ..player import current_player as player
from ..person import Person
from ..conversation import Conversation

logger = logging.getLogger(__name__)

class ReportingInOutpost(Conversation):
    def __init__(self, interlocutor: Person, outpost: Outpost):
        super().__init__(interlocutor)
        self.outpost: Outpost = outpost
        self.title: str =  f'Outpost "{outpost.name}", Communication Officer {interlocutor.name} {interlocutor.surname}'

    def start(self) -> None:
        visit_time_delta: Optional[float] = None if not self.outpost.last_visited\
            else (self.date_time - self.outpost.last_visited).total_seconds()

        if player.ship.cargo_hold.ore > 0:
            self.greet_and_thank(visit_time_delta)
        elif visit_time_delta > 60 * 60:
            logger.error("Dialog not implemented yet: self.greet_and_warn(visit_time_delta)")
        elif visit_time_delta >= 0:
            logger.error("Dialog not implemented yet: self.greet_why_back()")

    def greet_and_thank(self, time_since_last_visit: Optional[datetime]) -> None:
        from Galaxies.People.player import current_player as player

        if self.interlocutor.last_communication_at and (gem.current_environment.date_time - self.interlocutor.last_communication_at).total_seconds() > 28 * 24 * 60 * 60:
            self.say_had_not_seen_you_thanks(time_since_last_visit)
        elif self.interlocutor.last_communication_at:
            logger.error("Dialog not implemented yet: say_hi_again_and_thanks")
        elif time_since_last_visit:
            self.say_i_am_and_thanks(time_since_last_visit)
        else:
            self.say_this_is_and_thanks(time_since_last_visit)

    def say_had_not_seen_you_thanks(self, time_since_last_visit: int) -> None:
        # Prepare the text:
        introduction: str = str()
        if self.interlocutor.empathy100 < 0.2 or self.interlocutor.sympathy100 < 20:
            introduction += f"I thought you were dead.\n\n"
        elif self.interlocutor.empathy100 > 0.8 or self.interlocutor.sympathy100 > 80:
            introduction += f"Hello there! Long time no see.\n\n"
        else:
            introduction += f"Welcome back, pilot.\n\n"

        entity: PoliticalEntity = self.outpost.planet.parent_orbit.parent_stellar_system.political_entity
        if entity == PoliticalEntity.THOSE_WHO_SHARE:
            title = entity.title_for(player.those_who_share.reputation * self.interlocutor.sympathy100 * 2)
        else:
            logger.warning("Unknown political entity.")
            title = str()
        wants_to_chat: bool = self.interlocutor.sociability100 + self.interlocutor.sympathy100 > 100    
        text: str = (
            f"{introduction}"
            f"Thank you for sharing, {title}."
            f"{" You know if helps a lot." if self.interlocutor.loyalty100 > 50 else str()}"
            f"{"\n\nHow are you doing?" if wants_to_chat else "\n\nLong live the Community."}"
            )

        # Prepare the buttons:
        buttons = [
                {
                'text': 'Long live',
                'reputation': 0.01,
                }
                , {
                'text': '(Chat)' if wants_to_chat else 'Thank you for sharing',
                'sympathy': 5,
                }
            ]
        
        show_message(
            self.prepare_message(self.title, text, buttons),
            on_result=lambda button_index: self.finish(time_since_last_visit, button_index, buttons)
            )
        # If no chat, the next-best is Long live, as answer to long live.

    def say_i_am_and_thanks(self, time_since_last_visit: int) -> None:
        # Prepare the message:
        presentation: str = \
            f"I am {self.interlocutor.get_full_name()}" \
            if self.interlocutor.loyalty100 - self.interlocutor.empathy100 > 0 \
            else f"I am {self.interlocutor.name}, the ComOfficer here." \
            if self.interlocutor.empathy100 > 80\
            else f"I am ComOfficer {self.interlocutor.name} {self.interlocutor.surname}"
        
        text: str = (
            f"{presentation}"
            f"\n\nThank you for the ore, {player.get_title()}."
            f"{" It helps immensely." if self.interlocutor.loyalty100 > 10 else str()}"
            f"{"\n\nLong live the Community." if self.interlocutor.loyalty100 > 10 else str()}"
            )

        # Prepare the buttons: If disloyal, will appreciate a "wrong" answer.
        buttons = [
                {
                'text': 'Long live',
                'reputation': 0.01 if self.interlocutor.loyalty100 > 10 else 0,
                'sympathy': 0.1 if self.interlocutor.loyalty100 > 10 else -2,
                }
                , {
                'text': 'Thank you for sharing',
                'sympathy': 0 if self.interlocutor.loyalty100 > 10 else 5, # Took the hint
                }
            ]

        show_message(
            self.prepare_message(self.title, text, buttons),
            on_result=lambda button_index: self.finish(time_since_last_visit, button_index, buttons)
            )

    def say_this_is_and_thanks(self, time_since_last_visit: int) -> None:
        # Prepare the message:
        presentation: str = \
            f"I am {self.interlocutor.get_full_name()}" \
            if self.interlocutor.loyalty100 - self.interlocutor.empathy100 > 0 \
            else f"I am {self.interlocutor.name}, the ComOfficer here." \
            if self.interlocutor.empathy100 > 80\
            else f"I am ComOfficer {self.interlocutor.name} {self.interlocutor.surname}"
        
        text: str = (
            f"{presentation}"
            f"\n\nThank you for sharing the ore, {player.get_title()}."
            f"{" It helps immensely." if self.interlocutor.loyalty100 > 10 else str()}"
            f"\n\nWe will now replenish your resources and repair your ship."
            f"{"\n\nLong live the Community." if self.interlocutor.loyalty100 > 10 else str()}"
            )

        # Prepare the buttons: If disloyal, will appreciate a "wrong" answer.
        buttons = [
                {
                'text': 'Long live',
                'reputation': 0.01 if self.interlocutor.loyalty100 > 10 else 0,
                'sympathy': 0.1 if self.interlocutor.loyalty100 > 10 else -2,
                }
                , {
                'text': 'Thank you for sharing',
                'sympathy': -1 if self.interlocutor.loyalty100 > 10 else 10, # Took the hint
                }
            ]

        show_message(
            self.prepare_message(self.title, text, buttons),
            on_result=lambda button_index: self.finish(time_since_last_visit, button_index, buttons)
            )

    def finish(self, time_since_last_visit: Optional[int], chosen_button: int, consequences: dict) -> ReportingInOutpost:
        status = player.those_who_share
        ship = player.ship
        cargo_hold = ship.cargo_hold
        my_consequences: dict = consequences[chosen_button]

        if 'reputation' in my_consequences:
            status.reputation += my_consequences['reputation']
        if 'sympathy' in my_consequences and my_consequences['sympathy'] != 0:
            self.interlocutor.adjust_sympathy(my_consequences['sympathy'])

        # Reputation loss = need of stuff.
        rep_loss_maintenance = -((0.8 - ship.maintenance) if ship.maintenance < 0.8 else 0) * 12
        rep_loss_energy = -(1e12 - ship.energy) * 5e-13 # W/o laser or acc, negligible...
        rep_loss_air = -(28 - ship.cargo_hold.air) * 0.0006
        rep_loss_water = -(28 - ship.cargo_hold.air) * 0.0003
        rep_loss_food = -(28 - ship.cargo_hold.air) * 0.0006

        ship.maintenance = 0.8 if ship.maintenance < 0.8 else ship.maintenance
        ship.energy = 1e12
        cargo_hold.air = 28
        cargo_hold.water = 28
        cargo_hold.food = 28

        # Reputation loss due to mines:
        rep_loss_mines = -0.20 * (5 - cargo_hold.mines)
        cargo_hold.mines = 5

        # Reputation gain: ore
        rep_gain_ore = 0.02 * cargo_hold.ore
        cargo_hold.ore = 0

        rep_loss = rep_loss_maintenance \
            + rep_loss_energy \
            + rep_loss_air \
            + rep_loss_water \
            + rep_loss_food \
            + rep_loss_mines

        rep_change = rep_loss + rep_gain_ore

        logger.debug(
            "Reputation changes:"
            f"\n * Maintenance: {rep_loss_maintenance:.6f}"
            f"\n * Energy: {rep_loss_energy:.6f}"
            f"\n * Air: {rep_loss_air:.6f}"
            f"\n * Water: {rep_loss_water:.6f}"
            f"\n * Food: {rep_loss_food:.6f}"
            f"\n * Mines: {rep_loss_mines:.6f}"
            f"\n   Total loss: {rep_loss:.6f}"
            f"\n * Ore: {rep_gain_ore:.6f}"
            )

        if rep_change > 0.0:
            self.interaction_lines.append("Came with enough ore.")
        if time_since_last_visit is not None and time_since_last_visit > 60*60 and rep_gain_ore <= 0:
            self.interaction_lines.append("Came with no ore.")

        status.reputation += rep_change

        self.close(self.interaction_lines)
        return self
    