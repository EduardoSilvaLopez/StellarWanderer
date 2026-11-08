# How to write a `talk_*` method of the settlement chat

How-to for Claude. Read it when the user asks for a new (or a reworked) method in
`galaxies/people/conversations/settlement_chat.py`. The model to follow for a political talk is `talk_political`
(with `political_tone`), used by `talk_the_shining_throne`, `talk_united_diversity` and `talk_those_who_share`.

## What the user gives, and what not to invent
- The facts are in `common/wiki/*.txt` (United Diversity, Those-Who-Share; more may come) and in the user's
  own words in the request. **Use only those facts.** No new lore, names, numbers or places. If a fact is
  missing, ask or leave it out.
- First step when a wiki text is new: check its spelling and report the errors with links (file#Lline), and
  wait for the user to fix them. Do not edit the wiki files.
- The user edits the texts after me (wording, lore). Re-read the method before touching it and keep their
  wording; shorten only what the length rule needs.
- The sympathy effects (+/- to `adjust_sympathy`) and which traits matter are the user's decisions: propose,
  do not slip them in. Ask when a real choice is open (CLAUDE.md: in doubt, ask).

## Language and voice
- **British English** (colour, neighbour, criticise, centre, programme, defence...). Applies to the texts and
  to comments. The wiki files are the user's and may differ; do not "correct" them.
- Voice: blunt, spoken, rough edges (`<shrugs>`, `<Whispers>`, `<smiles>`, "Fuck them all. With a wrench."),
  never smooth or explanatory. Low empathy = harsh; high empathy = warm or anxious; shy loners = short.
- **Length guideline** (not a hard limit): low sociability (under 20) gets one short remark; from 20 on, the more
  sociable tell more topics (see the count in `talk_united_diversity`), so the reply grows with sociability.
  Keep each topic brief.
- Marks: `[word]` makes a conversation tag for the pilot. Use only tags that exist (keys of
  `reactions_index`: asteroids, belt, founders, happy birthday, life, noobie, paladin xi, pgms, space, the
  base, the network, the portal, the shining throne, those-who-share, united diversity). A new mark needs a
  new method: only add one if the user asks. Write `[The Shining Throne]` with the capitals as in the texts.

## The traits (all 0 to 100, `self.interlocutor.<trait>100`)
- `loyalty100`: to their own entity (as for now everybody lives in Those-Who-Share: `get_title` guesses it).
  Political topics only; apolitical conversations ignore it.
- `empathy100`: relevant when the player is weak or the topic is the people, the poor, the cost of things.
  Low empathy likes force and money.
- `sociability100`: always relevant; it sets the verbosity (see the length guideline).
- `sympathy100`: always relevant; rejection or approval of the pilot. Under 20: a brush-off line. From 80:
  a friend (confidences).
- Also available: `reputation` (high = proud of the entity), `age`, `role`, `place_of_birth`, `hobby`,
  `childhood`, `gender_group`. Use them when they truly add something.
- Bands used everywhere: under 20, under 80, 80 or more.
- Open every method with the "Short names" block and a comment that says, trait by trait, whether it is
  relevant and why (copy the style of the existing methods).

## Pattern of the political talks (`talk_political`, `political_tone`)
1. `talk_political(topics, friend_topics, generic, own_entity, praise_guarded)`: `sym < 20` returns a random
   unfriendly rejection (`unfriendly_rejections(soc)`). Otherwise the topics are drawn: `friend_topics` from
   sympathy 80, `topics` below. A `PoliticalTopics` is `name -> (score, curt line per tone, text per tone)`; a
   `PoliticalTexts` is the three tones in the order -1, 0, 1. Under sociability 20 one line is picked at random from
   the topics' curt lines and `generic`. From 20 on, the number of topics is drawn (1 and 2 most frequent, 3 and 4
   growing with sociability), chosen at random weighted by score, without repeats, and their texts joined. Each talk
   method holds its own topics and calls the helper; the Shining Throne keeps its fixed brush-off line.
2. `political_tone(own_entity, praise_guarded)`: for the person's own entity, loyalty alone decides (-1 below 20,
   0 below 80, +1 from 80); empathy is not a factor there. For the other entity,
   `likes_them = 50 + 1.212 * (0.8 * (50 - loy) + 0.2 * (50 - emp))` (the 1.212 keeps the variance). `tone` is -1,
   0 or 1 from the 20 / 80 bands. **No strict neutrality (it is too positive for a normal citizen):** -1 is a
   complete rejection, even colourful; 0 is a nuanced rejection (a concession, but still no); +1 is approval. For
   the own entity, neutral reads as clear approval; for the other one, neutral is a nuanced rejection.
3. **Praising what is frowned upon** (United Diversity, from a Those-Who-Share person, i.e. `own_entity=False`)
   needs `soc >= 80`, `loy < 20` or `sym >= 80`; otherwise `tone` drops from 1 to 0.
4. Each topic is written for the three tones, plus one curt line per tone for the replies under sociability 20.
   Topics are the way to scale: add a topic to a dict rather than a band of texts. The `friend_topics` (sympathy 80
   and up) are the confidences, with `<Whispers>`. Each dict needs at least four topics, since up to four are drawn.
5. Addressing the pilot: `you = self.interlocutor.address(self.player, to_player=True)` gives the right
   form by relative reputation and sympathy ("Pilot Surname", the title, title + first name, first name).
   Use `you` only where the person plainly addresses the pilot ("Nice to meet you, X!", "Hello X"). Keep the
   fixed or ironic forms as written ("Hello, Pilot,", "If it's not Title Pilot First Surname!") and lines
   with no address ("Leave me alone.").

## Style rules of the project that matter here
- Type hints on every parameter and return; `-> str` for the talk methods. No one-line helper methods:
  inline what fits in a line. Comments say what the code cannot; docstrings brief.
- No new files, no changes to other methods unless asked.
- Wiki numbers: Those-Who-Share has 15 systems with cities and United Diversity 50. `talk_the_network` says
  "two dozen" on purpose (people exaggerate their own nation; there are systems without cities). Leave it.

## Test (headless, no window)
Run with `PYTHONPATH=.`, `PYTHONPYCACHEPREFIX=<scratchpad>/pycache`, `SDL_VIDEODRIVER=dummy`,
`SDL_AUDIODRIVER=dummy`, `PYTHONIOENCODING=utf-8`. **Import `SettlementChat` before `Person`** (a circular import
between person and political_entity otherwise fails). Call the method unbound with fakes:

```python
from types import SimpleNamespace as NS
from galaxies.people.conversations.settlement_chat import SettlementChat
from galaxies.people.person import Person
from galaxies.people.chat_log import parse_marks
# NPC: loyalty100, empathy100, sociability100, sympathy100, reputation, role (NS(name=)), name, surname,
# get_title, address (Person.address bound to it), interactions; pilot: those_who_share.reputation, ...
text = SettlementChat.talk_xxx(NS(interlocutor=npc, player=pilot))
```
Run it over a grid (loyalty 5/15/25/50/90, empathy, sociability, sympathy, reputation) and check:
every mark in `parse_marks(text)` is a known tag; the frowned-upon praise never appears without its
conditions; no crash on any combination. Paragraphs (blank lines) reach the chat as separate paragraphs.
Never save games or touch `data/Savefiles` for this.

## Handover
Say what was written, the tests run, anything that needs the user's decision, and any inconsistency found in
the source texts (report it, do not fix it). Do not offer to commit.
