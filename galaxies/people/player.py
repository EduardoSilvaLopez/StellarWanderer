from __future__ import annotations
import logging

from common.dialogs.messages import Message, show_message
from galaxies.politics import political_entity
from galaxies.politics.personal_status import PersonalStatus
from spaceships.ship import Ship
import game_environment as gem

logger = logging.getLogger(__name__)


class Player:
    """The pilot: the ship they fly, the time compression they choose and their standing with the political entities.

    The ship holds where it is and how it moves (position, velocity, attitude); see Ship.
    """

    # Time compression, in ship-seconds per real second. Keypad +/- steps by 10x.
    TIME_SCALE_MIN = 1
    TIME_SCALE_MAX = 1_000_000
    TIME_SCALE_STEP = 10

    def __init__(self) -> None:
        self.time_scale: int = 1  # Default time scale
        self.ship: Ship = Ship(self)
        self.credits: int = 0
        self.those_who_share: PersonalStatus = PersonalStatus()
        self.is_dead: bool = False  # set by game_over; main then opens the starting dialog

    def spawn_in_environment(self, environment: gem.GameEnvironment) -> Player:
        """Spawn the player in the given environment, just using the first place we find."""
        self.ship.spawn_in_environment(environment)
        self.those_who_share = PersonalStatus()
        return self

    def serialize(self) -> dict:
        body = gem.current_environment.nearest_body
        system = body.stellar_system
        if not body.is_world:  # the star: it has no orbit, planet or moon
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
            'time_scale': self.time_scale,
            'stellar_system': {'x': system.x, 'y': system.y, 'z': system.z},
            'orbit': orbit_number,
            'planet': planet_index,
            'moon': moon_index,
            'ship': self.ship.serialize(),
            'credits': self.credits,
            'political_status': {
                'Those-Who-Share': self.those_who_share.serialize()
            }
        }

    @staticmethod
    def deserialize(loaded_attributes: dict) -> Player:
        result = Player()
        result.time_scale = loaded_attributes['time_scale']
        if 'credits' in loaded_attributes:
            result.credits = loaded_attributes['credits']

        result.ship = Ship.load(result, loaded_attributes['ship'])

        for entity_name, values in loaded_attributes['political_status'].items():
            if entity_name == political_entity.THOSE_WHO_SHARE.name:
                result.those_who_share = PersonalStatus.deserialize(values)

        return result

    def increase_time_scale(self) -> Player:
        self.time_scale = min(self.time_scale * self.TIME_SCALE_STEP, self.TIME_SCALE_MAX)
        return self

    def decrease_time_scale(self) -> Player:
        self.time_scale = max(self.time_scale // self.TIME_SCALE_STEP, self.TIME_SCALE_MIN)
        return self

    def get_title(self) -> str:
        if gem.current_environment.nearest_system.political_entity == political_entity.THOSE_WHO_SHARE:
            return political_entity.THOSE_WHO_SHARE.title_for(self.those_who_share.reputation)
        else:
            logger.warning("Unknown political entity.")
            return str()

    def game_over(self, reason: str) -> None:
        """The pilot dies: shows `reason` once. The game then ends when the message is closed (see main)."""
        if self.is_dead:
            return
        self.is_dead = True

        statistics: str = (
            f"STATISTICS:\n\n"
            f" * Denomination: {self.get_title()}\n\n"
            f" * Federal Credits: {self.credits} Ȼ\n\n"
            f" * Imperial Rank: Foreigner"
        )
        show_message(
            Message(
                title='GAME OVER',
                text=f"\n{reason}\n\n{statistics}",
                buttons=["Damn!"]
                )
            , None  # pending
            )


current_player: Player = None
