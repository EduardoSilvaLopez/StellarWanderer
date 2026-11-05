"""Take a probe of the atmosphere of a giant of the system and bring it to the portal base (see scoop_body.py for
how the probe works). The giant is chosen from the offer's seed, among the gas and ice giants of the system, and
kept in the mission; the probe fills with the scoop open in its atmosphere (`Ship.collect_probe`)."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Optional

from galaxies.seeds import of_text

from .mission import register
from .scoop_body import ScoopBody
from galaxies.missions.terms import Terms
from galaxies.settlement_kind import SettlementKind

if TYPE_CHECKING:
    from galaxies.body import Body
    from galaxies.jovian_world import JovianWorld
    from galaxies.settlement import Settlement
    from galaxies.people.player import Player
    from spaceships.ship import Ship


@register
class ScoopGiant(ScoopBody):
    """Take a probe of the atmosphere of a giant, then bring it to the portal base."""
    KIND = 'scoop_giant'

    # The offers are made at the portal base only (see MissionBoard.OFFERED_AT_BASE): an outpost has no terms (None).
    TERMS = {
        SettlementKind.OUTPOST: None,
        SettlementKind.PORTAL_BASE: Terms(
            frequency=0.05,
            taken_by_others=0.01,
            deadline_days_min=10,
            deadline_days_max=25,
            reward=25.0,
            failure_penalty=-5.0
            ),
    }

    def __init__(self, giant: str = '', probe_progress: float = 0.0, **common: Any) -> None:
        super().__init__(probe_progress, **common)
        self.giant: str = giant  # where the giant is in its system: "<orbit>|<index in the orbit>", saved

    @classmethod
    def _target(cls, outpost: Settlement, seed: int) -> Optional[dict]:
        from galaxies.jovian_world import JovianWorld
        giants = [world for world in outpost.stellar_system.get_all_worlds() if isinstance(world, JovianWorld)]
        if not giants:
            return None
        chosen = random.Random(of_text(f"{seed} giant")).choice(giants)
        return {'giant': f"{chosen.parent_orbit.get_alterations_key()}|{chosen.index}"}

    def giant_world(self) -> JovianWorld:
        """The giant, found from its place in the system."""
        from galaxies.jovian_world import JovianWorld
        orbit_key, index = self.giant.split('|')
        for orbit in self.issuer_settlement.stellar_system.orbits:
            if orbit.get_alterations_key() == orbit_key:
                tgt = orbit.planets[int(index)]
                if isinstance(tgt, JovianWorld):
                    return tgt
        raise KeyError(f"The giant {self.giant} is not in its system.")

    def subject(self) -> str:
        return f"the atmosphere of {self.giant_world().name}"

    def can_collect(self, ship: Ship) -> bool:
        """In the atmosphere of the giant (it is the one the ship is fixed to while it is there)."""
        import game_environment as gem
        return ship.navigation.ambient() is not None and gem.current_environment.fixed_body is self.giant_world()

    def target_body(self) -> Body:
        return self.giant_world()

    def title(self) -> str:
        return f"Take a probe of the atmosphere of {self.giant_world().name}"

    def description(self) -> str:
        return (
            f"We need a sample of the atmosphere of {self.giant_world().name}."
            "\n\nA good ship and scoop are required to take it."
            "\n\nGo down into the atmosphere, hold still, open the scoop and let it open until the probe is full. "
            "Mind the pressure and temperature."
            "\n\nBring the probe to the portal base."
            )

    def reward_text(self, player: Player) -> str:
        return (
            f"Thank you, Pilot {player.surname}. The probe will tell us more about the composition of"
            f"{self.giant_world().name}, which is becoming interesting for the Community."
            )

    def serialize(self) -> dict:
        return {**super().serialize(), 'giant': self.giant}

    @classmethod
    def _deserialize(cls, source: dict) -> ScoopGiant:
        return ScoopGiant(source['giant'], source['probe_progress'], **ScoopBody._common(source))
