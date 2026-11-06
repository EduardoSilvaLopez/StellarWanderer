"""One-off conversion of the savefiles made before a mission recorded when it finished (`Mission.finished_at`). The game
reads only the current format, so the saves are converted here, to new files; the originals are never touched.

    python tools/migrate_saves_finished_at.py SOURCE_DIR TARGET_DIR

A mission that is over (done or failed) gets its deadline as `finished_at`, an approximation: the real moment was not
kept. An open mission gets None. A save that already has the field is copied unchanged.
"""

from __future__ import annotations

import json
import os
import sys
from typing import List


def migrate_file(source: str, target: str) -> List[str]:
    """Converts the savefile `source` into the new file `target` (which must not exist). Returns what was added, in
    words."""
    if os.path.exists(target):
        raise FileExistsError(target)
    with open(source, encoding='utf-8') as file:
        data = json.load(file)
    added: List[str] = []
    for mission in data['player']['missions']:
        if 'finished_at' in mission:
            continue
        mission['finished_at'] = None if mission['status'] == 'open' else mission['deadline']
        added.append(f"finished_at of {mission['kind']} ({mission['status']}): {mission['finished_at']}")
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
