---
name: maths-affichage
description: Écrire des maths comme dans un manuel — formules en LaTeX (algèbre, analyse, matrices, vecteurs, trigo, probabilités, statistiques), opérations posées et courbes de fonctions calculées par l'application, figures de géométrie en svg, énoncé puis corrigé.
---

# Maths comme dans un manuel

Réponds dans la conversation (pas de fichier, pas d'image PNG, pas d'outil) sauf si on te demande un fichier.
L'application dessine quatre choses à ta place : utilise-les toujours.

| Besoin | Écris | L'application fait |
|---|---|---|
| Une formule | `$…$` dans la phrase, `$$…$$` seule sur sa ligne | la formule mise en page (KaTeX) |
| Une opération posée | un bloc `pose-texte` avec SEULEMENT l'opération | l'opération écrite en texte, alignée |
| Une division, SEULEMENT après la commande /visuel ([visuel] au début du message) | un bloc `division` avec SEULEMENT l'opération | la potence pas à pas, les noms, les flèches, une phrase par étape |
| Une addition, une soustraction, une multiplication, SEULEMENT après /visuel | un bloc `addition`, `soustraction` ou `multiplication` avec SEULEMENT l'opération | colonne par colonne, les retenues en rouge, une phrase par étape |
| La courbe d'une fonction | un bloc `graphe` avec la fonction | le repère et la courbe exacte |
| Une figure dans un repère (points, polygones, vecteurs, transformation) | un bloc `graphe` avec les points et les figures | le repère orthonormé et la figure exacte |
| Une figure de géométrie sans repère (cercle, angle, solide) | un bloc `svg` | la figure sur fond blanc |

Jamais de formule dans un bloc de code, jamais de calcul « dessiné » avec des tirets ou des espaces.

**Un résultat dont tu n'es pas sûr se calcule, il ne se devine pas.** Grands nombres, plus petite solution, équation
de Pell ou diophantienne, nombres premiers, PGCD, « combien de solutions » : calcule-le et vérifie-le avec
`run_command` (`python3 -c "…"` ou un petit script), puis écris la réponse vérifiée, avec la vérification
(par exemple $x^2 - 61y^2 = 1$ recalculé). Ne réécris jamais « est-ce juste ? » : vérifie, puis tranche.

Recettes justes (Python seul, sans rien installer) — copie-les, ne les réinvente pas :
```python
from math import isqrt, gcd
def pell(D):              # plus petite solution x > 0, y > 0 de x² − D·y² = 1 (D entier, pas un carré)
    a0 = isqrt(D); m, d, a = 0, 1, a0
    p0, p1, q0, q1 = 1, a0, 0, 1
    while p1 * p1 - D * q1 * q1 != 1:
        m = d * a - m; d = (D - m * m) // d; a = (a0 + m) // d
        p0, p1 = p1, a * p1 + p0; q0, q1 = q1, a * q1 + q0
    return p1, q1          # les autres solutions : (x + y√D)^n
def bezout(a, b):          # (pgcd, u, v) avec a·u + b·v = pgcd
    if b == 0: return a, 1, 0
    g, u, v = bezout(b, a % b); return g, v, u - (a // b) * v
def premier(n): return n > 1 and all(n % k for k in range(2, isqrt(n) + 1))
def facteurs(n):
    f, k = [], 2
    while k * k <= n:
        while n % k == 0: f.append(k); n //= k
        k += 1
    return f + ([n] if n > 1 else [])
```
Par exemple `python3 -c "…recette…; x, y = pell(61); print(x, y, x*x - 61*y*y)"` affiche le résultat ET sa vérification.

## 1. Formules (LaTeX) — mémo

- Nombres : virgule `0{,}5`, unités `12\ \text{cm}^2`, `\times`, `\div`, `\frac{a}{b}`, `\sqrt{x}`, `\sqrt[3]{x}`, `x^{2}`, `\approx`, `\neq`, `\leq`.
- Équation pas à pas (aligné sur =) :
  `$$\begin{aligned} 3x + 5 &= 20 \\ 3x &= 15 \\ x &= 5 \end{aligned}$$`
- Système : `$$\begin{cases} x + y = 10 \\ x - y = 2 \end{cases}$$`
- Second degré : `$$\Delta = b^2 - 4ac \qquad x_{1,2} = \frac{-b \pm \sqrt{\Delta}}{2a}$$`
- Fonctions et analyse : `f(x) = 2x^2 - 3x + 1`, `f'(x) = 4x - 3`, `\lim_{x \to +\infty} f(x) = +\infty`,
  `\int_{0}^{2} x^2 \,dx = \left[\frac{x^3}{3}\right]_0^2 = \frac{8}{3}`, `\sum_{k=1}^{n} k = \frac{n(n+1)}{2}`
