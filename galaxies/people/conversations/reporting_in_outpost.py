from typing import List, Optional
from datetime import datetime

import logging

import game_environment as gem
from common.dialogs.messages import show_message
from galaxies.politics.political_entity import PoliticalEntity
from galaxies.outpost import Outpost
from spaceships.ship import Ship
from ..player import current_player as player
from ..person import Person
from ..conversation import Conversation

logger = logging.getLogger(__name__)

class ReportingInOutpost(Conversation):
    def __init__(self, interlocutor: Person, outpost: Outpost):
        super().__init__(interlocutor)
        self.outpost: Outpost = outpost
        self.title: str =  f'Outpost "{outpost.name}", Communication Officer {interlocutor.name} {interlocutor.surname}'
        self.time_since_last_visit: Optional[float] = None if not self.outpost.last_visited\
            else (self.date_time - self.outpost.last_visited).total_seconds()

    def start(self) -> None:
        visit_time_delta: Optional[float] = None if not self.outpost.last_visited\
            else (self.date_time - self.outpost.last_visited).total_seconds()

        if player.ship.cargo_hold.ore > 0:
            self.greet_and_thank()
        elif visit_time_delta is None or visit_time_delta > 60 * 60:
            self.greet_and_warn()
        elif visit_time_delta >= 0:
            self.greet_why_back()

    # region Greet and thank
    def greet_and_thank(self) -> None:
        if self.interlocutor.last_communication_at and (gem.current_environment.date_time - self.interlocutor.last_communication_at).total_seconds() > 28 * 24 * 60 * 60:
            self.say_had_not_seen_you_thanks()
        elif self.interlocutor.last_communication_at:
            self.say_hi_again_and_thanks()
        elif self.time_since_last_visit:
            self.say_i_am_and_thanks()
        else:
            self.say_this_is_and_thanks()

    def say_had_not_seen_you_thanks(self) -> None:
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
            title = self.interlocutor.get_player_title(player)
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
        # If no chat, the next-best is Long live, as answer to long live.
        buttons = [
                {
                'text': 'Long live',
                'reputation': 0.01,
                }
                , {
                'text': '(Chat)' if wants_to_chat else 'Thank you for sharing',
                'sympathy': 5 if wants_to_chat else 0,
                }
            ]
        
        show_message(
            self.prepare_message(self.title, text, buttons),
            on_result=lambda button_index: self.finish(None, button_index, buttons)
            )

    def say_hi_again_and_thanks(self) -> None:
        # Prepare the message:
        presentation: str = \
            f"Welcome back, {player.get_title()} Pilot." \
            if self.interlocutor.loyalty100 - self.interlocutor.empathy100 > 0 \
            else f"Hello again, friend." \
            if self.interlocutor.empathy100 > 80\
            else f"Welcome back, {player.get_title()}."
        
        text: str = (
            f"{presentation}"
            f"\n\nThank you for the ore."
            f"{" It helps immensely." if self.interlocutor.loyalty100 > 10 else " As they say."}"
            f"{"\n\nLong live the Community." if self.interlocutor.loyalty100 > 10 else str()}"
            )

        # Prepare the buttons: If disloyal, will appreciate "wrong" answers.
        # This can be later a path for chatting rebellion.
        buttons = [
                {
                'text': 'Long live',
                'reputation': 0.01 if self.interlocutor.loyalty100 > 10 else 0,
                'sympathy': 0.5 if self.interlocutor.loyalty100 > 10 else -2,
                }
                , {
                'text': 'Thank you for sharing',
                'sympathy': 0.1 if self.interlocutor.loyalty100 > 10 else -0.5,
                }
                , {
                'text': 'Yeah. Whatever.',
                'sympathy': -0.5 if self.interlocutor.loyalty100 > 10 else 10,
                }
            ]

        show_message(
            self.prepare_message(self.title, text, buttons),
            on_result=lambda button_index: self.finish(button_index, buttons)
            )

    def say_i_am_and_thanks(self) -> None:
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
            on_result=lambda button_index: self.finish(button_index, buttons)
            )

    def say_this_is_and_thanks(self) -> None:
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
                , {
                'text': 'What about getting some cash?',
                'reputation': -0.5 if self.interlocutor.loyalty100 > 10 else 0,
                'sympathy': -5 if self.interlocutor.loyalty100 > 10 else 10,
                }
            ]

        show_message(
            self.prepare_message(self.title, text, buttons),
            on_result=lambda button_index: self.say_what_the_fuck(button_index, buttons)
            )

    def say_what_the_fuck(self, chosen_button: int, consequences: dict) -> ReportingInOutpost:
        if chosen_button == 2:
            subjective_title = self.interlocutor.get_player_title(player)
            # Prepare the text:
            text: str = f"That's a... joke?"
            text += f"\n\nDon't make such jokes, {subjective_title}."
            if self.interlocutor.loyalty100 < 10:
                text += f"\n\nI mean... I *personally* don't mind but... better not."

            # Prepare the buttons: Here I can pass on or even change the consequences :)
            only_button = consequences[2]
            only_button['text'] = 'Ok, nevermind'
            buttons = [ only_button ]

            show_message(
                self.prepare_message(self.title, text, buttons),
                on_result=lambda button_index: self.finish(button_index, buttons)
                )
            return self
    
        self.finish(chosen_button, consequences)
        return self

    # endregion

    def greet_and_warn(self) -> None:
        from galaxies.people.player import current_player as player

        subjective_title = self.interlocutor.get_player_title(player)

        # Prepare the text:
        salutation = None
        if self.interlocutor.loyalty100 - self.interlocutor.empathy100 > 0:
            salutation = f"Greetings, Pilot."

        presentation = None
        if not self.interlocutor.last_communication_at:
            if self.interlocutor.loyalty100 - self.interlocutor.empathy100 > 0:
                presentation = f"I am {self.interlocutor.get_full_name()}"
            elif self.interlocutor.empathy100 > 80:
                presentation = f"I am {self.interlocutor.name}, the ComOfficer here."
            else:
                presentation = f"\n\nI am ComOfficer {self.interlocutor.name} {self.interlocutor.surname}"

        is_conspiratory = self.interlocutor.loyalty100 < 20 and self.interlocutor.sociability100 > 80 and self.interlocutor.sympathy100 > 40

        warning = None
        if self.interlocutor.sympathy100 > 80:
            warning = f"No luck this time, hey, {subjective_title}?"
        elif is_conspiratory:
            warning = f"You bring no ore... look, I won't judge if you... but if you are not careful, they will take away you ship. Welcome to Those-Who-Share, you know what I mean?"
        elif player.those_who_share.reputation > 50:
            warning = f"No ore this time. Don't worry, we know you, {subjective_title}."
        elif player.those_who_share.reputation > 10:
            warning = f"No ore this time. Pity"
        else:
            warning = f"You bring no ore, {subjective_title}. Please remember that you license will be revoked if you do not use what you are shared to help."

        bye = None
        if is_conspiratory:
            schedule = None
            if self.outpost.staff.index(self.interlocutor) < 3:
                shift_start = 8 * self.outpost.staff.index(self.interlocutor)
                schedule = f"{shift_start}:00 to {shift_start + 8}:00"
            else:
                schedule = "time to time"
            bye = f"Be careful. I work here from {schedule}. Maybe we talk more one day."
        else:
            bye = f"Long live the Community."

        text:str = salutation
        if presentation:
            text += f"\n\n{presentation}"
        text += f"\n\n{warning}"
        text += f"\n\nWe will now replenish your resources and repair your ship."
        text += f"\n\n{bye}"

        # Prepare the buttons: If disloyal, will appreciate a "wrong" answer.
        buttons = [
                {
                'text': 'Thank you for sharing.',
                'sympathy': 0.02 if self.interlocutor.loyalty100 > 10 else 0,
                }
                , {
                'text': 'Whatever',
                'reputation': -0.1,
                'sympathy': -5 if self.interlocutor.loyalty100 > 10 else -1,
                }
            ]
        if is_conspiratory:
            buttons.append(
                {
                'text': 'Got it. Thank you.',
                'sympathy': 5,
                }
            )

        show_message(
            self.prepare_message(self.title, text, buttons),
            on_result=lambda button_index: self.finish(button_index, buttons)
            )

    def greet_why_back(self) -> None:
        from galaxies.people.player import current_player as player
        subjective_title = self.interlocutor.get_player_title(player)

        # Prepare the text:
        text:str = f"\n\nDo you want something, {subjective_title}?"

        # Prepare the buttons: If disloyal, will appreciate a "wrong" answer.
        buttons = [
                {
                'text': '<Ask about Those-Who-Share>',
                }
                , {
                'text': '<Ask about places outside Those-Who-Share>',
                }
                , {
                'text': 'Nevermind.',
                }
            ]

        show_message(
            self.prepare_message(self.title, text, buttons),
            on_result=lambda button_index: self.say_about_politics(button_index, buttons)
            )

    def say_about_politics(self, button_index: int, _) -> None:
        # Prepare the text:
        if button_index == 0:
            if self.interlocutor.sociability100 > 30:
                if self.interlocutor.loyalty100 > 80:
                    text = (
                        "We are great, aren't we? A Community growing together, caring about each other, expanding."
                        " Look at you. You wanted to ride a spaceship throught the stars. And here you are."
                        " We shared it with you. From each according to ability, to each according to needs."
                        " And our industry is unmatched."
                    )
                elif self.interlocutor.loyalty100 > 10:
                    text = (
                        "It's home, isn't it? We care about each other, we grow together. Look at you: you wanted"
                        " a ship - there you are. It may not be exciting or glorious but that also means you sleep at"
                        " night without asking yourself if you will earn your air tomorrow."
                    )
                elif self.interlocutor.loyalty100 < 10 and self.interlocutor.sympathy100 > 60:
                    text = (
                        "What do you want me to say? I don't 'feel' the Community as others do. They say they help"
                        " each other but is it help if you are constantly reminded to work harder, do more? And"
                        " what, so that people call you 'Speaker'? Who the fuck cares?"
                    )
                else:
                    text = (
                        "It's ok. There is worse. I guess. Look, I have to work."
                    )
            else:
                if self.interlocutor.loyalty100 > 80:
                    text = (
                        "From each according to ability, to each according to needs.\n\nWe are great."
                    )
                elif self.interlocutor.loyalty100 > 10:
                    text = ("It's home. And nobody has to be afraid about how to get some air.")
                elif self.interlocutor.loyalty100 < 10 and self.interlocutor.sympathy100 > 60:
                    text = ("I think you know what I think. Shithole.")
                else:
                    text = ("It's ok, I guess.")
        elif button_index == 1:
            if self.interlocutor.sociability100 > 30:
                if self.interlocutor.loyalty100 > 80:
                    text = (
                        "I don't care so much. United Diversity is powerful, they scare me a bit, with their"
                        " Militarists and tech moguls. But they let us in peace, so... it's ok, I guess."
                        "\n\nAnd I am not a soap opera fan, so... yeah, Shining Throne has beautiful things, but"
                        " below that you have millions of slaves and serfs, so fuck them, I'd say. Barbarians."
                    )
                elif self.interlocutor.loyalty100 > 10:
                    text = (
                        "They are strange places, yes?"
                        "\n\nUnited Diversity has so much industry, and they have this big 'armed forces', as"
                        " they call them, in case an Exterminating Mother appears again. But all the time"
                        " about money, money, money... I don't know. Scary."
                        "\n\nI like the Shining Throne's soap operas, as everybody. They have so many beautiful"
                        " things there! The arcades, the dresses... even the cutlery is beautiful!"
                        "\n\nBut to live all the time thinking about honor and so... and most are 'serfs' and'"
                        " 'servants', that's for sure not so nice as to be a member of the 'aristocracy'."
                    )
                elif self.interlocutor.loyalty100 < 10 and self.interlocutor.sympathy100 > 60:
                    text = (
                        "Well, the places where you have a chance, no?"
                        "\n\nIn United Diversity, you can be creative and bold, get rich. Or you can make a career"
                        " in the armed forces. You get real recognition, go around in your own vehicles, party"
                        " with whomever you want. A land of opportunity."
                        "\n\nAnd the Shining Throne? Only a sucker would remain a serf, that is the place for"
                        " Glory! Do great deeds, be a henchman, be knighted, live wonderful things... maybe even"
                        " meet the Emperor one day!"
                    )
                else:
                    text = (
                        "United Diversity believes in federalism, wealth and protection. It's their stuff."
                        "\n\nThe Shining Throne, well, you know the soap operas, yes? Glory, knights and so on."
                        "\n\nWe are just Those-Who-Share. We build stuff."
                    )
            else:
                if self.interlocutor.loyalty100 > 80:
                    text = (
                            "UniDiv is a bunch of wealth-obsessed militaristic morons lost in the glories"
                            " of the past. And the Shining Throne is a bunch of cruel kids playing soap opera."
                            " There is not much more to say."
                        )
                elif self.interlocutor.loyalty100 > 10:
                    text = (
                            "UniDiv if scary, so much military and greedy people. But they leave us in peace."
                            "\n\nThe Shining Thone is beautiful, but think about all those poor slaves."
                        )
                elif self.interlocutor.loyalty100 < 10 and self.interlocutor.sympathy100 > 60:
                    text = (
                            "I think you know what I think. In UniDiv you can be yourself. In the Throne, a hero."
                            "\n\nHere? 'Champion of the Revolution'. And live in the same quarters than everybody."
                            "\n\nGreat."
                        )
                else:
                    text = ("They have also their problems, I guess.")
        else:
            logger.debug(f"Reputation: {player.those_who_share.reputation}")
            logger.debug(f"Sympathy: {self.interlocutor.sympathy100}")
            self.close(self.interaction_lines)
            return
        
        # Prepare the buttons:
        buttons = [
                {
                'text': 'Long live the Community',
                'sympathy': 1 if self.interlocutor.loyalty100 > 80 else 0
                }
            ]
        if self.interlocutor.loyalty100 < 10:
            buttons.append(
                {
                'text': 'Thank you for your honesty.',
                'sympathy': 5 if self.interlocutor.sociability100 > 50 else 2
                }
            )

        show_message(
            self.prepare_message(self.title, text, buttons),
            on_result=lambda button_index: self.finish(button_index, buttons)
            )

    def finish(self, chosen_button: int, consequences: dict) -> ReportingInOutpost:
        status = player.those_who_share
        ship = player.ship
        cargo_hold = ship.cargo_hold
        my_consequences: dict = consequences[chosen_button]

        if 'reputation' in my_consequences:
            status.reputation += my_consequences['reputation']
        if 'sympathy' in my_consequences and my_consequences['sympathy'] != 0:
            self.interlocutor.adjust_sympathy(my_consequences['sympathy'])

        # Reputation loss = need of stuff.
        rep_loss_maintenance = -((0.8 - ship.maintenance) if ship.maintenance < 0.8 else 0) * 24
        rep_loss_energy = -(ship.energy_max - ship.energy) * 5e-13 # W/o laser or acc, negligible...
        rep_loss_air = -(28 - ship.cargo_hold.air) * 0.0006
        rep_loss_water = -(28 - ship.cargo_hold.air) * 0.0003
        rep_loss_food = -(28 - ship.cargo_hold.air) * 0.0006

        ship.maintenance = 0.8 if ship.maintenance < 0.8 else ship.maintenance
        ship.energy = ship.energy_max
        cargo_hold.air = 28
        cargo_hold.water = 28
        cargo_hold.food = 28

        # Reputation loss due to mines:
        rep_loss_mines = -0.20 * (5 - cargo_hold.mines)
        cargo_hold.mines = 5

        # Reputation gain: ore
        rep_gain_ore = 0.01 * cargo_hold.ore
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
            f"\n   Grand Total: {rep_change:.6f}"
            )

        if rep_change > 0.0:
            self.interaction_lines.append("Came with enough ore.")
        if self.time_since_last_visit is not None and self.time_since_last_visit > 60*60 and rep_gain_ore <= 0:
            self.interaction_lines.append("Came with no ore.")

        status.reputation += rep_change

        self.close(self.interaction_lines)
        return self
    