#!/usr/bin/env python3
"""Naim's presentations: a deck described in JSON becomes a real PowerPoint (native charts, notes, editable
text), a picture of every slide to look at before delivering it, and a check of the text that would overflow.

  diapo.py faire  plan.json  sortie.pptx        build the deck + its pictures (sortie-apercu/diapo-N.png) + the checks
  diapo.py lire   deck.pptx                     the text of every slide (titles, text, tables, notes)
  diapo.py modifier deck.pptx changements.json sortie.pptx   change an existing deck without rebuilding it
  diapo.py themes                               the colour themes

The same layout feeds both the PowerPoint and its pictures: what the pictures show is where things are."""
import json
import re
import subprocess
import sys
import tempfile
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H, M = 13.333, 7.5, 0.6          # a wide slide (16:9), in inches, and its margin
PX = 96                              # pixels per inch in the pictures
ICONS = json.loads((HERE / "icons.json").read_text())
NAIM_PDF = Path.home() / "Library/Application Support/Naim/bin/naim-pdf"
FONTS = {"Arial": "/System/Library/Fonts/Supplemental/Arial.ttf", "Arial-b": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
         "Georgia": "/System/Library/Fonts/Supplemental/Georgia.ttf", "Georgia-b": "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"}

# colour themes: a dominant colour, a light tint for cards, one sharp accent (named after what they suit)
THEMES = {
    "ardoise":  {"primaire": "1F2A44", "clair": "E9EDF5", "accent": "F2A541", "texte": "1F2A44", "doux": "6B7385"},   # business, bilan
    "foret":    {"primaire": "1E4D3A", "clair": "E4F0E8", "accent": "D9A441", "texte": "1C2B24", "doux": "5F7268"},   # nature, écologie
    "corail":   {"primaire": "2B2D42", "clair": "FDEDEA", "accent": "EF6F5E", "texte": "2B2D42", "doux": "6E6F80"},   # marketing, énergie
    "ocean":    {"primaire": "0B4F6C", "clair": "E2F2F7", "accent": "20A39E", "texte": "0E3443", "doux": "5A7682"},   # tech, eau, voyage
    "terre":    {"primaire": "7A3E2B", "clair": "F5EDE6", "accent": "C98B4A", "texte": "3B2219", "doux": "86695C"},   # histoire, culture
    "prune":    {"primaire": "4A1942", "clair": "F4E9F1", "accent": "E0A458", "texte": "34122F", "doux": "7C5E77"},   # art, mode, luxe
    "graphite": {"primaire": "2E3138", "clair": "F1F2F4", "accent": "4F8EF7", "texte": "24262B", "doux": "6B6F78"},   # sobre, technique
    "sante":    {"primaire": "0E5E6F", "clair": "E5F4F1", "accent": "E76F51", "texte": "123C45", "doux": "5B7B80"},   # médecine, soins
    "soleil":   {"primaire": "264653", "clair": "FFF4DC", "accent": "F4A261", "texte": "1E3640", "doux": "5F7680"},   # éducation, enfants
}


def hexc(c, default="000000"):
    c = str(c or default).strip().lstrip("#")
    return c[:6].upper() if re.fullmatch(r"[0-9A-Fa-f]{6,8}", c) else default


def mix(a, b, t):
    """a colour between a and b (t = share of b)."""
    a, b = hexc(a), hexc(b)
    return "".join(f"{round(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t):02X}" for i in (0, 2, 4))


# ------------------------------------------------------------------ text measure (the overflow check)
_fonts = {}


def text_lines(text, size, width_in, bold=False, family="Arial"):
    """How many lines a text takes at this size in a box this wide (Arial / Georgia metrics)."""
    try:
        from PIL import ImageFont
        key = (family + ("-b" if bold else ""), size)
        if key not in _fonts:
            _fonts[key] = ImageFont.truetype(FONTS.get(key[0], FONTS["Arial"]), int(size * 10))
        f = _fonts[key]
        measure = lambda s: f.getlength(s) / 10  # in points
    except Exception:  # noqa: BLE001 — no Pillow: an average width
        measure = lambda s: len(s) * size * 0.52
    width = width_in * 72
    n = 0
    for para in str(text).split("\n"):
        line, count = "", 1
        for word in para.split():
            trial = (line + " " + word).strip()
            if measure(trial) > width and line:
                count, line = count + 1, word
            else:
                line = trial
        n += count
    return n


