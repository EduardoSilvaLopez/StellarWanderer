"""Generate the sky panorama common/resources/textures/milky_way.png (drawn by graphics/milky_way.py).

Run from the project root:  python tools/generate_milky_way.py [width of the model, default 2048]

The panorama is the Milky Way as seen from the initial star (galaxies/constants.py INITIAL_STAR_POSITION), plus Andromeda and
the two Magellanic Clouds. It is an equirectangular picture in galactic coordinates: the column is the galactic longitude
l (the centre of the picture is l = 0, the direction of the galactic centre, and l grows to the right), the row is the
galactic latitude b (the top is the north galactic pole). The picture is twice as wide as the model, which is smoothed up.

How it is made:
- The light comes from a model of the Galaxy (all lengths in kpc, centred on the galactic centre): a thin and a thick
  disc, a bulge with a bar at 27 degrees, and spiral arms with the radii and pitch angles of Reid et al. 2019 (approximate:
  they are continued beyond what they measured). The Sun is at the position of the initial star. The light along each
  sight line is summed, with the dust in between: a disc of dust that follows the arms, in clumps (noise), and a few
  real clouds near the Sun (Aquila Rift, Ophiuchus, Pipe, Coalsack...). Dust reddens: blue is dimmed more than red.
- The scale is physical: the model is set so that the median of the band along the galactic plane is a surface brightness
  of BAND_MAG (V mag/arcsec2), and Andromeda and the Magellanic Clouds have their real total magnitudes. Everything is a
  luminance in cd/m2.
- The picture stores what a display needs to show the right ratios between regions: brightness in the display's gamma
  (GAMMA), where 255 is the luminance of REFERENCE_MAG. Nothing in it is meant to be shown at that absolute brightness:
  real sky is far too faint for a screen (the brightest Milky Way is about 1e-3 cd/m2). graphics/milky_way.py shows it
  scaled by MILKY_WAY_EXPOSURE (graphics/constants.py), which keeps the ratios.
"""

import math
import os
import sys
import time
from typing import List, Tuple

import numpy as np
import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from galaxies.constants import INITIAL_STAR_POSITION  # noqa: E402

OUT_PATH = os.path.join(ROOT, 'common', 'resources', 'textures', 'milky_way.png')

KPC_PER_LY = 0.306601e-3
# Standard galactic frame (right-handed, kpc, centred on the galactic centre): X to the centre, Y to l = 90, Z to the north
# pole. The game's galactic x is the opposite of X (the centre is at the origin and the star at +x); y and z are the same.
SUN = np.array([-INITIAL_STAR_POSITION[0], INITIAL_STAR_POSITION[1], INITIAL_STAR_POSITION[2]]) * KPC_PER_LY
SUN_RADIUS = float(np.hypot(SUN[0], SUN[1]))

BAND_MAG = 21.7  # the median of the band along the plane (|b| under BAND_LATITUDE), V mag/arcsec2
BAND_LATITUDE = 3.0  # degrees
REFERENCE_MAG = 19.5  # the surface brightness that is 255 in the picture
GAMMA = 2.2
SCATTER = 0.012  # share of the light a dust lane still shows (scattered), so lanes are not pitch black
SCATTER_EXTINCTION = 0.1  # the scattered light is dimmed by this share of the dust in front: deep dust (the centre) stays dark


def luminance(mag_per_arcsec2):
    """cd/m2 of a surface brightness in V mag/arcsec2."""
    return 1.08e5 * 10.0 ** (-0.4 * np.asarray(mag_per_arcsec2, dtype=np.float64))


# ---- the stars ----

DISC_SCALE_LENGTH = 2.0
DISC_SCALE_HEIGHT = 0.22
ARM_SCALE_HEIGHT = 0.12  # young stars: thinner
THICK_DISC = (0.015, 2.3, 0.9)  # weight, scale length, scale height
BULGE_WEIGHT = 1.0  # relative to the disc's density at the centre: the bulge then has about 0.6 of the disc's light
BULGE_AXES = (1.25, 0.55, 0.40)  # kpc, along the bar, across it, up
BAR_ANGLE = math.radians(27.0)  # from the Sun-centre line, the near end towards positive l
BAR = (0.8, 3.0, 0.8, 0.2)  # weight, half-length, half-width, scale height

# Colours as RGB weights, scaled to have a luminance of 1: old stars warm, the bulge yellower, young stars in the arms bluer.
def _colour(r: float, g: float, b: float) -> np.ndarray:
    return np.array([r, g, b]) / (0.2126 * r + 0.7152 * g + 0.0722 * b)


