"""A conversation of the outpost's chat (the Chat option of the outpost screen): started by a conversation tag, with the
person selected in the list. It writes into the chat's log (chat_log.py), never into a dialog window.

The texts are written with `say` (the person's line, with its [marks] that make new tags) and the replies with `offer`
(the callback gets the index of the reply the player chose). The conversation dies out when it offers nothing more: the
player then starts the next one from a tag, in the same log. `start` says the tag as the pilot's line, then the answer
(for the presentation tag, the pilot's line is Player.present_yourself).
Flags can be written to mark important events of the conversation.

Note for Claude: before writing or reworking a `talk_*` method here, read temp/ideas/outpost_chat_methods.md (the rules,
the pattern to follow and how to test). Do not read it for any other task.
"""

from __future__ import annotations
import random
from datetime import date, datetime, timedelta
from typing import Callable, List, Optional

from galaxies.people.chat_log import NPC, PLAYER, ChatLog, parse_marks
from galaxies.people.conversation import Conversation
from galaxies.people.person import Person
from galaxies.people.player import Player

# A political text: its three tones, in the order -1, 0, 1.
PoliticalTexts = tuple[str, str, str]
# A topic: its relevance score, a short line per tone for the low-sociability replies, and a text per tone.
PoliticalTopics = dict[str, tuple[float, PoliticalTexts, PoliticalTexts]]

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

    return f"{dt.strftime('%B')}, the {ordinal}"

