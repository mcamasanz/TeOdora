# -*- coding: utf-8 -*-
"""Plano de la ventana de focos: ortofoto de la planta con los focos dibujados (superficie,
punto, volumen) y el elegido RECUADRADO y rotulado (maqueta aprobada, 2026-10-25).

Mismo puente que el mapa principal (gui/mapa.py): Python → JS con `window.mapaApp.*` y JS → Python
con `console.log("MAPA:{json}")`. En el editor de focos también se dibuja aquí la ubicación de un foco (`forma`): un rectángulo (dos
esquinas opuestas), un círculo (el centro y un punto del borde; sale un polígono de 36 vértices), un polígono (clic a clic) o un punto; y el
borrador del foco que se edita (`borrador`).
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

# relleno y borde por modelo, los de la maqueta: los mismos que el plano de la página Focos
from teodors.gui.focos_graficos import COLORES  # noqa: E402

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
    var capas = {}, datos = {}, sel = null, marco = null, etiqueta = null, dib = null, borrador = null;

    function estilo(f, on) {
      var c = COL[f.modelo];
      return {color: on ? "var(--acento)" : c[1], weight: on ? 3 : 1.5, fillColor: c[0],
              fillOpacity: on ? 0.8 : 0.5, opacity: 1};
    }
    // Encuadrar con el mapa aún sin tamaño (la página carga antes de que se vea la ventana) lo dejaba en el zoom 0, el mundo entero
    // (usuario, 2026-11-08: «no veo el mapa»): el encuadre espera a que el mapa tenga tamaño
    var pendiente = null;
    function cuandoTenga(f) {
      var t = mapa.getSize();
      if (!t.x || !t.y) { pendiente = f; return; }
      pendiente = null;
      f();
    }
    function encuadra(b, opciones) {
      enPlanta = false;
      cuandoTenga(function () { mapa.fitBounds(b, opciones || {}); });
    }
    // la vista de «Ver la planta» (usuario, 2026-11-09: la ventana de focos y la de la operación se abren con ella). Se queda mientras
    // nadie mueva el mapa: si la vista cambia de tamaño (la ventana se monta o se arrastra un divisor), vuelve a la planta; antes, la
    // planta acababa en una esquina
    // `entera` (un plano pequeño, el de la ventana de la operación): la planta con todos sus focos dentro, nunca más cerca que «Ver la planta»
    var PLANTA = __PLANTA__, ZOOM_PLANTA = __ZOOM_PLANTA__, enPlanta = false, entera = false;
    function alaPlanta() {
      if (entera && grupo.getLayers().length) {
        mapa.fitBounds(grupo.getBounds().pad(0.08), {maxZoom: ZOOM_PLANTA, animate: false});
        return;
      }
      mapa.setView(PLANTA, ZOOM_PLANTA, {animate: false});
    }
    function verPlanta(todos) { enPlanta = true; entera = !!todos; cuandoTenga(alaPlanta); }
    function reajusta() {
      if (pendiente) { cuandoTenga(pendiente); } else if (enPlanta) { alaPlanta(); }
    }
    mapa.on("resize", reajusta);
    ["mousedown", "wheel", "touchstart", "keydown"].forEach(function (ev) {      // quien toca el mapa lo mueve él
      mapa.getContainer().addEventListener(ev, function () { enPlanta = false; }, true);
    });
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
      var forma = dib.forma || (dib.modelo === "superficie" ? "poligono" : "punto");
      if (forma === "poligono" && dib.puntos.length < 3) { return; }
      var pts = dib.puntos.map(function (p) { return [p.lat, p.lng]; });
      limpiaDibujo();
      enviar({evento: "ubicacion", puntos: pts, forma: forma});
    }
    // las esquinas de un rectángulo de esquinas opuestas a y b, y un círculo de centro c que pasa por b (36 vértices)
    function rectangulo(a, b) {
      return [L.latLng(a.lat, a.lng), L.latLng(a.lat, b.lng), L.latLng(b.lat, b.lng), L.latLng(b.lat, a.lng)];
    }
    function circulo(c, b) {
      var r = mapa.distance(c, b), pts = [];
      var mgrado = L.CRS.Earth.R * Math.PI / 180;                 // metros por grado de latitud
      var dlat = r / mgrado, dlon = r / (mgrado * Math.cos(c.lat * Math.PI / 180));
      for (var k = 0; k < 36; k++) {
        var t = 2 * Math.PI * k / 36;
        pts.push(L.latLng(c.lat + dlat * Math.sin(t), c.lng + dlon * Math.cos(t)));
      }
      return pts;
    }
    function previa(pts) {
      if (dib.capa) { mapa.removeLayer(dib.capa); }
      dib.capa = L.polygon(pts, {color: "var(--acento)", weight: 2, dashArray: "5 4", fillOpacity: 0.2,
                                 interactive: false}).addTo(mapa);
    }
    mapa.on("mousemove", function (e) {
      if (!dib || !dib.ancla) { return; }
      previa(dib.forma === "rectangulo" ? rectangulo(dib.ancla, e.latlng) : circulo(dib.ancla, e.latlng));
    });
    function cancela() { limpiaDibujo(); enviar({evento: "ubicacion", puntos: null}); }
    mapa.on("click", function (e) {
      if (!dib) { return; }
      if (dib.forma === "rectangulo" || dib.forma === "circulo") {
        if (!dib.ancla) { dib.ancla = e.latlng; return; }
        dib.puntos = dib.forma === "rectangulo" ? rectangulo(dib.ancla, e.latlng) : circulo(dib.ancla, e.latlng);
        termina();
        return;
      }
      if (dib.forma === "punto" || (!dib.forma && dib.modelo !== "superficie")) { dib.puntos = [e.latlng]; termina(); return; }
      var n = dib.puntos.length;
      if (n && mapa.latLngToContainerPoint(dib.puntos[n - 1]).distanceTo(e.containerPoint) < 5) { return; }
      dib.puntos.push(e.latlng);
      if (dib.capa) { mapa.removeLayer(dib.capa); }
      dib.capa = L.polygon(dib.puntos, {color: "var(--acento)", weight: 2, dashArray: "5 4",
                                        fillOpacity: 0.2, interactive: false}).addTo(mapa);
    });
    mapa.on("dblclick", function () { if (dib && (dib.forma === "poligono" || (!dib.forma && dib.modelo === "superficie"))) { termina(); } });
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
        if (encuadrar && grupo.getLayers().length) { encuadra(grupo.getBounds().pad(0.12)); }
        else if (enPlanta && entera && !pendiente) { alaPlanta(); }          // la planta entera, con los focos de ahora
        mapaApp.elegir(sel, false);
      },
      elegir: function (id, mostrar) {
        if (sel && capas[sel]) { capas[sel].setStyle(estilo(datos[sel], false)); }
        sel = id;
        if (sel && capas[sel]) {
          capas[sel].setStyle(estilo(datos[sel], true));
          capas[sel].bringToFront();
          // con la planta aún por enseñar, se queda la planta; si no, el foco se busca solo si no se ve
          if (mostrar && !(enPlanta && pendiente) && (pendiente || !mapa.getBounds().contains(limites(sel)))) {
            encuadra(limites(sel).pad(2), {maxZoom: 18});
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
      // el editor de focos: una forma para la ubicación del foco
      forma: function (forma) {
        limpiaDibujo();
        dib = {forma: forma, puntos: [], capa: null, ancla: null};
        mapa.doubleClickZoom.disable();
        mapa.getContainer().style.cursor = "crosshair";
        avisa({rectangulo: "Clic en una esquina y clic en la opuesta",
               circulo: "Clic en el centro y clic en el borde",
               poligono: "Clic en cada vértice · doble clic o Intro para terminar",
               punto: "Clic donde está el foco"}[forma] + " · Esc para cancelar", forma === "poligono");
      },
      // el foco que se edita, aparte y discontinuo: {tipo: "punto", lat, lon} | {tipo: "poligono", puntos}; null lo quita
      borrador: function (geo, encuadrar) {
        if (borrador) { mapa.removeLayer(borrador); borrador = null; }
        if (!geo) { return; }
        var est = {color: "var(--acento)", weight: 3, dashArray: "6 4", fillColor: "var(--acento)", fillOpacity: 0.25};
        borrador = geo.tipo === "punto" ? L.circleMarker([geo.lat, geo.lon], Object.assign({radius: 8}, est))
                                       : L.polygon(geo.puntos, est);
        borrador.addTo(mapa);
        if (encuadrar) {
          var b = borrador.getBounds ? borrador.getBounds() : L.latLngBounds([borrador.getLatLng(), borrador.getLatLng()]);
          if (pendiente || !mapa.getBounds().contains(b)) { encuadra(b.pad(2), {maxZoom: 19}); }
        }
      },
      // la vista se ha enseñado o ha cambiado de tamaño: que Leaflet lo sepa y haga el encuadre pendiente (o vuelva a la planta)
      ajustar: function () { mapa.invalidateSize(); reajusta(); },
      verPlanta: verPlanta,
      estado: function () { var c = mapa.getCenter();
                            return {focos: Object.keys(capas).length, sel: sel, marco: !!marco, enPlanta: enPlanta,
                                    dibujando: dib ? (dib.forma || dib.modelo) : null, borrador: !!borrador, zoom: mapa.getZoom(),
                                    centro: [c.lat, c.lng]}; }
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
    m = folium.Map(location=[emp["lat"], emp["lon"]], zoom_start=mapa_web.ZOOM_PLANTA, tiles=None,
                   control_scale=True, max_zoom=20)
    for i, (nombre, url, atr, nativo) in enumerate(mapa_web.fondos()):
        folium.TileLayer(tiles=url, attr=atr, name=nombre, overlay=False, control=True,
                         show=(i == 0), max_zoom=20, max_native_zoom=nativo).add_to(m)
    folium.LayerControl(position="topright", collapsed=True).add_to(m)
    js = (_JS.replace("__MAPA__", m.get_name())
             .replace("__COLORES__", json.dumps(COLORES))
             .replace("__PLANTA__", json.dumps([emp["lat"], emp["lon"]]))          # donde está la planta en el mapa principal
             .replace("__ZOOM_PLANTA__", str(mapa_web.ZOOM_PLANTA)))
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
    if m in ("superficie", "edificio") and len(u.get("poligono") or []) >= 3:          # «edificio»: el editor de edificios
        return {"tipo": "poligono", "puntos": [list(geo.a_geo(x, y)) for x, y in u["poligono"]]}
    if "x" not in u or "y" not in u:
        return None
    if m == "volumen":                                             # con su rumbo (una hilera no tiene por qué ir de este a oeste)
        from teodors.operacion import focos as F
        return {"tipo": "poligono", "puntos": [list(geo.a_geo(x, y)) for x, y in F.planta_volumen(foco)]}
    lat, lon = geo.a_geo(u["x"], u["y"])
    return {"tipo": "punto", "lat": lat, "lon": lon}


class VistaFocos(QWebEngineView):
    listo = QtCore.Signal()
    foco = QtCore.Signal(str)                  # id del foco pinchado en el plano
    ubicacion = QtCore.Signal(object)          # [(lat, lon), …] dibujados, o None si se cancela
    forma_dibujada = QtCore.Signal(str, object)  # la forma («rectangulo», «circulo», «poligono», «punto») y sus [(lat, lon), …]

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
        # diagnóstico (usuario, 2026-11-08: «no veo el mapa»): si la página no carga o su proceso se cae, que lo diga la actividad
        self._t0 = None
        self.loadFinished.connect(self._cargada)
        self._pagina.renderProcessTerminated.connect(
            lambda estado, codigo: log.error(f"Plano de focos: el proceso de la página web se ha cerrado ({estado.name}, código {codigo})"))
        tema.avisos.cambiado.connect(self.set_tema)

    def showEvent(self, evento):
        super().showEvent(evento)
        if self._listo:
            self.js("mapaApp.ajustar()")

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        if self._listo:
            self.js("mapaApp.ajustar()")

    def set_tema(self):
        """Otro estilo con el plano abierto: cambian las variables de color y no se recarga nada."""
        self._pagina.setBackgroundColor(QtGui.QColor(tema.c("fondo")))
        self.js(tema.js_variables())

    def cargar(self, emp):
        import time
        self._listo = False
        self._pendientes.clear()
        self._t0 = time.monotonic()
        ruta = escribir_html(emp)
        log.debug(f"Plano de focos: cargando {ruta}")
        self.setUrl(QtCore.QUrl.fromLocalFile(str(ruta)))

    def _cargada(self, ok):
        if not ok:
            log.warning(f"Plano de focos: la página no ha cargado ({self.url().toString()})")

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
            import time
            log.debug(f"Plano de focos listo en {time.monotonic() - (self._t0 or time.monotonic()):.1f} s")
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
            if p:
                self.forma_dibujada.emit(ev.get("forma") or "", [tuple(x) for x in p])

    def set_focos(self, lista_focos, encuadrar=False):
        lista = [{"id": f["id"], "nombre": f.get("nombre") or f["id"], "modelo": f["modelo"],
                  "geo": geometria(f)} for f in lista_focos]
        self.js(f"mapaApp.setFocos({json.dumps(lista)}, {'true' if encuadrar else 'false'})")

    def ver_planta(self, entera=False):
        """La vista de «Ver la planta» del mapa principal (centrado en la planta, `mapa_web.ZOOM_PLANTA`), que se queda mientras nadie mueva
        el plano; sin el plano cargado, en cuanto cargue. `entera` (un plano pequeño): centrado en la planta y con el zoom que haga falta
        para que quepan todos los focos, nunca más cerca que el de «Ver la planta»."""
        self.js(f"mapaApp.verPlanta({'true' if entera else 'false'})")

    def sin_leyenda(self):
        """Sin la leyenda de los modelos (un plano pequeño, junto a una lista que ya los lleva en color)."""
        self.js("document.querySelectorAll('.mapa-ley').forEach(function (e) { e.style.display = 'none'; })")

    def elegir(self, id_foco, mostrar=True):
        self.js(f"mapaApp.elegir({json.dumps(id_foco)}, {'true' if mostrar else 'false'})")

    def dibujar(self, modelo):
        self.setFocus()
        self.js(f"mapaApp.dibujar({json.dumps(modelo)})")

    def forma(self, forma):
        """Dibujar la ubicación del foco con una forma: «rectangulo», «circulo», «poligono» o «punto» (llega por `forma_dibujada`)."""
        self.setFocus()
        self.js(f"mapaApp.forma({json.dumps(forma)})")

    def borrador(self, foco, encuadrar=False):
        """El foco que se edita, discontinuo y aparte de los demás; None lo quita."""
        geo_ = geometria(foco) if foco is not None else None
        self.js(f"mapaApp.borrador({json.dumps(geo_)}, {'true' if encuadrar else 'false'})")
