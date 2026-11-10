"""Who works in a settlement, and when: the staffing history, replayed from the seed every time the settlement is made.

A settlement hires people, one at a time, to fill the teams its size asks for; they leave (retirement, or an arrest the
pilot caused) and the same day somebody is hired for their role. The Nth person hired in a settlement, over all roles,
has the seed `derive(settlement.seed, 'person', N)`, so the same history always gives the same people. Only what the
pilot changed is saved (a person's `status_changes`), and the replay applies it at its date.

The replay runs from the settlement's founding (not before STAFFING_START) to the game date, and goes on as the game
date moves. When several things happen at the same instant, the departures come first (by hire order), then the
enlargements, and the hires follow, role by role.

The rota is made from the people present: in each role the newest `teams` members are the substitutes and the rest are
cut into teams in order of hire, so any change reshuffles teams and shifts. That is intended.
"""

from __future__ import annotations
import heapq
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

from galaxies import seeds

if TYPE_CHECKING:
    from galaxies.people.person import Person
    from galaxies.people.role import Role
    from galaxies.settlement import Settlement

STAFFING_START = datetime(620, 1, 1)  # an older settlement starts with the staff of its size at this date

_DEPARTURE = 0  # the kinds of event, in the order they are handled at the same instant
_ENLARGEMENT = 1


class Staffing:
    """The staff history of one settlement, up to the date it was last advanced to (see advance)."""

    def __init__(self, settlement: Settlement) -> None:
        self.settlement: Settlement = settlement
        self.everyone: List[Person] = []  # all hired so far, in order of hire: index N is the Nth person
        self.teams: Dict[Role, int] = {}  # the teams of each role now, from the settlement's size
        self._present: Dict[Role, List[Person]] = {}
        self._gone: set[int] = set()  # indices of the people who have left
        self._arranged: Dict[Role, List[Person]] = {}  # cache of arranged(), cleared at every change
        # (date, kind, order): order is the hire index of a departure, the position in the dates of an enlargement
        self._events: List[tuple[datetime, int, int]] = [
            (max(date, STAFFING_START), _ENLARGEMENT, number)
            for number, date in enumerate(settlement.enlargement_dates)
        ]
        heapq.heapify(self._events)

    @property
    def next_change_at(self) -> Optional[datetime]:
        """When the staff changes next (a departure or an enlargement), None if never."""
        return self._events[0][0] if self._events else None

    def advance(self, until: datetime) -> bool:
        """Replays everything that happens up to `until`. Returns whether the staff changed."""
        changed = False
        while self._events and self._events[0][0] <= until:
            when = self._events[0][0]
            while self._events and self._events[0][0] == when:
                _, kind, order = heapq.heappop(self._events)
                if kind == _DEPARTURE:
                    self._leave(order)
                else:
                    self.teams = self.settlement.teams_at_size(order + 1)
            self._fill(when)
            changed = True
        if changed:
            self._arranged.clear()
        return changed

    def depart(self, person: Person, when: datetime) -> None:
        """Schedules the departure of `person` at `when` (an arrest); the next `advance` to that date carries it out."""
        heapq.heappush(self._events, (when, _DEPARTURE, self.everyone.index(person)))

    def _leave(self, index: int) -> None:
        if index not in self._gone:
            self._gone.add(index)
            person = self.everyone[index]
            self._present[person.role].remove(person)

    def _fill(self, when: datetime) -> None:
        """Hires, role by role, until every role has the members its teams ask for."""
        for role, teams in self.teams.items():
            present = self._present.setdefault(role, [])
            while len(present) < teams * role.team_size:
                self._hire(role, when)

    def _hire(self, role: Role, when: datetime) -> None:
        from galaxies.people.person import Person  # local: the people load the world, which loads the settlements
        index = len(self.everyone)
        person = Person(seeds.derive(self.settlement.seed, 'person', index), self.settlement, role, when)
        self.everyone.append(person)
        self._present[role].append(person)
        heapq.heappush(self._events, (person.departure_at, _DEPARTURE, index))

    def arranged(self, role: Role) -> List[Person]:
        """The present members of `role`, team by team: each team's shift members first, its substitute (if the role has
        any) last. The substitutes are the newest members, the older of them for the first team."""
        if role not in self._arranged:
            members = self._present.get(role, [])
            teams = self.teams.get(role, 0)
            substitutes = members[len(members) - teams:] if role.vacation > 0 and teams else []
            regular = members[:len(members) - len(substitutes)]
            result: List[Person] = []
            for team in range(teams):
                result += regular[team * role.shifts:(team + 1) * role.shifts]
                result += substitutes[team:team + 1]
            self._arranged[role] = result
        return self._arranged[role]

    def staff(self) -> List[Person]:
        """Everyone present, in the order of the roles and then of `arranged`."""
        return [person for role in self.teams for person in self.arranged(role)]
