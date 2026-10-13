#!/usr/bin/env python3
"""Genera el script de After Effects (.jsx) que construye el proyecto editable.

Lee <paquete>/timeline.json (lo exporta tgh_3_errores.py --exportar-ae) y escribe:
  <paquete>/CONSTRUIR_PROYECTO_TGH.jsx  (ExtendScript ES3, UTF-8 con BOM, literales \\uXXXX)
  <paquete>/LEEME.txt                   (instrucciones para el editor)

El editor abre After Effects 2020 o superior > Archivo > Scripts > Ejecutar archivo de script…
y el script crea la composición completa (capas de texto vivas, keyframes, efectos,
mate de la persona, audio por pistas) y guarda TGH_3_errores.aep junto al script.

Uso: python3 generar_ae.py carpeta_paquete
"""
import json
import math
import os
import sys

ETIQUETAS = dict(fondo=12, fondo_ajuste=5, detras=8, persona=9, ajuste_global=5, frente=2, hud=1, flash=14, audio=7,
                 guia=0)
FUENTES = {
    "Poppins-SemiBold": ["Poppins-SemiBold", "Poppins-Medium", "Montserrat-SemiBold", "Arial-BoldMT"],
    "Poppins-Bold": ["Poppins-Bold", "Montserrat-Bold", "Arial-BoldMT"],
    "Poppins-ExtraBold": ["Poppins-ExtraBold", "Poppins-Black", "Poppins-Bold", "Arial-BoldMT"],
    "DejaVuSansMono": ["DejaVuSansMono", "CourierNewPSMT", "Courier"],
}


