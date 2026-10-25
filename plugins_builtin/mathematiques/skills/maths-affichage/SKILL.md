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
| Une opération posée | un bloc `pose` avec SEULEMENT l'opération | les étapes exactes, alignées |
| La courbe d'une fonction | un bloc `graphe` avec la fonction | le repère et la courbe exacte |
| Une figure de géométrie | un bloc `svg` | la figure sur fond blanc |

Jamais de formule dans un bloc de code, jamais de calcul « dessiné » avec des tirets ou des espaces.

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

## 2. Opérations posées : bloc pose
```pose
234,56 × 12,3
```
Opérateurs `+`, `-`, `×`, `:`. Un bloc par opération. N'écris pas les étapes : l'application les calcule.

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

## 4. Figures de géométrie : bloc svg
Environ 280 × 220, `viewBox`, traits épais `stroke-width="2"`, noms des points en Helvetica, longueurs écrites, angle
droit marqué par un petit carré, codage des égalités par des petits traits. Exemples à adapter :

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
phrase de méthode, le calcul en LaTeX (ou le bloc pose / graphe), puis le résultat en gras avec son unité.

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
