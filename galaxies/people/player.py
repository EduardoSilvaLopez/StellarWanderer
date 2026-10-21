from __future__ import annotations
import logging

from typing import List

from common import audio
from common.dialogs.messages import Message, show_message
from galaxies.asteroid import Asteroid
from galaxies.missions import Mission
from galaxies.politics import political_entity
from galaxies.politics.personal_status import PersonalStatus
from common.updating import update_queue
from spaceships.ship import Ship
from spaceships.ship_configurations import ShabbyThsMiner
import game_environment as gem

logger = logging.getLogger(__name__)


class Player:
    """The pilot: the ship they fly, the time compression they choose and their standing with the political entities.

    The ship holds where it is and how it moves (position, velocity, attitude); see Ship.
    """

    # Time compression, in ship-seconds per real second. Keypad +/- steps by 10x, never below TIME_SCALE_MIN.
    TIME_SCALE_MIN = 1
    TIME_SCALE_MAX = 1_000_000
    TIME_SCALE_STEP = 10

    def __init__(self) -> None:
        self.time_scale: int = 1  # Default time scale
        self.ship: Ship = ShabbyThsMiner(self)
        self.credits: int = 0
        self.those_who_share: PersonalStatus = PersonalStatus()
        self.missions: List[Mission] = []  # every one taken, with its status (see missions.py)
        self.is_dead: bool = False  # set by game_over; main then opens the starting dialog

    def spawn_in_environment(self, environment: gem.GameEnvironment) -> Player:
        """Spawn the player in the given environment, just using the first place we find."""
        self.ship.spawn_in_environment(environment)
        self.those_who_share = PersonalStatus()
        return self

    # region Time scale
    def increase_time_scale(self) -> Player:
        """Faster, from TIME_SCALE_MIN up to TIME_SCALE_MAX."""
        old_time_scale = self.time_scale
        self.time_scale = min(max(self.time_scale * self.TIME_SCALE_STEP, self.TIME_SCALE_MIN), self.TIME_SCALE_MAX)
        if self.time_scale != old_time_scale:
            audio.play('time_up')
        return self

    def decrease_time_scale(self) -> Player:
        """Slower, down to TIME_SCALE_MIN."""
        old_time_scale = self.time_scale
        self.time_scale = max(self.time_scale // self.TIME_SCALE_STEP, self.TIME_SCALE_MIN)
        if self.time_scale != old_time_scale:
            audio.play('time_down')
        return self
    # endregion

    def get_title(self) -> str:
        if gem.current_environment.nearest_system.political_entity == political_entity.THOSE_WHO_SHARE:
            return political_entity.THOSE_WHO_SHARE.title_for(self.those_who_share.reputation)
        logger.warning("Unknown political entity.")
        return ''

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
        elif not body.is_world:  # the star: it has no orbit, planet or moon
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
            'asteroid': asteroid_site,
            'ship': self.ship.serialize(),
            'credits': self.credits,
            'missions': [mission.serialize() for mission in self.missions],
            'political_status': {
                'Those-Who-Share': self.those_who_share.serialize()
            }
        }

    @staticmethod
    def deserialize(loaded_attributes: dict) -> Player:
        result = Player()
        update_queue.remove(result.ship)  # the default ship made above; the saved one replaces it
        result.time_scale = loaded_attributes['time_scale']
        result.credits = loaded_attributes['credits']

        result.missions = [Mission.deserialize(mission) for mission in loaded_attributes['missions']]
        for mission in result.missions:
            mission.watch_deadline()
        result.ship = Ship.deserialize(result, loaded_attributes['ship'])

        for entity_name, values in loaded_attributes['political_status'].items():
            if entity_name == political_entity.THOSE_WHO_SHARE.name:
                result.those_who_share = PersonalStatus.deserialize(values)

        return result
    # endregion


current_player: Player = None
