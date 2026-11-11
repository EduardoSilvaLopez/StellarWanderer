"""A conversation of the settlement's chat (the Chat option of the settlement screen): started by a conversation tag,
with the person selected in the list. It writes into the chat's log (chat_log.py), never into a dialog window.

The texts are written with `say` (the person's line, whose expressions that are tags of `reactions` make new tags) and
the replies with `offer` (the callback gets the index of the reply the player chose). The conversation dies out
when it offers nothing more: the player then starts the next one from a tag, in the same log. `start` says the tag
as the pilot's line, then the answer (for the presentation tag, the pilot's line is Player.present_yourself).
Flags can be written to mark important events of the conversation.

Note for Claude: before writing or reworking a `talk_*` method here, read common/design/settlement_chat_method_howto.md
(the rules, the pattern to follow and how to test). Do not read it for any other task.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
import random
from datetime import date, datetime, timedelta
from typing import Callable, List, Optional

import logging
from galaxies.people.chat_log import NPC, PLAYER, ChatLog, parse_marks
from galaxies.people.conversation import Conversation
from galaxies.people.person import Person
from galaxies.people.role import COORDINATOR, KOMISAR, RINGMASTER
from galaxies.people.player import Player
from galaxies.politics import political_entity
from galaxies.portals.portal_base import PortalBase
from galaxies.settlement import Settlement
from common.prices import at_date

# A political text: its three tones, in the order -1, 0, 1.
PoliticalTexts = tuple[str, str, str]
# The text of a topic for one tone: one text, or a tuple of alternatives of which one is picked at random.
PoliticalText = str | tuple[str, ...]
# A topic: its relevance score, a short line per tone for the low-sociability replies, and a text per tone.
PoliticalTopics = dict[str, tuple[float, PoliticalTexts, tuple[PoliticalText, PoliticalText, PoliticalText]]]

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from galaxies.settlement import Settlement

# Flags of the Those-Who-Share standing, each followed by the seed of the system (see ore_mine._sells_for_credits).
SOLD_FLAG = "sold mine codes"
RATTED_FLAG = "ratted ore smugglers"
RAT_REPUTATION = 500.0  # what the pilot gains for denouncing the smugglers
OWNER_FLAG = "owner of the ship"  # a flag of the pilot (Player.flags) once the ship is bought from the Ringmaster

def pretty_date(dt: datetime) -> str:
    ordinal: str = ''
    if 11 <= dt.day <= 13:
        ordinal = f"{dt.day}th"
    else:
        match dt.day % 10:
            case 1:
                ordinal = f"{dt.day}st"
            case 2:
                ordinal = f"{dt.day}nd"
            case 3:
                ordinal = f"{dt.day}rd"
            case _:
                ordinal = f"{dt.day}th"

    return f"{dt.strftime('%B')} {ordinal}"


def founding_when(founded: datetime, now: datetime) -> str:
    """How long ago a settlement was founded, as a talk says it: 'this year', 'last year', 'two years ago'... up to four
    years, and the year itself from five years on."""
    years: int = now.year - founded.year
    words: dict[int, str] = {0: 'this year', 1: 'last year', 2: 'two years ago', 3: 'three years ago',
                             4: 'four years ago'}
    return words.get(years, str(founded.year))

def portal_arrival(place: Settlement) -> datetime:
    """When the Portal of the place's system came, which is when the portal base was founded: the day that every
    settlement of the system celebrates as the star's ('Happy star')."""
    arrival: datetime | None = place.stellar_system.founded_at
    assert arrival is not None  # a settlement only exists in a system with a history, which founds it
    return arrival

class SettlementChat(Conversation):
    def __init__(self, place: Settlement, player: Player, interlocutor: Person, log: ChatLog, tag: str) -> None:
        super().__init__(player, interlocutor)
        self.place: Settlement = place
        self.log: ChatLog = log  # the chat of the settlement screen: the texts go there
        self.tag: str = tag  # the conversation tag that started this conversation
        self.reactions: dict[str, Callable[[], str]] = self.reactions_index()
        self.flags = interlocutor.interactions.setdefault(self.date_time.replace(microsecond=0), [])
        self.remember()

    def start(self) -> None:
        """The tag is said by the pilot first, as a line of the chat, then the person answers it. The presentation tag
        is the exception: the pilot says what Player.present_yourself gives, not the tag."""
        has_met_before: bool = any("Presented himself." in lines for lines in self.interlocutor.interactions.values())
        is_presentation: bool = self.tag == Player.PRESENTATION_TAG

        pilot_line = \
            self.player.present_yourself_first_time() if is_presentation and not has_met_before \
            else self.player.present_yourself_further_times(self.interlocutor) if is_presentation \
            else self.tag
        self.log.add(PLAYER, [[(word, None) for word in pilot_line.split()]])
        reaction: Optional[Callable[[], str]] = next(
            (talk for tag, talk in self.reactions.items() if tag.lower() == self.tag.lower()), None
        )
        self.say(reaction if reaction is not None else self.talk_unknown_tag)

    def remember(self) -> None:
        """Writes the interaction into the person's record now, not only when the conversation closes, so a save made
        while the chat is open keeps it."""
        self.interlocutor.last_communication_at = self.date_time
        self.interlocutor.record()

    def say(self, generator: Callable[[], str]) -> None:
        """The person says `text` in the chat. The expressions of `text` that are tags of the reactions become the
        pilot's conversation tags, from now on. Time passes."""
        import game_environment as gem
        gem.current_environment.clock.advance(60)

        text: str = generator()
        words, tags = parse_marks(text, self.reactions.keys())
        self.player.conversation_tags.update(tags)
        self.log.add(NPC, words)
        self.remember()

    def offer(self, labels: List[str], then: Optional[Callable[[int], object]] = None) -> None:
        """Offers the player `labels` as replies. Choosing one calls `then` with its index; with no labels, the
        conversation has nothing more to say."""
        self.log.offer(labels, then)

