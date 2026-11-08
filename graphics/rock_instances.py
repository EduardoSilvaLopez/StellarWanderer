"""The ordinary rocks, drawn as instances of a fixed set of forms kept in the graphics card.

Every rock's mesh used to be worked out and sent again on every frame. Now FORMS shapes (of rock_shape.py, with
FINE_DETAIL subdivisions, so they are rounder than the old ones) are built once, and a rock is only a record: where
it is, its size, its tilt and orientation, its colour and its glow. The shape a rock takes is drawn from its own seed,
and the tilt, orientation and size make two rocks of the same form look different. A Km2's records are one buffer and
its draw is one call (`glMultiDrawArraysIndirect`, one command for each form that is present).

The light is worked out in the shader, from the sun and the shadow map of the ground (shadow_map.py), so no colour is
recomputed on the CPU. The look: a fine grain on the faces (the one of the terrain, from the same functions), the
faces turned down a little darker, and the foot of the rock blended into the colour of the ground (dust).

The rocks with an adjective keep their own meshes (rock_batches.py).
"""

from __future__ import annotations
import ctypes
import math
import weakref
from typing import Dict, List, Optional, Tuple

import numpy as np
from OpenGL import GL

from . import shadow_map
from .constants import SURFACE_STARLIGHT
from .rock_shape import COARSE_DETAIL, FINE_DETAIL, rock_meshes
from .shadow_map import ShadowMap
from .surface_light import SurfaceLight
from .terrain_gl import GRAIN_GLSL

FORMS = 64                  # the shapes in the set
FORM_SEED = 7340011         # the seeds of the shapes: any change gives other rocks everywhere
VISIBLE_TOP_SHARE = 0.1     # a rock's top is kept at least this share of its size above the ground, so it shows
DOWNWARD_DARKENING = 0.18   # faces facing down are darker, up to this share (dust and shadow in the hollows)
TILT_STEP = 0.5             # degrees between the tilts the support tables hold (tilt is at most 45)
CELL = 250.0               # m: a Km2 is drawn in cells of this size, each as fine or as coarse as its distance asks
COARSE_FROM = 300.0        # m: a cell farther than this from the player is drawn with the coarse shapes
DUST_HEIGHT = 0.12         # the share of a rock's size over which its foot is blended into the ground
GRAIN_RANGE = (30.0, 80.0)  # m: the grain of the faces is at full strength to the first, gone at the second

_PLACE_GLSL = """
layout(location = 0) in vec3 a_pos;        // the form's corner, in [-1, 1]
layout(location = 1) in vec3 a_normal;
layout(location = 2) in float a_tone;
layout(location = 3) in vec4 a_place;      // the rock's centre from its Km2's corner (y: height above the datum), size
layout(location = 4) in vec4 a_turn;       // tilt and orientation in radians, the ground's height
layout(location = 5) in vec3 a_colour;     // 0..1
layout(location = 6) in vec3 a_glow;       // 0..1, added after the light
uniform vec3 u_origin;                     // the Km2's corner minus the camera (x, z)
uniform float u_camy;                      // the camera's height (the modelview carries it)
vec3 turned(vec3 v) {                      // tilt about z, then orientation about the vertical (rock_shape.rotate)
    float ct = cos(a_turn.x), st = sin(a_turn.x), co = cos(a_turn.y), so = sin(a_turn.y);
    float x1 = v.x * ct - v.y * st, y1 = v.x * st + v.y * ct;
    return vec3(x1 * co + v.z * so, y1, -x1 * so + v.z * co);
}
"""

_VERTEX_SHADER = """
#version 330 core
""" + _PLACE_GLSL + """
uniform mat4 u_mvp;
out vec3 v_normal;
out vec3 v_colour;
out vec3 v_glow;
out vec3 v_grain;
out vec3 v_cpos;
out float v_depth;
out float v_height;
out float v_dist;
void main() {
    vec3 local = a_pos * (a_place.w * 0.5);
    vec3 world = a_place.xyz + turned(local) + vec3(u_origin.x, 0.0, u_origin.z);
    v_cpos = vec3(world.x, world.y - u_camy, world.z);
    gl_Position = u_mvp * vec4(world, 1.0);
    v_depth = gl_Position.w;
    v_normal = turned(a_normal);
    v_colour = a_colour * a_tone;
    v_glow = a_glow;
    v_height = (world.y - a_turn.z) / a_place.w;
    v_dist = length(world.xz);
    v_grain = local + a_place.xyz;
}
"""

