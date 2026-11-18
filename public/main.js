import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

// "Lengua materna" — adaptación jugable del cuento. Eres Esteban: despiertas en el cuarto de Renato
// y tienes que salir de la casa. La puerta de entrada tiene cinco cerraduras.

// ------------------------------------------------------------------ escena (noche, niebla de Playa Ancha)
const canvas = document.getElementById('game');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;

const scene = new THREE.Scene();
const NIGHT = 0x121722;
scene.background = new THREE.Color(NIGHT);
scene.fog = new THREE.Fog(NIGHT, 6, 42);

const camera = new THREE.PerspectiveCamera(70, innerWidth / innerHeight, 0.05, 900);
const EYE = 1.62;
camera.position.set(8, EYE, -8.1);

scene.add(new THREE.HemisphereLight(0x8a9cc0, 0x241a14, 0.22));
const moon = new THREE.DirectionalLight(0x9fb4ff, 0.3);
moon.position.set(-15, 30, -45);
moon.target.position.set(7, 0, -9);
scene.add(moon, moon.target);

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

// ------------------------------------------------------------------ UI
const $ = (id) => document.getElementById(id);
const ui = { overlay: $('overlay'), play: $('play'), loading: $('loading'), pct: $('pct'), hud: $('hud'),
  room: $('room'), goal: $('goal'), keys: $('keys'), prompt: $('prompt'), msg: $('msg'), voice: $('voice'),
  vignette: $('vignette'), ending: $('ending'), endTitle: $('ending-title'), endText: $('ending-text') };

let msgTimer = 0;
const queue = [];
let busyUntil = 0;
function say(text, secs = 5) {
  ui.msg.textContent = text;
  ui.msg.classList.add('show');
  clearTimeout(msgTimer);
  busyUntil = performance.now() + secs * 1000;
  msgTimer = setTimeout(() => ui.msg.classList.remove('show'), secs * 1000);
}
// mensajes encadenados (no se pisan entre ellos)
function tell(...lines) {
  for (const l of lines) queue.push(l);
}
function pumpQueue() {
  if (queue.length && performance.now() > busyUntil) {
    const t = queue.shift();
    say(t, Math.max(4, Math.min(9, t.length / 18)));
  }
}

let throatUntil = 0;
function throat(secs = 2.5) {
  throatUntil = performance.now() + secs * 1000;
  ui.vignette.classList.add('pulse');
  setTimeout(() => { if (performance.now() >= throatUntil - 50) ui.vignette.classList.remove('pulse'); }, secs * 1000);
}
function whisper(text) {
  ui.voice.textContent = text;
  ui.voice.classList.add('show');
  throat(3);
  setTimeout(() => ui.voice.classList.remove('show'), 3500);
}

// ------------------------------------------------------------------ controles
const controls = new PointerLockControls(camera, document.body);
let started = false, ended = false;
ui.play.addEventListener('click', () => controls.lock());
controls.addEventListener('lock', () => {
  ui.overlay.classList.add('hidden');
  ui.hud.hidden = false;
  if (!started) { started = true; intro(); }
});
controls.addEventListener('unlock', () => {
  if (ended) return;
  ui.overlay.classList.remove('hidden');
  ui.play.textContent = 'Continuar';
});
$('again').addEventListener('click', () => location.reload());

const keys = {};
addEventListener('keydown', (e) => {
  keys[e.code] = true;
  if (e.code === 'KeyE' && controls.isLocked && !ended) interact();
});
addEventListener('keyup', (e) => { keys[e.code] = false; });
addEventListener('blur', () => { for (const k in keys) keys[k] = false; });

// ------------------------------------------------------------------ mundo
const colliders = [];      // { box, obj, dyn }
const doors = [];          // puertas interiores con bisagra
const locks = [];          // cerraduras de la puerta principal
const roomLights = {};     // habitacion -> { on, lights[], bulbs[] }
const flickers = [];       // luces que parpadean
const animated = [];
let world = null;
let frontDoor = null;

