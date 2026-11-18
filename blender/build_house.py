"""
"Lengua materna" — construye la casa de Renato (cerro Playa Ancha, Valparaíso) y la exporta a
public/assets/casa.glb.

Uso (desde la raíz del repo):
    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup -P blender/build_house.py

Coordenadas Blender (Z arriba, metros). La casa va de x=0..15, y=0..19.5. El frente (puerta con cinco
cerraduras) está en y=0 y mira a la calle (-y). Al fondo (+y) está la bahía.

  Living-comedor   x 0..8,     y 0..5
  Cocina           x 8..15,    y 0..5
  Baño             x 1.5..6.5, y 5..9      (puerta desde el living)
  Cuarto de Renato x 6.5..9.5, y 5..9      (solo se llega pasando por el de la madre)
  Cuarto de madre  x 9.5..15,  y 5..9      (ventana sellada, retratos, muros grasosos)
  Habitación nueva x 6..9.75,  y 9..13.5   (la que Renato preparó "para ti", detrás de su cuarto)
  Pasillo en U     x 0..1.5 (oeste) -> y 18..19.5 (fondo) -> x 13.5..15 (este), termina en la madre
  Cinco piezas de antiguos estudiantes (s1..s5) a lo largo del pasillo.

Propiedades personalizadas (se exportan como "extras" en glTF y el juego las lee):
  colision=True                     el jugador no lo atraviesa
  interaccion="puerta"              puerta principal (cinco cerraduras)
  interaccion="puerta_int", giro    puerta interior con bisagra (se abre con E)
  interaccion="interruptor", habitacion
  interaccion="ventana", texto
  interaccion="leer", texto[, texto2]
  interaccion="llave", llave=n      una de las cinco llaves
  interaccion="madre" / "renato"
  cerradura=n                       cerraduras visibles en la puerta
  lampara=<habitacion>              el juego pone una luz aquí
  anim=...                          animaciones (las hace el juego)
  rol=...                           partes animadas (brazos, piernas)
  sinniebla=True                    luces lejanas que se ven a través de la niebla
"""
import bpy, bmesh, math, os, random
import numpy as np

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
DOOR_H = 2.1

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

# ----------------------------------------------------------------- texturas procedurales
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
    h, w = rgb.shape[:2]
    a = np.ones((h, w, 1))
    px = np.concatenate([np.clip(rgb, 0, 1), a], axis=2).astype(np.float32)
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.pixels.foreach_set(px.ravel())
    path = os.path.join(TEXDIR, name + ".png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    img.filepath = "//textures/" + name + ".png"
    return img

yy, xx = np.mgrid[0:N, 0:N]
rng = np.random.default_rng(3)

# Madera sucia (con rayones largos: alguien caminó la misma ruta una y otra vez)
plank = yy // 64
var = rng.uniform(0.75, 1.1, size=8)[plank]
offs = rng.integers(0, N, size=8)[plank]
grain = np.sin(xx * 0.03 + fbm(N, 8, 3, 7) * 12) * 0.5 + 0.5
wood = np.array([0.42, 0.28, 0.16]) * ((0.8 + 0.25 * grain) * var)[..., None]
seam = ((yy % 64) < 2) | (((xx + offs) % 256) < 2)
wood[seam] *= 0.35
scr = np.zeros((N, N))
for _ in range(40):
    r0 = rng.integers(0, N); c0 = rng.integers(0, N); L = rng.integers(60, 300)
    cols_ = (c0 + np.arange(L)) % N
    rows_ = (r0 + (np.arange(L) * rng.uniform(-0.08, 0.08)).astype(int)) % N
    scr[rows_, cols_] = 1
wood = wood * (1 - 0.45 * scr[..., None]) + 0.45 * scr[..., None] * np.array([0.7, 0.6, 0.45])
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

# Muro blanco helado con capa oleosa café (cuarto de la madre y piezas de estudiantes)
white = np.array([0.90, 0.91, 0.90]) * (0.95 + 0.05 * fbm(N, 3, 3, 61))[..., None]
oil = np.clip(fbm(N, 3, 6, 62) * 1.3 - 0.25 + drip * 0.5, 0, 1)
IMG_OIL = save_img("muro_grasoso", dirty(white, oil, col=(0.36, 0.22, 0.08), k=0.85))

# Azulejo de baño con moho
az = np.array([0.72, 0.82, 0.80]) * tile_var[..., None]
az[((xx % 64) < 3) | ((yy % 64) < 3)] = (0.25, 0.27, 0.2)
mold = np.clip((fbm(N, 6, 5, 77) - 0.5) * 5, 0, 1)
IMG_AZ = save_img("azulejo_moho", dirty(az, mold, col=(0.08, 0.12, 0.05), k=0.85))

# Retrato: la madre cuando era joven
P = 256
pv, pu = np.mgrid[0:P, 0:P] / P  # pv=0 abajo
def ell(cu, cv, ru, rv):
    return ((pu - cu) / ru) ** 2 + ((pv - cv) / rv) ** 2 < 1
por = np.array([0.55, 0.42, 0.28]) * (0.7 + 0.3 * pv)[..., None]
por[ell(0.5, 0.08, 0.40, 0.26)] = (0.30, 0.10, 0.12)          # vestido
por[ell(0.5, 0.56, 0.23, 0.33) & (pv > 0.36)] = (0.14, 0.09, 0.05)  # pelo largo
por[(abs(pu - 0.5) < 0.05) & (pv > 0.28) & (pv < 0.5)] = (0.86, 0.70, 0.56)  # cuello
por[ell(0.5, 0.62, 0.135, 0.18)] = (0.88, 0.72, 0.58)         # cara
por[ell(0.5, 0.78, 0.16, 0.07)] = (0.14, 0.09, 0.05)          # flequillo
por[ell(0.45, 0.64, 0.025, 0.012) | ell(0.55, 0.64, 0.025, 0.012)] = (0.1, 0.07, 0.05)
por[ell(0.5, 0.53, 0.04, 0.013)] = (0.6, 0.12, 0.12)          # labios
vig = 1 - 0.7 * ((pu - 0.5) ** 2 + (pv - 0.5) ** 2)
IMG_PORTRAIT = save_img("retrato_madre", por * vig[..., None])

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
    grasoso=mat("Muro blanco grasoso", img=IMG_OIL, rough=0.35),
    azulejo=mat("Azulejo con moho", img=IMG_AZ, rough=0.5),
    retrato=mat("Retrato", img=IMG_PORTRAIT, rough=0.6),
    techo=mat("Techo manchado", (0.70, 0.66, 0.56), 0.95),
    vidrio=mat("Vidrio sucio", (0.62, 0.6, 0.5), 0.2, alpha=0.16),
    esmerilado=mat("Vidrio esmerilado", (0.55, 0.6, 0.5), 0.6, alpha=0.85),
    marco=mat("Marco ventana", (0.75, 0.72, 0.62), 0.7),
    marco_dorado=mat("Marco dorado", (0.65, 0.5, 0.25), 0.4, metal=0.8),
    puerta=mat("Puerta", (0.36, 0.22, 0.12), 0.6),
    puerta_int=mat("Puerta interior", (0.55, 0.43, 0.30), 0.7),
    tabla=mat("Tablas clavadas", (0.38, 0.28, 0.18), 0.9),
    metal=mat("Metal", (0.7, 0.7, 0.68), 0.3, metal=1.0),
    bronce=mat("Bronce", (0.85, 0.62, 0.25), 0.3, metal=1.0),
    llave=mat("Llave", (0.9, 0.7, 0.3), 0.25, emit=(0.9, 0.7, 0.3), strength=0.8, metal=1.0),
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
    sabana_blanca=mat("Sabana blanca sucia", (0.78, 0.76, 0.68), 0.9),
    alfombra=mat("Alfombra", (0.45, 0.18, 0.15), 1.0),
    carton=mat("Carton", (0.62, 0.48, 0.3), 0.9),
    papel=mat("Papel", (0.85, 0.83, 0.75), 0.9),
    credencial=mat("Credencial", (0.92, 0.92, 0.95), 0.5),
    banda=mat("Banda credencial", (0.15, 0.3, 0.65), 0.5),
    pintura=mat("Pintura beige", (0.85, 0.76, 0.58), 0.6),
    bolsa=mat("Bolsa basura", (0.03, 0.03, 0.03), 0.25),
    botella_v=mat("Botella verde", (0.1, 0.35, 0.12), 0.1, alpha=0.75),
    botella_c=mat("Botella cafe", (0.35, 0.18, 0.05), 0.1, alpha=0.8),
    mancha=mat("Mancha", (0.16, 0.11, 0.06), 0.3, alpha=0.75),
    mancha_osc=mat("Mancha oscura", (0.08, 0.06, 0.04), 0.2, alpha=0.85),
    moho=mat("Moho", (0.12, 0.18, 0.08), 1.0, alpha=0.85),
    grasa=mat("Grasa", (0.25, 0.18, 0.06), 0.2, alpha=0.6),
    rayon=mat("Rayon piso", (0.12, 0.08, 0.05), 0.9, alpha=0.6),
    telarana=mat("Telarana", (0.85, 0.85, 0.85), 1.0, alpha=0.3),
    comida=mat("Comida podrida", (0.35, 0.3, 0.08), 0.8),
    ropa1=mat("Ropa azul", (0.2, 0.3, 0.55), 1.0),
    ropa2=mat("Ropa roja", (0.6, 0.15, 0.12), 1.0),
    ropa3=mat("Ropa gris", (0.45, 0.45, 0.45), 1.0),
    hortensia=mat("Hortensias de plastico", (0.55, 0.62, 0.95), 0.15),
    hortensia_podrida=mat("Hortensias podridas", (0.38, 0.32, 0.36), 0.9),
    tallo=mat("Tallo", (0.25, 0.35, 0.15), 0.8),
    # exterior (noche)
    pasto=mat("Pasto", (0.22, 0.32, 0.16), 1.0),
    asfalto=mat("Asfalto", (0.16, 0.16, 0.17), 0.6),
    vereda=mat("Vereda", (0.5, 0.48, 0.45), 0.9),
    linea=mat("Linea calle", (0.9, 0.85, 0.3), 0.8),
    fachada=mat("Fachada vecinos", (0.85, 0.55, 0.35), 0.85),
    fachada2=mat("Fachada vecinos 2", (0.35, 0.6, 0.7), 0.85),
    fachada3=mat("Fachada vecinos 3", (0.85, 0.8, 0.4), 0.85),
    techo_rojo=mat("Calamina", (0.5, 0.2, 0.14), 0.6, metal=0.3),
    interior_vec=mat("Muro vecinos", (0.95, 0.9, 0.75), 0.9),
    piso_vec=mat("Piso vecinos", (0.6, 0.45, 0.3), 0.6),
    tv_on=mat("Pantalla TV", (0.3, 0.5, 0.9), 0.2, emit=(0.4, 0.6, 1.0), strength=3),
    farol=mat("Farol", (1, 0.8, 0.5), 0.4, emit=(1, 0.75, 0.4), strength=10),
    poste=mat("Poste", (0.15, 0.15, 0.15), 0.5, metal=0.6),
    mar=mat("Mar de noche", (0.02, 0.035, 0.06), 0.15),
    cerro=mat("Cerros lejanos", (0.03, 0.03, 0.04), 1.0),
    luz_ciudad=mat("Luces ciudad", (1, 0.8, 0.5), 0.5, emit=(1, 0.75, 0.45), strength=12),
    luz_barco=mat("Luces barco", (1, 1, 0.9), 0.5, emit=(1, 0.95, 0.85), strength=15),
    tronco=mat("Tronco", (0.32, 0.22, 0.14), 0.9),
    hojas=mat("Hojas", (0.2, 0.3, 0.15), 0.9),
    cerca=mat("Cerca", (0.5, 0.42, 0.32), 0.9),
    auto=mat("Auto", (0.15, 0.3, 0.6), 0.3, metal=0.4),
    rueda=mat("Rueda", (0.05, 0.05, 0.05), 0.8),
    brasa=mat("Brasa", (1, 0.4, 0.1), 0.5, emit=(1, 0.35, 0.05), strength=8),
    piel=mat("Piel", (0.85, 0.65, 0.5), 0.7),
    piel2=mat("Piel 2", (0.55, 0.38, 0.26), 0.7),
    piel_gris=mat("Piel gris", (0.62, 0.60, 0.56), 0.8),
    piel_vieja=mat("Piel vieja", (0.72, 0.62, 0.55), 0.9),
    piel_seca=mat("Piel acartonada", (0.40, 0.31, 0.22), 1.0),
    pelo=mat("Pelo", (0.15, 0.1, 0.06), 0.8),
    pelo2=mat("Pelo canoso", (0.7, 0.7, 0.68), 0.8),
    pelo_blanco=mat("Pelo blanco", (0.88, 0.88, 0.85), 0.9),
    pelo_seco=mat("Pelo reseco", (0.3, 0.27, 0.22), 1.0),
    polera1=mat("Polera amarilla", (0.9, 0.7, 0.2), 0.9),
    polera2=mat("Polera verde", (0.2, 0.55, 0.3), 0.9),
    polera3=mat("Polera roja", (0.75, 0.2, 0.2), 0.9),
    polera4=mat("Polera morada", (0.5, 0.3, 0.6), 0.9),
    camisa=mat("Camisa blanca", (0.85, 0.85, 0.82), 0.9),
    camison=mat("Camison", (0.82, 0.78, 0.7), 0.9),
    trapo=mat("Ropa vieja", (0.32, 0.3, 0.26), 1.0),
    jeans=mat("Jeans", (0.2, 0.25, 0.4), 0.9),
    pantalon=mat("Pantalon cafe", (0.35, 0.28, 0.2), 0.9),
    perro=mat("Perro", (0.6, 0.42, 0.22), 0.9),
    flores=mat("Flores", (0.9, 0.3, 0.5), 0.8),
)

