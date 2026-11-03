"""Shared graphics constants and palette for the cockpit view."""

import math

# The font of the cockpit instruments and of the message dialogs' body text: a file in common/resources/fonts (SIL OFL).
# Change it here to change both. The dialogs' body size goes with it (common/dialogs/dialog_fonts.py).
FONT_FILE = 'Oxanium.ttf'

# Color palette
# pitch black: in vacuum there is no sky glow. What light the sky has is the Milky Way and the stars
SPACE_COLOR = (0, 0, 0)
# The Milky Way, Andromeda and the Magellanic Clouds (graphics/milky_way.py). The panorama (tools/generate_milky_way.py)
# keeps the real ratios between the brightness of its regions, but the real sky is far too faint for a screen (the
# brightest Milky Way is about 1e-3 cd/m2, under one 8-bit step), so it is shown at this share of its stored brightness:
# 0.2 puts the bulge near code 50 and the band near 20 on black. 0 hides it, 1 is the stored brightness. Ratios stay the
# same.
MILKY_WAY_EXPOSURE = 0.2
HULL_COLOR = (38, 42, 55)
HULL_DARK = (26, 24, 24)
HULL_EDGE_COLOR = (108, 101, 94)
STRUT = (30, 34, 46)
CONSOLE = (44, 40, 38)
CONSOLE_EDGE_COLOR = (150, 118, 70)  # the outline of each instrument: the one warm accent of the steel
ACCENT = (94, 234, 212)
ACCENT_DIM = (34, 92, 92)
# readout labels: halfway between, legible on READOUT_BG
ACCENT_LABEL = tuple((a + b) // 2 for a, b in zip(ACCENT, ACCENT_DIM))
AMBER = (240, 176, 92)
BINDING_MARK_RED = (235, 64, 64)
BINDING_NEAR_GREEN = (80, 230, 120)
NOTIFICATION_BAD_ORANGE = (255, 150, 40)  # a refused or failed attempt in the notification bar
# the gravity bar: darker than the warnings, as the pull is not critical in the normal case
GRAVITY_RED = (150, 42, 42)
GRAVITY_AMBER = (150, 110, 60)
GRAVITY_GREEN = (46, 130, 72)
SPEED_WARNING_RED = BINDING_MARK_RED  # "Speed" readout when a collision with the fixed body is unavoidable
PROGRADE_COLOR = AMBER
TARGET_MARKER_COLOR = (236, 236, 236)  # the X on the canopy where the target is, or on its border
ADVICE_COLOR = (200, 150, 255)  # the long distance advice and the mark where the target will be
ADVICE_ACCELERATE_COLOR = (120, 230, 140)
ADVICE_STAY_COLOR = (130, 190, 255)
ADVICE_DECELERATE_COLOR = (255, 170, 80)
ORBIT_PATH_COLOR = (46, 120, 120)  # the orbit of the targeted body, drawn in the sky
RETROGRADE_COLOR = BINDING_MARK_RED
RADAR_BAR_OVER = (240, 240, 240)
RADAR_BAR_UNDER = (120, 120, 120)
RADAR_WORLD_COLOR = (196, 154, 108)
RADAR_MOON_COLOR = (150, 190, 215)
RADAR_STAR_DOT_RADIUS = 3
RADAR_WORLD_DOT_RADIUS = 3
RADAR_MOON_DOT_RADIUS = 2
RADAR_ASTEROID_COLOR = (175, 150, 215)  # the asteroids of the ongoing missions: a lilac, apart from the worlds' colours
RADAR_ASTEROID_DOT_RADIUS = 2
RADAR_BASE_COLOR = (130, 215, 150)  # the portal base: a green, apart from the worlds' and the asteroids' colours
RADAR_BASE_DOT_RADIUS = 2
READOUT_BG = (9, 17, 21)
LASER_COLOR = (255, 255, 0)
# The beam's glow (graphics/laser.py) is additive, so it brightens what is behind it. It is round: concentric
# cylinders, each a layer (radius as a share of the beam's half-size, colour, alpha 0-255). Stacked, the layers near
# the axis add up to white-hot, and the light falls off smoothly, with no edge.
LASER_HALO_COLOR = (255, 170, 40)
LASER_CORE_COLOR = (255, 255, 230)
LASER_BEAM_SEGMENTS = 20  # the round cross-section of the beam and of the muzzle flash
LASER_BEAM_LAYERS = (
    (3.0, LASER_HALO_COLOR, 10),
    (2.3, LASER_HALO_COLOR, 14),
    (1.7, LASER_HALO_COLOR, 22),
    (1.2, LASER_COLOR, 36),
    (0.8, LASER_COLOR, 70),
    (0.5, LASER_COLOR, 140),
    (0.25, LASER_CORE_COLOR, 255),
)
# The muzzle flash: a round glow at the emitter, bright for a moment when the beam switches on, then steady and
# flickering
LASER_MUZZLE_COLOR = (255, 250, 220)
LASER_MUZZLE_RADIUS = 0.5  # metres
LASER_MUZZLE_STEADY = 0.35  # the share of full brightness while the beam fires, between the bursts
LASER_MUZZLE_BURST_SECONDS = 0.12  # real seconds: the burst at the start of the beam falls away in about this time
LASER_IMPACT_COLOR = (255, 250, 220)
LASER_IMPACT_RADIUS = 0.8  # metres: the hot spot on a rock at its hottest, smaller when it is cooler
LASER_IMPACT_LIFT = 0.3  # metres: the spot sits this far back along the beam, so it is not inside the rock
LASER_IMPACT_ALPHA = 255  # 0-255: the hot spot's centre, at the rock's hottest
LASER_IMPACT_SEGMENTS = 16

# Ore mine geometry and texture
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

# The texture of an external mine that has been unused for long (ExternalMine.is_inactive): weathered, no glowing band.
MINE_INACTIVE_HULL_COLOR = (74, 68, 60)
MINE_INACTIVE_HULL_DARK = (44, 40, 36)
MINE_INACTIVE_HULL_LIGHT = (98, 90, 80)
MINE_INACTIVE_ACCENT = (58, 52, 46)
MINE_INACTIVE_WARNING_A = (118, 98, 54)
MINE_INACTIVE_WARNING_B = (38, 35, 32)

# Canopy geometry (as fractions of window)
CANOPY_TOP = 0.055
CANOPY_TOP_INSET = 0.105
CANOPY_BOTTOM_INSET = 0.02
CONSOLE_TOP = 0.66

# View and rendering
VIEW_VERTICAL_FOV_RADIANS = math.radians(40)  # was 60; narrowed ~1/3 to better match real eye-to-screen viewing angle
NEAR_CLIP = 0.5  # metres
MAX_DEPTH = 2000  # metres
# The scoop's view (graphics/scoop_view.py): the camera under the hull, and how far its lamps reach.
# The local star (graphics/local_star.py): a limb-darkened disc and its corona.
STAR_LIMB_DARKENING = 0.5  # u in I(mu) = 1 - u (1 - mu): the rim's brightness is 1 - u of the centre's
STAR_CORE_WHITENESS = 0.6  # the centre of the disc: the star's colour mixed this much towards white
STAR_CORONA_EXTENT = 4.0  # the corona fades out at this many star radii from the centre
STAR_CORONA_FALLOFF = 2.5  # the corona's brightness falls as (R / r) ** this
STAR_CORONA_ALPHA = 150  # the corona's opacity at the rim, 0-255
STAR_GLOW_MIN_PX = 14  # the corona's radius in pixels is never less: a distant star is a glowing point
# The sun's surface and visor (graphics/star_surface.py). Granulation and sunspots are baked into its texture.
GRANULATION_STRENGTH = 0.08  # how much the granules darken and brighten the disc
GRANULE_CELL_SHARE = 0.04  # a granule's size, in disc radii
SPOT_COUNT_MIN = 3  # sunspots: this many, and up to SPOT_COUNT_EXTRA more, by the star's seed
SPOT_COUNT_EXTRA = 3
SPOT_RADIUS_MIN = 0.05  # a spot's radius, in disc radii
SPOT_RADIUS_MAX = 0.12
SPOT_DEPTH = 0.45  # how much darker a spot's core is
SPOT_FRAME_SECONDS = 1 / 30  # the real time of a frame, to work out how far a sunspot turns between two frames
SPOT_MAX_TURN_PER_FRAME = 0.25  # above this share of a turn per frame, a sunspot would jump: it is not drawn
VISOR_START_PX = 120  # the visor starts to darken the view when the sun's disc is this big on the screen
VISOR_FULL_PX = 400  # and is at its darkest at this size
VISOR_MAX_ALPHA = 0.8  # the darkest the visor makes the view (0 to 1)
# The sun's flares and glare (graphics/star_flares.py, graphics/star_gl.py). Flares are in game time.
FLARE_SLOT_SECONDS = 6 * 3600  # each slot of game time may hold one flare
FLARE_CHANCE = 0.5  # the chance that a slot holds one
FLARE_RISE_SECONDS = 60  # game seconds from start to peak
FLARE_DECAY_SECONDS = 600  # game seconds from peak to a tenth
FLARE_MAX_TIME_SCALE = 60  # above this time scale flares are not drawn: they would flicker
FLARE_SIZE_SHARE = 0.6  # a flare's size, in disc radii
GLARE_MAX = 0.5  # the glare's brightness at the sun's position when it is at the screen centre
GLARE_RADIUS_SHARE = 0.6  # the glare fades out at this share of the window's height from the sun
GLARE_SIZE_OF_CORONA = 1.0  # the glare's half-size, in corona radii: it follows the sun's apparent size, not the window
# Debug frame rate (graphics/debug_fps.py): source runs only.
DEBUG_FPS_WINDOW_SECONDS = 0.5  # the rate is measured over this long
DEBUG_FPS_POSITION = (12, 10)  # top-left corner of the window, in pixels
# Starlight on the cockpit and the heat vignette (graphics/starlight.py).
STARLIGHT_TINT_MAX = 0.35  # share of the star's colour added to the cockpit at the death radius and nearer
HEAT_VIGNETTE_COLOUR = (220, 30, 10)
HEAT_VIGNETTE_MAX_ALPHA = 200  # at the window's corners, when the temperature is at its maximum
HEAT_VIGNETTE_INNER = 0.45  # the vignette starts at this share of the way from the centre to a corner
WORLD_AMBIENT_LIGHT = 0.05  # share of a world's surface colour (World.surface_colour) still visible on the unlit side
# The gas of a giant is drawn up to this many scale heights above the cloud tops, and its single-scattered sunlight is
# multiplied by the gain, which is tuned by eye so that the cloud tops are as bright as their colour.
GIANT_HAZE_TOP = 10.0
GIANT_SUN_GAIN = 1.5
GIANT_LIMB_DARKENING = 0.6  # the cloud tops, seen along the horizon, have this much less light (0 to 1)
# The thin haze scatters light mostly forward (Henyey-Greenstein asymmetry, 0 = evenly): with the star behind a giant its
# limb glows as a crescent. Tuned by eye; the thick clouds scatter evenly.
GIANT_FORWARD_SCATTERING = 0.1
# The clouds of a giant: noise stretched along the latitude circles, in octaves that stop where a pixel could not show them.
GIANT_CLOUD_WAVELENGTH = 2.0e6  # m: the coarsest feature, across the bands
GIANT_CLOUD_STRETCH = 6.0  # how much longer the features are along the bands than across them
GIANT_CLOUD_OCTAVES = 10  # each with half the wavelength of the one before
GIANT_CLOUD_GAIN = 0.65  # each octave has this share of the strength of the one before: the higher, the sharper
GIANT_CLOUD_CONTRAST = 2.2  # the swing of the clouds' brightness, in band contrasts
GIANT_CLOUD_WARP = 0.8  # how far the noise bends its own coordinates, in coarsest wavelengths: the turbulence
# The clouds as a volume: the cloud tops rise and fall (relief, lit by the sun's slope) and the layers differ with depth.
GIANT_CLOUD_RELIEF = 1.5  # how far the cloud tops rise and fall, in scale heights
GIANT_CLOUD_RELIEF_OCTAVES = 5  # of the noise that shapes them: the coarse ones (fine ones would only add creases)
GIANT_CLOUD_DENSITY = 0.7  # how much the clouds thicken and thin the gas (0 to 1)
GIANT_CLOUD_LAYER_EDGE = 5.0  # the clouds reach this many scale heights above and below the 1 bar level (fading from half)
GIANT_CLOUD_DEPTH_WAVELENGTH = 3.0e5  # m: the altitude over which the coarsest clouds change, so the layers differ
GIANT_CLOUD_RELIEF_SHADING = 0.6  # how much the slope of the cloud tops lights and shadows them (0 to 1)
# Storms (JovianWorld.storms): vortices in the clouds, which swirl them, tint them and raise the cloud tops.
GIANT_STORM_RAISE = 0.8  # how much higher the cloud tops are in a storm, as a share of the clouds' relief
GIANT_STORM_MAX = 6  # the most that are drawn at once
# Lightning: the flashes of a giant (JovianWorld.lightning) light the gas round them from below.
GIANT_LIGHTNING_GAIN = 2.0  # how bright a flash is, against the clouds lit by the star
GIANT_LIGHTNING_COLOUR = (0.78, 0.86, 1.0)  # a little cold
GIANT_LIGHTNING_MAX_TIME_SCALE = 1000  # from this time scale on there is no lightning (below it, even a one-frame flash is shown)
GIANT_LIGHTNING_MAX_FLASHES = 8  # the most that are drawn at once
ATMOSPHERE_TINT_MAX = 0.5  # share of the cloud colour, lit, added to the cockpit when the gas around the ship is thick and lit
# The light inside the clouds is scattered many times, so it feels only a share of the optical depth that the direct sun
# does: by the diffusion approximation, sqrt(3 (1 - w) (1 - w g)) of it, where w is the single-scattering albedo of the
# cloud and g the asymmetry of its scatterers. The Galileo probe found the deeper clouds of Jupiter to scatter sunlight
# without absorbing much (Sromovsky et al. 1998), so w is close to 1; the two values are estimates, not measurements
# (ice particles of a micron have g near 0.85). The probe's radiometer measured from 0.44 to 14 bars.
GIANT_SINGLE_SCATTERING_ALBEDO = 0.99
GIANT_ASYMMETRY = 0.85
GIANT_LIGHT_PENETRATION = math.sqrt(3.0 * (1.0 - GIANT_SINGLE_SCATTERING_ALBEDO)
                                    * (1.0 - GIANT_SINGLE_SCATTERING_ALBEDO * GIANT_ASYMMETRY))
# How coarse the march through the gas is: the most optical depth, and the most altitude (in scale heights), of a step.
GIANT_STEP_DEPTH = 0.6
GIANT_STEP_HEIGHT = 1.0
# A giant on screen larger than this many pixels is drawn into a smaller target (what the shader does per pixel is the
# cost of the frame) and scaled up: the gas is smooth.
GIANT_PIXEL_BUDGET = 120000
GIANT_TARGET_SIZE = 1024  # the side of the square target, pixels
# Minimum light on any surface, from the stars: a share of full daylight that never goes away, from every direction.
# Keeps the night readable, so the ground, rocks and buildings do not go black.
SURFACE_STARLIGHT = 0.30
WORLD_LIGHT_TINT_MIX = 0.5  # how much the star's colour tints the light (0 = white light, 1 = star colour)
MIN_VISIBLE_PX = 1.0  # an object (world, ring, base, mission asteroid) whose diameter on screen is less is not drawn
WORLD_MIN_RADIUS_PX = 0.5  # floor so a distant world stays a lit disc of a pixel across, never smaller
OUTPOST_DOT_COLOR = (255, 250, 210)  # outposts on a planet's surface, drawn as tiny dots in the sky
OUTPOST_DOT_RADIUS_PX = 2
FIXED_STAR_DOT_RADIUS_PX = 1  # fixed stars are drawn in their own colour; they are far away, so tiny dots
# a fixed star is drawn only if its apparent magnitude is at most this (lower is brighter)
NAKED_EYE_LIMIT_MAGNITUDE = 6.0
LIT_WORLD_PIXEL_BUDGET = 80_000  # discs larger than this (in pixels) are shaded on a coarser grid