# region Presentation
    def reactions_index(self) -> dict[str, Callable[[], str]]:
        return {
            Player.PRESENTATION_TAG: self.talk_present_yourself,
            'asteroids': self.talk_asteroid,
            'base': self.talk_base,
            'belt': self.talk_belt,
            'bureaucrat': self.talk_bureaucrat,
            'communication officer': self.talk_communication_officer,
            'captain': self.talk_protection,
            'coordinator': self.talk_coordinator,
            'credits': self.talk_credits,
            'credits for the ship': self.traitor_credits_for_the_ship,
            'custorian thirds': self.talk_custodian_thirds,
            'dockmaster': self.talk_dockmaster,
            'engineer': self.talk_engineer,
            'Founders': self.talk_founders,
            'gunner': self.talk_gunner,
            'Happy birthday': self.talk_happy_birthday,
            'Happy founding': self.talk_happy_founding,
            'Happy star': self.talk_happy_star,
            'Happy new year': self.talk_happy_new_year,
            'hobby': self.talk_hobby,
            'janitor': self.talk_janitor,
            'job': self.talk_job,
            'komisar': self.talk_komisar,
            'life': self.talk_life,
            'noobie': self.talk_noobie,
            'outpost': self.talk_outpost,
            'Paladin Xi': self.talk_paladin_xi,
            'PGMs': self.talk_pgms,
            'portal': self.talk_portal,
            'researcher': self.talk_researcher,
            'ringmaster': self.talk_ringmaster,
            'security': self.talk_protection,
            'smith': self.talk_smith,
            'space': self.talk_space,
            'stevedore': self.talk_stevedore,
            'Surnemals': self.talk_surnemals,
            'the network': self.talk_the_network,
            'The Shining Throne': self.talk_the_shining_throne,
            'Those-Who-Share': self.talk_those_who_share,
            'United Diversity': self.talk_united_diversity,
        }

    def talk_present_yourself(self) -> str:
        # On January 1st the person greets the pilot first, once a year; the greeting makes the tag 'Happy new year'.
        # The shy (sociability under 10) do not.
        now: datetime = self.date_time
        new_year_key: str = f"Happy new year {now.year}"
        greeting: str = ""
        if ((now.month, now.day) == (1, 1)
                and self.interlocutor.sociability100 >= 10
                and self.interlocutor.sympathy100 >= 20
                and not any(new_year_key in lines for lines in self.interlocutor.interactions.values())):
            self.flags.append(new_year_key)
            greeting = "Happy new year! "

        if not any("Presented himself." in lines for lines in self.interlocutor.interactions.values()):
            self.interlocutor.adjust_sympathy(1)
            self.flags.append("Presented himself.")
            return greeting + self.talk_present_yourself_first_time()
        return greeting + self.talk_present_yourself_further_times()

    def talk_present_yourself_first_time(self) -> str:
        # Short names to make the rest more legible
        title: str = self.interlocutor.get_title()
        role: str = self.interlocutor.role.name
        first: str = self.interlocutor.name
        last: str = self.interlocutor.surname
        rep: float = self.interlocutor.reputation
        loy: float = self.interlocutor.loyalty100
        emp: float = self.interlocutor.empathy100
        soc: float = self.interlocutor.sociability100
        sym: float = self.interlocutor.sympathy100
        you: str = self.interlocutor.address(self.player, to_player=True)  # how the person calls the pilot

        # Apolitical conversation: Loyalty is irrelevant, save the self presentation.
        # Player in situation of weakness (begs for attention): Empathy relevant.
        # Sociability always relevant, makes the reply less or more verbose.
        # Sympathy always relevant, rejection or approval of the player.
        is_grandiose = rep * (loy - emp) > 2500
        self_present: str = " ".join(x for x in \
            [
            title if is_grandiose or loy > 80 else None,
            role if is_grandiose or loy > 50 or emp > 50 else None,
            first,
            last if is_grandiose and emp < 50 else None,
            ] \
            if x is not None
        )
        noobie_or_not: str = 'the noobie' if self.date_time < datetime(year=700, month=7, day=1) \
            else you

        if emp < 20:
            if soc < 20:
                if sym < 20:
                    return "Leave me alone."
                elif sym < 80:
                    return "I know."
                else:
                    return "I know. Not so fond about living, are you?"
            elif soc < 80:
                if sym < 20:
                    return "You. What do you want?"
                elif sym < 80:
                    return f"{noobie_or_not.capitalize()}. We will see how much you last."
                else:
                    return (
                        f"I know, Paladin Xi's last discovery. {noobie_or_not.capitalize()}, eager to die in space..."
                        "Miner's job is hard. You will see <smiles a wicked smile>."
                    )
            else:  # noqa: PLR5501
                if sym < 20:
                    return "You. What do you want? Don't you think you have done enough?"
                elif sym < 80:
                    return (
                        f"Yeah, I know. {noobie_or_not}. We will see how much you last. Space is hard."
                        " Paladin Xi wants to rush things, wants everybody on board. He has killed already some."
                        " People like you."
                    )
                else:
                    return (
                        f"I know, Paladin Xi's last discovery. {noobie_or_not.capitalize()}, eager to die here..."
                        " Space is hard. You will see <smiles a wicked smile>."
                        "\n\nYou should not move away from orbit. Moon and planet. Ore and rocks. Don't be stupid."
                    )
        elif emp < 80:
            if soc < 20:
                if sym < 20:
                    return "Leave me alone, Pilot. You've done enough."
                elif sym < 80:
                    return "I know. Ehm... hi."
                else:
                    return "Heard about you. We're cool."
            elif soc < 80:
                if sym < 20:
                    return "You. Look, I don't want problems, ok? Just leave me alone. You've done enough."
                elif sym < 80:
                    return f"Hello, Pilot, I am {self_present}. How are you? How's life going?"
                else:
                    return (
                        f"Nice to meet you, {you}! How are you doing? How is space being to you?"
                        f"\n\nMe, I prefer to remain between the outpost and the portal base. Less risky, you know?"
                        f" And people are nice here."
                    )
            else:  # noqa: PLR5501 - High soc
                if sym < 20:
                    return (
                        "Oh, no, don't approach me, ok? I don't want troubles and you have done enough,"
                        " just leave me alone. You should think about your life."
                    )
                elif sym < 80:
                    return (
                        "So here we have you, Paladin Xi's last discovery. He wants everybody on space."
                        " Take care. It is unforgiving. No beacon signal can save you if you are too far away,"
                        " drifting between planets. Noobies get killed."
                    )
                else:
                    return (
                        f"Nice to meet you, {you}! How are you doing?"
                        " Be careful in space. It is hard. You can get yourself killed. Avoid the asteroid belts."
                        "\n\nBut if you build yourself a good basis of mines and then do some science work on rocks,"
                        " everything will be ok. Safe way to build up some reputation and then back home, yes?"
                        "\n\nLife's too precious to loose it so soon."
                    )
        else:  # noqa: PLR5501 - High emp
            if soc < 20:
                if sym < 20:
                    return "<Looks sadly at you, says nothing>"
                elif sym < 80:
                    return f"Ah... yeah. Cool. Name's {first}. {role.capitalize()}."
                else:
                    return "Oh, you! Cool. <shy smile>"
            elif soc < 80:
                if sym < 20:
                    return (
                        "Yes, I know who you are. And I know what you have done. Look... space is hard. I know."
                        " But... no. Just leave me alone, ok? Sorry."
                    )
                elif sym < 80:
                    return (
                        f"Hello, Pilot, I am {self_present}. How are you? How has space treated you lately?"
                        f"\n\nHow was crossing the portal, was it the first time?"
                        f"\n\nDo you need a coffee? I need a coffee!"
                    )
                else:
                    return (
                        f"Nice to meet you, {you}! Heard good things about you."
                        f"\n\nHow is space treating you? Paladin Xi is not a bad guy, but he is ruthless. I see"
                        f" the ships you people start with. Ugh."
                    )
            else:  # noqa: PLR5501 - High soc
                if sym < 20:
                    return (
                        "DON'T YOU DARE! Oh, don't you dare to approach me, no, no, I know the likes of you!"
                        " Just leave me alone, life here is hard enough, just go away and let me have my meal"
                        " in peace. By the Founders I don't need this right now!"
                    )
                elif sym < 80:
                    return (
                        "So here we have you, Paladin Xi's last discovery! He wants everybody on space.\n\n"
                        " I get, we need the PGMs, and more valuable asteroids, but the belts are dangerous."
                        " People have been killed. No beacon signal can save you if you are too far away,"
                        " drifting between planets. Be careful, noobie, ok? Life is a precious thing."
                    )
                else:
                    return (
                        f"Nice to meet you, {you}! How are you doing?"
                        "\n\nI have heard about you. Good things! Do you want a coffee? Or maybe something... stronger?"
                        "\n\nHow is space treating you? Have you seen the portal?"
                        "Making our Paladin Xi proud? Tell me!"
                    )

    def talk_present_yourself_further_times(self) -> str:
        # Short names to make the rest more legible
        emp: float = self.interlocutor.empathy100
        soc: float = self.interlocutor.sociability100
        sym: float = self.interlocutor.sympathy100
        you: str = self.interlocutor.address(self.player, to_player=True)  # how the person calls the pilot

        if emp < 20:
            if soc < 20:
                if sym < 20:
                    return "Fuck off."
                elif sym < 80:
                    return "Hi."
                else:
                    return "Hi <shy smile>."
            elif soc < 80:
                if sym < 20:
                    return "You. What do you want?"
                elif sym < 80:
                    return f"{you}. Hi. What's the matter?"
                else:
                    return f"{you}! Hey! Still alive, apparently. Respect."
            else:  # noqa: PLR5501
                if sym < 20:
                    return "Bugger off, will you? Nobody wants to talk with you."
                elif sym < 80:
                    return (
                        f"If it's not good old {self.player.first_name}! You didn't manage to kill yourself yet,"
                        " I see. What do you want?"
                    )
                else:
                    return "Hello there. You are still alive, yes? I am surprised. You're not so stupid after all."
        elif emp < 80:
            if soc < 20:
                if sym < 20:
                    return f"{you}. Go."
                elif sym < 80:
                    return "Hello <looks suspiciously>."
                else:
                    return "Hey <shy smile>."
            elif soc < 80:
                if sym < 20:
                    return f"{self.player.first_name} {self.player.surname}. Now my day is screwed."
                elif sym < 80:
                    return f"Hello {you}, how are you?"
                else:
                    return (
                        f"{you}! Welcome! How are you doing? You want some coffee?"
                    )
            else:  # noqa: PLR5501 - High soc
                if sym < 20:
                    return (
                        f"If it's not {self.player.get_title()} Pilot {self.player.first_name} {self.player.surname}!"
                        " I have no interest in talking with you."
                    )
                elif sym < 80:
                    return (
                        f"Hey, {you}, how are you? Alive, I see! I'm glad."
                        f" Me... I miss {self.interlocutor.planet_of_birth}."
                    )
                else:
                    return (
                        f"{you}, my friend! How are you doing? Did you see the game yesterday?"
                    )
        else:  # noqa: PLR5501 - High emp
            if soc < 20:
                if sym < 20:
                    return "<Looks sadly at you, says nothing>"
                elif sym < 80:
                    return "Hello again." # 'again' maybe after five years, but he does not care: too son :D
                else:
                    return "Oh. You. Nice. <shy smile>"
            elif soc < 80:
                if sym < 20:
                    return (
                        "Oh, it's you again. Why don't you go bother someone else?"
                    )
                elif sym < 80:
                    return (
                        f"Ah, {you}. Hello. I was going to make myself a tea. One for you?"
                    )
                else:
                    return (
                        f"{you}, hello! Welcome! How are you doing? Something interesting to tell?"
                    )
            else:  # noqa: PLR5501 - High soc
                if sym < 20:
                    return (
                        f"If it's not {self.player.get_title()} Pilot {self.player.first_name} {self.player.surname}!"
                        " What are you doing here? What do you want? I have no interest in talking with"
                        " the likes of YOU."
                    )
                elif sym < 80:
                    return (
                        f"Hey, {you}, how are you? Alive, I see! I'm glad. How is good old space"
                        f" treating you lately? Friend, I miss {self.interlocutor.planet_of_birth}. And you, do"
                        f" you miss home?"
                    )
                else:
                    return (
                        f"{you}, my friend! How are you doing? What can I do for you?"
                    )

# endregion

