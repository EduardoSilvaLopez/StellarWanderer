"""Kepler's equation and the orientation of an elliptical orbit, in the reference frame of the stellar system (z along
the spin axes, the reference plane x, y), and the free fall of a ship about a body (`propagate`)."""

from __future__ import annotations

import math

from common.vector3 import Vector3

Axis = tuple[float, float, float]


def eccentric_anomaly(eccentricity: float, mean_anomaly: float) -> float:
    """Solves Kepler's equation, E - e sin E = M, for E by Newton's method."""
    if eccentricity == 0.0:
        return mean_anomaly
    anomaly = mean_anomaly + eccentricity * math.sin(mean_anomaly)
    for _ in range(20):
        step = (anomaly - eccentricity * math.sin(anomaly) - mean_anomaly) / (1.0 - eccentricity * math.cos(anomaly))
        anomaly -= step
        if abs(step) < 1e-12:
            break
    return anomaly


def orbit_axes(node_longitude: float, inclination: float, periapsis_argument: float) -> tuple[Axis, Axis]:
    """The orbit's two in-plane axes: towards the periapsis, and a quarter turn on."""
    cos_node, sin_node = math.cos(node_longitude), math.sin(node_longitude)
    cos_incl, sin_incl = math.cos(inclination), math.sin(inclination)
    cos_peri, sin_peri = math.cos(periapsis_argument), math.sin(periapsis_argument)
    periapsis_axis = (
        cos_node * cos_peri - sin_node * sin_peri * cos_incl,
        sin_node * cos_peri + cos_node * sin_peri * cos_incl,
        sin_peri * sin_incl,
    )
    quarter_axis = (
        -cos_node * sin_peri - sin_node * cos_peri * cos_incl,
        -sin_node * sin_peri + cos_node * cos_peri * cos_incl,
        cos_peri * sin_incl,
    )
    return periapsis_axis, quarter_axis


def stumpff_c(z: float) -> float:
    """The Stumpff function C(z) = (1 - cos(sqrt z)) / z: cosh for z < 0, one half at z = 0."""
    if abs(z) < 1.0:  # the series: the closed form loses its digits near 0
        return sum((-z) ** k / math.factorial(2 * k + 2) for k in range(12))
    if z > 0.0:
        root = math.sqrt(z)
        return (1.0 - math.cos(root)) / z
    root = math.sqrt(-z)
    return (math.cosh(root) - 1.0) / -z


def stumpff_s(z: float) -> float:
    """The Stumpff function S(z) = (sqrt z - sin(sqrt z)) / (sqrt z)^3: sinh for z < 0, one sixth at z = 0."""
    if abs(z) < 1.0:
        return sum((-z) ** k / math.factorial(2 * k + 3) for k in range(12))
    if z > 0.0:
        root = math.sqrt(z)
        return (root - math.sin(root)) / root ** 3
    root = math.sqrt(-z)
    return (math.sinh(root) - root) / root ** 3


def propagate(gravitational_parameter: float, position: Vector3, velocity: Vector3,
              seconds: float) -> tuple[Vector3, Vector3]:
    """The position and velocity after `seconds` of free fall about a centre with `gravitational_parameter` (G times its
    mass), from the position and velocity relative to that centre. The exact two-body solution for any orbit (ellipse,
    parabola or hyperbola) and any step: Lagrange coefficients in universal variables, with chi found by Newton's
    method, bisection as the fallback."""
    if seconds == 0.0:
        return position, velocity
    root_mu = math.sqrt(gravitational_parameter)
    radius = position.length()
    alpha = 2.0 / radius - velocity.dot(velocity) / gravitational_parameter  # 1 / semi-major axis
    radial = position.dot(velocity) / root_mu

    def residual(chi: float) -> float:
        z = alpha * chi * chi
        return radial * chi * chi * stumpff_c(z) + (1.0 - alpha * radius) * chi ** 3 * stumpff_s(z) \
            + radius * chi - root_mu * seconds

    def slope(chi: float) -> float:
        z = alpha * chi * chi
        return radial * chi * (1.0 - z * stumpff_s(z)) + (1.0 - alpha * radius) * chi * chi * stumpff_c(z) + radius

    # The residual rises with chi, and its slope is the radius, so the root is bracketed by 0 and a doubling.
    low, high = 0.0, root_mu * seconds / radius  # a circular orbit's chi, as a first guess
    while residual(high) < 0.0:
        low, high = high, 2.0 * high
    chi = high
    for _ in range(100):
        value = residual(chi)
        if value > 0.0:
            high = chi
        else:
            low = chi
        step = chi - value / slope(chi)
        if not low < step < high:
            step = (low + high) / 2.0
        converged = abs(step - chi) <= 1e-12 * high
        chi = step
        if converged:
            break

    z = alpha * chi * chi
    c, s = stumpff_c(z), stumpff_s(z)
    f = 1.0 - chi * chi / radius * c
    g = seconds - chi ** 3 / root_mu * s
    new_position = position * f + velocity * g
    new_radius = new_position.length()
    f_dot = root_mu / (new_radius * radius) * chi * (z * s - 1.0)
    g_dot = 1.0 - chi * chi / new_radius * c
    return new_position, position * f_dot + velocity * g_dot
