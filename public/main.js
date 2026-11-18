import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';

// ------------------------------------------------------------------ escena
const canvas = document.getElementById('game');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x9cc7e8);
scene.fog = new THREE.Fog(0x9cc7e8, 35, 90);

const camera = new THREE.PerspectiveCamera(70, innerWidth / innerHeight, 0.05, 200);
const EYE = 1.62;
camera.position.set(4.7, EYE, -1.6);

scene.add(new THREE.HemisphereLight(0xcfe3ff, 0x5a4a35, 0.45));
const sun = new THREE.DirectionalLight(0xfff1d6, 2.6);
sun.position.set(14, 30, -30);
sun.target.position.set(7, 0, -6);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -32, right: 32, top: 32, bottom: -32, near: 1, far: 100 });
sun.shadow.bias = -0.0005;
scene.add(sun, sun.target);

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

// ------------------------------------------------------------------ UI
const $ = (id) => document.getElementById(id);
const ui = { overlay: $('overlay'), play: $('play'), loading: $('loading'), pct: $('pct'),
  hud: $('hud'), room: $('room'), prompt: $('prompt'), msg: $('msg') };
let msgTimer = 0;
function say(text, secs = 4) {
  ui.msg.textContent = text;
  ui.msg.classList.add('show');
  clearTimeout(msgTimer);
  msgTimer = setTimeout(() => ui.msg.classList.remove('show'), secs * 1000);
}

// ------------------------------------------------------------------ controles
const controls = new PointerLockControls(camera, document.body);
ui.play.addEventListener('click', () => controls.lock());
controls.addEventListener('lock', () => { ui.overlay.classList.add('hidden'); ui.hud.hidden = false; });
controls.addEventListener('unlock', () => {
  ui.overlay.classList.remove('hidden');
  ui.play.textContent = 'Continuar';
});

const keys = {};
addEventListener('keydown', (e) => {
  keys[e.code] = true;
  if (e.code === 'KeyE' && controls.isLocked) interact();
});
addEventListener('keyup', (e) => { keys[e.code] = false; });
addEventListener('blur', () => { for (const k in keys) keys[k] = false; });

// ------------------------------------------------------------------ mundo
const colliders = [];      // Box3 en coordenadas del mundo
const interactables = [];  // objetos con userData.interaccion
const roomLights = {};     // habitacion -> { on, lights[], bulbs[] }
const animated = [];
let world = null;

function findFlag(o, key) {
  for (let n = o; n; n = n.parent) if (n.userData && n.userData[key] !== undefined) return n;
  return null;
}

const loader = new GLTFLoader();
loader.load('assets/casa.glb', (gltf) => {
  world = gltf.scene;
  scene.add(world);
  world.updateMatrixWorld(true);

  world.traverse((o) => {
    const d = o.userData || {};
    if (o.isMesh) {
      const transparent = o.material.transparent;
      o.castShadow = !transparent;
      o.receiveShadow = true;
      if (transparent) o.material.depthWrite = false;
    }
    if (d.colision) colliders.push(new THREE.Box3().setFromObject(o));
    if (d.interaccion) interactables.push(o);
    if (d.inicio) camera.position.set(o.position.x, EYE, o.position.z);
    if (d.lampara) addLamp(o, d.lampara);
    if (d.anim) setupAnim(o, d.anim);
  });

  // las luces empiezan encendidas: "la luz está funcionando"
  for (const r in roomLights) setRoom(r, true);

  ui.loading.hidden = true;
  ui.play.hidden = false;
}, (ev) => {
  if (ev.total) ui.pct.textContent = Math.round((ev.loaded / ev.total) * 100) + '%';
}, (err) => {
  ui.loading.textContent = 'No se pudo cargar la casa: ' + err.message;
});

function addLamp(bulb, room) {
  const p = new THREE.Vector3();
  bulb.getWorldPosition(p);
  const isNeighbor = room === 'vecinos';
  const light = new THREE.PointLight(isNeighbor ? 0xffe2b0 : 0xffd29a, isNeighbor ? 6 : 9, isNeighbor ? 7 : 8, 1.6);
  light.position.copy(p).add(new THREE.Vector3(0, -0.15, 0));
  scene.add(light);
  const r = (roomLights[room] ||= { on: true, lights: [], bulbs: [] });
  r.lights.push(light);
  bulb.material = bulb.material.clone();
  r.bulbs.push(bulb);
}

function setRoom(room, on) {
  const r = roomLights[room];
  if (!r) return;
  r.on = on;
  r.lights.forEach((l) => (l.visible = on));
  r.bulbs.forEach((b) => (b.material.emissiveIntensity = on ? 6 : 0));
}

// ------------------------------------------------------------------ interacción
const ray = new THREE.Raycaster();
ray.far = 2.6;
const center = new THREE.Vector2(0, 0);
const ROOM_NAMES = { living: 'Living-comedor', cocina: 'Cocina', bano: 'Baño', dorm1: 'Dormitorio 1', dorm2: 'Dormitorio 2' };