# ------------------------------------------------------------ serialización ES3
def js(v):
    """Literal ES3: dict/list/str/num/bool/None. Sin comas finales; no ASCII como \\uXXXX."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        x = float(v)
        if not math.isfinite(x):
            raise ValueError(f"número inválido: {v!r}")
        r = round(x, 5)
        if r == 0:
            r = 0.0
        t = repr(r)
        return t[:-2] if t.endswith(".0") else t
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=True)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(js(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(json.dumps(str(k), ensure_ascii=True) + ": " + js(x) for k, x in v.items()) + "}"
    raise TypeError(type(v))


# ------------------------------------------------------------- preparación
class Generador:
    def __init__(self, raiz):
        self.raiz = raiz
        with open(os.path.join(raiz, "timeline.json"), encoding="utf-8") as fh:
            self.t = json.load(fh)
        self.fps = self.t["fps"]
        self.n_total = int(round(self.t["duracion"] * self.fps))
        self.avisos = []

    def fr(self, t):
        """Segundos → frame entero (los keyframes quedan exactamente en frame)."""
        return int(round(float(t) * self.fps))

    def existe(self, rel):
        if not os.path.exists(os.path.join(self.raiz, rel)):
            raise SystemExit(f"Falta en el paquete: {rel}")
        return rel

    def claves(self, keys, conv=lambda v: v, nombre=""):
        """[(t, v)] → {"f": [frames], "v": [valores]} con frames estrictamente crecientes."""
        fs, vs = [], []
        for t, v in sorted(keys, key=lambda k: k[0]):
            f = self.fr(t)
            if fs and f <= fs[-1]:
                # dos claves en el mismo frame: se conserva la última (la de destino)
                fs.pop()
                vs.pop()
                if fs and f <= fs[-1]:
                    raise SystemExit(f"Claves desordenadas en {nombre}")
            fs.append(max(0, min(f, self.n_total)))
            vs.append(conv(v))
        return {"f": fs, "v": vs}

    def rango(self, c):
        f0, f1 = self.fr(c["inicio"]), self.fr(c["fin"])
        f0 = max(0, f0)
        f1 = min(self.n_total, f1)
        if f1 <= f0:
            f1 = f0 + 1
        return f0, f1

    def capa_js(self, c):
        f0, f1 = self.rango(c)
        d = {"tipo": c["tipo"], "nombre": c["nombre"], "grupo": c["grupo"], "f0": f0, "f1": f1,
             "etiqueta": ETIQUETAS.get(c["grupo"], 0)}
        op_base = c.get("opacidad", 100)
        if c["tipo"] in ("texto", "imagen"):
            d["pos"] = [c["cx"], c["cy"]]
            esc = c.get("escala_base", [1, 1])
            d["kpos"] = self.claves(c.get("kf_pos", []), lambda v: [float(v[0]), float(v[1])], c["nombre"])
            d["kesc"] = self.claves(c.get("kf_escala", []), lambda v: [esc[0] * v, esc[1] * v, 100.0], c["nombre"])
            d["esc"] = [esc[0] * 100, esc[1] * 100, 100.0]
            d["kop"] = self.claves(c.get("kf_opacidad", []), lambda v: v * op_base / 100, c["nombre"])
            d["op"] = op_base
            d["expr_op"] = c.get("expr_opacidad") or ""
        if c["tipo"] == "texto":
            d.update(texto=c["texto"], fuentes=FUENTES[c["fuente"]], tam=c["tam"],
                     color=[x / 255 for x in c["color"]], tracking=c["tracking"], glow=bool(c["glow"]))
        elif c["tipo"] == "imagen":
            d["archivo"] = self.existe(c["archivo"])
        elif c["tipo"] == "tinte":
            d["negro"] = [x / 255 for x in c["negro"]] + [1]
            d["blanco"] = [x / 255 for x in c["blanco"]] + [1]
        elif c["tipo"] == "timecode":
            d.update(fuentes=FUENTES[c["fuente"]], tam=c["tam"], pos=[c["x"], c["y"]], expr=c["expr"])
        elif c["tipo"] == "flash":
            d["kop"] = self.claves(c["kf_opacidad"], float, c["nombre"])
        return d

    def datos(self):
        t = self.t
        orden = ["fondo_ajuste", "detras", "ajuste_global", "frente", "hud", "flash"]
        capas = {g: [self.capa_js(c) for c in t["capas"] if c["grupo"] == g] for g in orden}
        ax, ay = t["ancla_zoom"]
        zoom = self.claves([(k["t"], k["escala"]) for k in t["zoom"]], lambda v: [v, v, 100.0], "zoom")
        zpos = self.claves([(k["t"], k["dy"]) for k in t["zoom"]], lambda v: [ax, ay + v], "zoom_pos")
        sfx = [{"archivo": self.existe(s["archivo"]), "nombre": s["nombre"], "inicio": round(s["inicio"], 4)}
               for s in t["audio"]["sfx"]]
        marcadores = [[0, "GANCHO"]]
        for c in t["capas"]:
            if c["tipo"] == "tinte":
                marcadores.append([self.fr(c["inicio"]), c["nombre"].replace("Fondo_rojo_", "").replace("_", " ")])
            elif c["nombre"] == "REC_blanco_y_negro":
                marcadores.append([self.fr(c["inicio"]), "REC"])
            elif c["nombre"] == "CTA_Comentanos":
                marcadores.append([self.fr(c["inicio"]), "CTA"])
        marcadores.append([self.fr(t["fin_toma"]), "CIERRE TGH"])
        marcadores.sort()
        fp = t["footage"]
        au = t["audio"]
        return {
            "proyecto": t["proyecto"], "ancho": t["ancho"], "alto": t["alto"], "fps": self.fps,
            "n_total": self.n_total, "f_fin_toma": self.fr(t["fin_toma"]),
            "ancla": [ax, ay], "zoom": zoom, "zpos": zpos,
            "footage": {k: (v if k == "original" else self.existe(v)) for k, v in fp.items()},
            "audio": {"voz": self.existe(au["voz"]), "musica": self.existe(au["musica"]),
                      # opcionales: el .jsx los importa solo si están en el paquete
                      "musica_sin_ducking": au["musica_sin_ducking"], "sfx_mezcla": au["sfx_mezcla"],
                      "mezcla": au["mezcla"]},
            "referencia": "07_Referencia/Render_final_referencia.mp4",
            "sfx": sfx, "capas": capas, "marcadores": marcadores,
            "sombra": t["estilo_texto"]["sombra"], "glow": t["estilo_texto"]["glow_amarillo"],
            "etiquetas": ETIQUETAS,
        }

    def escribir(self):
        datos = self.datos()
        codigo = PLANTILLA.replace("/*__DATOS__*/", "var D = " + js(datos) + ";")
        ruta = os.path.join(self.raiz, "CONSTRUIR_PROYECTO_TGH.jsx")
        with open(ruta, "w", encoding="utf-8-sig", newline="\n") as fh:
            fh.write(codigo)
        with open(os.path.join(self.raiz, "LEEME.txt"), "w", encoding="utf-8") as fh:
            fh.write(LEEME)
        return ruta


# ---------------------------------------------------------------- plantilla JSX
PLANTILLA = r"""// CONSTRUIR_PROYECTO_TGH.jsx
// Construye el proyecto editable del reel "3 errores en redes" (TGH Technology Solution).
// After Effects 2020 (17.0) o superior. Archivo > Scripts > Ejecutar archivo de script...
// Generado automaticamente por generar_ae.py a partir de timeline.json. No editar a mano.
(function () {
    /*__DATOS__*/

    var AVISOS = [];
    var FUENTES_FALTANTES = {};
    function aviso(t) { AVISOS.push(t); }
    function F(n) { return n / D.fps; }

    var ROOT = (new File($.fileName)).parent;
    function archivoRel(rel) { return new File(ROOT.fsName + "/" + rel); }

    if (parseFloat(app.version) < 17) {
        alert("Se requiere After Effects 2020 (17.0) o superior.");
        return;
    }

    // ------------------------------------------------------------ utilidades
    function fijarInOut(capa, tIn, tOut) {
        if (!(tOut > tIn)) { throw new Error("outPoint <= inPoint en " + capa.name); }
        if (tIn >= capa.outPoint) {
            capa.outPoint = tOut;
            capa.inPoint = tIn;
        } else {
            capa.inPoint = tIn;
            capa.outPoint = tOut;
        }
    }

    var CACHE = {};
    function importar(rel, carpeta) {
        var f, io, it;
        if (CACHE[rel]) { return CACHE[rel]; }
        f = archivoRel(rel);
        if (!f.exists) { throw new Error("Falta el archivo del paquete: " + f.fsName); }
        io = new ImportOptions(f);
        if (io.canImportAs(ImportAsType.FOOTAGE)) { io.importAs = ImportAsType.FOOTAGE; }
        it = app.project.importFile(io);
        it.parentFolder = carpeta;
        try {
            if (it.mainSource.hasAlpha) { it.mainSource.alphaMode = AlphaMode.STRAIGHT; }
        } catch (eAlfa) {}
        CACHE[rel] = it;
        return it;
    }

    function importarOpcional(rel, carpeta) {
        if (!archivoRel(rel).exists) {
            aviso("Opcional no encontrado (descomprime las partes 4 y 5 si lo quieres): " + rel);
            return null;
        }
        return importar(rel, carpeta);
    }

    function tr(capa, mn) { return capa.property("ADBE Transform Group").property(mn); }

    function claves(prop, k) {
        var i, n, ts = [];
        if (!k || !k.f || k.f.length === 0) { return false; }
        for (i = 0; i < k.f.length; i++) { ts.push(F(k.f[i])); }
        prop.setValuesAtTimes(ts, k.v);
        for (i = 0; i < ts.length; i++) {
            n = prop.nearestKeyIndex(ts[i]);
            prop.setInterpolationTypeAtKey(n, KeyframeInterpolationType.LINEAR, KeyframeInterpolationType.LINEAR);
        }
        return true;
    }

    function agregarEfecto(capa, mn, nombre) {
        var parade = capa.property("ADBE Effect Parade");
        var fx;
        if (!parade.canAddProperty(mn)) {
            aviso("Efecto no disponible: " + mn + " (capa " + capa.name + ")");
            return null;
        }
        fx = parade.addProperty(mn);
        if (nombre) { fx.name = nombre; }
        return fx;
    }

    function setP(fx, mn, valor) {
        var p = null;
        try { p = fx.property(mn); } catch (e0) { p = null; }
        if (p === null || p === undefined) { return false; }
        try {
            p.setValue(valor);
            return true;
        } catch (e1) {
            $.writeln("AVISO " + mn + ": " + e1.toString());
            return false;
        }
    }

    function setColor(fx, mn, rgba) {
        var p = null;
        try { p = fx.property(mn); } catch (e0) { p = null; }
        if (p === null || p === undefined) { return false; }
        if (p.propertyValueType !== PropertyValueType.COLOR) { return false; }
        return setP(fx, mn, rgba);
    }

    function setPct(fx, mn, pct) {
        var p = null, maxV = 100, v = pct;
        try { p = fx.property(mn); } catch (e0) { p = null; }
        if (p === null || p === undefined) { return false; }
        try { if (p.hasMax) { maxV = p.maxValue; } } catch (e1) {}
        if (maxV <= 1.0001) {
            v = pct / 100;
        } else if (maxV > 254 && maxV < 256) {
            v = pct * 2.55;
        }
        return setP(fx, mn, v);
    }

    function textoProp(capa) { return capa.property("ADBE Text Properties").property("ADBE Text Document"); }

    function fuenteInstalada(ps) {
        var lista;
        try {
            if (app.fonts === undefined || app.fonts === null) { return null; }
            lista = app.fonts.getFontsByPostScriptName(ps);
            if (!lista || lista.length === 0) { return false; }
            return !lista[0].isSubstitute;
        } catch (e) {
            return null;
        }
    }

    function fuenteAplicada(capa, ps) {
        var td = textoProp(capa).value;
        if (td.font !== ps) { return false; }
        try {
            if (td.fontObject && td.fontObject.isSubstitute) { return false; }
        } catch (e) {}
        return true;
    }

    function aplicarFuente(capa, candidatas) {
        var i, ok, td, prop = textoProp(capa);
        for (i = 0; i < candidatas.length; i++) {
            ok = fuenteInstalada(candidatas[i]);
            if (ok === false) { continue; }
            td = prop.value;
            td.font = candidatas[i];
            prop.setValue(td);
            if (fuenteAplicada(capa, candidatas[i])) {
                if (i > 0) { FUENTES_FALTANTES[candidatas[0]] = candidatas[i]; }
                return candidatas[i];
            }
        }
        FUENTES_FALTANTES[candidatas[0]] = textoProp(capa).value.font;
        return textoProp(capa).value.font;
    }

    function sombraTexto(capa) {
        var s = D.sombra;
        var ds = agregarEfecto(capa, "ADBE Drop Shadow", "Sombra");
        if (ds === null) { return; }
        setColor(ds, "ADBE Drop Shadow-0001", [s.color[0] / 255, s.color[1] / 255, s.color[2] / 255, 1]);
        setPct(ds, "ADBE Drop Shadow-0002", s.opacidad_pct);
        setP(ds, "ADBE Drop Shadow-0003", s.direccion);
        setP(ds, "ADBE Drop Shadow-0004", s.distancia);
        setP(ds, "ADBE Drop Shadow-0005", s.suavidad);
    }

    function glowAmarillo(capa) {
        // Glow con "colores originales" sobre texto ya amarillo (sin propiedades dudosas).
        var g = D.glow;
        var gl = agregarEfecto(capa, "ADBE Glo2", "Glow amarillo");
        if (gl === null) { return; }
        setPct(gl, "ADBE Glo2-0002", g.umbral_pct);
        setP(gl, "ADBE Glo2-0003", g.radio);
        setP(gl, "ADBE Glo2-0004", g.intensidad);
    }

    function transformar(capa, c) {
        if (!claves(tr(capa, "ADBE Position"), c.kpos)) { tr(capa, "ADBE Position").setValue(c.pos); }
        if (!claves(tr(capa, "ADBE Scale"), c.kesc)) { tr(capa, "ADBE Scale").setValue(c.esc); }
        if (!claves(tr(capa, "ADBE Opacity"), c.kop)) { tr(capa, "ADBE Opacity").setValue(c.op); }
        if (c.expr_op !== "") { tr(capa, "ADBE Opacity").expression = c.expr_op; }
    }

    function base(capa, c) {
        capa.name = c.nombre;
        capa.label = c.etiqueta;
        capa.startTime = 0;
        fijarInOut(capa, F(c.f0), F(c.f1));
    }

    // ------------------------------------------------------------ constructores
    function crearTexto(comp, c) {
        var capa = comp.layers.addText(c.texto);
        var prop, td, r;
        base(capa, c);
        prop = textoProp(capa);
        td = prop.value;
        td.resetCharStyle();
        td.fontSize = c.tam;
        td.applyFill = true;
        td.fillColor = c.color;
        td.applyStroke = false;
        td.tracking = c.tracking;
        td.justification = ParagraphJustification.CENTER_JUSTIFY;
        td.text = c.texto;
        prop.setValue(td);
        aplicarFuente(capa, c.fuentes);
        // ancla en el centro real del texto: la posicion es el centro de la tinta
        r = capa.sourceRectAtTime(capa.inPoint, false);
        tr(capa, "ADBE Anchor Point").setValue([r.left + r.width / 2, r.top + r.height / 2]);
        if (c.glow) { glowAmarillo(capa); }
        sombraTexto(capa);
        transformar(capa, c);
        return capa;
    }

    function crearImagen(comp, c, carpeta) {
        var capa = comp.layers.add(importar(c.archivo, carpeta), D.n_total / D.fps);
        base(capa, c);
        transformar(capa, c);
        return capa;
    }

    function crearAjuste(comp, c, nombreSolido) {
        var capa = comp.layers.addSolid([1, 1, 1], nombreSolido, D.ancho, D.alto, 1, D.n_total / D.fps);
        capa.adjustmentLayer = true;
        base(capa, c);
        return capa;
    }

    function crearTinte(comp, c, carpeta) {
        var capa = crearAjuste(comp, c, "Ajuste fondo rojo");
        var fx = agregarEfecto(capa, "ADBE Tint", "Fondo rojo");
        capa.source.parentFolder = carpeta;
        capa.comment = "Tine de rojo solo el fondo (la persona va encima, recortada con el mate).";
        if (fx !== null) {
            setColor(fx, "ADBE Tint-0001", c.negro);
            setColor(fx, "ADBE Tint-0002", c.blanco);
            setP(fx, "ADBE Tint-0003", 100);
        }
        return capa;
    }

    function crearByN(comp, c, carpeta) {
        var capa = crearAjuste(comp, c, "Ajuste blanco y negro");
        capa.source.parentFolder = carpeta;
        agregarEfecto(capa, "ADBE Black&White", "Blanco y negro (REC)");
        return capa;
    }

    function crearTimecode(comp, c) {
        var capa = comp.layers.addText("01:34:37:00");
        var prop = textoProp(capa), td = prop.value;
        base(capa, c);
        td.resetCharStyle();
        td.fontSize = c.tam;
        td.applyFill = true;
        td.fillColor = [1, 1, 1];
        td.applyStroke = false;
        td.justification = ParagraphJustification.LEFT_JUSTIFY;
        prop.setValue(td);
        aplicarFuente(capa, c.fuentes);
        tr(capa, "ADBE Anchor Point").setValue([0, 0]);
        tr(capa, "ADBE Position").setValue(c.pos);
        prop.expression = c.expr;
        return capa;
    }

    function crearFlash(comp, c, carpeta) {
        var capa = comp.layers.addSolid([1, 1, 1], "Flash blanco", D.ancho, D.alto, 1, D.n_total / D.fps);
        base(capa, c);
        capa.source.parentFolder = carpeta;
        claves(tr(capa, "ADBE Opacity"), c.kop);
        capa.comment = "Destello blanco en cada corte (keyframes de opacidad).";
        return capa;
    }

    function crearGrupo(comp, lista, carpetaGraf, carpetaSolidos) {
        var i, c;
        for (i = 0; i < lista.length; i++) {
            c = lista[i];
            if (c.tipo === "texto") {
                crearTexto(comp, c);
            } else if (c.tipo === "imagen") {
                crearImagen(comp, c, carpetaGraf);
            } else if (c.tipo === "tinte") {
                crearTinte(comp, c, carpetaSolidos);
            } else if (c.tipo === "byn") {
                crearByN(comp, c, carpetaSolidos);
            } else if (c.tipo === "timecode") {
                crearTimecode(comp, c);
            } else if (c.tipo === "flash") {
                crearFlash(comp, c, carpetaSolidos);
            }
        }
    }

    function zoomToma(capa) {
        tr(capa, "ADBE Anchor Point").setValue(D.ancla);
        claves(tr(capa, "ADBE Position"), D.zpos);
        claves(tr(capa, "ADBE Scale"), D.zoom);
    }

    function aplicarMate(capa, mate, tipo) {
        mate.moveBefore(capa);
        if (parseFloat(app.version) >= 23 && capa.setTrackMatte !== undefined) {
            capa.setTrackMatte(mate, tipo);
        } else {
            capa.trackMatteType = tipo;
        }
        mate.enabled = false;
    }

    // ------------------------------------------------------------ construccion
    function construir() {
        var i, s, capa, mv;
        var fComps = app.project.items.addFolder("01_Comps");
        var fFoot = app.project.items.addFolder("02_Footage");
        var fAudio = app.project.items.addFolder("03_Audio");
        var fSfx = fAudio.items.addFolder("SFX");
        var fGraf = app.project.items.addFolder("04_Graficos");
        var fMates = app.project.items.addFolder("05_Mates");
        var fSolidos = fGraf.items.addFolder("Solidos_y_ajustes");
        var fRef = app.project.items.addFolder("07_Referencia");
        var dur = D.n_total / D.fps;
        var finToma = F(D.f_fin_toma);

        var iToma = importar(D.footage.toma, fFoot);
        var iMate = importar(D.footage.mate, fMates);
        var iCierre = importar(D.footage.cierre, fFoot);
        importarOpcional(D.footage.original, fFoot);
        var iVoz = importar(D.audio.voz, fAudio);
        var iMusica = importar(D.audio.musica, fAudio);
        importarOpcional(D.audio.musica_sin_ducking, fAudio);
        importarOpcional(D.audio.sfx_mezcla, fAudio);
        var iMezcla = importarOpcional(D.audio.mezcla, fAudio);
        var iRef = importarOpcional(D.referencia, fRef);

        // Precomp de efectos de sonido (cada SFX en su capa y su tiempo).
        var compSfx = fComps.items.addComp("SFX_TGH (efectos de sonido)", D.ancho, D.alto, 1, dur, D.fps);
        for (i = 0; i < D.sfx.length; i++) {
            s = D.sfx[i];
            capa = compSfx.layers.add(importar(s.archivo, fSfx));
            capa.startTime = s.inicio;
            capa.name = s.nombre;
            capa.label = D.etiquetas.audio;
        }

        var comp = fComps.items.addComp(D.proyecto + "_FINAL", D.ancho, D.alto, 1, dur, D.fps);
        comp.bgColor = [0, 0, 0];

        // Capas de abajo hacia arriba (cada capa nueva entra arriba de todo).
        if (iRef !== null) {
            capa = comp.layers.add(iRef);
            capa.name = "GUIA render final (apagada)";
            capa.startTime = 0;
            capa.enabled = false;
            if (capa.hasAudio) { capa.audioEnabled = false; }
            try { capa.guideLayer = true; } catch (eG) {}
            capa.label = D.etiquetas.guia;
        }

        if (iMezcla !== null) {
            capa = comp.layers.add(iMezcla);
            capa.name = "AUDIO Mezcla final (referencia, apagada)";
            capa.startTime = 0;
            capa.audioEnabled = false;
            capa.label = D.etiquetas.audio;
        }

        capa = comp.layers.add(compSfx);
        capa.name = "AUDIO Efectos de sonido";
        capa.startTime = 0;
        capa.label = D.etiquetas.audio;

        capa = comp.layers.add(iMusica);
        capa.name = "AUDIO Musica TGH (con ducking)";
        capa.startTime = 0;
        capa.label = D.etiquetas.audio;

        capa = comp.layers.add(iVoz);
        capa.name = "AUDIO Voz limpia";
        capa.startTime = 0;
        capa.label = D.etiquetas.audio;

        var fondo = comp.layers.add(iToma);
        fondo.name = "FONDO Toma con color";
        fondo.startTime = 0;
        fijarInOut(fondo, 0, finToma);
        if (fondo.hasAudio) { fondo.audioEnabled = false; }
        fondo.label = D.etiquetas.fondo;
        zoomToma(fondo);

        crearGrupo(comp, D.capas.fondo_ajuste, fGraf, fSolidos);
        crearGrupo(comp, D.capas.detras, fGraf, fSolidos);

        var persona = comp.layers.add(iToma);
        persona.name = "PERSONA (recorte con mate)";
        persona.startTime = 0;
        fijarInOut(persona, 0, finToma);
        if (persona.hasAudio) { persona.audioEnabled = false; }
        persona.label = D.etiquetas.persona;
        persona.comment = "Copia de la toma recortada con el mate: va encima de los textos y capturas de atras.";
        zoomToma(persona);

        var mate = comp.layers.add(iMate);
        mate.name = "MATE persona (luma)";
        mate.startTime = 0;
        fijarInOut(mate, 0, finToma);
        if (mate.hasAudio) { mate.audioEnabled = false; }
        mate.label = D.etiquetas.persona;
        zoomToma(mate);

        crearGrupo(comp, D.capas.ajuste_global, fGraf, fSolidos);
        crearGrupo(comp, D.capas.frente, fGraf, fSolidos);
        crearGrupo(comp, D.capas.hud, fGraf, fSolidos);

        capa = comp.layers.add(iCierre);
        capa.name = "CIERRE tarjeta TGH";
        capa.startTime = finToma;
        if (capa.hasAudio) { capa.audioEnabled = false; }
        capa.label = D.etiquetas.fondo;

        crearGrupo(comp, D.capas.flash, fGraf, fSolidos);

        // Mate al final, cuando el orden de capas ya no cambia.
        aplicarMate(persona, mate, TrackMatteType.LUMA);

        for (i = 0; i < D.marcadores.length; i++) {
            mv = new MarkerValue(D.marcadores[i][1]);
            comp.markerProperty.setValueAtTime(F(D.marcadores[i][0]), mv);
        }
        comp.workAreaStart = 0;
        comp.workAreaDuration = dur;
        return comp;
    }

    // ------------------------------------------------------------ ejecucion
    var faltaPoppins = fuenteInstalada("Poppins-Bold");
    if (faltaPoppins === false) {
        if (!confirm("La fuente Poppins no esta instalada.\rInstala los archivos de la carpeta 06_Fuentes, reinicia After Effects y vuelve a ejecutar el script.\r\rContinuar igual (con fuente de respaldo)?")) {
            return;
        }
    }
    if (app.project && app.project.numItems > 0) {
        if (app.newProject() === null) { return; }
    }
    var comp = null;
    app.beginSuppressDialogs();
    app.beginUndoGroup("Construir reel TGH");
    try {
        comp = construir();
    } catch (err) {
        aviso("ERROR (linea " + err.line + "): " + err.toString());
    } finally {
        app.endUndoGroup();
        app.endSuppressDialogs(false);
    }
    var k, faltantes = [];
    for (k in FUENTES_FALTANTES) {
        if (FUENTES_FALTANTES.hasOwnProperty(k)) { faltantes.push(k + " -> " + FUENTES_FALTANTES[k]); }
    }
    if (faltantes.length > 0) {
        aviso("Fuentes reemplazadas (instala 06_Fuentes y vuelve a ejecutar): " + faltantes.join(", "));
    }
    if (comp !== null) {
        comp.openInViewer();
        try {
            app.project.save(new File(ROOT.fsName + "/TGH_3_errores.aep"));
            aviso("Proyecto guardado: TGH_3_errores.aep");
        } catch (eSave) {
            aviso("No se pudo guardar automaticamente (" + eSave.toString() + "). Guarda con Archivo > Guardar como.");
        }
        aviso("Listo: composicion " + comp.name + " (" + comp.numLayers + " capas).");
    }
    alert(AVISOS.join("\r"));
})();
"""

LEEME = """PROYECTO AFTER EFFECTS — Reel "3 errores en redes" (TGH Technology Solution)
==========================================================================

