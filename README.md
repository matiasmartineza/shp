# SHP — La Casa Sucia

Mini juego en primera persona: una casa sucia (2 dormitorios, baño, living-comedor y cocina).
La luz funciona, por las ventanas se ve a los vecinos, pero no se puede salir: falta una llave.

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