COLOUR_OLD = _colour(1.10, 0.98, 0.85)
COLOUR_BULGE = _colour(1.30, 0.97, 0.62)
COLOUR_ARM = _colour(0.95, 1.00, 1.15)

# Spiral arms: name, azimuth of the kink (degrees, from the Sun's direction, growing with the galactic rotation), radius at
# the kink, pitch angle inside and outside the kink (degrees), width, strength. The arm is a logarithmic spiral
# R = R_kink exp(-(beta - beta_kink) tan(pitch)), continued over the azimuths in BETA_RANGE_PAD. Approximate, after Reid et al. 2019.
ARMS = (
    ('Norma-Outer', 18.0, 4.46, -1.0, 19.5, 0.30, 1.8, (5.0, 54.0)),
    ('Scutum-Centaurus', 23.0, 4.91, 14.1, 12.1, 0.30, 2.6, (0.0, 104.0)),
    ('Sagittarius-Carina', 24.0, 6.04, 17.1, 1.0, 0.30, 2.6, (2.0, 97.0)),
    ('Local', 9.0, 8.26, 11.4, 11.4, 0.31, 0.5, (-8.0, 34.0)),
    ('Perseus', 40.0, 8.87, 10.3, 8.7, 0.35, 1.2, (-23.0, 115.0)),
    ('Outer', 18.0, 12.24, 3.0, 9.4, 0.65, 0.5, (-16.0, 71.0)),
)
BETA_PAD = (75.0, 25.0)  # degrees: the arm continues this far below and above the measured range
BETA_FADE = 25.0  # degrees over which the continued arm fades out
ARM_GRID_EXTENT = 20.0
ARM_GRID_STEP = 0.04

# ---- the dust ----

DUST_KAPPA = 0.38  # optical depth per kpc in V, in the plane at the Sun's distance from the centre (outside the arms)
DUST_SCALE_LENGTH = 3.0
DUST_SCALE_HEIGHT = 0.11
DUST_ARM_BOOST = 0.7
EXTINCTION = np.array([0.78, 1.0, 1.32])  # R, G, B relative to V
CLUMP_SCALES = ((0.30, 0.9), (0.07, 0.7))  # kpc, sigma of the logarithm
LATTICE = 128

# Real dust clouds near the Sun: name, l, b (degrees), distance (kpc), size (kpc, sigma), V extinction through the centre (mag).
CLOUDS = (
    ('Ophiuchus', 353.0, 16.5, 0.139, 0.008, 3.0),
    ('Pipe', 0.0, 5.0, 0.130, 0.006, 3.0),
    ('Aquila Rift', 8.0, 1.0, 0.250, 0.008, 2.5),
    ('Aquila Rift', 14.0, 2.0, 0.230, 0.008, 3.0),
    ('Aquila Rift', 20.0, 2.5, 0.225, 0.009, 3.0),
    ('Aquila Rift', 27.0, 3.5, 0.225, 0.010, 3.0),
    ('Aquila Rift', 34.0, 2.5, 0.300, 0.010, 2.5),
    ('Serpens', 32.0, 5.5, 0.436, 0.014, 1.8),
    ('Coalsack', 301.0, -2.0, 0.180, 0.008, 3.0),
    ('Chamaeleon', 297.0, -15.0, 0.170, 0.009, 1.5),
    ('Taurus', 173.0, -15.0, 0.140, 0.010, 1.5),
    ('Perseus clouds', 160.0, -18.0, 0.290, 0.012, 1.5),
    ('Orion', 209.0, -19.0, 0.400, 0.025, 1.5),
    ('Cepheus Flare', 110.0, 15.0, 0.300, 0.020, 1.2),
    ('Cygnus Rift', 80.0, 0.0, 0.800, 0.080, 2.5),
    ('Cygnus Rift', 70.0, 0.0, 0.600, 0.060, 2.0),
)

# ---- the objects ----

