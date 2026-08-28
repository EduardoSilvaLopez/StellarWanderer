"""Stellar Wanderer — first-person cockpit view.

Draws the pilot's-seat view of the player's ship as vector art: the starfield
seen through the canopy, the hull frame around it, and the instrument console.
The panel on the upper right is the ship clock — it starts at
500-01-01 00:00:00 and advances one second per real second.
"""

import math
import random
import pygame

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
ROCK = (112, 112, 112)
ROCK_EDGE = (60, 60, 60)

STAR_COUNT = 260
STAR_SEED = 20270101

# Time compression, in ship-seconds per real second. Keypad +/- steps by 10x.
TIME_SCALE_MIN = 1
TIME_SCALE_MAX = 1_000_000
TIME_SCALE_STEP = 10

# Canopy opening, as fractions of the window. The windshield is a trapezoid
# that flares outward toward the console, which reads as forward perspective.
CANOPY_TOP = 0.055
CANOPY_TOP_INSET = 0.105
CANOPY_BOTTOM_INSET = 0.02
CONSOLE_TOP = 0.66
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


def draw_deep_space(surface, stars, w, h):
    """Space seen through the canopy."""
    view_h = int(h * CONSOLE_TOP)
    surface.fill(SPACE, (0, 0, w, view_h))


def draw_stars(surface, stars, w, h):
    """Stars seen through the canopy."""
    view_h = int(h * CONSOLE_TOP)

    for nx, ny, radius, brightness in stars:
        x = int(nx * w)
        y = int(ny * view_h)

        # Slightly cool tint keeps the stars from looking like flat white dots.
        color = (brightness, brightness, min(255, brightness + 18))
        if radius == 1:
            surface.set_at((x, y), color)
        else:
            pygame.draw.circle(surface, color, (x, y), radius)

def draw_world(surface, w, h, environment, player):
    """Planet surface and horizon seen through the canopy."""
    view_h = int(h * CONSOLE_TOP)
    planet_radius = environment.current_world.radius
    observer_radius = planet_radius + player.position.y

    # Perspective projection from a 10 m altitude. The planet is not fitted to the
    # viewport; its screen radius is the projected angular radius seen by the
    # observer. Large planets therefore produce an enormous off-screen circle and a
    # nearly flat horizon, while small planets show visible curvature.
    focal_length_px = (view_h * 0.5) / math.tan(VIEW_VERTICAL_FOV_RADIANS * 0.5)
    angular_radius = math.asin(planet_radius / observer_radius)
    planet_radius_px = focal_length_px * math.tan(angular_radius)

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


def draw_rocks(surface, w, h, environment, player):
    """Draw rocks from the current world chunk as isometric cubes on the surface."""
    view_h = int(h * CONSOLE_TOP)
    
    # Get the current world chunk
    try:
        chunk = player.position.worldChunk
        if not chunk or not hasattr(chunk, 'rocks'):
            return
    except:
        return
    
    # Player position within the Km2
    player_x = player.position.x
    player_z = player.position.z
    player_y = player.position.y
    
    # Planet and observer parameters
    planet_radius = environment.current_world.radius
    observer_radius = planet_radius + player_y
    focal_length_px = (view_h * 0.5) / math.tan(VIEW_VERTICAL_FOV_RADIANS * 0.5)
    
    # Horizon Y position
    horizon_y = int(view_h * 0.52)
    
    # Render each rock
    for rock in chunk.rocks:
        rock_x = rock.x
        rock_z = rock.z
        rock_size = rock.size
        
        # Relative position to player (in world coordinates)
        rel_x = rock_x - player_x
        rel_z = rock_z - player_z
        
        # Distance from player in horizontal plane
        distance = math.sqrt(rel_x**2 + rel_z**2)
        
        # Skip rocks that are too far or behind the player
        if distance > 1000 or rel_z <= 0:
            continue
        
        # Rock sits on the surface at altitude 0
        # When player is above surface (positive altitude), rocks appear lower on screen
        rel_y = player_y  # Negative altitude difference (rock is below observer)
        
        # Calculate screen position using perspective projection
        # Horizontal angle from center
        angle_h = math.atan2(rel_x, rel_z)
        screen_x = w / 2 + focal_length_px * math.tan(angle_h)
        
        # Vertical angle and position
        # Use atan2 with proper signs: rel_y is negative when player is above rock
        angle_v = math.atan2(rel_y, distance)
        screen_y_offset = focal_length_px * math.tan(angle_v)
        
        # Rock's screen Y position (offset from horizon)
        screen_y_base = horizon_y + screen_y_offset
        
        # Angular size of the rock based on its size and distance
        angular_size = math.atan2(rock_size, distance)
        rock_size_px = focal_length_px * angular_size
        
        # Draw the rock as a complete isometric cube with three visible faces
        if rock_size_px > 1:  # Only draw if visible
            # Cube dimensions in screen space
            cube_w = rock_size_px
            cube_h = rock_size_px
            cube_d = rock_size_px / 2.5  # depth offset for isometric effect
            
            # Center of cube base on screen
            center_x = screen_x
            base_y = screen_y_base
            
            # Front face corners (the square facing camera)
            # Bottom edge sits at base_y
            front_bl = (center_x - cube_w / 2, base_y)
            front_br = (center_x + cube_w / 2, base_y)
            front_tr = (center_x + cube_w / 2, base_y - cube_h)
            front_tl = (center_x - cube_w / 2, base_y - cube_h)
            
            # Top face corners (receding into distance)
            top_bl = (center_x - cube_w / 2 - cube_d / 2, base_y - cube_h - cube_d / 2)
            top_br = (center_x + cube_w / 2 - cube_d / 2, base_y - cube_h - cube_d / 2)
            top_tr = (center_x + cube_w / 2 + cube_d / 2, base_y - cube_h - cube_d)
            top_tl = (center_x - cube_w / 2 + cube_d / 2, base_y - cube_h - cube_d)
            
            # Right face corners
            right_bl = (center_x + cube_w / 2, base_y)
            right_br = (center_x + cube_w / 2 + cube_d, base_y - cube_d / 2)
            right_tr = (center_x + cube_w / 2 + cube_d, base_y - cube_h - cube_d / 2)
            right_tl = (center_x + cube_w / 2, base_y - cube_h)
            
            # Draw in order: top, right, front (back to front for proper occlusion)
            
            # Top face (darkest)
            top_color = tuple(max(0, c - 50) for c in ROCK)
            pygame.draw.polygon(surface, top_color, [front_tl, front_tr, top_tr, top_tl])
            pygame.draw.lines(surface, ROCK_EDGE, True, [front_tl, front_tr, top_tr, top_tl], 1)
            
            # Right face (medium shade)
            right_color = tuple(max(0, c - 25) for c in ROCK)
            pygame.draw.polygon(surface, right_color, [right_bl, right_br, right_tr, right_tl])
            pygame.draw.lines(surface, ROCK_EDGE, True, [right_bl, right_br, right_tr, right_tl], 1)
            
            # Front face (brightest)
            pygame.draw.polygon(surface, ROCK, [front_bl, front_br, front_tr, front_tl])
            pygame.draw.lines(surface, ROCK_EDGE, True, [front_bl, front_br, front_tr, front_tl], 2)


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