_FRAGMENT_SHADER = """
#version 330 core
in vec3 v_normal;
in vec3 v_colour;
in vec3 v_glow;
in vec3 v_grain;
in vec3 v_cpos;
in float v_depth;
in float v_height;
in float v_dist;
uniform vec3 u_sun;
uniform vec3 u_ground;                     // the colour of the ground, 0..1
uniform float u_starlight;
out vec4 frag;
""" + shadow_map.RECEIVER_GLSL + GRAIN_GLSL + """
void main() {
    vec3 n = normalize(v_normal);
    vec3 bumped = n;
    float strength = 1.0 - smoothstep(@GRAIN_NEAR@, @GRAIN_FAR@, v_dist);
    float grain = 0.5;
    if (strength > 0.0) {
        grain = 0.6 * vnoise(v_grain * 1.5, 1023) + 0.4 * vnoise(v_grain * 4.0, 2047);
        float relief = (grain - 0.5) * 0.2 * strength;    // bump from the derivatives of one noise value, in metres
        vec3 dpdx = dFdx(v_grain), dpdy = dFdy(v_grain);
        vec3 r1 = cross(dpdy, bumped), r2 = cross(bumped, dpdx);
        float det = dot(dpdx, r1);
        vec3 surface = sign(det) * (dFdx(relief) * r1 + dFdy(relief) * r2);
        bumped = normalize(abs(det) * bumped - surface);
    }
    float sun = max(dot(bumped, u_sun), 0.0) * shadow_factor(v_cpos, n, v_depth);
    float brightness = u_starlight + (1.0 - u_starlight) * sun;
    float down = @DOWN@ * (1.0 - (n.y + 1.0) * 0.5);
    vec3 col = v_colour * (1.0 - down) * (1.0 + (grain - 0.5) * 0.5 * strength) * brightness;
    col = mix(col, u_ground * 0.8, (1.0 - smoothstep(0.0, @DUST@, v_height)) * 0.45);
    frag = vec4(min(col + v_glow, vec3(1.0)), 1.0);
}
"""

_SHADOW_VERTEX_SHADER = """
#version 330 core
""" + _PLACE_GLSL + """
uniform mat4 u_light_vp;
void main() {
    vec3 world = a_place.xyz + turned(a_pos * (a_place.w * 0.5)) + vec3(u_origin.x, 0.0, u_origin.z);
    gl_Position = u_light_vp * vec4(world.x, world.y - u_camy, world.z, 1.0);
}
"""

_FRAGMENT = (_FRAGMENT_SHADER.replace("@GRAIN_NEAR@", str(GRAIN_RANGE[0])).replace("@GRAIN_FAR@", str(GRAIN_RANGE[1]))
             .replace("@DOWN@", str(DOWNWARD_DARKENING)).replace("@DUST@", str(DUST_HEIGHT)))
_INSTANCE_FLOATS = 11       # place (4), turn (4), colour (3)


def form_seed(shape_seed: int) -> int:
    """The seed of the form a rock of this `shape_seed` is drawn with (the scanner shows the same shape)."""
    return FORM_SEED + shape_seed % FORMS


class _Forms:
    """The set of shapes, in one buffer, and what settling a rock on the ground needs of each."""

    def __init__(self) -> None:
        seeds = range(FORM_SEED, FORM_SEED + FORMS)
        fine = _vertices_of(seeds, FINE_DETAIL)
        coarse = _vertices_of(seeds, COARSE_DETAIL)
        self.vertex_count = fine.shape[1]
        self.coarse_count = coarse.shape[1]
        self.coarse_first = FORMS * self.vertex_count   # the coarse shapes follow the fine ones in the buffer
        corners = fine[..., 0:3]
        data = np.concatenate([fine.reshape(-1, 7), coarse.reshape(-1, 7)])
        # How low and how high a form reaches once tilted (the orientation, about the vertical, does not change it).
        angles = np.radians(np.arange(0.0, 45.0 + TILT_STEP, TILT_STEP))
        heights = corners[..., 0:1] * np.sin(angles) + corners[..., 1:2] * np.cos(angles)   # (forms, corners, angles)
        self.lowest = heights.min(axis=1)
        self.highest = heights.max(axis=1)
        self.buffer = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.buffer)
        data = np.ascontiguousarray(data, dtype=np.float32)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, data.nbytes, data, GL.GL_STATIC_DRAW)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)


