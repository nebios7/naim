---
name: convertisseurs
description: Convertir un fichier d'un format à un autre en une seule commande (images, documents, tableurs, audio, vidéo), sans réécrire son contenu.
---

# Convertir un fichier : UNE commande

```
python3 ~/.naim/plugins/convertisseurs/skills/convertisseurs/convertir.py <source> <sortie>
```
Le format vient de l'extension de la sortie. Pas de script à écrire, pas de contenu à relire ni à recopier.

| De | Vers | Exemple |
|---|---|---|
| Image (png, jpg, heic, webp, gif, tiff, bmp) | une autre image, ou un PDF | `photo.heic photo.jpg` · `--taille 1200` · `--qualite 80` |
| Plusieurs images | un PDF (album, dans l'ordre donné) | `p1.jpg p2.jpg p3.jpg album.pdf` |
| PDF | images (une par page), texte, Markdown, Word | `doc.pdf pages.png` (pages-1.png, pages-2.png…) · `doc.pdf doc.docx` |
| Word, Markdown, HTML, RTF, ODT, texte, EPUB | un autre de ces formats | `cv.docx cv.md` (les images vont dans cv-images/) |
| Tout document, PowerPoint, Excel, CSV | PDF au style pdf-pro | `rapport.docx rapport.pdf` · `--couleur gris` |
| CSV, Excel, JSON | un autre de ces formats | `notes.csv notes.xlsx` |
| Vidéo (mp4, mov, mkv, avi, webm) | autre vidéo, son (mp3, m4a, wav), GIF animé | `film.mov film.mp4` · `clip.mp4 clip.gif --debut 0:05 --duree 4` |
| Son (mp3, wav, m4a, flac, ogg) | un autre son | `memo.m4a memo.mp3` |

- La sortie a toujours un autre nom que la source (l'original n'est jamais écrasé) ; elle va à côté de la source
  sauf si l'utilisateur dit où.
- Le script dit « ok : <chemin> (taille) » : regarde le résultat avec look_at (une image, un PDF), puis donne le chemin.
- « l'outil … manque : brew install … » : installe-le (skill installer), puis relance la même commande.
- Un CV ou une lettre à refaire au propre : skill cv-lettre. Un quiz en PDF : `pdfpro.py quiz`.