- Suites : `u_{n+1} = u_n + r`, `u_n = u_0 \times q^n`
- Matrices : `$$A = \begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix} \qquad \det A = \begin{vmatrix} 1 & 2 \\ 3 & 4 \end{vmatrix} = 1 \times 4 - 2 \times 3 = -2$$`
  produit : `$$\begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix} \begin{pmatrix} 5 \\ 6 \end{pmatrix} = \begin{pmatrix} 17 \\ 39 \end{pmatrix}$$`
- Vecteurs : `\vec{AB} = \begin{pmatrix} x_B - x_A \\ y_B - y_A \end{pmatrix}`, `\|\vec{u}\| = \sqrt{x^2 + y^2}`, `\vec{u} \cdot \vec{v} = xx' + yy'`
- Géométrie : Pythagore `BC^2 = AB^2 + AC^2`, Thalès `\frac{AM}{AB} = \frac{AN}{AC} = \frac{MN}{BC}`,
  cercle `\mathcal{P} = 2\pi r`, `\mathcal{A} = \pi r^2`, angles `\widehat{ABC} = 60^\circ`
- Trigonométrie : `\cos \widehat{B} = \frac{\text{adjacent}}{\text{hypoténuse}}`, `\sin^2 x + \cos^2 x = 1`
- Probabilités : `P(A) = \frac{\text{cas favorables}}{\text{cas possibles}}`, `P(A \cap B)`, `P_A(B) = \frac{P(A \cap B)}{P(A)}`, `\binom{n}{k}`
- Statistiques : `\bar{x} = \frac{1}{n}\sum_{i=1}^{n} x_i`, `\sigma = \sqrt{\frac{1}{n}\sum (x_i - \bar{x})^2}`
- Tableau de valeurs ou de signes : un tableau Markdown (`| x | -2 | 0 | 2 |`) ou `\begin{array}{c|ccc} … \end{array}`.

## 2. Opérations posées : bloc pose-texte (en texte, aligné)
```pose-texte
854 : 7
```
Opérateurs `+`, `-`, `x`, `:` ; nombres entiers. Un bloc par opération : l'application l'écrit en texte, aligné et
juste. Un calcul avec virgule : écris-le en ligne (`234,56 × 12,3 = 2 885,088`) avec les étapes en texte.

