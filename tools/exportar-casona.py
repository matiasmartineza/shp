"""Publish the dressed Blender house as the browser map.

blender -b "Casona de Playa Ancha - ambientada.blend" --python tools/exportar-casona.py
The CAD-derived base.json lives beside the Blender file.
"""
import json
from collections import defaultdict
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

root = Path(__file__).resolve().parent.parent
source = Path(bpy.data.filepath).parent
out = root / 'public' / 'assets'
plan = json.loads((source / 'base.json').read_text(encoding='utf-8'))

def plan_bounds(lo, hi):
    return lo[0], 36-hi[1], hi[0], 36-lo[1]

structure = [plan_bounds(lo, hi) for kind, lo, hi in plan if kind == 'Muros']
windows = [plan_bounds(lo, hi) for kind, lo, hi in plan if kind == 'Ventanas']
runs = defaultdict(list)
for x, y, X, Y in structure:
    if X-x > Y-y:
        runs['x', round((y+Y)/2, 3)].append((x, X))
    else:
        runs['y', round((x+X)/2, 3)].append((y, Y))

doors = []
for (axis, position), segments in runs.items():
    ordered = sorted(segments)
    for (_, a), (b, _) in zip(ordered, ordered[1:]):
        if not .3 < b-a < 4.1:
            continue
        glazed = any(
            abs((y+Y if axis == 'x' else x+X)/2-position) < .1
            and abs(((x+X if axis == 'x' else y+Y)-a-b)/2) < .15
            for x, y, X, Y in windows
        )
        if glazed:
            structure.append((a, position-.09, b, position+.09) if axis == 'x'
                             else (position-.09, a, position+.09, b))
        elif b-a <= 3.6 and position != 0:
            doors.append((axis, position, a, b))
structure += [
    (10.43, 0, 10.57, 25.5), (35.43, 14.25, 35.57, 25.5),
    (10.5, 25.43, 21.8, 25.57), (24.2, 25.43, 35.5, 25.57),
    (8, -.07, 10.5, .07), (35.5, 14.18, 38, 14.32),
    (0, 25.5, .18, 27.5),
]

def remove_faces(obj, accepts):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    faces = [face for face in bm.faces if accepts(face.calc_center_median())]
    if faces:
        bmesh.ops.delete(bm, geom=faces, context='FACES')
        bm.to_mesh(obj.data)
    bm.free()

for obj in bpy.data.collections['Muros del plano'].objects:
    material = obj.data.materials[0].name
    if material not in ('Carpintería nogal', 'Roble encerado', 'Óleo verde humo', 'Latón patinado'):
        continue

    def is_leaf(v):
        if v.z >= 2.23:
            return False
        return any(
            a+.006 < (v.x if axis == 'x' else v.y) < b-.006
            and abs((v.y if axis == 'x' else v.x)-pos) < .16
            for axis, pos, a, b in doors
        )
    remove_faces(obj, is_leaf)

for obj in bpy.data.collections['Galería cerrada'].objects:
    remove_faces(obj, lambda v: 21.805 < v.x < 24.195 and abs(v.y-25.5) < .15 and v.z < 2.76)

# Dynamic collisions use the actual imported furniture footprints. Keep thin decorations,
# chairs around tables and small objects out of the blocking list so circulation stays usable.
furniture = []
for obj in bpy.context.scene.objects:
    if obj.type != 'MESH' or 'Modelo CC0' not in obj:
        continue
    if not obj.name.startswith(('Cama ', 'Catre ', 'Cómoda ', 'Sofá ', 'Mesa larga',
                                'Estante ', 'Escritorio ', 'Sillón ', 'Mueble de cocina')):
        continue
    corners = [obj.matrix_world @ Vector(p) for p in obj.bound_box]
    x, y = (min(p[i] for p in corners) for i in (0, 1))
    X, Y = (max(p[i] for p in corners) for i in (0, 1))
    if X-x > .25 and Y-y > .24 and min(p.z for p in corners) < .4:
        furniture.append(tuple(round(v, 3) for v in (x, y, X, Y)))
for i in (1, 2, 5):
    x = 8+5*(i-1)
    furniture.append((x+2.78, 28.62, x+4.13, 30.65))
for i in (1, 4, 6):
    x = 8+5*(i-1)
    furniture.append((x+3.09, 33.52, x+4.11, 35.52))