# ----------------------------------------------------------------- geometría básica
def _finish(name, bm, m, c, parent, loc, rot, uvscale, props, uvfunc=None):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    uvl = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            co = l.vert.co
            if uvfunc is not None:
                l[uvl].uv = uvfunc(co)
                continue
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
    if tuple(rot) == (0, 0, 0):
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

def hinged_door(name, along, fixed, s, e, giro, m=None):
    """Puerta interior con bisagra en 's'. giro=+1/-1 decide hacia qué lado abre."""
    m = m or M["puerta_int"]
    w = e - s - 0.02
    if along == "x":
        piv = empty(name, (s + 0.01, fixed, 0), c="Casa", interaccion="puerta_int", giro=giro)
        box(name + "_hoja", 0, -0.025, 0.0, w, 0.025, DOOR_H - 0.05, m, "Casa", parent=piv, colision=True)
        sphere(name + "_manilla_a", w - 0.1, 0.06, 1.0, 0.035, M["metal"], "Casa", parent=piv)
        sphere(name + "_manilla_b", w - 0.1, -0.06, 1.0, 0.035, M["metal"], "Casa", parent=piv)
    else:
        piv = empty(name, (fixed, s + 0.01, 0), c="Casa", interaccion="puerta_int", giro=giro)
        box(name + "_hoja", -0.025, 0, 0.0, 0.025, w, DOOR_H - 0.05, m, "Casa", parent=piv, colision=True)
        sphere(name + "_manilla_a", 0.06, w - 0.1, 1.0, 0.035, M["metal"], "Casa", parent=piv)
        sphere(name + "_manilla_b", -0.06, w - 0.1, 1.0, 0.035, M["metal"], "Casa", parent=piv)
    return piv

def overlay(name, along, fixed, a0, a1, side, m, z0=0.0, z1=H, uvscale=2.0):
    """Revestimiento delgado pegado a la cara interior de un muro (side=+1 lado +, -1 lado -)."""
    d = side * (T / 2)
    if along == "x":
        y = fixed + d
        box(name, a0, min(y, y + side * 0.008), z0, a1, max(y, y + side * 0.008), z1, m, uvscale=uvscale)
    else:
        x = fixed + d
        box(name, min(x, x + side * 0.008), a0, z0, max(x, x + side * 0.008), a1, z1, m, uvscale=uvscale)

