"""Cascaded shadow maps of the surface, for the sun as a direction: the view's depth is cut into cascades, each a
fitted orthographic light view in one layer of a depth texture array. What casts (the terrain, then the rocks and the
buildings) is drawn into them by its owner between `begin` and `end`; what receives (GLSL below) samples them.

Everything is relative to the camera, as the shaders are, so float32 is enough. Each cascade is fitted to a sphere
around its slice of the view, so turning does not change it, and its centre snaps to the shadow texels in
world-fixed light space, so moving does not make the edges crawl. A cascade is drawn again only when it is old or the
view has moved a share of its size (the far ones change slowly), and the matrix of one that is kept is moved with the
camera. Casters between a cascade and the sun are kept by depth clamping.
"""

from __future__ import annotations
import math
from typing import List

import numpy as np
from OpenGL import GL

CASCADES = 3
SPLITS = (0.5, 40.0, 300.0, 2500.0)   # m: the view depths where each cascade starts and ends
MAX_AGE = (3, 8, 20)                  # frames: the most a cascade is kept before it is drawn again
MOVE_SHARE = 0.3                      # the share of its size the view may move before a cascade is drawn again
SIZE = 2048                           # texels a side

# What a receiving fragment shader adds: `shadow_factor` is 0 in shadow and 1 in light. The far cascades are sampled
# wider (their texels are coarse, so the edge is softened), and the end of each cascade fades into the next.
RECEIVER_GLSL = """
uniform sampler2DArrayShadow u_shadow;
uniform mat4 u_light_vp[3];
uniform vec3 u_split_far;     // the view depth at which each cascade ends
uniform vec3 u_texel;         // the size in metres of a texel of each cascade
uniform int u_cascades;       // 0: no shadows
uniform float u_bias;
float cascade_shadow(int c, vec3 cpos, vec3 n) {
    vec4 lp = u_light_vp[c] * vec4(cpos + n * (u_texel[c] * 1.5), 1.0);   // pushed along the normal: no acne
    vec3 s = lp.xyz * 0.5 + 0.5;
    if (s.x < 0.0 || s.x > 1.0 || s.y < 0.0 || s.y > 1.0 || s.z > 1.0) return 1.0;
    float z = s.z - u_bias;
    if (c == 0) return texture(u_shadow, vec4(s.xy, float(c), z));
    const float o = 1.0 / @SIZE@.0;
    return 0.25 * (texture(u_shadow, vec4(s.xy + vec2(-o, -o), float(c), z))
                 + texture(u_shadow, vec4(s.xy + vec2(o, -o), float(c), z))
                 + texture(u_shadow, vec4(s.xy + vec2(-o, o), float(c), z))
                 + texture(u_shadow, vec4(s.xy + vec2(o, o), float(c), z)));
}
float shadow_factor(vec3 cpos, vec3 n, float depth) {
    if (u_cascades == 0) return 1.0;
    int c = min(int(depth > u_split_far.x) + int(depth > u_split_far.y), u_cascades - 1);
    if (depth > u_split_far[c]) return 1.0;
    float f = cascade_shadow(c, cpos, n);
    float blend_from = u_split_far[c] * 0.88;
    if (depth > blend_from) {
        float t = (depth - blend_from) / (u_split_far[c] - blend_from);
        f = mix(f, c + 1 < u_cascades ? cascade_shadow(c + 1, cpos, n) : 1.0, t);
    }
    return f;
}
""".replace("@SIZE@", str(SIZE))
RECEIVER_UNIFORMS = ("u_shadow", "u_light_vp", "u_split_far", "u_texel", "u_cascades", "u_bias")


