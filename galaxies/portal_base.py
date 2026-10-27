"""The portal base: an artificial station that hangs fixed over its star, on the star's z axis (the bases sit "over the
stars"), `HEAT_RADIUS_MULTIPLE` heat radii from it. It does not orbit, so its position is constant and its velocity zero
(it holds itself there with the ship's sci-fi energy, which the game does not model). It is a body ships navigate to, as
the star is: targetable, with a fixed zone round it, never bound to.

Its form is a ring that spins for 0.1 g, with a hangar on the axis that does not spin; the mouth of the hangar faces the
star. The radius of the ring, which contains everything else, is drawn from the seed in steps of 5 m (the engineers'
configurations). Only what flying to it needs is here for now: where it is, how big, its name and its entry in the
knowledge base."""

from __future__ import annotations
import math
from datetime import datetime
import random
from typing import TYPE_CHECKING, Optional

from common.vector3 import Vector3
from galaxies import seeds
from galaxies.body import Body
from galaxies.people.role import BASE_ROLES
from galaxies.settlement import Settlement
from galaxies.settlement_kind import SettlementKind
from galaxies.world import World

if TYPE_CHECKING:
    from galaxies.stellar_system import StellarSystem
    from spaceships.ship import Ship


class PortalBase(Body, Settlement):
    """The portal base of a stellar system: a settlement (what happens inside, see Settlement) and a body the ship
    navigates to (its position and its fixed zone). Its first version has the Dockmaster and the Communication Officer,
    and no mission offers yet (its frequency is 0 for each kind)."""

    is_world = False
    is_base = True  # serviced like an outpost: the long distance advice keeps the same reserve for it
    roles = BASE_ROLES
    kind = SettlementKind.PORTAL_BASE
    MOUTH_DEPTH = 48.0  # m, from the ring's centre to the mouth of the hangar, at the reference radius (100 m)
    BERTH_CLEARANCE = 200.0  # m, how far in front of the mouth the ship is put when the pilot leaves
    DOCK_MAX_SPEED = 1.0  # m/s relative to the base: the ship docks only below this
    # The hangar, at the reference radius (see graphics/portal_base_shape.py): its outer width and height, and the hub's
    # length, which is where the hangar meets the ring's spokes.
    HANGAR_WIDTH = 12.0
    HANGAR_HEIGHT = 10.0
    HUB_LENGTH = 8.0

    HEAT_RADIUS_MULTIPLE = 10  # how far over the star it hangs, in the star's heat radii
    RING_RADIUS_MIN = 100.0  # m, the outer radius of the ring: the body's radius, drawn in steps of 5 m
    RING_RADIUS_MAX = 200.0  # m, the largest outer radius
    FLOOR_RADIUS_FRACTION = 0.98  # of the outer radius: 2 m of shielding at 100 m
    FLOOR_GRAVITY = 0.981  # m/s^2, a tenth of the Earth's

    def __init__(self, stellar_system: StellarSystem, saved: Optional[dict] = None) -> None:
        self._stellar_system: StellarSystem = stellar_system
        self.seed: int = seeds.derive(stellar_system.seed, 'portal base')
        my_random: random.Random = random.Random(self.seed)

        self.radius: float = float(my_random.randrange(int(self.RING_RADIUS_MIN), int(self.RING_RADIUS_MAX) + 1, 5))
        self.height: float = float(PortalBase.HEAT_RADIUS_MULTIPLE * stellar_system.star.default_heat_radius)  # m
        self.name: str = self._generate_name(my_random)
        Settlement.__init__(self, self.seed)
        if saved is not None:  # what the settlement saved in its system (see StellarSystem.get_alterations)
            self._read_alterations(saved)
            self.is_altered = True

    def _generate_name(self, rnd: random.Random) -> str:
        return "Protecting-" + rnd.choice(self._stellar_system.political_entity.portal_base_names)

    def calculate_stellar_position(self, current_datetime: datetime) -> Vector3:
        return Vector3(0.0, 0.0, self.height)

    def calculate_stellar_velocity(self, current_datetime: datetime) -> Vector3:
        return Vector3(0.0, 0.0, 0.0)

    @property
    def stellar_system(self) -> StellarSystem:
        return self._stellar_system

    # region Settlement
    def stellar_position(self, current_datetime: datetime) -> Vector3:
        return Vector3(0.0, 0.0, self.height)

    # Missions that need a planet (rock scans) ask for it: the base has none.
    planet = None

    def _parent_altered(self) -> None:
        self._stellar_system.set_altered()

    def get_alterations(self) -> Optional[dict]:
        """What the settlement saves, in its system's alterations (its visits and its handling)."""
        alterations: dict = {}
        self._alterations_of_visits(alterations)
        return alterations or None

    def inside_key(self) -> str:
        return 'portal_base'

    def full_keys(self) -> str:
        """The key that names this base in the galaxy: its system's, and the base's."""
        return '|'.join((self._stellar_system.get_alterations_key(), self.inside_key()))

    def address(self) -> str:
        return f"{self.name}, portal base, {self._stellar_system.name}"

    def residency_line(self) -> str:
        return f"Portal base {self.name}, {self._stellar_system.name}"

    def place_details(self) -> list[str]:
        system = self._stellar_system
        return [self.name, system.star.name, system.political_entity.name]

    @property
    def body(self) -> Body:
        return self

    def stellar_velocity(self, current_datetime: datetime) -> Vector3:
        return Vector3(0.0, 0.0, 0.0)

    @property
    def plane_distance(self) -> float:
        return 0.0  # over the star: every belt point is the same distance up, so the nearest one is the innermost

    def needs_water(self) -> bool:
        return True  # the ring's people drink: there is no icy world under them

    def approach_position(self, clearance: float = BERTH_CLEARANCE) -> Vector3:
        """The point `clearance` metres in front of the mouth of the hangar, on the axis, toward the star: where the
        ship is put when the pilot leaves (the mouth faces the star, see graphics/portal_base_shape.py)."""
        mouth = self.MOUTH_DEPTH * self.radius / self.RING_RADIUS_MIN
        return Vector3(0.0, 0.0, self.height - mouth - clearance)

    def contains_hangar(self, position: Vector3) -> bool:
        """Whether the stellar-frame `position` is inside the hangar, from its mouth to the hub: a ship that has
        flown in through the mouth is at the base, whatever the beam says."""
        scale = self.radius / self.RING_RADIUS_MIN
        relative_x = position.x
        relative_y = position.y
        relative_z = position.z - self.height  # the ring's centre is at z = 0 in the base's own frame
        mouth_z = -self.MOUTH_DEPTH * scale
        hub_front_z = -self.HUB_LENGTH / 2.0 * scale
        half_width = self.HANGAR_WIDTH / 2.0 * scale
        half_height = self.HANGAR_HEIGHT / 2.0 * scale
        return abs(relative_x) < half_width and abs(relative_y) < half_height and mouth_z <= relative_z <= hub_front_z

    def place_after_leaving(self, ship: Ship) -> None:
        """The ship is put in front of the hangar, at rest, looking at the base (forward along +z, up along +y)."""
        position = self.approach_position()
        ship.position.set_vector((position.x, position.y, position.z))
        ship.velocity.set_vector((0.0, 0.0, 0.0))
        ship.attitude.forward = Vector3(0.0, 0.0, 1.0)
        ship.attitude.right = Vector3(1.0, 0.0, 0.0)
        ship.attitude.up = Vector3(0.0, 1.0, 0.0)
    # endregion

    @property
    def spin(self) -> float:
        """The angular speed of the ring (rad/s) that gives `FLOOR_GRAVITY` at its floor."""
        return math.sqrt(PortalBase.FLOOR_GRAVITY / (PortalBase.FLOOR_RADIUS_FRACTION * self.radius))

    @property
    def pull(self) -> float:
        """The pull of the star at the base (m/s^2), which the thrusters have to answer."""
        return World.GRAVITATIONAL_CONSTANT * self._stellar_system.star.mass / self.height ** 2

    def markdown(self) -> str:
        """Markdown of the base: where it hangs and how big it is."""
        AU: float = 1.496e11  # m. The text is for players, like the planets' entries.
        return (
            f"### {self.name}\n"
            f"* Fixed over the star, {self.height / AU:.2f} AU along its pole\n"
            f"* Ring of {self.radius:.0f} m of radius, spinning for a tenth of the gravity of the Earth "
            f"({math.sqrt(0.1 * 9.81 / (self.radius - 2.0)) * 60.0 / math.tau:.2f} turns per minute)\n"
        )
