# -*- coding: utf-8 -*-
"""Vista del mapa: QWebEngineView con el HTML de mapa_web y su puente JS ↔ Python."""
import json
from pathlib import Path

from PySide6 import QtCore, QtGui
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from teodors.comun import registro
from teodors.gui import mapa_web, tema

log = registro.get("mapa")


class PaginaMapa(QWebEnginePage):
    """Recoge los mensajes «MAPA:{json}» que el mapa escribe en la consola JS."""
    evento = QtCore.Signal(dict)

    def javaScriptConsoleMessage(self, nivel, mensaje, linea, origen):
        if mensaje.startswith("MAPA:"):
            try:
                self.evento.emit(json.loads(mensaje[5:]))
            except ValueError:
                log.debug(f"Mensaje del mapa ilegible: {mensaje!r}")
        elif nivel == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            log.warning(f"[mapa JS] {mensaje} (línea {linea})")
        else:
            log.debug(f"[mapa JS] {mensaje}")


class VistaMapa(QWebEngineView):
    clic = QtCore.Signal(float, float)             # lat, lon
    estacion = QtCore.Signal(str)                  # código de la estación pinchada
    capa = QtCore.Signal(str, bool)                # una capa del selector se enciende / apaga
    formaViento = QtCore.Signal()                  # se ha elegido otra forma del viento en el selector
    listo = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pagina = PaginaMapa(self)
        self.setPage(self._pagina)
        self._pagina.setBackgroundColor(QtGui.QColor(tema.c("fondo")))     # sin fogonazo blanco al cargar
        s = self._pagina.settings()
        # un HTML file:// no puede pedir teselas ni CDN sin esto (guía 07)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self._pagina.evento.connect(self._evento)
        self._listo = False
        self._pendientes = []
        tema.avisos.cambiado.connect(self.set_tema)

    def set_tema(self):
        """Otro estilo con el mapa abierto: cambian las variables de color y no se recarga nada."""
        self._pagina.setBackgroundColor(QtGui.QColor(tema.c("fondo")))
        self.js(tema.js_variables())

    # ── carga y JS ───────────────────────────────────────────────────────────────────────
    def cargar(self, emp, limites, ruta=None):
        self._listo = False
        self._local_enviado = False
        self._pendientes.clear()
        ruta = mapa_web.escribir_mapa_base(emp, limites, ruta)
        log.debug(f"Mapa base: {ruta}")
        self.setUrl(QtCore.QUrl.fromLocalFile(str(ruta)))

    def js(self, codigo, al_terminar=None):
        """Ejecuta JS en el mapa; si aún no está listo, lo guarda para después."""
        if not self._listo:
            self._pendientes.append((codigo, al_terminar))
        elif al_terminar is None:
            self._pagina.runJavaScript(codigo)
        else:
            self._pagina.runJavaScript(codigo, 0, al_terminar)

    def _evento(self, ev):
        tipo = ev.get("evento")
        if tipo == "listo":
            self._listo = True
            for codigo, cb in self._pendientes:
                self.js(codigo, cb)
            self._pendientes.clear()
            self.listo.emit()
        elif tipo == "clic":
            self.clic.emit(float(ev["lat"]), float(ev["lon"]))
        elif tipo == "estacion":
            self.estacion.emit(str(ev["codigo"]))
        elif tipo == "capa":
            self.capa.emit(str(ev["id"]), bool(ev["visible"]))
        elif tipo == "formaViento":
            if tema.preferencia("viento_forma") != ev["modo"]:
                tema.poner_preferencia("viento_forma", ev["modo"])
                self.formaViento.emit()
        elif tipo == "fondo":
            log.debug(f"Fondo del mapa: {ev.get('nombre')}")

    # ── acciones ─────────────────────────────────────────────────────────────────────────
    def set_planta(self, emp):
        self.js(f"mapaApp.setPlanta({json.dumps(mapa_web.datos_planta(emp))})")

    def set_limites(self, limites):
        self.js(f"mapaApp.setLimites({json.dumps(limites)})")

    def set_nucleos(self, lista):
        """lista = [{familia, lat, lon, texto}] (iconos de casa, fábrica y balón)."""
        self.js(f"mapaApp.setNucleos({json.dumps(lista)})")

    def set_estaciones(self, lista):
        """lista = [{codigo, lat, lon, texto}] (icono de estación meteorológica)."""
        self.js(f"mapaApp.setEstaciones({json.dumps(lista)})")

    def aviso(self, texto, tipo="ok"):
        """Aviso breve sobre el mapa; tipo: ok | fallo."""
        self.js(f"mapaApp.aviso({json.dumps(texto)}, {json.dumps(tipo)})")

    def ficha(self, lat, lon, html):
        """Ficha flotante en un punto del mapa."""
        self.js(f"mapaApp.ficha({lat}, {lon}, {json.dumps(html)})")

    def centrar(self):
        self.js("mapaApp.centrar()")

    def ver_planta(self):
        self.js("mapaApp.verPlanta()")

    def esta_listo(self):
        return self._listo

    def quitar_capa(self, id_capa):
        self.js(f"mapaApp.quitarCapa({json.dumps(id_capa)})")

    def ver_capa(self, id_capa, si=True):
        """Enciende o apaga una capa ya añadida al selector (botones «Ver …» del panel)."""
        self.js(f"mapaApp.verCapa({json.dumps(id_capa)}, {'true' if si else 'false'})")

    def set_capa_geojson(self, id_capa, nombre, datos, leyenda_html="", visible=True,
                         grupo=None):
        """Capa vectorial (GeoJSON en lat/lon), solo para los botones del panel. Las capas del mismo
        `grupo` son excluyentes: al activar una se desactiva la anterior."""
        datos = {"id": id_capa, "nombre": nombre, "datos": datos, "visible": visible,
                 "leyenda": leyenda_html, "grupo": grupo, "selector": False}
        self.js(f"mapaApp.setCapaGeoJSON({json.dumps(datos)})")

    def set_capa_puntos(self, id_capa, nombre, puntos, estilos, leyenda_html="",
                        visible=False, grupo=None):
        """Muchos puntos (p. ej. receptores): puntos = [(lat, lon, índice de estilo)],
        estilos = [{color, radio}]. Se dibujan en canvas (miles sin ralentizar el mapa)."""
        datos = {"id": id_capa, "nombre": nombre, "visible": visible, "grupo": grupo,
                 "leyenda": leyenda_html, "estilos": estilos,
                 "puntos": [[round(la, 6), round(lo, 6), k] for la, lo, k in puntos]}
        self.js(f"mapaApp.setCapaPuntos({json.dumps(datos)})")

    def set_viento(self, datos):
        """Viento en superficie de un día (viento_mapa.datos_dia): capa animada de partículas
        (o flechas) en el selector de capas. La primera vez envía también la biblioteca del motor de la planta."""
        if not self._local_enviado:
            from teodors.operacion import viento_mapa
            local = viento_mapa.datos_local()
            if local:
                self.js(f"mapaApp.setVientoLocal({json.dumps(local)})")
            self._local_enviado = True
        self.js(f"mapaApp.setViento({json.dumps(dict(datos, **tema.estilo_viento()))})")

    def viento_estilo(self):
        """Forma, color, escala y cantidad elegidos en la configuración, sin volver a cargar el viento."""
        self.js(f"mapaApp.vientoEstilo({json.dumps(tema.estilo_viento())})")

    def viento_hora(self, hora, fraccion=0.0):
        self.js(f"mapaApp.vientoHora({int(hora)}, {float(fraccion):.3f})")

    def quitar_viento(self):
        self.js("mapaApp.quitarViento()")

    def ocultar_viento(self, si):
        """El viento fuera del mapa y del selector de capas (Simular con el reanálisis: son sus años, no un día), sin olvidar el día; al volver, como estaba."""
        self.js(f"mapaApp.ocultarViento({'true' if si else 'false'})")

    def set_penacho(self, datos):
        """Penacho de un plan (planes_calculo.datos_penacho): sus imágenes por hora con fundido entre
        horas y el panel del tiempo (tiempo, termómetro, brújula)."""
        self.js(f"mapaApp.setPenacho({json.dumps(datos)})")

    def penacho_hora(self, hora, fraccion=0.0):
        self.js(f"mapaApp.penachoHora({int(hora)}, {float(fraccion):.3f})")

    def quitar_penacho(self):
        self.js("mapaApp.quitarPenacho()")

    def modo_penacho(self, iso):
        """El penacho en isolíneas (franjas) o en degradado, como la media y el máximo del mapa."""
        self.js(f"mapaApp.modoPenacho({'true' if iso else 'false'})")

    def set_imagen(self, id_capa, nombre, url, limites, leyenda_html="", visible=False,
                   opacidad=0.72, grupo=None):
        """Capa de imagen ya en Web Mercator (url file://, límites [[s, o], [n, e]]) con su
        leyenda HTML, en el selector de capas."""
        datos = {"id": id_capa, "nombre": nombre, "url": url, "bounds": limites,
                 "opacidad": opacidad, "visible": visible, "grupo": grupo, "leyenda": leyenda_html}
        self.js(f"mapaApp.setCapaImagen({json.dumps(datos)})")

    def set_imagenes(self, id_capa, nombre, imagenes, leyenda_html="", visible=False, opacidad=0.72,
                     grupo=None, escala=None):
        """Capa del selector formada por varias imágenes en Web Mercator: [{url, limites}]. Con `escala`
        («olor», «gases»), imágenes en grises que el mapa colorea con la escala elegida para esa magnitud."""
        datos = {"id": id_capa, "nombre": nombre, "imagenes": imagenes, "opacidad": opacidad,
                 "visible": visible, "grupo": grupo, "leyenda": leyenda_html, "escala": escala}
        self.js(f"mapaApp.setCapaImagen({json.dumps(datos)})")

    def set_isolineas(self, id_capa, nombre, datos, leyenda_html="", visible=False, opacidad=0.72, grupo=None, escala=None):
        """Capa del selector con las isolíneas rellenas de un campo (GeoJSON de `simulacion._isolineas`): sus franjas, con el color de la
        escala de su magnitud (`escala`), y sus líneas."""
        datos = {"id": id_capa, "nombre": nombre, "datos": datos, "opacidad": opacidad, "visible": visible, "grupo": grupo,
                 "leyenda": leyenda_html, "escala": escala}
        self.js(f"mapaApp.setCapaIsolineas({json.dumps(datos)})")

    def set_escalas(self):
        """Escalas de color elegidas en la configuración: las capas abiertas cambian sin rehacer imágenes."""
        self.js(f"mapaApp.setEscalas({json.dumps(tema.escalas_mapa())})")

    def set_capa_imagen(self, capa, carpeta, visible=False, opacidad=0.7, grupo=None):
        """Añade (o sustituye) una capa de imagen, solo para los botones del panel. `capa` es un dict de
        terreno.imagenes_mapa; el PNG está en `carpeta`."""
        png = Path(carpeta) / capa["png"]
        url = QtCore.QUrl.fromLocalFile(str(png)).toString() + f"?v={int(png.stat().st_mtime)}"
        datos = {"id": capa["id"], "nombre": capa["nombre"], "url": url,
                 "bounds": capa["bounds"], "opacidad": opacidad, "visible": visible,
                 "grupo": grupo, "selector": False,
                 "leyenda": mapa_web.leyenda_html(capa["nombre"], capa["leyenda"])}
        self.js(f"mapaApp.setCapaImagen({json.dumps(datos)})")