class ShadowMap:
    """The depth texture, its framebuffer and the fitting of the cascades to a view (see the module's docstring)."""

    def __init__(self) -> None:
        self.texture = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D_ARRAY, self.texture)
        GL.glTexImage3D(GL.GL_TEXTURE_2D_ARRAY, 0, GL.GL_DEPTH_COMPONENT24, SIZE, SIZE, CASCADES, 0,
                        GL.GL_DEPTH_COMPONENT, GL.GL_FLOAT, None)
        for name, value in ((GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR), (GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR),
                            (GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE), (GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE),
                            (GL.GL_TEXTURE_COMPARE_MODE, GL.GL_COMPARE_REF_TO_TEXTURE),
                            (GL.GL_TEXTURE_COMPARE_FUNC, GL.GL_LEQUAL)):
            GL.glTexParameteri(GL.GL_TEXTURE_2D_ARRAY, name, value)
        GL.glBindTexture(GL.GL_TEXTURE_2D_ARRAY, 0)
        self.fbo = GL.glGenFramebuffers(1)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.fbo)
        GL.glFramebufferTextureLayer(GL.GL_FRAMEBUFFER, GL.GL_DEPTH_ATTACHMENT, self.texture, 0, 0)
        GL.glDrawBuffer(GL.GL_NONE)
        GL.glReadBuffer(GL.GL_NONE)
        status = GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        GL.glDrawBuffer(GL.GL_BACK)
        GL.glReadBuffer(GL.GL_BACK)
        if status != GL.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"shadow framebuffer incomplete: {status:#x}")
        self.matrices = np.zeros((CASCADES, 4, 4), dtype=np.float32)          # what the receivers sample with
        self.render_matrices = np.zeros((CASCADES, 4, 4), dtype=np.float32)   # what a cascade is drawn with
        self.split_far = np.zeros(CASCADES, dtype=np.float32)
        self.texel = np.zeros(CASCADES, dtype=np.float32)
        self.bias = 2.0 / SIZE
        self.refresh = [True] * CASCADES      # which cascades are to be drawn this frame
        self.centres: List[np.ndarray] = []   # camera-relative, with the radius: what a cascade covers
        self.radii: List[float] = []
        self.right = np.array([1.0, 0.0, 0.0])
        self.up = np.array([0.0, 1.0, 0.0])
        self._valid = [False] * CASCADES
        self._age = [0] * CASCADES
        self._render_matrix = [np.eye(4)] * CASCADES    # float64, relative to the camera of _render_cam
        self._render_cam = [np.zeros(3)] * CASCADES
        self._render_centre = [np.zeros(3)] * CASCADES
        self._render_sun = [np.zeros(3)] * CASCADES
        self._render_radius = [0.0] * CASCADES
        self._viewport = (0, 0, 1, 1)   # the game's, kept while a cascade is drawn
        self._drawing = False

    def invalidate(self) -> None:
        """Every cascade is drawn again (the casters have changed)."""
        self._valid = [False] * CASCADES

    def update(self, camera: np.ndarray, forward: np.ndarray, aspect: float, fov_y: float, sun: np.ndarray) -> None:
        """Fits the cascades to the view (`camera`, in the world, and its `forward`) and the sun, and decides which are
        drawn again (`refresh`)."""
        sun = sun / np.linalg.norm(sun)
        light = -sun    # the direction the light travels
        ref = np.array([0.0, 1.0, 0.0]) if abs(light[1]) < 0.99 else np.array([1.0, 0.0, 0.0])
        right = np.cross(light, ref)
        right /= np.linalg.norm(right)
        up = np.cross(right, light)
        self.right, self.up = right, up
        k = math.tan(fov_y / 2.0) * math.sqrt(1.0 + aspect * aspect)
        self.centres, self.radii = [], []
        for i in range(CASCADES):
            near, far = SPLITS[i], SPLITS[i + 1]
            if k * k >= (far - near) / (far + near):
                z_centre, radius = far, far * k
            else:
                z_centre = 0.5 * (far + near) * (1.0 + k * k)
                radius = 0.5 * math.sqrt((far - near) ** 2 + 2.0 * (far * far + near * near) * k * k
                                         + (far + near) ** 2 * k ** 4)
            texel = 2.0 * radius / SIZE
            world = camera + forward * z_centre   # snapped in world-fixed light space, so moving does not crawl
            cx = math.floor(float(world @ right) / texel) * texel
            cy = math.floor(float(world @ up) / texel) * texel
            snapped = right * cx + up * cy + light * float(world @ light) - camera
            eye = snapped - light * radius
            view = np.eye(4)
            view[0, :3], view[1, :3], view[2, :3] = right, up, -light
            view[:3, 3] = -(view[:3, :3] @ eye)
            ortho = np.array([[1.0 / radius, 0, 0, 0], [0, 1.0 / radius, 0, 0], [0, 0, -1.0 / radius, -1.0],
                              [0, 0, 0, 1.0]])
            ideal = ortho @ view
            world_centre = camera + snapped
            stale = (not self._valid[i] or self._age[i] >= MAX_AGE[i]
                     or abs(radius - self._render_radius[i]) > 1e-6 * radius
                     or float(sun @ self._render_sun[i]) < 0.99999
                     or float(np.linalg.norm(world_centre - self._render_centre[i])) > MOVE_SHARE * radius)
            self.refresh[i] = stale
            if stale:
                self._render_matrix[i] = ideal
                self._render_cam[i] = camera.copy()
                self._render_centre[i] = world_centre
                self._render_sun[i] = sun.copy()
                self._render_radius[i] = radius
                self._valid[i] = True
                self._age[i] = 0
                self.render_matrices[i] = ideal.astype(np.float32)
            else:
                self._age[i] += 1
            shift = np.eye(4)
            shift[:3, 3] = camera - self._render_cam[i]
            self.matrices[i] = (self._render_matrix[i] @ shift).astype(np.float32)
            self.split_far[i] = far
            self.texel[i] = texel
            self.centres.append(snapped)
            self.radii.append(radius)

    def covers(self, cascade: int, centres: np.ndarray, radii: np.ndarray) -> np.ndarray:
        """Which spheres (camera-relative centres) can cast into a cascade: those over its square in the light's plane,
        at any distance from the sun."""
        centre, radius = self.centres[cascade], self.radii[cascade]
        dx = np.abs(centres @ self.right - float(centre @ self.right))
        dy = np.abs(centres @ self.up - float(centre @ self.up))
        return (dx <= radius + radii) & (dy <= radius + radii)

    def begin(self, cascade: int) -> None:
        """Starts drawing into a cascade: depth only, with the clamping and the offset that casting needs."""
        if not self._drawing:
            self._viewport = tuple(int(v) for v in GL.glGetIntegerv(GL.GL_VIEWPORT))
            self._drawing = True
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.fbo)
        GL.glFramebufferTextureLayer(GL.GL_FRAMEBUFFER, GL.GL_DEPTH_ATTACHMENT, self.texture, 0, cascade)
        GL.glViewport(0, 0, SIZE, SIZE)
        GL.glClear(GL.GL_DEPTH_BUFFER_BIT)
        GL.glColorMask(False, False, False, False)
        GL.glEnable(GL.GL_DEPTH_CLAMP)
        GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
        GL.glPolygonOffset(2.0, 4.0)

    def end(self) -> None:
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        GL.glDrawBuffer(GL.GL_BACK)
        GL.glColorMask(True, True, True, True)
        GL.glDisable(GL.GL_DEPTH_CLAMP)
        GL.glDisable(GL.GL_POLYGON_OFFSET_FILL)
        GL.glViewport(*self._viewport)
        self._drawing = False

    def bind_texture(self) -> None:
        """For the receivers, on texture unit 1 (unit 0 stays the game's)."""
        GL.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_2D_ARRAY, self.texture)
        GL.glActiveTexture(GL.GL_TEXTURE0)

    def set_uniforms(self, locations: dict, enabled: bool) -> None:
        """Sets what a receiving program needs (the program must be in use)."""
        GL.glUniform1i(locations["u_shadow"], 1)
        GL.glUniform1i(locations["u_cascades"], CASCADES if enabled else 0)
        if enabled:
            GL.glUniformMatrix4fv(locations["u_light_vp"], CASCADES, GL.GL_TRUE, self.matrices)
            GL.glUniform3f(locations["u_split_far"], *self.split_far)
            GL.glUniform3f(locations["u_texel"], *self.texel)
            GL.glUniform1f(locations["u_bias"], self.bias)
