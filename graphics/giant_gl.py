"""Gas and ice giants drawn in the OpenGL pass: a fragment shader intersects each pixel's view ray with the oblate
ellipsoid of the giant, shades it with its bands, and adds the haze at its limb. The giants behind the star are drawn
before it, the others after the sky, so the sun covers the first and not the second (see OpenGLGui.draw)."""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional
import math
from OpenGL import GL
from galaxies.jovian_world import JovianWorld
from common.vector3 import Vector3
from .constants import WORLD_AMBIENT_LIGHT, WORLD_MIN_RADIUS_PX, MIN_VISIBLE_PX, GIANT_HAZE_PIXELS, GIANT_HAZE_ALPHA
from .lit_worlds import LitWorlds

if TYPE_CHECKING:
    from galaxies.world import World
    from spaceships.ship import Ship
    from game_environment import GameEnvironment

VERTEX_SHADER = """
#version 120
void main() {
    gl_Position = gl_Vertex;
}
"""

# The same geometry as the rays of LitWorlds: the ray through pixel (x, y) is (x, y, 1) in the camera frame, and the
# ellipsoid is the quadric (P - C) M (P - C) = 1 with M = I / a^2 + k p p^T, p the spin axis, C the centre.
FRAGMENT_SHADER = """
#version 120
uniform vec2 screen;       // window size, pixels
uniform float horizon;     // pixel row of the horizon
uniform float focal;       // focal length, pixels
uniform vec3 centre;       // unit vector to the centre, camera frame
uniform vec3 pole;         // spin axis, camera frame
uniform vec3 light;        // unit vector to the star, camera frame
uniform float equatorial;  // equatorial semi-axis, in distances
uniform float polar;       // polar semi-axis, in distances
uniform vec3 tint;         // the cloud colour lit by the star, 0..255
uniform float ambient;     // WORLD_AMBIENT_LIGHT
uniform float band_count;
uniform float band_phase;
uniform float band_contrast;
uniform float haze_pixels;
uniform float haze_alpha;

const float HALF_PI = 1.5707963;

void main() {
    float px = gl_FragCoord.x;
    float py = screen.y - gl_FragCoord.y;
    vec3 d = vec3((px - 0.5 * screen.x) / focal, (horizon - py) / focal, 1.0);
    float norm_sq = dot(d, d);

    float a2 = equatorial * equatorial;
    float k = 1.0 / (polar * polar) - 1.0 / a2;
    float pole_on_ray = dot(pole, d);
    float ray_quad = norm_sq / a2 + k * pole_on_ray * pole_on_ray;
    vec3 mc = centre / a2 + k * dot(pole, centre) * pole;
    float ray_mc = dot(d, mc);
    float disc = ray_mc * ray_mc - ray_quad * (dot(centre, mc) - 1.0);
    float along = (ray_mc - sqrt(max(disc, 0.0))) / ray_quad;

    vec3 v = along * d - centre;
    float pv = dot(pole, v);
    vec3 n = v / a2 + k * pv * pole;
    float shade = clamp(dot(n, light) / length(n), 0.0, 1.0);

    float denominator = max(2.0 * equatorial * sqrt(1.0 - a2), 1e-3);
    float inside = disc / ray_quad * a2 / denominator * focal * norm_sq;
    float coverage = clamp(0.5 + inside, 0.0, 1.0) * step(0.0, along);

    float bands = sin(band_count * HALF_PI * pv / length(v) + band_phase);
    float lit = ambient + (1.0 - ambient) * shade;
    vec3 surface = clamp(lit * (1.0 + band_contrast * bands) * tint / 255.0, 0.0, 1.0);

    // Outside the limb the haze fades over haze_pixels, lit by the limb's own normal: only the sunlit edge glows.
    float haze = clamp(1.0 + inside / haze_pixels, 0.0, 1.0) * haze_alpha;
    vec3 u = d / sqrt(norm_sq);
    float towards = dot(u, centre);
    float across = sqrt(max(1.0 - towards * towards, 1e-6));
    float limb_lit = (dot(u, light) - towards * dot(centre, light)) / across;
    vec3 glow = (ambient + (1.0 - ambient) * clamp(limb_lit, 0.0, 1.0)) * tint / 255.0;

    vec3 colour = coverage > 0.0 ? surface : glow;
    gl_FragColor = vec4(colour, max(coverage, haze));
}
"""


