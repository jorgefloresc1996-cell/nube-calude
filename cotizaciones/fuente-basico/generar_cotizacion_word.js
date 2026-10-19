// Genera Cotizacion_Paquete_Basico_Marketing_Digital.docx (node generar_cotizacion_word.js)
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  WidthType, ShadingType, AlignmentType, BorderStyle, VerticalAlign, Footer, Header,
} = require('docx');

const NAVY = '2B3180', BLUE = '4471C4', SOFT = 'EEF2FB', LINE = 'D9DEF0', INK = '22264F', TXT = '3B3F5C', GREEN = '27A84A', MUTED = '6B6F8A';
const W = 9638; // ancho útil A4 con márgenes de 2 cm
const b = { style: BorderStyle.SINGLE, size: 4, color: LINE };
const borders = { top: b, bottom: b, left: b, right: b };
const none = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const noBorders = { top: none, bottom: none, left: none, right: none };

const run = (text, o = {}) => new TextRun({ text, bold: o.bold, size: o.size ?? 20, color: o.color ?? TXT, italics: o.italics });
const par = (runs, o = {}) => new Paragraph({
  alignment: o.align, spacing: { before: o.before ?? 0, after: o.after ?? 80 },
  children: Array.isArray(runs) ? runs : [runs],
});
const cell = (children, width, o = {}) => new TableCell({
  borders: o.borders ?? borders, width: { size: width, type: WidthType.DXA },
  shading: o.fill ? { type: ShadingType.CLEAR, fill: o.fill, color: 'auto' } : undefined,
  verticalAlign: o.v ?? VerticalAlign.CENTER, rowSpan: o.rowSpan, columnSpan: o.span,
  margins: { top: o.pad ?? 30, bottom: o.pad ?? 30, left: 110, right: 110 },
  children: Array.isArray(children) ? children : [children],
});
const table = (widths, rows) => new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: widths, rows });

const sec = (title) => new Paragraph({
  spacing: { before: 160, after: 80 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: LINE, space: 2 } },
  children: [run(title, { bold: true, size: 23, color: INK })],
});

const logo = fs.readFileSync(path.join(__dirname, 'assets', 'logo.png'));

// ---- Datos editables ----
const CLIENTE = 'Marca nueva';
const FECHA = '17/10/2026';
const PRECIO = 950;
const IGV = PRECIO * 0.18;
const soles = (n) => 'S/ ' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// Tabla de alcance (igual a la tabla del paquete)
const AREAS = [
  ['ESTRATEGIA', [['Estrategia orgánica', 'Sí'], ['Cronograma de contenido', 'Sí'], ['Planificación de presupuesto a invertir en publicidad', 'Sí']]],
  ['DISEÑO', [['Portada de Facebook', 'Sí'], ['Concepto creativo y línea gráfica digital', 'Sí']]],
  ['GESTIÓN DE REDES SOCIALES', [['Cantidad de redes sociales a gestionar', '3'], ['Creación de contenido', '8 post'], ['Monitoreo', 'Lun a Vie 8 a.m. a 6 p.m.']]],
  ['PRODUCCIÓN', [['Visitas al cliente', '1 visita'], ['Edición de videos', '8 videos'], ['Horarios de grabación', 'Lun a Vie 8 a.m. a 6 p.m. y Sáb 9 a.m. a 1 p.m.']]],
  ['PUBLICIDAD PAGADA', [['Propuesta de estrategia de publicidad pagada', 'Sí (cliente envía los recursos)'], ['Ejecución de campañas', 'Ilimitadas'], ['Reporte de campañas', 'Sí']]],
  ['REPORTE', [['Reporte de cumplimiento', 'Mensual']]],
];
const AW = [2400, 4338, 2900];
const alcanceRows = [
  new TableRow({ tableHeader: true, children: ['ÁREA', 'DETALLE', 'PAQUETE BÁSICO'].map((h, i) =>
    cell(par(run(h, { bold: true, color: 'FFFFFF', size: 19 }), { align: AlignmentType.CENTER, after: 0 }), AW[i], { fill: NAVY })) }),
];
for (const [area, items] of AREAS) {
  items.forEach(([det, val], i) => {
    const cells = [];
    if (i === 0) cells.push(cell(par(run(area, { bold: true, size: 18, color: INK }), { align: AlignmentType.CENTER, after: 0 }), AW[0], { fill: SOFT, rowSpan: items.length }));
    cells.push(cell(par(run(det, { size: 19 }), { after: 0 }), AW[1]));
    cells.push(cell(par(run(val, { size: 19, bold: true, color: NAVY }), { align: AlignmentType.CENTER, after: 0 }), AW[2]));
    alcanceRows.push(new TableRow({ children: cells }));
  });
}

// Pasos "nos encargamos de todo"
const PASOS = [
  ['1. DISEÑAMOS', 'Línea gráfica y piezas de la marca'],
  ['2. GRABAMOS', 'Visitamos tu negocio y producimos'],
  ['3. EDITAMOS', '8 videos listos para redes'],
  ['4. PUBLICAMOS', '8 contenidos en 3 redes'],
  ['5. LANZAMOS', 'Campañas en Meta que generan clientes'],
];
const PW = Array(5).fill(Math.floor(W / 5)); PW[4] = W - PW[0] * 4;
const pasoBorder = { top: { style: BorderStyle.SINGLE, size: 18, color: NAVY }, bottom: { style: BorderStyle.SINGLE, size: 4, color: 'FFFFFF' }, left: { style: BorderStyle.SINGLE, size: 12, color: 'FFFFFF' }, right: { style: BorderStyle.SINGLE, size: 12, color: 'FFFFFF' } };

