#!/usr/bin/env bash
# build_app.sh <Nom> <dossier-des-sources> [--install] [--open]
# Builds a real macOS app (Nom.app) from SwiftUI sources WITHOUT an Xcode project:
# a Swift package is generated, compiled with `swift build`, then wrapped into Nom.app (Info.plist, icon-less,
# ad-hoc signed). --install copies it to /Applications (or ~/Applications if not writable), --open launches it
# and checks that it runs. Every message gives full paths.
set -euo pipefail
trap 'echo "ÉCHEC du script à la ligne $LINENO (commande : $BASH_COMMAND)" >&2' ERR
NAME="${1:?nom de l application}"; SRC="${2:?dossier des sources .swift}"; shift 2
INSTALL=0; OPEN=0
for a in "$@"; do case "$a" in --install) INSTALL=1;; --open) OPEN=1;; esac; done
SRC="$(cd "$SRC" && pwd)"
ls "$SRC"/*.swift >/dev/null 2>&1 || { echo "aucun fichier .swift dans $SRC" >&2; exit 1; }
ID="$(echo "$NAME" | tr -cd '[:alnum:]')"
WORK="$SRC/.build-app"; rm -rf "$WORK"; mkdir -p "$WORK/Sources/$ID"
cp "$SRC"/*.swift "$WORK/Sources/$ID/"
cat > "$WORK/Package.swift" <<PKG
// swift-tools-version:5.9
import PackageDescription
let package = Package(name: "$ID", platforms: [.macOS(.v14)],
    targets: [.executableTarget(name: "$ID", path: "Sources/$ID")])
PKG
echo "→ sources : $SRC"
echo "→ compilation… (journal : $WORK/build.log)"
LOG="$WORK/build.log"
( cd "$WORK" && swift build -c release >"$LOG" 2>&1 ) || true
# the first errors only, plain (no colours), each with its file:line in the sources folder and the faulty line
sed -E 's/\x1b\[[0-9;]*m//g' "$LOG" | grep -E "^/.*: error: " | sed -E "s#^.*/Sources/$ID/#$SRC/#" | awk '!seen[$0]++' | head -5 > "$WORK/errors.txt" || true  # no error found is not a failure
if [ -s "$WORK/errors.txt" ]; then
  echo "ERREURS DE COMPILATION (corrige d'abord la première, puis relance ce script) :"
  while IFS= read -r line; do
    echo "• ${line}"
    f="${line%%:*}"; rest="${line#*:}"; n="${rest%%:*}"
    [ -f "$f" ] && [ "$n" -eq "$n" ] 2>/dev/null && echo "    ligne $n : $(sed -n "${n}p" "$f" | sed -E 's/^[[:space:]]+//')"
  done < "$WORK/errors.txt"
else
  grep -E "Build complete" "$LOG" || true
fi
BIN="$WORK/.build/release/$ID"
[ -x "$BIN" ] || { echo "ÉCHEC : la compilation n'a pas produit l'exécutable (voir les erreurs ci-dessus, corrige le code et relance)" >&2; exit 1; }
APP="$SRC/$NAME.app"; rm -rf "$APP"; mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/$ID"
cat > "$APP/Contents/Info.plist" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>$NAME</string><key>CFBundleDisplayName</key><string>$NAME</string>
<key>CFBundleExecutable</key><string>$ID</string><key>CFBundleIdentifier</key><string>local.naim.$ID</string>
<key>CFBundlePackageType</key><string>APPL</string><key>CFBundleShortVersionString</key><string>1.0</string>
<key>CFBundleVersion</key><string>1</string><key>LSMinimumSystemVersion</key><string>14.0</string>
<key>NSHighResolutionCapable</key><true/><key>NSPrincipalClass</key><string>NSApplication</string>
</dict></plist>
PL
codesign --force --deep -s - "$APP" >/dev/null 2>&1 || true
echo "✓ application créée : $APP"
if [ "$INSTALL" = 1 ]; then
  DEST="/Applications"; [ -w "$DEST" ] || { DEST="$HOME/Applications"; mkdir -p "$DEST"; }
  pkill -x "$ID" 2>/dev/null || true  # an old copy still open would keep the old version
  # the old version goes to the Trash (never deleted): it can be put back from the Finder
  [ -e "$DEST/$NAME.app" ] && mv "$DEST/$NAME.app" "$HOME/.Trash/$NAME $(date +%Y-%m-%d\ %H.%M.%S).app" && echo "→ ancienne version mise à la Corbeille"
  cp -R "$APP" "$DEST/"; APP="$DEST/$NAME.app"
  echo "✓ installée : $APP (visible dans le Finder > Applications et dans le Launchpad)"
fi
if [ "$OPEN" = 1 ]; then
  open "$APP"; sleep 2
  if pgrep -x "$ID" >/dev/null; then echo "✓ lancée : $NAME tourne (processus $(pgrep -x "$ID" | head -1))"
  else echo "ÉCHEC : $NAME ne tourne pas après l'ouverture. Lance-la à la main pour voir l'erreur : \"$APP/Contents/MacOS/$ID\"" >&2; exit 1; fi
fi
echo "Pour la relancer : open \"$APP\""
