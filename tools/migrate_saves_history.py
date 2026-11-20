"""Migrates the saves of one seed to the history's new initial system, for the change in which the history picks the initial
star (universe/society/politics/expansion_history.py). The old saves placed the pilot in the star at 26010 10 10, which
the new galaxy no longer has at that place.

What is kept: the pilot (identity, credits, flags, conversation tags, political status, time scale), the game date, and
the ship's last update. What is taken from a fresh game of the seed: the place (the initial star, its planet and moon),
the ship, the knowledge. What is cleared: the missions, the settlement the pilot was in, the people's alterations, and the
alterations of the galaxy (the outposts and mines of the old system), which have no place in the new galaxy.

The sources are read from data/Savefiles_before_history_migration/<seed>, the backup of the saves, and the migrated saves
are written to data/Savefiles/<seed>, so running it again gives the same result. Usage:
python tools/migrate_saves_history.py [seed, default 4]"""

from __future__ import annotations

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import game_environment as gem  # noqa: E402  (imported first, as the game does)
from common.game_logging import configure_logging  # noqa: E402
from common.paths import data_path  # noqa: E402
from universe.society.people import knowledge  # noqa: E402
from universe.society.people import player as player_module  # noqa: E402
from universe.structure.constants import EPOCH  # noqa: E402

# The player's keys that place the pilot in the world: taken from a fresh game.
PLACE_KEYS = ('stellar_system', 'orbit', 'planet', 'moon', 'asteroid', 'is_last_fixed_portal_base', 'inside_settlement',
              'missions', 'ship')


def fresh_game(seed: int) -> dict:
    """The place, the ship and the knowledge of a new game of the seed, as the save format holds them."""
    knowledge.current_knowledge = knowledge.Knowledge()
    gem.current_environment = gem.GameEnvironment(seed, EPOCH, None, None)
    gem.current_environment.generate_default()
    player_module.current_player = player_module.Player()
    player_module.current_player.spawn_in_environment(gem.current_environment)  # as a new game does: bound
    return {'player': player_module.current_player.serialize(),
            'knowledge': knowledge.current_knowledge.serialize()}


def migrate(old: dict, fresh: dict) -> dict:
    """The save of the new place: the old pilot, the fresh place, the old date."""
    player = dict(old['player'])
    for key in PLACE_KEYS:
        player[key] = fresh['player'][key]
    player['ship']['last_update_at'] = old['player']['ship']['last_update_at']
    return {
        'environment': {
            'galactic_seed': old['environment']['galactic_seed'],
            'date_time': old['environment']['date_time'],
            'galaxy_alterations': {},
            'persons': {},
            'target_index': -1,
        },
        'player': player,
        'knowledge': fresh['knowledge'],
    }


def main() -> None:
    configure_logging()
    seed = sys.argv[1] if len(sys.argv) > 1 else '4'
    source = os.path.join(ROOT, 'data', 'Savefiles_before_history_migration', seed)
    target = data_path('Savefiles', seed)
    fresh = fresh_game(int(seed))
    os.makedirs(target, exist_ok=True)
    paths = sorted(glob.glob(os.path.join(source, '*.json')))
    for path in paths:
        with open(path, encoding='utf-8') as file:
            old = json.load(file)
        new = migrate(old, fresh)
        with open(os.path.join(target, os.path.basename(path)), 'w', encoding='utf-8') as file:
            json.dump(new, file, ensure_ascii=False, indent=4)
    print(f"Migrated {len(paths)} saves of seed {seed} from {source} to {target}.")


if __name__ == '__main__':
    main()