def picture(name, along, fixed, side, a, z, w, h, texto=None):
    """Retrato con marco dorado colgado en un muro."""
    d = fixed + side * (T / 2 + 0.01)
    props = dict(interaccion="leer", texto=texto) if texto else {}
    if along == "x":
        fr = box(name, a - w / 2 - 0.05, d - 0.015, z - h / 2 - 0.05, a + w / 2 + 0.05, d + 0.015, z + h / 2 + 0.05,
                 M["marco_dorado"], "Casa", **props)
        y = d + side * 0.017
        x0, z0 = a - w / 2, z - h / 2
        bm = bmesh.new()
        vs = [bm.verts.new(v) for v in ((x0, y, z0), (x0 + w, y, z0), (x0 + w, y, z0 + h), (x0, y, z0 + h))]
        bm.faces.new(vs if side < 0 else vs[::-1])
        f = lambda co: ((co.x - x0) / w if side < 0 else 1 - (co.x - x0) / w, (co.z - z0) / h)
    else:
        fr = box(name, d - 0.015, a - w / 2 - 0.05, z - h / 2 - 0.05, d + 0.015, a + w / 2 + 0.05, z + h / 2 + 0.05,
                 M["marco_dorado"], "Casa", **props)
        x = d + side * 0.017
        y0, z0 = a - w / 2, z - h / 2
        bm = bmesh.new()
        vs = [bm.verts.new(v) for v in ((x, y0, z0), (x, y0 + w, z0), (x, y0 + w, z0 + h), (x, y0, z0 + h))]
        bm.faces.new(vs if side > 0 else vs[::-1])
        f = lambda co: ((co.y - y0) / w if side > 0 else 1 - (co.y - y0) / w, (co.z - z0) / h)
    img = _finish(name + "_lienzo", bm, M["retrato"], "Casa", fr, (0, 0, 0), (0, 0, 0), 1.0, {}, uvfunc=f)
    return fr

def planks(name, along, fixed, side, a0, a1, z0, z1):
    """Ventana sellada: tablas clavadas sobre la cara del muro."""
    d = fixed + side * (T / 2 + 0.02)
    box(name + "_fondo", *((a0, d - 0.005, z0, a1, d + 0.005, z1) if along == "x" else (d - 0.005, a0, z0, d + 0.005, a1, z1)),
        M["negro"])
    n = 5
    for i in range(n):
        z = z0 + (z1 - z0) * (i + 0.5) / n
        ang = random.uniform(-8, 8)
        if along == "x":
            box(f"{name}_tabla_{i}", a0 - 0.1, d + side * 0.02 - 0.012, z - 0.08, a1 + 0.1, d + side * 0.02 + 0.012, z + 0.08,
                M["tabla"], rot=(0, ang, 0))
        else:
            box(f"{name}_tabla_{i}", d + side * 0.02 - 0.012, a0 - 0.1, z - 0.08, d + side * 0.02 + 0.012, a1 + 0.1, z + 0.08,
                M["tabla"], rot=(ang, 0, 0))

def lamp(room, i, x, y, flicker=False):
    cyl(f"Lampara_{room}_{i}_cable", x, y, H - 0.35, H, 0.01, M["negro"], seg=6)
    cyl(f"Lampara_{room}_{i}_pantalla", x, y, H - 0.5, H - 0.3, 0.28, M["techo"], seg=16, r2=0.12)
    props = dict(lampara=room)
    if flicker:
        props["parpadeo"] = True
    sphere(f"Lampara_{room}_{i}", x, y, H - 0.5, 0.07, M["lampara"], **props)

def switch(room, along, fixed, side, a):
    d = fixed + side * (T / 2)
    if along == "x":
        box(f"Interruptor_{room}", a - 0.05, min(d, d + side * 0.02), 1.15, a + 0.05, max(d, d + side * 0.02), 1.27,
            M["interruptor"], interaccion="interruptor", habitacion=room)
    else:
        box(f"Interruptor_{room}", min(d, d + side * 0.02), a - 0.05, 1.15, max(d, d + side * 0.02), a + 0.05, 1.27,
            M["interruptor"], interaccion="interruptor", habitacion=room)

# =================================================================== CASA
XW, YD = 15.0, 19.5  # ancho y fondo de la casa

TXT = dict(
    living="Afuera, la niebla de Playa Ancha. Al otro lado de la calle, una vecina está de pie en su ventana iluminada. Parece mirar directo hacia acá.",
    comedor="Un hombre pasea a su perro entre la niebla. No mira hacia la casa. Nadie mira hacia esta casa.",
    cocina="El vecino de enfrente fuma en su puerta. La brasa del cigarro se enciende y se apaga, como si respirara.",
    pasillo_o="En la casa del lado alguien ve televisión. La luz azul parpadea contra las cortinas.",
    pasillo_e="Un niño en pijama te mira desde la ventana de la casa vecina. Levanta la mano y te saluda.",
    fondo="Abajo, el puerto encendido. Los barcos parecen muy lejos, como si fueran de otra vida.",
    bano="El vidrio es esmerilado y está cubierto de moho. No se ve nada.",
)

# Pisos
box("Piso_living", 0, 0, -0.1, 8, 5, 0, M["madera"])
box("Piso_cocina", 8, 0, -0.1, XW, 5, 0, M["baldosa"])
box("Piso_bano", 1.5, 5, -0.1, 6.5, 9, 0, M["baldosa"], uvscale=1.5)
box("Piso_resto", 0, 5, -0.1, XW, YD, 0, M["madera"])
box("Techo", -T / 2, -T / 2, H, XW + T / 2, YD + T / 2, H + 0.1, M["techo"])

# Muros exteriores
wall("Muro_frente", "x", 0, -T / 2, XW + T / 2, [
    (1.0, 2.8, 0.9, 2.1),          # ventana living
    (4.2, 5.2, 0.0, DOOR_H),       # puerta principal
    (6.0, 7.4, 0.9, 2.1),          # ventana comedor
    (10.5, 12.5, 0.9, 2.1),        # ventana cocina
])
wall("Muro_fondo", "x", YD, -T / 2, XW + T / 2, [(3.0, 4.6, 0.9, 2.1), (9.0, 10.6, 0.9, 2.1)])
wall("Muro_oeste", "y", 0, T / 2, YD - T / 2, [(10.5, 12.0, 0.9, 2.1)])
wall("Muro_este", "y", XW, T / 2, YD - T / 2, [(6.0, 8.0, 0.9, 2.1), (14.0, 15.5, 0.9, 2.1)])

# Muros interiores
wall("Muro_y5", "x", 5, T / 2, XW - T / 2, [(0.2, 1.3, 0, DOOR_H), (3.0, 3.9, 0, DOOR_H)])
wall("Muro_cocina", "y", 8, T / 2, 5 - T / 2, [(1.4, 3.6, 0, DOOR_H)])
wall("Muro_pasillo_oeste", "y", 1.5, 5 + T / 2, 18 + T / 2, [(10.8, 11.7, 0, DOOR_H), (15.2, 16.1, 0, DOOR_H)])
wall("Muro_pasillo_fondo", "x", 18, 1.5 - T / 2, 13.5 + T / 2, [(7.4, 8.3, 0, DOOR_H), (11.2, 12.1, 0, DOOR_H)])
wall("Muro_pasillo_este", "y", 13.5, 9 + T / 2, 18 - T / 2, [(10.8, 11.7, 0, DOOR_H)])
wall("Muro_y9", "x", 9, 1.5 + T / 2, XW - T / 2, [(7.6, 8.5, 0, DOOR_H), (13.8, 14.7, 0, DOOR_H)])
wall("Muro_y13", "x", 13.5, 1.5 + T / 2, 13.5 - T / 2)
wall("Muro_x6", "y", 6.0, 9 + T / 2, 18 - T / 2)
wall("Muro_x975", "y", 9.75, 9 + T / 2, 18 - T / 2)
wall("Muro_bano_renato", "y", 6.5, 5 + T / 2, 9 - T / 2)
wall("Muro_renato_madre", "y", 9.5, 5 + T / 2, 9 - T / 2, [(6.6, 7.5, 0, DOOR_H)])

# Puertas interiores
hinged_door("Puerta_bano", "x", 5, 3.0, 3.9, +1)
hinged_door("Puerta_s1", "y", 1.5, 10.8, 11.7, -1)
hinged_door("Puerta_s2", "y", 1.5, 15.2, 16.1, -1)
hinged_door("Puerta_s3", "x", 18, 7.4, 8.3, -1)
hinged_door("Puerta_s4", "x", 18, 11.2, 12.1, -1)
hinged_door("Puerta_s5", "y", 13.5, 10.8, 11.7, +1)
hinged_door("Puerta_madre", "x", 9, 13.8, 14.7, -1)
hinged_door("Puerta_renato", "y", 9.5, 6.6, 7.5, +1)
hinged_door("Puerta_nueva", "x", 9, 7.6, 8.5, +1)

