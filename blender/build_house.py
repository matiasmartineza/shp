"""
Construye la casa sucia del juego y la exporta a public/assets/casa.glb.

Uso (desde la raíz del repo):
    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup -P blender/build_house.py

Coordenadas Blender (Z arriba, metros). La casa va de x=0..14, y=0..10.
  Frente (puerta principal) en y=0, mirando hacia -y (la calle).
  Living-comedor  x 0..8,  y 0..5
  Cocina          x 8..14, y 0..5
  Dormitorio 1    x 0..5,  y 5..10
  Baño            x 5..9,  y 5..10
  Dormitorio 2    x 9..14, y 5..10

Propiedades personalizadas (se exportan como "extras" en glTF y el juego las lee):
  colision=True           -> el jugador no lo atraviesa
  interaccion="puerta"    -> puerta cerrada, falta la llave
  interaccion="interruptor", habitacion=...  -> enciende/apaga la luz
  interaccion="ventana", texto=...           -> mensaje al mirar
  lampara=<habitacion>    -> el juego pone una luz aquí
  anim=...                -> animación de vecinos (la hace el juego)
  rol=...                 -> partes animadas (brazos, piernas)
"""
import bpy, bmesh, math, os, random, sys
import numpy as np
from mathutils import Matrix, Vector

# ----------------------------------------------------------------- rutas
try:
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    ROOT = os.getcwd()
TEXDIR = os.path.join(ROOT, "blender", "textures")
OUT_GLB = os.path.join(ROOT, "public", "assets", "casa.glb")
OUT_BLEND = os.path.join(ROOT, "blender", "casa.blend")
os.makedirs(TEXDIR, exist_ok=True)
os.makedirs(os.path.dirname(OUT_GLB), exist_ok=True)

random.seed(7)
H = 2.7   # alto de muros
T = 0.15  # grosor de muros

# ----------------------------------------------------------------- limpiar escena
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for c in list(bpy.data.collections):
    bpy.data.collections.remove(c)

COLLS = {}
def coll(name):
    if name not in COLLS:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
        COLLS[name] = c
    return COLLS[name]

# ----------------------------------------------------------------- texturas procedurales (sucias)
N = 512

def vnoise(n, cells, seed):
    rng = np.random.default_rng(seed)
    g = rng.random((cells, cells))
    t = np.arange(n) * cells / n
    i0 = t.astype(int) % cells
    f = t - np.floor(t)
    f = f * f * (3 - 2 * f)
    i1 = (i0 + 1) % cells
    a = g[np.ix_(i0, i0)]; b = g[np.ix_(i0, i1)]
    c = g[np.ix_(i1, i0)]; d = g[np.ix_(i1, i1)]
    fy = f[:, None]; fx = f[None, :]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy

def fbm(n, base, octs, seed):
    tot = np.zeros((n, n)); amp = 1.0; norm = 0.0
    for k in range(octs):
        tot += vnoise(n, base * 2 ** k, seed + k) * amp
        norm += amp; amp *= 0.5
    return tot / norm

def grime(seed, amount=1.0):
    g = fbm(N, 4, 5, seed)
    stains = np.clip((g - 0.52) * 4, 0, 1)
    spots = np.clip((fbm(N, 16, 3, seed + 50) - 0.6) * 6, 0, 1)
    return np.clip((stains * 0.75 + spots * 0.55) * amount, 0, 1)

def dirty(rgb, d, col=(0.17, 0.12, 0.07), k=0.75):
    d = d[..., None] * k
    return rgb * (1 - d) + np.array(col) * d

