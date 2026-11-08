"""The ground of a rocky world with relief, drawn in the 3D pass of the surface (see Rocks.draw_view) in place of its
flat square: a quadtree of chunk meshes (terrain_mesh.py), built in helper processes (terrain_helpers.py) and drawn by a
shader that lights them as the game lights everything on the ground (SurfaceLight). All the chunks live in one vertex
buffer, in slots of the same size, and a pass is drawn with one call (an indirect multi-draw: each chunk is one
instance of the same attribute row, which gives its corner), since a call per chunk from Python was the largest cost.

The view is the one the rocks are drawn in: the camera is read from the matrices that Rocks.draw_view has set, and x and
z are relative to the camera, made in double precision, while y is the height above the datum (the modelview carries the
camera's y), as for every object of this pass.

The ground is drawn in two depth ranges, because one depth buffer cannot hold both the rocks at arm's length and the
mountains tens of kilometres away: first the far pass (from the depth where the near pass ends, to FAR_RANGE), then the
depth buffer is cleared and the near pass (up to MAX_DEPTH, the game's limit, with the rocks and everything else of
the surface) is drawn over it. The same leaves of the quadtree serve both: far chunks are coarse and cheap, so the
landmarks show at any distance. Only at the edge of FAR_RANGE does the relief fall to the ground under the camera and
the colour to the flat disc beyond (FixedWorld), too far for the fall to be seen as the ship moves.

A node of the quadtree is split into its four children only when all of them are built, so that what is drawn has no
holes and never falls back more than one level; the missing ones are requested coarsest first, and ahead of time by the
ship's speed (prefetch). Within KEEP_ALL_ROUND the ground is refined all round, so that a turn finds it built. The
choice of chunks is kept while the camera barely moves or turns (the view is widened a little for that), since the
walk over the quadtree is Python. Cached chunks are refreshed while the camera is near them, in view or not. The
lessons are those of the terrain prototype (temp/ideas/terrain_prototype/NOTES.md).

Shadows (shadow_map.py): the ground is both receiver and caster. What casts is chosen apart from what is seen, because a
mountain behind the camera shades the ground in front of it: all the cached chunks within SHADOW_RANGE, coarser with
distance, drawn into the cascades that need it by a vertex-only program that bends the ground as the lit one does.
Other things that cast (rocks, buildings) are drawn into the same cascades by the `casters` the caller gives.
"""

from __future__ import annotations
import ctypes
import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

import numpy as np
from OpenGL import GL

from common.frame_watch import frame_watch
from galaxies.terrain import Terrain
from . import terrain_mesh as mesh
from .constants import MAX_DEPTH, SURFACE_STARLIGHT
from . import shadow_map
from .shadow_map import ShadowMap
from .terrain_helpers import ChunkBuilder

if TYPE_CHECKING:
    from galaxies.km2 import Km2
    from galaxies.world import World
    from spaceships.ship import Ship
    from .surface_light import SurfaceLight

NEAR_RANGE = float(MAX_DEPTH)     # m: the near pass reaches this deep (the rocks and the rest of the surface are there)
DEPTH_OVERLAP = 20.0              # m: the far pass starts this much before the near pass ends, so that no line is left
FAR_RANGE = 300000.0              # m: the ground is drawn this far (about as far as the horizon of a ship at 10 km)
FAR_PLANE = 1.4 * FAR_RANGE       # m: the far pass's clip plane (the chunks reach past FAR_RANGE, and the ship is high)
FALL_START = 0.7 * FAR_RANGE      # m: from here the relief falls to the ground under the camera, gone at FAR_RANGE
HORIZON_MARGIN = 200.0            # m: what a chunk's top may be under the curve and still be drawn
KEEP_ALL_ROUND = 1200.0            # m: within this the ground is refined all round, seen or not (a turn finds it built)
VIEW_PADDING = 1.15               # the view's tangents are widened by this, so that a small turn shows nothing new
REUSE_MOVE = 3.0                  # m: the choice of chunks is kept while the camera has moved less than this
REUSE_TURN = 0.02                 # ... and no element of the view's rotation has changed by more than this (1 degree)
NEAR_SLACK = 1.5                  # the near pass takes the chunks whose gap is under this times its depth
NEAR_ROOTS_NOW = 12000.0          # m: the level-0 chunks within this of the camera are built at once when missing
SPLIT = 2.5                       # a node splits when the camera is nearer than its side times this
PREFETCH = 1.3                    # its children are requested from this many times that, ahead of time
LOOKAHEAD_SECONDS = 0.7           # by the ship's speed: the camera is taken this much closer for that
MAX_NODES = 20000                 # the nodes' data kept between frames
MAX_CHUNKS = 2500                 # cached; about 29 KB each
SLOTS = MAX_CHUNKS + 200          # the shared vertex buffer's slots: the cache, and what is uploaded before an eviction
PASSES = 2 + shadow_map.CASCADES  # the far pass, the near pass and a cascade each: buffers of their own
SHADOW_RANGE = 8000.0             # m: ground this far from the camera can cast a shadow into the view
SHADOW_SPLIT = 1.5                # a caster chunk is split into its children while the camera is nearer than this
                                  # times its side (the shadows need less than the view does)
