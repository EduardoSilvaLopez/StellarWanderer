import json
import os
import glob

import logging
from datetime import datetime

import game_environment as gem
from galaxies.people import knowledge
import galaxies.people.player as pem
from common.paths import data_path, SAVEFILES_DIR

logger = logging.getLogger(__name__)

# A save's file name is "<seed> <game date> <name typed>" plus ".json": the name typed is optional.
SAVE_NAME_FORBIDDEN = '\\/:*?"<>|'
SAVE_NAME_MAX_LENGTH = 60


class Savefile:

    # region Names
    @staticmethod
    def clean_name(text: str) -> str:
        '''A name made safe for a file name: printable, no path or reserved characters, no ".json" ending, at most
        SAVE_NAME_MAX_LENGTH characters. The spaces at its end are kept, the default name ends with one.'''
        cleaned = ''.join(c for c in text if c.isprintable() and c not in SAVE_NAME_FORBIDDEN).lstrip()
        if cleaned.lower().endswith('.json'):
            cleaned = cleaned[:-len('.json')]
        return cleaned[:SAVE_NAME_MAX_LENGTH]

    @staticmethod
    def default_name() -> str:
        '''The start of every save's name, which is the whole name when nothing is typed after it: the seed, the game's
        date in ISO format, and a space.'''
        env = gem.current_environment
        return f"{int(env.galaxy.seed)} {env.date_time.strftime('%Y-%m-%d')} "

    @staticmethod
    def exists(name: str) -> bool:
        return os.path.exists(data_path(SAVEFILES_DIR, name + '.json'))
    # endregion

    # region Saving
    @staticmethod
    def save() -> bool:
        '''F5: saves the game under the default name, silently replacing a save of that name (another save on the same
        game day).'''
        Savefile.save_as(Savefile.default_name())

    @staticmethod
    def save_as(name: str) -> None:
        '''Saves the current state of the game to `name` (a clean name, see clean_name), from the GameEnvironment and
        Player singletons. Replaces a save of that name.'''
        env = gem.current_environment
        player = pem.current_player

        data = {
            'environment': {
                'galactic_seed': env.galaxy.seed,
                'date_time': env.date_time.strftime('%Y-%m-%d %H:%M:%S.%f'),
                'galaxy_alterations': env.galaxy.get_alterations(),
                'persons': dict(env.persons),
                'target_index': env.target_index(player.ship.position.as_vector())
            }
            , 'player': player.serialize()
            , 'knowledge': knowledge.current_knowledge.serialize()
        }
        os.makedirs(data_path(SAVEFILES_DIR), exist_ok=True)
        file_path = data_path(SAVEFILES_DIR, name + '.json')
        logger.info("New savefile's name: " + file_path)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    # endregion

    # region Loading
    @staticmethod
    def load_last() -> None:
        '''Loads the most recently written savefile directly into GameEnvironment and Player singletons.

        WARNING: if you retrieved them before calling this method, remember to re-assign those variables.'''
        savefiles = glob.glob(data_path(SAVEFILES_DIR, '*.json'))
        if not savefiles:
            raise FileNotFoundError("No savefiles found.")
        Savefile.load_from_file(max(savefiles, key=os.path.getmtime))

    @staticmethod
    def load_from_file(filepath: str) -> None:
        '''Loads a specific savefile into GameEnvironment and Player singletons.

        WARNING: if you retrieved them before calling this method, remember to re-assign those variables.'''
        from common.updating import update_queue
        update_queue.clear()

        logger.info(f"Loading savefile: {filepath}")
        with open(filepath, encoding='utf-8') as f:
            load_object = json.load(f)

        # Before the environment: the systems it generates add to the knowledge.
        knowledge.current_knowledge = knowledge.Knowledge.deserialize(load_object['knowledge'])
        game_date_time = datetime.strptime(load_object['environment']['date_time'], '%Y-%m-%d %H:%M:%S.%f')
        # JSON keys are text; the people are looked up by their int seed.
        people_alterations = {int(seed): values for seed, values in load_object['environment']['persons'].items()}
        gem.current_environment = gem.GameEnvironment(
            load_object['environment']['galactic_seed'],
            game_date_time,
            load_object['environment']['galaxy_alterations'],
            people_alterations
            )
        logger.debug("Loaded seed: " + str(gem.current_environment.galaxy.seed))

        player_data: dict = load_object['player']
        system_data: dict = player_data['stellar_system']
        galaxy = gem.current_environment.galaxy
        gem.current_environment.nearest_system = galaxy.add_stellar_system(
            galaxy.fixed_star_at((system_data['x'], system_data['y'], system_data['z']))
            )
        if player_data['asteroid'] is not None:  # a mission's asteroid was the last fixed body
            body = gem.current_environment.nearest_system.asteroid_from_site(player_data['asteroid'])
        elif player_data['is_last_fixed_portal_base']:
            body = gem.current_environment.nearest_system.portal_base
        elif player_data['orbit'] is None:  # the star was the last fixed body
            body = gem.current_environment.nearest_system.star
        else:
            current_orbit = gem.current_environment.nearest_system.get_orbit(float(player_data['orbit']))
            planet_idx: int = player_data['planet']
            moon_idx: int = player_data['moon']
            if moon_idx is None:
                body = current_orbit.planets[planet_idx]
            else:
                body = current_orbit.planets[planet_idx].moons[moon_idx]
        # A bound ship is fixed to its world; an unbound one is fixed only if it is in a fixed zone, which the next
        # frame works out (refresh_fixed_body). The target is set once the ship and the missions are loaded (below).
        gem.current_environment.targeted_body = gem.current_environment.last_fixed_body = body
        gem.current_environment.fixed_body = body if player_data['ship']['is_bound'] else None

        position_data: dict = player_data['ship']['position']
        world = gem.current_environment.fixed_world  # None for the star: no surroundings to load
        if world is not None:
            world.update_surroundings(position_data['y'], position_data['x'], position_data['z'], game_date_time)

        pem.current_player = pem.Player.deserialize(load_object['player'])
        # The pilot saved inside a settlement: they are back inside it, and a repair going on there goes on (main opens
        # its screen). The portal base is the one of the system; an outpost is found by its key.
        if player_data['inside_settlement'] == 'portal_base':
            settlement = gem.current_environment.nearest_system.portal_base
        elif player_data['inside_settlement'] is not None:
            settlement = galaxy.outpost_of(player_data['inside_settlement'])
        else:
            settlement = None
        if settlement is not None and settlement.dockmaster is None:  # nobody on duty yet: staff and queue (prepare)
            settlement.prepare()
        if settlement is not None:
            pem.current_player.resume_inside(settlement)
        # The target is the body at the saved place in the Tab order, which depends on the ship and its missions, so
        # it is read only now. While fixed, the target is the fixed body (already set above).
        target_index: int = load_object['environment']['target_index']
        if gem.current_environment.fixed_body is None and target_index >= 0:
            bodies = gem.current_environment.bodies_by_distance(pem.current_player.ship.position.as_vector())
            gem.current_environment.targeted_body = bodies[target_index]
    # endregion
