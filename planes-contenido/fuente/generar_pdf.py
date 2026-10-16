from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, KeepTogether)
import os

OUT = os.path.join(os.path.dirname(__file__), "..",
                   "Plan_de_Contenidos_Escuela_y_Tour_Lima_Noviembre.pdf")

PRIMARY = colors.HexColor("#1F2A44")
ACCENT = colors.HexColor("#C8102E")
SOFT = colors.HexColor("#F3F4F7")
MUTED = colors.HexColor("#5B6475")

h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=22, leading=27, textColor=PRIMARY)
sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=11, leading=15, textColor=MUTED)
h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=PRIMARY, spaceBefore=12, spaceAfter=6)
h3 = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=ACCENT, spaceBefore=8, spaceAfter=3)
body = ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=14.5)
cell = ParagraphStyle("cell", parent=body, fontSize=9.5, leading=13)
cellb = ParagraphStyle("cellb", parent=cell, fontName="Helvetica-Bold", textColor=PRIMARY)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=12, bulletIndent=2)
quote = ParagraphStyle("quote", parent=body, fontName="Helvetica-Oblique", textColor=PRIMARY,
                       backColor=SOFT, borderPadding=8, leftIndent=8, rightIndent=8, spaceBefore=10, spaceAfter=10)

def P(t, s=body): return Paragraph(t, s)
def bullets(items): return [Paragraph(i, bullet, bulletText="•") for i in items]

def kv_table(rows, widths=(45*mm, 125*mm)):
    t = Table([[P(k, cellb), P(v, cell)] for k, v in rows], colWidths=widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), SOFT),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D5D9E0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t

def grid_table(header, rows, widths):
    data = [[P(h, ParagraphStyle("th", parent=cellb, textColor=colors.white)) for h in header]]
    data += [[P(c, cell) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D5D9E0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t

def footer(c, doc):
    c.saveState()
    c.setFillColor(ACCENT); c.rect(0, A4[1]-6*mm, A4[0], 6*mm, stroke=0, fill=1)
    c.setFont("Helvetica", 8); c.setFillColor(MUTED)
    c.drawString(20*mm, 10*mm, "Plan de contenidos · Noviembre")
    c.drawRightString(A4[0]-20*mm, 10*mm, f"Página {doc.page}")
    c.restoreState()

story = [
    Spacer(1, 4*mm),
    P("Plan de Contenidos", h1),
    P("Escuela para Profesores (23 de noviembre) y Separación de Cupos (24 de noviembre)", sub),
    Spacer(1, 6*mm),

    P("1. Resumen general", h2),
    grid_table(
        ["Fecha", "Actividad", "Asistentes", "Piezas"],
        [
            ["<b>23 de noviembre</b>", "Escuela para Profesores (por invitación)", "Grupo reducido y exclusivo · máx. 32 personas", "1 post de invitación"],
            ["<b>24 de noviembre</b>", "Cobro de S/ 150 para separar cupo", "Meta: 200 personas", "2 posts + 1 video"],
        ],
        (34*mm, 48*mm, 48*mm, 40*mm)),

    P("2. Día 23 de noviembre · Escuela para Profesores", h2),
    kv_table([
        ("Tipo de evento", "Evento <b>por invitación</b>. Grupo <b>reducido pero exclusivo</b>."),
        ("Asistentes", "Pocas personas: según estima el cliente, <b>a lo sumo 32</b>, ya que habrá <b>16 camillas</b>."),
        ("Separación de cupo", "<b>No aplica.</b> Los invitados no tienen que separar cupo."),
        ("Pieza", "<b>1 post de invitación</b>."),
        ("Imagen", "La imagen que desea el cliente dentro de la invitación es la de <b>las camillas</b>."),
    ]),

    P("3. Día 24 de noviembre · Separación de cupos", h2),
    kv_table([
        ("Objetivo", "Día de <b>cobro de S/ 150 para separar tu cupo</b>."),
        ("Meta", "Llenar <b>200 personas</b> para que sea rentable, según comenta el cliente."),
        ("Dirección", "<b>HOTEL MELIÁ LIMA</b> · Av. Gral. Felipe Salaverry 2599, San Isidro."),
        ("Piezas", "<b>2 posts + 1 video</b>."),
        ("Protagonistas", "De preferencia, <b>las coreanas</b> haciendo su tour y llegando a Lima."),
        ("Número de contacto", "<b>986 484 513</b> · irá en la campaña, en los posts y en el video."),
    ]),

    P("Idea del cliente", h3),
    P("La imagen y la idea que tienen es como <b>los anuncios que se hacen cuando las bandas o los coaches "
      "se van de gira</b>. Dentro del flyer se debe informar:"),
    *bullets([
        "<b>Qué países</b> han visitado.",
        "<b>A qué hora llegan a Perú</b>.",
    ]),
    P("Referencias", h3),
    P("Se pueden tomar referencias de la <b>Biblioteca de anuncios de Facebook</b>."),

    KeepTogether([P("4. Entregables", h2),
    grid_table(
        ["#", "Entregable", "Fecha"],
        [
            ["1", "Post de invitación – Escuela para Profesores (imagen de las camillas)", "23 nov"],
            ["2", "Post 1 – Anuncio estilo gira (países visitados y hora de llegada a Perú)", "24 nov"],
            ["3", "Post 2 – Anuncio estilo gira (países visitados y hora de llegada a Perú)", "24 nov"],
            ["4", "Video – Las coreanas haciendo su tour y llegando a Lima", "24 nov"],
        ],
        (10*mm, 130*mm, 30*mm))]),
]

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                        topMargin=18*mm, bottomMargin=18*mm,
                        title="Plan de Contenidos – Escuela y Tour Lima", author="Equipo de Marketing")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(os.path.abspath(OUT))
