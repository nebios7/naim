---
name: installer
description: Installer tout seul ce qu'il faut pour une tâche (paquet Python, paquet JavaScript, outil du Mac avec Homebrew) au bon endroit, vérifier que ça marche et le montrer.
---

# Installer ce qu'il faut, tout seul et proprement

## 1. Le bon nom (le module qu'on importe n'a pas toujours le nom du paquet)
| Besoin | Python (pip) | Outil du Mac (brew) |
|---|---|---|
| Excel | openpyxl (pandas pour analyser) | — |
| Word / PowerPoint | python-docx / python-pptx | — |
| PDF (lire, fusionner) | pypdf | poppler (pdftotext) |
| Images | pillow (`import PIL`) | imagemagick |
| Tableaux, statistiques | pandas, numpy | — |
| Graphiques | matplotlib | — |
| Pages web, API | requests, beautifulsoup4 (`import bs4`) | — |
| YAML | pyyaml (`import yaml`) | — |
| OpenCV | opencv-python (`import cv2`) | — |
| Machine learning | scikit-learn (`import sklearn`) | — |
| Vidéo, son | — | ffmpeg |
| Texte d'une image (OCR) | pytesseract | tesseract |
| Conversion de documents | — | pandoc |
| COBOL / REXX | — | gnucobol / regina-rexx |

## 2. Déjà là ? (on ne réinstalle pas ce qui marche)
`command -v ffmpeg` · `.venv/bin/python -c "import openpyxl"` · `brew list --formula | grep -x gnucobol`

## 3. Au bon endroit
- **Python** : dans le dossier du projet, `python3 -m venv .venv` (une fois) puis `.venv/bin/pip install <paquets>` ;
  ensuite toujours `.venv/bin/python`. Jamais dans le Python du Mac, jamais `--break-system-packages`, jamais `sudo`.
- **Word, Excel, PowerPoint** : déjà prêts dans `~/.naim/docs-venv/bin/python` (python-docx, openpyxl, python-pptx) :
  rien à installer.
- **JavaScript** : `npm install <paquets>` dans le dossier du projet (un `package.json` : `npm init -y` d'abord).
- **Outil du Mac** : `brew install <formule>`. Homebrew absent (`command -v brew` vide) : ne l'installe pas toi-même
  (il demande le mot de passe) ; donne à l'utilisateur la commande officielle de https://brew.sh et attends.

## 4. Vérifier, puis le montrer
- `.venv/bin/python -c "import openpyxl; print(openpyxl.__version__)"` · `ffmpeg -version | head -1`
- Puis un petit essai sur ce que l'utilisateur veut faire (lire SON fichier Excel, convertir SA vidéo…).
- Dis en une phrase ce qui est installé, où, et la commande pour s'en servir.

## 5. Si ça échoue
- « No matching distribution » : mauvais nom de paquet (voir le tableau) ou version de Python trop récente :
  essaie le nom correct, puis dis-le.
- Pas de réseau : dis-le, n'essaie pas dix fois.
- Une erreur que tu ne comprends pas : montre ses 5 dernières lignes à l'utilisateur et demande.