def draw_console(surface, fonts, w, h, environment, player):
    """Instrument panel below the windshield."""
    top = int(h * CONSOLE_TOP)
    height = h - top

    pygame.draw.rect(surface, CONSOLE, (0, top, w, height))
    pygame.draw.line(surface, CONSOLE_EDGE, (0, top), (w, top), 2)
    # Shadowed lip under the windshield, so the console reads as tilted away.
    pygame.draw.rect(surface, HULL_DARK, (0, top + 2, w, max(3, int(height * 0.06))))

    label_font = fonts.get(max(9, int(h * 0.017)))

    # Left cluster: altitude bar and position coordinates.
    cluster_left = int(w * 0.02)
    cluster_top = top + int(height * 0.24)
    cluster_height = int(height * 0.46)
    
    # Altitude bar (vertical level indicator)
    bar_w = int(w * 0.028)
    bar_h = cluster_height
    pygame.draw.rect(surface, READOUT_BG, (cluster_left, cluster_top, bar_w, bar_h))
    
    # Calculate altitude fraction (0-1) based on player position
    # Using the min/max from Player class
    from Player import Player
    max_altitude = Player.MAX_ALTITUDE
    min_altitude = Player.MIN_ALTITUDE
    altitude_range = max_altitude - min_altitude
    altitude_fraction = (player.position.y - min_altitude) / altitude_range
    altitude_fraction = min(1.0, max(0.0, altitude_fraction))
    
    filled = int(bar_h * altitude_fraction)
    pygame.draw.rect(
        surface, ACCENT, (cluster_left, cluster_top + bar_h - filled, bar_w, filled)
    )
    pygame.draw.rect(surface, CONSOLE_EDGE, (cluster_left, cluster_top, bar_w, bar_h), 2)
    
    # Altitude label
    alt_label = label_font.render('ALT', True, ACCENT_DIM)
    surface.blit(alt_label, alt_label.get_rect(midtop=(cluster_left + bar_w // 2, cluster_top - 12)))
    
    # Position coordinates (X and Z) displayed as numbers
    coord_x = cluster_left + bar_w + int(w * 0.035)
    coord_y = cluster_top + int(height * 0.05)
    
    x_text = label_font.render(f'X: {int(player.position.x)}', True, ACCENT)
    z_text = label_font.render(f'Z: {int(player.position.z)}', True, ACCENT)
    
    surface.blit(x_text, (coord_x, coord_y))
    surface.blit(z_text, (coord_x, coord_y + int(height * 0.06)))

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


def draw(surface, fonts, stars, ship_time, environment, player, time_scale=TIME_SCALE_MIN):
    w, h = surface.get_size()
    surface.fill(SPACE)
    draw_deep_space(surface, stars, w, h)
    draw_stars(surface, stars, w, h)
    draw_world(surface, w, h, environment, player)
    draw_rocks(surface, w, h, environment, player)
    draw_canopy(surface, w, h)
    draw_console(surface, fonts, w, h, environment, player)
    draw_ship_clock(surface, fonts, format_ship_time(ship_time), time_scale, w, h)