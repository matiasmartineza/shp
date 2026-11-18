import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';

const $ = id => document.getElementById(id);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x805e50);
scene.fog = new THREE.FogExp2(0x544443, .016);
const renderer = new THREE.WebGLRenderer({canvas:$('game'),antialias:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.08;
const camera = new THREE.PerspectiveCamera(68,1,.045,140);
camera.position.set(3.4,1.58,-26.5);
camera.lookAt(9,1.52,-26.5);
const controls = new PointerLockControls(camera,document.body);
function resize(){renderer.setSize(innerWidth,innerHeight);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();}
resize(); addEventListener('resize',resize);
scene.add(new THREE.HemisphereLight(0xffe0be,0x716258,.72));
const sun=new THREE.DirectionalLight(0xffbc87,.72);sun.position.set(-22,9,16);scene.add(sun);
function lamp(x,y,z,color,power,radius){const light=new THREE.PointLight(color,power,radius);light.position.set(x,z,-y);scene.add(light);}
lamp(38.6,15.8,1.22,0xffbc79,14,7);lamp(44.5,19,2,0xffc995,10,6);
lamp(3.7,8.8,2.65,0xffbe80,22,8);lamp(15.6,26.7,2.65,0xfac58b,14,7);
lamp(14.12,34.32,2.31,0xe5d1a3,10,4);
lamp(2.48,30.6,2.20,0xffc090,10,4);
const flashlight = new THREE.PointLight(0xe5d2ba,4,4);scene.add(flashlight);
const clues=[
 ['El recuento',1.83,8.73,.81,'En el reverso de un menú alguien anotó veinte puestos. Luego fue tachando los nombres. Al final de la hoja, una sola instrucción a lápiz: «Llevarle la bandeja a la pieza».'],
 ['Carta sin enviar',14.59,35.57,.78,'«El domingo también me quedo. Dice que si despierta y no me ve, le da miedo». El papel está doblado dentro de un sobre de Rancagua. No lleva estampilla.'],
 ['La silla',40.07,18.14,.55,'En el asiento hay dos hendiduras. Desde aquí, todos los retratos quedan a la espalda. La única persona a la que se puede mirar de frente es la mujer de la cama.'],
 ['Las hortensias',44.18,19.42,1.29,'Tocas un pétalo. Es de plástico. Tu madre se llamaba Hortensia. Cuando Renato trajo este florero, todavía no se lo habías contado.'],
 ['Presupuesto de obra',36.52,14.39,1.30,'«Una pieza grande, otra chica al fondo. Sellar la ventana antes de entregar». En el margen, con otra letra: «Preguntarle a Esteban de qué color la quiere».']
];
const found=new Set();let sightWalls=[],walls=[],active=null,ended=false,ready=false;
// Las primeras cuatro pistas coinciden con objetos de la escena exportada.
const [, planX, planY, planHeight] = clues[4];
const planNote = new THREE.Mesh(
 new THREE.BoxGeometry(.24,.29,.012),
 new THREE.MeshStandardMaterial({color:0xe1c59d,emissive:0x24190e})
);
planNote.position.set(planX,planHeight,-planY);
scene.add(planNote);
function blocked(x,y,r=.23,obstacles=walls){return obstacles.some(([a,b,c,d])=>x>a-r&&x<c+r&&y>b-r&&y<d+r);}
const held=new Set();let target=-1;
function pause(){held.clear();$('hud').hidden=true;$('overlay').classList.toggle('hidden',active!==null||ended);$('play').textContent='Continuar';}
controls.addEventListener('unlock',pause);
controls.addEventListener('lock',()=>{$('overlay').classList.add('hidden');$('hud').hidden=false;});
$('play').onclick=()=>{if(ready)controls.lock();};
function closeNote(){active=null;$('note').hidden=true;controls.lock();}
$('close').onclick=closeNote;
$('again').onclick=()=>location.reload();
function interact(){
 if(target===-2){ended=true;controls.unlock();$('ending').hidden=false;return;}
 if(target<0)return;
 active=target;found.add(target);$('noteTitle').textContent=clues[target][0];$('noteBody').textContent=clues[target][4];$('note').hidden=false;controls.unlock();$('close').focus();
}
addEventListener('keydown',e=>{if(active!==null&&['Escape','KeyE'].includes(e.code)&&!e.repeat){closeNote();return;}if(!controls.isLocked)return;held.add(e.code);if(e.code==='KeyE'&&!e.repeat)interact();});
addEventListener('keyup',e=>held.delete(e.code));addEventListener('blur',()=>held.clear());
const direction=new THREE.Vector3(),offset=new THREE.Vector3();
function pick(){
 target=-1;let best=2.25;const p=camera.position;camera.getWorldDirection(direction);
 clues.forEach((c,i)=>{offset.set(c[1]-p.x,c[3]-p.y,-c[2]-p.z);const dist=offset.length();
 if(dist>=best||offset.clone().normalize().dot(direction)<.49)return;
 for(let t=.12;t<.80;t+=.14)if(blocked(p.x+offset.x*t,-p.z-offset.z*t,0,sightWalls))return;
 best=dist;target=i;});
 if(found.size===clues.length&&p.x<2.5&&Math.abs(-p.z-26.5)<1.15)target=-2;
 $('prompt').textContent=target===-2?'E · Salir de la casa':target>=0?'E · '+clues[target][0]:'';
 $('goal').textContent=found.size===5?'Vuelve a la puerta de las cinco cerraduras.':found.size+' / 5 indicios · '+['Revisa el comedor.','Busca la carta en el segundo par del ala sur.','Encuentra la silla en la pieza de la madre.','Pasa al dormitorio de Renato.','Busca la orden de obra al final de la galería este.'][clues.findIndex((_,i)=>!found.has(i))];
}
function move(dt){
 let u=Number(held.has('KeyD'))-Number(held.has('KeyA')),v=Number(held.has('KeyW'))-Number(held.has('KeyS'));
 const p=camera.position;camera.getWorldDirection(direction);direction.y=0;direction.normalize();const step=dt*(held.has('ShiftLeft')?3.6:2.35)/Math.max(1,Math.hypot(u,v));
 const X=p.x+step*(v*direction.x-u*direction.z),Z=p.z+step*(v*direction.z+u*direction.x);
 if(X>.26&&X<45.74&&!blocked(X,-p.z))p.x=X;
 if(Z<-.26&&Z>-35.74&&!blocked(p.x,-Z))p.z=Z;
 flashlight.position.copy(p);
}
let prev=performance.now();
renderer.setAnimationLoop(now=>{if(controls.isLocked){move(Math.min(.045,(now-prev)/1000));pick();}prev=now;renderer.render(scene,camera);});
try{
 const decoder = new DRACOLoader()
  .setDecoderPath(new URL('./vendor/draco/', import.meta.url).href)
  .setWorkerLimit(2);
 const [g,rs]=await Promise.all([
  new GLTFLoader().setDRACOLoader(decoder).loadAsync('./assets/casona-ambientada.glb')
   .finally(()=>decoder.dispose()),
  fetch('./assets/casona-colisiones.json')
 ]);
 if(!rs.ok)throw Error('colisiones');
 const {muros,muebles}=await rs.json();
 sightWalls=muros;
 walls=[...muros,...muebles];
 scene.add(g.scene);flashlight.position.copy(camera.position);ready=true;$('loading').hidden=true;$('play').hidden=false;
}catch(err){$('loading').textContent='No se pudo cargar la casa. Recarga la página.';console.error(err);}
