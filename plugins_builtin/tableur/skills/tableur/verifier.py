"""Check an .xlsx before it is delivered: each sheet shown as a table (formulas with their computed result) and the
problems listed. The formulas are computed by LibreOffice on a copy (the file itself is not touched).
python3 verifier.py fichier.xlsx"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

ERR = re.compile(r"#(REF!|DIV/0!|VALUE!|NAME\?|N/A|NUM!|NULL!)")
SHEET_REF = re.compile(r"(?:'([^']+)'|([A-Za-z_][\w.]*))!")
HARD_NUM = re.compile(r"(?<![A-Z$\d.])\d+(?:\.\d+)?(?![\d:(])")


def soffice():
    return shutil.which("soffice") or next((p for p in ("/Applications/LibreOffice.app/Contents/MacOS/soffice",) if Path(p).exists()), None)


def computed(path):
    """The result of every formula, computed by LibreOffice on a copy: {sheet: {cell: value}}, or None without it."""
    exe = soffice()
    if not exe:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "classeur.xlsx"
        shutil.copy(path, src)
        try:  # its own profile: works even while LibreOffice is open
            subprocess.run([exe, f"-env:UserInstallation=file://{tmp}/profil", "--headless", "--calc", "--convert-to", "xlsx",
                            "--outdir", f"{tmp}/calc", str(src)], capture_output=True, timeout=120)
            wb = load_workbook(Path(tmp) / "calc" / "classeur.xlsx", data_only=True)
        except (OSError, subprocess.SubprocessError, ValueError, KeyError):
            return None
        return {ws.title: {c.coordinate: c.value for row in ws.iter_rows() for c in row if c.value is not None} for ws in wb.worksheets}


def main(path):
    wb = load_workbook(path)
    names, problems = set(wb.sheetnames), []
    calc = computed(path)
    print("Formules calculées par LibreOffice : chaque formule est suivie de son résultat (→)." if calc is not None
          else "LibreOffice absent : formules non calculées (seule leur forme est vérifiée).")
    for ws in wb.worksheets:
        print(f"\n== Feuille « {ws.title} » · {ws.max_row} lignes × {ws.max_column} colonnes")
        for r in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 15)):
            cells = []
            for c in r[:10]:
                v = "" if c.value is None else str(c.value)
                if calc is not None and v.startswith("="):
                    v = f"{v[:12]} → {calc.get(ws.title, {}).get(c.coordinate, '(vide)')}"
                cells.append(v[:24])
            print(" | ".join(f"{x:<24}" for x in cells))
        if ws.max_row > 15:
            print(f"… {ws.max_row - 15} lignes de plus")
        formulas = 0
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                if isinstance(v, str) and ERR.search(v):
                    problems.append(f"{ws.title}!{c.coordinate} : erreur {ERR.search(v).group(0)}")
                if isinstance(v, str) and v.startswith("="):
                    formulas += 1
                    got = (calc or {}).get(ws.title, {}).get(c.coordinate)
                    if isinstance(got, str) and ERR.search(got):
                        problems.append(f"{ws.title}!{c.coordinate} : « {v[:50]} » donne {ERR.search(got).group(0)} une fois calculée")
                    for a, b in SHEET_REF.findall(v):
                        if (a or b) not in names:
                            problems.append(f"{ws.title}!{c.coordinate} : la formule vise la feuille « {a or b} » qui n'existe pas")
                    body = SHEET_REF.sub("", re.sub(r'"[^"]*"', "", v[1:]))
                    body = re.sub(r"\$?[A-Z]{1,3}\$?\d+", "", body)
                    if [n for n in HARD_NUM.findall(body) if n not in ("0", "1", "100", "12")]:
                        problems.append(f"{ws.title}!{c.coordinate} : nombre écrit en dur dans « {v[:50]} » (mets-le dans une cellule d'hypothèse)")
        if ws.max_row > 1 and formulas == 0 and any(isinstance(c.value, (int, float)) for row in ws.iter_rows(min_row=2) for c in row):
            problems.append(f"« {ws.title} » : aucun calcul en formule (les totaux doivent être des formules)")
        head = [c for c in ws[1] if c.value is not None]
        if head and not any(c.font and c.font.b for c in head):
            problems.append(f"« {ws.title} » : ligne d'en-tête sans style (gras, fond, ligne figée)")
        for i in range(1, min(ws.max_column, 30) + 1):
            col = get_column_letter(i)
            longest = max((len(str(c.value)) for c in ws[col] if c.value is not None and not str(c.value).startswith("=")), default=0)
            width = ws.column_dimensions[col].width or 8.43
            if longest > width + 2:
                problems.append(f"« {ws.title} » colonne {col} : trop étroite ({width:.0f}) pour un texte de {longest} caractères")
    print("\n" + ("PROBLÈMES À CORRIGER :\n- " + "\n- ".join(dict.fromkeys(problems)) if problems else "Aucun problème trouvé : le classeur peut être livré."))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage : python3 verifier.py fichier.xlsx")
    main(sys.argv[1])
