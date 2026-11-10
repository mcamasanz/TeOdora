# -*- coding: utf-8 -*-
"""Las imágenes del informe, de la app misma: los mapas de una ventana principal oculta (el resultado, el relieve, los usos, los edificios y
los lugares, en la zona de cálculo y alrededor de la planta), los visores 3D de los edificios y de los focos, y lo que dice la ficha de cada
foco. Así el informe se ve como la app.

Qt se carga al usarlo, no al importar esto (`teodors.gui` es lo único que lo carga al importarse).
"""
import json
import time
from pathlib import Path

from teodors.comun import registro
from teodors.operacion import focos as F, penacho_mapa, simulacion as S

log = registro.get("writer")

# sin los mandos del mapa (zoom, capas, coordenadas, avisos)
SIN_MANDOS_JS = ("var s=document.createElement('style');s.textContent='.leaflet-control-zoom,.leaflet-control-layers,.mapa-coords,.mapa-toast"
                 "{display:none!important}';document.head.appendChild(s);")
# lo que aún se está cargando: teselas del fondo e imágenes de las capas
CARGANDO_JS = ("(function(){var n=0;document.querySelectorAll('img.leaflet-tile').forEach(function(i){if(!i.classList.contains('leaflet-tile-loaded'))"
               "n++;});document.querySelectorAll('img.leaflet-image-layer').forEach(function(i){if(!i.complete)n++;});return n;})()")
NIVELES_ENTORNO = 3                       # alrededor de la planta: la vista de la planta, 3 niveles de zoom más lejos
ESPERA_VIENTO_S = 180.0                   # lo más que se espera al viento de un día
# la vista del mapa: leerla ([lat, lon, zoom]) y ponerla, para que las dos situaciones se vean igual; y acercar un nivel más
_MAPA_JS = "(function(){for(var k in window){try{var m=window[k];if(m instanceof L.Map){%s}}catch(e){}}return null;})()"
VISTA_JS = _MAPA_JS % "var c=m.getCenter();return c.lat+','+c.lng+','+m.getZoom();"          # en texto: una lista de JS no llega a Python
ACERCAR_JS = _MAPA_JS % "m.setZoom(m.getZoom()+1,{animate:false});return 1;"
FUENTE_SVG = 'font-family="Segoe UI, Arial, sans-serif"' 
# las variables de color del estilo de la app, en las rosas que van al informe como imagen (fuera de la app no las hay)
COLORES_ROSA = {"var(--apagado)": "#c3cec7", "var(--tenue)": "#6b7a72", "var(--borde_fuerte)": "#a9b5ae", "var(--superficie)": "#ffffff",
                "var(--texto)": "#1d2723"}
# el mapa de las estaciones: sin los pueblos ni las industrias; las estaciones, en grande; y el rombo de la celda del ERA5
SOLO_ESTACIONES_JS = (
    "var s=document.createElement('style');s.id='solo-estaciones';s.textContent='"
    ".awesome-marker,.awesome-marker-shadow,.icono-industrial{display:none!important}"
    ".mapa-est .ico{width:46px!important;height:46px!important;margin:-9px 0 0 -9px;border-width:3px!important;border-radius:11px!important}"
    ".mapa-est .ico svg{width:30px;height:30px}"
    ".mapa-est .cod{left:42px!important;top:-1px!important;font-size:19px!important;font-weight:700!important;line-height:26px!important;"
    "padding:0 8px!important;border-radius:7px!important;box-shadow:0 1px 4px rgba(0,0,0,.25)}"
    ".era5-celda{background:none;border:none}"
    ".era5-celda .rombo{width:22px;height:22px;box-sizing:border-box;background:#fff;border:4px solid #7c4dbd;transform:rotate(45deg);"
    "box-shadow:0 1px 5px rgba(0,0,0,.35)}"
    ".era5-celda .cod{position:absolute;left:30px;top:-3px;background:rgba(255,255,255,.92);color:#4b2d7f;font:700 17px Segoe UI,Arial,"
    "sans-serif;padding:0 7px;border-radius:6px;line-height:26px;white-space:nowrap}';document.head.appendChild(s);")
ESPERA_MAX_S = 25.0                       # lo más que se espera a que carguen las teselas de una vista
CALIDAD_JPG = 88                          # los mapas y los visores, en JPEG: el PDF, de ~27 MB a unos pocos
_en_marcha = []                           # las capturas que trabajan: Qt no retiene el objeto de una llamada pendiente, y se perdería


