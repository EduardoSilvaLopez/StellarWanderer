from __future__ import annotations
import logging

from typing import TYPE_CHECKING, List, Optional, Tuple

from common import audio
from common.dialogs.messages import Message, show_message
from galaxies.asteroid import Asteroid
from galaxies.missions import Mission
from galaxies.people.person import Person
from galaxies.people.pilot_identity import PilotIdentity
from galaxies.portals.portal_base import PortalBase
from galaxies.world import World
from galaxies.politics import political_entity
from galaxies.politics.personal_status import PersonalStatus
from common.updating import update_queue
from spaceships.ship import Ship
from spaceships.ship_configurations import ShabbyTwsMiner
import game_environment as gem

if TYPE_CHECKING:
    from galaxies.settlement import Settlement

logger = logging.getLogger(__name__)


class Player:
    """The pilot: who they are (names, date of birth, traits, pronoun, see PilotIdentity), the ship they fly, the time
    compression they choose, whether they want to see orbits, and their standing with the political entities. The
    identity is empty until the new-game dialog asks for it (PilotIdentityDialog); a saved game always has it.

    The game has two states, equally important: the pilot is in the cockpit, or inside a settlement (`inside`, see
    `enter_settlement`). Both are saved, and a load puts the pilot back where they were.

    The ship holds where it is and how it moves (position, velocity, attitude); see Ship.
    """

    # Time compression, in ship-seconds per real second. Keypad +/- steps by 10x, never below TIME_SCALE_MIN.
    TIME_SCALE_MIN = 1
    TIME_SCALE_MAX = 1_000_000
    TIME_SCALE_STEP = 10
    # From these time scales on the clock warns in red, while the ship is moving: bound to a world, or unbound in space.
    TIME_SCALE_DANGER_BOUND = 10_000
    TIME_SCALE_DANGER_UNBOUND = 100_000

    PRESENTATION_TAG = '<present yourself>'

    def __init__(self) -> None:
        self.first_name: str = ''
        self.surname: str = ''
        self.date_of_birth: Tuple[int, int, int] = (0, 0, 0)  # year, month, day
        self.beauty: float = 50.0
        self.perception: float = 50.0
        self.education: float = 50.0
        self.pronoun: Optional[Person.Pronoun] = None
        self.physiology: float = 50.0
        self.attracted_to: float = 50.0
        self.sexuality: float = 50.0
        self.time_scale: int = 1  # Default time scale
        # The time scale before the caps lowered it last, and the one they lowered it to (see limit_time_scale)
        self._limited_from: int = 1
        self._limited_to: int = 1
        self.ship: Ship = ShabbyTwsMiner(self)
        self.credits: int = 0
        self.citizenship: Optional[political_entity.PoliticalEntity] = political_entity.THOSE_WHO_SHARE
        # The pilot's standing with each political entity, by entity (saved by the entity's name).
        self.political_status: dict[political_entity.PoliticalEntity, PersonalStatus] = {
            political_entity.THOSE_WHO_SHARE: PersonalStatus(political_entity.THOSE_WHO_SHARE)
        }
        self.missions: List[Mission] = []  # every one taken, with its status (see missions.py)
        self.is_gone: bool = False  # set by game_over; main then opens the starting dialog
        self.inside: Optional[Settlement] = None  # the settlement the pilot is in, if any (not the cockpit)
        # The conversation tags of the chat (see settlement_chat.py): one set for the pilot, not per person, saved sorted.
        self.conversation_tags: set[str] = {Player.PRESENTATION_TAG}
        # The pinned ones, in the order they were pinned: they come first in the chat, and each is one of the tags.
        self.pinned_tags: list[str] = []
        self.flags: set[str] = set()
        self.show_orbits: bool = True  # the pilot's choice (O): the orbit of the targeted body is drawn

    def apply_identity(self, identity: PilotIdentity) -> Player:
        """Takes the identity the new-game dialog gave."""
        self.first_name = identity.first_name
        self.surname = identity.surname
        self.date_of_birth = identity.date_of_birth
        self.beauty = identity.beauty
        self.perception = identity.perception
        self.education = identity.education
        self.pronoun = identity.pronoun
        self.physiology = identity.physiology
        self.attracted_to = identity.attracted_to
        self.sexuality = identity.sexuality
        return self

    def spawn_in_environment(self, environment: gem.GameEnvironment) -> Player:
        """Spawn the player in the given environment, just using the first place we find."""
        self.ship.spawn_in_environment(environment)
        self.political_status = {political_entity.THOSE_WHO_SHARE: PersonalStatus(political_entity.THOSE_WHO_SHARE)}
        return self

    # region Time scale
    def is_time_scale_dangerous(self) -> bool:
        """Whether the time compression is clearly dangerous at the ship's state (bound or unbound). Only while the ship
        has a speed (the same speed the console shows): a ship standing still, hovering or not, is never dangerous.
        Compensating a pull unbound burns energy as hovering does, so it has the bound limit."""
        burning = self.ship.is_bound or self.ship.navigation.compensates_pull()
        limit = self.TIME_SCALE_DANGER_BOUND if burning else self.TIME_SCALE_DANGER_UNBOUND
        return self.time_scale >= limit and self.ship.velocity.as_vector().length() > 0.0

    def wished_time_scale(self) -> int:
        """The time scale the pilot has asked for: the current one, except during a trip (TRAVEL), when it is the one
        the caps lowered it from, so that it comes back by itself when they lift: the pilot sets it once, and does not
        have to compress and decompress time as the trip goes on."""
        travelling = self.ship.navigation.travel is not None
        return self._limited_from if travelling and self.time_scale == self._limited_to else self.time_scale

    def reset_time_scale(self) -> None:
        """Back to x1, with nothing left to restore."""
        self.time_scale = self._limited_from = self._limited_to = self.TIME_SCALE_MIN

    def limit_time_scale(self, frame_seconds: float, limit: float) -> None:
        """Lowers the time scale, in its steps, until a frame of `frame_seconds` real seconds covers no more than
        `limit` game seconds (see Navigation.portal_base_time_limit; main passes no limit inside the station). The clock
        shows the lower one."""
        self.time_scale = self.wished_time_scale()
        wished = self.time_scale
        while self.time_scale > self.TIME_SCALE_MIN and frame_seconds * self.time_scale > limit:
            self.time_scale = max(self.time_scale // self.TIME_SCALE_STEP, self.TIME_SCALE_MIN)
        self._limited_from, self._limited_to = wished, self.time_scale

    def increase_time_scale(self) -> Player:
        """Faster, from TIME_SCALE_MIN up to TIME_SCALE_MAX."""
        old_time_scale = self.time_scale
        wished = self.wished_time_scale()
        self.time_scale = min(max(wished * self.TIME_SCALE_STEP, self.TIME_SCALE_MIN), self.TIME_SCALE_MAX)
        if self.time_scale != old_time_scale:
            audio.play('time_up')
        return self

    def present_yourself_first_time(self) -> str:
        return f"Hello. I am {self.first_name} {self.surname}, Pilot. Who are you?"

    def present_yourself_further_times(self, interlocutor: Person) -> str:
        return f"Hello, {interlocutor.address(self, to_player=False)}. How are you doing?"

    def decrease_time_scale(self) -> Player:
        """Slower, down to TIME_SCALE_MIN."""
        old_time_scale = self.time_scale
        self.time_scale = max(self.wished_time_scale() // self.TIME_SCALE_STEP, self.TIME_SCALE_MIN)
        if self.time_scale != old_time_scale:
            audio.play('time_down')
        return self
    # endregion

    # region Inside an outpost
    def enter_settlement(self, settlement: Settlement) -> Player:
        """The pilot goes into `settlement`: the game is in its other state, and the ship is docked (Ship.dock)."""
        self.ship.dock()
        self.inside = settlement
        return self

    def leave_settlement(self) -> Player:
        """The pilot goes back to the cockpit, and the ship is undocked and put where the settlement says (see
        Settlement.place_after_leaving)."""
        self.ship.undock()
        if self.inside is not None:
            self.inside.place_after_leaving(self.ship)
        self.inside = None
        return self

    def resume_inside(self, settlement: Settlement) -> Player:
        """A load puts the pilot back inside `settlement`. The saved ship was docked, and its time up to the save has
        been lived through as such, so it is only marked docked again, without settling anything."""
        self.inside = settlement
        self.ship.is_docked = True
        return self
    # endregion

    def get_title(self) -> str:
        if gem.current_environment.nearest_system.political_entity == political_entity.THOSE_WHO_SHARE:
            return political_entity.THOSE_WHO_SHARE.title_for(self.reputation)
        logger.warning("Unknown political entity.")
        return ''

    @property
    def reputation(self) -> float:
        """The pilot's reputation where they are (see `_standing`). 0, with a warning, when they have no standing."""
        standing = self._standing()
        if standing is None:
            logger.warning("The pilot has no standing for this place (see Player._standing).")
            return 0.0
        return standing.reputation

    @reputation.setter
    def reputation(self, value: float) -> None:
        """Sets the standing's reputation (see `_standing`). Nothing happens, with a warning, when there is none."""
        standing = self._standing()
        if standing is None:
            logger.warning("The pilot has no standing for this place (see Player._standing).")
            return
        standing.reputation = value

    def _standing(self) -> Optional[PersonalStatus]:
        """The pilot's standing with the entity of the system they are in. A system without an entity gives the entity
        of the pilot's citizenship instead. None when there is no such entity, or the pilot has no standing with it."""
        entity = gem.current_environment.nearest_system.political_entity
        if entity is None:
            entity = self.citizenship
        return self.political_status.get(entity) if entity is not None else None

    def adjust_reputation(self, change: float) -> None:
        '''Adds `change` to the reputation: negative for a cost paid, positive for a refund.'''
        old_rep: float = self.reputation
        self.reputation = old_rep + change
        standing = self._standing()
        if standing is None:
            return
        else:
            logger.info(
                f"Reputation in {standing.entity.name} changed by {change}:"
                f" {old_rep} + {change} = {self.reputation}."
                )

    def adjust_reputation_by_supply(self, key: str, quantity: float) -> None:
        """Gives (positive `quantity`) or takes a supply with the standing of this place (see `_standing`). Nothing
        happens, with a warning, when there is no standing."""
        standing = self._standing()
        if standing is None:
            logger.warning("The pilot has no standing for this place (see Player._standing).")
            return
        standing.adjust_reputation_by_supply(key, quantity)

    def game_over(self, reason: str) -> None:
        """Game over: shows `reason` once. The game then ends when the message is closed (see main)."""
        if self.is_gone:
            return
        self.is_gone = True

        statistics: str = (
            f"STATISTICS:\n\n"
            f" * Denomination: {self.get_title()}\n\n"
            f" * Federal Credits: {self.credits} Ȼ\n\n"
            f" * Imperial Rank: Foreigner"
        )
        show_message(Message(
            title='GAME OVER',
            text=f"\n{reason}\n\n{statistics}",
            buttons=["Damn!"],
            open_sound='game_over'
        ))

    # region Persistence
    def serialize(self) -> dict:
        # the body the ship is around, even when it is outside every fixed zone
        body = gem.current_environment.last_fixed_body
        system = body.stellar_system
        asteroid_site = None
        # a mission's asteroid: saved by its own identity, see StellarSystem.asteroid_from_site
        if isinstance(body, Asteroid):
            asteroid_site = body.site()
            orbit_number = planet_index = moon_index = None
        elif not isinstance(body, World):  # the star or the portal base: no orbit, planet or moon
            orbit_number = planet_index = moon_index = None
        elif body.parent_planet:
            orbit_number = body.parent_orbit.number
            planet_index = body.parent_planet.parent_orbit.planets.index(body.parent_planet)
            moon_index = body.index
        else:
            orbit_number = body.parent_orbit.number
            planet_index = body.parent_orbit.planets.index(body)
            moon_index = None

        return {
            'first_name': self.first_name,
            'surname': self.surname,
            'date_of_birth': list(self.date_of_birth),
            'beauty': self.beauty,
            'perception': self.perception,
            'education': self.education,
            'pronoun': self.pronoun.name if self.pronoun is not None else None,
            'physiology': self.physiology,
            'attracted_to': self.attracted_to,
            'sexuality': self.sexuality,
            'time_scale': self.time_scale,
            'stellar_system': {'x': system.x, 'y': system.y, 'z': system.z},
            'orbit': orbit_number,
            'planet': planet_index,
            'moon': moon_index,
            'asteroid': asteroid_site,
            'is_last_fixed_portal_base': isinstance(body, PortalBase),
            'ship': self.ship.serialize(),
            'credits': self.credits,
            'inside_settlement': self.inside.inside_key() if self.inside is not None else None,
            'missions': [mission.serialize() for mission in self.missions],
            'conversation_tags': sorted(self.conversation_tags),
            'pinned_tags': list(self.pinned_tags),
            'citizenship': self.citizenship.name if self.citizenship is not None else None,
            'flags': sorted(self.flags),
            'show_orbits': self.show_orbits,
            'political_status': {entity.name: status.serialize() for entity, status in self.political_status.items()}
        }

    @staticmethod
    def deserialize(loaded_attributes: dict) -> Player:
        result = Player()
        update_queue.remove(result.ship)  # the default ship made above; the saved one replaces it
        result.first_name = loaded_attributes['first_name']
        result.surname = loaded_attributes['surname']
        year, month, day = loaded_attributes['date_of_birth']
        result.date_of_birth = (year, month, day)
        result.beauty = loaded_attributes['beauty']
        result.perception = loaded_attributes['perception']
        result.education = loaded_attributes['education']
        result.pronoun = Person.Pronoun[loaded_attributes['pronoun']] if loaded_attributes['pronoun'] else None
        result.physiology = loaded_attributes['physiology']
        result.attracted_to = loaded_attributes['attracted_to']
        result.sexuality = loaded_attributes['sexuality']
        result.time_scale = loaded_attributes['time_scale']
        result.credits = loaded_attributes['credits']

        result.missions = [Mission.deserialize(mission) for mission in loaded_attributes['missions']]
        for mission in result.missions:
            mission.watch_deadline()
        result.ship = Ship.deserialize(result, loaded_attributes['ship'])
        result.conversation_tags = set(loaded_attributes['conversation_tags'])
        result.pinned_tags = list(loaded_attributes['pinned_tags'])
        result.flags = set(loaded_attributes['flags'])
        result.show_orbits = loaded_attributes['show_orbits']

        # None when the pilot has no citizenship, or when no entity has the saved name (warned: it cannot happen yet).
        citizenship_name: Optional[str] = loaded_attributes['citizenship']
        result.citizenship = political_entity.ENTITIES.get(citizenship_name) if citizenship_name is not None else None
        if citizenship_name is not None and result.citizenship is None:
            logger.warning(f"Unknown citizenship in the save: {citizenship_name}.")

        result.political_status = {}
        for entity_name, values in loaded_attributes['political_status'].items():
            entity = political_entity.ENTITIES.get(entity_name)
            if entity is None:
                logger.warning(f"Unknown political entity in the save: {entity_name}.")
                continue
            result.political_status[entity] = PersonalStatus.deserialize(values, entity_name)

        return result
    # endregion


# Set when a game starts or loads (main, Savefile.load_from_file); None before that.
current_player: Player = None  # type: ignore[assignment]
