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

## Choisir la forme d'après le sujet (pas la première recette venue)
| Le sujet a la forme… | Exemples | Recette |
|---|---|---|
| d'un tube long et replié | intestin, serpent, câble, racine, rivière | « tube enroulé » |
| d'une masse arrondie | cœur, rein, foie, poumon, cerveau, rocher, fruit | « forme organique » (+ « vaisseaux » si veines, nervures) |
| d'un assemblage d'objets simples | machine, maison, robot, molécule, système solaire | sphères, boîtes, cylindres dans des `THREE.Group` |
| d'une silhouette plate épaissie | étoile, feuille, logo, lettre | `THREE.Shape` + `ExtrudeGeometry` avec `bevelEnabled: true` |
Un cœur n'est pas un tube : ne recopie pas la recette du tube pour autre chose qu'un tube.

## Recette : une forme organique + des vaisseaux sur sa surface (vérifiée : un cœur)
`rayon(d)` dit, pour chaque direction depuis le centre, où est la surface. Change cette fonction pour une autre masse
(rein : creux d'un côté ; cerveau : bosses ; foie : aplati et large).
```js
// 1. la forme : rayon(direction) dit, pour chaque direction depuis le centre, à quelle distance est la surface
const COULEUR = 0xb3202a;                                   // la couleur demandée, sinon celle du sujet
function rayon(d) {                                         // d : direction (vecteur de longueur 1)
  const bas = Math.max(0, -d.y);                            // vers le bas : la forme s'affine en pointe
  const haut = Math.max(0, d.y);
  const lobes = 0.18 * haut * Math.abs(Math.sin(Math.atan2(d.z, d.x)));  // en haut : deux bosses (gauche, droite)
  return 1.0 + 0.1 * haut - 0.8 * Math.pow(bas, 1.6) + lobes;
}
const geo = new THREE.SphereGeometry(1, 128, 96);
const v = new THREE.Vector3();
const pos = geo.attributes.position;
for (let i = 0; i < pos.count; i++) {
  v.fromBufferAttribute(pos, i).normalize();
  v.multiplyScalar(rayon(v));
  pos.setXYZ(i, v.x, v.y * 1.1, v.z * 0.85);                // un peu plus haut que large, aplati devant
}
geo.computeVertexNormals();
const forme = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: COULEUR, roughness: 0.55 }));
forme.rotation.z = -0.35;                                   // inclinaison naturelle
monde.add(forme);

// 2. les vaisseaux : une courbe sur la surface (angles qui varient), posée juste au-dessus, puis un tube fin
function surLaSurface(theta, phi, dessus = 1.02) {         // theta : tour (0..2π), phi : hauteur (0 haut .. π bas)
  const d = new THREE.Vector3(Math.sin(phi) * Math.cos(theta), Math.cos(phi), Math.sin(phi) * Math.sin(theta));
  const r = rayon(d) * dessus;
  return new THREE.Vector3(d.x * r, d.y * r * 1.1, d.z * r * 0.85);
}
const vaisseau = (pts, epaisseur, couleur) => forme.add(new THREE.Mesh(
  new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 160, epaisseur, 10, false),
  new THREE.MeshStandardMaterial({ color: couleur, roughness: 0.4 })));
for (let k = 0; k < 8; k++) {                               // des branches tout autour, qui descendent en serpentant
  const t0 = k / 8 * Math.PI * 2, pts = [];
  for (let j = 0; j <= 30; j++) pts.push(surLaSurface(t0 + 0.2 * Math.sin(j * 0.45 + k * 1.7), 0.35 + j * 0.08));
  vaisseau(pts, 0.025, k % 2 ? 0x2c4a9a : 0x7a0f17);        // veines bleues, artères rouge sombre
}
// un gros vaisseau qui sort du haut en arc
// gros vaisseaux qui sortent du haut : une crosse qui part vers l'arrière, un tronc qui part vers l'avant
const crosse = [], tronc = [];
for (let j = 0; j <= 24; j++) {
  const a = j / 24 * Math.PI;
  crosse.push(new THREE.Vector3(0.1, 0.9 + 0.7 * Math.sin(a), 0.45 * Math.cos(a) - 0.1));
  tronc.push(new THREE.Vector3(-0.25 - 0.35 * j / 24, 0.85 + 0.55 * Math.sin(a * 0.6), 0.25 + 0.2 * j / 24));
}
vaisseau(crosse, 0.16, 0x9e1b22);
vaisseau(tronc, 0.13, 0x2c4a9a);
```

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
const COULEUR = 0xe3a0a0;   // la couleur demandée, sinon celle du sujet (tableau « Les couleurs »)
const tube = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 1200, 0.16, 16, false),
  new THREE.MeshStandardMaterial({ color: COULEUR, roughness: 0.45 }));
monde.add(tube);
```
Pour un organe ou un objet expliqué (anatomie, machine, planète), ajoute en HTML par-dessus le canvas un titre et 2 ou 3
phrases simples adaptées à l'âge demandé, pas un schéma.

## Les couleurs
- **La couleur demandée est appliquée** (« le cœur en rouge » → `color: 0xc0392b`), sur l'objet principal.
- **Sans couleur demandée, la couleur réelle du sujet**, jamais celle d'un exemple recopié. Quelques repères :
  | Sujet | Couleur |
  |---|---|
  | Cœur, muscle | `0x9e2a2b` (rouge sombre) |
  | Intestin, estomac | `0xe3a0a0` (rose chair) |
  | Poumons | `0xe8a5a5` (rose clair) |
  | Foie | `0x7b2d26` (brun rouge) |
  | Cerveau | `0xe6b8b0` (rose gris) |
  | Os, dents | `0xe9e2d0` (ivoire) |
  | Veines / artères | `0x3b5998` / `0xb22222` |
  | Terre, océan | `0x2a6fdb` ; végétation `0x3c8d3c` |
- Plusieurs parties : une couleur par partie, et la même couleur dans la légende HTML.

## Les informations : vérifiées avant d'être écrites
Un sujet scientifique (anatomie, astronomie, biologie, machine) : avant d'écrire les légendes, fais une recherche
(`web_search` « <sujet> taille enfant », « <organe> parties ») et prends les chiffres et les noms dans des sources
sérieuses (encyclopédie, site médical ou scientifique). Écris seulement ce que tu as trouvé, avec des mots adaptés à
l'âge demandé. Si une valeur n'est pas trouvée, ne l'écris pas : n'invente jamais un chiffre.

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
