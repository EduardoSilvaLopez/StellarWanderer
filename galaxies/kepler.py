"""Kepler's equation and the orientation of an elliptical orbit, in the reference frame of the stellar system (z along
the spin axes, the reference plane x, y)."""

from __future__ import annotations

import math

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
