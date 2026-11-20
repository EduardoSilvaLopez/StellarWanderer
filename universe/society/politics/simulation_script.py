"""Runs ExpansionHistory on its own, without the game: logs its results as of a year, writes the whole history to the
cache of its galaxy seed (data/Cache/<seed>/history.json), and the results as text to
data/Logs/<seed>/history_results_<year>.txt.

Usage: python -m universe.society.politics.simulation_script [seed, default 4] [year, default 750]"""

from __future__ import annotations

from datetime import datetime
import json
import os
import sys

from common.game_logging import configure_logging
from common.paths import data_path
from universe.society.politics.expansion_history import ExpansionHistory, HORIZON

DEFAULT_SEED = 4


def main() -> None:
    configure_logging()
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SEED
    year = int(sys.argv[2]) if len(sys.argv) > 2 else HORIZON.year
    history = ExpansionHistory(seed, datetime(year, 1, 1))
    history.log_results()

    folder = data_path('Cache', str(seed))
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, 'history.json')
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(history.to_dict(), file, ensure_ascii=False, indent=1)
    print(f"Cache written: {path} ({len(history.all_settled)} systems).")

    logs_folder = data_path('Logs', str(seed))
    os.makedirs(logs_folder, exist_ok=True)
    results_path = os.path.join(logs_folder, f'history_results_{year}.txt')
    with open(results_path, 'w', encoding='utf-8') as file:
        file.write(history.dropped_text() + "\n" + history.results_text() + "\n")
    print(f"Results written: {results_path}.")


if __name__ == '__main__':
    main()
