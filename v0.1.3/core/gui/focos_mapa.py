# -*- coding: utf-8 -*-
"""Plano de la ventana de focos: ortofoto de la planta con los focos dibujados (superficie,
punto, volumen) y el elegido RECUADRADO y rotulado (maqueta aprobada, 2026-10-25).

Mismo puente que el mapa principal (gui/mapa.py): Python → JS con `window.mapaApp.*` y JS → Python
con `console.log("MAPA:{json}")`. En el modo de edición también se dibuja aquí la ubicación de un foco
(clic a clic los vértices de una superficie; un clic para un punto o el centro de un volumen).
"""
import json

import folium
from PySide6 import QtCore, QtGui
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from teodors import planta as config
from teodors.comun import registro
from teodors.planta import geo
from teodors.gui import mapa_web, tema, web
from teodors.gui.mapa import PaginaMapa

log = registro.get("focos")

# relleno y borde por modelo, los de la maqueta
COLORES = {"superficie": ("#8fb4c6", "#5d8ea6"), "punto": ("#d9822b", "#a14a04"),
           "volumen": ("#b9a6d6", "#7d68a6")}

_CSS = """
<style>
.mapa-etq{background:none;border:none}
.mapa-etq span{display:inline-block;background:var(--acento);color:var(--sobre_acento);font:600 13px var(--letra);
  padding:4px 10px;border-radius:999px;white-space:nowrap;box-shadow:0 2px 7px var(--sombra)}
.mapa-ley{border-radius:12px;padding:6px 12px;font:12px var(--letra);display:flex;gap:12px}
.mapa-ley i{display:inline-block;width:14px;height:10px;margin-right:5px;vertical-align:-1px}
.mapa-aviso{position:absolute;top:10px;left:50%;transform:translateX(-50%);z-index:1000;display:none;
  background:var(--cristal);color:var(--texto);font:13px var(--letra);padding:7px 10px 7px 14px;
  border:1px solid var(--linea);border-radius:12px;box-shadow:0 8px 26px var(--sombra);align-items:center;gap:10px}
.mapa-aviso button{font:600 12.5px var(--letra);border:none;border-radius:8px;padding:5px 10px;cursor:pointer}
.mapa-aviso .si{background:var(--acento);color:var(--sobre_acento)}.mapa-aviso .no{background:var(--hover);color:var(--texto)}
</style>
"""