# Ventanas
window("Ventana_living", "x", 0, 1.0, 2.8, 0.9, 2.1, TXT["living"])
window("Ventana_comedor", "x", 0, 6.0, 7.4, 0.9, 2.1, TXT["comedor"])
window("Ventana_cocina", "x", 0, 10.5, 12.5, 0.9, 2.1, TXT["cocina"])
window("Ventana_fondo_1", "x", YD, 3.0, 4.6, 0.9, 2.1, TXT["fondo"])
window("Ventana_fondo_2", "x", YD, 9.0, 10.6, 0.9, 2.1, TXT["fondo"])
window("Ventana_pasillo_oeste", "y", 0, 10.5, 12.0, 0.9, 2.1, TXT["pasillo_o"])
window("Ventana_pasillo_este", "y", XW, 14.0, 15.5, 0.9, 2.1, TXT["pasillo_e"])
# la ventana de la madre: sellada herméticamente
box("Ventana_madre_sellada", XW - 0.01, 6.0, 0.9, XW + 0.01, 8.0, 2.1, M["negro"], colision=True,
    interaccion="leer", texto="La ventana está sellada herméticamente. No entra ni la más mínima luz.")
planks("Ventana_madre_tablas", "y", XW, -1, 6.0, 8.0, 0.9, 2.1)

# Puerta principal con cinco cerraduras
door = box("Puerta_principal", 4.22, -0.04, 0.0, 5.18, 0.04, DOOR_H - 0.02, M["puerta"],
           colision=True, interaccion="puerta")
for i, z in enumerate((0.5, 1.55)):
    box(f"Puerta_panel_{i}", 4.35, 0.04, z, 5.05, 0.06, z + 0.45, M["puerta"], parent=door)
sphere("Puerta_manilla", 5.02, 0.11, 1.0, 0.04, M["metal"], parent=door)
for i, z in enumerate((0.55, 0.85, 1.15, 1.45, 1.75)):
    box(f"Cerradura_{i + 1}", 4.95, 0.04, z, 5.1, 0.085, z + 0.12, M["metal"], parent=door, cerradura=i + 1)
    cyl(f"Cerradura_{i + 1}_ojo", 5.025, 0.09, z + 0.03, z + 0.09, 0.012, M["negro"], seg=6, parent=door, rot=(90, 0, 0))
box("Puerta_marco_izq", 4.15, -T / 2 - 0.02, 0, 4.22, T / 2 + 0.02, DOOR_H, M["marco"])
box("Puerta_marco_der", 5.18, -T / 2 - 0.02, 0, 5.25, T / 2 + 0.02, DOOR_H, M["marco"])
box("Puerta_marco_sup", 4.15, -T / 2 - 0.02, DOOR_H - 0.03, 5.25, T / 2 + 0.02, DOOR_H + 0.05, M["marco"])
box("Felpudo", 4.2, 0.12, 0, 5.2, 0.7, 0.012, M["carton"])

# Revestimiento blanco grasoso: cuarto de la madre, piezas de estudiantes y habitación nueva
def oily_room(name, x0, y0, x1, y1):
    overlay(f"{name}_grasa_s", "x", y0, x0 + T / 2, x1 - T / 2, +1, M["grasoso"])
    overlay(f"{name}_grasa_n", "x", y1, x0 + T / 2, x1 - T / 2, -1, M["grasoso"])
    overlay(f"{name}_grasa_o", "y", x0, y0 + T / 2, y1 - T / 2, +1, M["grasoso"])
    overlay(f"{name}_grasa_e", "y", x1, y0 + T / 2, y1 - T / 2, -1, M["grasoso"])

ROOMS = dict(
    madre=(9.5, 5, XW, 9), s1=(1.5, 9, 6, 13.5), s2=(1.5, 13.5, 6, 18), s3=(6, 13.5, 9.75, 18),
    s4=(9.75, 13.5, 13.5, 18), s5=(9.75, 9, 13.5, 13.5), nueva=(6, 9, 9.75, 13.5),
)
for r, (x0, y0, x1, y1) in ROOMS.items():
    oily_room(f"Muro_{r}", x0, y0, x1, y1)

# Azulejos del baño
overlay("Azulejo_O", "y", 1.5, 5 + T / 2, 9 - T / 2, +1, M["azulejo"], z1=1.6, uvscale=1.0)
overlay("Azulejo_N", "x", 9, 1.5 + T / 2, 6.5 - T / 2, -1, M["azulejo"], z1=1.6, uvscale=1.0)
overlay("Azulejo_E", "y", 6.5, 5 + T / 2, 9 - T / 2, -1, M["azulejo"], z1=1.6, uvscale=1.0)

# Lámparas e interruptores
lamp("living", 0, 4.0, 2.5)
lamp("cocina", 0, 11.5, 2.5)
lamp("bano", 0, 4.0, 7.0)
lamp("renato", 0, 8.0, 7.0)
lamp("nueva", 0, 7.9, 11.25)
lamp("pasillo", 0, 0.75, 11.5, flicker=True)
lamp("pasillo", 1, 7.0, 18.75)
lamp("pasillo", 2, 14.25, 13.0)
for r in ("s1", "s2", "s3", "s4", "s5"):
    x0, y0, x1, y1 = ROOMS[r]
    lamp(r, 0, (x0 + x1) / 2, (y0 + y1) / 2)

switch("living", "x", 0, +1, 3.85)
switch("cocina", "y", 8, +1, 0.95)
switch("bano", "x", 5, +1, 4.15)
switch("renato", "y", 9.5, -1, 8.4)
switch("nueva", "x", 9, +1, 8.75)
switch("s1", "y", 1.5, +1, 10.55)
switch("s2", "y", 1.5, +1, 14.95)
switch("s3", "x", 18, -1, 7.15)
switch("s4", "x", 18, -1, 10.95)
switch("s5", "y", 13.5, -1, 10.55)

# ----------------------------------------------------------------- muebles del frente (living, cocina, baño)
F = "Muebles"
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
box("Mesa_comedor", 5.2, 1.8, 0.72, 6.8, 3.0, 0.78, M["mesa"], F, colision=True)
for i, (x, y) in enumerate(((5.3, 1.9), (6.7, 1.9), (5.3, 2.9), (6.7, 2.9))):
    box(f"Mesa_comedor_pata_{i}", x - 0.04, y - 0.04, 0, x + 0.04, y + 0.04, 0.72, M["mesa"], F)
for i, (x, y, r) in enumerate(((5.6, 1.45, 0), (6.4, 1.45, 8), (5.6, 3.35, -12), (6.6, 3.5, 35))):
    box(f"Silla_{i}_asiento", x - 0.22, y - 0.22, 0.42, x + 0.22, y + 0.22, 0.46, M["mesa"], F, rot=(0, 0, r), colision=True)
    box(f"Silla_{i}_patas", x - 0.2, y - 0.2, 0, x + 0.2, y + 0.2, 0.42, M["mesa"], F, rot=(0, 0, r))
box("Silla_caida", 7.2, 3.9, 0.0, 7.65, 4.35, 0.45, M["mesa"], F, rot=(0, 90, 20), colision=True)

# Cocina
box("Meson_este", 14.35, 0.3, 0, 14.92, 4.92, 0.9, M["meson"], F, colision=True)
box("Meson_fondo", 10.6, 4.35, 0, 14.35, 4.92, 0.9, M["meson"], F, colision=True)
box("Lavaplatos", 14.45, 2.0, 0.85, 14.85, 2.8, 0.91, M["metal"], F)
box("Cocina_estufa", 11.2, 4.4, 0.9, 11.9, 4.9, 0.93, M["negro"], F)
for i, (x, y) in enumerate(((11.38, 4.52), (11.72, 4.52), (11.38, 4.78), (11.72, 4.78))):
    cyl(f"Quemador_{i}", x, y, 0.93, 0.945, 0.08, M["metal"], F, seg=10)
box("Refrigerador", 8.12, 4.2, 0, 8.85, 4.92, 1.85, M["nevera"], F, colision=True)
box("Refrigerador_manilla", 8.82, 4.25, 0.9, 8.86, 4.3, 1.5, M["metal"], F)
box("Mesa_cocina", 9.9, 1.6, 0.72, 11.3, 2.6, 0.76, M["mesa"], F, colision=True)
for i, (x, y) in enumerate(((9.95, 1.65), (11.25, 1.65), (9.95, 2.55), (11.25, 2.55))):
    box(f"Mesa_cocina_pata_{i}", x - 0.03, y - 0.03, 0, x + 0.03, y + 0.03, 0.72, M["mesa"], F)
cyl("Basurero", 13.9, 0.6, 0, 0.6, 0.22, M["metal"], F, colision=True)
for i in range(4):
    sphere(f"Basurero_rebalse_{i}", 13.9 + random.uniform(-0.15, 0.15), 0.6 + random.uniform(-0.15, 0.15),
           0.65 + i * 0.05, 0.16, M["bolsa"], F, scale=(1, 1, 0.8))