# ------------------------------------------------------------------ the layout: one list of elements per slide
class Deck:
    def __init__(self, plan):
        t = plan.get("theme") or "ardoise"
        self.th = {**THEMES["ardoise"], **(THEMES.get(str(t).lower()) or {}), **({k: hexc(v) for k, v in t.items()} if isinstance(t, dict) else {})}
        self.ft = "Georgia" if re.search(r"georgia|serif|cambria|élégant|elegant", str(plan.get("police", "")), re.I) else "Arial"
        self.fb = "Arial"
        self.warnings = []
        self.n = 0

    # elements
    def rect(self, x, y, w, h, fill, radius=False, line=None, alpha=None):
        return {"k": "rect", "x": x, "y": y, "w": w, "h": h, "fill": fill, "radius": radius, "line": line, "alpha": alpha}

    def oval(self, x, y, d, fill, alpha=None):
        return {"k": "oval", "x": x, "y": y, "w": d, "h": d, "fill": fill, "alpha": alpha}

    def text(self, x, y, w, h, text, size, color, bold=False, align="l", font=None, italic=False, valign="t", bullets=False, fit=True):
        font = font or self.fb
        if fit and text:
            items = text if isinstance(text, list) else [text]
            lines = sum(text_lines(t, size, w - (0.3 if bullets else 0), bold, font) for t in items)
            need = lines * size * 1.22 / 72 + (0.08 * (len(items) - 1) if bullets else 0)
            if need > h + 0.05:
                short = re.sub(r"\s+", " ", items[0] if isinstance(items[0], str) else str(items[0]))[:50]
                self.warnings.append(f"diapo {self.n} : le texte « {short}… » déborde ({need:.1f} po pour {h:.1f}) — raccourcis-le ou partage la diapositive")
        return {"k": "text", "x": x, "y": y, "w": w, "h": h, "text": text, "size": size, "color": color, "bold": bold,
                "align": align, "font": font, "italic": italic, "valign": valign, "bullets": bullets}

    def icon(self, name, x, y, d, color):
        if name not in ICONS:
            name = "spark"
        return {"k": "icon", "name": name, "x": x, "y": y, "w": d, "h": d, "color": color}

    def title(self, s, t):
        return [self.text(M, 0.45, W - 2 * M, 0.95, t, 32, self.th["primaire"], bold=True, font=self.ft, valign="m")]

    def footer(self, s):
        out = [self.text(W - M - 1, H - 0.45, 1, 0.3, str(self.n), 10, self.th["doux"], align="r", fit=False)]
        if s.get("pied"):
            out.append(self.text(M, H - 0.45, 6, 0.3, s["pied"], 10, self.th["doux"], fit=False))
        return out

    # slides
    def slide(self, s):
        self.n += 1
        kind = str(s.get("type", "points")).lower().replace("é", "e")
        fn = getattr(self, "s_" + kind.replace("-", "_"), None) or self.s_points
        bg, els = fn(s)
        return {"bg": bg, "els": els, "notes": s.get("notes", "")}

    def s_titre(self, s):
        th = self.th
        els = [self.oval(W - 4.2, -1.6, 6.4, th["accent"], alpha=22), self.oval(W - 2.4, 4.6, 3.6, th["clair"], alpha=12),
               self.text(M + 0.2, 2.2, 8.6, 1.9, s.get("titre", ""), 46, "FFFFFF", bold=True, font=self.ft, valign="b"),
               self.rect(M + 0.2, 4.35, 0.9, 0.07, th["accent"])]
        if s.get("sous_titre"):
            els.append(self.text(M + 0.2, 4.6, 8.4, 0.9, s["sous_titre"], 22, mix(th["primaire"], "FFFFFF", 0.82)))
        if s.get("auteur") or s.get("date"):
            els.append(self.text(M + 0.2, H - 1.1, 8, 0.4, " · ".join(x for x in (s.get("auteur"), s.get("date")) if x), 14, mix(th["primaire"], "FFFFFF", 0.65)))
        return th["primaire"], els

    def s_section(self, s):
        th = self.th
        num = s.get("numero") or f"{self.n:02d}"
        return th["primaire"], [self.text(M + 0.2, 2.0, 3, 1.4, str(num), 72, th["accent"], bold=True, font=self.ft, fit=False),
                                self.text(M + 0.2, 3.5, 10, 1.3, s.get("titre", ""), 40, "FFFFFF", bold=True, font=self.ft),
                                *([self.text(M + 0.2, 4.9, 10, 0.8, s["sous_titre"], 20, mix(th["primaire"], "FFFFFF", 0.75))] if s.get("sous_titre") else [])]

    def rows(self, items, x, y, w, h, icons=True):
        """icon + bold head + text, one row per item (a grid of two columns past 4 items)."""
        th, els = self.th, []
        cols = 2 if len(items) > 4 else 1
        per = -(-len(items) // cols)
        cw, rh = (w - 0.5 * (cols - 1)) / cols, min(1.25, h / max(1, per))
        for i, it in enumerate(items):
            it = it if isinstance(it, dict) else {"titre": str(it)}
            cx, cy = x + (i // per) * (cw + 0.5), y + (i % per) * rh
            d = 0.62
            els += [self.oval(cx, cy + 0.04, d, th["clair"]), self.icon(it.get("icone", "check"), cx + 0.15, cy + 0.19, 0.32, th["primaire"])]
            tx, tw = cx + d + 0.28, cw - d - 0.28
            if it.get("texte"):
                els += [self.text(tx, cy, tw, 0.4, it.get("titre", ""), 18, th["texte"], bold=True),
                        self.text(tx, cy + 0.4, tw, rh - 0.5, it["texte"], 14, th["doux"])]
            else:
                els.append(self.text(tx, cy + 0.08, tw, rh - 0.2, it.get("titre", ""), 18, th["texte"], bold=True))
        return els

    def s_points(self, s):
        items = s.get("points") or []
        els = self.title(s, s.get("titre", ""))
        side = s.get("image") or s.get("chiffre")
        w = (W - 2 * M) * (0.56 if side else 1)
        els += self.rows(items, M, 1.75, w, H - 2.6)
        if s.get("image"):
            els.append({"k": "image", "path": s["image"], "x": M + w + 0.5, "y": 1.75, "w": W - 2 * M - w - 0.5, "h": H - 2.6})
        elif s.get("chiffre"):
            c = s["chiffre"]; x0 = M + w + 0.5; cw = W - M - x0
            els += [self.rect(x0, 1.9, cw, 3.8, self.th["clair"], radius=True),
                    self.text(x0 + 0.3, 2.4, cw - 0.6, 1.4, str(c.get("valeur", "")), 60, self.th["primaire"], bold=True, align="c", font=self.ft),
                    self.text(x0 + 0.3, 3.9, cw - 0.6, 1.4, c.get("label", ""), 16, self.th["texte"], align="c")]
        return "FFFFFF", els + self.footer(s)

    def s_chiffres(self, s):
        th, stats = self.th, (s.get("chiffres") or [])[:4]
        els = self.title(s, s.get("titre", ""))
        n = max(1, len(stats)); gap = 0.4; cw = (W - 2 * M - gap * (n - 1)) / n
        for i, c in enumerate(stats):
            x = M + i * (cw + gap)
            els += [self.rect(x, 2.0, cw, 3.6, th["clair"], radius=True),
                    self.text(x + 0.3, 2.35, cw - 0.6, 1.3, str(c.get("valeur", "")), 54 if n < 4 else 44, th["primaire"], bold=True, font=self.ft),
                    self.text(x + 0.3, 3.7, cw - 0.6, 0.8, c.get("label", ""), 17, th["texte"], bold=True)]
            if c.get("detail"):
                els.append(self.text(x + 0.3, 4.45, cw - 0.6, 1.0, c["detail"], 13, th["doux"]))
        if s.get("source"):
            els.append(self.text(M, 6.2, W - 2 * M, 0.4, s["source"], 11, th["doux"], italic=True))
        return "FFFFFF", els + self.footer(s)

    def s_comparaison(self, s):
        th = self.th
        els = self.title(s, s.get("titre", ""))
        cw = (W - 2 * M - 1.2) / 2
        for i, side in enumerate((s.get("gauche") or {}, s.get("droite") or {})):
            x = M + i * (cw + 1.2)
            fill = th["clair"] if i == 0 else mix(th["accent"], "FFFFFF", 0.82)
            pts = side.get("points") or []
            ch = min(H - 2.55, 1.55 + 0.62 * max(len(pts), len((s.get("gauche") or {}).get("points") or []), len((s.get("droite") or {}).get("points") or [])))
            els += [self.rect(x, 1.75, cw, ch, fill, radius=True),  # as tall as the longer list, not the whole slide
                    self.text(x + 0.4, 2.0, cw - 0.8, 0.6, side.get("titre", ""), 22, th["primaire"] if i == 0 else mix(th["accent"], "000000", 0.35), bold=True, font=self.ft),
                    self.text(x + 0.4, 2.75, cw - 0.8, ch - 1.15, pts, 18, th["texte"], bullets=True)]
        vy = 1.75 + ch / 2 - 0.45
        els += [self.oval(W / 2 - 0.45, vy, 0.9, th["primaire"]), self.text(W / 2 - 0.45, vy, 0.9, 0.9, "VS", 18, "FFFFFF", bold=True, align="c", valign="m", fit=False)]
        return "FFFFFF", els + self.footer(s)

    def s_etapes(self, s):
        th, st = self.th, (s.get("etapes") or [])[:6]
        els = self.title(s, s.get("titre", ""))
        n = max(1, len(st)); cw = (W - 2 * M) / n; d = 0.9; cy = 2.5
        els.append({"k": "line", "x": M + cw / 2, "y": cy + d / 2, "w": cw * (n - 1), "h": 0, "color": mix(th["primaire"], "FFFFFF", 0.6), "width": 2.5})
        for i, e in enumerate(st):
            e = e if isinstance(e, dict) else {"titre": str(e)}
            cx = M + i * cw + cw / 2
            els += [self.oval(cx - d / 2, cy, d, th["primaire"] if i % 2 == 0 else th["accent"]),
                    self.text(cx - d / 2, cy, d, d, str(i + 1), 26, "FFFFFF", bold=True, align="c", valign="m", fit=False),
                    self.text(cx - cw / 2 + 0.15, cy + 1.15, cw - 0.3, 0.7, e.get("titre", ""), 17, th["texte"], bold=True, align="c")]
            if e.get("texte"):
                els.append(self.text(cx - cw / 2 + 0.15, cy + 1.85, cw - 0.3, 2.0, e["texte"], 13, th["doux"], align="c"))
        return "FFFFFF", els + self.footer(s)

    s_frise = s_etapes
    s_processus = s_etapes

    def s_graphique(self, s):
        th = self.th
        els = self.title(s, s.get("titre", ""))
        com = s.get("commentaire")
        cw = (W - 2 * M) * (0.64 if com else 1)
        els.append({"k": "chart", "x": M, "y": 1.6, "w": cw, "h": H - 2.4, "type": str(s.get("graphique", "colonnes")).lower(),
                    "categories": s.get("categories") or [], "series": s.get("series") or [], "unite": s.get("unite", ""),
                    "colors": [th["primaire"], th["accent"], mix(th["primaire"], "FFFFFF", 0.45), mix(th["accent"], "000000", 0.3), th["doux"], mix(th["accent"], "FFFFFF", 0.5)]})
        if com:
            x0 = M + cw + 0.4; w0 = W - M - x0
            hh = min(4.4, 0.6 + text_lines(com, 20, w0 - 0.6, True, self.ft) * 20 * 1.22 / 72)
            els += [self.rect(x0, 1.9, w0, hh, th["clair"], radius=True),
                    self.text(x0 + 0.3, 2.2, w0 - 0.6, hh - 0.6, com, 20, th["primaire"], bold=True, font=self.ft)]
        return "FFFFFF", els + self.footer(s)

    def s_tableau(self, s):
        th = self.th
        els = self.title(s, s.get("titre", ""))
        rows = [s.get("colonnes") or []] + (s.get("lignes") or [])
        rh = min(0.6, (H - 2.6) / max(1, len(rows)))
        els.append({"k": "table", "x": M, "y": 1.75, "w": W - 2 * M, "h": rh * len(rows), "rows": rows, "head": th["primaire"], "zebra": th["clair"], "color": th["texte"]})
        return "FFFFFF", els + self.footer(s)

    def s_citation(self, s):
        th = self.th
        return th["clair"], [self.text(M + 0.3, 1.0, 2, 1.6, "“", 120, th["accent"], bold=True, font="Georgia", fit=False),
                             self.text(M + 1.1, 2.3, W - 2 * M - 2, 2.8, s.get("texte", ""), 30, th["primaire"], italic=True, font="Georgia"),
                             self.text(M + 1.1, 5.3, W - 2 * M - 2, 0.6, ("— " + s["auteur"]) if s.get("auteur") else "", 16, th["doux"], bold=True)]

    def s_image(self, s):
        els = self.title(s, s.get("titre", ""))
        els.append({"k": "image", "path": s.get("image", ""), "x": M, "y": 1.6, "w": W - 2 * M, "h": H - 2.6})
        if s.get("legende"):
            els.append(self.text(M, H - 0.95, W - 2 * M, 0.4, s["legende"], 12, self.th["doux"], italic=True, align="c"))
        return "FFFFFF", els + self.footer(s)

    def s_deux_colonnes(self, s):
        th = self.th
        els = self.title(s, s.get("titre", ""))
        cw = (W - 2 * M - 0.6) / 2
        for i, side in enumerate((s.get("gauche") or {}, s.get("droite") or {})):
            x = M + i * (cw + 0.6)
            y = 1.75
            if side.get("titre"):
                els.append(self.text(x, y, cw, 0.55, side["titre"], 20, th["primaire"], bold=True, font=self.ft)); y += 0.7
            if side.get("image"):
                els.append({"k": "image", "path": side["image"], "x": x, "y": y, "w": cw, "h": H - y - 0.8})
            elif side.get("points"):
                els.append(self.text(x, y, cw, H - y - 0.8, side["points"], 16, th["texte"], bullets=True))
            elif side.get("texte"):
                els.append(self.text(x, y, cw, H - y - 0.8, side["texte"], 16, th["texte"]))
        return "FFFFFF", els + self.footer(s)

    def s_conclusion(self, s):
        th = self.th
        els = [self.oval(-1.8, H - 3.2, 5, th["accent"], alpha=18),
               self.text(M + 0.2, 0.9, W - 2 * M, 1.1, s.get("titre", "À retenir"), 38, "FFFFFF", bold=True, font=self.ft)]
        for i, p in enumerate((s.get("points") or [])[:4]):
            y = 2.35 + i * 1.0
            els += [self.oval(M + 0.2, y, 0.55, th["accent"]), self.icon("check", M + 0.32, y + 0.12, 0.31, "FFFFFF"),
                    self.text(M + 1.0, y + 0.02, W - 2 * M - 1.2, 0.8, p if isinstance(p, str) else p.get("titre", ""), 20, "FFFFFF")]
        if s.get("contact"):
            els.append(self.text(M + 0.2, H - 1.0, 10, 0.4, s["contact"], 14, mix(th["primaire"], "FFFFFF", 0.65)))
        return th["primaire"], els


# ------------------------------------------------------------------ icons as pictures (for PowerPoint)
def icon_png(name, color, cache=Path.home() / ".naim/cache/diapo-icons"):
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"{name}-{color}.png"
    if out.exists():
        return out
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 24 24" fill="none" stroke="#{color}" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">{ICONS.get(name, ICONS["spark"])}</svg>'
    html = cache / f"{name}-{color}.html"
    html.write_text(f"<!doctype html><html><body style='margin:0;background:transparent'>{svg}</body></html>")
    subprocess.run([str(NAIM_PDF), str(html), str(out), "fit"], capture_output=True, timeout=60)
    html.unlink(missing_ok=True)
    return out if out.exists() else None


# ------------------------------------------------------------------ PowerPoint
def to_pptx(deck, slides, out, plan):
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
    from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.oxml.ns import qn
    from pptx.util import Inches, Pt, Emu

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(W), Inches(H)
    blank = prs.slide_layouts[6]
    rgb = lambda c: RGBColor.from_string(hexc(c))
    prs.core_properties.title = str(plan.get("titre") or (plan.get("diapositives") or [{}])[0].get("titre") or "Présentation")

    def alpha(shape, a):
        if a is None:
            return
        sp = shape.fill._xPr.find(qn("a:solidFill"))
        clr = sp[0] if sp is not None and len(sp) else None
        if clr is not None:
            el = clr.makeelement(qn("a:alpha"), {"val": str(int(a * 1000))})
            clr.append(el)

    for sd in slides:
        sl = prs.slides.add_slide(blank)
        sl.background.fill.solid(); sl.background.fill.fore_color.rgb = rgb(sd["bg"])
        for e in sd["els"]:
            x, y, w, h = Inches(e["x"]), Inches(e["y"]), Inches(e["w"]), Inches(e["h"])
            k = e["k"]
            if k in ("rect", "oval"):
                shp = sl.shapes.add_shape(MSO_SHAPE.OVAL if k == "oval" else (MSO_SHAPE.ROUNDED_RECTANGLE if e.get("radius") else MSO_SHAPE.RECTANGLE), x, y, w, h)
                shp.fill.solid(); shp.fill.fore_color.rgb = rgb(e["fill"]); alpha(shp, e.get("alpha"))
                if e.get("radius"):
                    shp.adjustments[0] = 0.08
                if e.get("line"):
                    shp.line.color.rgb = rgb(e["line"])
                else:
                    shp.line.fill.background()
                shp.shadow.inherit = False
            elif k == "text":
                tb = sl.shapes.add_textbox(x, y, w, h); tf = tb.text_frame; tf.word_wrap = True
                tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
                tf.vertical_anchor = {"m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}.get(e["valign"], MSO_ANCHOR.TOP)
                items = e["text"] if isinstance(e["text"], list) else [e["text"]]
                for i, t in enumerate(items):
                    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    p.alignment = {"c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}.get(e["align"], PP_ALIGN.LEFT)
                    if e["bullets"]:
                        pPr = p._p.get_or_add_pPr(); pPr.set("marL", str(Emu(Inches(0.28)))); pPr.set("indent", str(-Emu(Inches(0.28))))
                        bu = pPr.makeelement(qn("a:buChar"), {"char": "•"}); pPr.append(bu)
                        p.space_after = Pt(8)
                    r = p.add_run(); r.text = str(t if not isinstance(t, dict) else t.get("titre", ""))
                    f = r.font; f.size = Pt(e["size"]); f.bold = e["bold"]; f.italic = e["italic"]; f.name = e["font"]; f.color.rgb = rgb(e["color"])
            elif k == "icon":
                png = icon_png(e["name"], hexc(e["color"]))
                if png:
                    pic = sl.shapes.add_picture(str(png), x, y, w, h); pic.name = f"Icône {e['name']}"
            elif k == "line":
                ln = sl.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x, y, Inches(e["x"] + e["w"]), Inches(e["y"] + e["h"]))
                ln.line.color.rgb = rgb(e["color"]); ln.line.width = Pt(e.get("width", 2))
            elif k == "image":
                p = Path(str(e.get("path", ""))).expanduser()
                if p.exists():
                    try:
                        from PIL import Image
                        iw, ih = Image.open(p).size
                        r = min(e["w"] / iw, e["h"] / ih); dw, dh = iw * r, ih * r
                        sl.shapes.add_picture(str(p), Inches(e["x"] + (e["w"] - dw) / 2), Inches(e["y"] + (e["h"] - dh) / 2), Inches(dw), Inches(dh))
                    except Exception:  # noqa: BLE001
                        sl.shapes.add_picture(str(p), x, y, w)
                else:
                    deck.warnings.append(f"image introuvable : {p}")
            elif k == "table":
                rows = e["rows"]; nc = max(len(r) for r in rows) if rows else 1
                tbl = sl.shapes.add_table(len(rows), nc, x, y, w, h).table
                for i, row in enumerate(rows):
                    for j in range(nc):
                        c = tbl.cell(i, j); c.text = str(row[j]) if j < len(row) else ""
                        c.fill.solid(); c.fill.fore_color.rgb = rgb(e["head"] if i == 0 else (e["zebra"] if i % 2 == 0 else "FFFFFF"))
                        for p in c.text_frame.paragraphs:
                            for r in p.runs:
                                r.font.size = Pt(14); r.font.name = deck.fb; r.font.bold = i == 0
                                r.font.color.rgb = rgb("FFFFFF" if i == 0 else e["color"])
                                if j > 0 and re.fullmatch(r"[-+]?[\d\s.,%€$]+", r.text.strip() or "x"):
                                    p.alignment = PP_ALIGN.RIGHT
            elif k == "chart":
                types = {"colonnes": XL_CHART_TYPE.COLUMN_CLUSTERED, "barres": XL_CHART_TYPE.BAR_CLUSTERED, "lignes": XL_CHART_TYPE.LINE_MARKERS,
                         "courbe": XL_CHART_TYPE.LINE_MARKERS, "camembert": XL_CHART_TYPE.PIE, "anneau": XL_CHART_TYPE.DOUGHNUT,
                         "empile": XL_CHART_TYPE.COLUMN_STACKED, "aire": XL_CHART_TYPE.AREA}
                ct = types.get(e["type"].replace("é", "e"), XL_CHART_TYPE.COLUMN_CLUSTERED)
                cd = CategoryChartData(); cd.categories = [str(c) for c in e["categories"]]
                for se in e["series"]:
                    cd.add_series(str(se.get("nom", "")), [float(v) for v in se.get("valeurs", [])])
                ch = sl.shapes.add_chart(ct, x, y, w, h, cd).chart
                ch.font.size = Pt(12); ch.font.name = deck.fb; ch.font.color.rgb = rgb(deck.th["doux"])
                pie = ct in (XL_CHART_TYPE.PIE, XL_CHART_TYPE.DOUGHNUT)
                ch.has_legend = pie or len(e["series"]) > 1
                if ch.has_legend:
                    ch.legend.position = XL_LEGEND_POSITION.BOTTOM; ch.legend.include_in_layout = False
                plot = ch.plots[0]
                plot.has_data_labels = True
                dl = plot.data_labels; dl.font.size = Pt(12); dl.font.color.rgb = rgb(deck.th["texte"])
                if pie:
                    dl.show_percentage, dl.show_value, dl.show_category_name = True, False, False
                    for i, pt in enumerate(plot.series[0].points):
                        pt.format.fill.solid(); pt.format.fill.fore_color.rgb = rgb(e["colors"][i % len(e["colors"])])
                else:
                    dl.number_format = '#,##0.##' + (f' "{e["unite"]}"' if e.get("unite") else ""); dl.number_format_is_linked = False
                    if ct != XL_CHART_TYPE.COLUMN_STACKED:
                        dl.position = XL_LABEL_POSITION.OUTSIDE_END if ct in (XL_CHART_TYPE.COLUMN_CLUSTERED, XL_CHART_TYPE.BAR_CLUSTERED) else XL_LABEL_POSITION.ABOVE
                    for i, se in enumerate(plot.series):
                        f = se.format
                        if ct in (XL_CHART_TYPE.LINE_MARKERS,):
                            f.line.color.rgb = rgb(e["colors"][i % 6]); f.line.width = Pt(2.75)
                        else:
                            f.fill.solid(); f.fill.fore_color.rgb = rgb(e["colors"][i % 6])
                    try:
                        ch.value_axis.has_major_gridlines = True
                        ch.value_axis.major_gridlines.format.line.color.rgb = rgb(mix(deck.th["doux"], "FFFFFF", 0.75))
                        ch.value_axis.format.line.fill.background(); ch.category_axis.format.line.color.rgb = rgb(mix(deck.th["doux"], "FFFFFF", 0.5))
                        ch.value_axis.tick_labels.font.size = Pt(11); ch.category_axis.tick_labels.font.size = Pt(12)
                    except Exception:  # noqa: BLE001
                        pass
        if sd.get("notes"):
            sl.notes_slide.notes_text_frame.text = str(sd["notes"])
    prs.save(out)


# ------------------------------------------------------------------ the pictures of the slides (same layout)
def svg_chart(e):
    w, h = e["w"] * PX, e["h"] * PX
    cats, series, cols = e["categories"], e["series"], e["colors"]
    t = e["type"]
    if t in ("camembert", "anneau"):
        import math
        vals = [float(v) for v in (series[0].get("valeurs", []) if series else [])]
        tot = sum(vals) or 1; cx, cy, r = w / 2, h / 2 - 14, min(w, h) / 2 - 34; a0 = -math.pi / 2; out = ""
        for i, v in enumerate(vals):
            a1 = a0 + 2 * math.pi * v / tot
            big = 1 if a1 - a0 > math.pi else 0
            out += f'<path d="M{cx},{cy} L{cx + r * math.cos(a0)},{cy + r * math.sin(a0)} A{r},{r} 0 {big} 1 {cx + r * math.cos(a1)},{cy + r * math.sin(a1)} Z" fill="#{cols[i % 6]}"/>'
            am = (a0 + a1) / 2
            out += f'<text x="{cx + r * 0.68 * math.cos(am)}" y="{cy + r * 0.68 * math.sin(am) + 5}" text-anchor="middle" fill="#fff" font-weight="700">{round(100 * v / tot)} %</text>'
            a0 = a1
        if t == "anneau":
            out += f'<circle cx="{cx}" cy="{cy}" r="{r * 0.5}" fill="#fff"/>'
        leg = "".join(f'<tspan fill="#{cols[i % 6]}">■</tspan> {escape(str(c))}   ' for i, c in enumerate(cats))
        return f'<svg width="{w}" height="{h}">{out}<text x="{w / 2}" y="{h - 8}" text-anchor="middle" font-size="13">{leg}</text></svg>'
    allv = [float(v) for s in series for v in s.get("valeurs", [])] or [1]
    vmax = max(max(allv), 0) * 1.15 or 1
    L, B, T, R = 50, 34, 14, 10
    pw, ph = w - L - R, h - B - T
    out = "".join(f'<line x1="{L}" x2="{w - R}" y1="{T + ph * (1 - k / 4)}" y2="{T + ph * (1 - k / 4)}" stroke="#e3e3e3"/>' for k in range(5))
    n, ns = max(1, len(cats)), max(1, len(series))
    for j, c in enumerate(cats):
        out += f'<text x="{L + pw * (j + .5) / n}" y="{h - 10}" text-anchor="middle" font-size="13">{escape(str(c))}</text>'
    for i, s in enumerate(series):
        vs = [float(v) for v in s.get("valeurs", [])]
        if t in ("lignes", "courbe", "aire"):
            pts = " ".join(f"{L + pw * (j + .5) / n},{T + ph * (1 - v / vmax)}" for j, v in enumerate(vs))
            out += f'<polyline points="{pts}" fill="none" stroke="#{cols[i % 6]}" stroke-width="3"/>'
            out += "".join(f'<circle cx="{L + pw * (j + .5) / n}" cy="{T + ph * (1 - v / vmax)}" r="4.5" fill="#{cols[i % 6]}"/><text x="{L + pw * (j + .5) / n}" y="{T + ph * (1 - v / vmax) - 9}" text-anchor="middle" font-size="12">{v:g}</text>' for j, v in enumerate(vs))
        else:
            bw = pw / n * 0.7 / ns
            for j, v in enumerate(vs):
                x = L + pw * j / n + pw / n * 0.15 + i * bw; bh = ph * v / vmax
                out += f'<rect x="{x}" y="{T + ph - bh}" width="{bw * 0.92}" height="{bh}" fill="#{cols[i % 6]}"/><text x="{x + bw * 0.46}" y="{T + ph - bh - 6}" text-anchor="middle" font-size="12">{v:g}{escape(e.get("unite", "") and " " + e["unite"])}</text>'
    return f'<svg width="{w}" height="{h}">{out}</svg>'


def to_html(sd):
    def box(e):
        return f"left:{e['x'] * PX:.1f}px;top:{e['y'] * PX:.1f}px;width:{e['w'] * PX:.1f}px;height:{e['h'] * PX:.1f}px;"
    parts = []
    for e in sd["els"]:
        k = e["k"]
        if k in ("rect", "oval"):
            op = f"opacity:{e['alpha'] / 100 if e.get('alpha') is not None else 1};"  # alpha: how opaque, in %
            parts.append(f'<div style="position:absolute;{box(e)}background:#{e["fill"]};{op}border-radius:{"50%" if k == "oval" else ("12px" if e.get("radius") else "0")}"></div>')
        elif k == "text":
            items = e["text"] if isinstance(e["text"], list) else [e["text"]]
            inner = "".join(f'<div style="{"padding-left:22px;text-indent:-22px;margin-bottom:8px" if e["bullets"] else ""}">{"•&nbsp;&nbsp;&nbsp;" if e["bullets"] else ""}{escape(str(t if not isinstance(t, dict) else t.get("titre", ""))).replace(chr(10), "<br>")}</div>' for t in items)
            jc = {"m": "center", "b": "flex-end"}.get(e["valign"], "flex-start")
            parts.append(f'<div style="position:absolute;{box(e)}display:flex;flex-direction:column;justify-content:{jc};font-family:{e["font"]};font-size:{e["size"] * PX / 72:.1f}px;'
                         f'line-height:1.18;color:#{e["color"]};font-weight:{700 if e["bold"] else 400};font-style:{"italic" if e["italic"] else "normal"};text-align:{ {"c": "center", "r": "right"}.get(e["align"], "left") }">{inner}</div>')
        elif k == "icon":
            parts.append(f'<svg style="position:absolute;{box(e)}" viewBox="0 0 24 24" fill="none" stroke="#{e["color"]}" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">{ICONS.get(e["name"], ICONS["spark"])}</svg>')
        elif k == "line":
            parts.append(f'<div style="position:absolute;left:{e["x"] * PX}px;top:{e["y"] * PX - 1.5}px;width:{e["w"] * PX}px;height:3px;background:#{e["color"]}"></div>')
        elif k == "image":
            p = Path(str(e.get("path", ""))).expanduser()
            parts.append(f'<img src="{p.as_uri() if p.exists() else ""}" style="position:absolute;{box(e)}object-fit:contain">')
        elif k == "table":
            rows = e["rows"]
            trs = "".join("<tr>" + "".join(f'<td style="padding:6px 10px;background:#{e["head"] if i == 0 else (e["zebra"] if i % 2 == 0 else "FFFFFF")};color:#{"FFFFFF" if i == 0 else e["color"]};font-weight:{700 if i == 0 else 400}">{escape(str(c))}</td>' for c in r) + "</tr>" for i, r in enumerate(rows))
            parts.append(f'<table style="position:absolute;{box(e)}border-collapse:collapse;font:{14 * PX / 72:.0f}px Arial">{trs}</table>')
        elif k == "chart":
            parts.append(f'<div style="position:absolute;{box(e)}font-family:Arial;color:#555">{svg_chart(e)}</div>')
    return (f'<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0"><div style="position:relative;width:{W * PX:.0f}px;height:{H * PX:.0f}px;overflow:hidden;background:#{sd["bg"]}">'
            + "".join(parts) + "</div></body></html>")


def pictures(slides, out):
    d = Path(out).with_suffix("")
    d = d.parent / (d.name + "-apercu")
    d.mkdir(exist_ok=True)
    made = []
    if not NAIM_PDF.exists():
        return made
    for i, sd in enumerate(slides, 1):
        h = d / f"diapo-{i}.html"; png = d / f"diapo-{i}.png"
        h.write_text(to_html(sd))
        subprocess.run([str(NAIM_PDF), str(h), str(png), "fit"], capture_output=True, timeout=90)
        h.unlink(missing_ok=True)
        if png.exists():
            try:  # the picture is exactly the slide (16:9), nothing of the page under it
                from PIL import Image
                im = Image.open(png); im.crop((0, 0, im.width, round(im.width * H / W))).save(png)
            except Exception:  # noqa: BLE001
                pass
            made.append(str(png))
    return made


# ------------------------------------------------------------------ commands
def faire(plan_path, out):
    plan = json.loads(Path(plan_path).read_text())
    deck = Deck(plan)
    slides = [deck.slide(s) for s in plan.get("diapositives") or plan.get("slides") or []]
    if not slides:
        sys.exit("le plan n'a pas de « diapositives »")
    kinds = [str(s.get("type", "points")) for s in plan.get("diapositives") or []]
    for a, b in zip(kinds, kinds[1:]):
        if a == b and a not in ("section",):
            deck.warnings.append(f"deux diapositives « {a} » à la suite : varie la mise en page (chiffres, étapes, comparaison, graphique…)")
            break
    to_pptx(deck, slides, out, plan)
    pics = pictures(slides, out)
    print(f"PowerPoint : {Path(out).resolve()} ({len(slides)} diapositives)")
    if pics:
        print(f"Aperçus : {Path(pics[0]).parent.resolve()} — regarde-les avec look_at (diapo-1.png … diapo-{len(pics)}.png) avant de livrer")
    for w in deck.warnings:
        print("PROBLÈME :", w)
    if not deck.warnings:
        print("Contrôle : aucun texte qui déborde")


def lire(path):
    from pptx import Presentation
    prs = Presentation(path)
    for i, sl in enumerate(prs.slides, 1):
        print(f"<!-- Diapositive {i} -->")
        for sh in sl.shapes:
            if sh.has_text_frame and sh.text_frame.text.strip():
                print(sh.text_frame.text.strip())
            if getattr(sh, "has_table", False) and sh.has_table:
                for r in sh.table.rows:
                    print("| " + " | ".join(c.text for c in r.cells) + " |")
            if getattr(sh, "has_chart", False) and sh.has_chart:
                ch = sh.chart
                print(f"[graphique : {', '.join(str(c) for c in ch.plots[0].categories)}]")
            if sh.shape_type == 13:
                print(f"[image{': ' + sh.name if sh.name else ''}]")
        if sl.has_notes_slide and sl.notes_slide.notes_text_frame.text.strip():
            print("Notes :", sl.notes_slide.notes_text_frame.text.strip())
        print()


def modifier(path, changes_path, out):
    """Changes without rebuilding: replace a text (its style kept), notes, delete or move a slide."""
    from pptx import Presentation
    prs = Presentation(path)
    ch = json.loads(Path(changes_path).read_text())
    ch = ch if isinstance(ch, list) else ch.get("changements", [])
    done = []
    for c in ch:
        if "remplacer" in c:
            r = c["remplacer"]; n = int(r.get("diapo", 0)); old, new = str(r["ancien"]), str(r["nouveau"]); hit = 0
            for i, sl in enumerate(prs.slides, 1):
                if n and i != n:
                    continue
                for sh in sl.shapes:
                    frames = [sh.text_frame] if sh.has_text_frame else []
                    if getattr(sh, "has_table", False) and sh.has_table:
                        frames += [cell.text_frame for row in sh.table.rows for cell in row.cells]
                    for tf in frames:
                        for p in tf.paragraphs:
                            whole = "".join(r_.text for r_ in p.runs)
                            if old in whole and p.runs:
                                p.runs[0].text = whole.replace(old, new)
                                for r_ in p.runs[1:]:
                                    r_.text = ""
                                hit += 1
            done.append(f"« {old[:30]} » → « {new[:30]} » : {hit} fois" if hit else f"PROBLÈME : « {old[:40]} » introuvable")
        elif "notes" in c:
            sl = prs.slides[int(c["notes"]["diapo"]) - 1]; sl.notes_slide.notes_text_frame.text = str(c["notes"]["texte"]); done.append("notes changées")
        elif "supprimer" in c:
            idx = int(c["supprimer"]) - 1; lst = prs.slides._sldIdLst; sid = list(lst)[idx]
            prs.part.drop_rel(sid.rId); lst.remove(sid); done.append(f"diapositive {idx + 1} supprimée")
        elif "deplacer" in c:
            a, b = (int(v) - 1 for v in c["deplacer"]); lst = prs.slides._sldIdLst; el = list(lst)[a]; lst.remove(el); lst.insert(b, el)
            done.append(f"diapositive {a + 1} placée en {b + 1}")
    prs.save(out)
    print(f"PowerPoint : {Path(out).resolve()}")
    for d in done:
        print(d)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["faire"] and len(a) >= 3:
        faire(a[1], a[2])
    elif a[:1] == ["lire"] and len(a) >= 2:
        lire(a[1])
    elif a[:1] == ["modifier"] and len(a) >= 4:
        modifier(a[1], a[2], a[3])
    elif a[:1] == ["themes"]:
        for k, v in THEMES.items():
            print(f"{k:10} primaire #{v['primaire']} · accent #{v['accent']}")
    else:
        print(__doc__)