def _alejar_js(n):
    return ("for(var i=0;i<%d;i++){setTimeout(function(){var b=document.querySelector('.leaflet-control-zoom-out');if(b){b.click();}},300+i*450);}" % n)


def capa_principal(d):
    """La capa del mapa del estadístico principal (el P98 del olor): la de la columna de `d["estadistico"]`."""
    m = d["mag"]
    col = next(c for c in m["columnas"] if c["clave"] == d["estadistico"])
    return next((c for c in m["capas"] if c["id"].endswith("_" + (col["capa"] or "maximo"))), m["capas"][-1])


def visor_foco(f, edificios):
    """El visor 3D de un foco, como en su ficha de la app (`ventana_focos.FichaVista._visor`)."""
    from teodors.gui import focos_graficos as G
    from teodors.gui.focos_graficos import cifra_corta
    from teodors.comun.formato import num as _num
    m = f.get("modelo")
    if m == "punto":
        from teodors.operacion import estela as ES
        w = G.PanelEstela()
        u = f.get("ubicacion") or {}
        try:
            cerca = ES.edificios_cerca(u["x"], u["y"]) if "x" in u else []
        except Exception:                                      # noqa: BLE001 (sin edificios, el visor igual)
            cerca = []
        w.poner(f, cerca, f.get("edificios"), "ok" if cerca else ("sin_edificios" if "x" in u else "sin_punto"))
        return w
    q, a = F.olor_ouE_s(f), F.area_m2(f)
    pila = m == "volumen" and F.clase_volumen(f) == "pila"
    etiqueta = " · ".join(([f"{_num(a, 0)} m²"] if a and (m == "superficie" or pila) else []) + ([f"{cifra_corta(q)} ou_E/s"] if q else []))
    w = G.PanelSuperficie() if m == "superficie" else G.PanelVolumen()
    w.poner(f, edificios, etiqueta)
    return w


def ficha(f):
    """Lo que dice la ficha de un foco en la app: su subtítulo, sus cifras (icono, valor, qué es) y su olor, con de dónde sale."""
    from teodors.gui.ventana_focos import FichaVista, _cifra
    fv = FichaVista(f)
    try:
        cifras = fv.cifras()
    finally:
        fv.deleteLater()
    q, o = F.olor_ouE_s(f), f.get("olor") or {}
    partes = []
    if q is not None:
        if F.olor_medido(f) is not None:
            partes.append(f"olfatometría: {o.get('valor')} {o.get('unidad', '')}".replace("m3", "m³").replace("m2", "m²"))
        else:
            gas = F.gas_dominante(f)[1]
            partes.append(f"estimada por su {F.NOMBRES.get(gas, gas)} (umbral de Nagata)")
        if f.get("modelo") == "superficie" and not (F.olor_medido(f) is not None and o.get("unidad") == "ou_E/(s·m2)"):
            partes.append(_cifra(F.por_m2(f, q), "ou_E/(s·m²)"))
    return {"sub": F.subtitulo(f), "cifras": [list(c) for c in cifras], "olor": _cifra(q, "ou_E/s") if q is not None else "sin emisión de olor",
            "detalle": " · ".join(partes)}