function findFlag(o, key) {
  for (let n = o; n; n = n.parent) if (n.userData && n.userData[key] !== undefined && n.userData[key] !== null) return n;
  return null;
}

const OFF_AT_START = new Set(['s1', 's2', 's3', 's4', 's5', 'nueva']);

const loader = new GLTFLoader();
loader.load('assets/casa.glb', (gltf) => {
  world = gltf.scene;
  scene.add(world);
  world.updateMatrixWorld(true);

  world.traverse((o) => {
    const d = o.userData || {};
    if (o.isMesh) {
      if (o.material.transparent) o.material.depthWrite = false;
      if (findFlag(o, 'sinniebla')) o.material.fog = false;
    }
    if (d.colision) colliders.push({ box: new THREE.Box3().setFromObject(o), obj: o, dyn: !!findFlag(o, 'giro') });
    if (d.interaccion === 'puerta_int') doors.push({ pivot: o, open: false, t: 0, giro: d.giro, base: o.rotation.y });
    if (d.interaccion === 'puerta') frontDoor = o;
    if (d.cerradura) { o.material = o.material.clone(); locks[d.cerradura - 1] = o; }
    if (d.inicio) {
      camera.position.set(o.position.x, EYE, o.position.z);
      camera.rotation.set(0, THREE.MathUtils.degToRad(d.yaw || 0), 0, 'YXZ');
    }
    if (d.lampara) addLamp(o, d.lampara, !!d.parpadeo);
    if (d.anim) setupAnim(o, d.anim);
  });

  for (const r in roomLights) setRoom(r, !OFF_AT_START.has(r));
  mergeStatic(world);
  ui.loading.hidden = true;
  ui.play.hidden = false;
}, (ev) => {
  if (ev.total) ui.pct.textContent = Math.round((ev.loaded / ev.total) * 100) + '%';
}, (err) => {
  ui.loading.textContent = 'No se pudo cargar la casa: ' + err.message;
});

// Une en una sola malla por material todo lo que no se mueve ni se usa: de ~1200 a ~100 llamadas de dibujo.
const DYNAMIC_KEYS = ['interaccion', 'anim', 'lampara', 'rol', 'cerradura', 'giro'];
function mergeStatic(root) {
  root.updateMatrixWorld(true);
  const groups = new Map();
  root.traverse((o) => {
    if (!o.isMesh || DYNAMIC_KEYS.some((k) => findFlag(o, k))) return;
    const key = o.material.uuid;
    if (!groups.has(key)) groups.set(key, { mat: o.material, meshes: [] });
    groups.get(key).meshes.push(o);
  });
  for (const { mat, meshes } of groups.values()) {
    if (meshes.length < 2) continue;
    const geos = meshes.map((m) => {
      const g = m.geometry.clone().applyMatrix4(m.matrixWorld);
      for (const name of Object.keys(g.attributes)) if (!['position', 'normal', 'uv'].includes(name)) g.deleteAttribute(name);
      return g.index ? g : g.setIndex([...Array(g.attributes.position.count).keys()]);
    });
    const merged = mergeGeometries(geos, false);
    if (!merged) continue;
    meshes.forEach((m) => m.parent.remove(m));
    const mesh = new THREE.Mesh(merged, mat);
    mesh.name = 'Fusion_' + mat.name;
    root.add(mesh);
  }
}

