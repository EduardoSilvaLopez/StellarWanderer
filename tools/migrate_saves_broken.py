"""One-off addition of the broken instruments (none) to the ships of the savefiles made before malfunctions
existed. The game reads only the current format, so the saves are converted in place: back up the folder first.

    python tools/migrate_saves_broken.py SAVE_DIR

Every ship that has no broken_instruments field gets an empty list: every instrument worked. A ship that already
has the field is left unchanged. Each file keeps the modification time of its source. Only the files directly in
SAVE_DIR are converted: its subfolders are never touched.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any


def add_broken(node: Any) -> int:
    """Adds an empty broken_instruments list to each ship in `node` that lacks it. Returns how many were given it."""
    if isinstance(node, dict):
        added = 0
        if 'configuration' in node and 'heat_shield' in node and 'broken_instruments' not in node:
            node['broken_instruments'] = []
            added += 1
        for value in node.values():
            added += add_broken(value)
        return added
    if isinstance(node, list):
        return sum(add_broken(value) for value in node)
    return 0


def migrate_file(path: str) -> int:
    """Converts the savefile `path` in place. Returns the number of ships given the field (0: not touched)."""
    with open(path, encoding='utf-8') as file:
        data = json.load(file)
    added = add_broken(data)
    if added == 0:
        return 0
    status = os.stat(path)
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
    os.utime(path, ns=(status.st_atime_ns, status.st_mtime_ns))
    return added


def main(save_dir: str) -> None:
    total = 0
    for name in sorted(os.listdir(save_dir)):
        path = os.path.join(save_dir, name)
        if not name.endswith('.json') or not os.path.isfile(path):
            continue
        added = migrate_file(path)
        if added:
            print(f"{path}: {added} ship(s)")
            total += added
    print(f"{total} ship(s) given the broken_instruments field")


if __name__ == '__main__':
    main(sys.argv[1])