# Baño (x 1.5..6.5, y 5..9)
box("Tina", 1.62, 7.95, 0, 3.5, 8.92, 0.55, M["blanco"], F, colision=True)
box("Tina_interior", 1.72, 8.05, 0.25, 3.4, 8.82, 0.56, M["comida"], F)
box("Inodoro_base", 5.6, 8.1, 0, 6.05, 8.7, 0.42, M["blanco"], F, colision=True)
box("Inodoro_estanque", 5.55, 8.65, 0.42, 6.1, 8.92, 0.85, M["blanco"], F, colision=True)
cyl("Inodoro_agua", 5.825, 8.35, 0.42, 0.43, 0.17, M["comida"], F, seg=14)
box("Lavamanos", 1.62, 5.9, 0.8, 2.1, 6.5, 0.88, M["blanco"], F, colision=True)
box("Lavamanos_pie", 1.75, 6.1, 0, 1.9, 6.3, 0.8, M["blanco"], F)
box("Espejo", 1.585, 5.9, 1.25, 1.6, 6.5, 1.85, M["metal"], F, interaccion="leer",
    texto="Abres la boca frente al espejo. Algo se mueve detrás de tus amígdalas: una sombra carnosa que se retrae.",
    texto2="«Debe ser un linfoma. O un quiste. O un parásito.» Ningún tumor late con voluntad propia.")
box("Espejo_mancha", 1.6, 6.0, 1.3, 1.605, 6.3, 1.55, M["mancha_osc"], F)

# ----------------------------------------------------------------- personas (vecinos, Renato, la madre, los despojos)
V = "Vecinos"
def person(name, x, y, rot, shirt, pants=None, skin=None, hair=None, s=1.0, seated=False, pose=None,
           c=V, z=None, rot3=None, **props):
    pants = pants or M["jeans"]; skin = skin or M["piel"]; hair = hair or M["pelo"]
    if z is None:
        z = (0.45 - 0.9 * s) if seated else 0.0
    root = empty(name, (x, y, z), rot3 if rot3 else (0, 0, rot), c=c, **props)
    for side, dx in (("izq", -0.1), ("der", 0.1)):
        piv = empty(f"{name}_pierna_{side}", (dx * s, 0, 0.9 * s), (90 if seated else 0, 0, 0), c=c, parent=root, rol="pierna_" + side)
        box(f"{name}_pierna_{side}_m", -0.07 * s, -0.08 * s, -0.9 * s, 0.07 * s, 0.08 * s, 0, pants, c, parent=piv)
    box(f"{name}_torso", -0.2 * s, -0.12 * s, 0.88 * s, 0.2 * s, 0.12 * s, 1.45 * s, shirt, c, parent=root)
    sphere(f"{name}_cabeza", 0, 0, 1.6 * s, 0.13 * s, skin, c, parent=root)
    sphere(f"{name}_pelo", 0, -0.02 * s, 1.66 * s, 0.135 * s, hair, c, parent=root, scale=(1, 1, 0.75))
    box(f"{name}_nariz", -0.015 * s, 0.11 * s, 1.57 * s, 0.015 * s, 0.15 * s, 1.61 * s, skin, c, parent=root)
    for side, dx in (("izq", -0.26), ("der", 0.26)):
        r = (0, 0, 0)
        if pose == "saludo" and side == "der":
            r = (0, -150, 0)
        if pose == "fumar" and side == "der":
            r = (-130, 0, 20)
        if seated:
            r = (-40, 0, 0)
        piv = empty(f"{name}_brazo_{side}", (dx * s, 0, 1.42 * s), r, c=c, parent=root, rol="brazo_" + side)
        box(f"{name}_brazo_{side}_m", -0.05 * s, -0.05 * s, -0.6 * s, 0.05 * s, 0.05 * s, 0, shirt, c, parent=piv)
        sphere(f"{name}_mano_{side}", 0, 0, -0.63 * s, 0.05 * s, skin, c, parent=piv)
        if pose == "fumar" and side == "der":
            sphere(f"{name}_cigarro", 0, 0.05, -0.68 * s, 0.015, M["brasa"], c, parent=piv)
    return root

def bed(name, x0, y0, x1, y1, head, m_sheet=None, c="Muebles"):
    """Cama: 'head' indica la pared de la cabecera: 'n','s','e','o'."""
    box(name, x0, y0, 0, x1, y1, 0.42, M["mesa"], c, colision=True)
    box(name + "_colchon", x0 + 0.04, y0 + 0.04, 0.42, x1 - 0.04, y1 - 0.04, 0.58, M["colchon"], c)
    hb = {"n": (x0, y1 - 0.08, x1, y1), "s": (x0, y0, x1, y0 + 0.08),
          "e": (x1 - 0.08, y0, x1, y1), "o": (x0, y0, x0 + 0.08, y1)}[head]
    box(name + "_respaldo", hb[0], hb[1], 0, hb[2], hb[3], 1.05, M["mesa"], c)

def lying(name, bx0, by0, bx1, by1, head, shirt, skin, hair, pants=None, s=1.0, **props):
    """Persona acostada boca arriba en una cama, con la cabeza hacia 'head'."""
    zt = 0.58 + 0.12 * s
    L = 1.75 * s
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
    if head == "n":
        loc, r = (cx, by1 - 0.15 - L), (-90, 180, 0)
    elif head == "s":
        loc, r = (cx, by0 + 0.15 + L), (90, 0, 0)
    elif head == "o":
        loc, r = (bx0 + 0.15 + L, cy), (90, 0, -90)
    else:
        loc, r = (bx1 - 0.15 - L, cy), (90, 0, 90)
    return person(name, loc[0], loc[1], 0, shirt, pants or shirt, skin, hair, s=s, c="Personajes",
                  z=zt, rot3=r, **props)

# ----------------------------------------------------------------- cuarto de Renato (x 6.5..9.5, y 5..9)
bed("Cama_renato", 6.65, 5.08, 8.2, 7.0, "s")
box("Cama_renato_sabana", 7.55, 5.6, 0.58, 8.15, 6.95, 0.64, M["sabana"], "Muebles")
lying("Renato", 6.7, 5.08, 7.5, 7.0, "s", M["camisa"], M["piel_gris"], M["pelo2"], M["jeans"],
      interaccion="renato", anim="respira")
box("Comoda", 8.95, 7.95, 0, 9.42, 8.85, 0.85, M["mesa"], "Muebles", colision=True)
cyl("Florero_plastico", 9.18, 8.4, 0.85, 1.05, 0.07, M["vidrio"], "Muebles", seg=10)
hort = sphere("Hortensias_plastico", 9.18, 8.4, 1.17, 0.17, M["hortensia"], "Muebles", scale=(1, 1, 0.8), seg=10,
              interaccion="leer",
              texto="Hortensias. Como se llamaba tu mamá. Al tocarlas notas que son de plástico.",
              texto2="Nunca le dijiste a Renato cómo se llamaba tu mamá. Aquella tarde en la picada te quedaste mudo. Y sin embargo, las hortensias ya estaban aquí.")
for i in range(4):
    sphere(f"Hortensias_plastico_{i}", 9.18 + random.uniform(-0.1, 0.1), 8.4 + random.uniform(-0.1, 0.1),
           1.15 + random.uniform(0, 0.08), 0.09, M["hortensia"], "Muebles", parent=None, seg=8)
box("Velador_renato", 8.35, 5.1, 0, 8.8, 5.55, 0.55, M["mesa"], "Muebles", colision=True)
clothes_rn = [("Camisa_suelo", 7.0, 7.7, M["camisa"]), ("Parka_suelo", 8.6, 6.0, M["ropa3"])]
for nm, x, y, mm in clothes_rn:
    sphere(nm, x, y, 0.05, 0.25, mm, "Suciedad", scale=(1.3, 1.0, 0.2), rot=(0, 0, random.uniform(0, 180)), seg=8)
empty("Inicio_jugador", (7.8, 8.0, 0), (0, 0, 0), c="Casa", inicio=True, yaw=180.0)

# ----------------------------------------------------------------- cuarto de la madre (x 9.5..15, y 5..9)
bed("Cama_madre", 11.0, 5.4, 13.0, 7.4, "o")
box("Cama_madre_sabana", 11.8, 5.45, 0.58, 12.95, 7.35, 0.68, M["sabana_blanca"], "Muebles")
lying("Madre", 11.0, 5.4, 13.0, 7.4, "o", M["camison"], M["piel_vieja"], M["pelo_blanco"], M["camison"],
      s=0.9, interaccion="madre", anim="madre")
