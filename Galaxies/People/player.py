from __future__ import annotations
import logging

from Galaxies.Politics import political_entity
from Galaxies.Politics.personal_status import PersonalStatus
from Spaceships.ship import Ship
from Updating import update_queue
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
        self.those_who_share: PersonalStatus = PersonalStatus()

    def spawn_in_environment(self, environment: gem.GameEnvironment) -> Player:
        """Spawn the player in the given environment, just using the first place we find."""
        self.ship.spawn_in_environment(environment)
        self.those_who_share = PersonalStatus()
        return self

    def serialize(self) -> dict:
        world = gem.current_environment.nearest_world
        if world.parent_planet:
            planet_index = world.parent_planet.parent_orbit.planets.index(world.parent_planet)
            moon_index = world.index
        else:
            planet_index = world.parent_orbit.planets.index(world)
            moon_index = None

        system = world.parent_orbit.parent_stellar_system
        return {
            'time_scale': self.time_scale,
            'stellar_system': {'x': system.x, 'y': system.y, 'z': system.z},
            'orbit': world.parent_orbit.number,
            'planet': planet_index,
            'moon': moon_index,
            'ship': self.ship.serialize(),
            'political_status': {
                'Those-Who-Share': self.those_who_share.serialize()
            }
        }

    @staticmethod
    def deserialize(loaded_attributes: dict) -> Player:
        result = Player()
        result.time_scale = loaded_attributes['time_scale']
        update_queue.remove(result.ship)
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

current_player: Player = None