# region Normal Talk

    def talk_asteroid(self) -> str:
        return (
            "Have you visited one? Sometimes the labs ask for somebody. I mean, I get it. But... damn. Some are"
            " simply fucking far away. Others are... in the belt. And those are worse."
        )

    def talk_base(self) -> str:
        if isinstance(self.interlocutor.residency, PortalBase):
            founded: datetime = self.place.founded_at
            now: datetime = self.date_time
            when: str = founding_when(founded, now)

            text: str = ''
            if (founded.year, founded.month, founded.day) == (now.year, now.month, now.day):
                text = "We *just* arrived *today*, how on Catherine are you here!? I mean... happy star! Wow!"
            elif (founded.month, founded.day) == (now.month, now.day):
                text = f"This place was founded as of today, {when}. Happy star!"
            elif founded.year + 5 < now.year:
                text = f"This place was founded at {pretty_date(founded)}, {when}. We expand!"
            else:
                text = f"This place was founded in {when}. Our happy star is {pretty_date(founded)}."
            return text

        text: str = (
            "Have you been there lately? People say Miners do not need it like us. I miss getting out of this"
            " uniform, I tell you. My shorts and a cocktail, looking at a garden. That's life."
            " Almost like a planet."
        )
        # The small outposts have no Komisar: somebody who likes the Community's advisers misses one.
        if (self.interlocutor.loyalty100 > 20 and self.interlocutor.sociability100 > 20
                and KOMISAR not in self.interlocutor.residency.teams_now() and random.random() < 0.3):
            text += " I miss having a Komisar to talk with."
        return text

    def talk_belt(self) -> str:
        return (
            "Don't go there if you don't want to get killed. Not without a well-prodected ship"
            " and a ton of sealant, at least."
        )
    def talk_bureaucrat(self) -> str:
        return (
            "Administration, inspection, requests, complains... to keep the machine of the Commuity going."
        )

    def talk_communication_officer(self) -> str:
        # Only sociability matters here: it sets the verbosity.
        soc: float = self.interlocutor.sociability100

        if soc < 20:
            return "Sit and talk."
        elif soc < 80:
            return "Take care of communications with the ship."
        else:
            return "Talk with the ships and other places. Belong to defence, have to wear uniform."

    def talk_coordinator(self) -> str:
        # Sociability sets the verbosity; loyalty, the tone towards the entity.
        soc: float = self.interlocutor.sociability100
        loy: float = self.interlocutor.loyalty100

        if soc < 20:
            if loy < 20:
                return "Little boss."
            elif loy < 80:
                return "Chief in the outpost."
            else:
                return "Outposts. Manage stuff. Make hard calls."
        elif soc < 80:
            if loy < 20:
                return "Bossing around in the outposts."
            elif loy < 80:
                return "Coordinate things in the outposts."
            else:
                return "Authority of an outpost. Job for well-respected people."
        else:  # noqa: PLR5501
            if loy < 20:
                return "Little boss of the outposts. And loving it."
            elif loy < 80:
                return "Responsible for the outposts. Coordinate and communicate with the portal base."
            else:
                return (
                    "The authority of an outpost. Job for highly respected people. Remove obstacles, coordinate,"
                    " communicate with the portal base and resolve conflicts."
                )

    def talk_credits(self) -> str:
        # Traits do not matter here: the role and what the pilot did in this system decide. Only an authority hears
        # the pilot who sold the mine codes of the system (see rat_offered), and only until the pilot has ratted.
        text: str = "The currency, the money of UniDiv. They use a symbol like a 'c' with a slash."
        if (self.interlocutor.role in (KOMISAR, COORDINATOR, RINGMASTER)
                and self.traitor_sold_codes_here() and not self.traitor_ratted_here()):
            text += "\n\nIs there something special you want to tell me?"
            self.offer(["<Explain the whole story>", "No, I was just curious."], self.traitor_rat_offered)
            if self.interlocutor.role is RINGMASTER:
                text += "\n\nTODO: the Ringmaster hints that the pilot may ask for [credits for the ship]."
        return text

    def talk_custodian_thirds(self) -> str:
        # Only sociability matters here: it sets the verbosity.
        soc: float = self.interlocutor.sociability100

        if soc < 20:
            return "You have children?"
        elif soc < 80:
            return (
                "Ah, children. Did you know it's a PosDis thing? From the Charismatic Revolution,"
                " I think. Before, fathers controlled everything, it was called 'daddiarchy'."
            )
        else:
            return (
                "Children... do you have some? How was the decision? It's not always easy, you know? Sometimes there"
                " are horrible quarrels before birth, even if the law is clear enough."
                " And other places organise them differently. But even in The Shining Throne thirds are chosen on"
                " time, one way or another. It's human nature."
            )

    def talk_dockmaster(self) -> str:
        # Only sociability matters here: it sets the verbosity.
        soc: float = self.interlocutor.sociability100

        if soc < 20:
            return "Load. Unload. Repair."
        elif soc < 80:
            return "Take care of the ships landing there."
        else:
            return "Responsible for ship maintanance and the cargo."

    def talk_engineer(self) -> str:
        return (
            "Design and handle all kinds of machinery, above all heavy industry."
        )
    def talk_founders(self) -> str:
        return (
            "Well, the ones who founded Those-Who-Share, you know?"
        )

    def talk_gunner(self) -> str:
        # Only sociability matters here: it sets the verbosity.
        soc: float = self.interlocutor.sociability100

        if soc < 20:
            return "Do nothing. Good."
        elif soc < 80:
            return "Sit, drill, wait. Until the shit hits the fan."
        else:
            return (
                "Well, when things go really bad, a Gunner's responsibility is be the ones who pull"
                " the trigger. A hard decision taken in seconds."
            )

    def talk_hobby(self) -> str:
        return self.interlocutor.hobby

    def talk_happy_birthday(self) -> str:
        # Short names to make the rest more legible
        soc: float = self.interlocutor.sociability100
        sym: float = self.interlocutor.sympathy100
        you: str = self.interlocutor.address(self.player, to_player=True)  # how the person calls the pilot

        # Loyalty is irrelevant, this is apolitical.
        # Empathy is irrelevant, as this is all about the interlocutor.
        # Sociability and sympathy combine, for verbose replies.

        # Auxiliary variables:
        interaction_key: str = "Happy birthday " + str(self.date_time.year)
        dtb: Optional[int] = self.days_to_birthday()
        is_really = dtb == 0
        is_near_enough = dtb is not None and dtb != 0
        is_not = dtb is None
        told_already: bool = is_really and any(
            interaction_key in lines for lines in self.interlocutor.interactions.values()
            )
        correction_text = "That's someone else." if is_not \
            else "That was the day before yesterday." if is_near_enough and dtb == -2 \
            else "That was yesterday." if is_near_enough and dtb == -1 \
            else "That's tomorrow." if is_near_enough \
            else "You told me already..." if told_already \
            else ""

        # The effects are impressive:
        if is_not:
            self.interlocutor.adjust_sympathy(-5)
        elif is_near_enough:
            self.interlocutor.adjust_sympathy(1)
        elif told_already:
            self.interlocutor.adjust_sympathy(-0.1)
        else:
            self.flags.append(interaction_key)
            self.interlocutor.adjust_sympathy(20)

        # Simplify soc and sym. The 1.212 is to keep variance.
        ver: float = 50 + 1.212 * (0.5 * (50 - soc) + 0.5 * (50 - sym))

        if told_already:
            return correction_text
        elif ver < 20:
            if is_really:
                return "Oh. Thank you. <Blushes a bit>"
            else:
                return correction_text
        elif ver < 80:
            if is_really:
                return "Oh, well, thank you very much!"
            elif is_near_enough:
                return f"You are mistaken, sorry. {correction_text}\n\nBut thanks anyway."
            else:
                return f"That's... weird. {correction_text}"
        else:  # noqa: PLR5501
            if is_really:
                return f"You remembered! That's so nice, {you}! THANK YOU!"
            elif is_near_enough:
                return f"Oh, dear! {correction_text}\n\nBut thanks anyway, don't worry."
            else:
                return f"Huh? {correction_text} And this was weird."

    def talk_happy_founding(self) -> str:
        # Apolitical and about the place: no trait of the person matters, only the date of the founding.
        founded: datetime = self.place.founded_at
        now: datetime = self.date_time

        if (founded.month, founded.day) == (now.month, now.day):
            interaction_key: str = f"Happy foundation {self.date_time.year} {self.place.seed}"
            already_said: bool = False
            for member in self.place.generate_staff().staff:
                if any(interaction_key in lines for lines in member.interactions.values()):
                    already_said = True
            if not already_said:
                self.flags.append(interaction_key)
                # Every member of the staff hears about it, the interlocutor included.
                for member in self.place.generate_staff().staff:
                    member.adjust_sympathy(5)
            return "<Everybody around cheers>"
        self.interlocutor.adjust_sympathy(-5)
        return f"<Looks weirdly> This place was founded at {pretty_date(founded)}, {founding_when(founded, now)}."

    def talk_happy_new_year(self) -> str:
        # Apolitical and about the season: no trait of the person matters, only the date. Every settlement celebrates
        # it, once a year each: the key holds the year and the settlement's seed.
        now: datetime = self.date_time

        if (now.month, now.day) == (1, 1):
            interaction_key: str = f"Happy new year {now.year} {self.place.seed}"
            already_said: bool = False
            for member in self.place.generate_staff().staff:
                if any(interaction_key in lines for lines in member.interactions.values()):
                    already_said = True
            if not already_said:
                self.flags.append(interaction_key)
                # Every member of the staff hears about it, the interlocutor included.
                for member in self.place.generate_staff().staff:
                    member.adjust_sympathy(3)
            return "<Everybody around cheers, some visibly drunk, high, or both>"
        self.interlocutor.adjust_sympathy(-5)
        return "<Looks weirdly> That's January 1st..."

    def talk_happy_star(self) -> str:
        # Apolitical and about the system: no trait of the person matters, only the day the Portal came. Every
        # settlement of the system celebrates it, once a year each: the key holds the year and the settlement's seed.
        star: datetime = portal_arrival(self.place)
        now: datetime = self.date_time

        if (star.month, star.day) == (now.month, now.day):
            interaction_key: str = f"Happy star {now.year} {self.place.seed}"
            already_said: bool = False
            for member in self.place.generate_staff().staff:
                if any(interaction_key in lines for lines in member.interactions.values()):
                    already_said = True
            if not already_said:
                self.flags.append(interaction_key)
                # Every member of the staff hears about it, the interlocutor included.
                for member in self.place.generate_staff().staff:
                    member.adjust_sympathy(3)
            return "<Everybody around cheers>"
        self.interlocutor.adjust_sympathy(-5)
        return f"<Looks weirdly> The Portal came on {pretty_date(star)}, {founding_when(star, now)}."

    def talk_janitor(self) -> str:
        # Only sociability matters here: it sets the verbosity.
        soc: float = self.interlocutor.sociability100

        if soc < 20:
            return "Base maintenance. Not cleaners."
        elif soc < 80:
            return "Base maintenance. Repairs, devices, checks, life support. Not here to clean your room."
        else:
            return (
                "Caring about base maintenance. Running around, checking the life support, devices, repairs."
                " Not your servant, not to cook for you."
            )

    def talk_job(self) -> str:
        text: str = ''
        how_happy_with_role: int = self.interlocutor.how_happy_with_role()
        if how_happy_with_role == 0 and self.interlocutor.sociability100 >= 20:
            if self.interlocutor.main_problem_with_role().startswith("+"):
                if self.interlocutor.main_problem_with_role().endswith("loy"):
                    text = "I wish I worked in something more relevant."
                elif self.interlocutor.main_problem_with_role().endswith("emp"):
                    text = "I wish I worked in something more helpful for people."
                else:
                    text = "I wish I worked more with people."
            else:  # noqa: PLR5501
                if self.interlocutor.main_problem_with_role().endswith("loy"):
                    text = "I wish I worked in something less demanding."
                elif self.interlocutor.main_problem_with_role().endswith("emp"):
                    text = "I wish I had more time for myself."
                else:
                    text = "I wish I could concentrate more, focus."
        elif how_happy_with_role == 1:
            text = f"Being {self.interlocutor.role.name} is ok."
        elif how_happy_with_role == 2:
            text = "I really like my job."
        else:
            text = "A job's a job."

        flags: set[str] = self.player.political_status[political_entity.THOSE_WHO_SHARE].flags
        already_sold: bool = True
        res = self.interlocutor.residency
        if isinstance(res, Settlement):
            seed = res.stellar_system.seed
            already_sold = f"{SOLD_FLAG} {seed}" in flags
        already_talked_openly: bool = any(
            "Dared talk openly." in lines for lines in self.interlocutor.interactions.values()
            )
        if not already_sold and not already_talked_openly \
                and self.interlocutor.loyalty100 < 20 and self.interlocutor.sympathy100 >= 80 \
                and how_happy_with_role == 0:
            buttons = ["I like mine.", "I guess it's ok.", "I don't have an option, do I? This or retire."]
            if self.interlocutor.sociability100 < 20:
                text += "\n\nYou? <stares intensively>"
            elif self.interlocutor.sociability100 < 80:
                text += "\n\nAnd you? You can be honest with me."
            else:
                text += (
                    "\n\nAnd you? You can tell me the truth. I am your friend, you know that. After all"
                    " you have done."
                    )
            self.offer(buttons, self.traitor_chance)

        return text

    def talk_komisar(self) -> str:
        # Sociability sets the verbosity; loyalty, the tone towards the entity.
        soc: float = self.interlocutor.sociability100
        loy: float = self.interlocutor.loyalty100

        if soc < 20:
            if loy < 20:
                return "<Looks away>"
            elif loy < 80:
                return "<Shrugs> Talk a lot."
            else:
                return "Explain things. Help with problems."
        elif soc < 80:
            if loy < 20:
                return "Soft-talking. Take care that people behave. Or else."
            elif loy < 80:
                return (
                    "Social engineers and psychologists. The job is to make sure people understand the will of the"
                    " Community. But they also often give personal advice."
                )
            else:
                return (
                    "The job is to friendly advice about the will of the Community and our role in it. Also, help"
                    " with personal problems. Be a good psychologist. Friend and helper."
                )
        else:  # noqa: PLR5501
            if loy < 20:
                return "Making sure everybody 'understands the will of the Community'. Usually, soft-talking. Else..."
            elif loy < 80:
                return (
                    "Indicate the right channels for a protest, talk with people if they feel bad, make sure"
                    " people understand the will of the Community."
                )
            else:
                return (
                    "The job is to be your friend <smiles>. Often enough they are asked for personal advice. But"
                    " of course the main tasks is to make sure people understand what are we doing here and what"
                    " the Community is for."
                )

    def talk_life(self) -> str:
        # General effect. People like to be asked about their lives. Once per day max, though.
        date_str: str = self.date_time.date().isoformat()
        if not any("Asked about life." in lines for lines in self.interlocutor.interactions.values()):
            self.interlocutor.adjust_sympathy(5)
            self.flags.append("Asked about life.")
        elif not any(f"Asked about life {date_str}" in lines for lines in self.interlocutor.interactions.values()):
            self.interlocutor.adjust_sympathy(0.1)
            self.flags.append(f"Asked about life {date_str}")

        # Short names to make the rest more legible
        soc: float = self.interlocutor.sociability100
        sym: float = self.interlocutor.sympathy100

        # Apolitical conversation: Loyalty is irrelevant, save the self presentation.
        # Empathy irrelevant: this is anyway about the interlocutor.
        # Sociability always relevant, makes the reply less or more verbose.
        # Sympathy always relevant, rejection or approval of the player.
        # Special: birthday discovery -2 to +1 days is relevant.
        days_to_birthday: Optional[int] = self.days_to_birthday()
        self_description: str = ''

        # more empathy = more humble
        if self.interlocutor.empathy100 < 20:
            self_description = "the best <smiles>"  # delulu :D
        elif self.interlocutor.empathy100 < 80:
            self_description = "cool"
        else:
            self_description = "ok, I guess"

        if soc < 20:
            if sym < 20:
                if days_to_birthday == 0:
                    return "On my birthday, for fuck's sake. Leave me alone."
                return "Leave me alone."
            elif sym < 80:
                if days_to_birthday == 0:
                    return "Life's ok. Birthday."
                if self.interlocutor.how_happy_with_role() == 2:
                    return "Job's good. Life's ok."
                return "Life's ok."
            else:
                if days_to_birthday == 0:
                    return "Doing ok. My birthday today."
                if self.interlocutor.how_happy_with_role() == 1:
                    return "Job's ok. Doing ok. Thanks."
                return "Doing ok. Thanks."
        elif soc < 80:
            if sym < 20:
                job: str = " I don't have enough with my job?" if self.interlocutor.how_happy_with_role() == 0 else ""
                if days_to_birthday == 0:
                    return f"On my birthday, for fuck's sake.{job} Leave me alone."
                return f"Oh, no.{job} Leave me alone."
            elif sym < 80:
                text = (
                    f"Me? I was born in {self.interlocutor.place_of_birth}, I am {self.interlocutor.age} years old,"
                    f" I work here as a {self.interlocutor.role.name}, that's my job."
                    f" People say I'm {self_description}."
                )
                if days_to_birthday == -2:
                    text += "\n\nI had my birthday two days ago."
                elif days_to_birthday == -1:
                    text += "\n\nMy birthday was yesterday."
                elif days_to_birthday == 0:
                    text += "\n\nYou wanted to say happy birthday?"
                elif days_to_birthday == 1:
                    text += "\n\nTomorrow is my birthday."
                return text
            else:
                text = (
                    "Me? Thank you for asking, friend <smiles>."
                    f" Well, I was born in {self.interlocutor.place_of_birth}, I am {self.interlocutor.age} years old,"
                    f" I work here as a {self.interlocutor.role.name} from {self.interlocutor.work_hours_text()}."
                    f" People say I'm {self_description}."
                    f"\n\nOh... and {self.interlocutor.hobby}, that's my hobby"
                )
                if days_to_birthday == -2:
                    text += "\n\nMy birthday was two days ago."
                elif days_to_birthday == -1:
                    text += "\n\nMy birthday was yesterday."
                elif days_to_birthday == 0:
                    text += "\n\nToday is my birthday. Just saying."
                elif days_to_birthday == 1:
                    text += "\n\nTomorrow is my birthday, by the way."
                return text
        else: # noqa: PLR5501 High soc
            if sym < 20:
                text = "What do you want to know? I work here. I do my best <stares at you firmly>."
                if days_to_birthday == -1:
                    text += "\n\nYesterday was my birthday, if you want to know."
                elif days_to_birthday == 0:
                    text += "\n\nToday is my birthday. So leave me alone."
                return text
            elif sym < 80:
                text = (
                    f"Me? I was born in {self.interlocutor.place_of_birth},"
                    f" I had {self.interlocutor.childhood}, I would say."
                    f" I am {self.interlocutor.age} years old."
                    f" I work here as a {self.interlocutor.role.name}, that's my job."
                    f" People say I'm {self_description}."
                )
                if days_to_birthday == -2:
                    text += "\n\nI had my birthday two days ago. Too late for Happy birthday! <laughs>."
                elif days_to_birthday == -1:
                    text += "\n\nMy birthday was yesterday, you just missed my 'Happy birthday!' <laughs>."
                elif days_to_birthday == 0:
                    text += "\n\nToday is my birthday. You can still wish me 'happy birthday' <smiles>."
                elif days_to_birthday == 1:
                    text += "\n\nTomorrow is my birthday, if you want to wish me happy birthday <smiles>."
                return text
            else:
                text = (
                    "Me? You want to talk about my life? I am flattered <laughs>."
                    f" Well... ok, I was born in {self.interlocutor.place_of_birth}. I really miss home sometimes."
                    f" I had {self.interlocutor.childhood}, I would say. But that's the past."
                    f" I am {self.interlocutor.age} years old. I know, I know."
                    f" I work here as a {self.interlocutor.role.name}, that's my job."
                    f" People say I'm {self_description}."
                    f"\n\nOh... and {self.interlocutor.hobby}. My hobby"
                )
                if days_to_birthday == -2:
                    text += "\n\nBTW, I had my birthday two days ago."
                elif days_to_birthday == -1:
                    text += "\n\nBTW, my birthday was yesterday, if you want to know."
                elif days_to_birthday == 0:
                    text += "\n\nYou know something? Today is my birthday! Will you wish me happy birthday?"
                elif days_to_birthday == 1:
                    text += (
                        "\n\nLook, so... tomorrow is my birthday. You could come by. Even without a present."
                        " I forgive you <laughs>."
                    )
                return text

    def talk_noobie(self) -> str:
        return (
            "Well, that's... no offense intended. Paladin Xi finished your training recently, yes? So..."
            " that's it."
        )

    def talk_outpost(self) -> str:
        from galaxies.outpost import Outpost
        if isinstance(self.place, Outpost):
            founded: datetime = self.place.founded_at
            now: datetime = self.date_time
            when: str = founding_when(founded, now)
            star: datetime = portal_arrival(self.place)
            text: str = ""
            if (founded.year, founded.month, founded.day) == (now.year, now.month, now.day):
                text = "We *just* opened operations, so... happy founding, I'd say!"
            elif (founded.month, founded.day) == (now.month, now.day):
                text = f"This place was founded as of today, {when}. Happy founding!"
            elif (star.month, star.day) == (now.month, now.day):
                text = "Happy star!"
            elif founded.year + 5 < now.year:
                text = f"This place was founded at {pretty_date(founded)}, {when}. Don't expect too much, ok?"
            else:
                text = f"This place was founded in {when}. Our happy founding is {pretty_date(founded)}."
            return text
        return "A place where you can get resupplied. Vital, for long trips."

    def talk_portal(self) -> str:
        return (
            "Crossing that thing was at the same time overwhelming and disappointing. I mean... it's just like"
            " you are simply travelling through. But one side is light years from the other side. Damn."
        )
    def talk_paladin_xi(self) -> str:
        return (
            "He trained you, yes? Of course 'Paladin' is not a real thing. I think he is considered a"
            " Steward or Herald or something."
        )
    def talk_pgms(self) -> str:
        return (
            "Did you find many out there? I think Iridium is the most important right now, but the whole"
            " Platinum-group is crucial. No PGMs - no energy, shields, no ooompf. Just cold space."
        )
    def talk_researcher(self) -> str:
        return (
            "From pure scientific theory to engineering research. But more of the latter."
        )

    def talk_ringmaster(self) -> str:
        # Sociability sets the verbosity; loyalty, the tone towards the entity.
        soc: float = self.interlocutor.sociability100
        loy: float = self.interlocutor.loyalty100

        if soc < 20:
            if loy < 20:
                return "Bigwhigs. Careful."
            elif loy < 80:
                return "Main coordinator. Answer to Ministry only."
            else:
                return "Responsible of all this. Heavy burden."
        elif soc < 80:
            if loy < 20:
                return "They are bigwhigs, the supreme bosses of the stellar system. Fiercy loyal."
            elif loy < 80:
                return (
                    "The main coordinator of the expansion effort in this system. Depend directly from the Ministry."
                    " Later, a Commander takes over."
                )
            else:
                return (
                    "Important job. Main responsible of the stellar system in development, depending only on the"
                    " Ministry of Expansion. Chosen very carefully."
                )
        else:  # noqa: PLR5501
            if loy < 20:
                return "They are the ones taking the decisions here. Kinglets in their turf. Fiercy loyal."
            elif loy < 80:
                return (
                    "Coordinate this system, until cities are established and a Commander takes"
                    " over. Depend directly on the Ministry of Expansion.\n\n"
                    " Chosen very, very carefully."
                )
            else:
                return (
                    "A very important job. Main responsible of the whole stellar system in development. Later, a"
                    " Commander takes over and makes it all about security, but during the settelment phase it is"
                    " the highest authority available, and responds only to the Ministry of Expansion.\n\n"
                    " It is to carry a very heavy burden for the Community."
                )

    def talk_protection(self) -> str:
        # Only sociability matters here: it sets the verbosity.
        soc: float = self.interlocutor.sociability100

        if soc < 20:
            return "Handle conflicts. Protect."
        elif soc < 80:
            return (
                "Security officers, captains and more are part of the Ministry of Protection."
                " You have to wear uniform."
            )
        else:
            return (
                "Security officers handle the conflicts. Trained to de-escalate, but ready to do what it takes."
                " Then come the officers: lieutenants, captains and so on, all  depend on the Ministry of Protection."
            )

    def talk_smith(self) -> str:
        return (
            "To take the ore miners bring, as well as other materials, and transform it into usable, standardised"
            " materials. Requires tough people, unlike other engineers."
        )
    def talk_space(self) -> str:
        return (
            "Unforgiving, yes? And fucking huge. In your head, make three layers of it: remaining around a"
            " planet with an outpost. Easy peasy and safe. Interplanetary. Hard and dangerous. Interstellar."
            " Just don't. Go to the bases, use the portals, remain in the network"
        )

    def talk_stevedore(self) -> str:
        # Only sociability matters here: it sets the verbosity.
        soc: float = self.interlocutor.sociability100

        if soc < 20:
            return "Haul stuff. Simple job."
        elif soc < 80:
            return "Move cargo from and to ships. A solitary job if not for your colleague."
        else:
            return (
                "Take cargo from the ship, move mines. A solitary job if it was not for your colleague. They never"
                " work alone. Too dangerous, with the inertia."
            )

    def talk_surnemals(self) -> str:
        return (
            "Ancient stuff. People born naturally when many came from the tube. Lineages. Ruled, lost, rose again"
            " around the third century. They say in UniDiv there are still some, but most must have gone to The"
            " Shining Throne."
        )
    def talk_the_network(self) -> str:
        return (
            "Every year a bit larger. I don't know, we must have like two dozen systems by now. I mean"
            " Those-Who-Share. Sure, 'United Diversity', UniDiv, has more. The Shining Throne, no idea."
        )

    def talk_the_shining_throne(self) -> str:
        # Political conversation, about the other entity (see talk_political). Loyalty is relevant: the less loyal to
        # Those-Who-Share, the more they like The Shining Throne. Empathy is still somehow relevant, to judge the place.
        # Sociability always relevant: how many topics they talk about. Sympathy always relevant: below 20 a brush-off,
        # from 80 the friend topics.
        topics: PoliticalTopics = {
            'slaves': (50, (
                "Slaves. Horrible.", "Slaves. Hm.", "Slaves, but treated well.",
            ), (
                (
                    "They're mad. Some live in luxury while others are enslaved. Literal slaves. Fuck.",
                    "Slaves have no rights there. Their owners can beat them, torture them, rape them, even kill"
                    " them, and nobody says a word. That's what I've heard.",
                ),
                "They have slaves. Maybe they don't torture them or so. But... slaves. Ugh.",
                "They have slaves, but I've heard they're not so many, and people can free themselves. No idea, ok?",
            )),
            'luxury': (40, (
                "Soap operas. Ugh.", "Soap operas are nice.", "Parks and boulevards. Gorgeous.",
            ), (
                (
                    "Luxury built on the back of poor serfs and servants. Corruption and filth, the lot of them.",
                    "The aristocrats live in luxury and the poor pay for it. They say the serfs love their Sires."
                    " Sure. Ask them when the Sire is not listening. They hate them, and one day they will rebel.",
                ),
                "Not that I'd like to *live* there, but the soap operas are really nice. Still...",
                "Hard to say. The parks, the boulevards, the clothes. It's so gorgeous. But hey, here is also ok.",
            )),
            'honour': (30, (
                "Honour and beauty. Bah.", "They're not like us.", "Super-humans. Hm.",
            ), (
                (
                    "They look for the 'super-humans', all that's whose more handsome. Stupid.",
                    "'Protecting the weak', 'chivalry'. Pure propaganda. The aristocrats are selfish and cruel, like"
                    " any other rulers, only better dressed.",
                ),
                "They're just not like us. For them it's all about 'honor' and 'beauty' and 'chivalry'.",
                "They're completely different to us, aren't they? Honour, beauty, protecting the weak."
                " I see what they mean.",
            )),
            'gardens': (30, (
                "Parks. Hm.", "Their gardens.", "The boulevards. Wow.",
            ), (
                (
                    "They have their parks and fountains and music, but it's all for the aristocrats.",
                    "All that beauty is for the aristocracy. The lower classes cannot even enter. Parks, music,"
                    " theatres: not for the likes of them.",
                ),
                "Their parks, their music. I'd like to see that in the shows.",
                "Parks, fountains, music, dances, poetry. They live, and we don't. They reward merit. We don't.",
            )),
            'freedom': (40, (
                "Own a person. Disgusting.", "Slaves. I don't get it.", "Heard slaves have rights.",
            ), (
                (
                    "How can one people own another human being? That's fucking disgusting.",
                    "Slaves can be killed, tortured or raped at will. At will! And the rest look the other way."
                    " Disgusting.",
                ),
                "They *say* the lower classes have rights, but who knows what happens behind closed doors.",
                "I've heard the slaves have rights, and the Knights have lots of duties. Things are not how"
                " people want them to be.",
            )),
            'family': (40, (
                "Lineage. Ugh.", "Families and stations. Hm.", "Stable families. Protected.",
            ), (
                "Children are born slaves in the eyes of their law, and the same law lets them be beaten. Lineage"
                " rules everything there. Fuck that.",
                "The mother keeps the child first, then the father, then anybody who applies. If nobody takes all three"
                " parts, the Crown takes over. And lineage matters a lot, too.",
                "Stable families, familias traditions like the old Surnemals. Weird, yes. But somehow beautiful, no?",
            )),
            'education': (30, (
                "Elite schools. For aristos.", "Schools for servants up.", "Good schools. For some.",
            ), (
                "Only servants and above get free school, and only followers get free university. The elite schools"
                " are for the nobility. Nice system, if you are a noble.",
                "Free school from servant up, free university from follower up. There are elite schools for the"
                " nobility too. That's how it is.",
                "Servants and above get free school, followers get free university. The elite schools are for the"
                " nobility, but the teaching is good, they say.",
            )),
            'decoration': (30, (
                "Gaudy. Everything.", "Decorated. Sure.", "Beautiful, everything. Yes.",
            ), (
                "Everything must be decorated there: the facades, the street lights, the food, even the cutlery."
                " Even the things for the lowest ranks. What for!? What a waste.",
                "They decorate everything: facades, lamps, food, vehicles, cutlery. Only the richness changes with"
                " the rank. What an obsession, yes?",
                "Everything is decorated there, not only the workplaces. And for everybody, they"
                " say. It's... not bad.",
            )),
        }
        friend_topics: PoliticalTopics = {
            'chapter': (40, (
                "Soap operas. Pah.", "Some shows are cool.", "Soap operas, guilty.",
            ), (
                "<whispers> In confidence, I never miss a chapter. But it's all slaves and depravity, friend. Makes no"
                " sense. That's why it's so interesting!",
                "<whispers> In confidence, I never miss a chapter. Gorgeous *cutlery*, for the Founders' sake. But"
                " at what cost?",
                "<whispers> I have heard... things, you know. The slaves have a lot of rights. The powerful have a lot"
                " of duties. Protect the weak. There is some logic there.",
            )),
            'ownership': (40, (
                "Own a person? Never.", "People are not ours to own.", "Own a house, sure. Person? Strange.",
            ), (
                (
                    "Own a person? How can one people own ANOTHER HUMAN BEING? That's over me. Fuck them all."
                    " With a wrench.",
                    "<Whispers> Own a person, and do whatever you want with them. Kill them, torture them, rape"
                    " them. And it's legal! Fuck them all. With a wrench.",
                ),
                "I guess I can see how a person can own even a house. But another human being? That's over me.",
                "Owning a house, fine. Strange, but fine. Owning a *person* is what they do."
                " I cannot wrap my head around it. But they don't rebel. So maybe it's not so bad."
                ,
            )),
            'merit': (30, (
                "They demand 'deeds'. Ugh.", "Merit, sure.", "They reward heroic deeds. Like yours, eh? <laugh>",
            ), (
                "They are all for heroes and deeds and stuff. They don't know what a hero is. We do.",
                "They reward heroic deeds and such. At least in the shows. Reality is probably a different stuff, ha!",
                "They try heroic stuff, those aristocrats. That's how they got so many stars."
                " We could learn from that.",
            )),
            'public gardens': (30, (
                "Gardens for aristos. Bah.", "Their gardens. Wow.", "Gardens. Not hydroponic.",
            ), (
                (
                    "<Whispers> They spend so much in those gardens for the aristocrats. Meh.",
                    "<Whispers> Gardens, music, art... all behind gates, for the aristocracy. Normal people never"
                    " get in.",
                ),
                "<Whispers> Their public gardens are something. I'd like to see them in person some day.",
                "<Whispers> So wonderful, their gardens and boulevards and whatnot. Simply gorgeous,"
                " and I'm not ashamed to say so.",
            )),
        }
        generic: tuple[PoliticalTexts, PoliticalTexts, PoliticalTexts] = (
            ("Disgusting people.", "Fucking bastards.", "Not the way to go, friend."),
            ("<shrugs>", "Whatever. Who knows, yes?", "<shrugs>"),
            ("Beautiful.", "Maybe better than here.", "<Whispers> So beautiful. Everything."),
        )
        if self.interlocutor.sympathy100 < 20:
            return "Just leave me."
        return self.talk_political(topics, friend_topics, generic, own_entity=False, praise_guarded=False)

    def talk_those_who_share(self) -> str:
        # Political conversation, about their own entity (see talk_political). Loyalty alone decides how much they
        # approve (see political_tone). Praise is not frowned upon here. Sociability: how many topics they talk
        # about. Sympathy: below 20 a brush-off, from 80 the friend topics.
        loy: float = self.interlocutor.loyalty100
        topics: PoliticalTopics = {
            'work': (40 + 0.4 * loy, (
                "Work, work. Ugh.", "We build things. Fine.", "Biggest industry. Good.",
            ), (
                "The biggest industry of mankind, and the working places should be pleasant. Should be. We work"
                " for the Community, not for ourselves.",
                "We have the biggest industry of mankind, and the hydroponic gardens are as good as any. We do fine.",
                "The biggest industry of mankind, and the factories are pleasant places to be. I like that in my"
                " workplace. Proud of it.",
            )),
            'money': (30 + 0.4 * loy, (
                "Stamps. Worth nothing.", "Stamps. Fine.", "No greed. Good.",
            ), (
                "Money is banned, and stamps only buy the small things: clothes, food, personal devices. Nothing else"
                " is ours.",
                "No money, so nobody buys their way up. Stamps for the small things. It works.",
                "No money. Nobody is admired for being rich, only for what they give. Stamps for the small things, and"
                " that's enough.",
            )),
            'reputation': (40,(
                "Students, prisoners. Shame.",
                "What people think of you counts. Fine.",
                "Reputation matters. Fair.",
            ), (
                "People speak low of you, you are sent to study. Or worse, you get a chaperone. People like"
                " you, you can get anything you want, a better apartment, a better job. Fair, they say.",
                "How you behave decides how they call you, and at the end even the housing you get. It's not"
                " perfect, but everybody knows where they stand.",
                "The Community rewards those who give. More skills, more obligations, better reputation."
                " I think that's right.",
            )),
            'community': (50 + 0.5 * loy, (
                "Community. Yeah. Whatever.", "We share. Mostly.", "Nobody left alone. I like that.",
            ), (
                "The Community, always the Community. Thinking about yourself is frowned upon, and I'd like to do"
                " my own stuff once in a while, you know? Like you.",
                "We share, and nobody gets less than they need. People are proud of the Community, and I guess I am"
                " too.",
                "From each by their skills, to each by their needs. Nobody is left alone here. There's something"
                " to defend there.",
            )),
            'culture': (25 + 0.3 * loy, (
                "Slogans and statues. Meh.", "Posters and songs. Ok.", "Poetry, festivals. Nice.",
            ), (
                "Nothing made just for beauty, only statues, posters and big screens. Our art is just propaganda.",
                "Statues, posters, the big screens. For the Community, yes? To remember what we have.",
                "Poetry and skill competitions in the square, songs, festivals. Nothing useless about them."
                " Art for the normal people. Feeds the soul.",
            )),
            'isolation': (20 + 0.3 * loy, (
                "Isolated. Scared.", "We keep to ourselves.", "We keep ourselves safe.",
            ), (
                "We keep to ourselves, and they call it safety. I'd like to know what's out there.",
                "We keep to ourselves. Maybe too much, but the others have their own fights.",
                "We don't need the others to be a community. Our people are enough.",
            )),
            'family': (40, (
                "So many with no family.", "Families, the usual.", "Family, looked after.",
            ), (
                "Too many people reject their custodian thirds, and the Community takes them and says nothing."
                " Cold, if you ask me.",
                "Mother two thirds, father one, and anybody who applies for the rest. Families change, and the"
                " Community takes the rest. Solidarity, yes?",
                "Anybody who is ready can take a child, and nobody is turned away. Families change, and the neighbours"
                " help raise them. That's what the Community is for.",
            )),
            'education': (30, (
                "Great schools. For some.", "School's free. Fine.", "Free school. Good.",
            ), (
                "Free school and university... as long as you don't look closer who comes in the best ones.",
                "School and university are free. Yes, not all are really the same, but that's impossible.",
                "School and university are free for everybody. It's just normal that the best schools take more"
                " children of the best people.",
            )),
        }
        friend_topics: PoliticalTopics = {
            'camps': (30, (
                "Camps. Shh.", "Camps? Not so bad.", "Camps. Hard. But they learn.",
            ), (
                "<Whispers> I know people who went to the re-education camps. They came back quiet. Don't ask me more.",
                "<Whispers> The camps are hard to think about. I'd rather not, friend.",
                "<Whispers> The camps are for those who forgot the values. Most come back better, I'm told.",
            )),
            'home': (40, (
                "Family. Shh.", "We're fine here.", "Family. Good.",
            ), (
                (
                    "<Whispers> Reputation hangs over every friendship here."
                     " I'd rather be somewhere nobody calculates how to call me."
                ),
                "<Whispers> It's not perfect, but I'd rather be here than anywhere else.",
                "<Whispers> I've got friends in every square, and that's worth more than any stamp.",
            )),
            'founders': (30, (
                "The Founders. Hm.", "The Founders, sure.", "The Founders, yes.",
            ), (
                "<Whispers> The Founders wanted empathy, and now we watch each other."
                " Something went wrong along the way.",
                "<Whispers> The Founders wanted empathy first. We try. That's more than others do.",
                "<Whispers> The Founders had it right. Empathy first, and nobody left alone. I wouldn't trade this"
                " square for anything.",
            )),
            'children': (30, (
                "Family kids, Community kids. Shh.", "Kids. Shh.", "Family kids are warm. Shh.",
            ), (
                "The Community kids are rational? the family ones are the emotional ones?"
                " I wouldn't be so sure.",
                "Between us, I think it's true that family kids are more emotional. Yes, Community ones have their"
                " camaraderie but when your whole neighbourhood cares about you, you learn that too, believe me.",
                "It's better to be raised by the Community. Yes, families are nice and good, but nothing beats the"
                " comrades you made in your alma mater <winks>.",
            )),
        }
        generic: tuple[PoliticalTexts, PoliticalTexts, PoliticalTexts] = (
            ("Keep your head down.", "Don't say it too loud.", "Some things here are wrong."),
            ("It works. Mostly.", "Fine, I suppose.", "<shrugs>"),
            ("We take care of each other.", "Good.", "We're family here."),
        )
        return self.talk_political(topics, friend_topics, generic, own_entity=True, praise_guarded=False)

    def talk_united_diversity(self) -> str:
        # Political conversation, about the other entity (see talk_political). Everybody lives in Those-Who-Share (see
        # get_title), so the more loyal they are, the less they like United Diversity. Empathy weighs less: the less
        # empathic, the more they like the money and the force. Approval is guarded (see political_tone). Sociability:
        # how many topics they talk about. Sympathy: below 20 a brush-off, from 80 the friend topics.
        loy: float = self.interlocutor.loyalty100
        emp: float = self.interlocutor.empathy100
        rep: float = self.interlocutor.reputation
        topics: PoliticalTopics = {
            'size': (40, (
                "Bloated. The Moon.", "Big. Not good.", "Fifty systems. Wow.",
            ), (
                "About fifty systems with cities and the Moon on top, the most crowded world there is. A fat, bloated"
                " giant, that's all they are. Big.",
                "About fifty systems with cities, against our fifteen or so. And the Moon, the most crowded world by"
                " far. Big, yes. Big is not the same as good.",
                "About fifty systems with cities. Fifteen or so ours. And the Moon, with more people than anywhere"
                " else. Imagine being part of that.",
            )),
            'money': (30 + 0.6 * loy, (
                "Credits, money. Disgusting.", "They love money.", "Get rich, get admired.",
            ), (
                (
                    "Everything about money, yes? The rich are admired just for being rich. But you cannot breathe"
                    " credits, can you? You cannot drink them, you cannot eat them.",
                    "Greedy people, all of them. Money, money, money. Credits is that's all they think about.",
                    "Their government works for the oligarchs. The rich buy the laws, and the rest just pay.",
                ),
                "They love money, yes. The rich are admired and get their luxury. Maybe some earned it, ok. But a"
                " society that measures people in credits? No, thanks.",
                "You make something people want to buy, you get rich, you get admired. No sacks of stamps, no waiting"
                " for a title. There is a logic there.",
            )),
            'military': (70 - 0.4 * emp, (
                "Biggest army. Sick.", "Big guns. Nervous.", "Guns for ETs. Good.",
            ), (
                (
                    "The largest armed forces of mankind, and a cult of violence around them. Still licking the"
                    " wounds of the war against the Exterminating Mother two hundred years ago. Sick.",
                    "Their whole life turns around the military. Uniforms, parades, war stories. Sick.",
                ),
                "Their military is the largest. They say it is only for the ETs, never against humans."
                " Maybe so. Still... that much weaponry makes me nervous.",
                "The largest armed forces, well paid, and for ETs only, never against humans. If a new Exterminating"
                " Mother comes out of the dark, I want those people between her and me.",
            )),
            'science': (80 - 0.5 * loy, (
                "Exams to vote. Ugh.", "Brains, but who votes?", "Experts should vote.",
            ), (
                "Their famous science! Experts playing gods, and the vote only for those who have served the State and"
                " passed their exams. Disgusting.",
                "The most advanced science of mankind, no discussion. But the vote only for those who served the"
                " State? And who decides you 'really know politics'? I don't like it.",
                "The most advanced science there is, and they let those who know what they talk about vote. Experts"
                " count there. Wouldn't harm anyone to ask for some brains.",
            )),
            'poor': (0.6 * emp + 0.2 * loy, (
                "Cells and ghettos. Ugh.", "Basic income. Cells too.", "Nobody is a slave.",
            ), (
                "Those living only on their U.B.I. get a cell in a kind of big re-education camp, shared kitchens and"
                " washrooms. Ghettos. Here nobody lacks what they need.",
                "Basic income and healthcare for everybody, they say. In practice a cell in a prison, shared washrooms."
                " Ghettos. Better than slavery, I suppose. Not like The Shining Throne.",
                (
                    "There is a basic income, healthcare for everybody and nobody is a slave."
                    " Not like The Shining Throne. Yes, there are cells and ghettos... but it is a start."
                ),
            )),
            'industry': (0.6 * loy + 0.4 * min(max(rep, 0), 100), (
                "We build more. Obviously.", "Second in industry.", "Good at industry, yes.",
            ), (
                "But they don't build as we do. We have the biggest industry of mankind. They have the money,"
                " Those-Who-Share has the PGMs. We know that more than many, yes?",
                "They are the wealthy guys, ok. But industry? That is ours. They come second.",
                "Well. They are only second in industry, after us. Small comfort if you ask me.",
            )),
            'federalism': (0.4 * loy + 20, (
                "Their experiment. Insulting.", "Interesting experiments. Hm.", "Respect, not rivals.",
            ), (
                (
                    (
                        "You know what they think of us? An interesting experiment. EXPERIMENT. As if the Founders"
                        " had built a laboratory and not a community."
                    ),
                    "They think they are the only true mankind, and the rest of us a curiosity. Arrogant bastards.",
                ),
                "They say they find the other entities interesting experiments, and cultural diversity something to"
                " encourage. Nice words. A bit condescending, though. We are nobody's experiment.",
                "They see everybody else, us too, as interesting experiments, not as rivals. A kind of respect we don't"
                " give.",
            )),
            'family': (40, (
                "Orphanages. Ugh.", "Large families. Hm.", "Adoption. Good.",
            ), (
                "Custody cut in thirds, and the rest is the State... ok, but children still end up in orphanages."
                " Not like our centres, they are like... rejected. Sad.",
                "The custodian thirds are as usual: mother two, father one, anybody after that. But families are"
                " very scattered. And then you have those... big families? Some say they're ok. Others call them"
                " baby factories <eyes wide open>.",
                "They have these... specialised-custodian-families, yes? With pedagogy degrees and many children. It's"
                " strange. But maybe a more... personal than an educative centre?",
            )),
            'education': (30, (
                "Free school, on paper.", "Free school, sure.", "Free for everyone. Good.",
            ), (
                "Education is free, they say. But the U.B.I. comes with a place the State picks, often far from"
                " any university. And the really good schools are *not* free, you can believe me.",
                "Education is free for everyone and the U.B.I. lets them attend, in principle, but you must *live"
                " there* to attend, and nobody makes sure of that. Of course not a problem for the rich anyway.",
                "Education is as free as here, and there are plenty of scientific institutions. The U.B.I. makes"
                " makes sure you get susteinance. Of course super-duper unis are expensive, but who needs that.",
            )),
            'advertising': (30, (
                "Ads everywhere. Ugh.", "Ads. Whatever.", "Ads. At least honest.",
            ), (
                "Ads on every wall and screen, selling you things you don't need, and telling you that you need them"
                " to be somebody. Crazy.",
                "Advertising is everywhere, very visible. Parks, cinemas, shops, bars, all shouting at you. That's how"
                " they sell.",
                "The ads are everywhere, some are beautiful, and with the variety of stuff they have they better"
                " tell people about it.",
            )),
        }
        friend_topics: PoliticalTopics = {
            'poor': (40, (
                "Cells, ghettos. Ugh.", "Cells. Shh.", "<Whispers> Basic income. Real.",
            ), (
                "The cells, the ghettos. Nobody cares. They just want to look big.",
                "Some live well and some live in cells. I don't get them.",
                "<Whispers> Their basic income is not bad at all. But don't tell anyone I said so.",
            )),
            'science': (30, (
                "Experts vote. Ugh.", "Brains. Shh.", "<Whispers> Best science.",
            ), (
                "The science is cool,but the experts decide who votes. Nobody asks the people.",
                "<Whispers> The science is incredible. I'd like to see their labs once, that's all.",
                (
                    "<Whispers> Their science is the best there is. I envy them that a little."
                    " Don't tell anyone I said so."
                 ),
            )),
            'life': (30, (
                "Parks. Cinemas. Ugh.", "Parks. Shh.", "<Whispers> Concerts. Wish I'd seen.",
            ), (
                "The parks and the concerts are nice, but I wouldn't go near the rest.",
                "<Whispers> It has its charm: the coffee shops, the bars, the concerts. Nobody here would admit it.",
                "<Whispers> I'd love to visit. Concerts, cinemas, bars. Don't tell anyone I said so.",
            )),
            'money': (30, (
                "Money above all. Ugh.", "All about the credits. Shh.", "<Whispers> Rich and admired.",
            ), (
                "Money above everything, and the very wealthy in power. Nobody can say that in the square.",
                "<Whispers> Credits are a strange obsession, but they do make transactions transparent."
                " Don't quote me.",
                "<Whispers> The rich are there because of what they have done, and that's a logic I can respect."
                " But don't tell around I said so, ok?",
            )),
        }
        generic: tuple[PoliticalTexts, PoliticalTexts, PoliticalTexts] = (
            ("Fucking moneygrubbers with guns.", "Not for me.", "<shrugs>"),
            ("Whatever.", "<shrugs>", "Not for me."),
            ("Rich, strong, free.", "Not bad at all.", "Good for them."),
        )
        return self.talk_political(topics, friend_topics, generic, own_entity=False, praise_guarded=True)

    def talk_unknown_tag(self) -> str:
        return ("I don't know what you mean.")

    # endregion

