"""Take a probe of the corona of the system's star and bring it to the portal base (see scoop_body.py for how the
probe works). It fills with the scoop open in the heat radius of the star (`Ship.collect_probe`)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .mission import register
from .scoop_body import ScoopBody
from galaxies.missions.terms import Terms
from galaxies.settlement_kind import SettlementKind

if TYPE_CHECKING:
    from galaxies.body import Body
    from galaxies.settlement import Settlement
    from galaxies.people.player import Player
    from spaceships.ship import Ship


@register
class ScoopStar(ScoopBody):
    """Take a probe of the corona, then bring it to the portal base."""
    KIND = 'scoop_star'

    # The offers are made at the portal base only (see MissionBoard.OFFERED_AT_BASE): an outpost has no terms (None).
    TERMS = {
        SettlementKind.OUTPOST: None,
        SettlementKind.PORTAL_BASE: Terms(
            frequency=0.03,
            taken_by_others=0.01,
            deadline_days_min=10,
            deadline_days_max=20,
            reward=80.0,  # By instantaneous resolution, 25% of it is more probable.
            failure_penalty=-5.0
            ),
    }

    @classmethod
    def _target(cls, outpost: Settlement, seed: int) -> Optional[dict]:
        return {}  # the star of the system: nothing to choose

    def subject(self) -> str:
        return "the corona"

    def can_collect(self, ship: Ship) -> bool:
        """Unbound, in the heat radius of the star of the system the mission asks for."""
        import game_environment as gem
        if ship.is_bound:
            return False
        system = gem.current_environment.nearest_system
        return (system.get_alterations_key() == self.system_key()
                and ship.navigation.distance_to_body_centre(system.star) < system.star.default_heat_radius)

    def target_body(self) -> Body:
        return self.issuer_settlement.stellar_system.star

    def title(self) -> str:
        return "Take a probe of the corona"

    def description(self) -> str:
        return (
            "We need a sample of the corona of our star."
            "\n\nA scoop is required to take it. A heat shield and solar panels are recommended."
            "\n\nGet close enough to the star, stop, open the scoop and let it open until the probe is full."
            "\n\nBring the probe to the portal base."
            )

    def reward_text(self, player: Player) -> str:
        return (
            f"Thank you, Pilot {player.surname}. The probe will tell us what the star is made of."
            )

    @classmethod
    def _deserialize(cls, source: dict) -> ScoopStar:
        return ScoopStar(source['probe_progress'], **ScoopBody._common(source))