const LAMP = {
  madre: { color: 0xffb36b, i: 1.6, d: 3.5 },
  calle: { color: 0xffc27a, i: 30, d: 18 },
  vecinos: { color: 0xffe2b0, i: 6, d: 7 }, vecinos2: { color: 0xffe2b0, i: 5, d: 6 }, vecinos3: { color: 0x9db8ff, i: 3, d: 6 },
  pasillo: { color: 0xffcf8f, i: 5, d: 6 },
};
function addLamp(bulb, room, flicker) {
  const p = new THREE.Vector3();
  bulb.getWorldPosition(p);
  const cfg = LAMP[room] || { color: 0xffd29a, i: 8, d: 8 };
  const light = new THREE.PointLight(cfg.color, cfg.i, cfg.d, 1.6);
  light.position.copy(p).add(new THREE.Vector3(0, room === 'madre' ? 0.05 : -0.15, 0));
  scene.add(light);
  const r = (roomLights[room] ||= { on: true, lights: [], bulbs: [] });
  r.lights.push(light);
  bulb.material = bulb.material.clone();
  r.bulbs.push(bulb);
  if (flicker) flickers.push({ light, bulb, base: cfg.i, room });
}

function setRoom(room, on) {
  const r = roomLights[room];
  if (!r) return;
  r.on = on;
  r.lights.forEach((l) => (l.visible = on));
  r.bulbs.forEach((b) => (b.material.emissiveIntensity = on ? 6 : 0));
}

// ------------------------------------------------------------------ historia: estado
const state = { keys: 0, credRead: 0, motherPrimed: false, frontTried: false, visited: new Set(), reads: new Map() };

function intro() {
  tell('Al despertar te sientes completamente vacío, como una cáscara. La garganta te arde.',
       'Renato duerme a tu lado, extrañamente pálido, casi gris.',
       'Tienes que salir de esta casa. Para llegar a la puerta hay que pasar por el cuarto de su madre.');
  throat(3);
  scheduleWhisper(40);
}

const WHISPERS = ['Me dejaste sola, Esteban.', 'Esteban… ¿por qué me abandonaste?', 'Pollito…',
  'No vuelvas a dejarme sola.', '¿No te pica la garganta por un poco de atención?'];
let nextWhisper = Infinity;
function scheduleWhisper(base) {
  const k = state.keys;
  nextWhisper = performance.now() + (base ?? (55 - k * 7 + Math.random() * 25)) * 1000;
}

const ZONES = [
  ['renato', 'Cuarto de Renato', 6.5, 5, 9.5, 9], ['madre', 'Cuarto de la madre', 9.5, 5, 15, 9],
  ['bano', 'Baño', 1.5, 5, 6.5, 9], ['nueva', 'Habitación nueva', 6, 9, 9.75, 13.5],
  ['s1', 'Pieza 1', 1.5, 9, 6, 13.5], ['s2', 'Pieza 2', 1.5, 13.5, 6, 18], ['s3', 'Pieza 3', 6, 13.5, 9.75, 18],
  ['s4', 'Pieza 4', 9.75, 13.5, 13.5, 18], ['s5', 'Pieza 5', 9.75, 9, 13.5, 13.5],
  ['living', 'Living-comedor', 0, 0, 8, 5], ['cocina', 'Cocina', 8, 0, 15, 5], ['pasillo', 'Pasillo', 0, 5, 15, 19.5],
];
function currentZone() {
  const x = camera.position.x, y = -camera.position.z; // coordenadas de Blender
  return ZONES.find(([, , x0, y0, x1, y1]) => x >= x0 && x < x1 && y >= y0 && y < y1) || ZONES[ZONES.length - 1];
}