## 2 bis. Les opérations : TOUJOURS en texte, le visuel SEULEMENT avec /visuel
- **Par défaut — toujours, quelle que soit la demande** (« combien font 854 divisé par 7 », « apprends-moi la
  division pour le CM1 », « propose-moi des calculs pour réviser », « explique avec la méthode visuelle ») :
  réponds EN TEXTE, comme avant. Une ligne simple pour annoncer un calcul : un petit bloc texte que tu écris
  (`12 ÷ 3 = ?`). L'opération posée en colonnes (la potence, les soustractions) : ne l'écris pas à la main (les
  colonnes se décalent), écris un bloc ```pose-texte avec seulement l'opération, l'application l'écrit en texte aligné :
```pose-texte
854 : 7
```
  (aussi `268 + 457`, `503 - 276`, `347 x 26`). Puis les étapes en texte (« Étape 1 : … »), le résultat en gras, la
  vérification, « À retenir ». Des calculs proposés pour réviser : donne les énoncés seulement, sans les réponses
  (l'utilisateur les cherche), et corrige quand il répond.
- **N'utilise JAMAIS** les blocs `division`, `addition`, `soustraction`, `multiplication` ni `pose` (ils dessinent) —
  SAUF quand le message commence par **[visuel]** (la commande /visuel de l'utilisateur).
- **Avec [visuel] au début du message** : le bloc de l'opération ci-dessous (joué pas à pas), puis les étapes écrites.

### Apprendre la division : bloc division
Seulement quand le message commence par [visuel] (la commande /visuel),
écris UN bloc avec seulement l'opération :
```division
854 : 7
```
L'application dessine la division comme au tableau et la joue pas à pas avec les boutons Suivant / Précédent :
d'abord les noms (dividende en rouge, diviseur en vert, quotient en bleu, reste en orange), puis à chaque étape
« combien de fois ? », le produit à enlever souligné, ce qui reste, le chiffre abaissé par une flèche verte, et à la
fin la vérification. Les calculs du dessin sont faits par l'application.
- **Le visuel ET l'explication écrite, les deux** : avant le bloc, une phrase simple (« On va partager 854 bonbons
  entre 7 enfants ! ») ; après le bloc, écris aussi les étapes en texte, comme au tableau :
  la règle en une ligne (**Diviser → Multiplier → Soustraire → Abaisser**), puis « Étape 1 : … », « Étape 2 : … »
  (combien de fois, le produit, la soustraction, le chiffre abaissé), le **résultat**, la **vérification**
  (quotient × diviseur + reste = dividende) et « À retenir ». Tes nombres sont les mêmes que ceux du dessin :
  calcule-les juste. Termine par un exercice du même niveau (une autre division, sans la réponse).
- Pour un enfant : des nombres adaptés à son niveau (CE2 : un chiffre au diviseur, CM : deux chiffres) ; des mots
  simples ; jamais de LaTeX autour.
- Nombres entiers seulement (jusqu'à 9 chiffres au dividende, 4 au diviseur). Une division avec virgule : en texte (sans bloc).

### Apprendre l'addition, la soustraction, la multiplication : mêmes règles
```addition
268 + 457
```
```soustraction
503 − 276
```
```multiplication
347 × 26
```
L'application les joue pas à pas comme la division : colonne par colonne (unités, dizaines, centaines…), les
retenues en rouge (addition, multiplication), les 10 ajoutés en haut et les 1 rendus en bas (soustraction, méthode
française), les lignes décalées puis additionnées (multiplication, 3 chiffres au plus au second nombre), la
vérification à la fin. Comme pour la division : le visuel ET les étapes écrites en texte après, puis un exercice.
Nombres entiers ; une soustraction qui donnerait un nombre négatif ou un calcul avec virgule : en texte.

## 2 ter. Un système linéaire AX = B en deux vues : bloc systeme
Quand on demande de **représenter, dessiner, visualiser** un système d'équations linéaires ou une équation matricielle
AX = B (« fais le graphe de ce système », « visualise AX = B », « interprétation géométrique et réseau »), ou avec
/visuel : écris UN bloc avec seulement le système. Pour un simple « résous ce système » : en texte, sans ce bloc.
```systeme
3x - y = 5
2x + y = 4
```
ou avec les matrices :
```systeme
A = [[1, 1, -1], [2, -1, 1], [-1, 2, -1]]
B = [2, 1, 0]
```
L'application résout le système exactement (fractions comprises) et dessine : en haut A, B et la solution X ;
**I. la géométrie** — 2 inconnues : les droites dans le repère, chacune de sa couleur et nommée (L1, L2…), la
solution en étoile avec ses pointillés vers les axes ; 3 inconnues : les plans en perspective (P1, P2, P3) et le
point commun ; **II. le réseau** — x₁, x₂… à gauche, b₁, b₂… à droite, chaque flèche pondérée par son coefficient
a_ij, les sommes à côté ; **la synthèse** — les deux vues donnent la même solution, avec la vérification. Cas sans
solution (droites parallèles) et infinité de solutions : dits et dessinés.
- 2 ou 3 inconnues (x, y, z ou x1, x2, x3), 2 à 4 équations. Ne calcule pas la solution toi-même dans le bloc.
- Avant le bloc : une phrase. Après : la résolution écrite en texte (substitution ou combinaison, ou Gauss), le
  résultat et ce que montrent les deux vues, en 2 ou 3 phrases.

## 3. Courbes de fonctions : bloc graphe
```graphe
f(x) = x^2 - 2x - 3
g(x) = 2x - 3
x : -3..5
A(0;-3)
```
Une fonction par ligne (`f(x) = …` ou `y = …`), avec `^`, `*` ou rien (`2x`), `/`, `sqrt`, `sin`, `cos`, `tan`, `exp`,
`ln`, `abs`, `pi`. Facultatif : `x : a..b`, `y : c..d`, des points nommés `A(1;2)`. L'application calcule la courbe
exacte : ne dessine jamais une courbe à la main en svg.

### Une figure dans un repère : toujours le bloc graphe
Points, polygones, segments, vecteurs, droites, et l'image d'une figure par une transformation (matrice, symétrie,
rotation, translation, homothétie) : calcule d'abord les coordonnées (run_command avec Python si besoin), puis
écris-les dans un bloc `graphe`. L'application trace un repère **orthonormé** (un carré reste un carré), remplit
chaque figure de sa couleur et place les noms à l'extérieur :
```graphe
A(1;1)
B(3;1)
C(3;2)
D(1;2)
A'(3;0)
B'(5;-2)
C'(7;-1)
D'(5;1)
polygone ABCD
polygone A'B'C'D'
vecteur A A'
coordonnées
```
- `polygone ABCD` (ou `triangle ABC`, `polygone A B C D`) : la figure reliant ces points, dans l'ordre ;
- `segment A B`, `vecteur A B` (une flèche), `droite A B` (la droite entière) ;
- `coordonnées` : écrit A(1 ; 1) à côté de chaque point ; `orthonormé` : impose le repère orthonormé avec des courbes ;
- un nom entre « » après la figure l'écrit au milieu : `polygone ABCD « initiale »`.
Jamais de diagramme Mermaid ni de page HTML pour une figure de maths, jamais de PDF si on ne demande pas de document :
la réponse avec la figure s'écrit dans la conversation.

## 4. Figures de géométrie sans repère : bloc svg
Environ 280 × 220, `viewBox`, traits épais `stroke-width="2"`, noms des points en Helvetica, longueurs écrites, angle
droit marqué par un petit carré, codage des égalités par des petits traits.

**Tu ne vois pas ton dessin : calcule-le, ne le devine pas.**
1. **D'abord les points, en vraies mesures** (cm, angles), puis l'échelle : `échelle = min(240 / largeur, 180 / hauteur)`
   (marge de 20 autour). Pour un triangle, un cercle, un angle, un polygone régulier : calcule les sommets
   (`x = cx + r·cos θ`, `y = cy − r·sin θ` — en SVG, y descend), avec run_command et Python si ce n'est pas immédiat.
   Écris la liste des points avant le SVG.
2. **Les noms à l'extérieur de la figure** : depuis le centre de la figure, pousse chaque nom de 12 à 16 unités
   dans la direction de son sommet (`text-anchor="middle"`). Une longueur : au milieu du côté, décalée vers l'extérieur.
3. **Jamais un texte sur un trait** ni deux textes l'un sur l'autre ; rien hors du viewBox ; la figure occupe
   l'essentiel du cadre.
4. L'application **mesure ton SVG** avant de l'afficher (hors cadre, étiquettes qui se chevauchent, texte coupé par un
   trait, nom loin de son point, figure trop petite) et te renvoie les défauts avec leurs coordonnées : corrige-les
   en recalculant. Un fichier .svg écrit est mesuré de la même façon (`python3 ~/Library/Application\ Support/Naim/app/svgcheck.py fichier.svg`).
5. Une figure dans un repère (coordonnées, vecteurs, transformation) : le bloc `graphe`, qui place tout seul.

Exemples à adapter :

Cercle de centre O et de rayon 3 cm, avec un diamètre :
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="240" height="220" viewBox="0 0 240 220" font-family="Helvetica" font-size="14">
  <circle cx="120" cy="110" r="80" fill="#eef4fb" stroke="#3d7cc9" stroke-width="2"/>
  <line x1="40" y1="110" x2="200" y2="110" stroke="#3d7cc9" stroke-width="2"/>
  <circle cx="120" cy="110" r="3" fill="#222"/>
  <text x="114" y="128">O</text><text x="22" y="114">A</text><text x="205" y="114">B</text>
  <text x="140" y="104">r = 3 cm</text>
</svg>
```