def _vertices_of(seeds, detail: int) -> np.ndarray:
    triangles, normals, tones = rock_meshes(seeds, detail=detail)
    count = triangles.shape[1] * 3
    return np.concatenate([triangles.reshape(len(seeds), count, 3), np.repeat(normals, 3, axis=1),
                           np.repeat(tones, 3, axis=1)[..., None]], axis=2)


def _compile(vertex: str, fragment: str) -> int:
    def shader(kind: int, source: str) -> int:
        handle = GL.glCreateShader(kind)
        GL.glShaderSource(handle, source)
        GL.glCompileShader(handle)
        if not GL.glGetShaderiv(handle, GL.GL_COMPILE_STATUS):
            raise RuntimeError(GL.glGetShaderInfoLog(handle))
        return handle

    program = GL.glCreateProgram()
    GL.glAttachShader(program, shader(GL.GL_VERTEX_SHADER, vertex))
    GL.glAttachShader(program, shader(GL.GL_FRAGMENT_SHADER, fragment))
    GL.glLinkProgram(program)
    if not GL.glGetProgramiv(program, GL.GL_LINK_STATUS):
        raise RuntimeError(GL.glGetProgramInfoLog(program))
    return program


def _delete(vao: int, buffers: Tuple[int, ...]) -> None:
    try:
        GL.glDeleteVertexArrays(1, [vao])
        GL.glDeleteBuffers(len(buffers), list(buffers))
    except Exception:   # the context may be gone at the end of the game
        pass


