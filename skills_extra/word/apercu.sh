#!/bin/bash
# Aperçu fidèle d'un document Word (.docx/.doc/.rtf) pour le vérifier : un PDF à côté du fichier.
#   bash ~/.naim/skills/word/apercu.sh "chemin/document.docx"   → affiche le chemin du PDF (puis look_at dessus)
# 1. Microsoft Word s'il est installé (rendu exact : en-têtes, numéros de page, tableaux, sauts de page)
# 2. sinon Quick Look de macOS (une image de la première page, styles approchés)
set -e
src="$1"
[ -f "$src" ] || { echo "error: fichier introuvable : $src" >&2; exit 1; }
abs="$(cd "$(dirname "$src")" && pwd)/$(basename "$src")"
pdf="${abs%.*}.apercu.pdf"
# Word is sandboxed by macOS: outside the user's own folders it asks for access (a window on screen) — never there
case "$abs" in "$HOME"/Library/*|"$HOME"/.*) word=no ;; "$HOME"/*) word=yes ;; *) word=no ;; esac
if [ "$word" = yes ] && [ -d "/Applications/Microsoft Word.app" ]; then
  if osascript - "$abs" "$pdf" <<'EOF' >/dev/null 2>&1
on run argv
  set src to POSIX file (item 1 of argv)
  with timeout of 60 seconds
  tell application "Microsoft Word"
    open src
    set d to active document
    save as d file name (item 2 of argv) file format format PDF
    close d saving no
  end tell
  end timeout
end run
EOF
  then
    [ -f "$pdf" ] && { echo "$pdf"; exit 0; }
  fi
  echo "(Word n'a pas pu exporter : la première fois, autorise Word à ouvrir ce dossier, puis recommence)" >&2
fi
out="$(dirname "$abs")"
qlmanage -t -s 1400 -o "$out" "$abs" >/dev/null 2>&1 || true
[ -f "$abs.png" ] && { echo "$abs.png  (aperçu Quick Look de la 1re page : tableaux et sauts de page approchés)"; exit 0; }
echo "error: aucun aperçu possible (ni Word ni Quick Look)" >&2
exit 1
