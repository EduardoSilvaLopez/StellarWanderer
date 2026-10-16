SEEDS_SCALING = 1000000

# Galactic coordinates are in light-years, with the galactic centre at the origin.
INITIAL_STAR_POSITION = (26010.0, 10.0, 10.0)  # the centre of its sector, so the star sits in the middle of the region

# Fixed stars (galaxies/fixed_stars.py): sectors are cubes aligned to multiples of SECTOR_SIZE.
SECTOR_SIZE = 20  # ly
SECTOR_RADIUS = 2  # sectors generated in each direction around the initial star's sector: a 5 x 5 x 5 block
FIXED_STARS_MEAN_PER_SECTOR = 23  # about 0.003 stars per cubic light-year, the density of the solar neighbourhood