SHADOW_REMAKE = 30.0              # m: the casters are chosen again after the camera moves this far
SLOT_BYTES = mesh.VERTEX_COUNT * mesh.VERTEX_FLOATS * 4
MAX_UPLOADS_PER_FRAME = 12
MAX_REQUESTS_IN_FLIGHT = 40
SHADOW_SUN_MIN = 0.02             # the sun's height (sine of its elevation) under which there are no shadows to draw
DETAIL_RANGE = (30.0, 80.0)       # m: the close ground's grain is at full strength to the first, gone at the second

VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 a_pos;       // x and z from the chunk's corner, y the height above the datum
layout(location = 1) in vec3 a_normal;
uniform mat4 u_mvp;
layout(location = 2) in vec4 a_chunk;     // per chunk: its corner minus the camera (x, z; the modelview carries y),
                                          // and the corner modulo 1024 m (keeps the grain seamless between chunks)
uniform float u_ground;                   // the height of the ground under the camera
uniform float u_camy;                     // the camera's height (the modelview carries it)
uniform vec2 u_fall;                      // the distance where the relief starts to fall, and where it is gone
uniform vec2 u_curve;                     // the distance where the world's curvature starts to show, and the radius
out vec3 v_normal;
out vec3 v_grain;
out float v_fall;
out float v_dist;
out vec3 v_cpos;                          // where it is, relative to the camera, for the shadows
out float v_depth;
void main() {
    vec3 p = a_pos + vec3(a_chunk.x, 0.0, a_chunk.y);
    float d = length(p.xz);
    float fall = 1.0 - smoothstep(u_fall.x, u_fall.y, d);
    v_grain = vec3(a_pos.x + a_chunk.z, a_pos.y, a_pos.z + a_chunk.w);
    p.y = u_ground + (p.y - u_ground) * fall;
    p.y -= max(d * d - u_curve.x * u_curve.x, 0.0) / (2.0 * u_curve.y);   // the ground curves away below the camera
    gl_Position = u_mvp * vec4(p, 1.0);
    v_normal = mix(vec3(0.0, 1.0, 0.0), a_normal, fall);
    v_fall = fall;
    v_dist = d;
    v_cpos = vec3(p.x, p.y - u_camy, p.z);
    v_depth = gl_Position.w;
}
"""

SHADOW_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 a_pos;
layout(location = 2) in vec4 a_chunk;
uniform mat4 u_light_vp;
uniform float u_camy;
uniform vec2 u_curve;
void main() {
    vec3 p = a_pos + vec3(a_chunk.x, 0.0, a_chunk.y);
    float d = length(p.xz);
    p.y -= max(d * d - u_curve.x * u_curve.x, 0.0) / (2.0 * u_curve.y);   // as the lit ground
    gl_Position = u_light_vp * vec4(p.x, p.y - u_camy, p.z, 1.0);
}
"""

GRAIN_GLSL = """
float cell(ivec3 i, int mask) {
    uvec3 u = uvec3(i & ivec3(mask));
    uint h = (u.x * 374761393u) ^ (u.y * 668265263u) ^ (u.z * 2246822519u);
    h = (h ^ (h >> 15)) * 2246822519u;
    h ^= h >> 13;
    return float(h) * (1.0 / 4294967296.0);
}

float vnoise(vec3 p, int mask) {          // value noise on a lattice that repeats every mask + 1 cells
    vec3 f = floor(p);
    vec3 t = p - f;
    t = t * t * t * (t * (t * 6.0 - 15.0) + 10.0);
    ivec3 i = ivec3(f);
    float a = mix(mix(cell(i, mask), cell(i + ivec3(1, 0, 0), mask), t.x),
                  mix(cell(i + ivec3(0, 1, 0), mask), cell(i + ivec3(1, 1, 0), mask), t.x), t.y);
    float b = mix(mix(cell(i + ivec3(0, 0, 1), mask), cell(i + ivec3(1, 0, 1), mask), t.x),
                  mix(cell(i + ivec3(0, 1, 1), mask), cell(i + ivec3(1, 1, 1), mask), t.x), t.y);
    return mix(a, b, t.z);
}
"""

FRAGMENT_SHADER = """
#version 330 core
in vec3 v_normal;
in vec3 v_grain;
in float v_fall;
in float v_dist;
in vec3 v_cpos;
in float v_depth;
uniform vec3 u_sun;
uniform vec3 u_tint;                      // the world's surface colour times the star's, 0..1
uniform float u_starlight;
uniform vec3 u_far;                       // the colour of the flat ground beyond, 0..1
uniform vec2 u_detail;                    // the distances where the grain starts to fade and is gone
out vec4 frag;

@GRAIN@
void main() {
    vec3 n = normalize(v_normal);
    float strength = 1.0 - smoothstep(u_detail.x, u_detail.y, v_dist);
    float grain = 0.5;
    if (strength > 0.0) {
        grain = 0.65 * vnoise(v_grain, 1023) + 0.35 * vnoise(v_grain * 2.0, 2047);
        // bump mapping from the screen-space derivatives of one noise value: relief in metres, fading with distance
        float relief = (grain - 0.5) * 0.12 * strength;
        vec3 dpdx = dFdx(v_grain), dpdy = dFdy(v_grain);
        vec3 r1 = cross(dpdy, n), r2 = cross(n, dpdx);
        float det = dot(dpdx, r1);
        vec3 surface = sign(det) * (dFdx(relief) * r1 + dFdy(relief) * r2);
        n = normalize(abs(det) * n - surface);
    }
    float sunlit = max(dot(n, u_sun), 0.0) * shadow_factor(v_cpos, normalize(v_normal), v_depth);
    float brightness = u_starlight + (1.0 - u_starlight) * sunlit;
    float steep = 1.0 - smoothstep(0.55, 0.85, normalize(v_normal).y);   // steep ground shows bare, darker rock
    vec3 col = u_tint * brightness * (1.0 + (grain - 0.5) * 0.3 * strength) * (1.0 - 0.25 * steep);
    frag = vec4(mix(u_far, col, v_fall), 1.0);
}
"""

