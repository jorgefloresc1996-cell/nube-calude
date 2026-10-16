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
    c.drawString(20*mm, 10*mm, "Plan de contenidos · Noviembre · Contacto de campaña: 986 484 513")
    c.drawRightString(A4[0]-20*mm, 10*mm, f"Página {doc.page}")
    c.restoreState()

story = [
    Spacer(1, 4*mm),
    P("Plan de Contenidos", h1),
    P("Escuela para Profesores (23 nov) y Evento de Separación de Cupos “Tour Lima” (24 nov)", sub),
    Spacer(1, 6*mm),

    P("1. Resumen general", h2),
    grid_table(
        ["Fecha", "Actividad", "Meta / Aforo", "Piezas a producir"],
        [
            ["<b>Lunes 23 de noviembre</b>", "Escuela para Profesores", "Máx. 32 personas (16 camillas)", "1 post de invitación"],
            ["<b>Martes 24 de noviembre</b>", "Separación de cupo · S/ 150", "200 personas (punto de rentabilidad)", "2 posts + 1 video"],
        ],
        (34*mm, 45*mm, 45*mm, 46*mm)),
    Spacer(1, 3*mm),
    P("<b>Número de contacto para toda la campaña (posts, video y anuncios): 986 484 513</b>"),

    P("2. Día 23 de noviembre · Escuela para Profesores", h2),
    kv_table([
        ("Objetivo", "Invitar a la Escuela para Profesores, una sesión práctica y de grupo reducido."),
        ("Aforo", "Pocas personas: según estimación del cliente, <b>a lo sumo 32 asistentes</b>, ya que se contará con <b>16 camillas</b> (2 personas por camilla)."),
        ("Pieza", "<b>1 post de invitación</b> (feed de Instagram / Facebook; adaptable a historia)."),
        ("Imagen", "La que pide el cliente: <b>fotografía de las camillas</b> preparadas para la sesión."),
        ("Enfoque del mensaje", "Exclusividad y cupos limitados: “solo 16 camillas”, “grupo reducido”, “práctica guiada”."),
        ("Contacto", "986 484 513"),
    ]),
    P("Copy sugerido para el post", h3),
    P("“Escuela para Profesores · Lunes 23 de noviembre. Una jornada práctica con solo 16 camillas "
      "disponibles: grupo reducido y atención personalizada. Cupos muy limitados. "
      "Reserva tu lugar al 986 484 513.”", quote),
    P("Lineamientos de diseño", h3),
    *bullets([
        "Imagen principal: camillas alineadas, bien iluminadas, transmitiendo orden y profesionalismo.",
        "Destacar en el arte: fecha (23 de noviembre), “Cupos limitados” y el número 986 484 513.",
        "Llamado a la acción claro: “Reserva tu lugar” / “Escríbenos por WhatsApp”.",
    ]),

    P("3. Día 24 de noviembre · Separación de cupos “Tour Lima”", h2),
    kv_table([
        ("Objetivo", "Que los asistentes paguen <b>S/ 150 para separar su cupo</b>."),
        ("Meta de asistentes", "<b>200 personas</b> para que el evento sea rentable, según comenta el cliente "
                               "(200 × S/ 150 = <b>S/ 30,000</b> en separaciones)."),
        ("Lugar", "<b>HOTEL MELIÁ LIMA</b> · Av. Gral. Felipe Salaverry 2599, San Isidro, Lima."),
        ("Piezas", "<b>2 posts + 1 video</b>."),
        ("Protagonistas", "De preferencia, <b>las coreanas</b>, mostrando su tour y su llegada a Lima."),
        ("Contacto", "<b>986 484 513</b> (debe ir en la campaña, en los posts y en el video)."),
    ]),

    P("Concepto creativo: anuncio “de gira”", h3),
    P("La idea del cliente es que la pieza se vea como los anuncios que se hacen cuando las <b>bandas o los "
      "coaches se van de gira</b>. El flyer debe informar:"),
    *bullets([
        "<b>Los países donde ya han estado</b> (listado tipo “tour dates”, con banderas o ciudades).",
        "<b>La fecha y la hora en que llegan a Perú</b>: “Próxima parada: LIMA · 24 de noviembre”.",
        "El lugar del evento (Hotel Meliá Lima, San Isidro), el precio de separación (S/ 150) y el número 986 484 513.",
    ]),
    P("<b>Referencias:</b> revisar la <b>Biblioteca de anuncios de Facebook (Meta Ad Library)</b> buscando anuncios "
      "de giras de bandas, conciertos, conferencias y coaches internacionales, para tomar estructura, tipografías "
      "y estilo visual."),

    KeepTogether([
        P("Detalle de piezas", h3),
        grid_table(
            ["Pieza", "Contenido", "Elementos obligatorios"],
            [
                ["<b>Post 1</b> · Flyer de gira",
                 "Flyer estilo tour: foto de las coreanas + lista de países visitados + “Próxima parada: Lima”.",
                 "Países, fecha y hora de llegada a Perú, lugar, 986 484 513"],
                ["<b>Post 2</b> · Separa tu cupo",
                 "Pieza enfocada en la conversión: “Separa tu cupo con S/ 150”, cupos limitados.",
                 "S/ 150, 24 de noviembre, Hotel Meliá Lima, 986 484 513"],
                ["<b>Video</b> · El tour llega a Lima",
                 "Las coreanas en su tour (recorrido por los países) y su llegada a Lima; cierre con invitación directa.",
                 "Países, llegada a Lima, lugar, S/ 150, 986 484 513 en pantalla"],
            ],
            (38*mm, 72*mm, 60*mm)),
    ]),

    P("Copy sugerido (Post 1)", h3),
    P("“¡El tour llega a Perú! Después de recorrer [PAÍS 1], [PAÍS 2] y [PAÍS 3], la próxima parada es LIMA. "
      "Martes 24 de noviembre · Hotel Meliá Lima, Av. Gral. Felipe Salaverry 2599, San Isidro. "
      "Separa tu cupo con S/ 150. Informes: 986 484 513.”", quote),
    P("Guion sugerido del video (20–30 s)", h3),
    grid_table(
        ["Tiempo", "Escena", "Texto en pantalla"],
        [
            ["0–3 s", "Gancho: las coreanas en un aeropuerto / avión.", "“Nuestra gira continúa…”"],
            ["3–12 s", "Clips de los países visitados (mapa o banderas animadas).", "[PAÍS 1] (visitado) [PAÍS 2] (visitado) [PAÍS 3] (visitado)"],
            ["12–18 s", "Llegada a Lima (aeropuerto, ciudad, hotel).", "“Próxima parada: LIMA · 24 de noviembre · [HORA]”"],
            ["18–25 s", "Las coreanas hablando a cámara invitando al evento.", "“Hotel Meliá Lima · San Isidro”"],
            ["25–30 s", "Cierre con llamado a la acción.", "“Separa tu cupo con S/ 150 · 986 484 513”"],
        ],
        (22*mm, 78*mm, 70*mm)),

    P("4. Datos pendientes por confirmar con el cliente", h2),
    *bullets([
        "Lista exacta de <b>países</b> (y ciudades) donde han estado en el tour.",
        "<b>Hora de llegada a Perú</b> / hora de inicio del evento del 24 de noviembre.",
        "Horario y lugar de la Escuela para Profesores del 23 de noviembre.",
        "Fotografía de las camillas (proporcionada por el cliente o sesión de fotos).",
        "Material de video/foto de las coreanas en su tour (o fecha de grabación).",
        "Método de pago para la separación de S/ 150 (Yape, Plin, transferencia, etc.).",
        "Logo, colores de marca y nombre oficial del evento.",
    ]),

    P("5. Checklist de entregables", h2),
    grid_table(
        ["#", "Entregable", "Fecha del evento", "Estado"],
        [
            ["1", "Post de invitación – Escuela para Profesores (imagen de camillas)", "23 nov", "Pendiente"],
            ["2", "Post 1 – Flyer de gira “Próxima parada: Lima”", "24 nov", "Pendiente"],
            ["3", "Post 2 – “Separa tu cupo con S/ 150”", "24 nov", "Pendiente"],
            ["4", "Video – Las coreanas en su tour y llegada a Lima", "24 nov", "Pendiente"],
            ["5", "Revisión de referencias en la Biblioteca de anuncios de Facebook", "—", "Pendiente"],
        ],
        (10*mm, 100*mm, 30*mm, 30*mm)),
]

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                        topMargin=18*mm, bottomMargin=18*mm,
                        title="Plan de Contenidos – Escuela y Tour Lima", author="Equipo de Marketing")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(os.path.abspath(OUT))