box("Velador_madre", 10.4, 5.2, 0, 10.92, 5.72, 0.55, M["mesa"], "Muebles", colision=True)
cyl("Lamparita_madre_base", 10.66, 5.46, 0.55, 0.8, 0.03, M["bronce"], "Muebles", seg=8)
cyl("Lamparita_madre_pantalla", 10.66, 5.46, 0.78, 0.95, 0.12, M["papel"], "Muebles", seg=12, r2=0.07)
sphere("Lamparita_madre", 10.66, 5.46, 0.82, 0.035, M["lampara"], "Muebles", lampara="madre", parpadeo=True)
cyl("Florero_madre", 10.55, 5.35, 0.55, 0.7, 0.05, M["vidrio"], "Muebles", seg=8)
sphere("Hortensias_podridas", 10.55, 5.35, 0.78, 0.12, M["hortensia_podrida"], "Muebles", scale=(1, 1, 0.7), seg=8,
       interaccion="leer", texto="Hortensias de verdad, junto a la lamparita. Se están pudriendo.")
box("Silla_pies_cama", 13.5, 6.15, 0.42, 13.95, 6.6, 0.46, M["mesa"], "Muebles", colision=True)
box("Silla_pies_cama_patas", 13.52, 6.17, 0, 13.93, 6.58, 0.42, M["mesa"], "Muebles")
box("Silla_pies_cama_resp", 13.9, 6.15, 0.46, 13.95, 6.6, 0.95, M["mesa"], "Muebles")
TXT_RET = "Retratos de una mujer joven, de una belleza indescriptible. Es ella. El tiempo la arruinó como un huracán destroza una flor."
for i, (a, z, w, h) in enumerate(((10.3, 1.6, 0.4, 0.5), (11.0, 1.8, 0.3, 0.4), (11.6, 1.5, 0.45, 0.6),
                                   (12.4, 1.75, 0.35, 0.45), (13.1, 1.55, 0.4, 0.5))):
    picture(f"Retrato_madre_s_{i}", "x", 5, +1, a, z, w, h, TXT_RET)
for i, (a, z, w, h) in enumerate(((10.2, 1.7, 0.35, 0.45), (10.9, 1.5, 0.45, 0.55), (11.8, 1.8, 0.3, 0.4),
                                   (12.6, 1.55, 0.4, 0.5))):
    picture(f"Retrato_madre_n_{i}", "x", 9, -1, a, z, w, h, TXT_RET)
for i, (a, z) in enumerate(((5.7, 1.6), (8.4, 1.7))):
    picture(f"Retrato_madre_e_{i}", "y", XW, -1, a, z, 0.35, 0.45, TXT_RET)
for i in range(5):
    sphere(f"Mancha_madre_{i}", random.uniform(10, 14.5), random.uniform(5.5, 8.6), 0.004, 0.3,
           M["mancha_osc"], "Suciedad", scale=(random.uniform(0.6, 1.4), random.uniform(0.6, 1.4), 0.01), seg=10)

# ----------------------------------------------------------------- habitación nueva (x 6..9.75, y 9..13.5)
box("Nueva_cama_sin_colchon", 6.15, 11.4, 0, 7.55, 13.35, 0.4, M["mesa"], "Muebles", colision=True)
box("Nueva_respaldo", 6.15, 13.27, 0, 7.55, 13.35, 1.0, M["mesa"], "Muebles")
for i, (x, y) in enumerate(((8.9, 12.9), (9.25, 12.95), (9.05, 12.55))):
    cyl(f"Lata_pintura_{i}", x, y, 0, 0.3, 0.14, M["pintura"], "Muebles", seg=14, colision=True,
        interaccion="leer", texto="Latas de pintura. Color: beige. «Quiero que te sientas cómodo aquí», dijo Renato. Esta habitación es para ti.")
box("Brocha", 8.6, 12.3, 0.0, 8.95, 12.36, 0.03, M["mesa"], "Muebles", rot=(0, 0, 30))
box("Plastico_piso", 7.8, 9.4, 0, 9.6, 12.2, 0.004, M["vidrio"], "Muebles")
for i, (a, z) in enumerate(((6.8, 1.6), (7.5, 1.8), (8.2, 1.55))):
    picture(f"Retrato_nueva_{i}", "x", 13.5, -1, a + 0.3, z, 0.35, 0.45, TXT_RET)
planks("Ventana_nueva_sellada", "y", 9.75, -1, 10.0, 11.6, 0.9, 2.1)

# ----------------------------------------------------------------- piezas de los antiguos estudiantes
STUDENTS = [
    # (id, cama x0,y0,x1,y1, cabecera, velador x0,y0, ventana sellada (along, fixed, side, a0, a1), datos)
    ("s1", (4.85, 11.35, 5.85, 13.35), "n", (4.25, 12.85), ("x", 9, +1, 2.6, 4.0),
     "Credencial Universidad de Valparaíso. Tomás Herrera Quiroz. Medicina. 2009. El muchacho de la foto sonríe."),
    ("s2", (4.85, 15.85, 5.85, 17.85), "n", (4.25, 17.35), ("x", 13.5, +1, 2.6, 4.0),
     "Credencial estudiantil. Felipe Araya Soto. Pedagogía en Música. 2012. La foto está desteñida."),
    ("s3", (6.15, 13.62, 7.15, 15.62), "s", (7.3, 13.62), ("y", 9.75, -1, 14.6, 16.2),
     "Credencial vencida. Ignacio Contreras Leiva. Arquitectura. 2016. Cubierta de polvo."),
    ("s4", (12.4, 13.62, 13.4, 15.62), "s", (11.8, 13.62), ("y", 9.75, +1, 14.6, 16.2),
     "Credencial estudiantil. Joaquín Rojas Pino. Enfermería. 2019. Tenía tu edad."),
    ("s5", (9.9, 11.35, 10.9, 13.35), "n", (11.05, 12.85), ("x", 9, +1, 11.0, 12.6),
     "Credencial estudiantil. Diego Fuentes Vera. Medicina. 2023. Es del año pasado."),
]
PHOTO_WALL = dict(s1=("y", 6, -1), s2=("y", 6, -1), s3=("y", 6, +1), s4=("y", 13.5, -1), s5=("y", 9.75, +1))
DESPOJO = "El despojo de lo que alguna vez fue un hombre: una envoltura de piel acartonada, colapsada sobre sus propios huesos, como una fruta dejada al sol."
for k, (sid, (bx0, by0, bx1, by1), head, (vx, vy), win, cred) in enumerate(STUDENTS):
    bed(f"Cama_{sid}", bx0, by0, bx1, by1, head)
    lying(f"Despojo_{sid}", bx0, by0, bx1, by1, head, M["trapo"], M["piel_seca"], M["pelo_seco"], M["trapo"],
          s=0.95, interaccion="leer", texto=DESPOJO)
    box(f"Velador_{sid}", vx, vy, 0, vx + 0.45, vy + 0.45, 0.55, M["mesa"], "Muebles", colision=True)
    # credencial
    card = box(f"Credencial_{sid}", vx + 0.05, vy + 0.08, 0.55, vx + 0.14, vy + 0.22, 0.556, M["credencial"], "Muebles",
               interaccion="leer", texto=cred, credencial=True)
    box(f"Credencial_{sid}_banda", vx + 0.05, vy + 0.18, 0.556, vx + 0.14, vy + 0.22, 0.558, M["banda"], "Muebles", parent=card)
    # llave
    kx, ky = vx + 0.3, vy + 0.22
    key = cyl(f"Llave_{sid}", kx, ky, 0.555, 0.565, 0.035, M["llave"], "Muebles", seg=10,
              interaccion="llave", llave=k + 1)
    box(f"Llave_{sid}_cana", -0.012, 0.03, -0.004, 0.012, 0.13, 0.004, M["llave"], "Muebles", parent=key)
    box(f"Llave_{sid}_diente", -0.012, 0.10, -0.004, 0.035, 0.12, 0.004, M["llave"], "Muebles", parent=key)
    # ventana sellada y retratos
    al, fx, sd, a0, a1 = win
    planks(f"Ventana_sellada_{sid}", al, fx, sd, a0, a1, 0.9, 2.1)
    x0, y0, x1, y1 = ROOMS[sid]
    pal, pfx, psd = PHOTO_WALL[sid]
    pa0, pa1 = (x0, x1) if pal == "x" else (y0, y1)
    for j in range(3):
        picture(f"Retrato_{sid}_{j}", pal, pfx, psd, pa0 + (pa1 - pa0) * (j + 1) / 4, 1.6 + 0.15 * (j % 2), 0.3, 0.4, TXT_RET)
    # polvo y telarañas
    for j in range(3):
        sphere(f"Polvo_{sid}_{j}", random.uniform(x0 + 0.4, x1 - 0.4), random.uniform(y0 + 0.4, y1 - 0.4), 0.004,
               0.18, M["mancha"], "Suciedad", scale=(random.uniform(0.7, 1.3), random.uniform(0.7, 1.3), 0.01), seg=10)