function onEnterZone(id) {
  if (state.visited.has(id)) return;
  const firstStudent = /^s\d$/.test(id) && ![...state.visited].some((v) => /^s\d$/.test(v));
  state.visited.add(id);
  if (id === 'madre') {
    tell('Una oscuridad que parece emerger de un abismo sin fondo. La ventana está sellada; solo una lamparita parpadeante ilumina su rostro.',
         'Las paredes, de un blanco helado, están cubiertas de una capa oleosa color café. La anciana duerme.');
  } else if (id === 'pasillo') {
    tell('Un largo pasillo que se retuerce en forma de U, repleto de puertas.',
         'El suelo está rayado, gastado, como si alguien hubiera recorrido esta misma ruta una y otra vez.');
  } else if (id === 'nueva') {
    tell('Una habitación nueva, idéntica a la de Renato. Huele a pintura fresca.');
  } else if (id === 'living') {
    tell('El aire es húmedo y viciado, cargado de un peso invisible que oprime el pecho.');
  } else if (/^s\d$/.test(id)) {
    if (firstStudent) {
      tell('Una pieza que antes se arrendaba a estudiantes. La ventana sellada, el mosaico de fotografías…',
           'Y una figura sobre la cama.');
      throat(2);
    } else {
      tell('La misma estructura. La ventana sellada, las fotografías. Otra figura sobre la cama.');
    }
  }
}

// ------------------------------------------------------------------ interacción
const ray = new THREE.Raycaster();
ray.far = 2.6;
const center = new THREE.Vector2(0, 0);
let currentTarget = null, lastRayAt = 0;

function target() {
  if (!world) return null;
  ray.setFromCamera(center, camera);
  // el primer objeto sólido o interactuable que mira el jugador (los vidrios sin interacción no bloquean)
  const hit = ray.intersectObject(world, true)
    .find((h) => findFlag(h.object, 'interaccion') || !h.object.material.transparent);
  return hit ? findFlag(hit.object, 'interaccion') : null;
}

function promptFor(t) {
  if (!t) return '';
  const d = t.userData;
  switch (d.interaccion) {
    case 'puerta': return state.keys >= 5 ? '[E] Abrir las cinco cerraduras' : '[E] Abrir la puerta';
    case 'puerta_int': return doors.find((x) => x.pivot === t)?.open ? '[E] Cerrar' : '[E] Abrir';
    case 'interruptor': return `[E] ${roomLights[d.habitacion]?.on ? 'Apagar' : 'Encender'} la luz`;
    case 'ventana': return '[E] Mirar por la ventana';
    case 'llave': return '[E] Tomar la llave';
    case 'leer': return '[E] Examinar';
    case 'madre': return state.keys >= 5 && state.motherPrimed ? '[E] Acercarte a ella' : '[E] Mirarla';
    case 'renato': return '[E] Mirar a Renato';
  }
  return '';
}

function interact() {
  const t = currentTarget = target();
  if (!t) return;
  const d = t.userData;
  if (d.interaccion !== 'puerta_int' && d.interaccion !== 'interruptor') queue.length = 0;
  switch (d.interaccion) {
    case 'puerta': return frontDoorAction();
    case 'puerta_int': {
      const door = doors.find((x) => x.pivot === t);
      if (door) door.open = !door.open;
      return;
    }
    case 'interruptor': return setRoom(d.habitacion, !roomLights[d.habitacion].on);
    case 'ventana': return say(d.texto || 'Afuera la vida sigue.', 6);
    case 'llave': return takeKey(t);
    case 'leer': return read(t);
    case 'madre': return mother();
    case 'renato':
      return say(state.keys >= 3
        ? 'Renato entreabre los ojos hundidos. —No luches —susurra. Y vuelve a dormirse.'
        : 'Renato duerme, extrañamente pálido, casi gris. Respira con dificultad.', 6);
  }
}

function read(t) {
  const d = t.userData;
  const n = (state.reads.get(t) || 0) + 1;
  state.reads.set(t, n);
  let text = d.texto;
  if (d.texto2 && (n > 1 || (t.name.startsWith('Hortensias_plastico') && state.credRead > 0))) text = d.texto2;
  if (d.credencial && n === 1) {
    state.credRead++;
    if (state.credRead === 1) {
      tell(text, '«Es un huesillo», piensas. Se te escapa una carcajada que no reconoces como tuya.');
      throat(2.5);
      return;
    }
  }
  say(text, Math.max(4, Math.min(9, text.length / 18)));
}