class GiantGl:
    """The giants of the nearest system, drawn as one screen rectangle each, with the shader above."""

    _program: Optional[int] = None  # compiled once, the first time a window exists

    @staticmethod
    def _compile(kind: int, source: str) -> int:
        shader = GL.glCreateShader(kind)
        GL.glShaderSource(shader, source)
        GL.glCompileShader(shader)
        if not GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS):
            raise RuntimeError(GL.glGetShaderInfoLog(shader).decode())
        return shader

    @staticmethod
    def _get_program() -> int:
        if GiantGl._program is None:
            program = GL.glCreateProgram()
            GL.glAttachShader(program, GiantGl._compile(GL.GL_VERTEX_SHADER, VERTEX_SHADER))
            GL.glAttachShader(program, GiantGl._compile(GL.GL_FRAGMENT_SHADER, FRAGMENT_SHADER))
            GL.glLinkProgram(program)
            if not GL.glGetProgramiv(program, GL.GL_LINK_STATUS):
                raise RuntimeError(GL.glGetProgramInfoLog(program).decode())
            GiantGl._program = program
        return GiantGl._program

    @staticmethod
    def draw(width: int, height: int, environment: GameEnvironment, ship: Ship, behind_star: bool) -> None:
        """Draws the giants of the nearest system that are behind the star (`behind_star`) or nearer than it, farthest
        first. Called from OpenGLGui.draw, with the depth test off."""
        giants: List[JovianWorld] = [
            world for world in environment.nearest_system.get_all_worlds() if isinstance(world, JovianWorld)
        ]
        if not giants:
            return
        to_star = ship.navigation.direction_to_star(environment.targeted_body, environment.date_time)
        star_distance = to_star.length()
        chosen = []
        for world in giants:
            to_world = ship.navigation.direction_to_body(world, environment.date_time)
            distance = to_world.length()
            if (distance > star_distance) == behind_star:
                chosen.append((distance, world, to_world))
        if not chosen:
            return

        from graphics.instruments.common import view_geometry
        view_h, horizon_y, focal = view_geometry(height)
        star_color = environment.targeted_body.stellar_system.star.color
        program = GiantGl._get_program()
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glUseProgram(program)
        for _, world, to_world in sorted(chosen, key=lambda item: item[0], reverse=True):
            GiantGl._draw_one(program, width, height, view_h, horizon_y, focal, world, to_world, to_star, star_color,
                              ship)
        GL.glUseProgram(0)
        GL.glDisable(GL.GL_BLEND)

    @staticmethod
    def _draw_one(program: int, width: int, height: int, view_h: int, horizon_y: int, focal: float,
                  world: World, to_world: Vector3, to_star: Vector3, star_color: tuple, ship: Ship) -> None:
        """The geometry of one giant on the screen (the same as LitWorlds' for a sphere, with the flattening), then the
        rectangle that holds its disc and its haze, shaded by the program."""
        flattening = world.flattening
        equatorial_radius = world.radius * (1.0 - flattening) ** (-1.0 / 3.0)
        polar_radius = equatorial_radius * (1.0 - flattening)
        distance = to_world.length()
        if distance <= equatorial_radius or 2.0 * equatorial_radius * focal / distance < MIN_VISIBLE_PX:
            return
        centre = ship.attitude.camera_components(to_world) * (1.0 / distance)
        light = ship.attitude.camera_components(to_star - to_world).normalized()
        pole = ship.attitude.camera_components(Vector3(0.0, 0.0, 1.0))

        # A giant too small to see is drawn as a small lit disc: inflated to a minimum angular size, all its axes with it.
        rho = min(max(world.radius / distance, WORLD_MIN_RADIUS_PX / focal), 0.999)
        inflation = rho * distance / world.radius
        a = min(equatorial_radius / distance * inflation, 0.999)
        c = polar_radius / distance * inflation

        haze_angle = GIANT_HAZE_PIXELS / focal
        outer_angle = math.asin(min(a + haze_angle, 0.999))
        max_angle = math.atan(math.hypot(width / 2, max(horizon_y, view_h - horizon_y)) / focal)
        if math.acos(max(-1.0, min(1.0, centre.z))) - outer_angle > max_angle:
            return
        x0, y0, x1, y1 = LitWorlds._screen_box(centre, outer_angle, width, view_h, horizon_y, focal)
        if x1 <= x0 or y1 <= y0:
            return

        tint = LitWorlds.light_tint(star_color, world.surface_colour)
        GL.glUniform2f(GL.glGetUniformLocation(program, "screen"), width, height)
        GL.glUniform1f(GL.glGetUniformLocation(program, "horizon"), horizon_y)
        GL.glUniform1f(GL.glGetUniformLocation(program, "focal"), focal)
        GL.glUniform3f(GL.glGetUniformLocation(program, "centre"), centre.x, centre.y, centre.z)
        GL.glUniform3f(GL.glGetUniformLocation(program, "pole"), pole.x, pole.y, pole.z)
        GL.glUniform3f(GL.glGetUniformLocation(program, "light"), light.x, light.y, light.z)
        GL.glUniform1f(GL.glGetUniformLocation(program, "equatorial"), a)
        GL.glUniform1f(GL.glGetUniformLocation(program, "polar"), c)
        GL.glUniform3f(GL.glGetUniformLocation(program, "tint"), *tint)
        GL.glUniform1f(GL.glGetUniformLocation(program, "ambient"), WORLD_AMBIENT_LIGHT)
        GL.glUniform1f(GL.glGetUniformLocation(program, "band_count"), world.band_count)
        GL.glUniform1f(GL.glGetUniformLocation(program, "band_phase"), world.band_phase)
        GL.glUniform1f(GL.glGetUniformLocation(program, "band_contrast"), world.band_contrast)
        GL.glUniform1f(GL.glGetUniformLocation(program, "haze_pixels"), GIANT_HAZE_PIXELS)
        GL.glUniform1f(GL.glGetUniformLocation(program, "haze_alpha"), GIANT_HAZE_ALPHA)

        # The rectangle in normalised device coordinates: the screen's rows run down from the top.
        def ndc(px: float, py: float) -> tuple:
            return 2.0 * px / width - 1.0, 1.0 - 2.0 * py / height
        GL.glBegin(GL.GL_QUADS)
        for px, py in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            GL.glVertex2f(*ndc(px, py))
        GL.glEnd()