def save_img(name, rgb):
    a = np.ones((N, N, 1))
    px = np.concatenate([np.clip(rgb, 0, 1), a], axis=2).astype(np.float32)
    img = bpy.data.images.new(name, N, N, alpha=False)
    img.pixels.foreach_set(px.ravel())
    path = os.path.join(TEXDIR, name + ".png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    img.filepath = "//textures/" + name + ".png"
    return img

yy, xx = np.mgrid[0:N, 0:N]
rng = np.random.default_rng(3)

# Madera sucia
plank = yy // 64
var = rng.uniform(0.75, 1.1, size=8)[plank]
offs = rng.integers(0, N, size=8)[plank]
grain = np.sin(xx * 0.03 + fbm(N, 8, 3, 7) * 12) * 0.5 + 0.5
wood = np.array([0.42, 0.28, 0.16]) * ((0.8 + 0.25 * grain) * var)[..., None]
seam = ((yy % 64) < 2) | (((xx + offs) % 256) < 2)
wood[seam] *= 0.35
IMG_WOOD = save_img("piso_madera_sucio", dirty(wood, grime(11)))

# Baldosa sucia
tile_var = rng.uniform(0.9, 1.05, size=(4, 4))[yy // 128, xx // 128]
tile = np.array([0.80, 0.78, 0.70]) * tile_var[..., None]
grout = ((xx % 128) < 4) | ((yy % 128) < 4)
tile[grout] = (0.24, 0.21, 0.17)
IMG_TILE = save_img("piso_baldosa_sucio", dirty(tile, grime(21, 1.2), col=(0.2, 0.17, 0.08)))

# Muro sucio con chorreos
wallc = np.array([0.80, 0.76, 0.66]) * (0.92 + 0.1 * fbm(N, 3, 3, 31))[..., None]
cols = vnoise(N, 48, 40)[0]
drip = np.clip((cols - 0.6) * 5, 0, 1)[None, :] * (yy / N)
IMG_WALL = save_img("muro_sucio", dirty(wallc, np.clip(grime(33, 0.8) + drip * 0.6, 0, 1), col=(0.3, 0.25, 0.15)))

# Azulejo de baño con moho
az = np.array([0.72, 0.82, 0.80]) * tile_var[..., None]
az[((xx % 64) < 3) | ((yy % 64) < 3)] = (0.25, 0.27, 0.2)
mold = np.clip((fbm(N, 6, 5, 77) - 0.5) * 5, 0, 1)
IMG_AZ = save_img("azulejo_moho", dirty(az, mold, col=(0.08, 0.12, 0.05), k=0.85))

# ----------------------------------------------------------------- materiales
def lin(c):
    return tuple(v ** 2.2 for v in c)

MATS = {}
def mat(name, color=(0.8, 0.8, 0.8), rough=0.8, img=None, alpha=None, emit=None, strength=4.0, metal=0.0):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    if m.node_tree is None:  # Blender < 5 crea los nodos solo con use_nodes
        m.use_nodes = True
    nt = m.node_tree
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    c = lin(color)
    p.inputs["Base Color"].default_value = (*c, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if img is not None:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img
        nt.links.new(t.outputs["Color"], p.inputs["Base Color"])
    if alpha is not None:
        p.inputs["Alpha"].default_value = alpha
        for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
            try:
                setattr(m, attr, val)
            except Exception:
                pass
    if emit is not None:
        p.inputs["Emission Color"].default_value = (*lin(emit), 1)
        p.inputs["Emission Strength"].default_value = strength
    m.diffuse_color = (*c, alpha if alpha is not None else 1)
    MATS[name] = m
    return m

M = dict(
    madera=mat("Piso madera sucio", img=IMG_WOOD),
    baldosa=mat("Piso baldosa sucio", img=IMG_TILE),
    muro=mat("Muro sucio", img=IMG_WALL, rough=0.9),
    azulejo=mat("Azulejo con moho", img=IMG_AZ, rough=0.5),
    techo=mat("Techo manchado", (0.70, 0.66, 0.56), 0.95),
    vidrio=mat("Vidrio sucio", (0.62, 0.6, 0.5), 0.2, alpha=0.16),
    esmerilado=mat("Vidrio esmerilado", (0.55, 0.6, 0.5), 0.6, alpha=0.85),
    marco=mat("Marco ventana", (0.75, 0.72, 0.62), 0.7),
    puerta=mat("Puerta", (0.36, 0.22, 0.12), 0.6),
    metal=mat("Metal", (0.7, 0.7, 0.68), 0.3, metal=1.0),
    lampara=mat("Ampolleta", (1, 0.9, 0.7), 0.4, emit=(1, 0.85, 0.6), strength=6),
    interruptor=mat("Interruptor", (0.88, 0.86, 0.8), 0.5),
    sofa=mat("Tela sofa", (0.35, 0.40, 0.30), 0.95),
    mesa=mat("Madera muebles", (0.45, 0.30, 0.18), 0.6),
    blanco=mat("Ceramica blanca", (0.85, 0.85, 0.8), 0.25),
    nevera=mat("Refrigerador", (0.82, 0.82, 0.78), 0.35),
    meson=mat("Meson", (0.55, 0.52, 0.48), 0.5),
    negro=mat("Negro", (0.04, 0.04, 0.04), 0.4),
    pantalla=mat("Pantalla apagada", (0.02, 0.02, 0.03), 0.15),
    colchon=mat("Colchon manchado", (0.78, 0.74, 0.62), 0.9),
    sabana=mat("Sabana", (0.42, 0.45, 0.6), 0.9),
    alfombra=mat("Alfombra", (0.45, 0.18, 0.15), 1.0),
    carton=mat("Carton", (0.62, 0.48, 0.3), 0.9),
    papel=mat("Papel", (0.85, 0.83, 0.75), 0.9),
    bolsa=mat("Bolsa basura", (0.03, 0.03, 0.03), 0.25),
    botella_v=mat("Botella verde", (0.1, 0.35, 0.12), 0.1, alpha=0.75),
    botella_c=mat("Botella cafe", (0.35, 0.18, 0.05), 0.1, alpha=0.8),
    mancha=mat("Mancha", (0.16, 0.11, 0.06), 0.3, alpha=0.75),
    mancha_osc=mat("Mancha oscura", (0.08, 0.06, 0.04), 0.2, alpha=0.85),
    moho=mat("Moho", (0.12, 0.18, 0.08), 1.0, alpha=0.85),
    grasa=mat("Grasa", (0.25, 0.18, 0.06), 0.2, alpha=0.6),
    telarana=mat("Telarana", (0.85, 0.85, 0.85), 1.0, alpha=0.3),
    comida=mat("Comida podrida", (0.35, 0.3, 0.08), 0.8),
    ropa1=mat("Ropa azul", (0.2, 0.3, 0.55), 1.0),
    ropa2=mat("Ropa roja", (0.6, 0.15, 0.12), 1.0),
    ropa3=mat("Ropa gris", (0.45, 0.45, 0.45), 1.0),
    # exterior
    pasto=mat("Pasto", (0.28, 0.45, 0.18), 1.0),
    asfalto=mat("Asfalto", (0.18, 0.18, 0.19), 0.9),
    vereda=mat("Vereda", (0.6, 0.58, 0.55), 0.9),
    linea=mat("Linea calle", (0.9, 0.85, 0.3), 0.8),
    fachada=mat("Fachada vecinos", (0.85, 0.78, 0.6), 0.85),
    fachada2=mat("Fachada vecinos 2", (0.62, 0.72, 0.8), 0.85),
    techo_rojo=mat("Teja", (0.55, 0.2, 0.12), 0.8),
    interior_vec=mat("Muro vecinos", (0.95, 0.9, 0.75), 0.9),
    piso_vec=mat("Piso vecinos", (0.6, 0.45, 0.3), 0.6),
    tv_on=mat("Pantalla TV", (0.3, 0.5, 0.9), 0.2, emit=(0.4, 0.6, 1.0), strength=3),
    tronco=mat("Tronco", (0.32, 0.22, 0.14), 0.9),
    hojas=mat("Hojas", (0.22, 0.42, 0.16), 0.9),
    cerca=mat("Cerca", (0.6, 0.5, 0.38), 0.9),
    auto=mat("Auto", (0.15, 0.3, 0.6), 0.3, metal=0.4),
    rueda=mat("Rueda", (0.05, 0.05, 0.05), 0.8),
    piel=mat("Piel", (0.85, 0.65, 0.5), 0.7),
    piel2=mat("Piel 2", (0.55, 0.38, 0.26), 0.7),
    pelo=mat("Pelo", (0.15, 0.1, 0.06), 0.8),
    pelo2=mat("Pelo canoso", (0.7, 0.7, 0.68), 0.8),
    polera1=mat("Polera amarilla", (0.9, 0.7, 0.2), 0.9),
    polera2=mat("Polera verde", (0.2, 0.55, 0.3), 0.9),
    polera3=mat("Polera roja", (0.75, 0.2, 0.2), 0.9),
    polera4=mat("Polera morada", (0.5, 0.3, 0.6), 0.9),
    jeans=mat("Jeans", (0.2, 0.25, 0.4), 0.9),
    pantalon=mat("Pantalon cafe", (0.35, 0.28, 0.2), 0.9),
    perro=mat("Perro", (0.6, 0.42, 0.22), 0.9),
    pelota=mat("Pelota", (0.9, 0.2, 0.15), 0.5),
    flores=mat("Flores", (0.9, 0.3, 0.5), 0.8),
)

# ----------------------------------------------------------------- geometría básica
def _finish(name, bm, m, c, parent, loc, rot, uvscale, props):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    uvl = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            co = l.vert.co
            if ax == 0:
                uv = (co.y, co.z)
            elif ax == 1:
                uv = (co.x, co.z)
            else:
                uv = (co.x, co.y)
            l[uvl].uv = (uv[0] / uvscale, uv[1] / uvscale)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    coll(c).objects.link(o)
    o.data.materials.append(m)
    if parent is not None:
        o.parent = parent
    o.location = loc
    o.rotation_euler = [math.radians(a) for a in rot]
    for k, v in props.items():
        o[k] = v
    return o

def box(name, x0, y0, z0, x1, y1, z1, m, c="Casa", parent=None, rot=(0, 0, 0), uvscale=2.0, **props):
    """Caja definida por sus esquinas (coordenadas del padre). La rotación es alrededor de su centro."""
    cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)), verts=bm.verts)
    if rot == (0, 0, 0):
        # sin rotación: geometría en coordenadas absolutas para que las UV sean continuas entre muros
        bmesh.ops.translate(bm, vec=(cx, cy, cz), verts=bm.verts)
        return _finish(name, bm, m, c, parent, (0, 0, 0), rot, uvscale, props)
    return _finish(name, bm, m, c, parent, (cx, cy, cz), rot, uvscale, props)

def cyl(name, cx, cy, z0, z1, r, m, c="Casa", seg=12, r2=None, parent=None, rot=(0, 0, 0), sx=1.0, sy=1.0, **props):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                          radius1=r, radius2=r if r2 is None else r2, depth=z1 - z0)
    bmesh.ops.scale(bm, vec=(sx, sy, 1), verts=bm.verts)
    return _finish(name, bm, m, c, parent, (cx, cy, (z0 + z1) / 2), rot, 1.0, props)

