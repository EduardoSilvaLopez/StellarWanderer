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
            Player.PRESENTATION_TAG: self.talk_present_yourself,
            'asteroid': self.talk_asteroid,
            'belt': self.talk_belt,
            'founders': self.talk_founders,
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
                    return f"Hello, Pilot, I am {self_present}. How are you? Share a drink?"
                else:
                    return (
                        f"Nice to meet you, {self.player.first_name}! How are you doing? How is [space] being to you?"
                        f"\n\nMe, I prefer to remain between the outpost and [the base]. Less risky, you know?"
                        f" And people are nice here."
                    )
            else:  # noqa: PLR5501
                if sym < 20:
                    return (
                        "Oh, no, [noobie], don't approach me, ok? I don't want troubles and you have done enough,"
                        " just leave me alone. You should think about your life."
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
                    )
        else:  # noqa: PLR5501
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
                        f"\n\nDo you need a coffee?"
                    )
                else:
                    return (
                        f"Nice to meet you, {self.player.first_name}! Heard good things about you."
                        f"\n\nHow is [space] treating you? [Paladin Xi] is not a bad guy, but he is ruthless. I see"
                        f" the ships you start with. Ugh."
                    )
            else:  # noqa: PLR5501
                if sym < 20:
                    return (
                        "DON'T YOU DARE! Oh, don't you dare to approach me, no, no, I know the likes of you!"
                        " Just leave me alone, life here is hard enough, just go away and let me have my meal"
                        " in peace. By the [Founders] I don't need this right now!"
                    )
                elif sym < 80:
                    return (
                        "So here we have you, [Paladin Xi]'s last discovery! He wants everybody on [space].\n\n"
                        " I get, we need the [PGMs], and more valuable [asteroids], but the belts are dangerous."
                        " People have been killed. No beacon signal can save you if you are too far away,"
                        " drifting between planets. Be careful, [noobie], ok?"
                    )
                else:
                    return (
                        f"Nice to meet you, {self.player.first_name}! How are you doing?"
                        "\n\nI have heard about you. Good things! Do you want a coffee? Or maybe something... stronger?"
                        "\n\nHow is [space] treating you? Making our [Paladin Xi] proud? Tell me!"
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
            " uniform, I tell you. My shorts and cocktail looking at the trees. That's life. Almost like a planet."
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

        # Must simplify this, so a formula which combines two without changing the sigma too much.
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
