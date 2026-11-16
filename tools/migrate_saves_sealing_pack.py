"""One-off addition of the sealing pack stock to the cargo holds of the savefiles made before sealing packs existed. The
game reads only the current format, so the saves are converted in place: back up the folder first.

    python tools/migrate_saves_sealing_pack.py SAVE_DIR

Every cargo hold that has no sealing pack gets none (0): the pilot had none before the cargo existed. A hold that already
has the stock is left unchanged. Each file keeps the modification time of its source. Only the files directly in
SAVE_DIR are converted: its subfolders are never touched.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any


def add_sealing_packs(node: Any) -> int:
    """Adds the sealing pack stock to each cargo hold in `node` that lacks it. Returns how many holds were given it."""
    if isinstance(node, dict):
        added = 0
        if 'configuration' in node and 'food' in node and 'sealing_pack' not in node:
            node['sealing_pack'] = 0
            added += 1
        for value in node.values():
            added += add_sealing_packs(value)
        return added
    if isinstance(node, list):
        return sum(add_sealing_packs(value) for value in node)
    return 0


def migrate_file(path: str) -> int:
    """Converts the savefile `path` in place. Returns the number of holds given the stock (0: the file is not
    touched)."""
    with open(path, encoding='utf-8') as file:
        data = json.load(file)
    added = add_sealing_packs(data)
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
            print(f"{path}: {added} hold(s)")
            total += added
    print(f"{total} cargo hold(s) given sealing packs")


if __name__ == '__main__':
    main(sys.argv[1])