# Equatorial (J2000) to galactic.
M_EQ_TO_GAL = np.array([
    [-0.0548755604, -0.8734370902, -0.4838350155],
    [+0.4941094279, -0.4448296300, +0.7469822445],
    [-0.8676661490, -0.1980763734, +0.4559837762],
])
# name, RA and Dec (degrees), total V magnitude, colour, and the components of its light:
# (share of the light, 'exp' or 'gauss', scale or sigma along the major axis (degrees), axis ratio, position angle (degrees, north through east)).
OBJECTS = (
    ('Andromeda', 10.6847, 41.2692, 3.44, (1.04, 1.0, 0.92),
     ((0.75, 'exp', 0.40, 0.30, 38.0), (0.25, 'gauss', 0.12, 0.80, 38.0))),
    ('Large Magellanic Cloud', 80.894, -69.756, 0.4, (0.97, 1.0, 1.03),
     ((0.70, 'exp', 1.60, 0.85, 150.0), (0.30, 'gauss', 1.30, 0.31, 120.0))),
    ('Small Magellanic Cloud', 13.187, -72.829, 2.2, (0.97, 1.0, 1.03),
     ((0.70, 'exp', 0.65, 0.55, 45.0), (0.30, 'gauss', 0.45, 0.50, 45.0))),
)

# Steps along a sight line (kpc): fine near the Sun, where the dust clouds are.
STEP_EDGES = np.concatenate([np.arange(0.0, 1.5, 0.03), np.arange(1.5, 6.0, 0.1), np.arange(6.0, 22.01, 0.25)])


def sight_lines(width: int, height: int) -> Tuple[np.ndarray, np.ndarray]:
    """Galactic longitude (centred on 0, radians) of each column and latitude of each row."""
    longitude = np.radians((np.arange(width) + 0.5) / width * 360.0 - 180.0)
    latitude = np.radians(90.0 - (np.arange(height) + 0.5) / height * 180.0)
    return longitude, latitude


def unit_vectors(longitude: np.ndarray, latitude: np.ndarray) -> np.ndarray:
    """(n, 3) galactic unit vectors (X, Y, Z) for the grid of longitudes and latitudes, row by row."""
    l, b = np.meshgrid(longitude, latitude)
    return np.stack([np.cos(b) * np.cos(l), np.cos(b) * np.sin(l), np.sin(b)], axis=-1).reshape(-1, 3)


# ---- noise ----

