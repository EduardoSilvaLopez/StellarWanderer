"""Malfunctions: instruments of the cockpit that fail, and how many (see incident.py). A broken instrument is greyed and
inactive, and does not update: the controls of the ship are not affected. A repair kit, used on the instrument, mends it
(Ship.repair_instrument)."""

from __future__ import annotations
from enum import Enum


class Instrument(Enum):
    """Every instrument of the cockpit that a malfunction can break, with the label it is shown with."""
    YAW = 'Yaw'
    PITCH = 'Pitch'
    ROLL = 'Roll'
    CREDITS = 'Credits'
    MAINTENANCE = 'Maintenance'
    ENERGY = 'Energy'
    TEMPERATURE = 'Temperature'
    GRAVITY = 'Gravity'
    PRESSURE = 'Pressure'
    OUTSIDE = 'Outside'
    COMPASS = 'Compass'
    ALTITUDE = 'Altitude'
    PROXIMITY = 'Proximity'
    WORLD_MAP = 'World map'
    RADAR = 'Radar'
    SCANNER = 'Scanner'
    LOCATION = 'Location'
    CLOCK = 'Clock'
    SYSTEMS = 'Systems'
    PEOPLE = 'People'
    SHIP = 'Ship'
    MISSIONS = 'Missions'
    ORBIT = 'Orbit'
    TRAVEL = 'Travel'
    CARGO = 'Cargo'
