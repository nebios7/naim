---
name: traduction-livre
description: Traduire fidèlement un livre ou un long PDF (même scanné) page par page, en gardant les dessins, les tableaux et les symboles de l'original, puis en faire un PDF mis en page.
---

# Traduire un livre en gardant ses dessins, tableaux et symboles

Le texte d'un PDF scanné vient d'une reconnaissance automatique (OCR) : les dessins y deviennent du charabia
(`^äSBlÄ r§<W`), les tableaux des lignes en vrac, les symboles (☉ ♈ 🜂) des `■` ou `△`. Ne traduis donc jamais
le texte brut d'un coup : suis ces étapes, avec l'outil `livre.py` de ce skill.

## 1. Préparer (une fois)
Dans le dossier de travail (celui des fichiers joints de la conversation) :
```bash
python3 -m venv "<dossier>/.venv" && "<dossier>/.venv/bin/pip" install -q pdfplumber
```
pdfplumber lit le texte et les images du PDF ; il installe aussi pypdfium2, qui rend les pages en image.
Ensuite, toutes les commandes : `"<dossier>/.venv/bin/python" ~/.naim/plugins/traduction/skills/traduction-livre/livre.py …`
(noté `livre.py` ci-dessous).

## 2. Inventaire
```bash
livre.py inventaire "<livre.pdf>" "<dossier>/livre"
```
Il dit si le livre est scanné, et liste les pages À REGARDER (image, peu de texte, signes bizarres, tableau).
Il crée `orig/` (texte de chaque page, sans l'en-tête courant), `fr/` (tes traductions), `glossaire.md`.

## 3. Traduire page par page
```bash
livre.py suivant "<dossier>/livre"
```
Il donne la page suivante : son texte, la fin de la page d'avant, le glossaire, et ce qu'il faut regarder.
- Page à regarder : `livre.py page "<dossier>/livre" <n>` puis **look_at** sur l'image. Fie-toi à l'IMAGE, pas au texte.
  - un dessin : `livre.py figure "<dossier>/livre" <n>` le découpe (l'original est gardé, jamais redessiné) ;
    look_at sur la figure ; si elle prend des paragraphes, redonne la zone `x0 y0 x1 y1` (fractions de la page).
    Dans la traduction, à sa place : `![Légende traduite — Sud, Écliptique, Équateur…](figures/p105.png)`.
  - un tableau : refais-le en tableau Markdown d'après l'image.
  - des symboles : écris les vrais caractères vus sur l'image (☉ ☽ ☿ ♀ ♂ ♃ ♄ ♅ ♆, ♈ … ♓, 🜁 🜂 🜃 🜄, △ ▽, ✠ …).
- Écris la traduction COMPLÈTE de la page dans `fr/p<NNN>.md` (write_file) : rien de résumé, rien de sauté,
  *italique* et notes comme l'original, `#` pour un titre de chapitre, `##` pour une section.
- Un terme qui revient (triplicities → triplicités) : ajoute-le à `glossaire.md`, et garde toujours la même traduction.
- Relance `livre.py suivant` : page après page, jusqu'à « Toutes les pages sont traduites ».
  Le travail survit à un arrêt : chaque page est son fichier, `suivant` reprend à la première qui manque.
- Ne t'arrête pas pour demander s'il faut continuer : un livre se traduit en entier.

## 4. Vérifier, assembler, envoyer
```bash
livre.py etat "<dossier>/livre"
livre.py assembler "<dossier>/livre" "<Titre traduit>" livre_fr.html
"$HOME/Library/Application Support/Naim/bin/naim-pdf" "<dossier>/livre/livre_fr.html" "<dossier>/livre/livre_fr.pdf" A4
```
`etat` doit dire que tout est traduit, sans figure oubliée. Puis look_at sur le PDF : la page de titre, une page
avec dessin, une page avec tableau ou symboles. Copie le PDF final dans ~/Documents/Naim/Fichiers, puis
envoie-le si on te l'a demandé (mail, SMS).
