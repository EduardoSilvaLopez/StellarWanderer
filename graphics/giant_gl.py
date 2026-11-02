"""Gas and ice giants drawn in the OpenGL pass as a ball of gas, not a sphere: a fragment shader marches each pixel's
view ray through the atmosphere, from the outside or from the inside. What the gas does to light comes from the
atmosphere model (`JovianWorld.optical_profile`): the extinction along the ray makes the cloud tops the visible surface
where the gas gets opaque, and below them the sunlight is used up by the column above, so the deeper the ship the
dimmer and the shorter its view, until all is dark. The giants behind the star are drawn before it, the others after the
sky, so the sun covers the first and not the second (see OpenGLGui.draw)."""

from __future__ import annotations
from typing import TYPE_CHECKING, Dict, List, Tuple
import math
import numpy as np
from OpenGL import GL
from galaxies.jovian_world import JovianWorld
from common.vector3 import Vector3
from .constants import (
    WORLD_AMBIENT_LIGHT, WORLD_MIN_RADIUS_PX, MIN_VISIBLE_PX, GIANT_HAZE_TOP, GIANT_SUN_GAIN, GIANT_STEP_DEPTH,
    GIANT_STEP_HEIGHT, GIANT_PIXEL_BUDGET, GIANT_TARGET_SIZE, GIANT_LIMB_DARKENING, GIANT_LIGHT_PENETRATION,
)
from .lit_worlds import LitWorlds

if TYPE_CHECKING:
    from spaceships.ship import Ship
    from game_environment import GameEnvironment

# The table of the gas: its extinction coefficient and the optical depth of the column above, at NODES altitudes spaced
# evenly in s, where altitude = scale height * sinh(s): fine near the cloud tops, and reaching deep with few nodes.
NODES = 64
S_MIN, S_MAX = -10.0, 3.3

VERTEX_SHADER = """
#version 120
void main() {
    gl_Position = gl_Vertex;
}
"""

