---
name: maths-affichage
description: Écrire des maths comme dans un manuel — formules en LaTeX, opérations posées dans un bloc pose (l'application calcule et dessine les étapes), figures de géométrie en svg, énoncé puis corrigé.
---

# Maths comme dans un manuel

L'application dessine trois choses à ta place. Utilise-les toujours, réponds dans la conversation (pas de fichier,
pas d'image PNG, pas d'outil) sauf si on te demande un fichier.

## 1. Les formules : LaTeX
- Dans la phrase : `$…$` → $2 \times 60 + 30 = 150$.
- Seule sur sa ligne : `$$…$$`.
- Virgule décimale : `0{,}456` ; unités : `\text{cm}^2`, `\text{min}` ; multiplication : `\times` ; division : `\div`
  ou `\frac{a}{b}`.
- Jamais de formule dans un bloc de code, jamais « 2 x 60 » en texte brut.

## 2. Les opérations posées : un bloc pose qui contient SEULEMENT l'opération
```pose
234,56 × 12,3
```
L'application calcule elle-même les étapes (produits partiels, retenues de colonnes, division en potence avec les restes)
et les dessine alignées, exactes. N'écris JAMAIS les étapes toi-même : ni tirets, ni colonnes, ni produits partiels.
Opérateurs : `+`, `-`, `×`, `:` (division). Un bloc par opération.

## 3. Les figures de géométrie : un bloc svg
Un dessin net, environ 260 × 200 : `viewBox`, traits épais, noms des points, longueurs, angle droit marqué par un petit
carré, texte en `font-family="Helvetica"`. Il s'affiche comme une figure sur fond blanc.

## 4. La forme d'un exercice
Énoncé complet d'abord (si on le demande), puis le corrigé question par question. Titres courts sans emoji. Une
phrase de méthode, le calcul, puis le résultat en gras avec son unité.

## Exemple complet (à imiter)

### Exercice 1 — Calculs posés

**a) Multiplication**

```pose
234,56 × 12,3
```

**b) Division**

```pose
789,01 : 9,2
```

### Exercice 2 — Conversion

Une heure vaut 60 minutes : $2\ \text{h}\ 30 = 2 \times 60 + 30 = 150\ \text{min}$. Résultat : **150 min**.

### Exercice 3 — Pourcentage

Une remise de 25 % sur 200 € :

$$200 \times \left(1 - \frac{25}{100}\right) = 200 \times 0{,}75 = 150\ \text{€}$$

Nouveau prix : **150 €**.

### Exercice 4 — Géométrie

L'aire d'un triangle rectangle est la moitié du rectangle de mêmes côtés :

$$\mathcal{A} = \frac{b \times h}{2} = \frac{6 \times 4}{2} = 12\ \text{cm}^2$$

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="260" height="190" viewBox="0 0 260 190" font-family="Helvetica" font-size="14">
  <polygon points="30,160 210,160 30,40" fill="#fdeee8" stroke="#c4553a" stroke-width="2"/>
  <polyline points="30,145 45,145 45,160" fill="none" stroke="#c4553a"/>
  <text x="105" y="180">b = 6 cm</text><text x="2" y="104">h = 4 cm</text>
  <text x="20" y="34">A</text><text x="18" y="176">B</text><text x="214" y="176">C</text>
</svg>
```

Aire du triangle : **12 cm²**.
