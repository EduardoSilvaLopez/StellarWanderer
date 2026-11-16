"""Moves the saves of data/Savefiles into one folder per galactic seed (data/Savefiles/<seed>/), as the game now keeps
them. A copy of the moved files is made first, in data/Savefiles/Backup <date>, which the game does not look at.

Only the .json files directly in data/Savefiles are moved; any folder there (the player's archives) is left alone.
Run it from the project folder: python tools/migrate_saves_per_seed.py"""

import json
import os
import shutil
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.paths import SAVEFILES_DIR, data_path  # noqa: E402


def migrate() -> None:
    folder = data_path(SAVEFILES_DIR)
    names = [n for n in os.listdir(folder) if n.endswith('.json') and os.path.isfile(os.path.join(folder, n))]
    plan: list[tuple[str, str]] = []
    for name in names:
        with open(os.path.join(folder, name), encoding='utf-8') as file:
            seed = int(json.load(file)['environment']['galactic_seed'])
        target = os.path.join(folder, str(seed), name)
        if os.path.exists(target):
            raise SystemExit(f"{target} exists: nothing was moved.")
        plan.append((name, target))
    backup = os.path.join(folder, f"Backup {date.today():%Y%m%d} per seed")
    os.makedirs(backup, exist_ok=False)
    for name, _ in plan:
        shutil.copy2(os.path.join(folder, name), os.path.join(backup, name))
    for name, target in plan:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        os.replace(os.path.join(folder, name), target)
    print(f"{len(plan)} saves moved; the copy is in {backup}")


if __name__ == '__main__':
    migrate()
