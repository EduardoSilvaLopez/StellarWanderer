# Galactic coordinates are in light-years, with the galactic centre at the origin.
INITIAL_STAR_POSITION = (26010.0, 10.0, 10.0)  # the centre of its sector, so the star sits in the middle of the region

# A star's colour is its blackbody colour at its temperature (galaxies/star.py), pushed away from grey by this factor:
# 1.0 is the plain blackbody colour, above 1.0 is more vivid, below 1.0 is paler.
STAR_COLOUR_VIVIDNESS = 1.0

# A world's surface (galaxies/world_surface.py). Its colour is this share of the colour of its surface type, the rest a
# random vivid colour of about the same brightness: 1.0 is the plain colour of the type, 0.0 is entirely random.
WORLD_COLOUR_REALISM = 0.7
WORLD_VIVID_SATURATION_MIN = 0.45  # the random vivid colour's saturation (HSV) is drawn between these two
WORLD_VIVID_SATURATION_MAX = 0.85
WORLD_BRIGHTNESS_JITTER = 0.08  # each world's colour is scaled by 1 plus or minus up to this
# the share of its star's light a world reflects, for its temperature: one value for all worlds
WORLD_BOND_ALBEDO = 0.15

# The fundamental unit is the meter; light-years are used for galactic coordinates.
LIGHT_YEAR_M = 300000000 * 365.2425 * 24 * 60 * 60  # meters, about 0.07% above the exact value (accepted)
ABSOLUTE_MAGNITUDE_DISTANCE_LY = 32.6156  # ly: the distance at which absolute magnitude is measured (about 32.6 ly)

# Galactic regions: cubes aligned to multiples of their size, each holding a whole number of the next smaller. Quadrants
# and districts only feed the seeds for now (galaxies/seeds.py); fixed stars (galaxies/fixed_stars.py) are generated per
# sector.
QUADRANT_SIZE = 8000  # ly
DISTRICT_SIZE = 400  # ly
SECTOR_SIZE = 20  # ly
SECTOR_RADIUS = 3  # sectors generated in each direction around the initial star's sector: 2 gives a 5 x 5 x 5 block
# ly: fixed stars outside this distance of the ship are not drawn in the sky
FIXED_STAR_SHOW_RADIUS = SECTOR_SIZE * SECTOR_RADIUS - 5.0
FIXED_STARS_MEAN_PER_SECTOR = 23  # about 0.003 stars per cubic light-year, the density of the solar neighbourhood