class OutpostChat(Conversation):
    def __init__(self, player: Player, interlocutor: Person, log: ChatLog, tag: str) -> None:
        super().__init__(player, interlocutor)
        self.log: ChatLog = log  # the chat of the outpost screen: the texts go there
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
        if self.tag in self.reactions:
            self.say(self.reactions[self.tag])
        else:
            self.say(self.talk_unknown_tag)

    def remember(self) -> None:
        """Writes the interaction into the person's record now, not only when the conversation closes, so a save made
        while the chat is open keeps it."""
        self.interlocutor.last_communication_at = self.date_time
        self.interlocutor.record()

    def say(self, generator: Callable[[], str]) -> None:
        """The person says `text` in the chat. Its [marks] become the pilot's conversation tags, from now on. Time
        passes."""
        import game_environment as gem
        gem.current_environment.date_time += timedelta(seconds=60)

        text: str = generator()
        words, tags = parse_marks(text)
        self.player.conversation_tags.update(tags)
        self.log.add(NPC, words)
        self.remember()

    def offer(self, labels: List[str], then: Optional[Callable[[int], object]] = None) -> None:
        """Offers the player `labels` as replies. Choosing one calls `then` with its index; with no labels, the
        conversation has nothing more to say."""
        self.log.offer(labels, then)

    # region Talk
    def reactions_index(self) -> dict[str, Callable[[], str]]:
        return {
            Player.PRESENTATION_TAG: self.talk_present_yourself,
            'asteroids': self.talk_asteroid,
            'base': self.talk_base,
            'belt': self.talk_belt,
            'founders': self.talk_founders,
            'happy birthday': self.talk_happy_birthday,
            'job': self.talk_job,
            'life': self.talk_life,
            'noobie': self.talk_noobie,
            'paladin xi': self.talk_paladin_xi,
            'pgms': self.talk_pgms,
            'portal': self.talk_portal,
            'space': self.talk_space,
            'the network': self.talk_the_network,
            'the shining throne': self.talk_the_shining_throne,
            'those-who-share': self.talk_those_who_share,
            'united diversity': self.talk_united_diversity,
        }

    def talk_present_yourself(self) -> str:
        if not any("Presented himself." in lines for lines in self.interlocutor.interactions.values()):
            self.interlocutor.adjust_sympathy(1)
            self.flags.append("Presented himself.")
            return self.talk_present_yourself_first_time()
        return self.talk_present_yourself_further_times()

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
                    return "The [noobie]. We will see how much you last."
                else:
                    return (
                        "I know, [Paladin Xi]'s last discovery. Eager to kill yourself, yeah, [noobie]?"
                        "[Space] is hard. You will see <smiles a wicked smile>."
                    )
            else:  # noqa: PLR5501
                if sym < 20:
                    return "You. What do you want? Don't you think you have done enough?"
                elif sym < 80:
                    return (
                        "Yeah, I know. The [noobie]. We will see how much you last, noobie. [Space] is hard."
                        " [Paladin Xi] wants to rush things, wants everybody on board. He has killed already some."
                        " Noobs like you."
                    )
                else:
                    return (
                        "I know, [Paladin Xi]'s last discovery. Eager to kill yourself, yeah, [noobie]?"
                        " [Space] is hard. You will see <smiles a wicked smile>."
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
                    return f"Hello, Pilot, I am {self_present}. How are you? How's [life] going?"
                else:
                    return (
                        f"Nice to meet you, {you}! How are you doing? How is [space] being to you?"
                        f"\n\nMe, I prefer to remain between the outpost and the [base]. Less risky, you know?"
                        f" And people are nice here."
                    )
            else:  # noqa: PLR5501 - High soc
                if sym < 20:
                    return (
                        "Oh, no, [noobie], don't approach me, ok? I don't want troubles and you have done enough,"
                        " just leave me alone. You should think about your [life]."
                    )
                elif sym < 80:
                    return (
                        "So here we have you, [Paladin Xi]'s last discovery. He wants everybody on [space]."
                        " Take care. It is unforgiving. No beacon signal can save you if you are too far away,"
                        " drifting between planets. [Noobie]s get killed."
                    )
                else:
                    return (
                        f"Nice to meet you, {you}! How are you doing?"
                        " Be careful in [space]. It is hard. You can get yourself killed. Avoid the asteroid [belt]s."
                        "\n\nBut if you build yourself a good basis of mines and then do some science work on rocks,"
                        " everything will be ok. Safe way to build up some reputation and then back home, yes?"
                        "\n\n[Life]'s too precious to loose it so soon."
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
                        "Yes, I know who you are. And I know what you have done. Look... [space] is hard. I know."
                        " But... no. Just leave me alone, ok? Sorry."
                    )
                elif sym < 80:
                    return (
                        f"Hello, Pilot, I am {self_present}. How are you? How has [space] treated you lately?"
                        f"\n\nIs [Paladin Xi] already proud of you? Ha!"
                        f"\n\nDo you need a coffee? I need a coffee!"
                    )
                else:
                    return (
                        f"Nice to meet you, {you}! Heard good things about you."
                        f"\n\nHow is [space] treating you? [Paladin Xi] is not a bad guy, but he is ruthless. I see"
                        f" the ships you start with. Ugh."
                    )
            else:  # noqa: PLR5501 - High soc
                if sym < 20:
                    return (
                        "DON'T YOU DARE! Oh, don't you dare to approach me, no, no, I know the likes of you!"
                        " Just leave me alone, [life] here is hard enough, just go away and let me have my meal"
                        " in peace. By the [Founders] I don't need this right now!"
                    )
                elif sym < 80:
                    return (
                        "So here we have you, [Paladin Xi]'s last discovery! He wants everybody on [space].\n\n"
                        " I get, we need the [PGMs], and more valuable [asteroids], but the belts are dangerous."
                        " People have been killed. No beacon signal can save you if you are too far away,"
                        " drifting between planets. Be careful, [noobie], ok? [Life] is a precious thing."
                    )
                else:
                    return (
                        f"Nice to meet you, {you}! How are you doing?"
                        "\n\nI have heard about you. Good things! Do you want a coffee? Or maybe something... stronger?"
                        "\n\nHow is [space] treating you? Making our [Paladin Xi] proud? Tell me!"
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
                    return "Hi. What's the matter?"
                else:
                    return "Hey. Still alive, apparently. Respect."
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
                        f"Ah, Pilot {self.player.surname}. Hello. I was going to make myself a tea. One for you?"
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
                        f"Hey, {you}, how are you? Alive, I see! I'm glad. How is good old [space]"
                        f" treating you lately? Friend, I miss {self.interlocutor.planet_of_birth}. And you, do"
                        f" you miss home?"
                    )
                else:
                    return (
                        f"{you}, my friend! How are you doing? What can I do for you?"
                    )

    def talk_asteroid(self) -> str:
        return (
            "Have you visited one? Sometimes the labs ask for somebody. I mean, I get it. But... damn. Some are"
            " simply fucking far away. Others are... in the [belt]. And those are worse."
        )
    def talk_base(self) -> str:
        return (
            "Have you been there lately? People say Miners do not need it like us. I miss getting out of this"
            " uniform, I tell you. My shorts and a cocktail, looking at a garden. That's [life]."
            " Almost like a planet."
        )
    def talk_belt(self) -> str:
        return (
            "Don't go there if you don't want to get killed. Not without a well-prodected ship"
            " and a ton of sealant, at least."
        )
    def talk_founders(self) -> str:
        return (
            "Well, the ones who founded Those-Who-Share, you know?"
        )

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

    def talk_job(self) -> str:
        if self.interlocutor.how_happy_with_role() == 0 and self.interlocutor.sociability100 >= 20:
            if self.interlocutor.main_problem_with_role().startswith("+"):
                if self.interlocutor.main_problem_with_role().endswith("loy"):
                    return "I wish I worked in something more relevant."
                elif self.interlocutor.main_problem_with_role().endswith("emp"):
                    return "I wish I worked in something more helpful for people."
                else:
                    return "I wish I worked more with people."
            else:  # noqa: PLR5501
                if self.interlocutor.main_problem_with_role().endswith("loy"):
                    return "I wish I worked in something less demanding."
                elif self.interlocutor.main_problem_with_role().endswith("emp"):
                    return "I wish I had more time for myself."
                else:
                    return "I wish I could concentrate more, focus."
        elif self.interlocutor.how_happy_with_role() == 1:
            return "My [job] is ok."
        elif self.interlocutor.how_happy_with_role() == 2:
            return "I really like my [job]."
        else:
            return "A [job]'s a [job]."


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
                    return "[Job]'s good. Life's ok."
                return "Life's ok."
            else:
                if days_to_birthday == 0:
                    return "Doing ok. My birthday today."
                if self.interlocutor.how_happy_with_role() == 1:
                    return "[Job]'s ok. Doing ok. Thanks."
                return "Doing ok. Thanks."
        elif soc < 80:
            if sym < 20:
                job: str = " I don't have enough with my [job]?" if self.interlocutor.how_happy_with_role() == 0 else ""
                if days_to_birthday == 0:
                    return f"On my birthday, for fuck's sake.{job} Leave me alone."
                return f"Oh, no.{job} Leave me alone."
            elif sym < 80:
                text = (
                    f"Me? I was born in {self.interlocutor.place_of_birth}, I am {self.interlocutor.age} years old,"
                    f" I work here as a {self.interlocutor.role.name}, that's my [job]."
                    f" People say I'm {self_description}."
                )
                if days_to_birthday == -2:
                    text += "\n\nI had my birthday two days ago."
                elif days_to_birthday == -1:
                    text += "\n\nMy birthday was yesterday."
                elif days_to_birthday == 0:
                    text += "\n\nToday is my birthday."
                elif days_to_birthday == 1:
                    text += "\n\nTomorrow is my birthday."
                return text
            else:
                text = (
                    "Me? Thank you for asking, friend <smiles>."
                    f" Well, I was born in {self.interlocutor.place_of_birth}, I am {self.interlocutor.age} years old,"
                    f" I work here as a {self.interlocutor.role.name} from {self.interlocutor.work_hours_text()}."
                    f" People say I'm {self_description}."
                    f"\n\nOh... and {self.interlocutor.hobby}"
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
                    f" I work here as a {self.interlocutor.role.name}, that's my [job]."
                    f" People say I'm {self_description}."
                )
                if days_to_birthday == -2:
                    text += "\n\nI had my birthday two days ago. Too late for [Happy birthday]! <laughs>."
                elif days_to_birthday == -1:
                    text += "\n\nMy birthday was yesterday, you just missed my '[Happy birthday]!' <laughs>."
                elif days_to_birthday == 0:
                    text += "\n\nToday is my birthday. You can still wish me '[happy birthday]' <smiles>."
                elif days_to_birthday == 1:
                    text += "\n\nTomorrow is my birthday, if you want to wish me [happy birthday] <smiles>."
                return text
            else:
                text = (
                    "Me? You want to talk about my life? I am flattered <laughs>."
                    f" Well... ok, I was born in {self.interlocutor.place_of_birth}. I really miss home sometimes."
                    f" I had {self.interlocutor.childhood}, I would say. But that's the past."
                    f" I am {self.interlocutor.age} years old. I know, I know."
                    f" I work here as a {self.interlocutor.role.name}, that's my [job]."
                    f" People say I'm {self_description}."
                    f"\n\nOh... and {self.interlocutor.hobby}"
                )
                if days_to_birthday == -2:
                    text += "\n\nBTW, I had my birthday two days ago."
                elif days_to_birthday == -1:
                    text += "\n\nBTW, my birthday was yesterday, if you want to know."
                elif days_to_birthday == 0:
                    text += "\n\nYou know something? Today is my birthday! Will you wish me [happy birthday]?"
                elif days_to_birthday == 1:
                    text += (
                        "\n\nLook, so... tomorrow is my birthday. You could come by. Even without a present."
                        " I forgive you <laughs>."
                    )
                return text

    def talk_noobie(self) -> str:
        return (
            "Well, that's... no offense intended. [Paladin Xi] finished your training recently, yes? So..."
            " that's it."
        )
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
            " Platinum-group is crucial. No PGMs - no energy, shields, no ooompf. Just cold [space]."
        )
    def talk_space(self) -> str:
        return (
            "Unforgiving, yes? And fucking huge. In your head, make three layers of it: remaining around a"
            " planet with an outpost. Easy peasy and safe. Interplanetary. Hard and dangerous. Interstellar."
            " Just don't. Go to the [base]s, use the [portal]s, remain in [the network]"
        )
    def talk_the_network(self) -> str:
        return (
            "Every year a bit larger. I don't know, we must have like two dozen systems by now. I mean"
            " [Those-Who-Share]. Sure, '[United Diversity]', UniDiv, has more. [The Shining Throne], no idea."
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
                "They're mad. Some live in luxury while others are enslaved. Literal slaves. Fuck.",
                "They have slaves. Maybe they don't torture them or so. But... slaves. Ugh.",
                "They have slaves, but I've heard they're not so many, and people can free themselves. No idea, ok?",
            )),
            'luxury': (40, (
                "Soap operas. Ugh.", "Soap operas are nice.", "Parks and boulevards. Gorgeous.",
            ), (
                "Luxury built on the back of poor serfs and servants. Corruption and filth, the lot of them.",
                "Not that I'd like to *live* there, but the soap operas are really nice. Still...",
                "Hard to say. The parks, the boulevards, the clothes. It's so gorgeous. But hey, here is also ok.",
            )),
            'honour': (30, (
                "Honour and beauty. Bah.", "They're not like us.", "Super-humans. Hm.",
            ), (
                "They look for the 'super-humans', all that's whose more handsome. Stupid.",
                "They're just not like us. For them it's all about 'honor' and 'beauty' and 'chivalry'.",
                "They're completely different to us, aren't they? Honour, beauty, protecting the weak."
                " I see what they mean.",
            )),
            'gardens': (30, (
                "Parks. Hm.", "Their gardens.", "The boulevards. Wow.",
            ), (
                "They have their parks and fountains and music, but it's all for the aristocrats.",
                "Their parks, their music. I'd like to see that in the shows.",
                "Parks, fountains, music, dances, poetry. They live, and we don't. They reward merit. We don't.",
            )),
            'freedom': (40, (
                "Own a person. Disgusting.", "Slaves. I don't get it.", "Heard slaves have rights.",
            ), (
                "How can one people own another human being? That's fucking disgusting.",
                "They *say* the lower classes have rights, but who knows what happens behind closed doors.",
                "I've heard the slaves have rights, and the Knights have lots of duties. Things are not how"
                " people want them to be.",
            )),
        }
        friend_topics: PoliticalTopics = {
            'chapter': (40, (
                "Soap operas. Pah.", "Some shows are cool.", "Soap operas, guilty.",
            ), (
                "<whispers> In confidence, I never miss a chapter. But it's all slaves and depravity, friend. Makes no"
                " sense. That's why it's so interesting!",
                "<whispers> In confidence, I never miss a chapter. Gorgeous *cutlery*, for the [Founders]' sake. But"
                " at what cost?",
                "<whispers> I have heard... things, you know. The slaves have a lot of rights. The powerful have a lot"
                " of duties. Protect the weak. There is some logic there.",
            )),
            'ownership': (40, (
                "Own a person? Never.", "People are not ours to own.", "Own a house, sure. Person? Strange.",
            ), (
                "Own a person? How can one people own ANOTHER HUMAN BEING? That's over me. Fuck them all."
                " With a wrench.",
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
                "<Whispers> They spend so much in those gardens for the aristocrats. Meh.",
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
                "The biggest industry of mankind, and the factories are pleasant places to be. I like my"
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
                " you, you can get anything you want, a better apartment, a better [job]. Fair, they say.",
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
                "Nothing made just for beauty, only statues, posters and big screens. Art is for the propaganda, and"
                " that's sad.",
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
                "The [Founders]. Hm.", "The [Founders], sure.", "The [Founders], yes.",
            ), (
                "<Whispers> The [Founders] wanted empathy, and now we watch each other."
                " Something went wrong along the way.",
                "<Whispers> The [Founders] wanted empathy first. We try. That's more than others do.",
                "<Whispers> The [Founders] had it right. Empathy first, and nobody left alone. I wouldn't trade this"
                " square for anything.",
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
                "Fifty systems with cities and the Moon on top, the most crowded world there is. A fat, bloated giant,"
                " that's all they are. Big.",
                "Fifty systems with cities, against our fifteen. And the Moon, the most crowded world by far. Big, yes."
                " Big is not the same as good.",
                "Fifty systems with cities. Fifteen ours. And the Moon, with more people than anywhere else. Imagine"
                " being part of that.",
            )),
            'money': (30 + 0.6 * loy, (
                "Money, money. Disgusting.", "They love money.", "Get rich, get admired.",
            ), (
                "Everything about money, yes? The rich are admired just for being rich. As if here in [space] you could"
                " eat money, drink it or breathe it.",
                "They love money, yes. The rich are admired and get their luxury. Maybe some earned it, ok. But a"
                " society that measures people in money? No, thanks.",
                "You make something people want to buy, you get rich, you get admired. No sacks of stamps, no waiting"
                " for a title. There is a logic there.",
            )),
            'military': (70 - 0.4 * emp, (
                "Biggest army. Sick.", "Big guns. Nervous.", "Guns for ETs. Good.",
            ), (
                "The largest armed forces of mankind, and a cult of violence around them. Still licking the wounds of"
                " the war against the Exterminating Mother two hundred years ago. Sick.",
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
                " Ghettos. Better than slavery, I suppose. Not like [The Shining Throne].",
                (
                    "There is a basic income, healthcare for everybody and nobody is a slave."
                    " Not like [The Shining Throne]. Yes, there are cells and ghettos... but it is a start."
                ),
            )),
            'industry': (0.6 * loy + 0.4 * min(max(rep, 0), 100), (
                "We build more. Obviously.", "Second in industry.", "Good at industry, yes.",
            ), (
                "But they don't build as we do. We have the biggest industry of mankind. They have the money,"
                " [Those-Who-Share] has the PGMs. We know that more than many, yes?",
                "They are the wealthy guys, ok. But industry? That is ours. They come second.",
                "Well. They are only second in industry, after us. Small comfort if you ask me.",
            )),
            'federalism': (0.4 * loy + 20, (
                "Their experiment. Insulting.", "Interesting experiments. Hm.", "Respect, not rivals.",
            ), (
                (
                    "You know what they think of us? An interesting experiment. EXPERIMENT. As if the [Founders] had"
                    " built a laboratory and not a community."
                ),
                "They say they find the other entities interesting experiments, and cultural diversity something to"
                " encourage. Nice words. A bit condescending, though. We are nobody's experiment.",
                "They see everybody else, us too, as interesting experiments, not as rivals. A kind of respect we don't"
                " give.",
            )),
        }
        friend_topics: PoliticalTopics = {
            'poor': (40, (
                "Cells, ghettos. Ugh.", "Cells. Shh.", "Basic income. Real.",
            ), (
                "<Whispers> The cells, the ghettos. Nobody in the State cares, friend. They just want to look big.",
                "<Whispers> Some live well and some live in cells. I can't say that in the square.",
                "<Whispers> Their basic income is a real thing. Don't tell anyone I said so.",
            )),
            'science': (30, (
                "Experts vote. Ugh.", "Brains. Shh.", "Best science.",
            ), (
                "<Whispers> The science is incredible, and the experts decide who votes. Nobody asked us, friend.",
                "<Whispers> The science is incredible. I'd like to see their labs once, that's all.",
                (
                    "<Whispers> Their science is the best there is. I envy them that a little."
                    " Don't tell anyone I said so."
                 ),
            )),
            'life': (30, (
                "Parks. Cinemas. Ugh.", "Parks. Shh.", "Concerts. Wish I'd seen.",
            ), (
                "<Whispers> The parks and the concerts are nice, but I wouldn't go near the rest.",
                "<Whispers> It has its charm: the coffee shops, the bars, the concerts. Nobody here would admit it.",
                "<Whispers> I'd love to visit. Concerts, cinemas, bars. Don't tell anyone I said so.",
            )),
            'money': (30, (
                "Money above all. Ugh.", "Money, money. Shh.", "Rich and admired. Good.",
            ), (
                "<Whispers> Money above everything, and the very wealthy in power. Nobody can say that in the square.",
                "<Whispers> Money is everywhere there, and I'm not sure it's so bad. Don't quote me.",
                "<Whispers> The rich are admired for what they produce, and that's a logic I can respect. Don't tell"
                " anyone.",
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

    # region Auxiliar methods

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
        sociability. Under sociability 20, one short line, from a topic or from `generic`."""
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
        return "\n\n".join(pool_topics[name][2][tone + 1] for name in chosen)

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