# Lengths are in metres, in the camera frame (x right, y up, z forward) with the origin at the giant's centre. The
# giant is the ellipsoid of the 1 bar level, and q is how many of its radii a point is from the centre along its own
# direction (q = 1 on it): the altitude is the distance from the centre times (1 - 1/q). The haze reaches q = top_q.
FRAGMENT_SHADER = """
#version 120
const int NODES = 64;
const int MAX_STEPS = 64;
const float HALF_PI = 1.5707963;

// Where a fragment is on the screen: pixel_offset + (fragment x, flip - fragment y) * pixel_scale, in screen pixels
// from the top left. The giant is drawn at the window's resolution, or, when it is big, into a smaller target.
uniform vec2 pixel_offset;
uniform vec2 pixel_scale;
uniform float flip;
uniform vec2 screen;       // window size, pixels
uniform float horizon;     // pixel row of the horizon
uniform float focal;       // focal length, pixels
uniform vec3 camera;       // where the camera is, relative to the centre
uniform vec3 pole;         // spin axis
uniform vec3 light;        // unit vector to the star
uniform float equatorial;  // equatorial radius of the 1 bar level
uniform float polar;       // polar radius of the 1 bar level
uniform float top_q;       // q at the top of the haze
uniform float scale_height;
uniform float s_min;
uniform float s_max;
uniform float log_k[NODES];     // ln of the extinction coefficient (1/m) at each node
uniform float log_tau[NODES];   // ln of the optical depth of the column above
uniform vec3 tint;         // the cloud colour lit by the star, 0..255
uniform float ambient;
uniform float sun_gain;
uniform float limb_darkening;  // how much darker the cloud tops are where they are seen at a slant
uniform float penetration;     // how much of its optical depth the diffuse light feels (it scatters on, deep)
uniform float step_depth;   // the optical depth a step may cover
uniform float step_height;  // the altitude, in scale heights, a step may cover
uniform float band_count;
uniform float band_phase;
uniform float band_contrast;

float inv_a2;
float shape;   // 1 / polar^2 - 1 / equatorial^2

float asinh_(float x) {
    return log(x + sqrt(x * x + 1.0));
}

void gas_at(float altitude, out float extinction, out float column) {
    float s = asinh_(altitude / scale_height);
    float f = clamp((s - s_min) / (s_max - s_min), 0.0, 1.0) * float(NODES - 1);
    int i = int(min(floor(f), float(NODES - 2)));
    float w = f - float(i);
    extinction = exp(mix(log_k[i], log_k[i + 1], w));
    column = exp(mix(log_tau[i], log_tau[i + 1], w));
}

// What the ray u from the camera gathers: the light the gas scatters towards it (premultiplied), and its opacity.
vec4 trace(vec3 u) {
    float pu = dot(pole, u);
    float pc = dot(pole, camera);
    float a = inv_a2 + shape * pu * pu;
    float b = dot(u, camera) * inv_a2 + shape * pu * pc;
    float c = dot(camera, camera) * inv_a2 + shape * pc * pc - top_q * top_q;
    float disc = b * b - a * c;
    if (disc <= 0.0) {
        return vec4(0.0);
    }
    float root = sqrt(disc);
    float t = max((-b - root) / a, 0.0);
    float t_end = (-b + root) / a;
    if (t_end <= 0.0) {
        return vec4(0.0);
    }

    float transmission = 1.0;
    vec3 gathered = vec3(0.0);
    for (int march = 0; march < MAX_STEPS; march++) {
        if (t >= t_end || transmission < 0.004) {
            break;
        }
        vec3 p = camera + u * t;
        float r = max(length(p), 1.0);
        float pp = dot(pole, p);
        float q = sqrt(max(dot(p, p) * inv_a2 + shape * pp * pp, 1e-12));
        float extinction, column;
        gas_at(r * (1.0 - 1.0 / q), extinction, column);

        // The step: a share of an optical depth, and no more than a share of a scale height of altitude.
        float radial = max(abs(dot(p, u)) / r, 0.02);
        float ds = min(step_depth / max(extinction, 1e-12), step_height * scale_height / radial);
        ds = min(max(ds, 0.01 * scale_height), t_end - t);
        float absorbed = 1.0 - exp(-extinction * ds);

        // The sunlight at the step: through the column above it along the slant, and none below the horizon.
        vec3 up = p / r;
        float mu = dot(up, light);
        float sun = smoothstep(-0.02, 0.15, mu) * exp(-penetration * column / max(mu, 0.05));
        float bands = 1.0 + band_contrast * sin(band_count * HALF_PI * dot(pole, up) + band_phase);
        // A single scattering is brighter at a slant, which a cloud deck is not: darken it there, but only where the gas
        // is thick (the thin haze above the limb stays bright).
        float slant = 1.0 - clamp(-dot(up, u), 0.0, 1.0);
        float deck = 1.0 - limb_darkening * slant * (1.0 - exp(-column));
        vec3 source = tint / 255.0 * bands * deck * (sun_gain * sun + ambient * exp(-2.0 * column));

        gathered += transmission * absorbed * source;
        transmission *= 1.0 - absorbed;
        t += ds;
    }
    return vec4(gathered, 1.0 - transmission);
}

void main() {
    inv_a2 = 1.0 / (equatorial * equatorial);
    shape = 1.0 / (polar * polar) - inv_a2;
    vec2 pixel = pixel_offset + vec2(gl_FragCoord.x, flip - gl_FragCoord.y) * pixel_scale;
    vec3 u = normalize(vec3((pixel.x - 0.5 * screen.x) / focal, (horizon - pixel.y) / focal, 1.0));

    // Pixels on the limb of the 1 bar level are traced four times, so its edge is smooth: how far in pixels the ray
    // passes from the limb follows from how far its closest approach is inside the ellipsoid.
    float pu = dot(pole, u);
    float pc = dot(pole, camera);
    float a = inv_a2 + shape * pu * pu;
    float b = dot(u, camera) * inv_a2 + shape * pu * pc;
    float inside = 1.0 - (dot(camera, camera) * inv_a2 + shape * pc * pc - b * b / a);
    float edge_px = 0.5 * inside * equatorial * focal / max(-b / a, 1.0);

    vec4 result;
    if (abs(edge_px) < 1.5) {
        result = vec4(0.0);
        for (int i = 0; i < 4; i++) {
            vec2 offset = vec2(float(i - (i / 2) * 2) - 0.5, float(i / 2) - 0.5) * 0.5 * pixel_scale;
            vec2 sub = pixel + offset;
            result += trace(normalize(vec3((sub.x - 0.5 * screen.x) / focal, (horizon - sub.y) / focal, 1.0)));
        }
        result *= 0.25;
    } else {
        result = trace(u);
    }
    gl_FragColor = vec4(min(result.rgb, vec3(1.0)), result.a);
}
"""


