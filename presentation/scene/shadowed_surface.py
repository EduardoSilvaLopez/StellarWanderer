"""The shadows on what stands on the ground (the rocks, the outposts): their fixed-function drawing, with the colours
the CPU has given each face (SurfaceLight), run through a program that darkens what the sun does not reach.

A face's colour already holds the sun's share, so a shadow takes it back to the starlight: the program works the face's
normal out from the screen-space derivatives (turned to face the camera, which all that is seen of a solid does) and
scales the colour by starlight over what the colour has. The shadow map is the terrain's (terrain_gl.py), and the
vertices are camera-relative before the modelview, as everywhere in the surface pass, so their position for the map is
the eye-space one turned back by the camera's rotation.
"""

from __future__ import annotations
from contextlib import contextmanager
from typing import Dict, Iterator, Optional

import numpy as np
from OpenGL import GL

from . import shadow_map
from .constants import SURFACE_STARLIGHT
from .shadow_map import ShadowMap
from .surface_light import SurfaceLight

VERTEX_SHADER = """
#version 330 compatibility
uniform mat3 u_rotation;     // the camera's rotation: eye space back to the world's axes
out vec4 v_color;
out vec2 v_uv;
out vec3 v_cpos;
out float v_depth;
void main() {
    vec4 eye = gl_ModelViewMatrix * gl_Vertex;
    v_cpos = transpose(u_rotation) * eye.xyz;
    gl_Position = gl_ProjectionMatrix * eye;
    v_depth = gl_Position.w;
    v_color = gl_Color;
    v_uv = gl_MultiTexCoord0.xy;
}
"""

FRAGMENT_SHADER = """
#version 330 compatibility
in vec4 v_color;
in vec2 v_uv;
in vec3 v_cpos;
in float v_depth;
uniform sampler2D u_tex;
uniform int u_textured;
uniform vec3 u_sun;
uniform float u_starlight;
out vec4 frag;
""" + shadow_map.RECEIVER_GLSL + """
void main() {
    vec4 base = v_color;
    if (u_textured == 1) base *= texture(u_tex, v_uv);
    vec3 n = normalize(cross(dFdx(v_cpos), dFdy(v_cpos)));
    if (dot(n, -v_cpos) < 0.0) n = -n;
    float shown = u_starlight + (1.0 - u_starlight) * max(dot(n, u_sun), 0.0);
    float lit = shadow_factor(v_cpos, n, v_depth);
    frag = vec4(base.rgb * mix(u_starlight / shown, 1.0, lit), base.a);
}
"""


class ShadowedSurface:
    """`begin` before drawing what should receive the shadows, `end` after."""

    _program = 0
    _uniforms: Dict[str, int] = {}

    @staticmethod
    def _ensure() -> None:
        if ShadowedSurface._program:
            return

        def shader(kind: int, source: str) -> int:
            handle = GL.glCreateShader(kind)
            GL.glShaderSource(handle, source)
            GL.glCompileShader(handle)
            if not GL.glGetShaderiv(handle, GL.GL_COMPILE_STATUS):
                raise RuntimeError(GL.glGetShaderInfoLog(handle))
            return handle

        program = GL.glCreateProgram()
        GL.glAttachShader(program, shader(GL.GL_VERTEX_SHADER, VERTEX_SHADER))
        GL.glAttachShader(program, shader(GL.GL_FRAGMENT_SHADER, FRAGMENT_SHADER))
        GL.glLinkProgram(program)
        if not GL.glGetProgramiv(program, GL.GL_LINK_STATUS):
            raise RuntimeError(GL.glGetProgramInfoLog(program))
        ShadowedSurface._program = program
        names = ("u_rotation", "u_tex", "u_textured", "u_sun", "u_starlight") + shadow_map.RECEIVER_UNIFORMS
        ShadowedSurface._uniforms = {name: GL.glGetUniformLocation(program, name) for name in names}

    @staticmethod
    def begin(shadow: Optional[ShadowMap], light: SurfaceLight, rotation: np.ndarray, textured: bool) -> bool:
        """Starts the program, if there are shadows (`shadow` the map, drawn this frame); False if there are none, and
        then nothing has changed. `rotation` is the camera's, the upper 3x3 of the view's modelview."""
        if shadow is None:
            return False
        ShadowedSurface._ensure()
        u = ShadowedSurface._uniforms
        GL.glUseProgram(ShadowedSurface._program)
        GL.glUniformMatrix3fv(u["u_rotation"], 1, GL.GL_TRUE, np.ascontiguousarray(rotation, dtype=np.float32))
        GL.glUniform1i(u["u_tex"], 0)
        GL.glUniform1i(u["u_textured"], 1 if textured else 0)
        GL.glUniform3f(u["u_sun"], light.sun.x, light.sun.y, light.sun.z)
        GL.glUniform1f(u["u_starlight"], SURFACE_STARLIGHT)
        shadow.bind_texture()
        shadow.set_uniforms(u, True)
        return True

    @staticmethod
    @contextmanager
    def receiving(shadow: Optional[ShadowMap], light: SurfaceLight, rotation: np.ndarray,
                  textured: bool) -> Iterator[None]:
        """`begin` and `end` around a block (nothing happens when there are no shadows)."""
        started = ShadowedSurface.begin(shadow, light, rotation, textured)
        try:
            yield
        finally:
            if started:
                GL.glUseProgram(0)