# region Traitor's Path
    def traitor_chance(self, answer: int) -> None:
        if answer == 0:
            self.say(self.traitor_glad_for_you)
        elif answer == 1:
            self.say(self.traitor_maybe_later)
        else:
            self.say(self.traitor_options)

    def traitor_glad_for_you(self) -> str:
        self.interlocutor.adjust_sympathy(-5)
        self.flags.append("Dared talk openly.")

        if self.interlocutor.sociability100 < 20:
            return "<shrugs>"
        elif self.interlocutor.sociability100 < 80:
            return "Cool! Good for you <avoids eye contact>"
        else:
            return "I am glad! Nice for you. Long live! <looks nervous>"

    def traitor_maybe_later(self) -> str:
        if self.interlocutor.sociability100 < 20:
            return "You can tell me later."
        elif self.interlocutor.sociability100 < 80:
            return "Ok. I understand. Tell me if this changes."
        else:
            return "Yeah. I understand. We do what we can. But tell me if one day you can't. I am here for you."

    def traitor_options(self) -> str:
        text: str = ""
        buttons = ["<Accept>", "<Reject>"]
        if self.interlocutor.sociability100 < 20:
            text = "<whispers> Options. Dangerous. But. Interested?"
        elif self.interlocutor.sociability100 < 80:
            text = (
                "<whispers> Well... there are options. But they are... we would be in trouble if someone finds out."
                " Big trouble.\n\n"
                "Are you interested, friend?"
            )
        else:
            text = (
                "<whispers> Yeah. Well... there are options. But we would be in BIG trouble if someone finds out."
                " So... are you still interested? Can I trust you, friend?"
                )
        self.offer(buttons, self.traitor_offered)
        return text

    def traitor_offered(self, answer: int) -> None:
        if answer == 0:
            self.say(self.traitor_instructions)
        else:
            self.say(self.traitor_said_too_much)

    def traitor_said_too_much(self) -> str:
        self.interlocutor.adjust_sympathy(-10)
        self.flags.append("Dared talk openly.")

        if self.interlocutor.sociability100 < 20:
            return "<Says nothing>"
        elif self.interlocutor.sociability100 < 80:
            return "Suit yourself, then."
        else:
            return "Then forget I said anything."

    def traitor_instructions(self) -> str:
        text: str = ""
        if self.interlocutor.sociability100 < 20:
            text = "<whispering> You give me codes. Ore mines. Mines gives Credits. Less ore."
        elif self.interlocutor.sociability100 < 80:
            text = (
                "<whispers> Well... I know somebody. UniDev. You give me the codes of your ore mines. When you"
                " collect, there is less ore. But there are Credits."
            )
        else:
            text = (
                "<whispers> Well... I know someboy. From UniDev. They come as visitors, with excuses, with their ships."
                "\n\nYou give me the codes for your ore mines. From then on, they will... mine less ore. But there will"
                " be cryptos waiting for you. UniDev credits. Accumulate them."
                )
        buttons = ["But what happens then?"]
        self.offer(buttons, self.traitor_what_then)
        return text

    def traitor_what_then(self, answer: int) -> None:
        self.say(self.traitor_what_happens_then)

    def traitor_what_happens_then(self) -> str:
        text: str = ""
        if self.interlocutor.sociability100 < 20:
            text = "<whispering> Ringmaster. Credits for the ship. He'll hate you. But you'll be free."
        elif self.interlocutor.sociability100 < 80:
            text = (
                "<whispering> When you have... enough money... you go to the"
                " Ringmaster. You offer him the credits for the ship. He will hate you. But the Community can use those"
                " Credits. You will be a foreigner from then on. And a traitor. But you will be free."
            )
        else:
            text = (
                "<whispering> When you have... enough money. You go to the Ringmaster. Not anybody else!"
                " You offer him the credits for the ship. In exchange of 'private property' of the ship. He will"
                " hate you. Hell, many people here will hate you. But the hypocrits can well use those Credits."
                " You will become a foreigner with a ship... your own... 'property'... 'personal property'."
                "\n\nThen you can leave. And be free."
                )
        buttons = ["<Give the access codes>", "How much money exactly?"]
        self.offer(buttons, self.traitor_how_much)
        return text

    def traitor_how_much(self, answer: int) -> None:
        self.interlocutor.adjust_sympathy(50)
        self.flags.append("Got mine codes.")
        res = self.interlocutor.residency
        if isinstance(res, Settlement):
            seed = res.stellar_system.seed
            self.player.political_status[political_entity.THOSE_WHO_SHARE].flags\
                .add(f"{SOLD_FLAG} {seed}")

        if answer == 0:
            self.say(self.traitor_codes_given)
        else:
            self.say(self.traitor_say_how_much)

    def traitor_say_how_much(self) -> str:
        text: str = ""
        if self.interlocutor.sociability100 < 20:
            text = (
                "<Whispering> Half a million for a shabby ship, then one, two, three for the best. No extras. Don't"
                " forget that."
            )
        elif self.interlocutor.sociability100 < 80:
            text = (
                "<whispering> Well... half a million for the shabby ship you started with. Then one for a real one."
                " Yeah. That should be enough. If you've got more serious stuff, two million, even three to be safe."
                " Keep no extras. And remember: if they refuse, it is jail for you. Don't take the risk."
            )
        else:
            text = (
                "<whispering> Well... half a million for the shabby ship you started with. Then one for a real one."
                " Yeah. That should be enough. If you've got more serious stuff, two million, even three for a hauler."
                " Take away all extras before you go, give everything away. And remember: if they refuse, it's jail"
                " for you. Don't take the risk."
                )
        buttons = ["<Give the access codes>"]
        self.offer(buttons, self.traitor_ready)
        return text

    def traitor_ready(self, answer: int) -> None:
        self.say(self.traitor_codes_given)

    def traitor_codes_given(self) -> str:
        text = "<whispering> Done. Let's not talk about this ever again. Good luck."
        return text

    def traitor_denounce(self) -> None:
        """What denouncing the smugglers does to the system, whatever the pilot gains from it: the flag, the contact
        arrested (and replaced, see Settlement.imprison), and the disloyal of the system lose sympathy for the pilot."""
        system = self.interlocutor.residency.stellar_system
        self._standing_flags().add(f"{RATTED_FLAG} {system.seed}")
        self.flags.append("Ratted ore smugglers.")

        contact: Optional[Person] = next((
                person for place in system.settlements() for person in place.staff
                    if any("Got mine codes." in lines for lines in person.interactions.values())
                ),
                None
            )

        if contact is None:
            logger.warning(f"The pilot ratted in the system {system.seed} but the contact is not among the staff.")
        else:
            contact.residency.imprison(contact)

        for place in system.settlements():
            for person in place.staff:
                if person.loyalty100 < 20:
                    person.adjust_sympathy(-10 * (20 - person.loyalty100))

    def traitor_sold_codes_here(self) -> bool:
        """Whether the pilot sold the mine codes of the system of the interlocutor's settlement."""
        return f"{SOLD_FLAG} {self.interlocutor.residency.stellar_system.seed}" in self._standing_flags()

    def traitor_ratted_here(self) -> bool:
        """Whether the pilot has denounced the ore smugglers of the system of the interlocutor's settlement."""
        return f"{RATTED_FLAG} {self.interlocutor.residency.stellar_system.seed}" in self._standing_flags()

    def traitor_rat_offered(self, answer: int) -> None:
        if answer == 0:
            self.say(self.traitor_rat)

    def traitor_rat(self) -> str:
        """The pilot rats the smugglers: the mines stop paying credits, the disloyals in the system lose sympathy
        for the pilot, the contact is arrested and replaced, and the pilot gains reputation."""
        has_done_before: bool = any(flag.startswith(RATTED_FLAG) for flag in self._standing_flags())
        self.traitor_denounce()
        self.player.adjust_reputation(RAT_REPUTATION + self.player.credits / 100000)
        self.player.credits = 0
        self.interlocutor.adjust_sympathy(10)

        text: str = ""
        if has_done_before:
            if self.interlocutor.sociability100 < 20:
                if self.interlocutor.sympathy100 < 20:
                    text = (
                        "ANOTHER one!?\n\n"
                        "You attract traitors, yes?\n\n"
                        "Well. You know the procedure."
                    )
                else:
                    text = (
                        "ANOTHER one!?\n\n"
                        "The detective here.\n\n"
                        "Well. You know the procedure."
                    )
            else:  # noqa: PLR5501
                if self.interlocutor.sympathy100 < 20:
                    text = (
                        "ANOTHER one!?\n\n"
                        "Impressive. Such a coincidence. Or you attract traitors. For some reason.\n\n"
                        "Well. You know the procedure."
                    )
                else:
                    text = (
                        "ANOTHER one!?\n\n"
                        "The detective here! You should work for the Ministry of Security! Ha!\n\n"
                        "Well, well... you know the procedure. Congratulations!"
                    )
        else:  # noqa: PLR5501
            if self.interlocutor.sociability100 < 20:
                if self.interlocutor.sympathy100 < 20:
                    text = (
                        "WHAT!?\n\n"
                        "Fuck.\n\n"
                        "Damn. Ok. You're not in trouble. This time. We take those credits. Criminals are arrested."
                        " You get new codes."
                    )
                else:
                    text = (
                        "WHAT!?\n\n"
                        "Wow.\n\n"
                        "Ok. It's all right. We take those credits. Criminals are arrested."
                        " You get new codes. Thank you."
                    )
            else:  # noqa: PLR5501
                if self.interlocutor.sympathy100 < 20:
                    text = (
                        "WHAT!?\n\n"
                        "Fuck.\n\n"
                        "Damn. Ok, 'hero' <scoffs>. You did the right thing, this time. We will take those Credits,"
                        " we buy things from UniDiv with them. And you get new codes. You can visit your 'friend'"
                        " in prison."
                    )
                else:
                    text = (
                        "YOU DID WHAT!?\n\n"
                        "The detective here! Ha ha ha!\n\n"
                        "Ok, ok! Thank you for your service, Pilot! We will use those credits to buy stuff from"
                        " UniDiv and the asshole will land in jail for some long, long years. Oh, and you need new"
                        " codes for your mines - we will set a trap, but you don't worry about that, just collect"
                        " your ore normally.\n\n"
                        "And again, thank you. This will be known."
                        f" I salute you, you are a real {self.interlocutor.get_player_title()}."
                    )
            text += "\n\n<Hands over new codes for your mines>"
        return text

    def traitor_credits_for_the_ship(self) -> str:
        """The Ringmaster is the only one who sells the ship. Only while the pilot has sold the codes and not ratted."""
        if (self.interlocutor.role is not RINGMASTER or not self.traitor_sold_codes_here()
                or self.traitor_ratted_here()):
            return "You heard about that? Yes, some filthy traitors do this." if self.interlocutor.loyalty100 >= 20 \
                else "Shhh... dangerous talk. Shut up."
        self.offer(
            [
            "Yes, I am. I want to get out of here. With *my* ship. I've earned that much.",
            "No, no, that was a misunderstanding."
            ],
            self.traitor_sure_answered
            )
        return (
            f"{self.interlocutor.address(self.player, True)}... this is a very serious matter. Are you really"
            " telling me you want to demand 'property' on that ship... betray our principles, abandon the Community?"
            " There is no turning back, then. But if you have somehow managed to get your hands on 'credits'... it"
            " is a problem already."
            )

    def traitor_sure_answered(self, answer: int) -> None:
        if answer == 0:
            self.say(self.traitor_valuation)
        else:
            self.say(self.traitor_ready_to_explain)

    def traitor_ready_to_explain(self) -> str:
        self.offer(
            ["Yes, no problem, I will explain everything.", "Suit yourself. I won't rat anybody."],
            self.traitor_explain_answered
            )
        return (
            "I cannot let that be now, Pilot. Credits are illegal. You will be searched. Are you ready to tell"
            " us everything about this dirty matter?"
        )

    def traitor_explain_answered(self, answer: int) -> None:
        if answer == 0:
            self.say(self.traitor_rat)  # the rat: the same reputation and credits as on the credits talk
        else:
            self.say(self.traitor_refused_to_explain)
            self.traitor_imprisoned()

    def traitor_refused_to_explain(self) -> str:
        return (  # Talked too much, now there is no way back.
            "Your loyalties are misplaced, Pilot. But if you have stolen from the Community, misusing what"
            " we entrusted to you, you will have time to think about this in prison."
        )

    def traitor_valuation(self) -> str:
        """The Ringmaster names the price of the ship, its cargo and its equipment, and the pilot's credits decide:
        enough pays for it; more than two thirds of the price offers to betray the contact for it; less ends the game.
        """
        price: float = self.traitor_price()
        credits: float = self.player.credits
        figures: str = f" (price {price:.0f} credits, the pilot has {credits} credits)"
        logging.info(f"traitor_valuation:{figures}.")
        if credits >= price:
            self.offer(
                    [
                        "You sell me the ship, I sell you the info. Nothing personal, just business.",
                        "I am not a rat, Ringmaster."
                        ],
                       lambda answer: self.traitor_informing_answered(answer, price))
            return (
                "You leave us with no other option. Such an amount of stolen credits can still help the"
                " Community in a way throwing you in prison does not. But will you tell us who organised this?"
                " If you do, you will be able to keep part of your filthy money."
                )
        if credits > price * 2 / 3:
            self.offer(
                    ["You are... fuck. Ok. I'll tell you all. Just let me free.",
                        "Suit yourself, then. I am not a rat."
                        ],
                    self.traitor_betrayal_answered
                    )
            return (
                "This is a good amount of money. But not enough, traitor. I think we can let it rot, and instead"
                " make justice with you.\n\n"
                "Unless, that is, you are ready to tell us everything about your contacts. Then you could still get"
                " your... 'deal'."
            )
        self.offer(["Wait..."], self.traitor_not_enough)
        return (
            "... and you think that compensates us for everything? The faith we put on you, the years of education,"
            " the ore you have stolen, breaking our laws? You should have solicited exile instead. We would have"
            " respected that. What you have done... is just a crime."
            )

    def traitor_informing_answered(self, answer: int, price: float) -> None:
        """With enough credits: informing on the criminals (no reputation gain) pays only the price, and the pilot keeps
        the rest. Without it, the whole of the credits go."""
        if answer == 0:
            self.say(self.traitor_informed)
            self.traitor_denounce()
            self.traitor_sell_ship(price)
        else:
            self.traitor_sell_ship(self.player.credits)

    def traitor_informed(self) -> str:
          # A player usually does not see this, the game over dialog hides it.
        return "Good. At least this social disease will be contained."

    def traitor_betrayal_answered(self, answer: int) -> None:
        if answer == 0:
            self.say(self.traitor_betrayal_accepted)
            self.traitor_denounce()
            self.traitor_sell_ship(self.player.credits)
        else:
            self.say(self.traitor_betrayal_refused)
            self.traitor_imprisoned()

    def traitor_betrayal_accepted(self) -> str:
        return "A wise decision as your last here, traitor. We will honour our part of this agreement."

    def traitor_betrayal_refused(self) -> str:
        return (  # Money was not enough, won't rat.
            "Your loyalties are misplaced, Pilot. But after stealing from the Community, misusing what"
            " we entrusted to you and betraying everything we stand for, you will have time to think about this"
            " in prison. You should have simply demanded exile instead, if you hated us so much."
        )

    def traitor_not_enough(self, answer: int) -> None:
        self.traitor_imprisoned()

    def traitor_price(self) -> float:
        """What the ship, its cargo and its equipment are worth now, in credits.
        Fuel, energy and maintenance do not count."""
        ship = self.player.ship
        prices: dict[str, float] = political_entity.UNITED_DIVERSITY.exchange_reputation_changes
        hold = ship.cargo_hold
        total: float = ship.PRICE_AT_700
        total += sum(getattr(hold, key) * prices[key] for key in ('air', 'water', 'food', 'mines', 'ore', 'raw_water'))
        if ship.has_scoop:
            total += prices['scoop']
        if ship.has_solar_panels:
            total += prices['solar_panels']
        heat_shield_key: Optional[str] = {
            ship.HeatShield.HeatShieldOne: 'heat_shield_1', ship.HeatShield.HeatShieldTwo: 'heat_shield_2'
        }.get(ship.heat_shield)
        if heat_shield_key is not None:
            total += prices[heat_shield_key]
        return at_date(total, self.date_time)

    def traitor_sell_ship(self, cost: float) -> None:
        """The pilot pays `cost` credits and owns the ship: the end of the game for this version. The rest of the
        credits stay with the pilot.
        TODO when international travel is implemented, teleport the pilot outside the borders instead of game over.
        """
        self.player.adjust_reputation(- self.player.reputation - 100)
        self.player.credits = round(self.player.credits - cost)
        self.player.flags.add(OWNER_FLAG)
        self.player.game_over(
            "You are finally free from Those-Who-Share. They escort your ship to the border and leave you here."
            " In a sense, it is only now that your adventures begin.\n\n"
            "DEVELOPER NOTE: I have not implemented international travel yet. Keep the last savegame so that you can"
            " use it when I do. And better tell me: eduardo.silva.lopez@hotmail.com"
            )

    def traitor_imprisoned(self) -> None:
        """The pilot is imprisoned for good: the game is over for this version."""
        self.player.game_over(
                "They contraint you, they send you in a shuttle to the inner systems, and then you are"
                " assigned a labor camp, where you will reflect about your decisions."
            )

    # endregion

    # region Auxiliar methods

    def _standing_flags(self) -> set[str]:
        return self.player.political_status[political_entity.THOSE_WHO_SHARE].flags

    def unfriendly_rejections(self, soc: float) -> list[str]:
        """The unfriendly rejections the person may say at random, by sociability: curt ones, then ones that remind the
        pilot of what they did (someone is refused only when the pilot did something terrible in their eyes). Add more
        to a band."""
        if soc < 20:
            return [
                "Leave me alone.",
                "Leave me alone, Pilot.",
                "Just leave me.",
                "Fuck off.",
                "Bugger off.",
            ]
        elif soc < 80:
            return [
                "You. What do you want?",
                "Oh, no, leave me alone.",
                "Oh, it's you again. Why don't you go bother someone else?",
                "Leave me alone, Pilot. You've done enough.",
                "You. What do you want? Don't you think you have done enough?",
            ]
        return [
                "Yes, I know who you are. And I know what you have done. But... no. Just leave me alone, ok? Sorry.",
                "Oh, no, don't approach me, ok? I don't want troubles and you have done enough. Just leave me alone.",
                "Bugger off, will you? I know what you did. Nobody wants to talk with you.",
        ]

    def talk_political(
        self, topics: PoliticalTopics, friend_topics: PoliticalTopics, generic: tuple[PoliticalTexts, ...],
        own_entity: bool, praise_guarded: bool,
    ) -> str:
        """The shape of the political talks. Below sympathy 20 a brush-off. Otherwise the topics, drawn at random and
        weighted by their score (no repeats); the friend topics from sympathy 80 on. The number of topics grows with
        sociability, and each topic after the first is bound to the one before. Under sociability 20, one short line,
        from a topic or from `generic`."""
        soc: float = self.interlocutor.sociability100
        sym: float = self.interlocutor.sympathy100
        if sym < 20:
            return random.choice(self.unfriendly_rejections(soc))
        tone: int = self.political_tone(own_entity, praise_guarded)
        pool_topics: PoliticalTopics = friend_topics if sym >= 80 else topics

        if soc < 20:  # Short replies first.
            lines: list[str] = [entry[1][tone + 1] for entry in pool_topics.values()] + list(generic[tone + 1])
            return random.choice(lines)

        # From 20 on, the count of topics grows with sociability: 1 and 2 stay the most frequent.
        x: float = (soc - 20) / 80
        count: int = random.choices([1, 2, 3, 4], weights=[3 - 2 * x, 2, 1.5 * x, 0.5 * x ** 3])[0]
        names: list[str] = list(pool_topics)
        chosen: list[str] = []
        for _ in range(count):
            name: str = random.choices(names, weights=[pool_topics[topic][0] for topic in names])[0]
            names.remove(name)
            chosen.append(name)
        paragraphs: list[str] = [
            text if isinstance(text, str) else random.choice(text)
            for text in (pool_topics[name][2][tone + 1] for name in chosen)
        ]
        bound: list[str] = paragraphs[:1] + [
            self.bind_to_previous(text, name) for name, text in zip(chosen[1:], paragraphs[1:])
        ]
        return "\n\n".join(bound)

    def bind_to_previous(self, text: str, topic: str) -> str:
        """The text of a later topic, started by a random binder that links it to the topic before ('And', 'Also'...),
        so the talk can reuse it. A binder may name the topic with `{topic}`. The first word then goes in lower case,
        except the pronoun I and a word with a capital inside (a name, an acronym)."""
        binder: str = random.choice([
            "And",
            "By the other side,",
            "But also,",
            "But also, on {topic},",
            "Anything on {topic},",
            "Also,",
            "Then,",
            "Then, on {topic},",
        ]).format(topic=topic)
        word, space, rest = text.partition(" ")
        if word != "I" and not word.startswith("I'") and word[1:].islower():
            word = word[0].lower() + word[1:]
        return f"{binder} {word}{space}{rest}"

    def political_tone(self, own_entity: bool, praise_guarded: bool) -> int:
        """-1, 0 or 1 from how much the person likes the entity. Their own entity: loyalty alone decides, the more
        loyal the more they approve. The other one: loyalty against it weighs most, empathy less (the less empathic,
        the more they like the money and the force). With praise_guarded, approval of the other one is said only by
        the very sociable, the hardly loyal or the trusted; otherwise it falls to 0, a nuanced rejection."""
        loy: float = self.interlocutor.loyalty100
        if own_entity:
            return -1 if loy < 20 else 0 if loy < 80 else 1

        emp: float = self.interlocutor.empathy100
        soc: float = self.interlocutor.sociability100
        sym: float = self.interlocutor.sympathy100
        # Simplify loy and emp. The 1.212 is to keep variance.
        likes_them: float = 50 + 1.212 * (0.8 * (50 - loy) + 0.2 * (50 - emp))
        tone: int = -1 if likes_them < 20 else 0 if likes_them < 80 else 1
        if praise_guarded and tone == 1 and not (soc >= 80 or loy < 20 or sym >= 80):
            tone = 0
        return tone

    def days_to_birthday(self) -> Optional[int]:
        """birthday discovery -2 to +1 days is relevant."""
        import game_environment as gem
        now: datetime = gem.current_environment.date_time
        birthday: date = self.interlocutor.dob.date()
        days_to_birthday: Optional[int] = None
        for offset in range(-2, 2):
            day = (now + timedelta(days=offset)).date()
            if day.day == birthday.day and day.month == birthday.month:
                days_to_birthday = offset
                break
        return days_to_birthday

# endregion
