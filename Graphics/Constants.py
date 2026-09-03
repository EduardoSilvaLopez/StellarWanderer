"""Shared graphics constants and palette for the cockpit view."""

# Color palette
SPACE = (8, 10, 24)
PLANET_GRAY = (96, 96, 96)
PLANET_HORIZON = (150, 150, 150)
HULL = (38, 42, 55)
HULL_DARK = (23, 26, 36)
HULL_EDGE = (70, 78, 98)
STRUT = (30, 34, 46)
CONSOLE = (29, 32, 43)
CONSOLE_EDGE = (74, 82, 102)
ACCENT = (94, 234, 212)
ACCENT_DIM = (34, 92, 92)
AMBER = (240, 176, 92)
READOUT_BG = (9, 17, 21)
ROCK_EDGE = (60, 60, 60)

# Starfield
STAR_COUNT = 260
STAR_SEED = 20270101

# Canopy geometry (as fractions of window)
CANOPY_TOP = 0.055
CANOPY_TOP_INSET = 0.105
CANOPY_BOTTOM_INSET = 0.02
CONSOLE_TOP = 0.66

# View and rendering
import math
VIEW_VERTICAL_FOV_RADIANS = math.radians(60)
NEAR_CLIP = 0.5   # metres
MAX_DEPTH = 2000  # metres
ROCK_DEPTH_SCALE = 0.35
