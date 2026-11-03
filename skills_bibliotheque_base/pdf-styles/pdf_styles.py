from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
H = colors.HexColor

THEMES = {
 "classique": dict(file="style_1_classique.pdf", name="Classique élégant", font="Times-Roman", bold="Times-Bold", ital="Times-Italic",
    ink=H("#1B2A41"), acc=H("#8C2F39"), light=H("#F5F1E8"), grey=H("#5A5A5A"), center=True, band=False, tbl_head=H("#1B2A41"), size=11.5),
 "moderne": dict(file="style_2_moderne.pdf", name="Moderne et coloré", font="Helvetica", bold="Helvetica-Bold", ital="Helvetica-Oblique",
    ink=H("#16202A"), acc=H("#0E9F8E"), light=H("#E8F6F4"), grey=H("#5B6B78"), center=False, band=True, tbl_head=H("#0E9F8E"), size=10.5),
 "minimal": dict(file="style_3_minimaliste.pdf", name="Minimaliste", font="Helvetica", bold="Helvetica-Bold", ital="Helvetica-Oblique",
    ink=H("#111111"), acc=H("#111111"), light=H("#F6F6F6"), grey=H("#8A8A8A"), center=False, band=False, tbl_head=None, size=10),
}

def build(k):
    t = THEMES[k]
    body = ParagraphStyle("b", fontName=t["font"], fontSize=t["size"], leading=t["size"]*1.5, textColor=t["ink"], spaceAfter=7)
    cell = ParagraphStyle("c", parent=body, fontSize=9.5, leading=13, spaceAfter=0)
    al = 1 if t["center"] else 0
    title = ParagraphStyle("t", fontName=t["bold"] if k!="minimal" else t["font"], fontSize=30 if k!="minimal" else 34, leading=36,
        textColor=colors.white if t["band"] else t["ink"], alignment=al, spaceAfter=4)
    sub = ParagraphStyle("s", fontName=t["ital"], fontSize=12, textColor=colors.HexColor("#CFEFEA") if t["band"] else t["grey"], alignment=al, spaceAfter=10)
    h1 = ParagraphStyle("h1", fontName=t["bold"], fontSize=15 if k!="minimal" else 11, textColor=t["acc"], spaceBefore=16, spaceAfter=6)
    cellh = ParagraphStyle("ch", parent=cell, fontName=t["bold"], textColor=colors.white if t["tbl_head"] else t["ink"])

    def deco(c, d):
        c.saveState()
        c.setFont(t["font"], 8.5); c.setFillColor(t["grey"])
        if k == "classique":
            c.drawCentredString(A4[0]/2, 1.2*cm, f"— {d.page} —")
            c.setStrokeColor(t["acc"]); c.setLineWidth(0.6); c.line(2.5*cm, A4[1]-1.5*cm, A4[0]-2.5*cm, A4[1]-1.5*cm)
        elif k == "moderne":
            c.setFillColor(t["acc"]); c.rect(0, 0, A4[0], 0.5*cm, stroke=0, fill=1)
            c.setFillColor(t["grey"]); c.drawRightString(A4[0]-2*cm, 1.0*cm, f"Page {d.page}")
        else:
            c.drawString(2.5*cm, 1.4*cm, "Exemple de style"); c.drawRightString(A4[0]-2.5*cm, 1.4*cm, f"{d.page:02d}")
        c.restoreState()

    margin = 2.5*cm if k != "moderne" else 2*cm
    W = A4[0] - 2*margin
    doc = SimpleDocTemplate(t["file"], pagesize=A4, leftMargin=margin, rightMargin=margin,
        topMargin=2.2*cm, bottomMargin=2.2*cm, title=t["name"], author="Naim")
    s = []
    if t["band"]:
        hb = Table([[Paragraph(t["name"], title)], [Paragraph("Un aperçu de ce que je peux produire", sub)]], colWidths=[W])
        hb.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),t["ink"]),("LEFTPADDING",(0,0),(-1,-1),16),
            ("TOPPADDING",(0,0),(0,0),18),("BOTTOMPADDING",(0,-1),(-1,-1),16)]))
        s += [hb, Spacer(1, 6)]
    else:
        s += [Spacer(1, 10 if k=="classique" else 30), Paragraph(t["name"], title), Paragraph("Un aperçu de ce que je peux produire", sub)]
        if k == "classique":
            s += [HRFlowable(width="100%", thickness=2, color=t["acc"], spaceAfter=1), HRFlowable(width="100%", thickness=0.5, color=t["acc"], spaceAfter=10)]
        else:
            s += [Spacer(1, 12)]
    h = (lambda x: x.upper()) if k=="minimal" else (lambda x: x)
    s += [Paragraph(h("1. Texte et mise en forme"), h1),
          Paragraph("Voici un paragraphe d'exemple. Je peux utiliser du <b>gras</b>, de l'<i>italique</i> et du "
                    f"<font color='{t['acc'].hexval().replace('0x','#')}'>texte coloré</font>. La typographie, les marges et les couleurs "
                    "changent complètement l'ambiance d'un document, sans changer son contenu.", body),
          ListFlowable([ListItem(Paragraph(x, body), leftIndent=14) for x in
              ["Hiérarchie claire des titres", "Listes pour structurer les idées", "En-têtes et pieds de page personnalisés"]],
              bulletType="bullet", bulletColor=t["acc"]),
          Paragraph(h("2. Tableau"), h1)]
    rows = [("Rapports","Documents structurés","Disponible"),("Factures","Totaux et logo","Disponible"),("CV","Mise en page soignée","Disponible")]
    data = [[Paragraph(x, cellh) for x in ["Élément","Description","Statut"]]] + [[Paragraph(c, cell) for c in r] for r in rows]
    tb = Table(data, colWidths=[W*0.25, W*0.5, W*0.25], repeatRows=1)
    st = [("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),("LEFTPADDING",(0,0),(-1,-1),8)]
    if t["tbl_head"]:
        st += [("BACKGROUND",(0,0),(-1,0),t["tbl_head"]),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,t["light"]])]
        if k=="classique": st += [("BOX",(0,0),(-1,-1),0.6,t["ink"])]
    else:
        st += [("LINEBELOW",(0,0),(-1,0),0.8,t["ink"]),("LINEBELOW",(0,1),(-1,-1),0.3,colors.HexColor("#CCCCCC")),("LEFTPADDING",(0,0),(-1,-1),0)]
    tb.setStyle(TableStyle(st))
    s += [tb, Spacer(1, 12), Paragraph(h("3. Encadré"), h1)]
    bx = Table([[Paragraph("<b>À savoir :</b> dites-moi le contenu, le ton et les couleurs souhaités, et j'adapte le style.", body)]], colWidths=[W])
    bs = [("BACKGROUND",(0,0),(-1,-1),t["light"]),("LEFTPADDING",(0,0),(-1,-1),12),("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),4)]
    if k=="classique": bs += [("BOX",(0,0),(-1,-1),0.8,t["acc"])]
    elif k=="moderne": bs += [("LINEBEFORE",(0,0),(0,-1),4,t["acc"])]
    bx.setStyle(TableStyle(bs)); s += [bx]
    doc.build(s, onFirstPage=deco, onLaterPages=deco)

for k in THEMES: build(k)