const KEY_LINES = [
  'Una llave pequeña, de bronce. Encaja en una de las cerraduras de la entrada.',
  'Otra llave. Ya son dos.',
  'Cinco puertas. Cinco cerraduras. En tu cabeza, la cuenta cuadra sola.',
  'Cada vez que uno se secaba, ella se mudaba a un cuarto nuevo y le dejaba la cama.',
  'Tienes las cinco llaves. La puerta de entrada te espera. Pero algo en tu garganta quiere volver al cuarto de ella.',
];
function takeKey(t) {
  t.parent.remove(t);
  state.keys++;
  ui.keys.hidden = false;
  ui.keys.textContent = `Llaves: ${state.keys}/5`;
  ui.goal.textContent = state.keys >= 5 ? 'Objetivo: abrir la puerta de entrada' : 'Objetivo: encontrar las cinco llaves';
  const lock = locks[state.keys - 1];
  if (lock) { lock.material.color.set(0xd9a441); lock.material.emissive.set(0x3a2a08); }
  tell(KEY_LINES[state.keys - 1]);
  if (state.keys === 1) tell('Desde el fondo del pasillo llega un ruido húmedo. Alguien se despertó.');
  if (state.keys >= 3) throat(2);
  scheduleWhisper(state.keys >= 5 ? 12 : undefined);
}

function frontDoorAction() {
  if (state.keys >= 5) return endingEscape();
  const missing = 5 - state.keys;
  const falta = missing === 1 ? 'falta una llave' : `faltan ${missing} llaves`;
  if (!state.frontTried) {
    state.frontTried = true;
    ui.goal.textContent = 'Objetivo: encontrar las cinco llaves';
    ui.keys.hidden = false;
    ui.keys.textContent = `Llaves: ${state.keys}/5`;
    tell('La puerta tiene cinco cerraduras. Renato las cerró por dentro, «para mantenerla calmada».',
         `Te ${falta}. Tienen que estar en algún lugar de esta casa.`);
  } else {
    say(`Sigue cerrada. Te ${falta}.`);
  }
}

function mother() {
  const k = state.keys;
  if (k === 0) {
    const n = (state.reads.get('madre') || 0) + 1;
    state.reads.set('madre', n);
    return say(n === 1
      ? 'La anciana duerme profundamente. En las fotos de la pared era de una belleza indescriptible; ahora está descuidada y demacrada.'
      : 'Duerme. Respira con un silbido húmedo. El hedor es insoportable.', 6);
  }
  if (k <= 2) {
    throat(2);
    return tell('Abre los ojos. En ellos no hay demencia senil, sino una lucidez depredadora.',
                '—¿Quién es este joven tan buen mozo? Renato es un buen chico. Me trae lo que necesito.');
  }
  if (k === 3) { throat(2); return say('—La belleza es la llave que abre todas las puertas… ¿Buscas llaves, pollito?', 6); }
  if (k === 4) { throat(2); return say('—Renato está seco. Ya casi termino con él.', 5); }
  if (!state.motherPrimed) {
    state.motherPrimed = true;
    throat(4);
    return tell('—Llegaste justo a tiempo, pollito. Acudiste a mi llamado, ¿ves?',
                'Algo late en tu garganta. Responde a su voz.');
  }
  endingMother();
}