_JS = """
<script>
(function () {
  function enviar(o) { console.log("MAPA:" + JSON.stringify(o)); }
  function esc(t) { return String(t).replace(/[&<>"]/g, function (c) {
    return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function iniciar() {
    L.Tooltip.mergeOptions({opacity: 1});
    var mapa = __MAPA__;
    var COL = __COLORES__;
    var grupo = L.featureGroup().addTo(mapa);
    var capas = {}, datos = {}, sel = null, marco = null, etiqueta = null, dib = null;

    function estilo(f, on) {
      var c = COL[f.modelo];
      return {color: on ? "var(--acento)" : c[1], weight: on ? 3 : 1.5, fillColor: c[0],
              fillOpacity: on ? 0.8 : 0.5, opacity: 1};
    }
    function limites(id) {
      var l = capas[id];
      return l.getBounds ? l.getBounds() : L.latLngBounds([l.getLatLng(), l.getLatLng()]);
    }
    // recuadro discontinuo a 12 px del foco y su rótulo encima (se rehace al hacer zoom)
    function pintaMarco() {
      if (marco) { mapa.removeLayer(marco); marco = null; }
      if (etiqueta) { mapa.removeLayer(etiqueta); etiqueta = null; }
      if (!sel || !capas[sel]) { return; }
      var b = limites(sel), p = 12;
      var so = mapa.latLngToContainerPoint(b.getSouthWest()), ne = mapa.latLngToContainerPoint(b.getNorthEast());
      var a = mapa.containerPointToLatLng([so.x - p, so.y + p]), z = mapa.containerPointToLatLng([ne.x + p, ne.y - p]);
      marco = L.rectangle([a, z], {color: "var(--acento)", weight: 3, dashArray: "7 5", fill: false,
                                   interactive: false}).addTo(mapa);
      etiqueta = L.marker([z.lat, a.lng], {interactive: false, keyboard: false, zIndexOffset: 1000,
        icon: L.divIcon({className: "mapa-etq", html: "<span>" + esc(datos[sel].nombre) + "</span>",
                         iconSize: null, iconAnchor: [0, 33]})}).addTo(mapa);
    }
    mapa.on("zoomend", pintaMarco);

    var Ley = L.Control.extend({options: {position: "bottomleft"}, onAdd: function () {
      var d = L.DomUtil.create("div", "mapa-ley");
      d.innerHTML = ["superficie", "punto", "volumen"].map(function (m) {
        return "<span><i style='background:" + COL[m][0] + ";border:1px solid " + COL[m][1] + "'></i>" + m + "</span>";
      }).join("");
      return d; }});
    mapa.addControl(new Ley());

    // aviso del modo dibujo, con Terminar y Cancelar
    var aviso = L.DomUtil.create("div", "mapa-aviso", mapa.getContainer());
    L.DomEvent.disableClickPropagation(aviso);
    function avisa(texto, conTerminar) {
      aviso.innerHTML = "<span>" + texto + "</span>" + (conTerminar ? "<button class='si'>Terminar</button>" : "")
        + "<button class='no'>Cancelar</button>";
      aviso.style.display = "flex";
      var bs = aviso.querySelectorAll("button");
      if (conTerminar) { bs[0].onclick = function () { termina(); }; }
      bs[bs.length - 1].onclick = function () { cancela(); };
    }
    function limpiaDibujo() {
      if (dib && dib.capa) { mapa.removeLayer(dib.capa); }
      dib = null;
      aviso.style.display = "none";
      mapa.getContainer().style.cursor = "";
      mapa.doubleClickZoom.enable();
    }
    function termina() {
      if (!dib) { return; }
      if (dib.modelo === "superficie" && dib.puntos.length < 3) { return; }
      var pts = dib.puntos.map(function (p) { return [p.lat, p.lng]; });
      limpiaDibujo();
      enviar({evento: "ubicacion", puntos: pts});
    }
    function cancela() { limpiaDibujo(); enviar({evento: "ubicacion", puntos: null}); }
    mapa.on("click", function (e) {
      if (!dib) { return; }
      if (dib.modelo !== "superficie") { dib.puntos = [e.latlng]; termina(); return; }
      var n = dib.puntos.length;
      if (n && mapa.latLngToContainerPoint(dib.puntos[n - 1]).distanceTo(e.containerPoint) < 5) { return; }
      dib.puntos.push(e.latlng);
      if (dib.capa) { mapa.removeLayer(dib.capa); }
      dib.capa = L.polygon(dib.puntos, {color: "var(--acento)", weight: 2, dashArray: "5 4",
                                        fillOpacity: 0.2, interactive: false}).addTo(mapa);
    });
    mapa.on("dblclick", function () { if (dib && dib.modelo === "superficie") { termina(); } });
    document.addEventListener("keydown", function (e) {
      if (!dib) { return; }
      if (e.key === "Escape") { cancela(); }
      if (e.key === "Enter") { termina(); }
    });

    window.mapaApp = {
      // lista = [{id, nombre, modelo, geo: {tipo: "punto", lat, lon} | {tipo: "poligono", puntos}}]
      setFocos: function (lista, encuadrar) {
        grupo.clearLayers(); capas = {}; datos = {};
        lista.forEach(function (f) {
          if (!f.geo) { return; }
          var l = f.geo.tipo === "punto"
            ? L.circleMarker([f.geo.lat, f.geo.lon], Object.assign({radius: 7}, estilo(f, false)))
            : L.polygon(f.geo.puntos, estilo(f, false));
          l.bindTooltip(esc(f.nombre), {sticky: true});
          l.on("click", function (e) { if (!dib) { L.DomEvent.stopPropagation(e); enviar({evento: "foco", id: f.id}); } });
          l.addTo(grupo);
          capas[f.id] = l; datos[f.id] = f;
        });
        if (encuadrar && grupo.getLayers().length) { mapa.fitBounds(grupo.getBounds().pad(0.12)); }
        mapaApp.elegir(sel, false);
      },
      elegir: function (id, mostrar) {
        if (sel && capas[sel]) { capas[sel].setStyle(estilo(datos[sel], false)); }
        sel = id;
        if (sel && capas[sel]) {
          capas[sel].setStyle(estilo(datos[sel], true));
          capas[sel].bringToFront();
          if (mostrar && !mapa.getBounds().contains(limites(sel))) {
            mapa.fitBounds(limites(sel).pad(2), {maxZoom: 18});
          }
        }
        pintaMarco();
      },
      // modo dibujo (edición): superficie clic a clic; punto y volumen, un clic
      dibujar: function (modelo) {
        limpiaDibujo();
        dib = {modelo: modelo, puntos: [], capa: null};
        mapa.doubleClickZoom.disable();
        mapa.getContainer().style.cursor = "crosshair";
        avisa(modelo === "superficie"
              ? "Clic en cada vértice · doble clic o Intro para terminar · Esc para cancelar"
              : (modelo === "punto" ? "Clic donde está la salida" : "Clic en el centro del volumen")
                + " · Esc para cancelar", modelo === "superficie");
      },
      estado: function () { return {focos: Object.keys(capas).length, sel: sel, marco: !!marco,
                                    dibujando: dib ? dib.modelo : null, zoom: mapa.getZoom()}; }
    };
    enviar({evento: "listo"});
  }
  // Con los scripts ya ejecutados, sin esperar a las imágenes: «load» espera a todas las teselas y, con el
  // servidor lento o atascado, no había focos, ni capas, ni nada del mapa (medido, 2026-10-31).
  document.addEventListener("DOMContentLoaded", iniciar);
})();
</script>
"""