class Capturas:
    """Hace las imágenes en `carpeta` con la ventana principal `ventana` (oculta: fuera de la pantalla), paso a paso con el reloj de Qt, y
    al acabar llama a `al_acabar({"imagenes", "fichas"})`; si falla, a `fallo(mensaje)`."""

    def __init__(self, ventana, d, carpeta, progreso=None, al_acabar=None, fallo=None, comparacion=None):
        self.v, self.d, self.carpeta = ventana, d, Path(carpeta)
        self.comparacion = comparacion                               # la de dos escenarios (`datos.reunir_comparacion`): sus resultados y el cambio
        self.avisa = progreso or (lambda *_: None)
        self.al_acabar, self.fallo = al_acabar, fallo
        self.imagenes, self.fichas = [], {}
        self._gen = None
        self.carpeta.mkdir(parents=True, exist_ok=True)

    def empezar(self):
        _en_marcha.append(self)
        self.avisa(2, "Esperando al mapa…")
        self._gen = self._pasos()
        self._siguiente()

    def _fin(self):
        if self in _en_marcha:
            _en_marcha.remove(self)

    # ── el bucle ──
    def _siguiente(self):
        from PySide6 import QtCore
        try:
            paso = next(self._gen)
        except StopIteration:
            self._fin()
            return
        except Exception as ex:                                      # noqa: BLE001 (se dice y se para)
            import traceback
            log.error("Informe: fallo al hacer las imágenes:\n" + traceback.format_exc())
            self._fin()
            if self.fallo:
                self.fallo(f"{type(ex).__name__}: {ex}")
            return
        if isinstance(paso, tuple):                                  # ("mapa", ms): esperar y luego a que el mapa acabe de cargar
            QtCore.QTimer.singleShot(paso[1], lambda: self._esperar_mapa(time.time(), 0))
        else:
            QtCore.QTimer.singleShot(paso, self._siguiente)

    def _esperar_mapa(self, t0, quietas):
        from PySide6 import QtCore

        def visto(n):
            if (n == 0 and quietas >= 1) or time.time() - t0 > ESPERA_MAX_S:
                QtCore.QTimer.singleShot(350, self._siguiente)
            else:
                QtCore.QTimer.singleShot(300, lambda: self._esperar_mapa(t0, quietas + 1 if n == 0 else 0))
        self.v.mapa.js(CARGANDO_JS, visto)

    # ── las imágenes ──
    def _foto_mapa(self, nombre):
        self.v.mapa.grab().save(str(self.carpeta / f"{nombre}.jpg"), "JPG", CALIDAD_JPG)
        self.imagenes.append(nombre)

    def _foto(self, w, nombre, ancho, alto):
        w.resize(ancho, alto)
        w.grab().save(str(self.carpeta / f"{nombre}.jpg"), "JPG", CALIDAD_JPG)
        self.imagenes.append(nombre)

    def _entorno(self):
        self.v.mapa.ver_planta()
        self.v.mapa.js(_alejar_js(NIVELES_ENTORNO))

    def _rosas(self, me):
        """Las rosas de los vientos de la planta y de las estaciones (como en el mapa de la app: `mapa_web.rosa_svg`) y su leyenda, en SVG."""
        from teodors.comun.formato import num as _num
        from teodors.gui import mapa_web as MW

        def guarda(nombre, svg):
            for a, b in COLORES_ROSA.items():
                svg = svg.replace(a, b)
            svg = svg.replace("<svg ", f"<svg {FUENTE_SVG} ", 1)
            (self.carpeta / f"{nombre}.svg").write_text(svg, encoding="utf-8")
            self.imagenes.append(nombre)
        p = me["planta"]
        guarda("rosa_planta", MW.rosa_svg(p["rosa"], p["clases"], lado=260))
        for s in (me.get("estaciones") or {}).get("lista", []):
            guarda(f"rosa_{s['codigo']}", MW.rosa_svg(s["obs"], me["estaciones"]["clases"], lado=260))
        lim = list(p["clases"]) + [None]
        piezas = ['<text x="0" y="12" font-size="12" font-weight="700" fill="#2b3631">Viento, m/s</text>']
        for k in range(len(p["clases"])):                           # en columna: va junto a la rosa de la planta
            txt = (f"{_num(lim[k], 1 if lim[k] % 1 else 0)}–{_num(lim[k + 1])}" if lim[k + 1] is not None else f"≥ {_num(lim[k])}")
            y = 20 + 17 * k
            piezas.append(f'<rect x="0" y="{y}" width="13" height="13" rx="2.5" fill="{MW.COLORES_VEL[k]}"/>'
                          f'<text x="19" y="{y + 11}" font-size="12" fill="#2b3631">{txt}</text>')
        alto = 20 + 17 * len(p["clases"])
        guarda("rosa_leyenda", f'<svg xmlns="http://www.w3.org/2000/svg" width="84" height="{alto}" viewBox="0 0 84 {alto}">{"".join(piezas)}</svg>')

    def _estaciones(self, me):
        """Las estaciones de la zona en el mapa, solas (sin pueblos ni industrias), en grande y con su código, con la planta y la celda del
        ERA5 (usuario, 2026-11-10: «una imagen del mapa con solo los iconos de las estaciones con un buen tamaño y referenciadas a su id»)."""
        import json as _json
        est = (me.get("estaciones") or {}).get("lista", [])
        if not est:
            return
        punto = (me.get("era5") or {}).get("punto")
        emp = self.d["emp"]
        puntos = [(s["lat"], s["lon"]) for s in est] + [(emp["lat"], emp["lon"])] + ([(punto["lat"], punto["lon"])] if punto else [])
        caja = [[min(p[0] for p in puntos), min(p[1] for p in puntos)], [max(p[0] for p in puntos), max(p[1] for p in puntos)]]
        mapa = self.v.mapa
        mapa.js(SOLO_ESTACIONES_JS)
        era5 = (f"window.__era5=L.marker([{punto['lat']},{punto['lon']}],{{icon:L.divIcon({{className:'era5-celda',iconSize:[22,22],"
                f"iconAnchor:[11,11],html:'<div class=\"rombo\"></div><span class=\"cod\">ERA5</span>'}}),zIndexOffset:400}}).addTo(m);"
                if punto else "")
        mapa.js(_MAPA_JS % (era5 + f"m.fitBounds({_json.dumps(caja)},{{paddingTopLeft:[60,60],paddingBottomRight:[150,60],animate:false}});"
                            "return 1;"))
        yield ("mapa", 2500)
        self._foto_mapa("estaciones")
        mapa.js("(function(){var s=document.getElementById('solo-estaciones');if(s){s.remove();}"
                "if(window.__era5){window.__era5.remove();window.__era5=null;}})()")

    def _leer_vista(self):
        """La vista del mapa, [lat, lon, zoom] ([] si no se lee); con `vista = yield from self._leer_vista()`."""
        leida = {}
        self.v.mapa.js(VISTA_JS, lambda r: leida.update(v=r))
        while "v" not in leida:
            yield 100
        try:
            return [float(x) for x in str(leida["v"]).split(",")]
        except ValueError:
            log.warning(f"Informe: no se lee la vista del mapa ({leida['v']!r}).")
            return []

    def _a_la_vista(self, vista):
        """Pone el mapa en `vista` y espera a que cargue; si al acabar no está en ella (algo lo ha vuelto a encuadrar mientras: pasó una vez,
        con la zona un nivel más lejos), otra vez."""
        for intento in range(3):
            self.v.mapa.js(_MAPA_JS % f"m.setView([{vista[0]},{vista[1]}],{round(vista[2])},{{animate:false}});return 1;")
            yield ("mapa", 2500)
            ahora = yield from self._leer_vista()
            pixel = 360.0 / (256 * 2 ** round(vista[2]))           # grados de un píxel, más o menos: el centro, a 3 píxeles
            if not ahora or (round(ahora[2]) == round(vista[2]) and max(abs(ahora[0] - vista[0]), abs(ahora[1] - vista[1])) < 3 * pixel):
                return
            log.info(f"Informe: el mapa se ha movido ({ahora} en vez de {vista}); se vuelve a poner.")

    def _apaisar(self, proporcion):
        """Baja la ventana hasta que su mapa quede de `proporcion` (ancho / alto), o casi: lo que no es mapa no siempre cede lo mismo."""
        for _ in range(3):
            w, h = self.v.mapa.width(), self.v.mapa.height()
            sobra = h - round(w / proporcion)
            if sobra <= 2:
                return
            self.v.resize(self.v.width(), self.v.height() - sobra)
            yield 700

    def _viento(self, me):
        """El viento de las situaciones (`textos.situaciones`: las más frecuentes y la más extrema) en líneas de corriente: en la zona y
        alrededor de la planta, con el mapa más apaisado que en las otras fotos (`estilo.PROPORCION_VIENTO`); luego, la ventana como estaba."""
        import json as _json
        from teodors.gui import tema
        from teodors.writer import estilo, textos
        v, mapa = self.v, self.v.mapa
        vista, alto = None, v.height()
        for k, (clave, titulo, ev) in enumerate(textos.situaciones(me["eventos"])):
            self.avisa(54 + 3 * k, f"El viento: {titulo[0].lower() + titulo[1:]}…")
            v._dia_viento = None
            v._cargar_viento(ev["dia"], me["serie"])
            t1 = time.time()
            while (getattr(v, "_dia_viento", None) or ("",))[0] != ev["dia"]:
                if time.time() - t1 > ESPERA_VIENTO_S:
                    raise RuntimeError(f"no llega el viento del {ev['dia']}")
                yield 500
            # en blanco, como lo enseña la app al abrirse (usuario, 2026-11-09): se ve sobre cualquier fondo
            mapa.js(f"mapaApp.vientoEstilo({_json.dumps(dict(tema.estilo_viento(), modo='lineas', blanco=True))})")
            mapa.viento_hora(ev["h"], 0.0)
            if vista is None:                                        # la zona, como la deja `centrar`; las demás, igual que la primera
                mapa.centrar()
                yield 1500
                vista = yield from self._leer_vista()                # sin vista: cada una como la deje `centrar`
                yield from self._apaisar(estilo.PROPORCION_VIENTO)  # la zona, con su centro y su zoom: se recorta por arriba y por abajo
            if vista:
                yield from self._a_la_vista(vista)
            else:
                mapa.centrar()
                yield ("mapa", 2500)
            self._foto_mapa(f"viento_{clave}_zona")
            mapa.ver_planta()                                        # de cerca: un nivel más que la vista de la planta, para las estelas
            yield 1200
            mapa.js(ACERCAR_JS)
            yield ("mapa", 3000)
            self._foto_mapa(f"viento_{clave}_planta")
        mapa.quitar_viento()
        v.resize(v.width(), alto)
        yield 700

    def _cambio(self, dc):
        """El cambio del P98 de A a B (`comparacion.comparar`: sus isolíneas), en la zona y alrededor de la planta."""
        mapa = self.v.mapa
        mo = dc["comp"]["magnitudes"].get("olor") or next(iter(dc["comp"]["magnitudes"].values()))
        capa = next((c for c in mo["capas"] if c["clave"] == "p98"), mo["capas"][-1])
        datos = json.loads(Path(capa["ruta"]).read_text(encoding="utf-8"))
        mapa.set_isolineas(capa["id"], f"Cambio · {mo['nombre']} · {capa['titulo']}", datos, capa["leyenda"], visible=True,
                           opacidad=penacho_mapa.OPACIDAD, grupo=penacho_mapa.GRUPO)
        mapa.centrar()
        yield ("mapa", 2500)
        self._foto_mapa("cambio_zona")
        self._entorno()
        yield ("mapa", 3000)
        self._foto_mapa("cambio_entorno")
        mapa.quitar_capa(capa["id"])

    def _resultados(self, d, prefijo=""):
        """Los estadísticos de la magnitud principal (media, máximo y P98) en isolíneas, en la zona y alrededor de la planta, con el mapa más
        apaisado (`estilo.PROPORCION_VIENTO`: tres filas en una página); la zona, como la deja `centrar` en la ventana entera. Luego, la
        ventana como estaba."""
        from teodors.writer import estilo
        m, mapa = d["mag"], self.v.mapa
        vista, alto = None, self.v.height()
        for col in m["columnas"]:
            capa = next((c for c in m["capas"] if c["id"].endswith("_" + (col["capa"] or "maximo"))), None)
            if capa is None:
                continue
            iso = S.leer_isolineas(capa)
            if iso is not None:
                mapa.set_isolineas(capa["id"], capa["titulo"], iso, capa["isolineas"]["leyenda"], visible=True, opacidad=penacho_mapa.OPACIDAD,
                                   grupo=penacho_mapa.GRUPO, escala=capa["escala"])
            else:
                mapa.set_imagenes(capa["id"], capa["titulo"], capa["imagenes"], capa["leyenda"], visible=True, opacidad=penacho_mapa.OPACIDAD,
                                  grupo=penacho_mapa.GRUPO, escala=capa["escala"])
            if vista is None:
                mapa.centrar()
                yield 1500
                vista = yield from self._leer_vista()
                yield from self._apaisar(estilo.PROPORCION_VIENTO)
            if vista:
                yield from self._a_la_vista(vista)
            else:
                mapa.centrar()
                yield ("mapa", 2500)
            self._foto_mapa(f"{prefijo}resultado_{col['clave']}_zona")
            self._entorno()
            yield ("mapa", 3000)
            self._foto_mapa(f"{prefijo}resultado_{col['clave']}_entorno")
            mapa.quitar_capa(capa["id"])
        self.v.resize(self.v.width(), alto)
        yield 700

    def _pasos(self):
        v, d, mapa = self.v, self.d, self.v.mapa
        t0 = time.time()
        while not (mapa.esta_listo() and getattr(v, "terreno_info", None) is not None) and time.time() - t0 < 90:
            yield 500
        yield 1500
        mapa.js(SIN_MANDOS_JS)
        # el resultado: el estadístico principal, en isolíneas
        self.avisa(5, "Mapas del resultado…")
        capa = capa_principal(d)
        iso = S.leer_isolineas(capa)
        if iso is not None:
            mapa.set_isolineas(capa["id"], capa["titulo"], iso, capa["isolineas"]["leyenda"], visible=True, opacidad=penacho_mapa.OPACIDAD,
                               grupo=penacho_mapa.GRUPO, escala=capa["escala"])
        else:
            mapa.set_imagenes(capa["id"], capa["titulo"], capa["imagenes"], capa["leyenda"], visible=True, opacidad=penacho_mapa.OPACIDAD,
                              grupo=penacho_mapa.GRUPO, escala=capa["escala"])
        mapa.centrar()
        yield ("mapa", 2500)
        self._foto_mapa("resultado_zona")
        self._entorno()
        yield ("mapa", 3000)
        self._foto_mapa("resultado_entorno")
        mapa.quitar_capa(capa["id"])
        if self.comparacion:                                         # los de A y los de B, y el cambio de uno a otro
            self.avisa(10, "Mapas de los resultados de A…")
            yield from self._resultados(self.comparacion["a"], "a_")
            self.avisa(14, "Mapas de los resultados de B…")
            yield from self._resultados(self.comparacion["b"], "b_")
            self.avisa(18, "El cambio de A a B…")
            yield from self._cambio(self.comparacion)
        else:
            self.avisa(12, "Mapas de la media, el máximo y el P98…")
            yield from self._resultados(d)
        # el relieve y los usos del suelo
        for k, (id_capa, pct) in enumerate((("elevacion", 20), ("usos", 35))):
            self.avisa(pct, f"Mapas del {'relieve' if id_capa == 'elevacion' else 'uso del suelo'}…")
            mapa.ver_capa(id_capa, True)
            mapa.centrar()
            yield ("mapa", 2500)
            self._foto_mapa(id_capa)
            self._entorno()
            yield ("mapa", 3000)
            self._foto_mapa(f"{id_capa}_entorno")
            mapa.ver_capa(id_capa, False)
        # los edificios junto a la planta y los lugares de la zona
        self.avisa(50, "Mapas de los edificios y los lugares…")
        mapa.ver_planta()
        mapa.ver_capa("edificios", True)
        yield ("mapa", 2500)
        self._foto_mapa("edificios")
        mapa.ver_capa("edificios", False)
        mapa.centrar()
        yield ("mapa", 2500)
        self._foto_mapa("dominio")
        # la meteorología: las estaciones, las rosas y el viento de las situaciones del mapa
        if d.get("meteo"):
            self.avisa(52, "Las estaciones y las rosas de los vientos…")
            yield from self._estaciones(d["meteo"])
            self._rosas(d["meteo"])
            yield from self._viento(d["meteo"])
        # en 3D: los edificios, todos los focos y cada uno
        from teodors.gui import focos_graficos as G
        from teodors.gui import tema
        self.avisa(65, "Los focos en 3D…")
        eds, focos = d["edificios"], d["focos"]["focos"]
        if eds:
            w = G.VisorEdificios()
            w.resize(1500, 1000)
            w.poner(eds, encuadrar=True)
            yield 200
            self._foto(w, "edificios_3d", 1500, 1000)
            w.deleteLater()
        w = G.VisorFocos3D()
        w.resize(1820, 1080)
        w.poner(focos, eds)
        yield 200
        self._foto(w, "focos_3d", 1820, 1080)
        w.deleteLater()
        for j, f in enumerate(focos):
            w = visor_foco(f, eds)
            w.resize(450, 530)
            yield 120
            self._foto(w, f"foco_{f['id']}", 450, 530)
            w.deleteLater()
            self.fichas[f["id"]] = ficha(f)
            self.avisa(65 + 30 * (j + 1) // max(len(focos), 1), f"Foco {j + 1} de {len(focos)}…")
        for ic in sorted({c[0] for fi in self.fichas.values() for c in fi["cifras"]}):
            tema.pixmap(ic, tema.T["acento"], 32).save(str(self.carpeta / f"ico_{ic}.png"))
            self.imagenes.append(f"ico_{ic}")
        (self.carpeta / "fichas.json").write_text(json.dumps(self.fichas, ensure_ascii=False, indent=1), encoding="utf-8")
        self.avisa(96, "Imágenes hechas")
        if self.al_acabar:
            self.al_acabar({"imagenes": list(self.imagenes), "fichas": self.fichas})
