"""Gas and ice giants drawn in the OpenGL pass as a ball of gas, not a sphere: a fragment shader marches each pixel's
view ray through the atmosphere, from the outside or from the inside. What the gas does to light comes from the
atmosphere model (`JovianWorld.optical_profile`): the extinction along the ray makes the cloud tops the visible surface
where the gas gets opaque, and below them the sunlight is used up by the column above, so the deeper the ship the
dimmer and the shorter its view, until all is dark. The clouds are noise stretched along the bands, in octaves down to what a pixel can show, which each wind cell of
the planet (`JovianWorld.cloud_state`) carries east or west, so they drift and shear with the date. They are a volume:
they raise and lower the cloud tops, thicken and thin the gas, brighten the slopes the sun faces and shadow the others,
and the colour of the gas changes with the depth (`deep_colour`). Storms (`JovianWorld.storms`) swirl the clouds, tint them and
raise their tops; lightning (`JovianWorld.lightning`), mostly in the storms, lights the gas round each flash from below,
a glow on the night side. Rings (`JovianWorld.ring`) lie in the equatorial plane: a ray meets them once, they are lit by
the star and shaded by the planet, and they dim what is behind them; where a ring lies beyond the gas, the gas hides it.
With the star behind a giant its thin haze, lit above the planet's
shadow and scattering forward, rings the limb as a crescent. The giants are drawn under the sky texture (the star
covers those behind it, and they cover it otherwise): the sky is made transparent over each (`sky_erasers`), and the
orbit line is cut where a giant is in front of it (`hidden`), so a moon or its orbit passes in front of or behind its
planet as it should (see OpenGLGui.draw)."""