def make_lattice(seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(LATTICE ** 3).astype(np.float32)


def noise3(lattice: np.ndarray, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Smooth 3D noise (trilinear, smoothed) of the coordinates, in lattice units. The lattice repeats every LATTICE units."""
    x0, y0, z0 = np.floor(x), np.floor(y), np.floor(z)
    fx, fy, fz = (c - c0 for c, c0 in ((x, x0), (y, y0), (z, z0)))
    fx, fy, fz = (f * f * (3.0 - 2.0 * f) for f in (fx, fy, fz))
    i0, j0, k0 = (c0.astype(np.int32) % LATTICE for c0 in (x0, y0, z0))
    i1, j1, k1 = (i0 + 1) % LATTICE, (j0 + 1) % LATTICE, (k0 + 1) % LATTICE

    def at(i, j, k):
        return lattice[(i * LATTICE + j) * LATTICE + k]

    c00 = at(i0, j0, k0) * (1 - fx) + at(i1, j0, k0) * fx
    c10 = at(i0, j1, k0) * (1 - fx) + at(i1, j1, k0) * fx
    c01 = at(i0, j0, k1) * (1 - fx) + at(i1, j0, k1) * fx
    c11 = at(i0, j1, k1) * (1 - fx) + at(i1, j1, k1) * fx
    return (c00 * (1 - fy) + c10 * fy) * (1 - fz) + (c01 * (1 - fy) + c11 * fy) * fz


# ---- the spiral arms, on a map of the plane ----

def arm_maps() -> Tuple[np.ndarray, np.ndarray]:
    """The arms' contribution to the stars and to the dust, on a grid of the plane (X, Y), which the sight lines look up."""
    axis = np.arange(-ARM_GRID_EXTENT, ARM_GRID_EXTENT, ARM_GRID_STEP)
    x, y = np.meshgrid(axis, axis, indexing='ij')
    radius = np.hypot(x, y)
    beta = np.degrees(np.arctan2(y, -x))  # X = -R cos(beta), Y = R sin(beta): beta is 0 towards the Sun, grows with the rotation
    stars = np.zeros_like(radius)
    dust = np.zeros_like(radius)
    for _, beta_kink, radius_kink, pitch_in, pitch_out, width, strength, (beta_min, beta_max) in ARMS:
        low, high = beta_min - BETA_PAD[0], beta_max + BETA_PAD[1]
        pitch = np.radians(np.where(beta < beta_kink, pitch_in, pitch_out))
        ridge = radius_kink * np.exp(-np.radians(beta - beta_kink) * np.tan(pitch))
        across = (radius - ridge) * np.cos(pitch)
        taper = np.clip(np.minimum(beta - low, high - beta) / BETA_FADE, 0.0, 1.0)
        stars += strength * taper * np.exp(-0.5 * (across / width) ** 2)
        dust += strength * taper * np.exp(-0.5 * (across / (0.8 * width)) ** 2)
    return stars.astype(np.float32), dust.astype(np.float32)


def look_up(grid: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    size = grid.shape[0]
    i = np.clip(((x + ARM_GRID_EXTENT) / ARM_GRID_STEP).astype(np.int32), 0, size - 1)
    j = np.clip(((y + ARM_GRID_EXTENT) / ARM_GRID_STEP).astype(np.int32), 0, size - 1)
    return grid[i, j]


# ---- the light along the sight lines ----

def cloud_vectors() -> List[Tuple[np.ndarray, float, float]]:
    """(centre in kpc, sigma, optical depth through the centre) for every real dust cloud."""
    clouds = []
    for _, l, b, distance, sigma, extinction_v in CLOUDS:
        l, b = math.radians(l), math.radians(b)
        direction = np.array([math.cos(b) * math.cos(l), math.cos(b) * math.sin(l), math.sin(b)])
        clouds.append((SUN + distance * direction, sigma, extinction_v / 1.086))
    return clouds


def integrate(directions: np.ndarray, arms: Tuple[np.ndarray, np.ndarray], lattice: np.ndarray, clouds) -> np.ndarray:
    """(n, 3) linear RGB light along each sight line: the stars' light dimmed by the dust in front of it."""
    arm_stars, arm_dust = arms
    count = directions.shape[0]
    dx, dy, dz = (directions[:, k].astype(np.float32) for k in range(3))
    light = np.zeros((3, count), np.float32)
    free = np.zeros(count, np.float32)
    tau = np.zeros(count, np.float32)  # optical depth in V so far
    cos_bar, sin_bar = math.cos(BAR_ANGLE), math.sin(BAR_ANGLE)
    # Python floats, not NumPy scalars: a NumPy float64 scalar would make the float32 arrays float64.
    sun_x, sun_y, sun_z = (float(c) for c in SUN)
    extinction = [float(c) for c in EXTINCTION]
    colour_old, colour_arm, colour_bulge = ([float(c) for c in colour] for colour in (COLOUR_OLD, COLOUR_ARM, COLOUR_BULGE))
    edges = STEP_EDGES.tolist()

    for s0, s1 in zip(edges[:-1], edges[1:]):
        s, ds = 0.5 * (s0 + s1), s1 - s0
        x, y, z = sun_x + s * dx, sun_y + s * dy, sun_z + s * dz
        radius = np.maximum(np.hypot(x, y), 0.3)
        height = np.abs(z)
        arm_s = look_up(arm_stars, x, y)

        disc = np.exp(-radius / DISC_SCALE_LENGTH - height / DISC_SCALE_HEIGHT)
        thick = THICK_DISC[0] * np.exp(-radius / THICK_DISC[1] - height / THICK_DISC[2])
        young = np.exp(-radius / DISC_SCALE_LENGTH - height / ARM_SCALE_HEIGHT) * arm_s
        along = -x * cos_bar + y * sin_bar  # along the bar, the near end towards the Sun at positive l
        across = x * sin_bar + y * cos_bar
        bulge = BULGE_WEIGHT * np.exp(-np.sqrt((along / BULGE_AXES[0]) ** 2 + (across / BULGE_AXES[1]) ** 2 + (height / BULGE_AXES[2]) ** 2))
        bulge += BAR[0] * np.exp(-np.sqrt((along / BAR[1]) ** 2 + (across / BAR[2]) ** 2)) * np.exp(-height / BAR[3])
        old = disc + thick

        # The dust: a disc that follows the arms, in clumps.
        coarse = noise3(lattice, x / CLUMP_SCALES[0][0], y / CLUMP_SCALES[0][0], z / CLUMP_SCALES[0][0] + 31.0)
        fine = noise3(lattice, x / CLUMP_SCALES[1][0] + 53.0, y / CLUMP_SCALES[1][0], z / CLUMP_SCALES[1][0] + 7.0)
        clump = np.exp(CLUMP_SCALES[0][1] * coarse + CLUMP_SCALES[1][1] * fine - 0.5 * (CLUMP_SCALES[0][1] ** 2 + CLUMP_SCALES[1][1] ** 2) * 0.5)
        kappa = (DUST_KAPPA * np.exp(-(radius - SUN_RADIUS) / DUST_SCALE_LENGTH) * np.exp(-height / DUST_SCALE_HEIGHT)
                 * (1.0 + DUST_ARM_BOOST * look_up(arm_dust, x, y)) * clump)
        if s < 1.7:
            position = np.stack([x, y, z], axis=-1)
            detail = noise3(lattice, x / 0.010 + 11.0, y / 0.010 + 3.0, z / 0.010 + 19.0)  # as fine as the clouds are small
            ragged = np.exp(1.1 * detail + 0.5 * fine + 0.3 * coarse - 0.5)  # real clouds are filaments, not discs
            for centre, sigma, depth in clouds:
                squared = ((position - centre.astype(np.float32)) ** 2).sum(axis=-1)
                kappa += depth / (sigma * math.sqrt(2.0 * math.pi)) * np.exp(-0.5 * squared / sigma ** 2) * ragged

        tau_middle = tau + 0.5 * kappa * ds
        for channel in range(3):
            emitted = old * colour_old[channel] + young * colour_arm[channel] + bulge * colour_bulge[channel]
            light[channel] += emitted * np.exp(-extinction[channel] * tau_middle) * ds
        free += (old + young + bulge) * np.exp(-SCATTER_EXTINCTION * tau_middle) * ds
        tau += kappa * ds

    return (light + SCATTER * free).T


# ---- the objects ----

def object_luminance(directions: np.ndarray, ra: float, dec: float, magnitude: float, components) -> np.ndarray:
    """cd/m2 of one object at each direction: exponential or gaussian components, with a total light of `magnitude`."""
    ra, dec = math.radians(ra), math.radians(dec)
    centre = M_EQ_TO_GAL @ np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)])
    l0, b0 = math.atan2(centre[1], centre[0]), math.asin(centre[2])
    east = np.array([-math.sin(l0), math.cos(l0), 0.0])
    north = np.array([-math.sin(b0) * math.cos(l0), -math.sin(b0) * math.sin(l0), math.cos(b0)])
    equatorial_north = np.array([-math.sin(dec) * math.cos(ra), -math.sin(dec) * math.sin(ra), math.cos(dec)])
    equatorial_east = np.array([-math.sin(ra), math.cos(ra), 0.0])

    cosine = directions @ centre
    near = cosine > math.cos(math.radians(30.0))
    xi = np.degrees((directions[near] @ east) / cosine[near])  # the tangent plane at the object, degrees
    eta = np.degrees((directions[near] @ north) / cosine[near])
    result = np.zeros(directions.shape[0])
    for share, shape, scale, ratio, angle in components:
        axis = M_EQ_TO_GAL @ (math.cos(math.radians(angle)) * equatorial_north + math.sin(math.radians(angle)) * equatorial_east)
        a1, a2 = axis @ east, axis @ north
        norm = math.hypot(a1, a2)
        a1, a2 = a1 / norm, a2 / norm
        along = (xi * a1 + eta * a2) / scale
        across = (-xi * a2 + eta * a1) / (scale * ratio)
        radius = np.hypot(along, across)
        profile = np.exp(-radius) if shape == 'exp' else np.exp(-0.5 * radius ** 2)
        area = 2.0 * math.pi * (scale * 3600.0) ** 2 * ratio  # arcsec2, of the profile's centre value
        centre_flux = share * 10.0 ** (-0.4 * magnitude) / area
        result[near] += luminance(-2.5 * math.log10(centre_flux)) * profile
    return result