def sphere(name, cx, cy, cz, r, m, c="Casa", parent=None, scale=(1, 1, 1), rot=(0, 0, 0), seg=12, **props):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(6, seg * 2 // 3), radius=r)
    bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    return _finish(name, bm, m, c, parent, (cx, cy, cz), rot, 1.0, props)

def poly(name, verts, faces, m, c="Casa", **props):
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    for f in faces:
        bm.faces.new([vs[i] for i in f])
    return _finish(name, bm, m, c, None, (0, 0, 0), (0, 0, 0), 2.0, props)

def empty(name, loc, rot=(0, 0, 0), c="Vecinos", parent=None, **props):
    e = bpy.data.objects.new(name, None)
    coll(c).objects.link(e)
    e.empty_display_size = 0.3
    if parent is not None:
        e.parent = parent
    e.location = loc
    e.rotation_euler = [math.radians(a) for a in rot]
    for k, v in props.items():
        e[k] = v
    return e

def wall(name, along, fixed, a0, a1, openings=(), m=None, c="Casa", h=H, t=T, z0=0.0):
    """Muro alineado a un eje con vanos (inicio, fin, alto_inferior, alto_superior)."""
    m = m or M["muro"]
    segs, cur = [], a0
    for (s, e, b, tp) in sorted(openings):
        if s > cur:
            segs.append((cur, s, 0, h))
        if b > 0:
            segs.append((s, e, 0, b))
        if tp < h:
            segs.append((s, e, tp, h))
        cur = e
    if cur < a1:
        segs.append((cur, a1, 0, h))
    for i, (s, e, zb, zt) in enumerate(segs):
        if along == "x":
            box(f"{name}_{i}", s, fixed - t / 2, z0 + zb, e, fixed + t / 2, z0 + zt, m, c, colision=True)
        else:
            box(f"{name}_{i}", fixed - t / 2, s, z0 + zb, fixed + t / 2, e, z0 + zt, m, c, colision=True)

def window(name, along, fixed, s, e, b, tp, texto, glass=None, c="Casa", t=T):
    glass = glass or M["vidrio"]
    fw = 0.05
    if along == "x":
        box(f"{name}_vidrio", s, fixed - 0.01, b, e, fixed + 0.01, tp, glass, c,
            colision=True, interaccion="ventana", texto=texto)
        box(f"{name}_marco_inf", s, fixed - t / 2 - 0.03, b - 0.02, e, fixed + t / 2 + 0.03, b + 0.03, M["marco"], c)
        box(f"{name}_marco_sup", s, fixed - t / 2, tp - fw, e, fixed + t / 2, tp, M["marco"], c)
        box(f"{name}_marco_izq", s, fixed - t / 2, b, s + fw, fixed + t / 2, tp, M["marco"], c)
        box(f"{name}_marco_der", e - fw, fixed - t / 2, b, e, fixed + t / 2, tp, M["marco"], c)
        box(f"{name}_marco_mid", (s + e) / 2 - 0.025, fixed - 0.04, b, (s + e) / 2 + 0.025, fixed + 0.04, tp, M["marco"], c)
    else:
        box(f"{name}_vidrio", fixed - 0.01, s, b, fixed + 0.01, e, tp, glass, c,
            colision=True, interaccion="ventana", texto=texto)
        box(f"{name}_marco_inf", fixed - t / 2 - 0.03, s, b - 0.02, fixed + t / 2 + 0.03, e, b + 0.03, M["marco"], c)
        box(f"{name}_marco_sup", fixed - t / 2, s, tp - fw, fixed + t / 2, e, tp, M["marco"], c)
        box(f"{name}_marco_izq", fixed - t / 2, s, b, fixed + t / 2, s + fw, tp, M["marco"], c)
        box(f"{name}_marco_der", fixed - t / 2, e - fw, b, fixed + t / 2, e, tp, M["marco"], c)
        box(f"{name}_marco_mid", fixed - 0.04, (s + e) / 2 - 0.025, b, fixed + 0.04, (s + e) / 2 + 0.025, tp, M["marco"], c)

# =================================================================== CASA
DOOR_H = 2.1
TXT = dict(
    living="Al otro lado de la calle, la vecina te saluda desde su ventana. Por la vereda pasa un señor con su perro.",
    comedor="Un señor pasea a su perro por la vereda. Enfrente, el vecino riega sus plantas.",
    cocina="El vecino de enfrente riega las plantas del jardín sin apuro.",
    dorm1="En el patio del lado, una vecina tiende ropa. Allá afuera todo parece limpio y normal.",
    dorm2="Un niño juega con una pelota en el patio del vecino.",
    bano="El vidrio es esmerilado y está cubierto de moho. No se ve nada.",
)

# Pisos
box("Piso_living", 0, 0, -0.1, 8, 5, 0, M["madera"])
box("Piso_cocina", 8, 0, -0.1, 14, 5, 0, M["baldosa"], uvscale=2.0)
box("Piso_dorm1", 0, 5, -0.1, 5, 10, 0, M["madera"])
box("Piso_bano", 5, 5, -0.1, 9, 10, 0, M["baldosa"], uvscale=1.5)
box("Piso_dorm2", 9, 5, -0.1, 14, 10, 0, M["madera"])
box("Techo", -T / 2, -T / 2, H, 14 + T / 2, 10 + T / 2, H + 0.1, M["techo"])

# Muros exteriores
wall("Muro_frente", "x", 0, -T / 2, 14 + T / 2, [
    (1.0, 2.8, 0.9, 2.1),          # ventana living
    (4.2, 5.2, 0.0, DOOR_H),       # puerta principal
    (6.0, 7.4, 0.9, 2.1),          # ventana comedor
    (10.5, 12.5, 0.9, 2.1),        # ventana cocina
])
wall("Muro_fondo", "x", 10, -T / 2, 14 + T / 2, [(6.5, 7.5, 1.5, 2.2)])  # ventana baño
wall("Muro_oeste", "y", 0, T / 2, 10 - T / 2, [(6.5, 8.5, 0.9, 2.1)])    # ventana dormitorio 1
wall("Muro_este", "y", 14, T / 2, 10 - T / 2, [(6.5, 8.5, 0.9, 2.1)])    # ventana dormitorio 2

# Muros interiores
wall("Muro_central", "x", 5, T / 2, 14 - T / 2, [
    (2.0, 3.0, 0, DOOR_H),    # dormitorio 1
    (6.5, 7.5, 0, DOOR_H),    # baño
    (9.4, 10.3, 0, DOOR_H),   # dormitorio 2 (desde la cocina)
])
wall("Muro_cocina", "y", 8, T / 2, 5 - T / 2, [(1.4, 3.6, 0, DOOR_H)])
wall("Muro_dorm1_bano", "y", 5, 5 + T / 2, 10 - T / 2)
wall("Muro_bano_dorm2", "y", 9, 5 + T / 2, 10 - T / 2)

# Azulejos del baño (revestimiento hasta 1.6 m)
for nm, args in {
    "Azulejo_O": (5 + T / 2, 5 + T / 2, 0, 5 + T / 2 + 0.01, 10 - T / 2, 1.6),
    "Azulejo_E": (9 - T / 2 - 0.01, 5 + T / 2, 0, 9 - T / 2, 10 - T / 2, 1.6),
    "Azulejo_N": (5 + T / 2, 10 - T / 2 - 0.01, 0, 9 - T / 2, 10 - T / 2, 1.5),
}.items():
    box(nm, *args, M["azulejo"], uvscale=1.0)

# Ventanas
window("Ventana_living", "x", 0, 1.0, 2.8, 0.9, 2.1, TXT["living"])
window("Ventana_comedor", "x", 0, 6.0, 7.4, 0.9, 2.1, TXT["comedor"])
window("Ventana_cocina", "x", 0, 10.5, 12.5, 0.9, 2.1, TXT["cocina"])
window("Ventana_bano", "x", 10, 6.5, 7.5, 1.5, 2.2, TXT["bano"], glass=M["esmerilado"])
window("Ventana_dorm1", "y", 0, 6.5, 8.5, 0.9, 2.1, TXT["dorm1"])
window("Ventana_dorm2", "y", 14, 6.5, 8.5, 0.9, 2.1, TXT["dorm2"])

# Puerta principal (cerrada con llave)
door = box("Puerta_principal", 4.22, -0.04, 0.0, 5.18, 0.04, DOOR_H - 0.02, M["puerta"],
           colision=True, interaccion="puerta")
for i, z in enumerate((0.5, 1.55)):
    box(f"Puerta_panel_{i}", 4.35, 0.04, z, 5.05, 0.06, z + 0.45, M["puerta"], parent=door)
sphere("Puerta_manilla", 5.02, 0.11, 1.0, 0.04, M["metal"], parent=door)
box("Puerta_cerradura", 4.99, 0.04, 1.12, 5.05, 0.07, 1.2, M["metal"], parent=door)
box("Puerta_marco_izq", 4.15, -T / 2 - 0.02, 0, 4.22, T / 2 + 0.02, DOOR_H, M["marco"])
box("Puerta_marco_der", 5.18, -T / 2 - 0.02, 0, 5.25, T / 2 + 0.02, DOOR_H, M["marco"])
box("Puerta_marco_sup", 4.15, -T / 2 - 0.02, DOOR_H - 0.03, 5.25, T / 2 + 0.02, DOOR_H + 0.05, M["marco"])
box("Felpudo", 4.2, 0.12, 0, 5.2, 0.7, 0.012, M["carton"])

# Lámparas de techo e interruptores
LAMPS = {
    "living": [(2.5, 2.5), (6.0, 2.5)],
    "cocina": [(11.0, 2.5)],
    "bano": [(7.0, 7.5)],
    "dorm1": [(2.5, 7.5)],
    "dorm2": [(11.5, 7.5)],
}
for room, pts in LAMPS.items():
    for i, (x, y) in enumerate(pts):
        cyl(f"Lampara_{room}_{i}_cable", x, y, H - 0.35, H, 0.01, M["negro"], seg=6)
        cyl(f"Lampara_{room}_{i}_pantalla", x, y, H - 0.5, H - 0.3, 0.28, M["techo"], seg=16, r2=0.12)
        sphere(f"Lampara_{room}_{i}", x, y, H - 0.5, 0.07, M["lampara"], lampara=room)

SWITCHES = {  # (x0, y0, x1, y1) placa del interruptor a 1.2 m
    "living": (3.85, T / 2, 3.95, T / 2 + 0.02),
    "cocina": (8 + T / 2, 0.9, 8 + T / 2 + 0.02, 1.0),
    "bano": (7.7, 5 + T / 2, 7.8, 5 + T / 2 + 0.02),
    "dorm1": (3.2, 5 + T / 2, 3.3, 5 + T / 2 + 0.02),
    "dorm2": (10.5, 5 + T / 2, 10.6, 5 + T / 2 + 0.02),
}
for room, (x0, y0, x1, y1) in SWITCHES.items():
    box(f"Interruptor_{room}", x0, y0, 1.15, x1, y1, 1.27, M["interruptor"],
        interaccion="interruptor", habitacion=room)

# ----------------------------------------------------------------- muebles
F = "Muebles"
# Living
box("Sofa_base", 0.15, 1.2, 0, 1.05, 3.8, 0.45, M["sofa"], F, colision=True)
box("Sofa_respaldo", 0.08, 1.2, 0.45, 0.35, 3.8, 0.95, M["sofa"], F)
box("Sofa_brazo_1", 0.15, 1.05, 0, 1.05, 1.25, 0.65, M["sofa"], F, colision=True)
box("Sofa_brazo_2", 0.15, 3.75, 0, 1.05, 3.95, 0.65, M["sofa"], F, colision=True)
box("Alfombra", 1.2, 1.4, 0, 3.2, 3.6, 0.01, M["alfombra"], F)
box("Mesa_centro", 1.6, 2.0, 0.35, 2.5, 3.0, 0.42, M["mesa"], F, colision=True)
for i, (x, y) in enumerate(((1.65, 2.05), (2.45, 2.05), (1.65, 2.95), (2.45, 2.95))):
    box(f"Mesa_centro_pata_{i}", x - 0.03, y - 0.03, 0, x + 0.03, y + 0.03, 0.35, M["mesa"], F)
box("Mueble_TV", 3.3, 1.8, 0, 3.7, 3.2, 0.5, M["mesa"], F, colision=True)
box("TV", 3.45, 1.9, 0.5, 3.55, 3.1, 1.2, M["negro"], F, colision=True)
box("TV_pantalla", 3.44, 1.95, 0.55, 3.45, 3.05, 1.15, M["pantalla"], F)
# Comedor
box("Mesa_comedor", 5.2, 1.8, 0.72, 6.8, 3.0, 0.78, M["mesa"], F, colision=True)
for i, (x, y) in enumerate(((5.3, 1.9), (6.7, 1.9), (5.3, 2.9), (6.7, 2.9))):
    box(f"Mesa_comedor_pata_{i}", x - 0.04, y - 0.04, 0, x + 0.04, y + 0.04, 0.72, M["mesa"], F)
for i, (x, y, r) in enumerate(((5.6, 1.45, 0), (6.4, 1.45, 8), (5.6, 3.35, -12), (6.6, 3.5, 35))):
    box(f"Silla_{i}_asiento", x - 0.22, y - 0.22, 0.42, x + 0.22, y + 0.22, 0.46, M["mesa"], F, rot=(0, 0, r), colision=True)
    box(f"Silla_{i}_patas", x - 0.2, y - 0.2, 0, x + 0.2, y + 0.2, 0.42, M["mesa"], F, rot=(0, 0, r))
box("Silla_caida", 7.2, 3.9, 0.0, 7.65, 4.35, 0.45, M["mesa"], F, rot=(0, 90, 20), colision=True)

# Cocina
box("Meson_este", 13.35, 0.3, 0, 13.92, 4.92, 0.9, M["meson"], F, colision=True)
box("Meson_fondo", 10.6, 4.35, 0, 13.35, 4.92, 0.9, M["meson"], F, colision=True)
box("Lavaplatos", 13.45, 2.0, 0.85, 13.85, 2.8, 0.91, M["metal"], F)
box("Cocina_estufa", 11.2, 4.4, 0.9, 11.9, 4.9, 0.93, M["negro"], F)
for i, (x, y) in enumerate(((11.38, 4.52), (11.72, 4.52), (11.38, 4.78), (11.72, 4.78))):
    cyl(f"Quemador_{i}", x, y, 0.93, 0.945, 0.08, M["metal"], F, seg=10)
box("Refrigerador", 8.12, 4.2, 0, 8.85, 4.92, 1.85, M["nevera"], F, colision=True)
box("Refrigerador_manilla", 8.82, 4.25, 0.9, 8.86, 4.3, 1.5, M["metal"], F)
box("Mesa_cocina", 9.9, 1.6, 0.72, 11.3, 2.6, 0.76, M["mesa"], F, colision=True)
for i, (x, y) in enumerate(((9.95, 1.65), (11.25, 1.65), (9.95, 2.55), (11.25, 2.55))):
    box(f"Mesa_cocina_pata_{i}", x - 0.03, y - 0.03, 0, x + 0.03, y + 0.03, 0.72, M["mesa"], F)
cyl("Basurero", 12.9, 0.6, 0, 0.6, 0.22, M["metal"], F, colision=True)
for i in range(4):
    sphere(f"Basurero_rebalse_{i}", 12.9 + random.uniform(-0.15, 0.15), 0.6 + random.uniform(-0.15, 0.15),
           0.65 + i * 0.05, 0.16, M["bolsa"], F, scale=(1, 1, 0.8))

# Baño
box("Tina", 5.12, 8.95, 0, 6.9, 9.92, 0.55, M["blanco"], F, colision=True)
box("Tina_interior", 5.22, 9.05, 0.25, 6.8, 9.82, 0.56, M["comida"], F)
box("Inodoro_base", 8.3, 9.0, 0, 8.75, 9.6, 0.42, M["blanco"], F, colision=True)
box("Inodoro_estanque", 8.25, 9.6, 0.42, 8.8, 9.85, 0.85, M["blanco"], F, colision=True)
cyl("Inodoro_agua", 8.525, 9.25, 0.42, 0.43, 0.17, M["comida"], F, seg=14)
box("Lavamanos", 5.12, 6.3, 0.8, 5.6, 6.9, 0.88, M["blanco"], F, colision=True)
box("Lavamanos_pie", 5.25, 6.5, 0, 5.4, 6.7, 0.8, M["blanco"], F)
box("Espejo", 5.08, 6.3, 1.25, 5.1, 6.9, 1.85, M["metal"], F)
box("Espejo_mancha", 5.1, 6.4, 1.3, 5.105, 6.7, 1.55, M["mancha_osc"], F)

# Dormitorio 1
box("Cama1", 1.2, 7.8, 0, 3.0, 9.9, 0.45, M["mesa"], F, colision=True)
box("Cama1_colchon", 1.25, 7.85, 0.45, 2.95, 9.85, 0.62, M["colchon"], F)
box("Cama1_sabana", 1.3, 7.7, 0.55, 2.4, 8.9, 0.66, M["sabana"], F, rot=(0, 0, 14))
box("Cama1_respaldo", 1.2, 9.85, 0, 3.0, 9.93, 1.1, M["mesa"], F)
box("Velador1", 3.1, 9.4, 0, 3.6, 9.9, 0.55, M["mesa"], F, colision=True)
box("Ropero", 4.25, 6.0, 0, 4.9, 8.0, 2.0, M["mesa"], F, colision=True)
box("Ropero_puerta_entreabierta", 3.75, 6.0, 0.05, 4.25, 6.05, 1.95, M["mesa"], F, rot=(0, 0, -30))

# Dormitorio 2
box("Cama2", 11.5, 7.8, 0, 13.4, 9.9, 0.45, M["mesa"], F, colision=True)
box("Cama2_colchon", 11.55, 7.85, 0.45, 13.35, 9.85, 0.6, M["colchon"], F)
box("Cama2_respaldo", 11.5, 9.85, 0, 13.4, 9.93, 1.0, M["mesa"], F)
box("Escritorio", 9.12, 8.6, 0.72, 10.4, 9.9, 0.76, M["mesa"], F, colision=True)
box("Escritorio_cajonera", 9.15, 8.65, 0, 9.6, 9.85, 0.72, M["mesa"], F)
box("Notebook", 9.6, 9.1, 0.76, 10.0, 9.4, 0.78, M["negro"], F)
box("Notebook_pantalla", 9.6, 9.38, 0.78, 10.0, 9.4, 1.05, M["negro"], F, rot=(-15, 0, 0))
box("Silla_escritorio", 9.9, 8.0, 0.0, 10.35, 8.45, 0.46, M["negro"], F, rot=(0, 0, 25), colision=True)

# ----------------------------------------------------------------- suciedad
S = "Suciedad"
def stain(name, x, y, r, sx=1.0, sy=1.0, m=None, z=0.0):
    cyl(name, x, y, z + 0.002, z + 0.006, r, m or M["mancha"], S, seg=10, sx=sx, sy=sy, rot=(0, 0, random.uniform(0, 180)))

def bag(name, x, y, s=1.0):
    sphere(name, x, y, 0.27 * s, 0.3 * s, M["bolsa"], S, scale=(1, 0.9, 0.9), colision=True)
    cyl(name + "_nudo", x, y, 0.5 * s, 0.62 * s, 0.05 * s, M["bolsa"], S, seg=6, r2=0.09 * s)

def bottle(name, x, y, lying=False, green=True, z=0.0):
    m = M["botella_v"] if green else M["botella_c"]
    if lying:
        cyl(name, x, y, z + 0.035, z + 0.035 + 0.25, 0.035, m, S, seg=8, rot=(90, 0, random.uniform(0, 360)))
    else:
        cyl(name, x, y, z, z + 0.22, 0.035, m, S, seg=8)
        cyl(name + "_cuello", x, y, z + 0.22, z + 0.29, 0.015, m, S, seg=6, r2=0.012)

def paper(name, x, y, z=0.0):
    box(name, x - 0.105, y - 0.15, z + 0.003, x + 0.105, y + 0.15, z + 0.006, M["papel"], S,
        rot=(0, 0, random.uniform(0, 180)))

def pizza(name, x, y, z=0.0, open_=False):
    box(name, x - 0.2, y - 0.2, z, x + 0.2, y + 0.2, z + 0.05, M["carton"], S, rot=(0, 0, random.uniform(0, 90)))

def clothes(name, x, y, z=0.0):
    for i in range(3):
        m = random.choice([M["ropa1"], M["ropa2"], M["ropa3"]])
        sphere(f"{name}_{i}", x + random.uniform(-0.2, 0.2), y + random.uniform(-0.2, 0.2), z + 0.06,
               0.22, m, S, scale=(1.3, 1.0, 0.25), rot=(0, 0, random.uniform(0, 180)), seg=8)

def dishes(name, x, y, z, n=5):
    for i in range(n):
        cyl(f"{name}_{i}", x + random.uniform(-0.02, 0.02), y + random.uniform(-0.02, 0.02),
            z + i * 0.025, z + i * 0.025 + 0.02, 0.12, M["blanco"], S, seg=14)
    sphere(f"{name}_resto", x, y, z + n * 0.025 + 0.02, 0.06, M["comida"], S, scale=(1.3, 1, 0.4), seg=8)

def web(name, corner, size=0.6):
    x, y, sxn, syn = corner
    z = H - 0.001
    poly(name, [(x, y, z), (x + sxn * size, y, z), (x, y + syn * size, z - 0.05),
                (x, y, z - size * 0.8)], [(0, 1, 2), (0, 2, 3), (0, 3, 1)], M["telarana"], S)

def wall_patch(name, along, fixed, a, z, w, h, m, side=1):
    if along == "x":
        y = fixed + side * (T / 2 + 0.003)
        box(name, a - w / 2, y - 0.002, z - h / 2, a + w / 2, y + 0.002, z + h / 2, m, S)
    else:
        x = fixed + side * (T / 2 + 0.003)
        box(name, x - 0.002, a - w / 2, z - h / 2, x + 0.002, a + w / 2, z + h / 2, m, S)

# Living-comedor
for i in range(9):
    stain(f"Mancha_living_{i}", random.uniform(0.5, 7.5), random.uniform(0.5, 4.5),
          random.uniform(0.15, 0.45), random.uniform(0.6, 1.4), random.uniform(0.6, 1.4))
stain("Mancha_alfombra", 2.0, 2.2, 0.35, 1.5, 0.8, M["mancha_osc"], z=0.01)
pizza("Pizza_mesa", 2.0, 2.5, 0.42)
pizza("Pizza_piso_1", 3.0, 1.2)
pizza("Pizza_piso_2", 2.9, 1.0, 0.05)
for i, (x, y, l, g) in enumerate(((1.8, 2.8, False, True), (2.3, 2.2, False, False), (2.7, 3.4, True, True),
                                   (3.1, 1.6, True, False), (5.9, 2.6, False, True), (0.6, 4.4, True, True),
                                   (7.4, 0.6, True, False))):
    bottle(f"Botella_living_{i}", x, y, lying=l, green=g, z=0.42 if (i < 2) else (0.78 if i == 4 else 0.0))
for i in range(8):
    paper(f"Diario_{i}", random.uniform(1, 7.5), random.uniform(0.4, 4.6))
bag("Bolsa_living_1", 7.6, 0.45)
bag("Bolsa_living_2", 7.65, 1.05, 0.8)
bag("Bolsa_living_3", 0.45, 0.45, 0.9)
clothes("Ropa_sofa", 0.6, 2.7, 0.45)
clothes("Ropa_living", 4.0, 3.8)
dishes("Platos_comedor", 5.7, 2.2, 0.78, 4)
dishes("Platos_comedor_2", 6.4, 2.6, 0.78, 3)
wall_patch("Mancha_muro_living", "y", 0, 2.5, 1.2, 0.8, 0.5, M["mancha"], side=1)

# Cocina
for i in range(7):
    stain(f"Mancha_cocina_{i}", random.uniform(8.5, 13.2), random.uniform(0.5, 4.2),
          random.uniform(0.15, 0.4), random.uniform(0.6, 1.4), random.uniform(0.6, 1.4), M["grasa"])
for i, (x, y) in enumerate(((13.6, 1.0), (13.65, 3.4), (12.1, 4.6), (10.9, 4.6))):
    dishes(f"Platos_meson_{i}", x, y, 0.9, random.randint(4, 8))
dishes("Platos_lavaplatos", 13.65, 2.4, 0.86, 7)
for i in range(4):
    cyl(f"Olla_{i}", 11.4 + (i % 2) * 0.35, 4.55 + (i // 2) * 0.25 - 0.1, 0.93, 1.08, 0.12,
        M["metal"], S, seg=12)
    sphere(f"Olla_{i}_resto", 11.4 + (i % 2) * 0.35, 4.55 + (i // 2) * 0.25 - 0.1, 1.06, 0.1,
           M["comida"], S, scale=(1, 1, 0.3), seg=8)
for i, (x, y) in enumerate(((10.3, 2.0), (10.8, 2.3))):
    pizza(f"Pizza_cocina_{i}", x, y, 0.76)
bag("Bolsa_cocina_1", 12.4, 0.4)
bag("Bolsa_cocina_2", 12.5, 0.95, 0.85)
bag("Bolsa_cocina_3", 9.0, 0.5)
for i in range(5):
    bottle(f"Botella_cocina_{i}", random.uniform(9, 12.8), random.uniform(0.6, 3.8), lying=True, green=i % 2 == 0)
for i in range(6):
    wall_patch(f"Grasa_muro_{i}", "y", 14, random.uniform(0.6, 4.5), random.uniform(1.0, 1.8),
               random.uniform(0.2, 0.5), random.uniform(0.15, 0.4), M["grasa"], side=-1)
wall_patch("Grasa_estufa", "x", 5, 11.55, 1.25, 1.0, 0.6, M["grasa"], side=-1)
stain("Mancha_refri", 8.85, 4.5, 0.25, 0.1, 1.0, M["mancha"], z=0.0)

# Baño
for i in range(14):
    wall_patch(f"Moho_muro_{i}", "x", 10, random.uniform(5.3, 8.7), random.uniform(1.6, 2.6),
               random.uniform(0.15, 0.6), random.uniform(0.1, 0.4), M["moho"], side=-1)
for i in range(8):
    wall_patch(f"Moho_oeste_{i}", "y", 5, random.uniform(5.3, 9.7), random.uniform(1.7, 2.6),
               random.uniform(0.15, 0.5), random.uniform(0.1, 0.35), M["moho"], side=1)
for i in range(6):
    box(f"Moho_techo_{i}", random.uniform(5.2, 8.5), random.uniform(8.5, 9.6), H - 0.004,
        random.uniform(5.2, 8.5) + 0.3, random.uniform(8.5, 9.6) + 0.2, H - 0.001, M["moho"], S)
stain("Charco_bano", 6.5, 8.2, 0.5, 1.4, 0.8, M["grasa"])
stain("Mancha_inodoro", 8.5, 8.7, 0.25, 1.2, 0.8, M["mancha"])
for i in range(3):
    cyl(f"Rollo_papel_{i}", 8.0 + i * 0.15, 9.7, 0.0, 0.11, 0.055, M["papel"], S, seg=10,
        rot=(0, 90 if i == 2 else 0, 0))
clothes("Toallas_bano", 6.0, 6.0)

# Dormitorio 1
stain("Mancha_colchon1", 2.4, 9.2, 0.3, 1.3, 0.8, M["mancha"], z=0.62)
clothes("Ropa_dorm1_a", 1.0, 6.2)
clothes("Ropa_dorm1_b", 3.6, 7.0)
clothes("Ropa_cama1", 2.5, 8.4, 0.66)
for i in range(4):
    bottle(f"Botella_dorm1_{i}", random.uniform(0.5, 4.0), random.uniform(5.6, 7.5), lying=i % 2 == 0, green=False)
dishes("Plato_velador", 3.35, 9.65, 0.55, 2)
pizza("Pizza_dorm1", 0.7, 9.4)
for i in range(4):
    stain(f"Mancha_dorm1_{i}", random.uniform(0.5, 4.5), random.uniform(5.5, 9.5), random.uniform(0.15, 0.35))

# Dormitorio 2
for i in range(3):
    box(f"Caja_{i}", 12.6 + i * 0.1, 5.4 + i * 0.55, 0, 13.1 + i * 0.1, 5.9 + i * 0.55, 0.45 - i * 0.05,
        M["carton"], S, colision=True)
box("Caja_encima", 12.65, 5.45, 0.45, 13.05, 5.85, 0.8, M["carton"], S, rot=(0, 0, 12))
for i in range(10):
    paper(f"Papel_dorm2_{i}", random.uniform(9.5, 12.5), random.uniform(5.5, 8.3))
for i in range(3):
    paper(f"Papel_escritorio_{i}", 9.4 + i * 0.25, 8.9, 0.76)
dishes("Plato_escritorio", 10.15, 9.6, 0.76, 2)
clothes("Ropa_dorm2", 12.4, 7.2)
clothes("Ropa_cama2", 12.6, 8.8, 0.6)
bag("Bolsa_dorm2", 13.6, 5.5, 0.8)
for i in range(4):
    stain(f"Mancha_dorm2_{i}", random.uniform(9.5, 13.5), random.uniform(5.5, 9.5), random.uniform(0.15, 0.35))

# Telarañas en esquinas de techo
WEBS = [
    (T / 2, T / 2, 1, 1), (8 - T / 2, T / 2, -1, 1), (8 + T / 2, T / 2, 1, 1), (14 - T / 2, T / 2, -1, 1),
    (T / 2, 10 - T / 2, 1, -1), (5 - T / 2, 10 - T / 2, -1, -1), (5 + T / 2, 10 - T / 2, 1, -1),
    (9 - T / 2, 10 - T / 2, -1, -1), (14 - T / 2, 10 - T / 2, -1, -1), (14 - T / 2, 5 + T / 2, -1, 1),
]
for i, c in enumerate(WEBS):
    web(f"Telarana_{i}", c, random.uniform(0.4, 0.8))

# =================================================================== EXTERIOR
X = "Exterior"
box("Suelo_pasto", -60, -45, -0.4, 75, 50, -0.02, M["pasto"], X, uvscale=4)
box("Vereda_casa", -60, -6.5, -0.02, 75, -5.0, 0.03, M["vereda"], X)
box("Calle", -60, -12.5, -0.03, 75, -6.5, 0.0, M["asfalto"], X)
for i in range(-12, 15):
    box(f"Linea_{i}", i * 5, -9.58, 0.0, i * 5 + 2.5, -9.42, 0.005, M["linea"], X)
box("Vereda_enfrente", -60, -14.0, -0.02, 75, -12.5, 0.03, M["vereda"], X)
box("Camino_entrada", 4.2, -5.0, -0.02, 5.2, -0.1, 0.02, M["vereda"], X)

def tree(name, x, y, h=4.0, r=1.6):
    cyl(name + "_tronco", x, y, 0, h * 0.55, 0.18, M["tronco"], X, seg=8)
    sphere(name + "_copa", x, y, h * 0.7, r, M["hojas"], X, seg=10, scale=(1, 1, 1.15))

for i, (x, y, h) in enumerate(((-5, -3, 4.5), (20, -3.5, 5), (-4, 14, 4), (31, 13, 5), (14.5, -16, 4.2),
                                (-7, -18, 5), (25, -20, 4.6), (16, 14, 4.5))):
    tree(f"Arbol_{i}", x, y, h)

# Auto estacionado
cx, cy = 21.0, -8.0
box("Auto_carroceria", cx - 2.1, cy - 0.85, 0.3, cx + 2.1, cy + 0.85, 0.95, M["auto"], X)
box("Auto_cabina", cx - 1.1, cy - 0.8, 0.95, cx + 0.9, cy + 0.8, 1.5, M["auto"], X)
box("Auto_vidrios", cx - 1.05, cy - 0.82, 1.0, cx + 0.85, cy + 0.82, 1.45, M["vidrio"], X)
for i, (dx, dy) in enumerate(((-1.4, -0.85), (1.4, -0.85), (-1.4, 0.85), (1.4, 0.85))):
    cyl(f"Auto_rueda_{i}", cx + dx, cy + dy - 0.1, 0.0, 0.2, 0.33, M["rueda"], X, seg=14, rot=(90, 0, 0))

# Casa de enfrente (con ventana iluminada)
VX0, VX1, VY0, VY1 = 0.0, 12.0, -23.0, -15.0
wall("Vecinos_frente", "x", VY1, VX0, VX1, [(2.0, 7.0, 0.8, 2.3), (9.0, 10.0, 0.0, 2.1)],
     m=M["fachada"], c=X, h=3.0, t=0.2)
wall("Vecinos_fondo", "x", VY0, VX0, VX1, m=M["fachada"], c=X, h=3.0, t=0.2)
wall("Vecinos_oeste", "y", VX0, VY0, VY1, m=M["fachada"], c=X, h=3.0, t=0.2)
wall("Vecinos_este", "y", VX1, VY0, VY1, m=M["fachada"], c=X, h=3.0, t=0.2)
wall("Vecinos_interior", "y", 8.0, VY0, VY1, m=M["interior_vec"], c=X, h=3.0, t=0.15)
box("Vecinos_muro_int_fondo", VX0 + 0.1, VY0 + 0.1, 0, 8.0, VY0 + 0.12, 3.0, M["interior_vec"], X)
box("Vecinos_piso", VX0, VY0, -0.05, VX1, VY1, 0.02, M["piso_vec"], X)
box("Vecinos_cielo", VX0 - 0.1, VY0 - 0.1, 3.0, VX1 + 0.1, VY1 + 0.1, 3.1, M["interior_vec"], X)
box("Vecinos_puerta", 9.0, VY1 + 0.08, 0, 10.0, VY1 + 0.12, 2.1, M["puerta"], X)
box("Vecinos_vidrio", 2.0, VY1 - 0.01, 0.8, 7.0, VY1 + 0.01, 2.3, M["vidrio"], X)
poly("Vecinos_techo", [(VX0 - 0.4, VY0 - 0.4, 3.1), (VX1 + 0.4, VY0 - 0.4, 3.1), (VX1 + 0.4, VY1 + 0.4, 3.1),
                       (VX0 - 0.4, VY1 + 0.4, 3.1), (VX0 - 0.4, (VY0 + VY1) / 2, 5.0), (VX1 + 0.4, (VY0 + VY1) / 2, 5.0)],
     [(0, 1, 5, 4), (3, 4, 5, 2), (0, 4, 3), (1, 2, 5)], M["techo_rojo"], X)
# interior de los vecinos
box("Vecinos_sofa", 6.4, -20.5, 0, 7.3, -18.0, 0.45, M["polera2"], X)
box("Vecinos_sofa_resp", 7.05, -20.5, 0.45, 7.3, -18.0, 0.95, M["polera2"], X)
box("Vecinos_mueble_tv", 0.3, -20.0, 0, 0.8, -18.4, 0.5, M["mesa"], X)
tv = box("Vecinos_tv", 0.45, -19.9, 0.5, 0.55, -18.5, 1.3, M["tv_on"], X, anim="tv")
box("Vecinos_mesa", 2.5, -18.4, 0.7, 4.0, -17.2, 0.75, M["mesa"], X)
sphere("Vecinos_florero", 3.2, -17.8, 0.85, 0.12, M["flores"], X)
cyl("Vecinos_lampara_pantalla", 4.5, -19.0, 2.4, 2.7, 0.3, M["papel"], X, seg=14, r2=0.15)
sphere("Vecinos_lampara", 4.5, -19.0, 2.4, 0.08, M["lampara"], X, lampara="vecinos")
# jardín de los vecinos
for i, x in enumerate((1.0, 1.8, 8.0, 10.6, 11.4)):
    sphere(f"Arbusto_vecinos_{i}", x, -14.4, 0.35, 0.45, M["hojas"], X, scale=(1, 1, 0.8), seg=8)
    sphere(f"Flor_vecinos_{i}", x + 0.15, -14.2, 0.65, 0.1, M["flores"], X, seg=6)

# Casa del lado (este)
EX0, EX1, EY0, EY1 = 19.0, 29.0, 1.0, 10.0
for nm, args in {
    "Vecinos2_frente": ("x", EY0, EX0, EX1), "Vecinos2_fondo": ("x", EY1, EX0, EX1),
    "Vecinos2_oeste": ("y", EX0, EY0, EY1), "Vecinos2_este": ("y", EX1, EY0, EY1),
}.items():
    wall(nm, *args, m=M["fachada2"], c=X, h=3.0, t=0.2)
box("Vecinos2_cielo", EX0 - 0.1, EY0 - 0.1, 3.0, EX1 + 0.1, EY1 + 0.1, 3.1, M["fachada2"], X)
for i, y in enumerate((2.5, 6.5)):
    box(f"Vecinos2_ventana_{i}", EX0 - 0.12, y, 1.0, EX0 - 0.1, y + 1.6, 2.2, M["vidrio"], X)
poly("Vecinos2_techo", [(EX0 - 0.4, EY0 - 0.4, 3.1), (EX1 + 0.4, EY0 - 0.4, 3.1), (EX1 + 0.4, EY1 + 0.4, 3.1),
                        (EX0 - 0.4, EY1 + 0.4, 3.1), ((EX0 + EX1) / 2, EY0 - 0.4, 5.0), ((EX0 + EX1) / 2, EY1 + 0.4, 5.0)],
     [(0, 4, 5, 3), (1, 2, 5, 4), (0, 1, 4), (3, 5, 2)], M["techo_rojo"], X)

# Cercas
def fence(name, x0, y0, x1, y1, h=1.1):
    L = math.hypot(x1 - x0, y1 - y0); n = int(L / 1.5) + 1
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n; y = y0 + (y1 - y0) * i / n
        box(f"{name}_poste_{i}", x - 0.05, y - 0.05, 0, x + 0.05, y + 0.05, h, M["cerca"], X)
    for j, z in enumerate((0.4, 0.9)):
        if x0 == x1:
            box(f"{name}_tabla_{j}", x0 - 0.02, y0, z, x0 + 0.02, y1, z + 0.12, M["cerca"], X)
        else:
            box(f"{name}_tabla_{j}", x0, y0 - 0.02, z, x1, y0 + 0.02, z + 0.12, M["cerca"], X)

fence("Cerca_este", 17.0, -4.5, 17.0, 13.0)
fence("Cerca_oeste", -3.0, -4.5, -3.0, 13.0)
fence("Cerca_fondo", -3.0, 13.0, 17.0, 13.0)

# Tendedero (oeste)
for i, y in enumerate((5.5, 9.5)):
    box(f"Tendedero_poste_{i}", -6.05, y - 0.05, 0, -5.95, y + 0.05, 1.9, M["metal"], X)
box("Tendedero_cuerda", -6.01, 5.5, 1.85, -5.99, 9.5, 1.86, M["papel"], X)
ropa_tendida = empty("Ropa_tendida", (-6.0, 7.5, 1.85), c=X, anim="ropa")
for i, (y, mm) in enumerate(((6.0, M["ropa1"]), (6.8, M["ropa2"]), (7.9, M["polera1"]), (8.8, M["ropa3"]))):
    box(f"Ropa_tendida_{i}", -0.01, y - 7.5 - 0.3, -0.6, 0.01, y - 7.5 + 0.3, 0.0, mm, X, parent=ropa_tendida)

# =================================================================== VECINOS
V = "Vecinos"
def person(name, x, y, rot, shirt, pants=None, skin=None, hair=None, s=1.0, seated=False, pose=None, **props):
    pants = pants or M["jeans"]; skin = skin or M["piel"]; hair = hair or M["pelo"]
    z = (0.45 - 0.9 * s) if seated else 0.0
    root = empty(name, (x, y, z), (0, 0, rot), c=V, **props)
    for side, dx in (("izq", -0.1), ("der", 0.1)):
        piv = empty(f"{name}_pierna_{side}", (dx * s, 0, 0.9 * s), (90 if seated else 0, 0, 0), parent=root, rol="pierna_" + side)
        box(f"{name}_pierna_{side}_m", -0.07 * s, -0.08 * s, -0.9 * s, 0.07 * s, 0.08 * s, 0, pants, V, parent=piv)
    box(f"{name}_torso", -0.2 * s, -0.12 * s, 0.88 * s, 0.2 * s, 0.12 * s, 1.45 * s, shirt, V, parent=root)
    sphere(f"{name}_cabeza", 0, 0, 1.6 * s, 0.13 * s, skin, V, parent=root)
    sphere(f"{name}_pelo", 0, -0.02 * s, 1.66 * s, 0.135 * s, hair, V, parent=root, scale=(1, 1, 0.75))
    box(f"{name}_nariz", -0.015 * s, 0.11 * s, 1.57 * s, 0.015 * s, 0.15 * s, 1.61 * s, skin, V, parent=root)
    for side, dx in (("izq", -0.26), ("der", 0.26)):
        r = (0, 0, 0)
        if pose == "saludo" and side == "der":
            r = (0, -150, 0)
        if pose == "regar" and side == "der":
            r = (-70, 0, 0)
        if pose == "tender":
            r = (-160, 0, 0)
        if seated:
            r = (-40, 0, 0)
        piv = empty(f"{name}_brazo_{side}", (dx * s, 0, 1.42 * s), r, parent=root, rol="brazo_" + side)
        box(f"{name}_brazo_{side}_m", -0.05 * s, -0.05 * s, -0.6 * s, 0.05 * s, 0.05 * s, 0, shirt, V, parent=piv)
        sphere(f"{name}_mano_{side}", 0, 0, -0.63 * s, 0.05 * s, skin, V, parent=piv)
    return root

# Vecina saludando desde la ventana de enfrente (mira hacia +y, nuestra casa)
person("Vecina_ventana", 4.2, -15.9, 0, M["polera4"], M["pantalon"], hair=M["pelo"], pose="saludo", anim="saludo")
# Vecino viendo TV en el sofá (mira hacia -x)
person("Vecino_tv", 6.8, -19.2, 90, M["polera3"], seated=True, hair=M["pelo2"], anim="sentado")
# Jardinero regando (mira hacia sus plantas)
j = person("Vecino_jardinero", 9.5, -14.5, 70, M["polera2"], M["pantalon"], M["piel2"], M["pelo"], pose="regar", anim="jardinero")
cyl("Manguera", 0.32, 0.45, 1.0, 1.25, 0.03, M["polera2"], V, seg=6, parent=j, rot=(-70, 0, 0))
# Señor paseando al perro por la vereda (mira hacia +x)
person("Vecino_paseante", -10.0, -5.8, -90, M["polera1"], M["jeans"], hair=M["pelo2"],
       anim="paseante", rango_min=-25.0, rango_max=32.0)
dog = empty("Perro", (-11.3, -5.5, 0), (0, 0, -90), c=V, anim="perro")
box("Perro_cuerpo", -0.12, -0.3, 0.25, 0.12, 0.3, 0.48, M["perro"], V, parent=dog)
box("Perro_cabeza", -0.1, 0.25, 0.4, 0.1, 0.5, 0.6, M["perro"], V, parent=dog)
box("Perro_hocico", -0.05, 0.48, 0.42, 0.05, 0.6, 0.5, M["negro"], V, parent=dog)
for i, (dx, dy) in enumerate(((-0.08, -0.22), (0.08, -0.22), (-0.08, 0.22), (0.08, 0.22))):
    box(f"Perro_pata_{i}", dx - 0.035, dy - 0.035, 0, dx + 0.035, dy + 0.035, 0.27, M["perro"], V, parent=dog)
box("Perro_cola", -0.02, -0.45, 0.42, 0.02, -0.28, 0.46, M["perro"], V, parent=dog, rot=(30, 0, 0))
# Niño con pelota en el patio del lado (mira hacia -x, hacia nuestra casa)
person("Nino", 18.2, 8.0, 90, M["polera3"], M["jeans"], hair=M["pelo"], s=0.65, anim="nino")
sphere("Pelota", 17.6, 8.0, 0.12, 0.12, M["pelota"], V, anim="pelota")
# Vecina tendiendo ropa (mira hacia +x)
person("Vecina_ropa", -6.5, 7.2, -90, M["polera1"], M["pantalon"], M["piel2"], M["pelo"], pose="tender", anim="tender")

# ----------------------------------------------------------------- jugador (marcador de inicio)
empty("Inicio_jugador", (4.7, 1.6, 0), (0, 0, 0), c="Casa", inicio=True)

# =================================================================== exportar
bpy.context.view_layer.update()
try:
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, relative_remap=True)
except Exception as ex:
    print("No se pudo guardar .blend:", ex)

bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", export_extras=True, export_yup=True)
n_obj = len(bpy.data.objects)
print(f"OK: {n_obj} objetos -> {OUT_GLB} ({os.path.getsize(OUT_GLB) / 1024:.0f} KB)")
