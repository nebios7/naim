---
name: threejs-3d
description: La 3D dans une page web avec Three.js — scène, caméra, lumières, objets, animation, rotation à la souris (OrbitControls), modèles 3D (glTF), taille qui suit l'écran — à partir d'un modèle vérifié.
---

# La 3D avec Three.js

Le modèle vérifié est dans ce skill : `$HOME/.naim/plugins/threejs/skills/threejs-3d/modele.html` (une scène complète
qui marche : lumières, objet, rotation, souris, taille, mouvement réduit, nettoyage). Copie-le puis change SEULEMENT le bloc
entre `// ---- la scène` et `// ---- fin de la scène` (avec edit_file) — ne réécris pas la base.

**Un nouveau travail va dans son propre dossier**, nommé d'après le sujet. N'écrase jamais l'`index.html` d'un autre
projet.

```bash
mkdir -p <dossier>/<sujet> && cp "$HOME/.naim/plugins/threejs/skills/threejs-3d/modele.html" <dossier>/<sujet>/index.html
```

## Les trois règles qui évitent une scène vide
1. **Tout objet va dans `monde`** (`monde.add(...)`), jamais directement dans `scene`. Le modèle appelle ensuite
   `cadrer(monde)` : l'objet est centré et remplit la vue, qu'il mesure 0,5 ou 40 unités. Si tu ajoutes des objets
   plus tard (après un chargement), rappelle `cadrer(monde)`.
2. **L'ordre des paramètres** des formes (les erreurs les plus fréquentes) :
   - `TubeGeometry(courbe, segmentsLongueur, rayon, segmentsTour, fermé)` : segmentsTour est un ENTIER (12 à 24),
     jamais un rayon ;
   - `TorusGeometry(rayon, épaisseur, segmentsTour, segmentsAnneau)` ;
   - `CylinderGeometry(rayonHaut, rayonBas, hauteur, segments)` ;
   - `SphereGeometry(rayon, segmentsLargeur, segmentsHauteur)`.
3. **Lis la console** : le modèle y signale un objet vide (pas de triangles), minuscule ou hors champ. Corrige avant de
   dire que c'est fini.

## Recette : un tube enroulé (intestin, câble, serpent, racine, rivière)
Beaucoup de points d'une marche qui serpente dans une boîte, puis un tube autour. Vérifié : une pelote bien remplie.
```js
const pts = [], p = new THREE.Vector3(), cap = new THREE.Vector3(1, 0, 0), limite = 2.2;
let graine = 7; const hasard = () => ((graine = (graine * 16807) % 2147483647) / 2147483647) - 0.5;
for (let i = 0; i < 260; i++) {
  cap.add(new THREE.Vector3(hasard(), hasard(), hasard()).multiplyScalar(0.9)).normalize();
  if (Math.abs(p.x) > limite) cap.x = -Math.sign(p.x) * Math.abs(cap.x);       // rebondit : reste en pelote
  if (Math.abs(p.y) > limite * 0.8) cap.y = -Math.sign(p.y) * Math.abs(cap.y);
  if (Math.abs(p.z) > limite * 0.6) cap.z = -Math.sign(p.z) * Math.abs(cap.z);
  p.addScaledVector(cap, 0.32); pts.push(p.clone());
}
const tube = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 1200, 0.16, 16, false),
  new THREE.MeshStandardMaterial({ color: 0xe8846b, roughness: 0.45 }));
monde.add(tube);
```
Pour un organe ou un objet expliqué (anatomie, machine, planète), ajoute en HTML par-dessus le canvas un titre et 2 ou 3
phrases simples adaptées à l'âge demandé, pas un schéma.

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