// ------------------------------------------------------------------ finales
function showEnding(title, paragraphs) {
  ended = true;
  queue.length = 0;
  controls.unlock();
  ui.hud.hidden = true;
  ui.overlay.classList.add('hidden');
  ui.endTitle.textContent = title;
  ui.endText.innerHTML = paragraphs.map((p) => `<p>${p}</p>`).join('');
  ui.ending.hidden = false;
}
function endingEscape() {
  if (frontDoor) frontDoor.rotation.y = -1.2;
  showEnding('Afuera', [
    'Las cinco cerraduras ceden una tras otra. Sales a la calle sin despedirte.',
    'Valparaíso ya no te parece una ciudad, sino un organismo vivo y hostil. La niebla espesa y salada de Playa Ancha te envuelve mientras bajas cerros infinitos.',
    'A eso del mediodía llega un mensaje de Renato: <em>«¿Hoy en mi casa?»</em>',
    'Tu cuerpo tiembla. Escapaste. Por ahora.',
  ]);
}
function endingMother() {
  showEnding('Lengua materna', [
    'Te acercas a la cama. La cosa que vive en ella sonríe con la boca desencajada.',
    'En el velador, junto a la lamparita, las hortensias se pudren. Renato, desde el suelo, te mira con los ojos hundidos. No hay amor en su mirada: solo un alivio inmenso.',
    'Lo que late en tu garganta vibra en respuesta. Tu propósito era este.',
    '<em>No volveré a dejarte sola, mamá.</em>',
  ]);
}

// ------------------------------------------------------------------ movimiento y colisiones
const R = 0.28;
function blocked(x, z) {
  for (const c of colliders) {
    const b = c.box;
    if (b.max.y < 0.3 || b.min.y > 1.8) continue;
    if (x > b.min.x - R && x < b.max.x + R && z > b.min.z - R && z < b.max.z + R) return true;
  }
  return false;
}

const fwd = new THREE.Vector3(), right = new THREE.Vector3(), mv = new THREE.Vector3();
let bobT = 0;
function move(dt) {
  camera.getWorldDirection(fwd);
  fwd.y = 0; fwd.normalize();
  right.crossVectors(fwd, camera.up).normalize();
  mv.set(0, 0, 0);
  if (keys.KeyW || keys.ArrowUp) mv.add(fwd);
  if (keys.KeyS || keys.ArrowDown) mv.sub(fwd);
  if (keys.KeyD || keys.ArrowRight) mv.add(right);
  if (keys.KeyA || keys.ArrowLeft) mv.sub(right);
  const p = camera.position;
  if (mv.lengthSq() > 0) {
    const speed = keys.ShiftLeft || keys.ShiftRight ? 3.6 : 2.0;
    mv.normalize().multiplyScalar(speed * dt);
    if (!blocked(p.x + mv.x, p.z)) p.x += mv.x;
    if (!blocked(p.x, p.z + mv.z)) p.z += mv.z;
    bobT += dt * speed * 2.2;
  }
  const shake = performance.now() < throatUntil ? (Math.random() - 0.5) * 0.02 : 0;
  p.y = EYE + Math.sin(bobT) * 0.03 + shake;
}

function updateDoors(dt) {
  for (const d of doors) {
    const goal = d.open ? 1 : 0;
    if (d.t === goal) continue;
    d.t = goal > d.t ? Math.min(goal, d.t + dt * 2.5) : Math.max(goal, d.t - dt * 2.5);
    d.pivot.rotation.y = d.base + d.giro * d.t * Math.PI * 0.5;
    d.pivot.updateMatrixWorld(true);
    for (const c of colliders) if (c.dyn && findFlag(c.obj, 'giro') === d.pivot) c.box.setFromObject(c.obj);
  }
}

// ------------------------------------------------------------------ animaciones
const _q = new THREE.Quaternion();
const AX = new THREE.Vector3(1, 0, 0), AZ = new THREE.Vector3(0, 0, 1);
let walker = null;

function parts(o) {
  const p = {};
  o.traverse((c) => { if (c.userData.rol) p[c.userData.rol] = { obj: c, q0: c.quaternion.clone() }; });
  return p;
}
function swing(part, axis, angle) {
  if (!part) return;
  part.obj.quaternion.copy(part.q0).multiply(_q.setFromAxisAngle(axis, angle));
}

