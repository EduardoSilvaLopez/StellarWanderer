"""Render the cargo ship with Blender, in the look of tools/ship_style.py.

Run from the project root, headless (Blender 5.2 is installed at its default place):
    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup --python tools/render_ship.py

It builds the scene from nothing each time, so the picture only depends on this script and on ship_style.py. The output
is common/resources/presentation/cargo_ship_render.png. The hull is a prism with a sloped windscreen at the front, the
only window; the legs hang from its bottom corners to landing pads; the moon is a displaced grey plane with rocks.
"""

from __future__ import annotations
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ship_style as style  # noqa: E402

ROOT = os.path.join(HERE, '..')
OUTPUT = os.path.join(ROOT, 'common', 'resources', 'presentation', 'cargo_ship_render.png')

LENGTH, WIDTH, HEIGHT = 17.0, 7.5, 6.0  # the hull, in metres
HOOD = 2.2  # the windscreen takes this much of the height at the front
LEG = 1.8  # from the ground to the hull's bottom


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def material(name: str, colour, roughness: float, bump: float = 0.0, wear: float = 0.0,
             emission=None, emission_strength: float = 0.0) -> bpy.types.Material:
    """A Principled material. `bump` raises a noise relief; `wear` roughens the surface, unevenly, with the noise."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*colour, 1.0)
    bsdf.inputs['Roughness'].default_value = roughness
    if emission is not None:
        bsdf.inputs['Emission Color'].default_value = (*emission, 1.0)
        bsdf.inputs['Emission Strength'].default_value = emission_strength
    if bump or wear:
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 70.0
        noise.inputs['Detail'].default_value = 12.0
        if bump:
            bump_node = nodes.new('ShaderNodeBump')
            bump_node.inputs['Strength'].default_value = bump
            links.new(noise.outputs['Fac'], bump_node.inputs['Height'])
            links.new(bump_node.outputs['Normal'], bsdf.inputs['Normal'])
        if wear:
            scaled = nodes.new('ShaderNodeMath')
            scaled.operation = 'MULTIPLY'
            scaled.inputs[1].default_value = 0.35 * wear
            added = nodes.new('ShaderNodeMath')
            added.operation = 'ADD'
            added.inputs[1].default_value = roughness
            links.new(noise.outputs['Fac'], scaled.inputs[0])
            links.new(scaled.outputs['Value'], added.inputs[0])
            links.new(added.outputs['Value'], bsdf.inputs['Roughness'])
    return mat


def hull_mesh(name: str, hull_material, glass_material) -> bpy.types.Object:
    """A prism in the side profile (length along x, height along z), extruded across the width, with its front top cut
    back into the windscreen. The windscreen is the one face that points forward and up: it takes the glass."""
    bottom = LEG
    profile = [(-LENGTH / 2, 0.0), (LENGTH / 2, 0.0), (LENGTH / 2, HEIGHT - HOOD),
               (LENGTH / 2 - HOOD, HEIGHT), (-LENGTH / 2, HEIGHT)]
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rows = []
    for y in (-WIDTH / 2, WIDTH / 2):
        rows.append([bm.verts.new((x, y, z + bottom)) for x, z in profile])
    neg, pos = rows
    bm.faces.new(neg)
    bm.faces.new(list(reversed(pos)))
    for i in range(len(profile)):
        j = (i + 1) % len(profile)
        bm.faces.new((neg[i], neg[j], pos[j], pos[i]))
    bm.normal_update()
    # The windscreen is the sloped face: the one whose centre is at the front, high up, under the top.
    for face in bm.faces:
        c = face.calc_center_median()
        is_windscreen = c.x > LENGTH / 4 and c.z > LEG + HEIGHT - HOOD + 0.1 and abs(face.normal.z) > 0.3
        face.material_index = 1 if is_windscreen else 0
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(hull_material)
    mesh.materials.append(glass_material)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bevel = obj.modifiers.new('Bevel', 'BEVEL')
    bevel.width = 0.12
    bevel.segments = 2
    bevel.limit_method = 'ANGLE'
    return obj


def box(name: str, location, scale, mat) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def cylinder(name: str, location, radius: float, depth: float, mat) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=radius, depth=depth, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def ship(mats: dict) -> None:
    hull = hull_mesh('Hull', mats['hull'], mats['glass'])
    bpy.context.view_layer.objects.active = hull
    # The amber stripes along both sides, and the hazard band under the nose.
    for side in (-1, 1):
        box(f'Stripe{side}', (0.0, side * (WIDTH / 2 + 0.02), LEG + HEIGHT * 0.52), (LENGTH * 0.86, 0.05, 0.32),
            mats['amber'])
    box('Hazard', (LENGTH / 2 + 0.02, 0.0, LEG + 0.5), (0.05, WIDTH * 0.7, 0.3), mats['amber'])
    # The headlights, cool white-blue, on the nose, low down.
    for side in (-1, 1):
        box(f'Headlight{side}', (LENGTH / 2 + 0.03, side * WIDTH * 0.3, LEG + 1.4), (0.05, 0.55, 0.32),
            mats['headlight'])
    # The rivets and seams are the bump of the hull; the top has a hatch and two vents.
    for x, y in ((-3.0, 0.0), (1.5, 0.0)):
        box('Hatch', (x, y, LEG + HEIGHT + 0.03), (1.6, 1.6, 0.06), mats['hull_dark'])
    for x in (-5.0, -4.0, -3.0):
        for y in (-WIDTH * 0.25, WIDTH * 0.25):
            box('Vent', (x, y, LEG + HEIGHT + 0.03), (0.35, 0.8, 0.05), mats['hull_dark'])
    # The four legs: struts from the bottom corners to the ground, each with a landing pad.
    for x in (-LENGTH / 2 + 2.6, LENGTH / 2 - 2.6):
        for y in (-WIDTH * 0.32, WIDTH * 0.32):
            cylinder('Leg', (x, y, LEG / 2), 0.2, LEG + 0.1, mats['leg'])
            box('Pad', (x, y, 0.09), (1.1, 1.1, 0.18), mats['leg_dark'])


def moon(mats: dict, rng: random.Random) -> None:
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=200, y_subdivisions=200, size=240.0, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = 'Moon'
    ground.data.materials.append(mats['moon'])
    texture = bpy.data.textures.new('MoonRelief', 'CLOUDS')
    texture.noise_scale = 3.0
    texture.noise_depth = 5
    displace = ground.modifiers.new('Relief', 'DISPLACE')
    displace.texture = texture
    displace.strength = 0.35
    displace.mid_level = 0.5
    for _ in range(38):  # rocks of regolith, scattered, some near the ship
        radius = rng.uniform(0.12, 0.9)
        x, y = rng.uniform(-14, 14), rng.uniform(-12, 12)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=radius, location=(x, y, radius * 0.25))
        rock = bpy.context.active_object
        rock.data.materials.append(mats['moon'])
        rock.scale = (1.0, 1.0, rng.uniform(0.5, 0.8))


def lights_and_camera() -> None:
    sun = bpy.data.lights.new('Sun', 'SUN')
    sun.energy = style.SUN_STRENGTH
    sun.angle = math.radians(style.SUN_ANGLE_DEG)
    sun_obj = bpy.data.objects.new('Sun', sun)
    bpy.context.collection.objects.link(sun_obj)
    direction = -Vector(style.SUN_DIRECTION).normalized()
    sun_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

    camera = bpy.data.cameras.new('Camera')
    camera.lens = style.CAMERA_LENS_MM
    camera_obj = bpy.data.objects.new('Camera', camera)
    bpy.context.collection.objects.link(camera_obj)
    location = Vector(style.CAMERA_LOCATION)
    camera_obj.location = location
    camera_obj.rotation_euler = (Vector(style.CAMERA_TARGET) - location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = camera_obj


def world() -> None:
    scene = bpy.context.scene
    scene.world = bpy.data.worlds.new('Sky')
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes['Background']
    background.inputs['Color'].default_value = (*style.SKY, 1.0)
    background.inputs['Strength'].default_value = 1.0


def render() -> None:
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = style.RENDER_SAMPLES
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = 'Standard'
    scene.render.resolution_x = style.RENDER_WIDTH
    scene.render.resolution_y = style.RENDER_HEIGHT
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = os.path.abspath(OUTPUT)
    bpy.ops.render.render(write_still=True)


def main() -> None:
    clear_scene()
    rng = random.Random(2027)
    mats = {
        'hull': material('Hull', style.HULL, roughness=0.55, bump=0.9, wear=style.WEAR),
        'hull_dark': material('HullDark', style.HULL_DARK, roughness=0.7, bump=0.5, wear=style.WEAR),
        'glass': material('Glass', style.GLASS, roughness=0.05),
        'amber': material('Amber', style.AMBER, roughness=0.4),
        'headlight': material('Headlight', style.HEADLIGHT, roughness=0.2, emission=style.HEADLIGHT,
                              emission_strength=style.HEADLIGHT_STRENGTH),
        'leg': material('Leg', style.HULL_DARK, roughness=0.6, bump=0.2, wear=style.WEAR),
        'leg_dark': material('LegDark', (0.08, 0.08, 0.09), roughness=0.8),
        'moon': material('Moon', style.MOON, roughness=0.95, bump=1.2, wear=0.5),
    }
    world()
    moon(mats, rng)
    ship(mats)
    lights_and_camera()
    render()
    print(f'Rendered {os.path.abspath(OUTPUT)}')


if __name__ == '__main__':
    main()