CÓMO ABRIRLO (2 minutos)
1. Descomprime el ZIP (si lo recibiste en varias partes, descomprímelas todas en la MISMA carpeta
   y acepta combinar carpetas). No cambies los nombres de las subcarpetas.
   Los archivos opcionales (toma original, render de referencia, mezclas) pueden no venir:
   el script funciona igual y solo avisa.
2. Instala las fuentes de 06_Fuentes (Poppins SemiBold, Bold, ExtraBold y DejaVu Sans Mono).
   Si After Effects estaba abierto, ciérralo y vuelve a abrirlo.
3. After Effects 2020 o superior > Archivo > Scripts > Ejecutar archivo de script…
   (en algunas versiones en español: "Secuencias de comandos") y elige CONSTRUIR_PROYECTO_TGH.jsx
4. El script crea la composición "TGH_3_errores_en_redes_FINAL" y guarda TGH_3_errores.aep en esta
   misma carpeta. A partir de ahí trabaja con el .aep.
   (Si aparece un aviso sobre permisos: Preferencias > Scripts y expresiones > activar
   "Permitir que los scripts escriban archivos y accedan a la red".)

QUÉ CONTIENE LA COMPOSICIÓN (de abajo hacia arriba)
- AUDIO: Voz limpia, Música TGH (con ducking), Efectos de sonido (precomp con cada SFX en su capa)
  y la Mezcla final de referencia (apagada).