function setupAnim(o, kind) {
  const a = { o, kind, p: parts(o), pos0: o.position.clone(), rotY0: o.rotation.y, scale0: o.scale.clone(), phase: Math.random() * 6 };
  if (kind === 'paseante') { a.min = o.userData.rango_min; a.max = o.userData.rango_max; a.dir = 1; walker = a; }
  if (kind === 'tv') o.traverse((c) => { if (c.isMesh) { c.material = c.material.clone(); a.mat = c.material; } });
  animated.push(a);
}

function animate(t, dt) {
  for (const a of animated) {
    const { o, p } = a;
    switch (a.kind) {
      case 'saludo': swing(p.brazo_der, AZ, Math.sin(t * 5) * 0.35); break;
      case 'mirar': o.rotation.y = a.rotY0 + Math.sin(t * 0.25 + a.phase) * 0.06; break;
      case 'fumar': swing(p.brazo_der, AX, (Math.sin(t * 0.7) > 0.6 ? -0.25 : 0.35)); break;
      case 'sentado': o.rotation.y = a.rotY0 + Math.sin(t * 0.3) * 0.05; break;
      case 'respira': case 'madre': {
        const s = 1 + Math.sin(t * (a.kind === 'madre' ? 0.9 : 1.3) + a.phase) * 0.01;
        o.scale.set(a.scale0.x * s, a.scale0.y, a.scale0.z);
        break;
      }
      case 'paseante': {
        o.position.x += a.dir * 1.1 * dt;
        if (o.position.x > a.max) a.dir = -1;
        if (o.position.x < a.min) a.dir = 1;
        o.rotation.y = a.dir > 0 ? -Math.PI / 2 : Math.PI / 2;
        const s = Math.sin(t * 6.5) * 0.45;
        swing(p.pierna_izq, AX, s); swing(p.pierna_der, AX, -s);
        swing(p.brazo_izq, AX, -s * 0.7); swing(p.brazo_der, AX, s * 0.7);
        break;
      }
      case 'perro':
        if (walker) {
          o.position.x = walker.o.position.x - walker.dir * 1.3;
          o.position.z = walker.o.position.z - 0.35;
          o.rotation.y = walker.o.rotation.y;
          o.position.y = Math.abs(Math.sin(t * 9)) * 0.04;
        }
        break;
      case 'tv':
        if (a.mat && Math.random() < 0.15) a.mat.emissiveIntensity = 1.5 + Math.random() * 2.5;
        break;
    }
  }
  for (const f of flickers) {
    if (!roomLights[f.room]?.on) continue;
    const dip = Math.random() < (f.room === 'madre' ? 0.12 : 0.04) ? Math.random() * 0.8 : 0;
    f.light.intensity = f.base * (1 - dip);
    f.bulb.material.emissiveIntensity = 6 * (1 - dip);
  }
}

// ------------------------------------------------------------------ bucle
const clock = new THREE.Clock();
let lastZone = '';
renderer.setAnimationLoop(() => {
  const dt = Math.min(clock.getDelta(), 0.05);
  const t = clock.elapsedTime;
  if (controls.isLocked && !ended) {
    move(dt);
    const now = performance.now();
    if (now - lastRayAt > 100) { lastRayAt = now; currentTarget = target(); ui.prompt.textContent = promptFor(currentTarget); }
    const [id, name] = currentZone();
    if (id !== lastZone) { ui.room.textContent = name; lastZone = id; onEnterZone(id); }
    if (now > nextWhisper) {
      whisper(state.keys >= 5 ? 'Pollito… ven.' : WHISPERS[Math.floor(Math.random() * WHISPERS.length)]);
      scheduleWhisper(state.keys >= 5 ? 20 : undefined);
    }
    pumpQueue();
  }
  updateDoors(dt);
  animate(t, dt);
  renderer.render(scene, camera);
});

// para depurar desde la consola
window.__game = { renderer, camera, scene, colliders, roomLights, setRoom, controls, blocked, state, doors, interact, target,
  takeKey, frontDoorAction, mother, currentZone };
