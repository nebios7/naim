#!/usr/bin/env bash
# capture_app.sh <Nom> [fichier.png] — photographs ONLY the window of the running app <Nom> (to check its design).
set -uo pipefail
NAME="${1:?nom de l application}"; OUT="${2:-/tmp/$NAME-capture.png}"
ID="$(echo "$NAME" | tr -cd '[:alnum:]')"
pgrep -x "$ID" >/dev/null || { echo "ÉCHEC : $NAME n'est pas lancée (lance-la d'abord avec build_app.sh … --open)" >&2; exit 1; }
WID="$(swift -e '
import CoreGraphics
let l = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as! [[String: Any]]
for w in l where (w["kCGWindowOwnerName"] as? String) == CommandLine.arguments[1] && (w["kCGWindowLayer"] as? Int) == 0 { print(w["kCGWindowNumber"]!); break }
' "$ID" 2>/dev/null)"
[ -n "$WID" ] || { echo "ÉCHEC : aucune fenêtre visible pour $NAME" >&2; exit 1; }
screencapture -x -o -l "$WID" "$OUT" && echo "✓ capture de la fenêtre : $OUT (regarde-la avec look_at)"