const EQUIPO = [['1', 'Coordinador de Marketing'], ['1', 'Trafficker Digital'], ['2', 'Comunicadores Audiovisuales'], ['1', 'Diseñador(a) Gráfico(a)'], ['1', 'Community Manager']];

const IW = [6438, 3200];
const fila = (label, sub, val, color, fill) => new TableRow({ children: [
  cell([par(run(label, { bold: true, size: 20, color: fill ? 'FFFFFF' : INK }), { after: 0 }), ...(sub ? [par(run(sub, { size: 16, color: MUTED }), { after: 0 })] : [])], IW[0], { fill }),
  cell(par(run(val, { bold: true, size: 24, color }), { align: AlignmentType.RIGHT, after: 0 }), IW[1], { fill }),
] });

const children = [
  par(run('PROPUESTA SERVICIO DE MARKETING DIGITAL', { bold: true, size: 34, color: NAVY }), { align: AlignmentType.CENTER, before: 0, after: 40 }),
  par(run('COMMUNITY MANAGER · PAQUETE BÁSICO', { bold: true, size: 20, color: BLUE }), { align: AlignmentType.CENTER, after: 140 }),

  table([4300, 2400, 2938], [new TableRow({ children: [['CLIENTE', CLIENTE, 4300], ['FECHA', FECHA, 2400], ['MODALIDAD', 'Servicio mensual', 2938]].map(([k, v, w]) =>
    cell([par(run(k, { bold: true, size: 15, color: BLUE }), { after: 20 }), par(run(v, { bold: true, size: 21, color: INK }), { after: 0 })], w)) })]),

  sec('NOS ENCARGAMOS DE TODO'),
  par([
    run('Tu marca no necesita diseñar, grabar ni publicar: nuestro equipo hace la '),
    run('gestión completa del contenido', { bold: true, color: INK }),
    run(' y además '), run('lanza y optimiza tus campañas de publicidad pagada', { bold: true, color: INK }),
    run('. Tú solo apruebas el contenido y atiendes a los clientes que llegan.'),
  ], { after: 120 }),
  table(PW, [new TableRow({ children: PASOS.map(([t, d], i) => cell([
    par(run(t, { bold: true, size: 18, color: NAVY }), { align: AlignmentType.CENTER, after: 20 }),
    par(run(d, { size: 16 }), { align: AlignmentType.CENTER, after: 0 }),
  ], PW[i], { fill: SOFT, borders: pasoBorder, pad: 50 })) })]),

  sec('¿QUÉ INCLUYE?'),
  table(AW, alcanceRows),

  sec('EQUIPO DEDICADO A LA MARCA'),
  table(PW, [new TableRow({ children: EQUIPO.map(([n, r], i) => cell([
    par(run(n, { bold: true, size: 26, color: NAVY }), { align: AlignmentType.CENTER, after: 0 }),
    par(run(r, { size: 16 }), { align: AlignmentType.CENTER, after: 0 }),
  ], PW[i], { fill: SOFT, borders: pasoBorder, pad: 60 })) })]),

  sec('INVERSIÓN MENSUAL'),
  table(IW, [
    fila('Paquete básico', 'Precio sin IGV', soles(PRECIO), GREEN),
    fila('IGV (18%)', null, soles(IGV), NAVY),
    fila('Total mensual con IGV', null, soles(PRECIO + IGV), 'FFFFFF', NAVY),
  ]),
  new Paragraph({
    spacing: { before: 120, after: 60 },
    shading: { type: ShadingType.CLEAR, fill: SOFT, color: 'auto' },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: BLUE, space: 6 } },
    children: [run('*No incluye ', { bold: true, size: 18, color: INK }), run('el presupuesto de pauta (pagado directamente a Meta/TikTok). El cliente envía los recursos para la publicidad pagada.', { size: 18 })],
  }),
  par([run('Forma de pago: ', { bold: true, size: 19, color: INK }), run('100% adelantado antes del inicio del servicio.', { size: 19 })], { after: 40 }),
  par(run('Precios en soles · Válida 15 días', { size: 16, color: MUTED, italics: true }), { align: AlignmentType.RIGHT }),
];

const doc = new Document({
  creator: 'TGH Technology Solution',
  title: 'Cotización Paquete Básico · Marketing Digital',
  styles: { default: { document: { run: { font: 'Calibri', size: 20 } } } },
  sections: [{
    properties: { page: { margin: { top: 1350, bottom: 1000, left: 1134, right: 1134, header: 350 } } },
    headers: { default: new Header({ children: [new Paragraph({ children: [new ImageRun({ type: 'png', data: logo, transformation: { width: 170, height: 60 } })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      shading: { type: ShadingType.CLEAR, fill: NAVY, color: 'auto' },
      children: [run('  976 - 224 - 095   ·   administracion@tghtechnologysolution.com  ', { bold: true, size: 19, color: 'FFFFFF' })],
    })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = path.join(__dirname, '..', 'Cotizacion_Paquete_Basico_Marketing_Digital.docx');
  fs.writeFileSync(out, buf);
  console.log('OK', out);
});
