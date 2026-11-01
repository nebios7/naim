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
# (in fixed format the division starts at column 8: seven spaces, or six and an indicator)
if ! grep -qE '^ {6}([ *-/] *| {1,})(IDENTIFICATION|identification|ID|id) +(DIVISION|division)' "$file"; then format=-free; fi
grep -qiE '^ *>>SOURCE +(FORMAT +)?(IS +)?FREE' "$file" && format=-free
out=$("$cobc" -fsyntax-only $format -I "$(dirname "$file")" "$file" 2>&1)
if [ $? -ne 0 ]; then
  # how to fix the usual ones, not only « fix it » (without it Naim rewrote the same mistake six times)
  hints=""
  case "$out" in *"invalid indicator"*) hints="$hints
- « invalid indicator » : en format fixe, la colonne 7 est réservée (espace, * ou -) ; le code commence colonne 8 (7 espaces avant IDENTIFICATION, 11 avant les instructions). Ou écris tout en format libre avec >>SOURCE FORMAT FREE en toute première ligne.";; esac
  case "$out" in *"expecting ("*) hints="$hints
- « expecting ( » : une FUNCTION prend ses arguments entre parenthèses : MOVE FUNCTION CONCATENATE(A B C) TO CIBLE. Pour assembler un texte, le plus sûr : STRING A DELIMITED BY SIZE B DELIMITED BY SIZE INTO CIBLE END-STRING.";; esac
  case "$out" in *"SET"*|*"unexpected TO"*) hints="$hints
- SET … TO sert aux index et aux conditions (niveau 88) : pour mettre une valeur dans une variable, MOVE valeur TO variable.";; esac
  case "$out" in *"is not defined"*|*"not defined"*) hints="$hints
- « not defined » : déclare la variable dans WORKING-STORAGE (ou LINKAGE) SECTION avant de l'utiliser, avec le même nom exact.";; esac
  case "$out" in *"unexpected end of file"*|*"expecting END-"*) hints="$hints
- fin de fichier inattendue : chaque IF/PERFORM/EVALUATE a son END-IF/END-PERFORM/END-EVALUATE, et la dernière phrase finit par un point.";; esac
  case "$out" in *"FREE"*|*"unknown directive"*) hints="$hints
- format libre : la première ligne est exactement >>SOURCE FORMAT FREE (pas « FREE » seul).";; esac
  printf 'GnuCOBOL (%s) a trouvé des erreurs dans %s :\n%s\n%s\nCorrige ces lignes-là (pas tout le fichier), puis continue.\n' \
    "${format#-}" "$file" "$(printf '%s' "$out" | head -24)" "${hints:+Comment corriger :$hints}" >&2
  exit 2
fi
exit 0
