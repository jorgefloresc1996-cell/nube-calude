// Genera Briefing_Campanas_Marca_Nueva.docx (node generar_briefing.js)
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  WidthType, ShadingType, AlignmentType, BorderStyle, Footer, PageNumber, LevelFormat,
} = require('docx');

const NAVY = '2B3180', BLUE = '4471C4', SOFT = 'EEF2FB', LINE = 'C5CBE3', INK = '22264F';
const W = 9638; // ancho útil A4 con márgenes de 2 cm
const border = { style: BorderStyle.SINGLE, size: 4, color: LINE };
const borders = { top: border, bottom: border, left: border, right: border };
const BOX = '☐';

const p = (text, o = {}) => new Paragraph({
  spacing: { before: o.before ?? 0, after: o.after ?? 80 }, alignment: o.align,
  children: [new TextRun({ text, bold: o.bold, size: o.size ?? 20, color: o.color ?? INK, italics: o.italics })],
});

const sec = (n, title) => new Paragraph({
  spacing: { before: 280, after: 120 },
  shading: { type: ShadingType.CLEAR, fill: NAVY, color: 'auto' },
  children: [new TextRun({ text: `  ${n}. ${title}`, bold: true, color: 'FFFFFF', size: 22 })],
});

const cell = (children, width, fill) => new TableCell({
  borders, width: { size: width, type: WidthType.DXA },
  shading: fill ? { type: ShadingType.CLEAR, fill, color: 'auto' } : undefined,
  margins: { top: 70, bottom: 70, left: 110, right: 110 },
  children: Array.isArray(children) ? children : [children],
});

// Tabla pregunta | respuesta (la columna derecha queda vacía para que el cliente escriba)
function qa(rows, q = 3900) {
  const a = W - q;
  return new Table({
    width: { size: W, type: WidthType.DXA }, columnWidths: [q, a],
    rows: rows.map(([pregunta, ayuda]) => new TableRow({ children: [
      cell([
        new Paragraph({ children: [new TextRun({ text: pregunta, bold: true, size: 19, color: INK })] }),
        ...(ayuda ? [new Paragraph({ children: [new TextRun({ text: ayuda, size: 16, color: '6B6F8A', italics: true })] })] : []),
      ], q, SOFT),
      cell(new Paragraph({ children: [new TextRun({ text: '', size: 20 })] }), a),
    ] })),
  });
}

// Opciones para marcar con X
const checks = (items, cols = 3) => {
  const cw = Math.floor(W / cols), widths = Array(cols).fill(cw);
  widths[cols - 1] = W - cw * (cols - 1);
  const rows = [];
  for (let i = 0; i < items.length; i += cols) {
    rows.push(new TableRow({ children: widths.map((w, j) => cell(
      new Paragraph({ children: [new TextRun({ text: items[i + j] ? `${BOX} ${items[i + j]}` : '', size: 19 })] }), w)) }));
  }
  return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: widths, rows });
};

// Tabla con encabezado
function grid(headers, widths, nRows, firstCol) {
  const head = new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(
    new Paragraph({ children: [new TextRun({ text: h, bold: true, color: 'FFFFFF', size: 18 })] }), widths[i], BLUE)) });
  const body = Array.from({ length: nRows }, (_, r) => new TableRow({ children: widths.map((w, i) => cell(
    new Paragraph({ children: [new TextRun({ text: i === 0 && firstCol ? firstCol[r] : '', size: 19, bold: i === 0 })] }), w,
    i === 0 && firstCol ? SOFT : undefined)) }));
  return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: widths, rows: [head, ...body] });
}

const note = (label, text) => new Paragraph({
  spacing: { before: 100, after: 100 },
  shading: { type: ShadingType.CLEAR, fill: SOFT, color: 'auto' },
  border: { left: { style: BorderStyle.SINGLE, size: 18, color: BLUE, space: 6 } },
  children: [new TextRun({ text: label + ' ', bold: true, size: 18, color: INK }), new TextRun({ text, size: 18 })],
});

const step = (text) => new Paragraph({
  numbering: { reference: 'pasos', level: 0 }, spacing: { after: 40 },
  children: [new TextRun({ text, size: 19 })],
});
const bullet = (text) => new Paragraph({
  numbering: { reference: 'vinetas', level: 0 }, spacing: { after: 40 },
  children: [new TextRun({ text, size: 19 })],
});

const logo = fs.readFileSync(path.join(__dirname, 'assets', 'logo.png'));