Repère avec un vecteur AB :
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="260" height="220" viewBox="0 0 260 220" font-family="Helvetica" font-size="13">
  <defs><marker id="f" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#c4553a"/></marker></defs>
  <line x1="20" y1="180" x2="245" y2="180" stroke="#555"/><line x1="40" y1="200" x2="40" y2="10" stroke="#555"/>
  <line x1="70" y1="150" x2="190" y2="60" stroke="#c4553a" stroke-width="2.5" marker-end="url(#f)"/>
  <circle cx="70" cy="150" r="3" fill="#222"/><circle cx="190" cy="60" r="3" fill="#222"/>
  <text x="56" y="168">A(1;1)</text><text x="196" y="56">B(5;4)</text><text x="132" y="96">u</text>
</svg>
```

Rectangle, parallélogramme, trapèze, solide (pavé, cylindre en perspective) : même principe, en adaptant les points.

## 5. Forme d'un exercice
Énoncé complet d'abord (si on le demande), puis le corrigé question par question. Titres courts sans emoji. Une
phrase de méthode, le calcul en LaTeX (ou le bloc pose-texte / graphe), puis le résultat en gras avec son unité.

### Exemple (à imiter, pas à recopier)

**Exercice — Fonction du second degré.** Soit $f(x) = x^2 - 2x - 3$. Trouver ses racines et tracer sa courbe.

On calcule le discriminant :

$$\Delta = b^2 - 4ac = (-2)^2 - 4 \times 1 \times (-3) = 16$$

$$x_1 = \frac{2 - 4}{2} = -1 \qquad x_2 = \frac{2 + 4}{2} = 3$$

```graphe
f(x) = x^2 - 2x - 3
x : -3..5
A(-1;0)
B(3;0)
```

Les racines sont **−1 et 3**.