function target() {
  if (!world) return null;
  ray.setFromCamera(center, camera);
  const hit = ray.intersectObject(world, true)[0];
  return hit ? findFlag(hit.object, 'interaccion') : null;
}

function promptFor(t) {
  if (!t) return '';
  const d = t.userData;
  if (d.interaccion === 'puerta') return '[E] Abrir la puerta';
  if (d.interaccion === 'interruptor') return `[E] ${roomLights[d.habitacion]?.on ? 'Apagar' : 'Encender'} la luz`;
  if (d.interaccion === 'ventana') return '[E] Mirar por la ventana';
  return '';
}

let doorTries = 0;
function interact() {
  const t = target();
  if (!t) return;
  const d = t.userData;
  if (d.interaccion === 'puerta') {
    doorTries++;
    say(doorTries < 3
      ? 'La puerta está cerrada con llave. Falta una llave para salir.'
      : 'Sigue cerrada. Falta una llave… tiene que estar en algún lugar de esta casa.');
  } else if (d.interaccion === 'interruptor') {
    const r = roomLights[d.habitacion];
    setRoom(d.habitacion, !r.on);
  } else if (d.interaccion === 'ventana') {
    say(d.texto || 'Afuera la vida sigue.', 5);
  }
}

// ------------------------------------------------------------------ movimiento y colisiones
const R = 0.28;
function blocked(x, z) {
  for (const b of colliders) {
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
    const speed = keys.ShiftLeft || keys.ShiftRight ? 4.0 : 2.2;
    mv.normalize().multiplyScalar(speed * dt);
    if (!blocked(p.x + mv.x, p.z)) p.x += mv.x;
    if (!blocked(p.x, p.z + mv.z)) p.z += mv.z;
    bobT += dt * speed * 2.2;
  }
  p.y = EYE + Math.sin(bobT) * 0.03;
}

function currentRoom() {
  const x = camera.position.x, y = -camera.position.z; // coordenadas de Blender
  if (y < 5) return x < 8 ? 'living' : 'cocina';
  return x < 5 ? 'dorm1' : x < 9 ? 'bano' : 'dorm2';
}

// ------------------------------------------------------------------ vecinos animados
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
  const a = { o, kind, p: parts(o), pos0: o.position.clone(), rotY0: o.rotation.y, phase: Math.random() * 6 };
  if (kind === 'paseante') {
    a.min = o.userData.rango_min; a.max = o.userData.rango_max; a.dir = 1;
    walker = a;
  }
  if (kind === 'tv') {
    o.traverse((c) => { if (c.isMesh) { c.material = c.material.clone(); a.mat = c.material; } });
  }
  animated.push(a);
}

function animate(t, dt) {
  for (const a of animated) {
    const { o, p } = a;
    switch (a.kind) {
      case 'saludo':
        swing(p.brazo_der, AZ, Math.sin(t * 6) * 0.35);
        break;
      case 'jardinero':
        o.rotation.y = a.rotY0 + Math.sin(t * 0.6 + a.phase) * 0.5;
        break;
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
      case 'nino':
        o.position.y = a.pos0.y + Math.max(0, Math.sin(t * 3.2)) * 0.06;
        swing(p.brazo_der, AX, -Math.abs(Math.sin(t * 3.2)) * 1.2);
        swing(p.brazo_izq, AX, -Math.abs(Math.sin(t * 3.2)) * 1.2);
        break;
      case 'pelota':
        o.position.y = a.pos0.y + Math.abs(Math.sin(t * 3.2)) * 0.9;
        break;
      case 'tender':
        swing(p.brazo_der, AX, Math.sin(t * 1.5) * 0.35);
        swing(p.brazo_izq, AX, Math.sin(t * 1.5 + 1) * 0.35);
        break;
      case 'ropa':
        o.rotation.z = Math.sin(t * 1.3) * 0.12;
        break;
      case 'sentado':
        o.rotation.y = a.rotY0 + Math.sin(t * 0.3) * 0.05;
        break;
      case 'tv':
        if (a.mat && Math.random() < 0.15) a.mat.emissiveIntensity = 1.5 + Math.random() * 2.5;
        break;
    }
  }
}

// ------------------------------------------------------------------ bucle
const clock = new THREE.Clock();
let lastRoom = '';
renderer.setAnimationLoop(() => {
  const dt = Math.min(clock.getDelta(), 0.05);
  const t = clock.elapsedTime;
  if (controls.isLocked) {
    move(dt);
    ui.prompt.textContent = promptFor(target());
    const r = currentRoom();
    if (r !== lastRoom) { ui.room.textContent = ROOM_NAMES[r]; lastRoom = r; }
  }
  animate(t, dt);
  renderer.render(scene, camera);
});

// para depurar desde la consola
window.__game = { camera, scene, colliders, roomLights, setRoom, controls, blocked };