# ----------------------------------------------------------------- suciedad del resto de la casa
S = "Suciedad"
def stain(name, x, y, r, sx=1.0, sy=1.0, m=None, z=0.0):
    cyl(name, x, y, z + 0.002, z + 0.006, r, m or M["mancha"], S, seg=10, sx=sx, sy=sy, rot=(0, 0, random.uniform(0, 180)))

def bag(name, x, y, s=1.0):
    sphere(name, x, y, 0.27 * s, 0.3 * s, M["bolsa"], S, scale=(1, 0.9, 0.9), colision=True)
    cyl(name + "_nudo", x, y, 0.5 * s, 0.62 * s, 0.05 * s, M["bolsa"], S, seg=6, r2=0.09 * s)

def bottle(name, x, y, lying_=False, green=True, z=0.0):
    m = M["botella_v"] if green else M["botella_c"]
    if lying_:
        cyl(name, x, y, z + 0.035, z + 0.035 + 0.25, 0.035, m, S, seg=8, rot=(90, 0, random.uniform(0, 360)))
    else:
        cyl(name, x, y, z, z + 0.22, 0.035, m, S, seg=8)
        cyl(name + "_cuello", x, y, z + 0.22, z + 0.29, 0.015, m, S, seg=6, r2=0.012)

def paper(name, x, y, z=0.0):
    box(name, x - 0.105, y - 0.15, z + 0.003, x + 0.105, y + 0.15, z + 0.006, M["papel"], S,
        rot=(0, 0, random.uniform(0, 180)))

def pizza(name, x, y, z=0.0):
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

def web(name, x, y, sxn, syn, size=0.6):
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
    bottle(f"Botella_living_{i}", x, y, lying_=l, green=g, z=0.42 if (i < 2) else (0.78 if i == 4 else 0.0))
for i in range(8):
    paper(f"Diario_{i}", random.uniform(1, 7.5), random.uniform(0.4, 4.6))
bag("Bolsa_living_1", 7.6, 0.45)
bag("Bolsa_living_2", 7.65, 1.05, 0.8)
bag("Bolsa_living_3", 0.45, 0.45, 0.9)
clothes("Ropa_sofa", 0.6, 2.7, 0.45)
dishes("Platos_comedor", 5.7, 2.2, 0.78, 4)
dishes("Platos_comedor_2", 6.4, 2.6, 0.78, 3)
wall_patch("Mancha_muro_living", "y", 0, 2.5, 1.2, 0.8, 0.5, M["mancha"], side=1)

# Cocina
for i in range(7):
    stain(f"Mancha_cocina_{i}", random.uniform(8.5, 14.0), random.uniform(0.5, 4.0),
          random.uniform(0.15, 0.4), random.uniform(0.6, 1.4), random.uniform(0.6, 1.4), M["grasa"])
for i, (x, y) in enumerate(((14.6, 1.0), (14.65, 3.4), (13.1, 4.6), (10.9, 4.6))):
    dishes(f"Platos_meson_{i}", x, y, 0.9, random.randint(4, 8))