FRAGMENT_SHADER = FRAGMENT_SHADER.replace("out vec4 frag;", "out vec4 frag;\n" + shadow_map.RECEIVER_GLSL, 1)
FRAGMENT_SHADER = FRAGMENT_SHADER.replace("@GRAIN@", GRAIN_GLSL)

Key = mesh.Key


@dataclass
class _Node:
    """What the quadtree needs of a node without its mesh: where it is and how far its mesh can reach."""
    centre_x: float
    centre_z: float
    centre_y: float
    edge: float
    radius: float


class _Chunk:
    __slots__ = ("key", "corner_x", "corner_z", "wrap", "slot", "last_used", "heights", "top", "bottom")

    def __init__(self, key: Key, slot: int, heights: np.ndarray) -> None:
        self.key = key
        self.heights = heights   # the grid's heights (CELLS + 1 a side): where the children's centres are read
        self.top = float(heights.max())   # its highest point, for the horizon test
        self.bottom = float(heights.min())
        self.corner_x, self.corner_z = mesh.chunk_corner(key)
        self.wrap = (self.corner_x % 1024.0, self.corner_z % 1024.0)
        self.slot = slot   # where its vertices are in the shared buffer
        self.last_used = 0


class _Batch:
    """The chunks of one pass, with what the multi-draw needs of them as arrays (made once per choice of chunks)."""
    __slots__ = ("chunks", "corners", "wraps", "commands", "centres", "radii")

    def __init__(self, chunks: List[_Chunk]) -> None:
        self.chunks = chunks
        self.corners = np.array([(c.corner_x, c.corner_z) for c in chunks], dtype=np.float64).reshape(-1, 2)
        self.wraps = np.array([c.wrap for c in chunks], dtype=np.float32).reshape(-1, 2)
        commands = np.zeros((len(chunks), 5), dtype=np.uint32)   # count, instances, first index, base vertex, instance
        commands[:, 0] = mesh.index_buffer().size
        commands[:, 1] = 1
        commands[:, 3] = [c.slot * mesh.VERTEX_COUNT for c in chunks]
        commands[:, 4] = np.arange(len(chunks))
        self.commands = commands
        # a sphere round each chunk (skirt included), in the world, for the shadows' choice of what can cast
        edges = np.array([mesh.chunk_size(c.key[0]) for c in chunks])
        heights = np.array([(c.top + c.bottom) / 2.0 for c in chunks])
        self.centres = np.column_stack([self.corners[:, 0] + edges / 2.0, heights, self.corners[:, 1] + edges / 2.0])
        self.radii = 0.85 * edges + np.array([(c.top - c.bottom) / 2.0 for c in chunks])