- FONDO Toma con color: la toma con corrección de color y keyframes de zoom/latigazo en cada corte.
- Degradados superiores y "Fondo rojo" (capas de ajuste Tint) que solo afectan al fondo.
- Capas "de atrás": palabras grandes (3 ERRORES, POCO PROFESIONALES, SATURAR...), ERROR 1/2/3 x3
  y capturas con marco blanco.
- PERSONA (recorte con mate) + MATE persona (luma): la persona recortada va encima de lo anterior,
  por eso los textos grandes y capturas quedan DETRÁS de ella.
- Capa de ajuste blanco y negro (efecto cámara REC).
- Capas "de adelante": subtítulos en dos niveles (texto vivo, Poppins), stickers y pastillas.
- Interfaz REC (PNG + punto parpadeante + código de tiempo por expresión).
- CIERRE tarjeta TGH y Flash blanco (destellos en los cortes).
- Marcadores de composición: GANCHO, ERROR 1/2/3, REC, CTA, CIERRE TGH.

DATOS DE ESTILO
- Tipografía: Poppins (SemiBold línea chica, Bold palabras, ExtraBold CTA). Tracking -50/-60.
- Colores: amarillo #FCFC00 (con Glow), blanco, azul TGH #3B00EF, verde #25D067, rojo #F03635.
- Sombra de texto: Drop Shadow negro 80 %, dirección 180°, distancia 7, suavidad 22.