from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Dict, List, Tuple
import math
from datetime import datetime
import numpy as np
from OpenGL import GL
from galaxies.jovian_world import JovianWorld
from common.vector3 import Vector3
from .constants import (
    WORLD_AMBIENT_LIGHT, WORLD_MIN_RADIUS_PX, MIN_VISIBLE_PX, GIANT_HAZE_TOP, GIANT_SUN_GAIN, GIANT_STEP_DEPTH,
    GIANT_STEP_HEIGHT, GIANT_PIXEL_BUDGET, GIANT_TARGET_SIZE, GIANT_LIMB_DARKENING, GIANT_LIGHT_PENETRATION,
    GIANT_FORWARD_SCATTERING, GIANT_CLOUD_WAVELENGTH, GIANT_CLOUD_STRETCH, GIANT_CLOUD_OCTAVES, GIANT_CLOUD_WARP,
    GIANT_CLOUD_CONTRAST, GIANT_CLOUD_DEPTH_WAVELENGTH, GIANT_CLOUD_RELIEF, GIANT_CLOUD_RELIEF_OCTAVES, GIANT_CLOUD_DENSITY, GIANT_CLOUD_GAIN,
    GIANT_CLOUD_LAYER_EDGE, GIANT_CLOUD_RELIEF_SHADING, GIANT_LIGHTNING_GAIN, GIANT_LIGHTNING_COLOUR,
    GIANT_LIGHTNING_MAX_TIME_SCALE, GIANT_LIGHTNING_MAX_FLASHES, GIANT_STORM_RAISE, GIANT_STORM_MAX, NEAR_CLIP,
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
const float NOISE_SIZE = 64.0;

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
uniform float forward;         // how much the thin haze scatters forward (Henyey-Greenstein asymmetry)
uniform float step_depth;   // the optical depth a step may cover
uniform float step_height;  // the altitude, in scale heights, a step may cover
uniform float band_count;
uniform float band_phase;
uniform float band_contrast;
const int RING_N = 64;
uniform float ring_on;           // 1 where the giant has rings
uniform float ring_inner;        // m from the centre
uniform float ring_outer;
uniform float ring_mean;         // the mean optical depth of the rings: what their shadow on the planet is made of
uniform float ring_opacity[RING_N];  // the optical depth of the rings, from the inner edge out
uniform vec3 ring_colour;
uniform sampler3D noise;       // random lattice values, see lattice_noise
uniform vec3 prime_x;          // the planet's prime meridian, in the camera frame (it turns with the spin)
uniform vec3 prime_y;          // 90 degrees east of it
uniform vec3 cloud_offset;     // where in the noise this giant's clouds are
uniform float cloud_wavelength;
uniform float cloud_stretch;
uniform float cloud_octaves;
uniform float cloud_warp;
uniform float cloud_gain;        // the strength of each octave against the one before
uniform float cloud_contrast;
uniform float cloud_depth;       // m: the altitude over which the coarsest clouds change
uniform float cloud_relief;      // how far the cloud tops rise and fall, in scale heights
uniform float relief_octaves;    // the octaves that shape the cloud tops: the coarse ones
uniform int flash_count;           // the flashes that are alight, and where (camera frame), how wide (m), how bright
uniform vec3 flash_direction[8];
uniform vec2 flash_shape[8];
uniform float flash_column;       // the optical depth above the flashes
uniform vec3 flash_colour;
uniform int storm_count;           // the storms, and where (camera frame); their radius (m), twist (rad), strength
uniform vec3 storm_direction[6];
uniform vec3 storm_shape[6];
uniform vec3 storm_colour;         // what the clouds of a storm are multiplied by
uniform float storm_raise;
uniform float cloud_density;     // how much the clouds thicken and thin the gas, 0 to 1
uniform float layer_edge;        // scale heights from the 1 bar level where the clouds end
uniform float relief_shading;
uniform float cell_first;      // index of the first wind cell
uniform float cell_count;
uniform float cell_angle[16];  // how far each wind cell's clouds have drifted east of the planet's turn

float inv_a2;
float cloud_h;  // noise units per metre along the bands, and across them
float cloud_v;
float shape;   // 1 / polar^2 - 1 / equatorial^2
float pole_light;  // the spin axis against the direction to the star

// How much more light the haze scatters through an angle (cosine c) than through a right angle.
float haze_phase(float c) {
    float g2 = forward * forward;
    return pow(1.0 + g2, 1.5) / pow(1.0 + g2 - 2.0 * forward * c, 1.5);
}

float asinh_(float x) {
    return log(x + sqrt(x * x + 1.0));
}


// Random values on a lattice, three to a cell, in a 3D texture that repeats every NOISE_SIZE cells; the texture's own
// linear filter does the interpolation, and the coordinates are eased so that the noise is smooth across cells.
vec3 lattice_noise(vec3 p) {
    vec3 i = floor(p);
    vec3 f = p - i;
    f = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    return texture3D(noise, (mod(i, NOISE_SIZE) + f + 0.5) / NOISE_SIZE).rgb;
}

float value_noise(vec3 p) {
    return lattice_noise(p).r;
}

// The clouds at a place of the planet and an altitude, -1 to 1: its prime meridian coordinates a, b and sine of
// latitude c, with the cell's clouds turned east by theta. The noise is stretched along the latitude circles, bent by itself, and made
// of octaves, each half as wide as the one before, dropped where a pixel (`footprint`, metres) could not show them.
float clouds(float a, float b, float c, float altitude, float theta, float footprint, float turbulence,
             float octaves) {
    float x = a * cos(theta) + b * sin(theta);
    float y = b * cos(theta) - a * sin(theta);
    vec3 p = vec3(x * cloud_h, y * cloud_h, c * cloud_v + altitude / cloud_depth) + cloud_offset;
    vec3 bend = lattice_noise(p * 0.5 + vec3(3.1, 1.7, 5.3)) - 0.5;
    p += cloud_warp * turbulence * bend;
    float sum = 0.0;
    float amplitude = 1.0;
    float wavelength = cloud_wavelength;
    for (int octave = 0; octave < 12; octave++) {
        float seen = clamp(wavelength / (2.0 * footprint) - 1.0, 0.0, 1.0);
        if (float(octave) >= octaves || seen <= 0.0) {
            break;
        }
        sum += amplitude * seen * (value_noise(p) - 0.5);
        p = p * 2.0 + vec3(5.2, 1.3, 3.7);
        amplitude *= cloud_gain;
        wavelength *= 0.5;
    }
    float scaled = sum * 1.3 * (1.0 - cloud_gain) / 0.5 * 2.0;
    return scaled / (1.0 + abs(scaled));  // a soft limit: a hard one flattens the clouds into plateaus
}

// The clouds in the direction `up` from the centre, at an altitude: in the wind cell of the latitude, and in the next
// one over where two cells meet, as the clouds shear there. `octaves` is how many to make of them.
float cloud_field(vec3 up, float altitude, float footprint, float octaves) {
    if (2.0 * footprint > cloud_wavelength) {
        return 0.0;  // too far to show even the coarsest
    }
    float a = dot(up, prime_x);
    float b = dot(up, prime_y);
    float c = dot(up, pole);
    float pattern = band_count * HALF_PI * c + band_phase;
    float turbulence = 0.75 - 0.25 * sin(pattern);
    float place = pattern / 3.1415927 + 0.5;
    float cell = floor(place);
    float within = place - cell;
    float index = clamp(cell - cell_first, 0.0, cell_count - 1.0);
    float value = clouds(a, b, c, altitude, cell_angle[int(index)], footprint, turbulence, octaves);
    float other = within < 0.2 ? index - 1.0 : (within > 0.8 ? index + 1.0 : index);
    if (other != index && other >= 0.0 && other < cell_count) {
        float share = within < 0.2 ? 0.5 * (1.0 - within / 0.2) : 0.5 * (within - 0.8) / 0.2;
        value = mix(value, clouds(a, b, c, altitude, cell_angle[int(other)], footprint, turbulence, octaves), share);
    }
    return value;
}

// The colour of the gas by the optical depth above it: pale ice haze on top, the cloud colour at the deck, brown
// below it, and a cold grey-blue in the deep.
vec3 deep_colour(vec3 base, float column) {
    float s = log(max(column, 1e-4));
    vec3 colour = mix(mix(base, vec3(0.95), 0.35), base, smoothstep(-2.5, -0.3, s));
    colour = mix(colour, base * vec3(0.78, 0.6, 0.42), smoothstep(0.7, 2.3, s));
    return mix(colour, vec3(0.2, 0.28, 0.42) * (0.3 + dot(base, vec3(0.33))), smoothstep(3.0, 4.2, s));
}

void gas_at(float altitude, out float extinction, out float column) {
    float s = asinh_(altitude / scale_height);
    float f = clamp((s - s_min) / (s_max - s_min), 0.0, 1.0) * float(NODES - 1);
    int i = int(min(floor(f), float(NODES - 2)));
    float w = f - float(i);
    extinction = exp(mix(log_k[i], log_k[i + 1], w));
    column = exp(mix(log_tau[i], log_tau[i + 1], w));
}

// The direction `up` turned round each storm it lies in, as the clouds swirl in a vortex: a rotation about the
// storm's own axis, as far as its twist at its middle and less out to its edge. `amount` is how much it is in storms.
vec3 storm_swirl(vec3 up, out float amount) {
    amount = 0.0;
    for (int i = 0; i < 6; i++) {
        if (i >= storm_count) {
            break;
        }
        vec3 centre = storm_direction[i];
        float chord = 2.0 * (1.0 - dot(up, centre)) * equatorial * equatorial;
        float radius = storm_shape[i].x;
        if (chord > 6.0 * radius * radius) {
            continue;  // too far to feel it
        }
        float inside = exp(-chord / (radius * radius));
        amount += storm_shape[i].z * inside;
        if (inside > 0.01) {
            float angle = storm_shape[i].y * storm_shape[i].z * inside;
            up = up * cos(angle) + cross(centre, up) * sin(angle) + centre * dot(centre, up) * (1.0 - cos(angle));
        }
    }
    return normalize(up);
}

// The rings, in the equatorial plane (normal: the pole) through the centre. Their optical depth is looked up by the
// radius in the plane; a ray meets the plane once, and crosses it more obliquely the more it runs along it.
float ring_radius(vec3 p) {
    return length(p - dot(p, pole) * pole);
}

float ring_tau_at(float r) {
    if (ring_on < 0.5 || r < ring_inner || r > ring_outer) {
        return 0.0;
    }
    float f = clamp((r - ring_inner) / (ring_outer - ring_inner), 0.0, 1.0) * float(RING_N - 1);
    int i = int(min(floor(f), float(RING_N - 2)));
    return mix(ring_opacity[i], ring_opacity[i + 1], f - float(i));  // interpolated: no steps on screen
}

// The share of the sun's light that the rings let through to the point q (outside the planet). Their shadow on the
// planet is made of the mean optical depth, with soft edges, not of the rings' own structure: the gaps would make a
// dashed line where the sun is nearly in the ring plane. And a ring has a thickness, so the slant has a limit. With
// the sun that close to the ring plane the shadow is a line thinner than a pixel, which no sampling draws cleanly: it
// fades out below a few degrees of elevation.
float ring_shadow(vec3 q) {
    float cosine = dot(light, pole);
    if (ring_on < 0.5 || abs(cosine) < 1e-5) {
        return 1.0;
    }
    float s = -dot(q, pole) / cosine;
    if (s <= 0.0) {
        return 1.0;
    }
    float share = (ring_radius(q + light * s) - ring_inner) / (ring_outer - ring_inner);
    if (share <= 0.0 || share >= 1.0) {
        return 1.0;
    }
    float edge = smoothstep(0.0, 0.06, share) * (1.0 - smoothstep(0.94, 1.0, share));
    return mix(1.0, exp(-ring_mean * edge * min(1.0 / abs(cosine), 6.0)), smoothstep(0.01, 0.06, abs(cosine)));
}

// 0 where the planet hides the sun from the point q, 1 where it does not.
float planet_shadow(vec3 q) {
    float pl = dot(pole, light);
    float pq = dot(pole, q);
    float a = inv_a2 + shape * pl * pl;
    float b = dot(q, light) * inv_a2 + shape * pl * pq;
    float c = dot(q, q) * inv_a2 + shape * pq * pq - 1.0;
    float disc = b * b - a * c;
    if (disc <= 0.0 || c <= 0.0) {
        return 1.0;
    }
    return (-b - sqrt(disc)) / a > 0.0 ? 0.0 : 1.0;
}

// The ring a ray meets (premultiplied colour and opacity), and how far along the ray it is.
vec4 ring_at(vec3 u, out float t_ring) {
    t_ring = 1e30;
    float cosine = dot(u, pole);
    if (ring_on < 0.5 || abs(cosine) < 1e-5) {
        return vec4(0.0);
    }
    t_ring = -dot(camera, pole) / cosine;
    if (t_ring <= 0.0) {
        t_ring = 1e30;
        return vec4(0.0);
    }
    vec3 p = camera + u * t_ring;
    float tau = ring_tau_at(ring_radius(p));
    if (tau <= 0.0) {
        return vec4(0.0);
    }
    float alpha = 1.0 - exp(-tau * min(1.0 / abs(cosine), 12.0));  // a ring has a thickness: no solid line edge-on
    float lit = (0.3 + abs(dot(pole, light))) * planet_shadow(p);
    return vec4(ring_colour * sun_gain * lit * alpha, alpha);
}

// What the ray u from the camera gathers from the gas: the light it scatters towards it (premultiplied), and its
// opacity; t_enter is where the ray enters the gas (far away when it misses it).
vec4 gas_trace(vec3 u, out float t_enter) {
    t_enter = 1e30;
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
    t_enter = t;
    float t_end = (-b + root) / a;
    if (t_end <= 0.0) {
        return vec4(0.0);
    }

    float transmission = 1.0;
    vec3 gathered = vec3(0.0);
    bool cloud_seen = false;
    float deck_shadow = 1.0;  // the share of the sun's light the rings let through to the deck
    float cloud = 0.0;     // the fine clouds where the ray first meets the deck
    for (int march = 0; march < MAX_STEPS; march++) {
        if (t >= t_end || transmission < 0.004) {
            break;
        }
        vec3 p = camera + u * t;
        float r = max(length(p), 1.0);
        float pp = dot(pole, p);
        float q = sqrt(max(dot(p, p) * inv_a2 + shape * pp * pp, 1e-12));
        vec3 up = p / r;
        float altitude = r * (1.0 - 1.0 / q);
        float footprint = max(t, 1.0) / focal * pixel_scale.x / max(-dot(up, u), 0.15);
        // The cloud tops rise and fall: in the layer of the clouds the gas is looked up at an altitude moved by the
        // clouds there, as if the whole atmosphere were raised where they are high.
        float storm_amount = 0.0;
        vec3 up_swirl = up;
        float relief = 0.0;
        float layer = 1.0 - smoothstep(0.5 * layer_edge, layer_edge, abs(altitude) / scale_height);
        if (layer > 0.0 && storm_count > 0) {
            up_swirl = storm_swirl(up, storm_amount);
        }
        if (layer > 0.0 && cloud_relief > 0.0) {
            relief = cloud_field(up_swirl, altitude, footprint, relief_octaves);
        }
        relief = clamp(relief + storm_raise * min(storm_amount, 1.0) * layer, -1.0, 1.6);  // the storms stand higher
        float extinction, column;
        gas_at(altitude - relief * cloud_relief * scale_height * layer, extinction, column);
        extinction *= max(1.0 + cloud_density * relief * layer, 0.2);  // puffs and gaps in the gas itself

        // The step: a share of an optical depth, and no more than a share of a scale height of altitude.
        float radial = max(abs(dot(p, u)) / r, 0.02);
        float ds = min(step_depth / max(extinction, 1e-12), step_height * scale_height / radial);
        ds = min(max(ds, 0.01 * scale_height), t_end - t);
        float absorbed = 1.0 - exp(-extinction * ds);

        // The sunlight at the step: through the column above it along the slant. Below the 1 bar level none reaches
        // past the horizon. Above it the beam may graze the planet: it is cut by the planet itself, or, passing above
        // it, crosses the gas at its closest altitude (the length of a grazing path is that of Chapman's law), which
        // lights the haze beyond the terminator.
        float mu = dot(up, light);
        float sun;
        if (q <= 1.0) {
            sun = smoothstep(-0.02, 0.15, mu) * exp(-penetration * column / max(mu, 0.05));
        } else {
            float along = 1.0 / (max(mu, 0.0) + 1.0 / sqrt(0.5 * 3.1415927 * r / scale_height));
            float path = column * along;
            float al = inv_a2 + shape * pole_light * pole_light;
            float bl = dot(p, light) * inv_a2 + shape * pp * pole_light;
            float closest = -bl / al;
            if (mu < 0.1 && closest > 0.0) {
                float q_closest = q * q - bl * bl / al;
                if (q_closest <= 1.0) {
                    path = 1e4;
                } else {
                    float r_closest = max(length(p + light * closest), 1.0);
                    float grazing_extinction, grazing_column;
                    gas_at(r_closest * (1.0 - inversesqrt(q_closest)), grazing_extinction, grazing_column);
                    path = grazing_column * sqrt(2.0 * 3.1415927 * r_closest / scale_height);
                }
            }
            sun = exp(-penetration * path);
        }
        float scattering = mix(1.0, haze_phase(dot(light, u)), exp(-column));
        float pattern = band_count * HALF_PI * dot(pole, up) + band_phase;
        float bands = 1.0 + band_contrast * sin(pattern);
        if (!cloud_seen && column > 0.15) {
            // The fine clouds, looked up once per ray where it first meets the deck.
            cloud_seen = true;
            deck_shadow = ring_shadow(p);  // the rings' shadow on the deck, once per ray: a whole band, not steps of it
            cloud = cloud_field(up_swirl, altitude, footprint, cloud_octaves);
        }
        // How the sun lights the slope of the cloud top: from the clouds here to those a short way towards the sun.
        float relief_light = 1.0;
        float slope_weight = smoothstep(0.05, 0.25, column) * (1.0 - smoothstep(1.5, 3.0, column));
        vec3 toward = light - up * mu;
        float toward_length = length(toward);
        if (slope_weight > 0.0 && layer > 0.0 && cloud_relief > 0.0 && toward_length > 1e-3) {
            float span = clamp(4.0 * footprint, 1000.0, 6.0e4);
            vec3 up_sun = normalize(up + toward / toward_length * span / r);
            float sun_storm;
            vec3 up_sun_swirl = storm_swirl(up_sun, sun_storm);
            float relief_sun = clamp(cloud_field(up_sun_swirl, altitude, footprint, relief_octaves)
                                     + storm_raise * min(sun_storm, 1.0) * layer, -1.0, 1.6);
            float slope = cloud_relief * scale_height * layer * (relief_sun - relief) / span;
            float low = max(mu, 0.05);
            float facing = clamp((low - slope * sqrt(max(1.0 - mu * mu, 0.0))) / low, 0.2, 2.0);
            relief_light = mix(1.0, mix(1.0, facing, relief_shading), slope_weight);
        }
        float turbulence = 0.75 - 0.25 * sin(pattern);
        float shade = max(1.0 + cloud_contrast * (cloud + relief) * 0.5 * turbulence * smoothstep(0.1, 1.0, column), 0.0);
        // A single scattering is brighter at a slant, which a cloud deck is not: darken it there, but only where the gas
        // is thick (the thin haze above the limb stays bright).
        float slant = 1.0 - clamp(-dot(up, u), 0.0, 1.0);
        float deck = 1.0 - limb_darkening * slant * (1.0 - exp(-column));
        // The flashes light the gas round them: through the column between them and the step.
        vec3 flash_light = vec3(0.0);
        for (int flash = 0; flash < 8; flash++) {
            if (flash >= flash_count) {
                break;
            }
            float chord = 2.0 * (1.0 - dot(up, flash_direction[flash])) * equatorial * equatorial;
            float width = flash_shape[flash].x;
            flash_light += flash_colour * flash_shape[flash].y * exp(-chord / (width * width))
                           * exp(-penetration * abs(column - flash_column));
        }
        float lit = sun * relief_light * deck_shadow;
        vec3 source = deep_colour(tint / 255.0 * mix(vec3(1.0), storm_colour, min(storm_amount, 1.0) * smoothstep(0.05, 0.5, column)), column) * bands * shade * deck
                      * (sun_gain * lit * scattering + ambient * exp(-2.0 * column));

        gathered += transmission * absorbed * (source + flash_light);
        transmission *= 1.0 - absorbed;
        t += ds;
    }
    return vec4(gathered, 1.0 - transmission);
}

// The gas and the rings: a ring between the camera and the gas lies over it, one beyond the gas lies under it, so the
// gas hides it where the gas is opaque and the sky shows through where it is not.
vec4 trace(vec3 u) {
    float t_enter;
    vec4 gas = gas_trace(u, t_enter);
    if (ring_on < 0.5) {
        return gas;
    }
    float t_ring;
    vec4 ring = ring_at(u, t_ring);
    if (t_ring < t_enter) {
        return ring + (1.0 - ring.a) * gas;
    }
    return gas + (1.0 - gas.a) * ring;
}

void main() {
    inv_a2 = 1.0 / (equatorial * equatorial);
    cloud_h = equatorial / (cloud_wavelength * cloud_stretch);
    cloud_v = equatorial / cloud_wavelength;
    shape = 1.0 / (polar * polar) - inv_a2;
    pole_light = dot(pole, light);
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
    OUTLINE_POINTS = 64  # the points of a giant's outline on the screen (see sky_erasers)
    _noise: int = 0  # the 3D texture of lattice noise the clouds are made of
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
    def _set_storms(uniform: Callable[[str], int], world: JovianWorld, date_time: datetime, spin: float, ship: Ship,
                    camera: Vector3, equatorial: float) -> None:
        """The storms that can be seen: the biggest GIANT_STORM_MAX of those on the side of the planet the camera sees
        (their edges may reach round the horizon), all of them from inside the gas."""
        inside = camera.length() < equatorial * 1.05
        chosen = sorted(world.storms(date_time), key=lambda storm: -storm.radius * storm.strength)
        directions: List[float] = []
        shapes: List[float] = []
        for storm in chosen:
            azimuth = spin + storm.longitude
            direction = ship.attitude.camera_components(Vector3(math.cos(storm.latitude) * math.cos(azimuth),
                                                               math.cos(storm.latitude) * math.sin(azimuth),
                                                               math.sin(storm.latitude)))
            if not inside and direction.dot(camera) < (0.95 - 2.0 * storm.radius / equatorial) * equatorial:
                continue
            directions += [direction.x, direction.y, direction.z]
            shapes += [storm.radius, storm.twist, storm.strength]
            if len(shapes) >= 3 * GIANT_STORM_MAX:
                break
        count = len(shapes) // 3
        GL.glUniform1i(uniform("storm_count"), count)
        if count:
            GL.glUniform3fv(uniform("storm_direction"), count, np.array(directions, dtype=np.float32))
            GL.glUniform3fv(uniform("storm_shape"), count, np.array(shapes, dtype=np.float32))
            GL.glUniform3f(uniform("storm_colour"), *world.storm_colour)
            GL.glUniform1f(uniform("storm_raise"), GIANT_STORM_RAISE)

    @staticmethod
    def _set_flashes(uniform: Callable[[str], int], world: JovianWorld, date_time: datetime, spin: float, ship: Ship,
                     camera: Vector3, equatorial: float) -> None:
        """The lightning that is alight and can be seen: the strongest GIANT_LIGHTNING_MAX_FLASHES of the flashes on
        the side of the planet the camera sees (all of them from inside the gas). From a time scale of
        GIANT_LIGHTNING_MAX_TIME_SCALE on there are none: a flash may be there for a single frame, and that is fine, but
        a time scale like that turns the sky over too fast for them to mean anything."""
        flashes = [] if ship.owner.time_scale >= GIANT_LIGHTNING_MAX_TIME_SCALE else world.lightning(date_time)
        directions: List[float] = []
        shapes: List[float] = []
        inside = camera.length() < equatorial * 1.05
        for latitude, longitude, radius, brightness in sorted(flashes, key=lambda flash: -flash[3]):
            azimuth = spin + longitude
            direction = ship.attitude.camera_components(Vector3(math.cos(latitude) * math.cos(azimuth),
                                                               math.cos(latitude) * math.sin(azimuth),
                                                               math.sin(latitude)))
            if not inside and direction.dot(camera) < 0.95 * equatorial:
                continue  # beyond the horizon
            directions += [direction.x, direction.y, direction.z]
            shapes += [radius, brightness * GIANT_LIGHTNING_GAIN]
            if len(shapes) >= 2 * GIANT_LIGHTNING_MAX_FLASHES:
                break
        count = len(shapes) // 2
        GL.glUniform1i(uniform("flash_count"), count)
        if count:
            altitude = world.altitude_of_pressure(world.LIGHTNING_PRESSURE, 0.0)
            GL.glUniform3fv(uniform("flash_direction"), count, np.array(directions, dtype=np.float32))
            GL.glUniform2fv(uniform("flash_shape"), count, np.array(shapes, dtype=np.float32))
            GL.glUniform1f(uniform("flash_column"), world.optical_profile([altitude])[1][0])
            GL.glUniform3f(uniform("flash_colour"), *GIANT_LIGHTNING_COLOUR)

    @staticmethod
    def _frame_of(world: JovianWorld, to_world: Vector3, ship: Ship) -> Tuple[np.ndarray, np.ndarray]:
        """Where a giant's centre is from the ship, and its spin axis, in the camera frame (right, up, forward)."""
        centre = ship.attitude.camera_components(to_world)
        pole = ship.attitude.camera_components(Vector3(0.0, 0.0, 1.0))
        return np.array([centre.x, centre.y, centre.z]), np.array([pole.x, pole.y, pole.z])

    @staticmethod
    def sky_erasers(environment: GameEnvironment, ship: Ship, width: int, height: int) -> List[Tuple[float, object]]:
        """What each giant hides of the sky texture (the stars, the worlds and the orbit line farther than it): its
        distance from the ship and the polygon of its outline on the screen, or None when the ship is inside it and
        everything is hidden. The giants are drawn under the sky texture, so the sky is made transparent over them, after
        what is farther than they are is drawn and before what is nearer."""
        from graphics.instruments.common import view_geometry
        _, horizon_y, focal = view_geometry(height)
        erasers: List[Tuple[float, object]] = []
        for world in environment.nearest_system.get_all_worlds():
            if not isinstance(world, JovianWorld):
                continue
            to_world = ship.navigation.direction_to_body(world, environment.date_time)
            distance = to_world.length()
            if 2.0 * world.equatorial_radius * focal / max(distance, 1.0) < MIN_VISIBLE_PX:
                continue
            centre, pole = GiantGl._frame_of(world, to_world, ship)
            stretch = world.equatorial_radius / world.polar_radius
            scaled = centre + (stretch - 1.0) * centre.dot(pole) * pole  # the giant as a sphere of its equatorial radius
            scaled_distance = float(np.linalg.norm(scaled))
            if scaled_distance <= world.equatorial_radius:
                erasers.append((distance, None))
                continue
            toward = scaled / scaled_distance
            e1 = np.cross(toward, [0.0, 1.0, 0.0] if abs(toward[1]) < 0.9 else [1.0, 0.0, 0.0])
            e1 /= np.linalg.norm(e1)
            e2 = np.cross(toward, e1)
            cosine = world.equatorial_radius / scaled_distance
            sine = math.sqrt(1.0 - cosine * cosine)
            outline = []
            for step in range(GiantGl.OUTLINE_POINTS):
                angle = math.tau * step / GiantGl.OUTLINE_POINTS
                normal = -cosine * toward + sine * (math.cos(angle) * e1 + math.sin(angle) * e2)
                point = scaled + world.equatorial_radius * normal
                outline.append(point + (1.0 / stretch - 1.0) * point.dot(pole) * pole)
            polygon = GiantGl._clip_to_view(outline)
            screen = [(width / 2 + focal * x / z, horizon_y - focal * y / z) for x, y, z in polygon]
            screen = GiantGl._clip_to_screen(screen, width, height)
            if len(screen) >= 3:
                erasers.append((distance, [(round(x), round(y)) for x, y in screen]))
        return erasers

    @staticmethod
    def _clip_to_view(polygon: List[np.ndarray]) -> List[Tuple[float, float, float]]:
        """The closed polygon (camera frame) cut by the near plane, so that it can be put on the screen."""
        clipped: List[Tuple[float, float, float]] = []
        for index, start in enumerate(polygon):
            end = polygon[(index + 1) % len(polygon)]
            start_in, end_in = start[2] >= NEAR_CLIP, end[2] >= NEAR_CLIP
            if start_in:
                clipped.append((start[0], start[1], start[2]))
            if start_in != end_in:
                share = (NEAR_CLIP - start[2]) / (end[2] - start[2])
                cut = start + (end - start) * share
                clipped.append((cut[0], cut[1], NEAR_CLIP))
        return clipped

    @staticmethod
    def _clip_to_screen(polygon: List[Tuple[float, float]], width: int, height: int) -> List[Tuple[float, float]]:
        """The polygon cut to the window (a little wider): drawn whole, an outline far off the screen would make the
        software drawing run over millions of rows."""
        margin = 8.0
        edges = ((0, -margin, 1.0), (0, width + margin, -1.0), (1, -margin, 1.0), (1, height + margin, -1.0))
        for axis, limit, sign in edges:
            clipped: List[Tuple[float, float]] = []
            for index, start in enumerate(polygon):
                end = polygon[(index + 1) % len(polygon)]
                start_in, end_in = sign * (start[axis] - limit) >= 0.0, sign * (end[axis] - limit) >= 0.0
                if start_in:
                    clipped.append(start)
                if start_in != end_in:
                    share = (limit - start[axis]) / (end[axis] - start[axis])
                    clipped.append((start[0] + (end[0] - start[0]) * share, start[1] + (end[1] - start[1]) * share))
            polygon = clipped
            if not polygon:
                break
        return polygon

    @staticmethod
    def occluders(environment: GameEnvironment, ship: Ship) -> List[Tuple[np.ndarray, np.ndarray]]:
        """The giants as what `hidden` needs: the centre in the camera frame and the matrix of the ellipsoid (a point x
        from the centre is inside it when x . M . x < 1). A giant the ship is inside of is left out."""
        found: List[Tuple[np.ndarray, np.ndarray]] = []
        for world in environment.nearest_system.get_all_worlds():
            if not isinstance(world, JovianWorld):
                continue
            centre, pole = GiantGl._frame_of(world, ship.navigation.direction_to_body(world, environment.date_time), ship)
            matrix = np.eye(3) / world.equatorial_radius ** 2                 + (1.0 / world.polar_radius ** 2 - 1.0 / world.equatorial_radius ** 2) * np.outer(pole, pole)
            if centre @ matrix @ centre > 1.0:
                found.append((centre, matrix))
        return found

    @staticmethod
    def hidden(points: np.ndarray, occluders: List[Tuple[np.ndarray, np.ndarray]]) -> np.ndarray:
        """Which of the points (camera frame, from the ship) a giant is in front of: the straight line from the ship to
        the point goes through the giant first."""
        covered = np.zeros(len(points), dtype=bool)
        for centre, matrix in occluders:
            quadratic = np.einsum('ni,ij,nj->n', points, matrix, points)
            linear = -points @ (matrix @ centre)
            constant = centre @ matrix @ centre - 1.0
            discriminant = linear * linear - quadratic * constant
            with np.errstate(invalid='ignore', divide='ignore'):
                entry = (-linear - np.sqrt(discriminant)) / quadratic
            covered |= (discriminant > 0.0) & (entry > 0.0) & (entry < 1.0)
        return covered

    @staticmethod
    def _noise_texture() -> int:
        """The cloud noise: NOISE_SIZE cubed random lattice values (three channels), repeating, linearly filtered."""
        if not GiantGl._noise:
            size = 64
            values = np.random.default_rng(20241102).integers(0, 256, (size, size, size, 3), dtype=np.uint8)
            GiantGl._noise = int(GL.glGenTextures(1))
            GL.glBindTexture(GL.GL_TEXTURE_3D, GiantGl._noise)
            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
            GL.glTexImage3D(GL.GL_TEXTURE_3D, 0, GL.GL_RGB8, size, size, size, 0, GL.GL_RGB, GL.GL_UNSIGNED_BYTE, values)
            for parameter in (GL.GL_TEXTURE_WRAP_S, GL.GL_TEXTURE_WRAP_T, GL.GL_TEXTURE_WRAP_R):
                GL.glTexParameteri(GL.GL_TEXTURE_3D, parameter, GL.GL_REPEAT)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        return GiantGl._noise

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
        GL.glViewport(0, 0, width, height)  # the shader's pixels are the window's: the Milky Way leaves the view's viewport
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)  # the shader's colour is premultiplied by its opacity
        GL.glUseProgram(program)
        for _, world, to_world in sorted(chosen, key=lambda item: item[0], reverse=True):
            GiantGl._draw_one(program, width, height, view_h, horizon_y, focal, world, to_world, to_star, star_color,
                              ship, environment.date_time)
        GL.glUseProgram(0)
        GL.glDisable(GL.GL_BLEND)

    @staticmethod
    def _draw_one(program: int, width: int, height: int, view_h: int, horizon_y: int, focal: float,
                  world: JovianWorld, to_world: Vector3, to_star: Vector3, star_color: tuple, ship: Ship,
                  date_time: datetime) -> None:
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
        # the screen box must hold the rings too, out to their outer edge
        reach_q = top_q if world.ring is None else max(top_q, world.ring.outer / equatorial)
        pole_on_camera = pole.dot(camera)
        q_camera = math.sqrt(camera.dot(camera) / equatorial ** 2
                             + (1.0 / polar ** 2 - 1.0 / equatorial ** 2) * pole_on_camera ** 2)
        if q_camera < reach_q:
            x0, y0, x1, y1 = 0, 0, width, view_h
        else:
            camera_distance = camera.length()
            centre = camera * (-1.0 / camera_distance)
            outer_angle = math.asin(min(equatorial * reach_q / camera_distance, 0.999))
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
        GL.glUniform1f(uniform("forward"), GIANT_FORWARD_SCATTERING)
        GL.glUniform1f(uniform("step_depth"), GIANT_STEP_DEPTH)
        GL.glUniform1f(uniform("step_height"), GIANT_STEP_HEIGHT)
        GL.glUniform1f(uniform("band_count"), world.band_count)
        GL.glUniform1f(uniform("band_phase"), world.band_phase)
        GL.glUniform1f(uniform("band_contrast"), world.band_contrast)
        ring = world.ring
        GL.glUniform1f(uniform("ring_on"), 0.0 if ring is None else 1.0)
        GL.glUniform1f(uniform("ring_inner"), 0.0 if ring is None else ring.inner)
        GL.glUniform1f(uniform("ring_outer"), 0.0 if ring is None else ring.outer)
        GL.glUniform1f(uniform("ring_mean"), 0.0 if ring is None else sum(ring.opacity) / len(ring.opacity))
        GL.glUniform3f(uniform("ring_colour"), *(0.0, 0.0, 0.0) if ring is None else ring.colour)
        opacity = [0.0] * JovianWorld.RING_SAMPLES if ring is None else list(ring.opacity)
        GL.glUniform1fv(uniform("ring_opacity"), JovianWorld.RING_SAMPLES, np.array(opacity, dtype=np.float32))

        spin, first_cell, cell_angles = world.cloud_state(date_time)
        prime_x = ship.attitude.camera_components(Vector3(math.cos(spin), math.sin(spin), 0.0))
        prime_y = ship.attitude.camera_components(Vector3(-math.sin(spin), math.cos(spin), 0.0))
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_3D, GiantGl._noise_texture())
        GL.glUniform1i(uniform("noise"), 0)
        GL.glUniform3f(uniform("prime_x"), prime_x.x, prime_x.y, prime_x.z)
        GL.glUniform3f(uniform("prime_y"), prime_y.x, prime_y.y, prime_y.z)
        GL.glUniform3f(uniform("cloud_offset"), *world.cloud_offset)
        GL.glUniform1f(uniform("cloud_wavelength"), GIANT_CLOUD_WAVELENGTH)
        GL.glUniform1f(uniform("cloud_stretch"), GIANT_CLOUD_STRETCH)
        GL.glUniform1f(uniform("cloud_octaves"), GIANT_CLOUD_OCTAVES)
        GL.glUniform1f(uniform("cloud_warp"), GIANT_CLOUD_WARP)
        GL.glUniform1f(uniform("cloud_gain"), GIANT_CLOUD_GAIN)
        GL.glUniform1f(uniform("cloud_contrast"), GIANT_CLOUD_CONTRAST * world.band_contrast)
        GL.glUniform1f(uniform("cloud_depth"), GIANT_CLOUD_DEPTH_WAVELENGTH)
        GL.glUniform1f(uniform("cloud_relief"), GIANT_CLOUD_RELIEF)
        GL.glUniform1f(uniform("relief_octaves"), GIANT_CLOUD_RELIEF_OCTAVES)
        GL.glUniform1f(uniform("cloud_density"), GIANT_CLOUD_DENSITY)
        GL.glUniform1f(uniform("layer_edge"), GIANT_CLOUD_LAYER_EDGE)
        GL.glUniform1f(uniform("relief_shading"), GIANT_CLOUD_RELIEF_SHADING)
        GL.glUniform1f(uniform("cell_first"), first_cell)
        GL.glUniform1f(uniform("cell_count"), len(cell_angles))
        GL.glUniform1fv(uniform("cell_angle"), len(cell_angles), np.array(cell_angles, dtype=np.float32))

        GiantGl._set_flashes(uniform, world, date_time, spin, ship, camera, equatorial)
        GiantGl._set_storms(uniform, world, date_time, spin, ship, camera, equatorial)

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