const children = [
  new Paragraph({ children: [new ImageRun({ type: 'png', data: logo, transformation: { width: 190, height: 67 } })] }),
  new Paragraph({ spacing: { before: 160, after: 40 }, children: [new TextRun({ text: 'BRIEFING PARA CAMPAÑAS DIGITALES', bold: true, size: 34, color: NAVY })] }),
  p('Marca nueva · Pauta mensual de S/ 1,000 a S/ 2,000', { color: BLUE, bold: true, size: 21, after: 160 }),
  p('Por favor, completa este documento escribiendo en los recuadros en blanco y marcando con una X las opciones que correspondan. Toma unos 15 minutos. Si no sabes alguna respuesta, déjala en blanco y la vemos juntos en la reunión.', { size: 19 }),

  sec(1, 'DATOS DE LA EMPRESA'),
  qa([
    ['Nombre comercial de la marca'],
    ['Razón social y RUC'],
    ['¿A qué se dedica la empresa?', 'Descríbelo en una frase. Ej.: “Clínica dental en Surco especializada en ortodoncia”.'],
    ['Tiempo en el mercado'],
    ['Zonas donde atiende', 'Distritos, ciudades o todo el Perú.'],
    ['Página web'],
    ['Redes sociales (links)', 'Facebook, Instagram, TikTok.'],
    ['WhatsApp de atención'],
    ['Persona de contacto (nombre, cargo y celular)'],
  ]),
  p('Rubro (marca con X):', { bold: true, size: 19, after: 60, before: 120 }),
  checks(['Salud / clínica', 'Belleza / estética', 'Restaurante / comida', 'Tienda / e-commerce', 'Educación / cursos', 'Inmobiliaria / construcción', 'Servicios profesionales', 'Tecnología', 'Otro: ____________']),

  sec(2, 'SERVICIOS O PRODUCTOS A PROMOCIONAR'),
  grid(['#', 'Servicio / producto', 'Precio (S/)', '¿Por qué es importante?'], [500, 4000, 1500, 3638], 3, ['1', '2', '3']),
  note('Recomendación:', 'con esta inversión conviene enfocarse en 1 o máximo 2 servicios (los más rentables o con más demanda). Repartir entre muchos diluye los resultados.'),
  qa([
    ['¿Tienen alguna promoción u oferta para lanzar?', 'Descuento, paquete, primera consulta gratis, delivery gratis, etc.'],
    ['¿Hay alguna fecha o temporada importante en los próximos 3 meses?'],
  ]),

  sec(3, 'OBJETIVO Y PÚBLICO'),
  p('¿Qué quieres lograr con la publicidad? (marca la principal):', { bold: true, size: 19, after: 60 }),
  checks(['Mensajes por WhatsApp', 'Formularios con datos (leads)', 'Ventas en la web', 'Visitas al local', 'Llamadas', 'Dar a conocer la marca']),
  new Paragraph({ spacing: { after: 60 } }),
  qa([
    ['Meta mensual', '¿Cuántos clientes, ventas o contactos quieres al mes?'],
    ['Tu cliente ideal', 'Edad, género, zona y a qué se dedica.'],
    ['¿Qué problema le resuelves?'],
    ['¿Por qué te eligen a ti y no a la competencia?', 'Precio, rapidez, calidad, garantía, ubicación…'],
    ['Menciona 2 o 3 competidores'],
    ['¿Han hecho publicidad antes? ¿Qué resultados tuvieron?'],
    ['¿Quién responderá los mensajes y en qué horario?', 'Responder rápido es clave para que la campaña venda.'],
  ]),

  sec(4, 'PRESUPUESTO'),
  grid(['Concepto', 'Respuesta'], [3900, W - 3900], 3, ['Inversión mensual en pauta (S/ 1,000 – 2,000)', '¿Con qué tarjeta se pagará la pauta? (crédito/débito a nombre de la empresa)', 'Fecha de inicio deseada']),
  note('Cómo distribuiremos la inversión:', 'equivale a S/ 33 – S/ 66 diarios. Canal principal: Meta Ads (Facebook + Instagram). Aproximadamente 70% para captar clientes, 20% para remarketing (personas que ya interactuaron) y 10% para probar anuncios nuevos. Los primeros 7 a 14 días son de aprendizaje del algoritmo. La pauta se paga directamente a Meta y no incluye el servicio de la agencia.'),

  sec(5, 'MATERIAL DE LA MARCA'),
  p('Marca con X lo que puedes enviarnos (por Google Drive o WhatsApp):', { bold: true, size: 19, after: 60 }),
  checks(['Logo en buena calidad', 'Colores / manual de marca', 'Fotos reales del negocio', 'Videos del negocio o servicio', 'Testimonios / reseñas', 'Lista de precios o catálogo']),

  sec(6, 'SOLICITUD DE ACCESOS'),
  p('Para crear y administrar las campañas necesitamos acceso a las cuentas de la marca. Nunca pedimos contraseñas: los accesos se dan como socio o colaborador y pueden retirarse en cualquier momento. Las cuentas siguen siendo 100% de la empresa.', { size: 19 }),
  p('Datos de la agencia para dar los accesos:', { bold: true, size: 19, after: 60 }),
  qa([
    ['Correo de la agencia', 'administracion@tghtechnologysolution.com'],
    ['ID del Business Manager de TGH', 'Te lo enviamos por WhatsApp junto con este documento.'],
  ]),
  new Paragraph({ spacing: { after: 60 } }),
  p('Marca el estado de cada acceso:', { bold: true, size: 19, after: 60 }),
  grid(['Acceso', 'Nivel', '¿Lo tienen?', '¿Acceso dado?'], [4300, 2138, 1600, 1600], 0),
  new Table({
    width: { size: W, type: WidthType.DXA }, columnWidths: [4300, 2138, 1600, 1600],
    rows: [
      ['Business Manager / Portfolio comercial (Meta)', 'Socio', true],
      ['Página de Facebook', 'Control total', true],
      ['Cuenta de Instagram (vinculada a la página)', 'Control total', true],
      ['Cuenta publicitaria de Meta', 'Administrador', true],
      ['Píxel / conjunto de datos de Meta', 'Administrador', true],
      ['WhatsApp Business (número vinculado)', 'Administrador', true],
      ['Google Ads (opcional)', 'Administrador', true],
      ['Google Analytics / Tag Manager (si hay web)', 'Editor', true],
      ['Administrador de la web (si hay web)', 'Editor', true],
    ].map(([a, n]) => new TableRow({ children: [
      cell(new Paragraph({ children: [new TextRun({ text: a, size: 19, bold: true })] }), 4300, SOFT),
      cell(new Paragraph({ children: [new TextRun({ text: n, size: 18 })] }), 2138),
      cell(new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: `${BOX} Sí  ${BOX} No`, size: 18 })] }), 1600),
      cell(new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: `${BOX} Sí`, size: 18 })] }), 1600),
    ] })),
  }),

  p('Cómo darnos acceso en Meta (5 minutos):', { bold: true, size: 20, color: NAVY, after: 60, before: 200 }),
  step('Ingresa a business.facebook.com con la cuenta de Facebook del dueño de la página.'),
  step('Ve a Configuración → Usuarios → Socios → Agregar → “Dar a un socio acceso a tus activos”.'),
  step('Escribe el ID del Business Manager de TGH.'),
  step('Selecciona y activa “Control total” en: Página de Facebook, cuenta de Instagram, cuenta publicitaria, píxel y WhatsApp.'),
  step('Guarda los cambios y avísanos por WhatsApp para confirmar.'),
  note('¿No tienes Business Manager o cuenta publicitaria?', 'No te preocupes. Agendamos una videollamada de 15 minutos y lo creamos juntos a nombre de la empresa.'),

  p('Cómo darnos acceso en Google Ads (opcional):', { bold: true, size: 20, color: NAVY, after: 60, before: 160 }),
  bullet('Herramientas → Acceso y seguridad → botón “+” → agrega el correo de la agencia con nivel Administrador.'),

  sec(7, 'COMENTARIOS ADICIONALES'),
  qa([['¿Algo más que debamos saber?', 'Restricciones, temas a evitar, palabras de la marca, etc.']]),

  new Paragraph({ spacing: { before: 300 }, alignment: AlignmentType.CENTER, children: [
    new TextRun({ text: '¡Gracias! Envía este documento completo a administracion@tghtechnologysolution.com o al WhatsApp 976 224 095.', bold: true, size: 19, color: NAVY }),
  ] }),
];

const doc = new Document({
  creator: 'TGH Technology Solution',
  title: 'Briefing para campañas digitales',
  styles: { default: { document: { run: { font: 'Calibri', size: 20 } } } },
  numbering: { config: [
    { reference: 'pasos', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 400, hanging: 300 } } } }] },
    { reference: 'vinetas', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 400, hanging: 300 } } } }] },
  ] },
  sections: [{
    properties: { page: { margin: { top: 1000, bottom: 1000, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
      new TextRun({ text: 'TGH Technology Solution · 976 224 095 · administracion@tghtechnologysolution.com   |   Pág. ', size: 15, color: '6B6F8A' }),
      new TextRun({ children: [PageNumber.CURRENT], size: 15, color: '6B6F8A' }),
    ] })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = path.join(__dirname, '..', 'Briefing_Campanas_Marca_Nueva.docx');
  fs.writeFileSync(out, buf);
  console.log('OK', out);
});
