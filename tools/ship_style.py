"""The look of the ship pictures, in one place: the colours, the camera, the light and the render settings that every
Blender script for the ships reads (tools/render_ship.py), so that all their pictures agree.

Change a value here and every picture made from it changes; nothing else holds these values. A text prompt for an image
generator, if one is ever used, should be written from the same values (see prompt_for_image_generator), so that both
kinds of picture share one style. The style is grey steel, dusty and worn, on a generic grey moon under a black sky, as
the game icon and the outpost are.
"""

from __future__ import annotations

# Colours, as sRGB 0..1 (the same grey steel and amber as the game icon and the outpost texture).
HULL = (0.42, 0.45, 0.50)  # the grey steel of the hull
HULL_DARK = (0.14, 0.15, 0.18)  # the seams, the recesses
AMBER = (0.93, 0.66, 0.16)  # the stripes and the hazard bands
GLASS = (0.10, 0.16, 0.22)  # the windscreen: dark, with a sky reflection
MOON = (0.24, 0.245, 0.26)  # the regolith: dark, like real regolith under a sun with no air
SKY = (0.01, 0.01, 0.02)  # black sky; the stars are the icon's sparkles, not drawn here
HEADLIGHT = (0.60, 0.80, 1.00)  # the cool white-blue lights of the icon: they glow
HEADLIGHT_STRENGTH = 14.0

# Wear: how much dust, pits and scratches the hull shows, from 0 (new) to 1 (heavily worn).
WEAR = 0.6

# The camera: a three-quarter view from above, as the game icon is drawn.
CAMERA_LOCATION = (20.0, -24.0, 15.0)  # in metres around the ship, which stands at the origin
CAMERA_TARGET = (0.0, 0.0, 4.0)  # the point the camera looks at: the hull's middle, a little above the ground
CAMERA_LENS_MM = 50.0

# The light: one low sun from the upper left, and the moon's black sky, with no atmosphere.
SUN_DIRECTION = (-0.6, 0.4, 0.7)  # where the light comes from
SUN_STRENGTH = 3.0
SUN_ANGLE_DEG = 0.5  # the sun is far away: its light is nearly parallel, with hard shadows

# The render: the picture the outpost shows, at the size of its cargo panel.
RENDER_WIDTH = 1024
RENDER_HEIGHT = 576
RENDER_SAMPLES = 128  # Cycles samples; enough for a clean picture on the CPU in a few minutes


def prompt_for_image_generator(subject: str) -> str:
    """A text prompt for an image generator, written from the values above: the same subject in the same style. For
    the Blender pictures there is no prompt, only these values."""
    grey = "dusty, weathered grey steel" if WEAR >= 0.5 else "grey steel"
    return (
        f"{subject}, {grey}, amber stripes, dark glass windscreen, on a grey regolith moon, black starry sky, "
        "photorealistic, low sun from the upper left, three-quarter view from above"
    )