class GiantGl:
    """The giants of the nearest system, drawn as one screen rectangle each, with the shader above."""

    _program: int = 0  # compiled once, the first time a window exists
    _framebuffer: int = 0  # the smaller target of a big giant (see _target), made the first time it is needed
    _texture: int = 0
    _tables: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}  # by the giant's id: ln extinction, ln column depth

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
        if not GiantGl._program:
            program = GL.glCreateProgram()
            GL.glAttachShader(program, GiantGl._compile(GL.GL_VERTEX_SHADER, VERTEX_SHADER))
            GL.glAttachShader(program, GiantGl._compile(GL.GL_FRAGMENT_SHADER, FRAGMENT_SHADER))
            GL.glLinkProgram(program)
            if not GL.glGetProgramiv(program, GL.GL_LINK_STATUS):
                raise RuntimeError(GL.glGetProgramInfoLog(program).decode())
            GiantGl._program = program
        return GiantGl._program

    @staticmethod
    def _table(world: JovianWorld) -> Tuple[np.ndarray, np.ndarray]:
        """What the gas of the giant does to light (see the shader's NODES), worked out once."""
        key = id(world)
        if key not in GiantGl._tables:
            nodes = np.linspace(S_MIN, S_MAX, NODES)
            altitudes = [world.scale_height * math.sinh(s) for s in nodes]
            extinctions, columns = world.optical_profile(altitudes)
            GiantGl._tables[key] = (np.log(np.maximum(extinctions, 1e-30)).astype(np.float32),
                                    np.log(np.maximum(columns, 1e-30)).astype(np.float32))
        return GiantGl._tables[key]

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
        GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)  # the shader's colour is premultiplied by its opacity
        GL.glUseProgram(program)
        for _, world, to_world in sorted(chosen, key=lambda item: item[0], reverse=True):
            GiantGl._draw_one(program, width, height, view_h, horizon_y, focal, world, to_world, to_star, star_color,
                              ship)
        GL.glUseProgram(0)
        GL.glDisable(GL.GL_BLEND)

    @staticmethod
    def _draw_one(program: int, width: int, height: int, view_h: int, horizon_y: int, focal: float,
                  world: JovianWorld, to_world: Vector3, to_star: Vector3, star_color: tuple, ship: Ship) -> None:
        """One giant: where the camera is in its frame, the rectangle of the screen that can show it, and the program
        run over it. Seen from inside the haze the whole view is the rectangle."""
        equatorial = world.equatorial_radius
        polar = world.polar_radius
        distance = to_world.length()
        if 2.0 * equatorial * focal / max(distance, 1.0) < MIN_VISIBLE_PX:
            return
        # A giant too small to see is drawn as a small lit disc: the camera is brought nearer, to a minimum angular size.
        inflation = max(1.0, WORLD_MIN_RADIUS_PX / focal * distance / world.radius)
        camera = ship.attitude.camera_components(to_world) * (-1.0 / inflation)
        light = ship.attitude.camera_components(to_star - to_world).normalized()
        pole = ship.attitude.camera_components(Vector3(0.0, 0.0, 1.0))

        top_q = 1.0 + GIANT_HAZE_TOP * world.scale_height / equatorial
        pole_on_camera = pole.dot(camera)
        q_camera = math.sqrt(camera.dot(camera) / equatorial ** 2
                             + (1.0 / polar ** 2 - 1.0 / equatorial ** 2) * pole_on_camera ** 2)
        if q_camera < top_q:
            x0, y0, x1, y1 = 0, 0, width, view_h
        else:
            camera_distance = camera.length()
            centre = camera * (-1.0 / camera_distance)
            outer_angle = math.asin(min(equatorial * top_q / camera_distance, 0.999))
            max_angle = math.atan(math.hypot(width / 2, max(horizon_y, view_h - horizon_y)) / focal)
            if math.acos(max(-1.0, min(1.0, centre.z))) - outer_angle > max_angle:
                return
            x0, y0, x1, y1 = LitWorlds._screen_box(centre, outer_angle, width, view_h, horizon_y, focal)
            if x1 <= x0 or y1 <= y0:
                return

        def uniform(name: str) -> int:
            return GL.glGetUniformLocation(program, name)

        extinctions, columns = GiantGl._table(world)
        tint = LitWorlds.light_tint(star_color, world.surface_colour)
        GL.glUniform2f(uniform("screen"), width, height)
        GL.glUniform1f(uniform("horizon"), horizon_y)
        GL.glUniform1f(uniform("focal"), focal)
        GL.glUniform3f(uniform("camera"), camera.x, camera.y, camera.z)
        GL.glUniform3f(uniform("pole"), pole.x, pole.y, pole.z)
        GL.glUniform3f(uniform("light"), light.x, light.y, light.z)
        GL.glUniform1f(uniform("equatorial"), equatorial)
        GL.glUniform1f(uniform("polar"), polar)
        GL.glUniform1f(uniform("top_q"), top_q)
        GL.glUniform1f(uniform("scale_height"), world.scale_height)
        GL.glUniform1f(uniform("s_min"), S_MIN)
        GL.glUniform1f(uniform("s_max"), S_MAX)
        GL.glUniform1fv(uniform("log_k"), NODES, extinctions)
        GL.glUniform1fv(uniform("log_tau"), NODES, columns)
        GL.glUniform3f(uniform("tint"), *tint)
        GL.glUniform1f(uniform("ambient"), WORLD_AMBIENT_LIGHT)
        GL.glUniform1f(uniform("sun_gain"), GIANT_SUN_GAIN)
        GL.glUniform1f(uniform("limb_darkening"), GIANT_LIMB_DARKENING)
        GL.glUniform1f(uniform("penetration"), GIANT_LIGHT_PENETRATION)
        GL.glUniform1f(uniform("step_depth"), GIANT_STEP_DEPTH)
        GL.glUniform1f(uniform("step_height"), GIANT_STEP_HEIGHT)
        GL.glUniform1f(uniform("band_count"), world.band_count)
        GL.glUniform1f(uniform("band_phase"), world.band_phase)
        GL.glUniform1f(uniform("band_contrast"), world.band_contrast)

        # The rectangle in normalised device coordinates: the screen's rows run down from the top.
        left, top = 2.0 * x0 / width - 1.0, 1.0 - 2.0 * y0 / height
        right, bottom = 2.0 * x1 / width - 1.0, 1.0 - 2.0 * y1 / height
        box_w, box_h = x1 - x0, y1 - y0
        factor = max(1.0, math.sqrt(box_w * box_h / GIANT_PIXEL_BUDGET), box_w / GIANT_TARGET_SIZE,
                     box_h / GIANT_TARGET_SIZE)
        if factor == 1.0:
            GL.glUniform2f(uniform("pixel_offset"), 0.0, 0.0)
            GL.glUniform2f(uniform("pixel_scale"), 1.0, 1.0)
            GL.glUniform1f(uniform("flip"), height)
            GiantGl._fill(left, top, right, bottom)
            return

        # A big giant: drawn into a smaller target, which fills the rectangle (blended as the program's colour is).
        target_w, target_h = math.ceil(box_w / factor), math.ceil(box_h / factor)
        framebuffer, texture = GiantGl._target()
        viewport = [int(value) for value in GL.glGetIntegerv(GL.GL_VIEWPORT)]
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, framebuffer)
        GL.glViewport(0, 0, target_w, target_h)
        GL.glEnable(GL.GL_SCISSOR_TEST)
        GL.glScissor(0, 0, target_w, target_h)
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        GL.glDisable(GL.GL_SCISSOR_TEST)
        GL.glUniform2f(uniform("pixel_offset"), x0, y0)
        GL.glUniform2f(uniform("pixel_scale"), box_w / target_w, box_h / target_h)
        GL.glUniform1f(uniform("flip"), target_h)
        GiantGl._fill(-1.0, 1.0, 1.0, -1.0)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        GL.glViewport(*viewport)

        GL.glUseProgram(0)
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        GL.glColor4f(1.0, 1.0, 1.0, 1.0)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        u, v = target_w / GIANT_TARGET_SIZE, target_h / GIANT_TARGET_SIZE
        GL.glBegin(GL.GL_QUADS)
        for s, t, x, y in ((0.0, v, left, top), (u, v, right, top), (u, 0.0, right, bottom), (0.0, 0.0, left, bottom)):
            GL.glTexCoord2f(s, t)
            GL.glVertex2f(x, y)
        GL.glEnd()
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glUseProgram(program)

    @staticmethod
    def _fill(left: float, top: float, right: float, bottom: float) -> None:
        """A rectangle in normalised device coordinates, for the program to run over."""
        GL.glBegin(GL.GL_QUADS)
        for x, y in ((left, top), (right, top), (right, bottom), (left, bottom)):
            GL.glVertex2f(x, y)
        GL.glEnd()

    @staticmethod
    def _target() -> Tuple[int, int]:
        """The framebuffer and the texture of the smaller target, made the first time a big giant is drawn."""
        if not GiantGl._framebuffer:
            texture = GL.glGenTextures(1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
            for parameter, value in ((GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR), (GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR),
                                     (GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE),
                                     (GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)):
                GL.glTexParameteri(GL.GL_TEXTURE_2D, parameter, value)
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, GIANT_TARGET_SIZE, GIANT_TARGET_SIZE, 0, GL.GL_RGBA,
                            GL.GL_UNSIGNED_BYTE, None)
            framebuffer = GL.glGenFramebuffers(1)
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, framebuffer)
            GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, texture, 0)
            if GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) != GL.GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError("The target of the giants is not complete.")
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
            GiantGl._framebuffer, GiantGl._texture = framebuffer, texture
        return GiantGl._framebuffer, GiantGl._texture
