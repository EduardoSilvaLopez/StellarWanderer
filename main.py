"""Stellar Wanderer — first-person cockpit view.

Draws the pilot's-seat view of the player's ship as vector art: the starfield
seen through the canopy, the hull frame around it, and the instrument console.
The panel on the upper right is the ship clock — it starts at
500-01-01 00:00:00 and advances one second per real second.

Controls:
    Keypad +   compress time 10x further, up to 1 000 000 s/s
    Keypad -   step back down, no slower than 1 s/s
    Esc        quit
"""

import math
import random
from datetime import datetime, timedelta
from shutil import SameFileError

import pygame

from FontCache import FontCache
from Savefile import Savefile
from GameEnvironment import GameEnvironment

WINDOW_TITLE = 'Stellar Wanderer'
WINDOW_SIZE = (1280, 720)
MIN_SIZE = (640, 400)
FPS = 60

# Ship clock. Rendered with an unpadded year so it reads "500-01-01", as spec'd.
EPOCH = datetime(500, 1, 1)

# Time compression, in ship-seconds per real second. Keypad +/- steps by 10x.
TIME_SCALE_MIN = 1
TIME_SCALE_MAX = 1_000_000
TIME_SCALE_STEP = 10
# datetime tops out at year 9999; stop there rather than raising mid-frame.
MAX_ELAPSED = (datetime.max.replace(microsecond=0) - EPOCH).total_seconds()

# Palette
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

STAR_COUNT = 260
STAR_SEED = 20270101

# Canopy opening, as fractions of the window. The windshield is a trapezoid
# that flares outward toward the console, which reads as forward perspective.
CANOPY_TOP = 0.055
CANOPY_TOP_INSET = 0.105
CANOPY_BOTTOM_INSET = 0.02
CONSOLE_TOP = 0.66
VIEW_ALTITUDE_METERS = 10
VIEW_VERTICAL_FOV_RADIANS = math.radians(60)

def make_starfield(count, seed):
    """Stars as (nx, ny, radius, brightness), normalised to the canopy area."""
    rng = random.Random(seed)
    stars = []
    for _ in range(count):
        brightness = rng.randint(70, 255)
        # Bias small: a few bright stars read better than a uniform wash.
        radius = 1 if rng.random() < 0.82 else 2
        stars.append((rng.random(), rng.random(), radius, brightness))
    return stars


def format_ship_time(moment):
    """ISO 8601 layout without zero-padding the year, e.g. '500-01-01 00:00:00'."""
    return (f'{moment.year}-{moment.month:02d}-{moment.day:02d} '
            f'{moment.hour:02d}:{moment.minute:02d}:{moment.second:02d}')


