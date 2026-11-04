"""Runs ExpansionHistory on its own, without the game, to read the logs it writes."""

from __future__ import annotations

from datetime import datetime

from common.game_logging import configure_logging
from galaxies.politics.expansion_history import ExpansionHistory


def main() -> None:
    configure_logging()
    ExpansionHistory(4, datetime(700, 1, 1)).log_results()

if __name__ == '__main__':
    main()
