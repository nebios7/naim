#!/bin/bash
# Hook of the mainframe plugin: after Naim writes a COBOL file, GnuCOBOL checks its syntax.
# Errors → exit 2 with the messages on stderr: Naim reads them and corrects the file. Anything else: silent.
input=$(cat)
file=$(printf '%s' "$input" | /usr/bin/python3 -c 'import json,sys
d=json.load(sys.stdin); t=d.get("tool_input") or {}
print(t.get("path") or t.get("file_path") or "")' 2>/dev/null)
case "$file" in *.cbl|*.cob|*.CBL|*.COB) ;; *) exit 0 ;; esac
cobc=$(command -v cobc || ls /opt/homebrew/bin/cobc /usr/local/bin/cobc 2>/dev/null | head -1)
[ -n "$cobc" ] || exit 0                       # GnuCOBOL not installed: nothing to check
cwd=$(printf '%s' "$input" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin).get("cwd") or ".")' 2>/dev/null)
cd "${cwd:-.}" 2>/dev/null || true
[ -f "$file" ] || exit 0
# fixed format (code from column 8, the classic mainframe layout) unless the lines start at column 1
format=-fixed
if ! grep -qE '^ {6}[ *-/]? *(IDENTIFICATION|identification|ID|id) +(DIVISION|division)' "$file"; then format=-free; fi
out=$("$cobc" -fsyntax-only $format -I "$(dirname "$file")" "$file" 2>&1)
if [ $? -ne 0 ]; then
  printf 'GnuCOBOL (%s) a trouvé des erreurs dans %s :\n%s\nCorrige-les avant de continuer.\n' "${format#-}" "$file" "$out" | head -40 >&2
  exit 2
fi
exit 0
