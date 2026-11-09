"""One-off conversion of the savefiles made before the pilot's identity had a date of birth, traits, pronoun and
sliders (PilotIdentityDialog), when the pilot still had a gender. The game reads only the current format, so the saves
are converted here, to new files; the originals are never touched.

    python tools/migrate_saves_pilot_identity.py SOURCE_DIR TARGET_DIR

Every save gets the same values, which are the pilot's own: the date of birth 670-10-27, beauty 50, perception 30,
education 70, pronoun He, physiology 80, attracted to 10 and sexuality 80. The gender is dropped. A save that already
has the identity is copied unchanged. Each new file keeps the modification time of its source.
"""

from __future__ import annotations

import json
import os
import sys
from typing import List

PILOT_IDENTITY = {
    'date_of_birth': [670, 10, 27],
    'beauty': 50.0,
    'perception': 30.0,
    'education': 70.0,
    'pronoun': 'HE',
    'physiology': 80.0,
    'attracted_to': 10.0,
    'sexuality': 80.0,
}


def migrate_file(source: str, target: str) -> List[str]:
    """Converts the savefile `source` into the new file `target` (which must not exist). Returns what was changed, in
    words."""
    if os.path.exists(target):
        raise FileExistsError(target)
    with open(source, encoding='utf-8') as file:
        data = json.load(file)
    player: dict = data['player']
    if 'pronoun' in player:
        changed: List[str] = []
    else:
        changed = [f"dropped gender {player.pop('gender')}", 'added the pilot identity']
        converted = {'first_name': player.pop('first_name'), 'surname': player.pop('surname'), **PILOT_IDENTITY}
        data['player'] = {**converted, **player}
    with open(target, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
    status = os.stat(source)
    os.utime(target, ns=(status.st_atime_ns, status.st_mtime_ns))
    return changed


def main(source_dir: str, target_dir: str) -> None:
    os.makedirs(target_dir, exist_ok=True)
    for name in sorted(os.listdir(source_dir)):
        if not name.endswith('.json'):
            continue
        print(name)
        for message in migrate_file(os.path.join(source_dir, name), os.path.join(target_dir, name)):
            print(f"    {message}")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
