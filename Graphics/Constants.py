"""Shared graphics constants and palette for the cockpit view."""

# Color palette
SPACE_COLOR = (8, 10, 24)
PLANET_GRAY = (32, 32, 32)
HULL_COLOR = (38, 42, 55)
HULL_DARK = (23, 26, 36)
HULL_EDGE_COLOR = (70, 78, 98)
STRUT = (30, 34, 46)
CONSOLE = (29, 32, 43)
CONSOLE_EDGE_COLOR = (74, 82, 102)
ACCENT = (94, 234, 212)
ACCENT_DIM = (34, 92, 92)
AMBER = (240, 176, 92)
BINDING_MARK_RED = (235, 64, 64)
BINDING_NEAR_GREEN = (80, 230, 120)
PROGRADE_COLOR = AMBER
RETROGRADE_COLOR = BINDING_MARK_RED
RADAR_BAR_OVER = (240, 240, 240)
RADAR_BAR_UNDER = (120, 120, 120)
RADAR_WORLD_COLOR = (196, 154, 108)
READOUT_BG = (9, 17, 21)
ROCK_EDGE_COLOR = (60, 60, 60)
LASER_COLOR = (255, 255, 0)

# Ore mine geometry and texture
MINE_RADIUS = 4.0  # metres
MINE_HEIGHT = 12.0  # metres
MINE_SEGMENTS = 16
MINE_BASE_HEIGHT = 0.05  # Small offset above the ground to avoid z-fighting.
MINE_TEXTURE_WIDTH = 256
MINE_TEXTURE_HEIGHT = 512

MINE_HULL_COLOR = (60, 64, 72)
MINE_HULL_DARK = (34, 37, 44)
MINE_HULL_LIGHT = (96, 101, 112)
MINE_ACCENT = ACCENT
MINE_WARNING_A = (240, 196, 40)
MINE_WARNING_B = (26, 26, 26)
MINE_CAP_COLOR = (48, 51, 58)

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
VIEW_VERTICAL_FOV_RADIANS = math.radians(40)  # was 60; narrowed ~1/3 to better match real eye-to-screen viewing angle
NEAR_CLIP = 0.5   # metres
MAX_DEPTH = 2000  # metres
LOCAL_STAR_MIN_RADIUS_PX = 1  # floor so a distant/small star never vanishes to 0px
LOCAL_STAR_HALO_WIDTH_PX = 4  # extra radius of the semi-transparent glow ring around the star
LOCAL_STAR_HALO_ALPHA = 90    # 0-255