class _Renderer:
    """The state of the terrain's drawing: the world it is for, the cache, the shader and the helpers."""

    def __init__(self) -> None:
        self.builder = ChunkBuilder()
        self.program = 0
        self.uniforms: Dict[str, int] = {}
        self.index_buffer = 0
        self.vaos: List[int] = []               # one per pass: its rows and commands have buffers of their own
        self.vertex_buffer = 0                  # every chunk's vertices, SLOTS of VERTEX_COUNT each
        self.instance_buffers: List[int] = []   # the per-chunk rows of each pass
        self.command_buffers: List[int] = []    # the multi-draw commands of each pass
        self.free_slots: List[int] = []
        self.cache: Dict[Key, _Chunk] = {}
        self.nodes: Dict[Key, _Node] = {}
        self.world_seed: Optional[tuple] = None
        self.terrain: Optional[Terrain] = None   # the world's: its heights, and what the helpers are told to build
        self.frame = 0
        self.last_time = 0.0
        self.last_position: Optional[Tuple[float, float]] = None
        self.lookahead = 0.0
        self.camera = (0.0, 0.0, 0.0)
        self.planes: List[Tuple[float, float, float]] = []
        self.holes = 0
        self.horizon = (0.0, 0.0, 1.0)     # the ground under the camera, the distance to the horizon, the radius
        self.unsettled: List[_Node] = []   # this frame's nodes shown coarser than wanted, or not at all
        # The last choice of chunks: the near and far ones, the camera and the rotation it was made for. It is used
        # again until the camera has moved or turned more than REUSE_MOVE or REUSE_TURN, or something has been built.
        self.selection: Optional[Tuple[_Batch, _Batch, Tuple[float, float, float], np.ndarray]] = None
        self.root_keys: List[Key] = []     # the roots in range, as last seen, with the data to test them by
        self.root_data = np.zeros((0, 5))
        self.shadow: Optional[ShadowMap] = None
        self.shadows_active = False             # whether this frame's ground has shadows (and so the map is valid)
        self.shadow_program = 0
        self.shadow_uniforms: Dict[str, int] = {}
        self.casters: Optional[_Batch] = None   # the chunks that can cast (see casters_at)
        self.casters_at = (math.inf, 0.0, 0.0)
        self.casters_stamp = -1                 # how many chunks the cache had then

    # region GL resources
    def _ensure_gl(self) -> None:
        if self.program:
            return
        self.program = self._compile(VERTEX_SHADER, FRAGMENT_SHADER)
        self.uniforms = {name: GL.glGetUniformLocation(self.program, name) for name in
                         ("u_mvp", "u_ground", "u_fall", "u_sun", "u_tint", "u_starlight",
                          "u_far", "u_detail", "u_curve", "u_camy") + shadow_map.RECEIVER_UNIFORMS}
        self.shadow_program = self._compile(SHADOW_VERTEX_SHADER, "#version 330 core\nvoid main() {}\n")
        self.shadow_uniforms = {name: GL.glGetUniformLocation(self.shadow_program, name)
                                for name in ("u_light_vp", "u_camy", "u_curve")}
        self.shadow = ShadowMap()
        indices = mesh.index_buffer()
        self.index_buffer, self.vertex_buffer = GL.glGenBuffers(2)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vertex_buffer)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, SLOTS * SLOT_BYTES, None, GL.GL_DYNAMIC_DRAW)
        for _ in range(PASSES):
            vao = GL.glGenVertexArrays(1)
            instances, commands = GL.glGenBuffers(2)
            GL.glBindVertexArray(vao)
            GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self.index_buffer)
            if not self.vaos:
                GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL.GL_STATIC_DRAW)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vertex_buffer)
            for location, offset in ((0, 0), (1, 12)):
                GL.glEnableVertexAttribArray(location)
                GL.glVertexAttribPointer(location, 3, GL.GL_FLOAT, False, 24, ctypes.c_void_p(offset))
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, instances)
            GL.glBufferData(GL.GL_ARRAY_BUFFER, SLOTS * 16, None, GL.GL_STREAM_DRAW)
            GL.glEnableVertexAttribArray(2)
            GL.glVertexAttribPointer(2, 4, GL.GL_FLOAT, False, 16, None)
            GL.glVertexAttribDivisor(2, 1)
            GL.glBindBuffer(GL.GL_DRAW_INDIRECT_BUFFER, commands)
            GL.glBufferData(GL.GL_DRAW_INDIRECT_BUFFER, SLOTS * 20, None, GL.GL_STREAM_DRAW)
            GL.glBindVertexArray(0)
            self.vaos.append(vao)
            self.instance_buffers.append(instances)
            self.command_buffers.append(commands)
        # The buffers are global state, and a bound vertex buffer turns the pointers of the game's own arrays (the
        # rocks') into offsets: nothing may stay bound.
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, 0)
        GL.glBindBuffer(GL.GL_DRAW_INDIRECT_BUFFER, 0)
        self.free_slots = list(range(SLOTS - 1, -1, -1))

    @staticmethod
    def _compile(vertex_source: str, fragment_source: str) -> int:
        def shader(kind: int, source: str) -> int:
            handle = GL.glCreateShader(kind)
            GL.glShaderSource(handle, source)
            GL.glCompileShader(handle)
            if not GL.glGetShaderiv(handle, GL.GL_COMPILE_STATUS):
                raise RuntimeError(GL.glGetShaderInfoLog(handle))
            return handle

        program = GL.glCreateProgram()
        GL.glAttachShader(program, shader(GL.GL_VERTEX_SHADER, vertex_source))
        GL.glAttachShader(program, shader(GL.GL_FRAGMENT_SHADER, fragment_source))
        GL.glLinkProgram(program)
        if not GL.glGetProgramiv(program, GL.GL_LINK_STATUS):
            raise RuntimeError(GL.glGetProgramInfoLog(program))
        return program

    def _upload(self, key: Key, vertices: np.ndarray) -> None:
        if not self.free_slots:
            return   # every slot is in use this frame; the chunk is asked for again
        slot = self.free_slots.pop()
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vertex_buffer)
        GL.glBufferSubData(GL.GL_ARRAY_BUFFER, slot * SLOT_BYTES, vertices.nbytes, vertices)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        side = mesh.CELLS + 1
        chunk = _Chunk(key, slot, vertices[:side * side, 1].reshape(side, side).copy())
        chunk.last_used = self.frame
        self.cache[key] = chunk

    def _forget_all(self) -> None:
        self.free_slots = list(range(SLOTS - 1, -1, -1))
        self.cache.clear()
        self.nodes.clear()
        self.selection = None
        self.casters = None
        if self.shadow is not None:
            self.shadow.invalidate()
        self.builder.shutdown()

    def _evict(self) -> None:
        if len(self.cache) <= MAX_CHUNKS + 100:
            return
        for chunk in sorted(self.cache.values(), key=lambda c: c.last_used, reverse=True)[MAX_CHUNKS:]:
            if chunk.last_used == self.frame:
                continue
            self.free_slots.append(chunk.slot)
            del self.cache[chunk.key]
    # endregion

    # region The quadtree
    def _node(self, key: Key) -> _Node:
        """A node's centre height is read from its parent's mesh, where the centre is a vertex: working it out from the
        noise, in Python, for every node met while the ship moves fast, was the largest cost of choosing the chunks."""
        node = self.nodes.get(key)
        if node is None:
            level, ix, iz = key
            edge = mesh.chunk_size(level)
            x0, z0 = mesh.chunk_corner(key)
            parent = self.cache.get((level - 1, ix // 2, iz // 2))
            if parent is not None:
                quarter = mesh.CELLS // 4
                height = float(parent.heights[quarter * (1 + 2 * (ix % 2)), quarter * (1 + 2 * (iz % 2))])
            else:
                height = self.terrain.height_for_mesh(x0 + edge / 2.0, z0 + edge / 2.0, edge / mesh.CELLS)
            node = self.nodes[key] = _Node(x0 + edge / 2.0, z0 + edge / 2.0, height, edge, edge * 1.1)
            if len(self.nodes) > MAX_NODES:
                self.nodes.clear()   # they are cheap to make again; the ones kept are only a cache
                self.nodes[key] = node
        return node

    def _behind_horizon(self, chunk: _Chunk, gap: float) -> bool:
        """Whether the world's curvature hides the whole chunk from the camera: past the horizon, a point shows only if
        it rises over the curve by (distance beyond the horizon) squared over twice the radius."""
        ground, horizon, radius = self.horizon
        return gap > horizon and chunk.top - ground + HORIZON_MARGIN < (gap - horizon) ** 2 / (2.0 * radius)

    def _gap(self, node: _Node) -> float:
        """The horizontal distance from the camera to the nearest point of the node (0 when it is over it)."""
        cam_x, _, cam_z = self.camera
        half = node.edge / 2.0
        return math.hypot(max(abs(node.centre_x - cam_x) - half, 0.0), max(abs(node.centre_z - cam_z) - half, 0.0))

    def _visible(self, node: _Node, gap: float) -> bool:
        if gap > FAR_RANGE:
            return False
        cam_x, cam_y, cam_z = self.camera
        wx, wy, wz = node.centre_x - cam_x, node.centre_y - cam_y, node.centre_z - cam_z
        limit = -node.radius
        return all(nx * wx + ny * wy + nz * wz >= limit for nx, ny, nz in self.planes)

    def _select(self, key: Key, out: List[Tuple[_Chunk, float]], requests: List[Tuple[float, Key]]) -> None:
        """The leaves to draw, with their gap, from this node down. A leaf shown coarser than wanted (the finer one
        is still being built) is noted in `unsettled`, as is a hole."""
        node = self._node(key)
        gap = self._gap(node)
        seen = self._visible(node, gap)
        if not seen and gap > KEEP_ALL_ROUND:
            return
        level, ix, iz = key
        own = self.cache.get(key)
        if own is not None:
            own.last_used = self.frame
        cam_x, cam_y, cam_z = self.camera
        dist = math.sqrt((node.centre_x - cam_x) ** 2 + (node.centre_y - cam_y) ** 2 + (node.centre_z - cam_z) ** 2)
        if level < mesh.MAX_LEVEL:
            reach = node.edge * SPLIT
            if dist - self.lookahead < reach * PREFETCH:
                children = [(level + 1, ix * 2 + cx, iz * 2 + cz) for cx in (0, 1) for cz in (0, 1)]
                missing = []
                for child_key in children:
                    child = self.cache.get(child_key)
                    if child is None:
                        missing.append(child_key)
                    else:
                        child.last_used = self.frame   # kept while the camera is near: a split and a merge need it
                urgent = dist < reach
                priority = (0.0 if urgent else 1e11) + (level + 1) * 1e9 + dist   # coarse first, then near
                requests.extend((priority, child_key) for child_key in missing)
                if urgent and not missing:
                    for child_key in children:
                        self._select(child_key, out, requests)
                    return
                if urgent:
                    self.unsettled.append(node)
        if own is not None:
            if seen and not self._behind_horizon(own, gap):
                out.append((own, gap))
        else:
            requests.append((dist, key))
            self.holes += 1
            self.unsettled.append(node)

    def _roots(self) -> List[Key]:
        cam_x, _, cam_z = self.camera
        low_x, high_x = (math.floor((cam_x + sign * FAR_RANGE) / mesh.ROOT_SIZE) for sign in (-1, 1))
        low_z, high_z = (math.floor((cam_z + sign * FAR_RANGE) / mesh.ROOT_SIZE) for sign in (-1, 1))
        return [(0, ix, iz) for ix in range(low_x, high_x + 1) for iz in range(low_z, high_z + 1)]

    def _visible_roots(self, roots: List[Key]) -> List[Key]:
        """The roots that can be seen, all at once with numpy: with over two hundred roots in range, testing each one in
        Python every frame was the largest part of choosing the chunks."""
        if self.root_keys != roots:
            missing = [key for key in roots if key not in self.nodes]
            if missing:   # all at once with numpy: a few hundred of them when the ship crosses into a new row of roots
                corners = np.array([mesh.chunk_corner(key) for key in missing]) + mesh.ROOT_SIZE / 2.0
                heights = self.terrain.heights(corners[:, 0], corners[:, 1])
                for key, (x, z), height in zip(missing, corners.tolist(), heights.tolist()):
                    self.nodes[key] = _Node(x, z, height, mesh.ROOT_SIZE, mesh.ROOT_SIZE * 1.1)
            nodes = [self.nodes[key] for key in roots]
            self.root_keys = roots
            self.root_data = np.array([[n.centre_x, n.centre_y, n.centre_z, n.edge / 2.0, n.radius] for n in nodes])
        data = self.root_data
        cam_x, cam_y, cam_z = self.camera
        gap = np.hypot(np.maximum(np.abs(data[:, 0] - cam_x) - data[:, 3], 0.0),
                       np.maximum(np.abs(data[:, 2] - cam_z) - data[:, 3], 0.0))
        inside = gap <= FAR_RANGE
        relative = data[:, :3] - np.array([cam_x, cam_y, cam_z])
        for plane in self.planes:
            inside &= relative @ np.array(plane) >= -data[:, 4]
        return [roots[index] for index in np.nonzero(inside | (gap <= KEEP_ALL_ROUND))[0]]

    def _build_roots_now(self, roots: List[Key]) -> None:
        """The roots are what everything falls back to: the near ones are built here when missing (a few ms each), at
        the first frame; the far ones are requested from the helpers, and left out until they arrive."""
        cam_x, _, cam_z = self.camera
        for key in roots:
            if key in self.cache:
                self.cache[key].last_used = self.frame
                continue
            x0, z0 = mesh.chunk_corner(key)
            gap = math.hypot(max(x0 - cam_x, 0.0, cam_x - x0 - mesh.ROOT_SIZE),
                             max(z0 - cam_z, 0.0, cam_z - z0 - mesh.ROOT_SIZE))
            if gap < NEAR_ROOTS_NOW:
                self._upload(key, mesh.build_chunk(key, self.terrain.seed, self.terrain.radius, self.terrain.relief,
                                                    self.terrain.platforms))
    # endregion

    # region A frame
    def prepare(self, terrain: Terrain) -> None:
        """For the world whose ground this is: another world has other chunks."""
        if self.world_seed != (terrain.seed, terrain.platforms):   # other graded sites make other meshes
            self._forget_all()
            self.world_seed = (terrain.seed, terrain.platforms)
        self.terrain = terrain
        self._ensure_gl()

    def draw(self, world: World, ship: Ship, light: SurfaceLight, shadows: bool = False,
             casters: Optional[Callable[[ShadowMap, int], None]] = None) -> bool:
        """Draws the ground in the camera the caller has set, with the shadows if asked (`casters` draws what else casts
        into a cascade, between its start and its end); False (nothing drawn) for a world with no relief."""
        self.shadows_active = False
        terrain = getattr(world, "terrain", None)
        if terrain is None or terrain.relief == 0.0:
            return False
        self.prepare(terrain)
        self.frame += 1
        now = time.perf_counter()
        position = (ship.position.x, ship.position.z)
        if self.last_position is not None and now > self.last_time:
            speed = math.dist(position, self.last_position) / (now - self.last_time)
            self.lookahead = min(speed * LOOKAHEAD_SECONDS, 4000.0)
        self.last_position, self.last_time = position, now

        projection = np.asarray(GL.glGetFloatv(GL.GL_PROJECTION_MATRIX), dtype=np.float64).T
        modelview = np.asarray(GL.glGetFloatv(GL.GL_MODELVIEW_MATRIX), dtype=np.float64).T
        self.camera = (ship.position.x, ship.position.y, ship.position.z)
        ground = ship.navigation.ground_height_at(ship.position.x, ship.position.z)
        self.horizon = (ground, math.sqrt(2.0 * terrain.radius * max(ship.position.y - ground, 0.0)), terrain.radius)
        right, up, back = modelview[0, :3], modelview[1, :3], modelview[2, :3]
        if self._collect():
            self.selection = None   # something new can be shown
        frame_watch.mark('ground: uploads')
        rotation = modelview[:3, :3]
        chosen = self.selection
        moved = chosen is None or np.linalg.norm(np.subtract(self.camera, chosen[2])) > REUSE_MOVE
        if moved or np.abs(rotation - chosen[3]).max() > REUSE_TURN:
            tan_h, tan_v = VIEW_PADDING / projection[0, 0], VIEW_PADDING / projection[1, 1]
            forward = -back
            self.planes = []
            for normal in (forward * tan_h - right, forward * tan_h + right, forward * tan_v - up,
                           forward * tan_v + up):
                unit = normal / np.linalg.norm(normal)
                self.planes.append((float(unit[0]), float(unit[1]), float(unit[2])))
            roots = self._roots()
            self._build_roots_now(roots)
            out: List[Tuple[_Chunk, float]] = []
            requests: List[Tuple[float, Key]] = []
            self.holes = 0
            self.unsettled = []
            for root in self._visible_roots(roots):
                self._select(root, out, requests)
            self._request(requests)
            # A chunk is in the near pass if it can have anything within that depth (a point at that depth can be
            # farther from the camera, to the side), and in the far pass if it can have anything beyond the split.
            near = [chunk for chunk, gap in out if gap < NEAR_RANGE * NEAR_SLACK]
            split = NEAR_RANGE - DEPTH_OVERLAP
            far = [chunk for chunk, gap in out if gap + mesh.chunk_size(chunk.key[0]) * 1.5 > split]
            self.selection = chosen = (_Batch(near), _Batch(far), self.camera, rotation.copy())
        else:
            for chunk in chosen[0].chunks + chosen[1].chunks:
                chunk.last_used = self.frame   # kept while shown, so the unused ones can be evicted
        frame_watch.mark('ground: choosing chunks')

        shadows = self.shadows_active = shadows and light.sun.y > SHADOW_SUN_MIN
        if shadows:
            self._update_shadows(projection, modelview, light, casters)
            frame_watch.mark('ground: shadows')
        far_split = NEAR_RANGE - DEPTH_OVERLAP
        far_projection = projection.copy()      # the same view, with the far pass's depth range
        far_projection[2, 2] = (FAR_PLANE + far_split) / (far_split - FAR_PLANE)
        far_projection[2, 3] = 2.0 * FAR_PLANE * far_split / (far_split - FAR_PLANE)
        near, far = chosen[0], chosen[1]
        self._draw_chunks(far, 0, ship, light, far_projection @ modelview, shadows)
        GL.glClear(GL.GL_DEPTH_BUFFER_BIT)
        self._draw_chunks(near, 1, ship, light, projection @ modelview, shadows)
        self._evict()
        return True

    def _collect(self) -> bool:
        """Uploads the chunks the helpers have built; True if there were any."""
        uploaded = False
        for key, vertices in self.builder.collect(MAX_UPLOADS_PER_FRAME):
            if key not in self.cache:
                self._upload(key, vertices)
                uploaded = True
        return uploaded

    def _request(self, requests: List[Tuple[float, Key]]) -> None:
        requests.sort()
        for _, key in requests:
            if self.builder.pending >= MAX_REQUESTS_IN_FLIGHT:
                break
            if key not in self.cache:
                self.builder.request(key, self.terrain.seed, self.terrain.radius, self.terrain.relief,
                                     self.terrain.platforms)

    def _caster_chunks(self) -> List[_Chunk]:
        """The cached chunks that can cast a shadow into the view, from the nearest ground at full detail to the
        farthest coarse: the walk of the quadtree, but all round and over what is built only."""
        cam_x, _, cam_z = self.camera
        chosen: List[_Chunk] = []

        def visit(key: Key) -> None:
            chunk = self.cache.get(key)
            if chunk is None:
                return
            level = key[0]
            edge = mesh.chunk_size(level)
            gap = math.hypot(max(chunk.corner_x - cam_x, 0.0, cam_x - chunk.corner_x - edge),
                             max(chunk.corner_z - cam_z, 0.0, cam_z - chunk.corner_z - edge))
            if gap > SHADOW_RANGE:
                return
            if level < mesh.MAX_LEVEL and gap < edge * SHADOW_SPLIT:
                children = [(level + 1, key[1] * 2 + cx, key[2] * 2 + cz) for cx in (0, 1) for cz in (0, 1)]
                if all(child in self.cache for child in children):
                    for child in children:
                        visit(child)
                    return
            chosen.append(chunk)

        low_x, high_x = (math.floor((cam_x + sign * SHADOW_RANGE) / mesh.ROOT_SIZE) for sign in (-1, 1))
        low_z, high_z = (math.floor((cam_z + sign * SHADOW_RANGE) / mesh.ROOT_SIZE) for sign in (-1, 1))
        for ix in range(low_x, high_x + 1):
            for iz in range(low_z, high_z + 1):
                visit((0, ix, iz))
        return chosen

    def _update_shadows(self, projection: np.ndarray, modelview: np.ndarray, light: SurfaceLight,
                        casters: Optional[Callable[[ShadowMap, int], None]]) -> None:
        """Fits the cascades and draws again the ones that need it: the ground that can cast, then the other casters."""
        shadow = self.shadow
        camera = np.array(self.camera)
        forward = -modelview[2, :3]
        sun = np.array([light.sun.x, light.sun.y, light.sun.z])
        fov_y = 2.0 * math.atan(1.0 / projection[1, 1])
        shadow.update(camera, forward, projection[1, 1] / projection[0, 0], fov_y, sun)
        if not any(shadow.refresh):
            return
        moved = math.hypot(self.camera[0] - self.casters_at[0], self.camera[2] - self.casters_at[2])
        if self.casters is None or len(self.cache) != self.casters_stamp or moved > SHADOW_REMAKE:
            self.casters = _Batch(self._caster_chunks())
            self.casters_at, self.casters_stamp = self.camera, len(self.cache)
        centres = self.casters.centres - camera
        u = self.shadow_uniforms
        GL.glUseProgram(self.shadow_program)
        GL.glUniform1f(u["u_camy"], self.camera[1])
        GL.glUniform2f(u["u_curve"], NEAR_RANGE, self.terrain.radius)
        for cascade in range(shadow_map.CASCADES):
            if not shadow.refresh[cascade]:
                continue
            shadow.begin(cascade)
            GL.glUseProgram(self.shadow_program)
            GL.glUniformMatrix4fv(u["u_light_vp"], 1, GL.GL_TRUE, shadow.render_matrices[cascade])
            inside = shadow.covers(cascade, centres, self.casters.radii)
            batch = _Batch([chunk for chunk, taken in zip(self.casters.chunks, inside.tolist()) if taken])
            self._multi_draw(batch, 2 + cascade)
            GL.glUseProgram(0)
            if casters is not None:
                casters(shadow, cascade)
            shadow.end()

    def _multi_draw(self, batch: _Batch, which: int) -> None:
        """Draws the chunks of a batch with one call: their rows and commands in the buffers of pass `which`."""
        if not batch.chunks:
            return
        cam_x, _, cam_z = self.camera
        rows = np.empty((len(batch.chunks), 4), dtype=np.float32)
        rows[:, 0] = batch.corners[:, 0] - cam_x
        rows[:, 1] = batch.corners[:, 1] - cam_z
        rows[:, 2:] = batch.wraps
        GL.glBindVertexArray(self.vaos[which])
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.instance_buffers[which])
        GL.glBufferSubData(GL.GL_ARRAY_BUFFER, 0, rows.nbytes, rows)
        GL.glBindBuffer(GL.GL_DRAW_INDIRECT_BUFFER, self.command_buffers[which])
        GL.glBufferSubData(GL.GL_DRAW_INDIRECT_BUFFER, 0, batch.commands.nbytes, batch.commands)
        GL.glMultiDrawElementsIndirect(GL.GL_TRIANGLES, GL.GL_UNSIGNED_SHORT, ctypes.c_void_p(0),
                                       len(batch.chunks), 0)
        GL.glBindBuffer(GL.GL_DRAW_INDIRECT_BUFFER, 0)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        GL.glBindVertexArray(0)

    def _draw_chunks(self, batch: _Batch, which: int, ship: Ship, light: SurfaceLight, mvp: np.ndarray,
                     shadows: bool) -> None:
        if not batch.chunks:
            return
        u = self.uniforms
        sun = light.sun
        GL.glUseProgram(self.program)
        GL.glUniformMatrix4fv(u["u_mvp"], 1, GL.GL_TRUE, mvp.astype(np.float32))
        GL.glUniform3f(u["u_sun"], sun.x, sun.y, sun.z)
        GL.glUniform3f(u["u_tint"], *(channel / 255.0 for channel in light.tint))
        GL.glUniform1f(u["u_starlight"], SURFACE_STARLIGHT)
        GL.glUniform3f(u["u_far"], *(channel / 255.0 for channel in light.ground_colour()))
        GL.glUniform1f(u["u_ground"], ship.navigation.ground_height_at(ship.position.x, ship.position.z))
        GL.glUniform2f(u["u_fall"], FALL_START, FAR_RANGE)
        GL.glUniform2f(u["u_curve"], NEAR_RANGE, self.terrain.radius)
        GL.glUniform2f(u["u_detail"], *DETAIL_RANGE)
        GL.glUniform1f(u["u_camy"], self.camera[1])
        self.shadow.bind_texture()
        self.shadow.set_uniforms(u, shadows)
        self._multi_draw(batch, which)
        GL.glUseProgram(0)
    # endregion


class TerrainGl:
    """What the 3D pass uses: `draw` in place of the flat ground, `preload` at load, `shutdown` at quit."""

    _renderer: Optional[_Renderer] = None

    @staticmethod
    def _get() -> _Renderer:
        if TerrainGl._renderer is None:
            TerrainGl._renderer = _Renderer()
        return TerrainGl._renderer

    @staticmethod
    def preload() -> None:
        """Starts the helper processes when the game's worlds have relief, so that the first ground does not wait."""
        from galaxies.rocky_world import RockyWorld   # not at the top: the graphics are loaded before the galaxies
        if RockyWorld.TERRAIN_RELIEF > 0.0:
            TerrainGl._get().builder.start()

    @staticmethod
    def draw(world: World, ship: Ship, light: SurfaceLight, shadows: bool = False,
             casters: Optional[Callable[[ShadowMap, int], None]] = None) -> bool:
        return TerrainGl._get().draw(world, ship, light, shadows, casters)

    @staticmethod
    def shadow_map() -> Optional[ShadowMap]:
        """The shadow map of this frame's ground, for what stands on it to receive the shadows; None if it has none."""
        renderer = TerrainGl._renderer
        return renderer.shadow if renderer is not None and renderer.shadows_active else None

    @staticmethod
    def reach(world: World) -> float:
        """How high above the ground the surface pass is still worth drawing: the far ground of a world with relief
        shows from afar, the flat one has nothing beyond the near pass."""
        terrain = getattr(world, "terrain", None)
        return FAR_RANGE if terrain is not None and terrain.relief != 0.0 else float(MAX_DEPTH)

    @staticmethod
    def is_settled(world: World, km2: Km2) -> bool:
        """False while the ground under the Km2 is shown coarser than wanted (or not at all), so that the Km2's rocks,
        which sit on the exact ground, are not drawn above or below a mesh that is still rough. True for flat worlds."""
        terrain = getattr(world, "terrain", None)
        renderer = TerrainGl._renderer
        if terrain is None or terrain.relief == 0.0 or renderer is None:
            return True
        low_x, low_z, high_x, high_z = km2.longitude, km2.latitude, km2.longitude + km2.SIZE, km2.latitude + km2.SIZE
        cam_x, _, cam_z = renderer.camera
        gap = math.hypot(max(low_x - cam_x, 0.0, cam_x - high_x), max(low_z - cam_z, 0.0, cam_z - high_z))
        if gap > KEEP_ALL_ROUND:
            return True    # too far to tell, and only refined where seen
        return not any(abs(node.centre_x - (low_x + high_x) / 2) < node.edge / 2 + km2.SIZE / 2
                       and abs(node.centre_z - (low_z + high_z) / 2) < node.edge / 2 + km2.SIZE / 2
                       for node in renderer.unsettled)

    @staticmethod
    def shutdown() -> None:
        if TerrainGl._renderer is not None:
            TerrainGl._renderer.builder.shutdown()