# ---- the picture ----

def resize(image: np.ndarray, height: int, width: int) -> np.ndarray:
    """Bilinear resize of a (h, w) or (h, w, c) array."""
    def axis_weights(old: int, new: int):
        position = np.clip((np.arange(new) + 0.5) * old / new - 0.5, 0, old - 1)
        low = np.floor(position).astype(int)
        high = np.minimum(low + 1, old - 1)
        return low, high, (position - low).astype(np.float32)

    rows = axis_weights(image.shape[0], height)
    columns = axis_weights(image.shape[1], width)
    fraction = rows[2].reshape((-1,) + (1,) * (image.ndim - 1))
    vertical = image[rows[0]] * (1 - fraction) + image[rows[1]] * fraction
    fraction = columns[2].reshape((1, -1) + (1,) * (image.ndim - 2))
    return vertical[:, columns[0]] * (1 - fraction) + vertical[:, columns[1]] * fraction


def fine_detail(shape: Tuple[int, int], brightness: np.ndarray) -> np.ndarray:
    """A multiplier with fine structure (patchy light, small dust), stronger where the light is stronger."""
    rng = np.random.default_rng(2024)
    height, width = shape
    noise = np.zeros(shape, np.float32)
    for cells, weight in ((64, 0.35), (160, 0.30), (400, 0.20), (1000, 0.15)):
        noise += weight * resize(rng.standard_normal((cells // 2, cells)).astype(np.float32), height, width)
    noise /= noise.std()
    amplitude = 0.05 + 0.27 * np.clip(brightness / 0.25, 0.0, 1.0)
    return np.exp(amplitude * noise - 0.5 * amplitude ** 2)


def build(model_width: int) -> np.ndarray:
    """The panorama as an (h, w, 3) uint8 array."""
    model_height = model_width // 2
    width, height = model_width * 2, model_height * 2
    started = time.time()

    longitude, latitude = sight_lines(model_width, model_height)
    directions = unit_vectors(longitude, latitude)
    arms = arm_maps()
    lattice = make_lattice(7)
    clouds = cloud_vectors()

    light = np.zeros((directions.shape[0], 3), np.float32)
    chunk = 200000
    for start in range(0, directions.shape[0], chunk):
        light[start:start + chunk] = integrate(directions[start:start + chunk], arms, lattice, clouds)
        print(f'  sight lines {min(start + chunk, directions.shape[0])} of {directions.shape[0]}  ({time.time() - started:.0f} s)', flush=True)

    # Physical scale: the median of the band along the plane is BAND_MAG.
    luminosity = (light @ np.array([0.2126, 0.7152, 0.0722], np.float32)).reshape(model_height, model_width)
    in_band = np.abs(np.degrees(latitude)) < BAND_LATITUDE
    light *= float(luminance(BAND_MAG) / np.median(luminosity[in_band]))
    light = resize(light.reshape(model_height, model_width, 3), height, width)  # cd/m2, linear RGB

    reference = float(luminance(REFERENCE_MAG))
    relative = light.sum(axis=-1) / 3.0 / reference
    light *= fine_detail((height, width), relative)[..., None]

    longitude, latitude = sight_lines(width, height)
    full_directions = unit_vectors(longitude, latitude)
    for name, ra, dec, magnitude, colour, components in OBJECTS:
        added = object_luminance(full_directions, ra, dec, magnitude, components).reshape(height, width)
        light += added[..., None] * np.array(colour, np.float32)
        print(f'  {name}: peak {added.max():.2e} cd/m2 (V {-2.5 * math.log10(added.max() / 1.08e5) / 1.0:.1f} mag/arcsec2)')

    picture = 255.0 * np.clip(light / reference, 0.0, 1.0) ** (1.0 / GAMMA)
    report(light, reference, longitude, latitude)
    return np.round(picture).astype(np.uint8)


def report(light: np.ndarray, reference: float, longitude: np.ndarray, latitude: np.ndarray) -> None:
    """Surface brightness (V mag/arcsec2) at some sight lines, to check the picture against the real sky."""
    luminosity = light @ np.array([0.2126, 0.7152, 0.0722])
    print('  surface brightness, V mag/arcsec2:')
    for label, l, b in (('galactic centre', 0, 0), ('bulge window', 1, -4), ('Scutum cloud', 27, 0), ('Cygnus', 80, 0),
                        ('anticentre', 180, 0), ('Carina', -77, 0), ('Norma', -32, 0), ('l 0, b 30', 0, 30),
                        ('l 0, b 60', 0, 60), ('north pole', 0, 89)):
        column = int(((l + 180.0) % 360.0) / 360.0 * len(longitude)) % len(longitude)
        row = int((90.0 - b) / 180.0 * len(latitude))
        row = min(row, len(latitude) - 1)
        value = luminosity[row, column]
        print(f'    {label:>16} (l {l:4d}, b {b:3d}): {-2.5 * math.log10(max(value, 1e-12) / 1.08e5):5.1f}')


def main() -> None:
    model_width = int(sys.argv[1]) if len(sys.argv) > 1 else 2048
    print(f'Generating the Milky Way, model {model_width} x {model_width // 2}, picture {2 * model_width} x {model_width}')
    picture = build(model_width)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    pygame.image.save(pygame.surfarray.make_surface(picture.swapaxes(0, 1)), OUT_PATH)
    print(f'Wrote {OUT_PATH} ({os.path.getsize(OUT_PATH) / 1e6:.1f} MB). Largest values: {picture.reshape(-1, 3).max(axis=0)}')


if __name__ == '__main__':
    main()