furniture.extend([(39.22, 15.11, 40.77, 17.28), (.31, 13.16, 1.10, 16.30)])
(out / 'casona-colisiones.json').write_text(
    json.dumps({'muros': structure, 'muebles': sorted(set(furniture))}, separators=(',', ':')),
    encoding='utf-8'
)

# Convert the architectural procedural materials into tiled PBR textures for WebGL.
# Imported furniture and the archival photographs keep their original textures.
procedural = [m for m in bpy.data.materials if m.use_nodes
              and any(n.type == 'TEX_NOISE' for n in m.node_tree.nodes)]
rng = np.random.default_rng(193)
size = 256

def noise(x_cells, y_cells):
    grid = rng.random((y_cells, x_cells))
    x = np.arange(size)*x_cells/size
    y = np.arange(size)*y_cells/size
    xi, yi = x.astype(int), y.astype(int)
    xf, yf = x-xi, y-yi
    xf, yf = xf*xf*(3-2*xf), yf*yf*(3-2*yf)
    a = grid[yi[:, None], xi[None, :]]
    b = grid[yi[:, None], ((xi+1)%x_cells)[None, :]]
    c = grid[((yi+1)%y_cells)[:, None], xi[None, :]]
    d = grid[((yi+1)%y_cells)[:, None], ((xi+1)%x_cells)[None, :]]
    return (a*(1-xf)+b*xf)*(1-yf[:, None])+(c*(1-xf)+d*xf)*yf[:, None]

tile_materials = {'Roble encerado', 'Carpintería nogal', 'Cal envejecida', 'Óleo verde humo',
                  'Tejuela de arcilla', 'Tierra y ripio', 'Manchas de humedad superpuestas'}
texture_materials = set()
for material in procedural:
    nt = material.node_tree
    bs = nt.nodes.get('Principled BSDF')
    for name in ('Base Color', 'Normal'):
        for link in list(bs.inputs[name].links):
            nt.links.remove(link)
    base = np.asarray(material.diffuse_color[:3], dtype=np.float32)
    bs.inputs['Base Color'].default_value = (*base, 1)
    if material.name not in tile_materials:
        continue
    wooden = material.name in ('Roble encerado', 'Carpintería nogal')
    pattern = (noise(3, 84)*.46+noise(5, 16)*.26+.32 if wooden
               else noise(4, 4)*.36+noise(14, 14)*.22+noise(60, 58)*.13+.33)
    if material.name == 'Cal envejecida':
        pattern -= np.maximum(0, noise(6, 8)-.49)*.35
    rgb = np.clip(pattern[:, :, None]*base[None, None, :], 0, 1)
    rgb = np.where(rgb <= .0031308, rgb*12.92, 1.055*np.power(rgb, 1/2.4)-.055)
    image = bpy.data.images.new(material.name+' · mapa de color', size, size, alpha=False)
    image.pixels.foreach_set(np.concatenate([rgb, np.ones((size, size, 1))], axis=2).astype(np.float32).ravel())
    image.pack()
    node = nt.nodes.new('ShaderNodeTexImage')
    node.image = image
    nt.links.new(node.outputs['Color'], bs.inputs['Base Color'])
    texture_materials.add(material.name)

processed = set()
for obj in bpy.context.scene.objects:
    if obj.type != 'MESH' or obj.data in processed:
        continue
    data = obj.data
    if not data.materials or data.materials[0].name not in texture_materials:
        continue
    processed.add(data)
    uvs = data.uv_layers.active or data.uv_layers.new()
    wood_grain = data.materials[0].name in ('Roble encerado', 'Carpintería nogal')
    for poly in data.polygons:
        axis = max(range(3), key=lambda index: abs(poly.normal[index]))
        axes = ((1, 2), (0, 2), (0, 1))[axis]
        for i in poly.loop_indices:
            p = data.vertices[data.loops[i].vertex_index].co
            uvs.data[i].uv = (p[axes[0]]*.8, p[axes[1]]*(2.3 if wood_grain else .79))

glass = bpy.data.materials['Vidrio antiguo']
nt = glass.node_tree
bs = nt.nodes.get('Principled BSDF')
nt.links.new(bs.outputs[0], nt.nodes.get('Material Output').inputs[0])
bs.inputs['Base Color'].default_value = (.34, .43, .40, 1)
bs.inputs['Alpha'].default_value = .11

bpy.ops.export_scene.gltf(
    filepath=str(out / 'casona-ambientada.glb'),
    export_cameras=False, export_lights=False, export_yup=True,
    export_image_format='JPEG', export_jpeg_quality=85,
    export_draco_mesh_compression_enable=True
)