def escribir_html(emp, ruta=None):
    """HTML del plano (fuera de OneDrive, regenerable) con las librerías embebidas."""
    ruta = ruta or (config.DIR_WEB / "mapa_focos.html")
    m = folium.Map(location=[emp["lat"], emp["lon"]], zoom_start=17, tiles=None,
                   control_scale=True, max_zoom=20)
    for i, (nombre, url, atr, nativo) in enumerate(mapa_web.fondos()):
        folium.TileLayer(tiles=url, attr=atr, name=nombre, overlay=False, control=True,
                         show=(i == 0), max_zoom=20, max_native_zoom=nativo).add_to(m)
    folium.LayerControl(position="topright", collapsed=True).add_to(m)
    js = (_JS.replace("__MAPA__", m.get_name())
             .replace("__COLORES__", json.dumps(COLORES)))
    m.get_root().header.add_child(folium.Element(mapa_web.css_tema() + _CSS))
    m.get_root().html.add_child(folium.Element(js))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(ruta))
    try:
        web.hacer_autonomo(ruta, config.DIR_WEB_ASSETS)
    except Exception as e:                          # sigue funcionando con los CDN
        log.warning(f"No se pudo hacer autónomo el plano de focos (se usarán los CDN): {e!r}")
    return ruta


def geometria(foco):
    """Lo que dibuja el plano (lat/lon) a partir de la ubicación UTM; None si no está ubicado."""
    u = foco.get("ubicacion") or {}
    m = foco.get("modelo")
    if m == "superficie" and len(u.get("poligono") or []) >= 3:
        return {"tipo": "poligono", "puntos": [list(geo.a_geo(x, y)) for x, y in u["poligono"]]}
    if "x" not in u or "y" not in u:
        return None
    if m == "volumen":
        d = foco.get("dimensiones") or {}
        lx, ly = (d.get("largo_m") or 6.0) / 2, (d.get("ancho_m") or 6.0) / 2
        x, y = u["x"], u["y"]
        return {"tipo": "poligono", "puntos": [list(geo.a_geo(x + sx * lx, y + sy * ly))
                                               for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]}
    lat, lon = geo.a_geo(u["x"], u["y"])
    return {"tipo": "punto", "lat": lat, "lon": lon}


class VistaFocos(QWebEngineView):
    listo = QtCore.Signal()
    foco = QtCore.Signal(str)                  # id del foco pinchado en el plano
    ubicacion = QtCore.Signal(object)          # [(lat, lon), …] dibujados, o None si se cancela

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pagina = PaginaMapa(self)
        self.setPage(self._pagina)
        self._pagina.setBackgroundColor(QtGui.QColor(tema.c("fondo")))
        s = self._pagina.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self._pagina.evento.connect(self._evento)
        self._listo, self._pendientes = False, []
        tema.avisos.cambiado.connect(self.set_tema)

    def set_tema(self):
        """Otro estilo con el plano abierto: cambian las variables de color y no se recarga nada."""
        self._pagina.setBackgroundColor(QtGui.QColor(tema.c("fondo")))
        self.js(tema.js_variables())

    def cargar(self, emp):
        self._listo = False
        self._pendientes.clear()
        self.setUrl(QtCore.QUrl.fromLocalFile(str(escribir_html(emp))))

    def js(self, codigo, al_terminar=None):
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
        elif tipo == "foco":
            self.foco.emit(str(ev["id"]))
        elif tipo == "ubicacion":
            p = ev.get("puntos")
            self.ubicacion.emit([tuple(x) for x in p] if p else None)

    def set_focos(self, lista_focos, encuadrar=False):
        lista = [{"id": f["id"], "nombre": f.get("nombre") or f["id"], "modelo": f["modelo"],
                  "geo": geometria(f)} for f in lista_focos]
        self.js(f"mapaApp.setFocos({json.dumps(lista)}, {'true' if encuadrar else 'false'})")

    def elegir(self, id_foco, mostrar=True):
        self.js(f"mapaApp.elegir({json.dumps(id_foco)}, {'true' if mostrar else 'false'})")

    def dibujar(self, modelo):
        self.setFocus()
        self.js(f"mapaApp.dibujar({json.dumps(modelo)})")