def draw_view(surface, stars, w, h, environment):
    """Space, stars, and the planet horizon seen through the canopy."""
    view_h = int(h * CONSOLE_TOP)
    surface.fill(SPACE, (0, 0, w, view_h))

    planet_radius = environment.planetRadius
    observer_radius = planet_radius + VIEW_ALTITUDE_METERS

    # Perspective projection from a 10 m altitude. The planet is not fitted to the
    # viewport; its screen radius is the projected angular radius seen by the
    # observer. Large planets therefore produce an enormous off-screen circle and a
    # nearly flat horizon, while small planets show visible curvature.
    focal_length_px = (view_h * 0.5) / math.tan(VIEW_VERTICAL_FOV_RADIANS * 0.5)
    angular_radius = math.asin(planet_radius / observer_radius)
    planet_radius_px = focal_length_px * math.tan(angular_radius)
    pixels_per_meter = planet_radius_px / planet_radius

    horizon_y = int(view_h * 0.52)
    planet_center = (w // 2, int(horizon_y + planet_radius_px))

    pygame.draw.circle(
        surface,
        PLANET_GRAY,
        planet_center,
        max(1, int(planet_radius_px)),
    )
    pygame.draw.arc(
        surface,
        PLANET_HORIZON,
        pygame.Rect(
            int(planet_center[0] - planet_radius_px),
            int(planet_center[1] - planet_radius_px),
            int(planet_radius_px * 2),
            int(planet_radius_px * 2),
        ),
        math.pi,
        math.tau,
        2,
    )

    for nx, ny, radius, brightness in stars:
        x = int(nx * w)
        y = int(ny * view_h)

        dx = x - planet_center[0]
        dy = y - planet_center[1]
        if dx * dx + dy * dy <= planet_radius_px * planet_radius_px:
            continue

        # Slightly cool tint keeps the stars from looking like flat white dots.
        color = (brightness, brightness, min(255, brightness + 18))
        if radius == 1:
            surface.set_at((x, y), color)
        else:
            pygame.draw.circle(surface, color, (x, y), radius)

def draw_canopy(surface, w, h):
    """Hull frame: top rail, two A-pillars, and the struts between panes."""
    top = int(h * CANOPY_TOP)
    bottom = int(h * CONSOLE_TOP)
    top_inset = w * CANOPY_TOP_INSET
    bottom_inset = w * CANOPY_BOTTOM_INSET

    # Top rail.
    pygame.draw.rect(surface, HULL, (0, 0, w, top))
    pygame.draw.line(surface, HULL_EDGE, (0, top - 1), (w, top - 1), 2)

    # A-pillars, angling inward as they rise.
    left = [(0, 0), (top_inset, top), (bottom_inset, bottom), (0, bottom)]
    right = [(w, 0), (w - top_inset, top), (w - bottom_inset, bottom), (w, bottom)]
    for pillar in (left, right):
        points = [(int(x), int(y)) for x, y in pillar]
        pygame.draw.polygon(surface, HULL, points)
        pygame.draw.lines(surface, HULL_EDGE, False, points[1:3], 2)

    # Two vertical struts splitting the windshield into three panes.
    for frac in (1 / 3, 2 / 3):
        half = max(2, int(w * 0.004))
        x_top = top_inset + (w - 2 * top_inset) * frac
        x_bottom = bottom_inset + (w - 2 * bottom_inset) * frac
        strut = [
            (int(x_top - half), top), (int(x_top + half), top),
            (int(x_bottom + half), bottom), (int(x_bottom - half), bottom),
        ]
        pygame.draw.polygon(surface, STRUT, strut)
        pygame.draw.line(surface, HULL_EDGE, strut[0], strut[3], 1)


def draw_gauge(surface, center, radius, fraction, color):
    """Round dial with tick marks and a needle at `fraction` of its sweep."""
    pygame.draw.circle(surface, READOUT_BG, center, radius)
    pygame.draw.circle(surface, CONSOLE_EDGE, center, radius, 2)

    start, sweep = math.radians(150), math.radians(240)
    for i in range(9):
        angle = start + sweep * (i / 8)
        inner = radius * (0.72 if i % 2 else 0.62)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        pygame.draw.line(
            surface, ACCENT_DIM,
            (center[0] + cos_a * inner, center[1] + sin_a * inner),
            (center[0] + cos_a * radius * 0.88, center[1] + sin_a * radius * 0.88),
            1,
        )

    angle = start + sweep * fraction
    pygame.draw.line(
        surface, color, center,
        (center[0] + math.cos(angle) * radius * 0.78,
         center[1] + math.sin(angle) * radius * 0.78),
        max(2, radius // 12),
    )
    pygame.draw.circle(surface, CONSOLE_EDGE, center, max(2, radius // 8))


def draw_console(surface, fonts, w, h):
    """Instrument panel below the windshield."""
    top = int(h * CONSOLE_TOP)
    height = h - top

    pygame.draw.rect(surface, CONSOLE, (0, top, w, height))
    pygame.draw.line(surface, CONSOLE_EDGE, (0, top), (w, top), 2)
    # Shadowed lip under the windshield, so the console reads as tilted away.
    pygame.draw.rect(surface, HULL_DARK, (0, top + 2, w, max(3, int(height * 0.06))))

    label_font = fonts.get(max(9, int(h * 0.017)))

    # Left cluster: three dials.
    radius = int(height * 0.20)
    dial_y = top + int(height * 0.42)
    for i, (name, fraction, color) in enumerate((
        ('VEL', 0.42, ACCENT),
        ('HDG', 0.66, ACCENT),
        ('FUEL', 0.28, AMBER),
    )):
        cx = int(w * (0.10 + i * 0.10))
        draw_gauge(surface, (cx, dial_y), radius, fraction, color)
        label = label_font.render(name, True, ACCENT_DIM)
        surface.blit(label, label.get_rect(midtop=(cx, dial_y + radius + 6)))

    # Centre multi-function display.
    mfd = pygame.Rect(0, 0, int(w * 0.24), int(height * 0.56))
    mfd.center = (w // 2, top + int(height * 0.44))
    pygame.draw.rect(surface, READOUT_BG, mfd)
    pygame.draw.rect(surface, CONSOLE_EDGE, mfd, 2)

    nav = fonts.render_to_fit(
        'NAV — NO CONTACT', ACCENT, mfd.width - 12, max(9, int(h * 0.017))
    )
    surface.blit(nav, nav.get_rect(midtop=(mfd.centerx, mfd.top + 5)))

    # Grid sits below the header band so the two never collide.
    grid = mfd.inflate(-8, 0)
    grid.top = mfd.top + nav.get_height() + 9
    grid.height = mfd.bottom - 5 - grid.top
    pygame.draw.line(surface, CONSOLE_EDGE, (grid.left, grid.top - 4),
                     (grid.right, grid.top - 4), 1)
    for i in range(1, 5):
        y = grid.top + grid.height * i // 5
        pygame.draw.line(surface, ACCENT_DIM, (grid.left, y), (grid.right, y), 1)
    for i in range(1, 6):
        x = grid.left + grid.width * i // 6
        pygame.draw.line(surface, ACCENT_DIM, (x, grid.top), (x, grid.bottom), 1)

    # Right cluster: vertical level bars.
    bar_w = int(w * 0.018)
    bar_h = int(height * 0.46)
    bar_top = top + int(height * 0.24)
    for i, level in enumerate((0.72, 0.51, 0.88, 0.34)):
        x = int(w * 0.70 + i * bar_w * 2.1)
        pygame.draw.rect(surface, READOUT_BG, (x, bar_top, bar_w, bar_h))
        filled = int(bar_h * level)
        pygame.draw.rect(
            surface, ACCENT, (x, bar_top + bar_h - filled, bar_w, filled)
        )
        pygame.draw.rect(surface, CONSOLE_EDGE, (x, bar_top, bar_w, bar_h), 1)

    # Indicator lights along the bottom.
    light = max(4, int(height * 0.045))
    for i in range(10):
        x = int(w * 0.06 + i * light * 2.2)
        color = AMBER if i in (3, 7) else ACCENT_DIM
        pygame.draw.rect(surface, color, (x, h - light * 2, light, light))


def format_time_scale(scale):
    """Compression rate as a compact multiplier, e.g. 'x1' or 'x1 000 000'."""
    return f'x{scale:,}'.replace(',', ' ')


def draw_ship_clock(surface, fonts, text, scale, w, h):
    """Clock panel mounted on the upper right of the cockpit."""
    digit_font = fonts.get(max(14, int(h * 0.030)), bold=True)
    label_font = fonts.get(max(9, int(h * 0.016)))

    digits = digit_font.render(text, True, ACCENT)
    label = label_font.render('SHIP TIME', True, ACCENT_DIM)
    # Highlight the rate whenever time is compressed, so the state is obvious.
    rate_color = ACCENT_DIM if scale == TIME_SCALE_MIN else AMBER
    rate = label_font.render(format_time_scale(scale), True, rate_color)

    pad = max(8, int(h * 0.014))
    gap = max(10, int(w * 0.012))
    header_w = label.get_width() + gap + rate.get_width()
    panel = pygame.Rect(
        0, 0,
        max(digits.get_width(), header_w) + pad * 2,
        digits.get_height() + label.get_height() + pad * 2,
    )
    panel.topright = (int(w * 0.975), int(h * 0.075))

    pygame.draw.rect(surface, HULL_DARK, panel.inflate(6, 6))
    pygame.draw.rect(surface, READOUT_BG, panel)
    pygame.draw.rect(surface, CONSOLE_EDGE, panel, 2)

    surface.blit(label, (panel.left + pad, panel.top + pad))
    surface.blit(rate, rate.get_rect(topright=(panel.right - pad, panel.top + pad)))
    surface.blit(digits, (panel.left + pad, panel.top + pad + label.get_height()))


def draw(surface, fonts, stars, ship_time, environment, time_scale=TIME_SCALE_MIN):
    w, h = surface.get_size()
    surface.fill(SPACE)
    draw_view(surface, stars, w, h, environment)
    draw_canopy(surface, w, h)
    draw_console(surface, fonts, w, h)
    draw_ship_clock(surface, fonts, format_ship_time(ship_time), time_scale, w, h)


def main():
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    fonts = FontCache()
    stars = make_starfield(STAR_COUNT, STAR_SEED)
    elapsed = 0.0  # seconds of ship time since EPOCH
    time_scale = TIME_SCALE_MIN

    # Create all seeds and random objects and calculate the initial planet's radius.
    print("Give the galactic Seed: ")
    galacticSeed = 1 # galacticSeed = input()
    ge = GameEnvironment(galacticSeed)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_KP_PLUS:
                    time_scale = min(time_scale * TIME_SCALE_STEP, TIME_SCALE_MAX)
                elif event.key == pygame.K_KP_MINUS:
                    time_scale = max(time_scale // TIME_SCALE_STEP, TIME_SCALE_MIN)
                elif event.key == pygame.K_F5:
                    Savefile.new(ge, EPOCH + timedelta(seconds=elapsed))
                elif event.key == pygame.K_F6:
                    Savefile.load()
            elif event.type == pygame.VIDEORESIZE:
                size = (max(event.w, MIN_SIZE[0]), max(event.h, MIN_SIZE[1]))
                screen = pygame.display.set_mode(size, pygame.RESIZABLE)

        dt = clock.tick(FPS) / 1000.0
        elapsed = min(elapsed + dt * time_scale, MAX_ELAPSED)

        draw(screen, fonts, stars, EPOCH + timedelta(seconds=elapsed), ge, time_scale)
        pygame.display.flip()

    pygame.quit()

if __name__ == '__main__':
    print('Starting game.')
    main()
    print('Ending game.')