CARPETAS
02_Footage   Toma_con_color.mp4 (usada), Toma_original.mp4 (sin color, con audio original)
             y Cierre_TGH.mp4
03_Audio     Voz_limpia.wav, Musica_TGH_con_ducking.wav, Musica_TGH_sin_ducking.wav,
             SFX_mezcla.wav, Mezcla_final.wav y SFX/ (cada efecto por separado, 24 bit / 48 kHz)
04_Graficos  PNG con transparencia (capturas, stickers, pastillas, degradado, interfaz REC)
05_Mates     Mate_persona.mp4 (blanco = persona)
06_Fuentes   Poppins (licencia OFL) y DejaVu Sans Mono
07_Referencia Render_final_referencia.mp4 (cómo debe verse; también está como capa guía)

NOTAS
- La música es original (compuesta por código): se puede usar sin problemas de derechos.
  Para cambiarla, reemplaza "AUDIO Musica TGH" y ajusta su nivel (-12 a -18 dB bajo la voz).
- Exporta en H.264, 1080x1920, 30 fps, audio AAC 48 kHz; normaliza a -14 LUFS para redes.
- Si cambias el orden de capas, deja "MATE persona (luma)" justo encima de "PERSONA".
"""


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    ruta = Generador(sys.argv[1]).escribir()
    print("✔", ruta)


if __name__ == "__main__":
    main()
