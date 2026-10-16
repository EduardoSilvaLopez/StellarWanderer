SEEDS_SCALING = 1000000

# Galactic coordinates are in light-years, with the galactic centre at the origin.
INITIAL_STAR_POSITION = (26010.0, 10.0, 10.0)  # the centre of its sector, so the star sits in the middle of the region

# A star's colour is its blackbody colour at its temperature (galaxies/star.py), pushed away from grey by this factor:
# 1.0 is the plain blackbody colour, above 1.0 is more vivid, below 1.0 is paler.
STAR_COLOUR_VIVIDNESS = 1.0

# The fundamental unit is the meter; light-years are used for galactic coordinates.
LIGHT_YEAR_M = 300000000 * 365.2425 * 24 * 60 * 60  # meters, about 0.07% above the exact value (accepted)
ABSOLUTE_MAGNITUDE_DISTANCE_LY = 32.6156  # ly: the distance at which absolute magnitude is measured (about 32.6 ly)

# Fixed stars (galaxies/fixed_stars.py): sectors are cubes aligned to multiples of SECTOR_SIZE.
SECTOR_SIZE = 20  # ly
SECTOR_RADIUS = 3  # sectors generated in each direction around the initial star's sector: 2 gives a 5 x 5 x 5 block
FIXED_STAR_SHOW_RADIUS = SECTOR_SIZE * SECTOR_RADIUS - 5.0  # ly: fixed stars outside this distance of the ship are not drawn in the sky
FIXED_STARS_MEAN_PER_SECTOR = 23  # about 0.003 stars per cubic light-year, the density of the solar neighbourhood