dishes("Platos_lavaplatos", 14.65, 2.4, 0.86, 7)
for i in range(4):
    cyl(f"Olla_{i}", 11.4 + (i % 2) * 0.35, 4.45 + (i // 2) * 0.25, 0.93, 1.08, 0.12, M["metal"], S, seg=12)
bag("Bolsa_cocina_1", 13.4, 0.4)
bag("Bolsa_cocina_2", 13.5, 0.95, 0.85)
bag("Bolsa_cocina_3", 9.0, 0.5)
for i in range(5):
    bottle(f"Botella_cocina_{i}", random.uniform(9, 13.5), random.uniform(0.6, 3.8), lying_=True, green=i % 2 == 0)
for i in range(6):
    wall_patch(f"Grasa_muro_{i}", "y", XW, random.uniform(0.6, 4.5), random.uniform(1.0, 1.8),
               random.uniform(0.2, 0.5), random.uniform(0.15, 0.4), M["grasa"], side=-1)
wall_patch("Grasa_estufa", "x", 5, 11.55, 1.25, 1.0, 0.6, M["grasa"], side=-1)

# Baño
for i in range(12):
    wall_patch(f"Moho_muro_{i}", "x", 9, random.uniform(1.8, 6.2), random.uniform(1.7, 2.6),
               random.uniform(0.15, 0.6), random.uniform(0.1, 0.4), M["moho"], side=-1)
for i in range(5):
    box(f"Moho_techo_{i}", random.uniform(1.8, 5.5), random.uniform(7.0, 8.6), H - 0.004,
        random.uniform(1.8, 5.5) + 0.3, random.uniform(7.0, 8.6) + 0.2, H - 0.001, M["moho"], S)
stain("Charco_bano", 4.2, 7.2, 0.5, 1.4, 0.8, M["grasa"])
for i in range(3):
    cyl(f"Rollo_papel_{i}", 5.0 + i * 0.15, 8.7, 0.0, 0.11, 0.055, M["papel"], S, seg=10)

# Pasillo: el suelo rayado por la misma ruta recorrida una y otra vez
for i in range(14):
    y = 5.2 + i * 0.95
    box(f"Rayon_pasillo_o_{i}", 0.55 + random.uniform(-0.1, 0.1), y, 0.0005, 0.62 + random.uniform(-0.1, 0.1), y + 0.9, 0.003,
        M["rayon"], S, rot=(0, 0, random.uniform(-4, 4)))
for i in range(13):
    x = 0.8 + i * 1.0
    box(f"Rayon_pasillo_f_{i}", x, 18.65, 0.0005, x + 0.95, 18.72, 0.003, M["rayon"], S, rot=(0, 0, random.uniform(-4, 4)))
for i in range(10):
    y = 9.1 + i * 1.0
    box(f"Rayon_pasillo_e_{i}", 14.2, y, 0.0005, 14.27, y + 0.95, 0.003, M["rayon"], S, rot=(0, 0, random.uniform(-4, 4)))

# Telarañas
for i, (x, y, sx, sy) in enumerate((
    (T / 2, T / 2, 1, 1), (8 - T / 2, T / 2, -1, 1), (XW - T / 2, T / 2, -1, 1), (T / 2, YD - T / 2, 1, -1),
    (XW - T / 2, YD - T / 2, -1, -1), (1.5 + T / 2, 9 + T / 2, 1, 1), (6 - T / 2, 18 - T / 2, -1, -1),
    (9.75 + T / 2, 18 - T / 2, 1, -1), (13.5 - T / 2, 9 + T / 2, -1, 1), (XW - T / 2, 9 - T / 2, -1, -1),
    (9.5 + T / 2, 5 + T / 2, 1, 1),
)):
    web(f"Telarana_{i}", x, y, sx, sy, random.uniform(0.4, 0.8))

# =================================================================== EXTERIOR (noche, niebla)
X = "Exterior"
box("Suelo_pasto", -60, -45, -0.4, 75, 26, -0.02, M["pasto"], X, uvscale=4)
box("Vereda_casa", -60, -6.5, -0.02, 75, -5.0, 0.03, M["vereda"], X)
box("Calle", -60, -12.5, -0.03, 75, -6.5, 0.0, M["asfalto"], X)
for i in range(-12, 15):
    box(f"Linea_{i}", i * 5, -9.58, 0.0, i * 5 + 2.5, -9.42, 0.005, M["linea"], X)
box("Vereda_enfrente", -60, -14.0, -0.02, 75, -12.5, 0.03, M["vereda"], X)
box("Camino_entrada", 4.2, -5.0, -0.02, 5.2, -0.1, 0.02, M["vereda"], X)

# Faroles
for i, x in enumerate((-2.0, 13.0)):
    box(f"Farol_{i}_poste", x - 0.06, -5.9, 0, x + 0.06, -5.78, 4.2, M["poste"], X)
    box(f"Farol_{i}_brazo", x - 0.04, -6.6, 4.1, x + 0.04, -5.8, 4.18, M["poste"], X)
    sphere(f"Farol_{i}", x, -6.6, 4.0, 0.15, M["farol"], X, lampara="calle")

def tree(name, x, y, h=4.0, r=1.6):
    cyl(name + "_tronco", x, y, 0, h * 0.55, 0.18, M["tronco"], X, seg=8)
    sphere(name + "_copa", x, y, h * 0.7, r, M["hojas"], X, seg=10, scale=(1, 1, 1.15))

for i, (x, y, h) in enumerate(((-5, -3, 4.5), (20, -3.5, 5), (14.5, -16, 4.2), (-7, -18, 5), (25, -20, 4.6))):
    tree(f"Arbol_{i}", x, y, h)

cx, cy = 21.0, -8.0
box("Auto_carroceria", cx - 2.1, cy - 0.85, 0.3, cx + 2.1, cy + 0.85, 0.95, M["auto"], X)
box("Auto_cabina", cx - 1.1, cy - 0.8, 0.95, cx + 0.9, cy + 0.8, 1.5, M["auto"], X)
box("Auto_vidrios", cx - 1.05, cy - 0.82, 1.0, cx + 0.85, cy + 0.82, 1.45, M["vidrio"], X)
for i, (dx, dy) in enumerate(((-1.4, -0.85), (1.4, -0.85), (-1.4, 0.85), (1.4, 0.85))):
    cyl(f"Auto_rueda_{i}", cx + dx, cy + dy - 0.1, 0.0, 0.2, 0.33, M["rueda"], X, seg=14, rot=(90, 0, 0))

def roof(name, x0, y0, x1, y1, ridge_along_x=True, z=3.1, top=5.0):
    if ridge_along_x:
        poly(name, [(x0 - 0.4, y0 - 0.4, z), (x1 + 0.4, y0 - 0.4, z), (x1 + 0.4, y1 + 0.4, z),
                    (x0 - 0.4, y1 + 0.4, z), (x0 - 0.4, (y0 + y1) / 2, top), (x1 + 0.4, (y0 + y1) / 2, top)],
             [(0, 1, 5, 4), (3, 4, 5, 2), (0, 4, 3), (1, 2, 5)], M["techo_rojo"], X)
    else:
        poly(name, [(x0 - 0.4, y0 - 0.4, z), (x1 + 0.4, y0 - 0.4, z), (x1 + 0.4, y1 + 0.4, z),
                    (x0 - 0.4, y1 + 0.4, z), ((x0 + x1) / 2, y0 - 0.4, top), ((x0 + x1) / 2, y1 + 0.4, top)],
             [(0, 4, 5, 3), (1, 2, 5, 4), (0, 1, 4), (3, 5, 2)], M["techo_rojo"], X)

def neighbor_house(name, x0, y0, x1, y1, m, win_wall, win, lamp_pos, lamp_name, ridge_x=True):
    """Casa vecina con una ventana iluminada. win_wall: 's','n','o','e'; win=(a0,a1)."""
    walls = {"s": ("x", y0, x0, x1), "n": ("x", y1, x0, x1), "o": ("y", x0, y0, y1), "e": ("y", x1, y0, y1)}
    for k, (al, fx, a0, a1) in walls.items():
        ops = [(win[0], win[1], 0.8, 2.3)] if k == win_wall else []
        wall(f"{name}_{k}", al, fx, a0, a1, ops, m=m, c=X, h=3.0, t=0.2)
    box(f"{name}_piso", x0, y0, -0.05, x1, y1, 0.02, M["piso_vec"], X)
    box(f"{name}_cielo", x0 - 0.1, y0 - 0.1, 3.0, x1 + 0.1, y1 + 0.1, 3.1, M["interior_vec"], X)
    al, fx = walls[win_wall][:2]
    if al == "x":
        box(f"{name}_vidrio", win[0], fx - 0.01, 0.8, win[1], fx + 0.01, 2.3, M["vidrio"], X)
    else:
        box(f"{name}_vidrio", fx - 0.01, win[0], 0.8, fx + 0.01, win[1], 2.3, M["vidrio"], X)
    sphere(f"{name}_lampara", *lamp_pos, 0.08, M["lampara"], X, lampara=lamp_name)
    roof(f"{name}_techo", x0, y0, x1, y1, ridge_x)

# Casa de enfrente: la vecina de pie en la ventana; el vecino fuma en la puerta
neighbor_house("Vecinos_enfrente", 0.0, -23.0, 12.0, -15.0, M["fachada"], "n", (2.0, 7.0), (4.5, -18.5, 2.5), "vecinos")
box("Vecinos_enfrente_muro_int", 0.1, -22.88, 0, 8.0, -22.86, 3.0, M["interior_vec"], X)
box("Vecinos_enfrente_puerta", 9.0, -14.92, 0, 10.0, -14.88, 2.1, M["puerta"], X)
box("Vecinos_enfrente_sofa", 6.4, -20.5, 0, 7.3, -18.0, 0.45, M["polera2"], X)
box("Vecinos_enfrente_mesa", 2.5, -18.4, 0.7, 4.0, -17.2, 0.75, M["mesa"], X)
for i, x in enumerate((1.0, 1.8, 8.0, 11.4)):
    sphere(f"Arbusto_vecinos_{i}", x, -14.4, 0.35, 0.45, M["hojas"], X, scale=(1, 1, 0.8), seg=8)

# Casa del lado oeste: alguien ve televisión
neighbor_house("Vecinos_oeste", -14.0, 7.0, -5.0, 16.0, M["fachada3"], "e", (10.0, 13.0), (-7.5, 11.5, 2.5), "vecinos3",
               ridge_x=False)
box("Vecinos_oeste_tv", -12.2, 10.6, 0.6, -12.1, 12.2, 1.4, M["tv_on"], X, anim="tv")
box("Vecinos_oeste_cortina", -5.2, 10.0, 0.8, -5.15, 10.6, 2.3, M["ropa2"], X)

# Casa del lado este: el niño en pijama en la ventana
neighbor_house("Vecinos_este", 19.0, 9.0, 29.0, 19.0, M["fachada2"], "o", (13.5, 16.0), (21.0, 14.5, 2.5), "vecinos2",
               ridge_x=False)

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

fence("Cerca_este", 17.0, -4.5, 17.0, 23.0)
fence("Cerca_oeste", -3.0, -4.5, -3.0, 23.0)
fence("Cerca_fondo", -3.0, 23.0, 17.0, 23.0)

# La bahía de Valparaíso, abajo: el puerto encendido
box("Mar", -400, 26, -40, 400, 600, -39.5, M["mar"], X)
box("Acantilado", -200, 25.9, -40, 200, 26.0, -0.02, M["cerro"], X)
box("Cerros_lejanos", -400, 420, -40, 400, 470, 60, M["cerro"], X)
rnd = random.Random(11)
for i in range(160):
    x = rnd.uniform(-380, 380); z = rnd.uniform(-35, 55)
    box(f"Luz_ciudad_{i}", x, 419.0, z, x + rnd.uniform(0.8, 2.0), 419.5, z + 0.8, M["luz_ciudad"], X, sinniebla=True)
for i in range(12):
    x = rnd.uniform(-200, 200); y = rnd.uniform(90, 360)
    box(f"Barco_{i}", x, y, -39.5, x + rnd.uniform(6, 14), y + 2.5, -37.5, M["cerro"], X)
    for j in range(3):
        box(f"Barco_{i}_luz_{j}", x + j * 3, y - 0.2, -37.4, x + j * 3 + 0.8, y, -36.8, M["luz_barco"], X, sinniebla=True)

# =================================================================== VECINOS
# La vecina de enfrente: de pie en su ventana, mirando hacia acá
person("Vecina_ventana", 4.2, -15.9, 0, M["polera4"], M["pantalon"], hair=M["pelo"], anim="mirar")
# El vecino que fuma en su puerta
person("Vecino_fumando", 9.5, -14.4, 10, M["polera2"], M["pantalon"], M["piel2"], M["pelo"], pose="fumar", anim="fumar")
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
# Vecino del oeste viendo TV (sentado, mira hacia -x)
box("Vecinos_oeste_sillon", -9.3, 10.9, 0, -8.5, 12.0, 0.45, M["polera3"], X)
person("Vecino_tv", -9.0, 11.5, 90, M["polera3"], seated=True, hair=M["pelo2"], anim="sentado")
# Niño en pijama en la ventana de la casa del este, saludando (mira hacia -x)
person("Nino", 19.6, 14.8, 90, M["ropa1"], M["ropa1"], hair=M["pelo"], s=0.65, pose="saludo", anim="saludo")

# =================================================================== exportar
bpy.context.view_layer.update()
try:
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, relative_remap=True)
except Exception as ex:
    print("No se pudo guardar .blend:", ex)

bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", export_extras=True, export_yup=True)
print(f"OK: {len(bpy.data.objects)} objetos -> {OUT_GLB} ({os.path.getsize(OUT_GLB) / 1024:.0f} KB)")