class InstancedRocks:
    """The ordinary rocks of one Km2 as records in a buffer. Valid while that list of rocks is unchanged
    (see `is_current`)."""

    _forms: Optional[_Forms] = None
    _program = 0
    _shadow_program = 0
    _uniforms: Dict[str, int] = {}
    _shadow_uniforms: Dict[str, int] = {}
    _active_origin = -1          # where the program in use takes the Km2's offset

    @staticmethod
    def _ensure() -> _Forms:
        if InstancedRocks._forms is None:
            InstancedRocks._forms = _Forms()
            InstancedRocks._program = _compile(_VERTEX_SHADER, _FRAGMENT)
            InstancedRocks._shadow_program = _compile(_SHADOW_VERTEX_SHADER, "#version 330 core\nvoid main() {}\n")
            names = ("u_mvp", "u_origin", "u_camy", "u_sun", "u_ground", "u_starlight") + shadow_map.RECEIVER_UNIFORMS
            InstancedRocks._uniforms = {n: GL.glGetUniformLocation(InstancedRocks._program, n) for n in names}
            InstancedRocks._shadow_uniforms = {n: GL.glGetUniformLocation(InstancedRocks._shadow_program, n)
                                               for n in ("u_light_vp", "u_origin", "u_camy")}
        return InstancedRocks._forms

    def __init__(self, km2) -> None:
        forms = self._ensure()
        self.origin_x: int = km2.longitude   # the records are relative to the Km2's corner: small, float32-safe
        self.origin_z: int = km2.latitude
        rocks = [rock for rock in km2.rocks if not rock.adjective]
        form = np.array([form_seed(rock.shape_seed) - FORM_SEED for rock in rocks], dtype=np.int64)
        cells = int(math.ceil(km2.SIZE / CELL))
        cell = np.array([min(int((rock.latitude - self.origin_z) // CELL), cells - 1) * cells
                         + min(int((rock.longitude - self.origin_x) // CELL), cells - 1) for rock in rocks],
                        dtype=np.int64)
        order = np.argsort(cell * FORMS + form, kind="stable")
        self.rocks = tuple(rocks[i] for i in order)   # in the order of the records
        self._source = tuple(rocks)
        count = len(self.rocks)
        if count == 0:
            return

        def column(name: str) -> np.ndarray:
            return np.array([getattr(rock, name) for rock in self.rocks], dtype=np.float64)

        size, tilt, altitude = column("size"), column("tilt"), column("altitude")
        ground = np.array([rock.ground_height for rock in self.rocks], dtype=np.float64)
        # Settled on the flat ground at 0, as the old meshes were: never floating, always showing (see rock_batches.py).
        step = np.clip(np.rint(tilt / TILT_STEP).astype(np.int64), 0, forms.lowest.shape[1] - 1)
        altitude -= np.maximum(0.0, altitude + size / 2.0 * forms.lowest[form, step])
        altitude += np.maximum(0.0, VISIBLE_TOP_SHARE * size - (altitude + size / 2.0 * forms.highest[form, step]))
        records = np.zeros((count, _INSTANCE_FLOATS), dtype=np.float32)
        records[:, 0] = column("longitude") - self.origin_x
        records[:, 1] = altitude + ground
        records[:, 2] = column("latitude") - self.origin_z
        records[:, 3] = size
        records[:, 4] = np.radians(tilt)
        records[:, 5] = np.radians(column("orientation"))
        records[:, 6] = ground
        colours = np.array([rock.initial_color for rock in self.rocks], dtype=np.float64).reshape(count, 3)
        records[:, 8:11] = colours / 255.0
        # One set of commands for each cell and each fineness, kept to be chosen between by distance (see `draw`).
        key = np.sort(cell * FORMS + form)
        form = (key % FORMS).astype(np.int64)
        cell = (key // FORMS).astype(np.int64)
        self._cell_rects = [(self.origin_x + (c % cells) * CELL, self.origin_z + (c // cells) * CELL)
                            for c in range(cells * cells)]
        self._coarse_cells: Optional[Tuple[bool, ...]] = None
        self._command_count = 0
        self._fine: List[np.ndarray] = []
        self._coarse: List[np.ndarray] = []
        for c in range(cells * cells):
            here = np.nonzero(cell == c)[0]
            if not len(here):
                self._fine.append(np.zeros((0, 4), dtype=np.uint32))
                self._coarse.append(np.zeros((0, 4), dtype=np.uint32))
                continue
            present, counts = np.unique(form[here], return_counts=True)
            starts = here[0] + np.concatenate([[0], np.cumsum(counts)[:-1]])
            for kept, first, length in ((self._fine, present * forms.vertex_count, forms.vertex_count),
                                        (self._coarse, forms.coarse_first + present * forms.coarse_count,
                                         forms.coarse_count)):
                kept.append(np.stack([np.full(len(present), length), counts, first, starts],
                                     axis=1).astype(np.uint32))

        self.glow = np.zeros((count, 3), dtype=np.int32)    # the heat glow, added after the light
        self._was_hot: List[bool] = [False] * count
        self._glow_dirty = False
        self.vao = GL.glGenVertexArrays(1)
        self._records, self._glow_buffer, self._command_buffer = GL.glGenBuffers(3)
        GL.glBindVertexArray(self.vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, forms.buffer)
        for location, width, offset in ((0, 3, 0), (1, 3, 12), (2, 1, 24)):
            GL.glEnableVertexAttribArray(location)
            GL.glVertexAttribPointer(location, width, GL.GL_FLOAT, False, 28, ctypes.c_void_p(offset))
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._records)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, records.nbytes, records, GL.GL_STATIC_DRAW)
        for location, width, offset in ((3, 4, 0), (4, 4, 16), (5, 3, 32)):
            GL.glEnableVertexAttribArray(location)
            GL.glVertexAttribPointer(location, width, GL.GL_FLOAT, False, 4 * _INSTANCE_FLOATS, ctypes.c_void_p(offset))
            GL.glVertexAttribDivisor(location, 1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._glow_buffer)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, count * 12, np.zeros((count, 3), dtype=np.float32), GL.GL_DYNAMIC_DRAW)
        GL.glEnableVertexAttribArray(6)
        GL.glVertexAttribPointer(6, 3, GL.GL_FLOAT, False, 12, None)
        GL.glVertexAttribDivisor(6, 1)
        GL.glBindVertexArray(0)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        GL.glBindBuffer(GL.GL_DRAW_INDIRECT_BUFFER, self._command_buffer)
        GL.glBufferData(GL.GL_DRAW_INDIRECT_BUFFER, 4 * 4 * FORMS * cells * cells, None, GL.GL_DYNAMIC_DRAW)
        GL.glBindBuffer(GL.GL_DRAW_INDIRECT_BUFFER, 0)
        weakref.finalize(self, _delete, self.vao, (self._records, self._glow_buffer, self._command_buffer))

    def is_current(self, km2) -> bool:
        """False once a rock has melted away, or has been given an adjective (none are added after creation)."""
        return self._source == tuple(rock for rock in km2.rocks if not rock.adjective)

    def _refresh_glow(self) -> None:
        """The heat glow (rock.color above rock.initial_color). Only rocks that are hot, or were last frame, are looked
        at, so a cold Km2 costs one pass over its rocks and nothing else."""
        for index, rock in enumerate(self.rocks):
            hot = rock.temperature > 0.0
            if hot or self._was_hot[index]:
                glow = [max(0, int(now) - int(start)) for now, start in zip(rock.color, rock.initial_color)]
                if glow != self.glow[index].tolist():
                    self.glow[index] = glow
                    self._glow_dirty = True
                self._was_hot[index] = hot
        if self._glow_dirty:
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._glow_buffer)
            GL.glBufferSubData(GL.GL_ARRAY_BUFFER, 0, self.glow.size * 4, (self.glow / 255.0).astype(np.float32))
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
            self._glow_dirty = False

    # region Drawing
    @staticmethod
    def begin(light: SurfaceLight, mvp: np.ndarray, camera_y: float, shadow: Optional[ShadowMap]) -> None:
        """Starts drawing rocks in the view: the program and what is the same for every Km2."""
        InstancedRocks._ensure()
        u = InstancedRocks._uniforms
        GL.glUseProgram(InstancedRocks._program)
        GL.glUniformMatrix4fv(u["u_mvp"], 1, GL.GL_TRUE, mvp.astype(np.float32))
        GL.glUniform1f(u["u_camy"], camera_y)
        GL.glUniform3f(u["u_sun"], light.sun.x, light.sun.y, light.sun.z)
        GL.glUniform3f(u["u_ground"], *(channel / 255.0 for channel in light.ground_colour()))
        GL.glUniform1f(u["u_starlight"], SURFACE_STARLIGHT)
        if shadow is not None:
            shadow.bind_texture()
        GL.glUniform1i(u["u_shadow"], 1)
        GL.glUniform1i(u["u_cascades"], 0)
        if shadow is not None:
            shadow.set_uniforms(u, True)
        InstancedRocks._active_origin = u["u_origin"]

    @staticmethod
    def begin_cast(light_matrix: np.ndarray, camera_y: float) -> None:
        """Starts drawing rocks into a cascade of the shadow map, with the light's matrix."""
        InstancedRocks._ensure()
        u = InstancedRocks._shadow_uniforms
        GL.glUseProgram(InstancedRocks._shadow_program)
        GL.glUniformMatrix4fv(u["u_light_vp"], 1, GL.GL_TRUE, np.ascontiguousarray(light_matrix, dtype=np.float32))
        GL.glUniform1f(u["u_camy"], camera_y)
        InstancedRocks._active_origin = u["u_origin"]

    @staticmethod
    def end() -> None:
        GL.glUseProgram(0)

    def draw(self, player_x: float, player_z: float) -> None:
        """Draws the Km2's rocks, between `begin` (or `begin_cast`) and `end`. The Km2's offset from the camera is made
        in double precision here, so that only a small number reaches the card."""
        if not self.rocks:
            return
        GL.glUniform3f(InstancedRocks._active_origin, self.origin_x - player_x, 0.0, self.origin_z - player_z)
        GL.glBindVertexArray(self.vao)
        GL.glBindBuffer(GL.GL_DRAW_INDIRECT_BUFFER, self._command_buffer)
        coarse = tuple(math.hypot(max(x - player_x, 0.0, player_x - x - CELL),
                                  max(z - player_z, 0.0, player_z - z - CELL)) > COARSE_FROM
                       for x, z in self._cell_rects)
        if coarse != self._coarse_cells:   # the commands in the buffer are for the cells as they were last drawn
            self._coarse_cells = coarse
            commands = np.concatenate([(c if far else f) for f, c, far in zip(self._fine, self._coarse, coarse)])
            self._command_count = len(commands)
            GL.glBufferSubData(GL.GL_DRAW_INDIRECT_BUFFER, 0, commands.nbytes, commands)
        GL.glMultiDrawArraysIndirect(GL.GL_TRIANGLES, ctypes.c_void_p(0), self._command_count, 0)
        GL.glBindBuffer(GL.GL_DRAW_INDIRECT_BUFFER, 0)
        GL.glBindVertexArray(0)

    def refresh(self) -> None:
        """Before drawing: what changes between frames (the glow)."""
        if self.rocks:
            self._refresh_glow()
    # endregion

