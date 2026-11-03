---
name: threejs-3d
description: La 3D dans une page web avec Three.js — scène, caméra, lumières, objets, animation, rotation à la souris (OrbitControls), modèles 3D (glTF), taille qui suit l'écran — à partir d'un modèle vérifié.
---

# La 3D avec Three.js

Le modèle vérifié est dans ce skill : `$HOME/.naim/plugins/threejs/skills/threejs-3d/modele.html` (une scène complète
qui marche : lumières, objet, rotation, souris, taille, mouvement réduit, nettoyage). Copie-le dans le dossier du
projet puis change SEULEMENT la scène (objets, couleurs, mouvement) — ne réécris pas la base.

```bash
cp "$HOME/.naim/plugins/threejs/skills/threejs-3d/modele.html" <dossier>/index.html
```

## Ce que le modèle fait déjà (à garder)
- **three.js en version FIXE** par une importmap (`three@0.185.0`, jamais « latest ») ; les extensions viennent de
  `three/addons/…` (même version) : `import { OrbitControls } from "three/addons/controls/OrbitControls.js"`.
- `renderer.setPixelRatio(Math.min(devicePixelRatio, 2))` : net sans écraser la carte graphique.
- La taille suit le conteneur (`ResizeObserver` → `renderer.setSize` + `camera.aspect`) : panneau, fenêtre, téléphone.
- `renderer.setAnimationLoop` (pas de boucle maison) ; le temps avec `THREE.Timer` (`THREE.Clock` est signalé dépassé) :
  le mouvement dépend du temps écoulé, pas du nombre d'images.
- `prefers-reduced-motion` : pas de rotation automatique.
- Un message clair si WebGL manque ; tout est libéré (`dispose`) en quittant la page.
- `role="img"` et `aria-label` décrivent la scène ; le texte reste en HTML par-dessus (pas dans la 3D).

## Construire la scène
- **Lumières** : une `HemisphereLight` douce + une `DirectionalLight` principale (relief). Sans lumière, un
  `MeshStandardMaterial` est noir.
- **Matières** : `MeshStandardMaterial({ color, roughness, metalness })` ; `MeshBasicMaterial` ne réagit pas à la lumière.
- **Plusieurs objets** : un `THREE.Group` qu'on fait tourner d'un coup ; réutilise la même géométrie et la même matière
  pour des objets identiques (ou `InstancedMesh` au-delà de quelques centaines).
- **Système solaire / orbites** : un groupe par planète, la planète décalée dans le groupe, on fait tourner le groupe.
- **Modèle 3D** (.glb / .gltf) : `import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js"`, puis
  `new GLTFLoader().load("modele.glb", (g) => scene.add(g.scene))` — le fichier doit être servi par un serveur
  (`python3 -m http.server`), pas ouvert en file://.
- **Texte, boutons, légendes** : en HTML par-dessus le canvas, pas en 3D.
- **Couleurs et style de la page autour** : le skill ui-ux-pro-max, et ses règles pour Three.js :
  `python3 "$HOME/.naim/plugins/ui-ux-pro-max/skills/ui-ux-pro-max/scripts/search.py" "<sujet>" --stack threejs`.

## Vérifier
Ouvre la page (Aperçu ou `browser` action=open) et lis les erreurs (`browser` action=console) : une erreur d'import
(version, chemin `three/addons/`) ou de WebGL se voit là. Le navigateur de vérification de Naim est invisible : il ne
fait pas tourner l'animation, c'est normal — l'absence d'erreur est ce qui compte.

## Pour finir
Dis comment la voir (le fichier, ou l'adresse si un serveur est lancé) et comment on s'en sert (glisser, zoomer).
