"""One-off conversion of the savefiles made before the pilot had a citizenship and flags (see Player.serialize). The
game reads only the current format, so the saves are converted here, to new files; the originals are never touched.

    python tools/migrate_saves_citizenship_flags.py SOURCE_DIR TARGET_DIR

Before this change the pilot was always a citizen of Those-Who-Share (the default of Player) and had no flags, so the
converted save gets exactly that: citizenship 'Those-Who-Share' and no flags. A save that already has them is copied
unchanged.
"""

from __future__ import annotations

import json
import os
import sys
from typing import List

DEFAULT_CITIZENSHIP = 'Those-Who-Share'


def migrate_file(source: str, target: str) -> List[str]:
    """Converts the savefile `source` into the new file `target` (which must not exist). Returns what was added, in
    words."""
    if os.path.exists(target):
        raise FileExistsError(target)
    with open(source, encoding='utf-8') as file:
        data = json.load(file)
    player: dict = data['player']
    added: List[str] = []
    if 'citizenship' not in player:
        player['citizenship'] = DEFAULT_CITIZENSHIP
        added.append(f"citizenship: {DEFAULT_CITIZENSHIP}")
    if 'flags' not in player:
        player['flags'] = []
        added.append("flags: none")
    with open(target, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
    os.utime(target, (os.path.getatime(source), os.path.getmtime(source)))
    return added


def main(source_dir: str, target_dir: str) -> None:
    os.makedirs(target_dir, exist_ok=True)
    for name in sorted(os.listdir(source_dir)):
        if not name.endswith('.json'):
            continue
        print(name)
        for message in migrate_file(os.path.join(source_dir, name), os.path.join(target_dir, name)):
            print(f"    added {message}")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
