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
from datetime import date, datetime, timedelta
from typing import Callable, List, Optional

from galaxies.people.chat_log import NPC, PLAYER, ChatLog, parse_marks
from galaxies.people.conversation import Conversation
from galaxies.people.person import Person
from galaxies.people.player import Player

def pretty_date(dt: datetime) -> str:
    ordinal: str = ''
    if 11 <= dt.day % 100 <= 13:
        ordinal = f"{dt.day}th"
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
        self.reactions: map = self.reactions_index()
        # The lines of this time are the person's record from now on: the list is shared with `interactions`, so a
        # second conversation in the same visit (the same game time) adds to it instead of replacing it.
        self.interaction_lines = interlocutor.interactions.setdefault(self.date_time.replace(microsecond=0), [])
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
        self.log.add(PLAYER, [(word, None) for word in pilot_line.split()])
        if self.tag in self.reactions:
            self.say(self.reactions[self.tag])
        else:
            self.say(self.talk_unknown_tag)

    def remember(self) -> None:
        """Writes the interaction into the person's record now, not only when the conversation closes, so a save made
        while the chat is open keeps it."""
        self.interlocutor.last_communication_at = self.date_time
        self.interlocutor.record()

    def say(self, generator: Callable[[OutpostChat], str]) -> None:
        """The person says `text` in the chat. Its [marks] become the pilot's conversation tags, from now on. Time
        passes."""
        import game_environment as gem
        gem.current_environment.date_time += timedelta(seconds=60)

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
            Player.PRESENTATION_TAG: self.talk_present_yourself,
            'asteroids': self.talk_asteroid,
            'belt': self.talk_belt,
            'founders': self.talk_founders,
            'happy birthday': self.talk_happy_birthday,
            'life': self.talk_life,
            'noobie': self.talk_noobie,
            'paladin xi': self.talk_paladin_xi,
            'pgms': self.talk_pgms,
            'space': self.talk_space,
            'the base': self.talk_the_base,
            'the network': self.talk_the_network,
            'the portal': self.talk_the_portal,
            'the shining throne': self.talk_the_shining_throne,
            'those-who-share': self.talk_those_who_share,
            'united diversity': self.talk_united_diversity,
        }

    def talk_present_yourself(self) -> str:
        if not any("Presented himself." in lines for lines in self.interlocutor.interactions.values()):
            self.interlocutor.adjust_sympathy(1)
            self.interaction_lines.append("Presented himself.")
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
                        f"Nice to meet you, {self.player.first_name}! How are you doing? How is [space] being to you?"
                        f"\n\nMe, I prefer to remain between the outpost and [the base]. Less risky, you know?"
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
                        f"Nice to meet you, {self.player.first_name}! How are you doing?"
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
                        f"Nice to meet you, {self.player.first_name}! Heard good things about you."
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
                        f"Nice to meet you, {self.player.first_name}! How are you doing?"
                        "\n\nI have heard about you. Good things! Do you want a coffee? Or maybe something... stronger?"
                        "\n\nHow is [space] treating you? Making our [Paladin Xi] proud? Tell me!"
                    )

    def talk_present_yourself_further_times(self) -> str:
        # Short names to make the rest more legible
        emp: float = self.interlocutor.empathy100
        soc: float = self.interlocutor.sociability100
        sym: float = self.interlocutor.sympathy100

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
                    return f"{self.player.first_name}. Go."
                elif sym < 80:
                    return "Hello <looks suspiciously>."
                else:
                    return "Hey <shy smile>."
            elif soc < 80:
                if sym < 20:
                    return f"{self.player.first_name} {self.player.surname}. Now my day is screwed."
                elif sym < 80:
                    return f"Hello {self.player.first_name}, how are you?"
                else:
                    return (
                        f"{self.player.first_name}! Welcome! How are you doing? You want some coffee?"
                    )
            else:  # noqa: PLR5501 - High soc
                if sym < 20:
                    return (
                        f"If it's not {self.player.get_title()} Pilot {self.player.first_name} {self.player.surname}!"
                        " I have no interest in talking with you."
                    )
                elif sym < 80:
                    return (
                        f"Hey, {self.player.first_name}, how are you? Alive, I see! I'm glad."
                        f" Me... I miss {self.interlocutor.planet_of_birth}."
                    )
                else:
                    return (
                        f"{self.player.first_name}, my friend! How are you doing? Did you see the game yesterday?"
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
                        f"{self.player.first_name}, hello! Welcome! How are you doing? Something interesting to tell?"
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
                        f"Hey, {self.player.first_name}, how are you? Alive, I see! I'm glad. How is good old [space]"
                        f" treating you lately? Friend, I miss {self.interlocutor.planet_of_birth}. And you, do"
                        f" you miss home?"
                    )
                else:
                    return (
                        f"{self.player.first_name}, my friend! How are you doing? What can I do for you?"
                    )

    def talk_asteroid(self) -> str:
        return (
            "Have you visited one? Sometimes the labs ask for somebody. I mean, I get it. But... damn. Some are"
            " simply fucking far away. Others are... in the [belt]. And those are worse."
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
            self.interaction_lines.append(interaction_key)
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
                return f"You remembered! That's so nice, {self.player.first_name}! THANK YOU!"
            elif is_near_enough:
                return f"Oh, dear! {correction_text}\n\nBut thanks anyway, don't worry."
            else:
                return f"Huh? {correction_text} And this was weird."

    def talk_life(self) -> str:
        # General effect. People like to be asked about their lives. Once.
        if not any("Asked about life." in lines for lines in self.interlocutor.interactions.values()):
            self.interlocutor.adjust_sympathy(5)
            self.interaction_lines.append("Asked about life.")

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
                return "Life's ok."
            else:
                if days_to_birthday == 0:
                    return "Doing ok. My birthday today."
                return "Doing ok."
        elif soc < 80:
            if sym < 20:
                if days_to_birthday == 0:
                    return "On my birthday, for fuck's sake. Leave me alone."
                return "Oh, no, leave me alone."
            elif sym < 80:
                text = (
                    f"Me? I was born in {self.interlocutor.place_of_birth}, I am {self.interlocutor.age} years old,"
                    f" I work here as a {self.interlocutor.role.name}. People say I'm {self_description}."
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
                    f" I work here as a {self.interlocutor.role.name} from {self.interlocutor.work_hours_text()}. People say I'm {self_description}."
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
                    f" I work here as a {self.interlocutor.role.name}."
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
                    f" I work here as a {self.interlocutor.role.name}. I like it."
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
            " Just don't. Use [the portal], go to [the base], remain in [the network]"
        )
    def talk_the_base(self) -> str:
        return (
            "Have you been there lately? People say Miners do not need it like us. I miss getting out of this"
            " uniform, I tell you. My shorts and cocktail looking at the trees. That's [life]. Almost like a planet."
        )
    def talk_the_network(self) -> str:
        return (
            "Every year a bit larger. I don't know, we must have like two dozen systems by now. I mean"
            " [Those-Who-Share]. Sure, '[United Diversity]', UniDiv, has more. [The Shining Throne], no idea."
        )
    def talk_the_portal(self) -> str:
        return (
            "Crossing that thing was at the same time overwhelming and disappointing. I mean... it's just like"
            " you are simply travelling through. But one side is light years from the other side. Damn."
        )

    def talk_the_shining_throne(self) -> str:
        # Short names to make the rest more legible
        loy: float = self.interlocutor.loyalty100
        emp: float = self.interlocutor.empathy100
        soc: float = self.interlocutor.sociability100
        sym: float = self.interlocutor.sympathy100

        # Political conversation: Loyalty is relevant.
        # Empathy still somehow relevant, to judge the place.
        # Sociability always relevant, makes the reply less or more verbose.
        # Sympathy always relevant, rejection or approval of the player.

        # Simplify loy and emp. The 1.212 is to keep variance.
        likes_them: float = 50 + 1.212 * (0.8 * (50 - loy) + 0.2 * (50 - emp))

        if sym < 20:
            return "Just leave me."
        elif sym < 80:
            if soc < 20:  # Short replies first.
                if likes_them < 20:
                    return 'Disgusting people.'
                elif likes_them < 80:
                    return '<shrugs>'
                else:
                    return 'Beautiful.'
            elif soc < 80:
                if likes_them < 20:
                    return (
                        'They are mad. Some living in luxury while others are enslaved. And what do they actually'
                        ' *want* anyway?'
                    )
                elif likes_them < 80:
                    return (
                        "Well, not that I'd like to *live* there, but the soap operas are really nice. Still..."
                        " slaves. I mean literal slaves. Fuck."
                    )
                else:
                    return (
                        "They just aren't like us. For them it is all about 'honor' and 'beauty' and 'protect the"
                        " weak'. Yes, they have slaves, but I've heard they treat them quite good, actually."
                        "\n\nSo... who knows. Live and let live, yes?"
                    )
            else:  # noqa: PLR5501
                if likes_them < 20:
                    return (
                        "Oh, by the [Founders]... horrible people. Luxury built on the back of the poor slaves,"
                        " serfs, servants, henchmen, whatever. Corruption and filth. Hearts of stone, the lot of them."
                    )
                elif likes_them < 80:
                    return (
                        "Well, everyone loves a soap opera, but let's be honest, this is a horrible, horrible society."
                        " Some toil and suffer, others sit on the top and fancy themselves artists and Counts and"
                        " Dukes and whatnot. Ew."
                    )
                else:
                    return (
                        "Well, they are really completely different to us, aren't they? They look for the special"
                        " people, the 'super-humans' and all that thing about ethics and aesthetics. They have slaves,"
                        " that's pretty horrible, but I've heard they're not so many and people can free themselves..."
                        "\n\nLook, no idea, ok? <looks embarrassed> Forget I said that. Everyone their own."
                    )
        else:  # noqa: PLR5501
            if soc < 20: # Short replies first.
                if likes_them < 20:
                    return 'Fucking bastards. Not the way to go, friend.'
                elif likes_them < 80:
                    return 'Whatever. Who knows, yes? Maybe better than here.'
                else:
                    return "<Whispers> I've seen their gardens. Public gardens. Will never forget."
            elif soc < 80:
                if likes_them < 20:
                    return (
                        "I just... don't get them. How can a person own a house? Well, ok. Somehow I guess. But how can"
                        " one people own ANOTHER HUMAN BEING? That's over me. Fuck them all. With a wrench."
                    )
                elif likes_them < 80:
                    return (
                        "In confidence <whispers> I never miss a chapter. <Louder> But you know what they say. Slaves"
                        " and depravity. It may be fun to watch, and sure they can make gorgeous things. Even"
                        " cutlery for the [Founders]' sake. But at the cost of the freedom of human beings? That"
                        " makes no sense, friend."
                    )
                else:
                    return (
                        "I have heard... <whispers> things, you know. That the slaves have a lot of rights. That the"
                        " Knights have lots of duties. Things are there not how people want them to be. Even the"
                        " soap operas. Why there is so often a suffering serf or servant, an evil Baron... if they"
                        " are such bastards, why would they critisize their own so hard? I think they have something,"
                        " and we just don't get it."
                    )
            else:  # noqa: PLR5501
                if likes_them < 20:
                    return (
                        "What do you want me to tell about them, my dear? I don't even watch that stupid propaganda"
                        " they call TV shows! Horrible people. They don't give their poor a chance. You have for sure"
                        " heard about slavery. But there is much more... serfs, and servants... nobody can really"
                        " LIVE there if it's not an Aristo. Screw them."
                        "\n\nI wish we had more confidence and we would make more of our own movies and shows. We have"
                        " a lot to be grateful for. Here we have all the same 'stand'. We don't need stupid rules"
                        " of 'honor' to share with each other, it is not pity, it is justice, community."
                    )
                elif likes_them < 80:
                    return (
                        "Hard to say, yes? Sometimes you are looking at those images... the parks, the boulevards, the"
                        " houses, the clothes. And it's so GORGEOUS! But then you remember how this must be in reality,"
                        " I mean outside the aristocracy. And that... well, I mean they can also go to the parks but..."
                        " I bet they'd prefer to live here, as a community."
                        "\n\nBut dreaming is normal, yes? Who has not dreamt in some moment to be a "
                        f"{("prince" if self.interlocutor.gender_group == Person.GenderGroup.MALE else "princess")}"
                        "?"
                    )
                else:
                    return (
                        "<Whispers> They live, you know. They live, and we don't. Parks. Fountains. Music. Clothes."
                        " Dances. Poetry. And yes, even if we pretend otherwise, their 'slaves' have it better than"
                        " many of us. And they are just a bunch, the rest are better off. A follower there lives"
                        " better than a Hero here. They reward merit. We don't."
                        "\n\nBut we should not talk so much about that here, yes? Let this be between you and me."
                    )

    def talk_those_who_share(self) -> str:
        return (
            "Well, that's what we do, yes? We care about each other. Nobody tries to have a million stamps,"
            " can you imagine? Carrying sacks of stamps to feel 'rich'. 'From each by their skills, to each"
            " by their needs'."
            "\n\nAnd nobody uses *those* [PGMs] as we do <evil smile>."
        )
    def talk_united_diversity(self) -> str:
        return (
            "They still hold the Moon. And the original system. The fighters. Suits them, Militaristic"
            " bastards. And money, money, money yes? Everything about money. As if here in [space] you could"
            " eat money, drink it or breathe it."
            "\n\nBut yeah, the high tech is high. I must concede this."
        )

    def talk_unknown_tag(self) -> str:
        return ("I don't know what you mean.")

    # endregion

    # region Auxiliar methods

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
