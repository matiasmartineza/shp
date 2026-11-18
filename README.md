# SHP — Lengua materna

Juego de terror en primera persona, adaptado del cuento «Lengua materna».
Eres Esteban: despiertas en el cuarto de Renato, en su casa del cerro Playa Ancha (Valparaíso).
La puerta de entrada tiene cinco cerraduras; las cinco llaves están en las piezas de los antiguos
estudiantes, a lo largo de un pasillo en U. Para salir del cuarto de Renato hay que pasar por el de su madre.
Por las ventanas se ve a los vecinos y, al fondo, el puerto. Dos finales.

## Estructura
- `public/` — el sitio que publica Netlify (`index.html`, `main.js`, `style.css`, `assets/casa.glb`).
- `blender/build_house.py` — script que construye la casa en Blender y exporta `public/assets/casa.glb`.
- `blender/casa.blend` — la escena de Blender para abrir y editar.

Regenerar el modelo:
```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup -P blender/build_house.py
```

Probar en local: `python -m http.server 8765 --directory public` y abrir http://localhost:8765

## Controles
WASD moverse · Mouse mirar · Shift correr · E interactuar · Esc pausa

## Ramas
- `main`: producción (Netlify publica desde aquí).
- `pruebas`: rama de pruebas (branch deploy en Netlify).
