# -*- coding: utf-8 -*-
"""Mapa base interactivo (folium/Leaflet) con un puente JS ↔ Python.

El HTML se genera UNA vez y después se actualiza con llamadas JS (`window.mapaApp.*`), sin
recargar: añadir capas o iconos de núcleos es instantáneo.
JS → Python: `console.log("MAPA:" + JSON)`, que recoge gui.mapa.PaginaMapa.

Fondos: los de la planta (`fuentes.fondos` de planta.json), solo servicios con licencia apta para un producto.
"""
import html
import json

import folium

from teodors import planta as config
from teodors.comun import registro
from teodors.comun.escalas import COLORES_VEL
from teodors.gui import tema, web

log = registro.get("mapa")


def fondos():
    """Los fondos del mapa de la planta, el primero el que se ve al abrir: [(nombre, url, atribución, zoom nativo máximo)]."""
    return [tuple(f) for f in config.pide("fuentes", "fondos")]


# Controles de Leaflet y del mapa, con los colores de gui/tema.py. También los usa el plano de focos.
CSS_BASE = """
<style>
__VARIABLES__
html,body{background:var(--fondo)}
.leaflet-container{background:var(--fondo);font-family:var(--letra);font-size:12.5px;color:var(--texto)}
.leaflet-container a{color:var(--acento_claro)}
.leaflet-bar,.leaflet-control-layers,.mapa-leyenda,.mapa-viento,.mapa-coords,.mapa-wx .wxb,
.leaflet-tooltip,.leaflet-popup-content-wrapper,.leaflet-popup-tip,.mapa-ley,.mapa-toast{
  background:var(--cristal)!important;color:var(--texto)!important;border:1px solid var(--linea)!important;
  -webkit-backdrop-filter:blur(10px) saturate(1.25);backdrop-filter:blur(10px) saturate(1.25);
  box-shadow:0 8px 26px var(--sombra)}
.leaflet-touch .leaflet-bar,.leaflet-bar{border:1px solid var(--linea);border-radius:10px;overflow:hidden}
.leaflet-bar a,.leaflet-touch .leaflet-bar a{background:transparent;color:var(--texto);border-bottom:1px solid var(--linea);
  width:34px;height:34px;line-height:34px;font-weight:400}
.leaflet-bar a:hover{background:var(--hover);color:var(--acento_claro)}
.leaflet-bar a:last-child{border-bottom:none}
.leaflet-control-layers{border-radius:12px}
.leaflet-touch .leaflet-control-layers{border:1px solid var(--linea)}
.leaflet-control-layers-toggle,.leaflet-touch .leaflet-control-layers-toggle,.leaflet-retina .leaflet-control-layers-toggle{
  width:38px;height:38px;position:relative;background-image:none!important}
/* con máscara, para que el icono siga al color del estilo */
.leaflet-control-layers-toggle::before{content:"";position:absolute;inset:8px;background:var(--texto);
  -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3 3 8l9 5 9-5z'/%3E%3Cpath d='m3 12.5 9 5 9-5'/%3E%3Cpath d='m3 17 9 5 9-5'/%3E%3C/svg%3E") center/contain no-repeat}
.leaflet-control-layers-expanded{padding:10px 14px 10px 10px;color:var(--texto);font-size:12.5px;line-height:1.7}
.leaflet-control-layers input{accent-color:var(--acento);vertical-align:-1px;margin-right:6px}
.leaflet-control-layers label{cursor:pointer}
.leaflet-control-layers label:hover{color:var(--acento_claro)}
.leaflet-control-layers-separator{border-top:1px solid var(--linea);margin:6px -10px 6px -10px}
.leaflet-control-attribution,.leaflet-container .leaflet-control-attribution{background:var(--cristal_suave)!important;color:var(--tenue);
  font-size:10.5px;border-radius:6px 0 0 0;padding:1px 6px}
.leaflet-container .leaflet-control-attribution a{color:var(--texto)!important}
.leaflet-control-attribution svg{display:none!important}
/* sin juntas entre teselas con el escalado de Windows (125 %…) */
.leaflet-tile-container img.leaflet-tile{width:256.6px!important;height:256.6px!important}
.leaflet-control-scale-line{background:var(--cristal_suave)!important;color:var(--tenue)!important;border:1px solid var(--linea)!important;border-top:none!important;
  font-size:10.5px;text-shadow:none!important}
.leaflet-tooltip{border-radius:10px;padding:8px 11px;font-size:12px;line-height:1.45;white-space:nowrap;
  background:var(--cristal_solido)!important}
.leaflet-tooltip-top:before{border-top-color:var(--cristal_solido)}
.leaflet-tooltip-bottom:before{border-bottom-color:var(--cristal_solido)}
.leaflet-tooltip-left:before{border-left-color:var(--cristal_solido)}
.leaflet-tooltip-right:before{border-right-color:var(--cristal_solido)}
.leaflet-popup-content-wrapper{border-radius:12px}
.leaflet-popup-content{margin:12px 14px;font-size:12.5px;line-height:1.45}
.leaflet-popup-close-button,.leaflet-container a.leaflet-popup-close-button{color:var(--tenue)!important;padding:6px 6px 0 0}
.leaflet-popup-tip{box-shadow:none}
.mapa-ficha h4{margin:0 0 6px;font-size:13px;font-weight:600}
.mapa-ficha table{border-collapse:collapse}
.mapa-ficha td{padding:1px 10px 1px 0;vertical-align:top}
.mapa-ficha td:first-child{color:var(--tenue);white-space:nowrap}
.mapa-toast{position:absolute;left:50%;bottom:26px;transform:translate(-50%,14px);z-index:1100;opacity:0;pointer-events:none;
  padding:9px 16px;border-radius:999px;font:500 13px var(--letra);max-width:70%;transition:opacity .25s,transform .25s}
.mapa-toast.si{opacity:1;transform:translate(-50%,0)}
.mapa-toast.fallo{background:var(--tinte_fallo)!important;color:var(--fallo)!important}
</style>
"""

_CSS = """
<style>
.mapa-pin{background:none;border:none}
.mapa-pin .halo{position:absolute;left:50%;top:15px;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;
  background:var(--acento);opacity:.22}
.mapa-pin svg{position:relative;filter:drop-shadow(0 3px 5px rgba(0,0,0,.55))}
.leaflet-top.mapa-delante{z-index:1001}
.mapa-coords{padding:3px 9px;border-radius:999px;font:11.5px Consolas,monospace;color:var(--tenue);box-shadow:none}
.mapa-wx{display:flex;gap:8px;align-items:flex-end}
/* tiempo, termómetro y brújula: sus iconos están pensados para un fondo oscuro, con cualquier estilo */
.mapa-wx .wxb{border-radius:14px;padding:8px 10px 6px;text-align:center;background:rgba(20,24,24,.86)!important;
  color:#eef2ee!important;border-color:rgba(255,255,255,.12)!important}
.mapa-wx .cap{margin-top:3px;font:600 11.5px var(--letra);white-space:nowrap}
.mapa-wx #wxic svg{width:92px;height:92px;display:block;margin:0 auto}
.escala-olor{filter:url(#escala-olor)}
.escala-gases{filter:url(#escala-gases)}
.mapa-viento{padding:8px 12px;border-radius:12px;font:12px var(--letra);line-height:1.5}
.mapa-viento b{font-weight:600}
.mapa-viento .sec{color:var(--tenue);font-size:11px}
.mapa-leyenda{display:none;box-sizing:border-box;padding:9px 12px;border-radius:12px;font:12px var(--letra);min-width:240px}
.mapa-leyenda h4{margin:0 0 6px;font-size:12px;font-weight:600}
.mapa-leyenda .parte + .parte{border-top:1px solid var(--linea);margin-top:9px;padding-top:9px}
.mapa-leyenda .barra{height:10px;border:none;border-radius:5px;margin:2px 0}
.mapa-leyenda .extremos{display:flex;justify-content:space-between;color:var(--tenue)}
.mapa-leyenda .clases{column-gap:16px}
.mapa-leyenda .clase{display:flex;align-items:center;gap:6px;white-space:nowrap;line-height:16px;
  font-size:11px;break-inside:avoid}
.mapa-leyenda .muestra{width:13px;height:10px;border:1px solid var(--linea);border-radius:2px;flex:none}
.mapa-leyenda .pct{color:var(--tenue);margin-left:auto;padding-left:8px}
.icono-industrial{background:none;border:none}
.mapa-tip-rosa{padding:8px 10px}
.mapa-est{background:none;border:none}
.mapa-est .ico{box-sizing:border-box;width:28px;height:28px;background:var(--chip);border:2px solid var(--estacion);
  border-radius:8px;box-shadow:0 2px 7px var(--sombra);display:flex;align-items:center;justify-content:center}
.mapa-est .cod{position:absolute;left:31px;top:5px;background:var(--cristal);color:var(--texto);
  font:600 11px var(--letra);padding:0 5px;border-radius:5px;line-height:17px;white-space:nowrap}
</style>
"""

# Placeholders __X__ en vez de llaves de format(): el JS está lleno de llaves.
_JS = """
<script>
(function () {
  var ESTADO = __ESTADO__;
  function enviar(o) { console.log("MAPA:" + JSON.stringify(o)); }
  function iconoPlanta() {
    var svg = '<div class="halo"></div><svg xmlns="http://www.w3.org/2000/svg" width="30" height="40" viewBox="0 0 30 40">'
      + '<path d="M15 1C7.3 1 1 7.2 1 14.8 1 25 15 39 15 39s14-14 14-24.2C29 7.2 22.7 1 15 1z" '
      + 'fill="var(--acento)" stroke="var(--sobre_acento)" stroke-width="1.5"/>'
      + '<circle cx="15" cy="15" r="5.5" fill="var(--sobre_acento)"/></svg>';
    return L.divIcon({html: svg, className: "mapa-pin", iconSize: [30, 40],
                      iconAnchor: [15, 39], popupAnchor: [0, -34]});
  }
  // Núcleos (como en el cajón): casa azul, balón naranja (marcadores estándar) y fábrica
  // amarilla (no hay amarillo entre los colores de AwesomeMarkers: chincheta propia). Los de antes
  // de la interfaz moderna (usuario, 2026-10-31); sus colores no cambian con el estilo.
  function iconoNucleo(familia) {
    if (familia === "residencial") {
      return L.AwesomeMarkers.icon({icon: "home", prefix: "fa", markerColor: "blue",
                                    iconColor: "white"});
    }
    if (familia === "deportivo") {
      return L.AwesomeMarkers.icon({icon: "futbol", prefix: "fa", markerColor: "orange",
                                    iconColor: "white"});
    }
    var html = '<div style="width:28px;height:28px;background:#f5c518;border:1px solid #9a7b00;'
      + 'border-radius:50% 50% 50% 0;transform:rotate(-45deg);'
      + 'box-shadow:1px 1px 3px rgba(0,0,0,.45);display:flex;align-items:center;'
      + 'justify-content:center"><i class="fa fa-industry" style="transform:rotate(45deg);'
      + 'color:#3b3000;font-size:14px"></i></div>';
    return L.divIcon({html: html, iconSize: [28, 40], iconAnchor: [14, 40],
                      className: "icono-industrial"});
  }
  // Estación meteorológica: mástil con anemómetro de cazoletas y veleta, con el código al lado.
  var SVG_ESTACION = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
    + 'stroke="var(--estacion)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    + '<line x1="12" y1="6" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/>'
    + '<line x1="4.5" y1="6" x2="19.5" y2="6"/>'
    + '<path d="M2.5 6a2 2 0 0 0 4 0z" fill="var(--estacion)"/><path d="M17.5 6a2 2 0 0 0 4 0z" fill="var(--estacion)"/>'
    + '<circle cx="12" cy="3" r="1.4" fill="var(--estacion)" stroke="none"/>'
    + '<line x1="6" y1="13" x2="18" y2="13"/><path d="M8.5 10.5 6 13l2.5 2.5"/>'
    + '<path d="M18 10.5v5l2.5 1v-7z" fill="var(--estacion)"/></svg>';
  function iconoEstacion(codigo) {
    return L.divIcon({html: '<div class="ico">' + SVG_ESTACION + '</div><span class="cod">'
                      + codigo + '</span>', className: "mapa-est", iconSize: [28, 28],
                      iconAnchor: [14, 14], tooltipAnchor: [0, -14]});
  }
  function iniciar() {
    L.Tooltip.mergeOptions({opacity: 1});
    var mapa = __MAPA__;
    var marcador = L.marker([0, 0], {icon: iconoPlanta(), zIndexOffset: 1000})
      .addTo(__G_PLANTA__);
    var gNucleos = __G_NUCLEOS__;
    var gEstaciones = __G_ESTACIONES__;
    var marcadoresEst = {};             // código -> marcador
    var limites = null;
    var control = __CONTROL__;
    var capas = {};                    // id -> {capa, leyenda, grupo}

    var Leyenda = L.Control.extend({
      options: {position: "bottomright"},
      onAdd: function () {
        var d = L.DomUtil.create("div", "mapa-leyenda");
        L.DomEvent.disableClickPropagation(d);
        L.DomEvent.disableScrollPropagation(d);
        return d;
      }
    });
    var leyenda = new Leyenda();
    mapa.addControl(leyenda);
    function pintaLeyenda() {
      var html = "";
      for (var id in capas) {
        if (mapa.hasLayer(capas[id].capa) && capas[id].leyenda) {
          html += '<div class="parte">' + capas[id].leyenda + "</div>";
        }
      }
      var d = leyenda.getContainer();
      d.innerHTML = html;
      d.style.display = html ? "block" : "none";
      igualaLeyenda();
      ajustaLeyenda();
    }
    // Con el panel del tiempo a la vista, la leyenda llega hasta su borde izquierdo, el del icono de día o
    // noche (usuario, 2026-10-31). Como mínimo: la de usos del suelo puede necesitar más sitio.
    function igualaLeyenda() {
      var w = document.querySelector(".mapa-wx");
      leyenda.getContainer().style.minWidth = (w && w.offsetWidth) ? w.offsetWidth + "px" : "";
    }
    // La leyenda muestra SIEMPRE todas las clases (decisión del usuario): sin barra de
    // desplazamiento; si no cabe en el alto del mapa, se reparte en 2, 3 o 4 columnas.
    // Alto libre: el del mapa menos el ICONO del selector de capas (arriba a la derecha: nunca
    // debe quedar tapado, o no se puede desplegar; pedido del usuario, 2026-10-22), los demás
    // controles de la misma esquina (panel del penacho) y la atribución de abajo.
    function ajustaLeyenda() {
      var d = leyenda.getContainer();
      if (d.style.display === "none") { return; }
      var listas = d.querySelectorAll(".clases");
      var otros = 0, hermanos = d.parentNode.children;
      for (var i = 0; i < hermanos.length; i++) {
        if (hermanos[i] !== d && hermanos[i].offsetHeight) { otros += hermanos[i].offsetHeight + 10; }
      }
      var disponible = mapa.getSize().y - 64 - otros - 30;
      for (var n = 1; n <= 6; n++) {
        listas.forEach(function (l) { l.style.columnCount = n; });
        if (d.offsetHeight <= disponible) { break; }
      }
    }
    mapa.on("resize", ajustaLeyenda);
    // El selector de capas (arriba a la derecha) se despliega hacia abajo y quedaba DETRÁS de la
    // leyenda y del panel del penacho: las dos esquinas tienen el mismo z-index (1000) en
    // Leaflet y gana la de abajo, que va después en la página. Con el ratón encima (o el foco
    // dentro), su esquina pasa delante.
    (function () {
      var sel = control.getContainer(), esquina = sel.parentNode;
      function delante(si) { esquina.classList.toggle("mapa-delante", si); }
      sel.addEventListener("mouseenter", function () { delante(true); });
      sel.addEventListener("mouseleave", function () { delante(false); });
      sel.addEventListener("focusin", function () { delante(true); });
      sel.addEventListener("focusout", function () { delante(sel.matches(":hover")); });
    })();
    // Capas del mismo grupo: EXCLUYENTES. La exclusión se hace DESPUÉS de que el control
    // termine de procesar el clic (setTimeout 0): Leaflet 1.9 primero lista las casillas
    // marcadas y luego añade las que no estén en el mapa, así que si se quitaba la anterior
    // durante ese recorrido la volvía a meter y ganaba la vieja (medido en la prueba). Fuera
    // del clic, al quitarla Leaflet repinta también su casilla.
    function idDe(capa) {
      for (var id in capas) { if (capas[id].capa === capa) { return id; } }
      return null;
    }
    mapa.on("overlayadd", function (e) {
      var nueva = idDe(e.layer);
      if (nueva !== null) { enviar({evento: "capa", id: nueva, visible: true}); }   // botones del panel
      if (nueva !== null && capas[nueva].grupo) {
        setTimeout(function () {
          if (!capas[nueva] || !mapa.hasLayer(capas[nueva].capa)) { return; }
          for (var j in capas) {
            if (j !== nueva && capas[j].grupo === capas[nueva].grupo
                && mapa.hasLayer(capas[j].capa)) { mapa.removeLayer(capas[j].capa); }
          }
          pintaLeyenda();
        }, 0);
      }
      pintaLeyenda();
    });
    mapa.on("overlayremove", function (e) {
      var id = idDe(e.layer);
      if (id !== null) { enviar({evento: "capa", id: id, visible: false}); }
      pintaLeyenda();
    });

    // Con `selector: false`, la capa solo se enciende con los botones del panel (usuario, 2026-10-31). Leaflet
    // solo avisa de las capas de su selector: estas avisan igual por su cuenta (exclusión, botones y leyenda).
    function ponCapa(capa, c) {
      capas[c.id] = {capa: capa, leyenda: c.leyenda, grupo: c.grupo};
      if (c.selector === false) {
        capa.on("add", function () { mapa.fire("overlayadd", {layer: capa}); });
        capa.on("remove", function () { mapa.fire("overlayremove", {layer: capa}); });
      } else {
        control.addOverlay(capa, c.nombre);
      }
      if (c.visible) { capa.addTo(mapa); }
      pintaLeyenda();
    }

    function claseEscala(escala) { return escala ? "escala-" + escala : ""; }

    window.mapaApp = {
      // Escalas de color de las concentraciones: las imágenes van en grises y el color lo pone este filtro, así
      // que cambiar de escala no rehace ninguna. Con sRGB: si no, la tabla se aplicaría en color lineal.
      setEscalas: function (e) {
        var caja = document.getElementById("mapa-escalas");
        if (!caja) {
          caja = document.createElement("div");
          caja.id = "mapa-escalas";
          caja.style.cssText = "position:absolute;width:0;height:0;overflow:hidden";
          document.body.appendChild(caja);
        }
        caja.innerHTML = "<svg width='0' height='0'>" + Object.keys(e).map(function (k) {
          document.documentElement.style.setProperty("--escala-" + k, e[k].gradiente);
          return "<filter id='escala-" + k + "' color-interpolation-filters='sRGB' x='0' y='0' width='1' height='1'>"
            + "<feComponentTransfer><feFuncR type='table' tableValues='" + e[k].r + "'/>"
            + "<feFuncG type='table' tableValues='" + e[k].g + "'/><feFuncB type='table' tableValues='" + e[k].b + "'/>"
            + "</feComponentTransfer></filter>";
        }).join("") + "</svg>";
      },
      // botones «Ver …» del panel: enciende o apaga una capa (la exclusión del grupo la hace
      // el aviso overlayadd)
      verCapa: function (id, si) {
        if (!capas[id]) { return false; }
        if (si && !mapa.hasLayer(capas[id].capa)) { mapa.addLayer(capas[id].capa); }
        if (!si && mapa.hasLayer(capas[id].capa)) { mapa.removeLayer(capas[id].capa); }
        return true;
      },
      setCapaImagen: function (c) {
        if (capas[c.id]) {
          control.removeLayer(capas[c.id].capa);
          mapa.removeLayer(capas[c.id].capa);
        }
        var capa = c.imagenes                // varias imágenes: la zona cercana con más detalle
          ? L.layerGroup(c.imagenes.map(function (i) {
              return L.imageOverlay(i.url, i.limites, {opacity: c.opacidad, interactive: false,
                                                       className: claseEscala(c.escala)}); }))
          : L.imageOverlay(c.url, c.bounds, {opacity: c.opacidad, interactive: false});
        ponCapa(capa, c);
      },
      setCapaGeoJSON: function (c) {      // {id, nombre, datos, visible, leyenda, grupo}
        if (capas[c.id]) {
          control.removeLayer(capas[c.id].capa);
          mapa.removeLayer(capas[c.id].capa);
        }
        var capa = L.geoJSON(c.datos, {
          style: function (f) {
            return {color: "#333", weight: 0.5, fillColor: f.properties.color,
                    fillOpacity: 0.85};
          },
          onEachFeature: function (f, l) {
            if (f.properties.texto) { l.bindTooltip(f.properties.texto, {sticky: true}); }
          }
        });
        ponCapa(capa, c);
      },
      // Muchos puntos (receptores): círculos en canvas, sin interacción, un estilo por clase.
      setCapaPuntos: function (c) {      // {id, nombre, puntos: [[lat, lon, k]], estilos, ...}
        if (capas[c.id]) {
          control.removeLayer(capas[c.id].capa);
          mapa.removeLayer(capas[c.id].capa);
        }
        var lienzo = L.canvas({padding: 0.5});
        var capa = L.layerGroup();
        c.puntos.forEach(function (p) {
          var e = c.estilos[p[2]];
          L.circleMarker([p[0], p[1]], {renderer: lienzo, radius: e.radio, stroke: false,
                                        fillColor: e.color, fillOpacity: 0.9,
                                        interactive: false}).addTo(capa);
        });
        ponCapa(capa, c);
      },
      quitarCapa: function (id) {
        if (!capas[id]) { return; }
        control.removeLayer(capas[id].capa);
        mapa.removeLayer(capas[id].capa);
        delete capas[id];
        pintaLeyenda();
      },
      capasVisibles: function () {
        var v = [];
        for (var id in capas) { if (mapa.hasLayer(capas[id].capa)) { v.push(id); } }
        return v;
      },
      setPlanta: function (p) {
        marcador.setLatLng([p.lat, p.lon]);
        marcador.bindPopup("<b>" + p.nombre + "</b><br>" + p.lat.toFixed(6) + ", "
          + p.lon.toFixed(6));
      },
      setNucleos: function (lista) {      // [{familia, lat, lon, texto}]
        gNucleos.clearLayers();
        lista.forEach(function (n) {
          L.marker([n.lat, n.lon], {icon: iconoNucleo(n.familia)})
            .bindTooltip(n.texto, {sticky: true}).addTo(gNucleos);
        });
      },
      // [{codigo, lat, lon, texto, lateral}]: con `lateral` (tooltip grande, con la rosa) se
      // abre a izquierda o derecha según el lado del mapa, para que no se salga por arriba.
      setEstaciones: function (lista) {
        gEstaciones.clearLayers();
        marcadoresEst = {};
        lista.forEach(function (s) {
          var op = s.lateral ? {direction: "auto", offset: [15, 0], className: "mapa-tip-rosa",
                                opacity: 1}
                             : {direction: "top", offset: [0, -15]};
          marcadoresEst[s.codigo] = L.marker([s.lat, s.lon],
                                             {icon: iconoEstacion(s.codigo), zIndexOffset: 500})
            .bindTooltip(s.texto, op)
            .on("click", function () { enviar({evento: "estacion", codigo: s.codigo}); })
            .addTo(gEstaciones);
        });
      },
      abrirEstacion: function (codigo) {      // abre el tooltip (pruebas y, más adelante, panel)
        if (marcadoresEst[codigo]) { marcadoresEst[codigo].openTooltip(); }
      },
      setLimites: function (b) { limites = b; },    // [[s, o], [n, e]] del terreno
      // Aviso breve sobre el mapa: lo que antes solo salía en la consola
      aviso: function (texto, tipo) {
        var d = mapa.getContainer().querySelector(".mapa-toast");
        if (!d) { d = L.DomUtil.create("div", "mapa-toast", mapa.getContainer()); }
        d.textContent = texto;
        d.className = "mapa-toast" + (tipo === "fallo" ? " fallo" : "");
        void d.offsetWidth;
        d.classList.add("si");
        clearTimeout(mapaApp._tAviso);
        mapaApp._tAviso = setTimeout(function () { d.classList.remove("si"); }, tipo === "fallo" ? 9000 : 4500);
      },
      // Ficha flotante en un punto (clic en el mapa, estación)
      ficha: function (lat, lon, html) {
        L.popup({maxWidth: 340, autoPan: true}).setLatLng([lat, lon]).setContent(html).openOn(mapa);
      },
      // ×2 de zoom (un nivel más) en los dos (usuario, 2026-10-29): la región, centrada en la
      // planta, a un nivel más del que encuadra todo el terreno; la planta, a 18 (antes 16; a 17 se
      // quedaba corto)
      centrar: function () {
        if (limites) {
          mapa.setView(marcador.getLatLng(), mapa.getBoundsZoom(limites, false, L.point(20, 20)) + 1);
        }
      },
      verPlanta: function () { mapa.setView(marcador.getLatLng(), 18); },
      estado: function () {
        var n = {};
        gNucleos.eachLayer(function () { n.total = (n.total || 0) + 1; });
        gEstaciones.eachLayer(function (l) {
          n.est = (n.est || 0) + 1;
          if (String(l.getTooltip().getContent()).indexOf("<svg") >= 0) { n.rosas = (n.rosas || 0) + 1; }
        });
        return {planta: marcador.getLatLng(), nucleos: n.total || 0, estaciones: n.est || 0,
                rosas: n.rosas || 0,
                poligonos: document.querySelectorAll("path.leaflet-interactive").length};
      }
    };

    // ── Viento en superficie (nivel 1 de viento3d): canvas animado ──────────────────────
    // Adaptado de la capa de viento del cajón (probada), con su
    // arreglo de la desalineación: la rejilla se proyecta SIN redondear a píxeles y los
    // vectores salen de las esquinas opuestas. u, v respecto a la cuadrícula UTM (i este,
    // j norte). Datos de Python: u, v por hora en int16 (centésimas) y base64.
    var V = null, VL = null;               // VL: la biblioteca del motor de la planta
    function crearViento() {
      // En un panel PROPIO de Leaflet (z-index 450): encima del penacho (overlayPane, 400) y
      // DEBAJO de los iconos (600) y de los tooltips (650) con las tablas y las rosas (pedido
      // del usuario, 2026-10-24). Antes colgaba del contenedor con z-index 450 y tapaba todo
      // el mapa, tooltips incluidos. Se dibuja en coordenadas de PANTALLA: en geom() se coloca
      // en la esquina del contenedor, compensando el desplazamiento del panel.
      var pv = mapa.getPane("mapaViento") || mapa.createPane("mapaViento");
      pv.style.zIndex = 450; pv.style.pointerEvents = "none";
      var cv = document.createElement("canvas");
      cv.style.cssText = "position:absolute;left:0;top:0;pointer-events:none";
      pv.appendChild(cv);
      var g = cv.getContext("2d");
      var W = null, NX = 0, NY = 0, NC = 0, CL = null, U = [], Vv = [];
      var modo = null, Uc = null, Vc = null, fa = 0, ff = 0, anim = null, parts = [];
      var P0, Ei, Ej, det, E, Nv, celda;
      function dec(b64) {
        var s = atob(b64), n = s.length, b = new Uint8Array(n);
        for (var i = 0; i < n; i++) { b[i] = s.charCodeAt(i); }
        var e = new Int16Array(b.buffer), f = new Float32Array(e.length);
        for (var k = 0; k < e.length; k++) { f[k] = e[k] * W.escala; }
        return f;
      }
      function pto(lat, lon) {                  // a pantalla SIN redondear (guía 07)
        var lp = mapa.project(L.latLng(lat, lon)).subtract(mapa.getPixelOrigin());
        return mapa.layerPointToContainerPoint(lp);
      }
      function geom() {
        var s = mapa.getSize();
        if (cv.width !== s.x || cv.height !== s.y) { cv.width = s.x; cv.height = s.y; }
        L.DomUtil.setPosition(cv, mapa.containerPointToLayerPoint([0, 0]));
        var a = pto(W.esquinas.c00[0], W.esquinas.c00[1]);
        var b = pto(W.esquinas.c10[0], W.esquinas.c10[1]);
        var c = pto(W.esquinas.c01[0], W.esquinas.c01[1]);
        P0 = a;
        Ei = [(b.x - a.x) / (NX - 1), (b.y - a.y) / (NX - 1)];
        Ej = [(c.x - a.x) / (NY - 1), (c.y - a.y) / (NY - 1)];
        det = Ei[0] * Ej[1] - Ei[1] * Ej[0];
        E = [Ei[0] / W.dg, Ei[1] / W.dg];
        Nv = [Ej[0] / W.dg, Ej[1] / W.dg];
        celda = Math.hypot(Ei[0], Ei[1]);
        if (VL) {
          var a0 = pto(VL.esq.c00[0], VL.esq.c00[1]), b0 = pto(VL.esq.c10[0], VL.esq.c10[1]), c0 = pto(VL.esq.c01[0], VL.esq.c01[1]);
          VL.P = a0;
          VL.Ei = [(b0.x - a0.x) / (VL.nx - 1), (b0.y - a0.y) / (VL.nx - 1)];
          VL.Ej = [(c0.x - a0.x) / (VL.ny - 1), (c0.y - a0.y) / (VL.ny - 1)];
          VL.det = VL.Ei[0] * VL.Ej[1] - VL.Ei[1] * VL.Ej[0];
        }
      }
      function campo() {
        var h = Math.min(fa, U.length - 1), h2 = Math.min(h + 1, U.length - 1), f = ff;
        var u1 = U[h], v1 = Vv[h], u2 = U[h2], v2 = Vv[h2];
        for (var c = 0; c < NC; c++) { Uc[c] = u1[c] + (u2[c] - u1[c]) * f; Vc[c] = v1[c] + (v2[c] - v1[c]) * f; }
      }
      // Motor de la planta (tareas/viento_local_biblioteca.py): la dirección y la velocidad de la zona en la planta eligen
      // los dos campos de la biblioteca más cercanos; mezclados, valen para ese instante.
      function campoLocal() {
        if (!VL || !W || !W.origen) { return; }
        var gi = (VL.cx - W.origen[0]) / W.dg, gj = (VL.cy - W.origen[1]) / W.dg, i = Math.floor(gi), j = Math.floor(gj);
        var fx = gi - i, fy = gj - j, c = j * NX + i;
        var u = (Uc[c] * (1 - fx) + Uc[c + 1] * fx) * (1 - fy) + (Uc[c + NX] * (1 - fx) + Uc[c + NX + 1] * fx) * fy;
        var v = (Vc[c] * (1 - fx) + Vc[c + 1] * fx) * (1 - fy) + (Vc[c + NX] * (1 - fx) + Vc[c + NX + 1] * fx) * fy;
        var vel = Math.hypot(u, v), a = ((Math.atan2(-u, -v) * 180 / Math.PI + 360) % 360) / VL.paso;
        var k0 = Math.floor(a) % VL.U.length, k1 = (k0 + 1) % VL.U.length, f = a - Math.floor(a);
        var U0 = VL.U[k0], U1 = VL.U[k1], V0 = VL.V[k0], V1 = VL.V[k1], Lu = VL.Lu, Lv = VL.Lv;
        for (var q = 0; q < Lu.length; q++) {
          Lu[q] = vel * (U0[q] + (U1[q] - U0[q]) * f);
          Lv[q] = vel * (V0[q] + (V1[q] - V0[q]) * f);
        }
      }
      var pesoL = 0, suL = 0, svL = 0;
      function sumaL(q, w) { var x = VL.Lu[q]; if (x === x) { pesoL += w; suL += w * x; svL += w * VL.Lv[q]; } }
      // A menos del radio del segmento entre los dos puntos de la planta manda este motor, con un fundido hasta el borde; null dentro de un edificio. Con su PROPIA colocación
      // en pantalla: la de la zona, una sola transformación para 50 km, se desvía ~40 m en el centro (medido): con celdas
      // de 400 m no se nota, pero las estelas quedarían fuera de los edificios.
      function enPlanta(x, y, u, v) {
        if (!VL || !VL.P) { return [u, v]; }
        var ex = x - VL.P.x, ey = y - VL.P.y;
        var li = (ex * VL.Ej[1] - ey * VL.Ej[0]) / VL.det, lj = (VL.Ei[0] * ey - VL.Ei[1] * ex) / VL.det;
        var sx = VL.i2 - VL.ic, sy = VL.j2 - VL.jc;
        var t = Math.min(1, Math.max(0, ((li - VL.ic) * sx + (lj - VL.jc) * sy) / (sx * sx + sy * sy)));
        var d = Math.hypot(li - VL.ic - t * sx, lj - VL.jc - t * sy) * VL.dx;
        if (d >= VL.rb) { return [u, v]; }
        var a = Math.floor(li), b = Math.floor(lj);
        if (a < 0 || b < 0 || a >= VL.nx - 1 || b >= VL.ny - 1) { return [u, v]; }
        var ax = li - a, ay = lj - b, q = b * VL.nx + a;
        pesoL = 0; suL = 0; svL = 0;
        sumaL(q, (1 - ax) * (1 - ay)); sumaL(q + 1, ax * (1 - ay));
        sumaL(q + VL.nx, (1 - ax) * ay); sumaL(q + VL.nx + 1, ax * ay);
        if (pesoL < 0.5) { return null; }
        var w = d <= VL.r ? 1 : (VL.rb - d) / (VL.rb - VL.r);
        return [u + (suL / pesoL - u) * w, v + (svL / pesoL - v) * w];
      }
      function muestra(x, y) {
        var dx = x - P0.x, dy = y - P0.y;
        var gi = (dx * Ej[1] - dy * Ej[0]) / det, gj = (Ei[0] * dy - Ei[1] * dx) / det;
        if (gi < CL[0] || gj < CL[2] || gi > CL[1] || gj > CL[3]) { return null; }
        var i = Math.min(Math.floor(gi), NX - 2), j = Math.min(Math.floor(gj), NY - 2);
        var fx = gi - i, fy = gj - j, c = j * NX + i;
        var u = (Uc[c] * (1 - fx) + Uc[c + 1] * fx) * (1 - fy) + (Uc[c + NX] * (1 - fx) + Uc[c + NX + 1] * fx) * fy;
        var v = (Vc[c] * (1 - fx) + Vc[c + 1] * fx) * (1 - fy) + (Vc[c + NX] * (1 - fx) + Vc[c + NX + 1] * fx) * fy;
        return enPlanta(x, y, u, v);
      }
      function pant(u, v) { return [u * E[0] + v * Nv[0], u * E[1] + v * Nv[1]]; }
      function color(sp) {
        var p = W.pal, i = Math.min(p.length - 1, Math.floor(p.length * Math.min(sp, W.vmax) / W.vmax));
        return p[Math.min(i, p.length - 1)];
      }
      function cajaRejilla() {
        var xs = [], ys = [];
        [[CL[0], CL[2]], [CL[1], CL[2]], [CL[0], CL[3]], [CL[1], CL[3]]].forEach(function (q) {
          xs.push(P0.x + q[0] * Ei[0] + q[1] * Ej[0]); ys.push(P0.y + q[0] * Ei[1] + q[1] * Ej[1]);
        });
        return [Math.max(0, Math.min.apply(null, xs)), Math.max(0, Math.min.apply(null, ys)),
                Math.min(cv.width, Math.max.apply(null, xs)), Math.min(cv.height, Math.max.apply(null, ys))];
      }
      function punta(x, y, dx, dy, hl, col) {
        var hw = hl * 0.55; g.beginPath(); g.moveTo(x, y);
        g.lineTo(x - dx * hl - dy * hw, y - dy * hl + dx * hw); g.lineTo(x - dx * hl + dy * hw, y - dy * hl - dx * hw);
        g.closePath(); g.fillStyle = col; g.fill();
      }
      // Puntos de dibujo separados `sep` px en pantalla (menos con más cantidad), fijos respecto a la rejilla y
      // solo en lo que se ve: valen para cualquier zoom, también cuando una celda ocupa más que `sep`.
      function malla(sep, fn) {
        var paso = sep / Math.sqrt(W.factor || 1) / Math.max(celda, 0.01), m = 40, gis = [], gjs = [];
        [[-m, -m], [cv.width + m, -m], [-m, cv.height + m], [cv.width + m, cv.height + m]].forEach(function (q) {
          var dx = q[0] - P0.x, dy = q[1] - P0.y;
          gis.push((dx * Ej[1] - dy * Ej[0]) / det); gjs.push((Ei[0] * dy - Ei[1] * dx) / det);
        });
        var i0 = Math.max(CL[0], Math.min.apply(null, gis)), i1 = Math.min(CL[1], Math.max.apply(null, gis)),
            j0 = Math.max(CL[2], Math.min.apply(null, gjs)), j1 = Math.min(CL[3], Math.max.apply(null, gjs));
        for (var gj = Math.ceil(j0 / paso) * paso; gj <= j1; gj += paso) {
          for (var gi = Math.ceil(i0 / paso) * paso; gi <= i1; gi += paso) {
            fn(P0.x + gi * Ei[0] + gj * Ej[0], P0.y + gi * Ei[1] + gj * Ej[1]);
          }
        }
      }
      function flechas() {
        malla(34, function (x, y) {
          var s = muestra(x, y); if (!s) { return; }
          var sp = Math.hypot(s[0], s[1]); if (sp < 0.05) { return; }
          var d = pant(s[0], s[1]), n = Math.hypot(d[0], d[1]); if (!n) { return; }
          var dx = d[0] / n, dy = d[1] / n, Lg = Math.max(14, 38 * Math.min(sp, W.vmax) / W.vmax),
              col = W.blanco ? "#ffffff" : color(sp);
          var x0 = x - dx * Lg / 2, y0 = y - dy * Lg / 2, x1 = x + dx * Lg / 2, y1 = y + dy * Lg / 2, hl = Math.max(6, Lg * 0.34);
          g.lineCap = "round";
          g.strokeStyle = "rgba(20,20,40,.75)"; g.lineWidth = 4.2;
          g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.stroke();
          punta(x1 + dx * 1.2, y1 + dy * 1.2, dx, dy, hl + 2.5, "rgba(20,20,40,.75)");
          g.strokeStyle = col; g.lineWidth = 2.2;
          g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.stroke(); punta(x1, y1, dx, dy, hl, col);
        });
      }
      // Líneas de corriente: desde cada punto de la malla, el recorrido del viento hacia delante y hacia atrás
      // (método del punto medio, en px de pantalla), con una punta en el centro para ver el sentido. Agrupadas
      // por clase de velocidad para dibujarlas de una vez.
      function lineas() {
        var np = W.pal.length, trazos = [], puntas = [], H = 4, N = 20, k;
        for (k = 0; k < np; k++) { trazos.push(new Path2D()); puntas.push(new Path2D()); }
        function dir(x, y, sentido) {
          var s = muestra(x, y); if (!s || Math.hypot(s[0], s[1]) < 0.05) { return null; }
          var d = pant(s[0], s[1]), n = Math.hypot(d[0], d[1]);
          return n ? [sentido * d[0] / n, sentido * d[1] / n] : null;
        }
        function tramo(camino, x, y, sentido) {
          camino.moveTo(x, y);
          for (var q = 0; q < N; q++) {
            var a = dir(x, y, sentido); if (!a) { return; }
            var b = dir(x + a[0] * H / 2, y + a[1] * H / 2, sentido); if (!b) { return; }
            x += b[0] * H; y += b[1] * H;
            camino.lineTo(x, y);
          }
        }
        malla(46, function (x, y) {
          var s = muestra(x, y); if (!s) { return; }
          var sp = Math.hypot(s[0], s[1]), a = dir(x, y, 1); if (!a) { return; }
          var c = Math.min(np - 1, Math.floor(np * Math.min(sp, W.vmax) / W.vmax));
          tramo(trazos[c], x, y, 1); tramo(trazos[c], x, y, -1);
          puntas[c].moveTo(x + a[0] * 6, y + a[1] * 6);
          puntas[c].lineTo(x - a[0] * 3 - a[1] * 3.6, y - a[1] * 3 + a[0] * 3.6);
          puntas[c].lineTo(x - a[0] * 3 + a[1] * 3.6, y - a[1] * 3 - a[0] * 3.6);
          puntas[c].closePath();
        });
        g.lineCap = "round"; g.lineJoin = "round";
        g.strokeStyle = "rgba(10,15,25,.4)";                     // contorno: se ven sobre cualquier fondo
        for (k = 0; k < np; k++) { g.lineWidth = 3.2; g.stroke(trazos[k]); g.lineWidth = 2.2; g.stroke(puntas[k]); }
        g.lineWidth = 1.5;
        for (k = 0; k < np; k++) {
          var col = W.blanco ? "rgba(255,255,255," + (0.6 + 0.4 * k / Math.max(1, np - 1)).toFixed(2) + ")" : W.pal[k];
          g.strokeStyle = col; g.fillStyle = col;
          g.stroke(trazos[k]); g.fill(puntas[k]);
        }
      }
      var msDibujo = 0;
      // Partículas ajustadas al zoom y al equipo (pedido del usuario, 2026-10-22: al acercar
      // iba lento). (1) El número sale del área de la rejilla EN PANTALLA con una densidad
      // moderada y un tope; (2) se mide lo que tarda cada fotograma y se quitan partículas si
      // va lento o se añaden si va sobrado; (3) ~30 fotogramas/s; (4) los trazos se agrupan
      // por clase de velocidad: 5 órdenes de dibujo por fotograma en vez de una por partícula.
      var DENS = 1 / 260, NMIN = 250, NMAX = 2500, VIDA = 45, objetivo = 0, tPrev = 0,
          msMedia = 0, cuadros = 0, msTotal = 0;
      function nueva(B, edad) {
        return {x: B[0] + Math.random() * (B[2] - B[0]), y: B[1] + Math.random() * (B[3] - B[1]),
                a: edad ? Math.floor(Math.random() * VIDA) : 0};
      }
      function siembra() {
        var B = cajaRejilla();
        var op = W.opciones || {};                              // viento de muestra, calmado
        var f = W.factor || 1;                                  // cantidad elegida en la configuración
        objetivo = Math.max(NMIN, Math.min((op.nmax || NMAX) * f, Math.round((B[2] - B[0]) * (B[3] - B[1]) * (op.dens || DENS) * f)));
        parts = [];
        for (var i = 0; i < objetivo; i++) { parts.push(nueva(B, true)); }
        msMedia = 0; tPrev = 0;
      }
      function particulas(t) {
        anim = requestAnimationFrame(particulas);
        if (tPrev && t - tPrev < ((W.opciones && W.opciones.ms) || 30)) { return; }   // ~30 fotogramas por segundo
        tPrev = t;
        cuadro(true);
      }
      // color de la clase de velocidad k: con W.blanco, blanco más opaco cuanto más viento (así
      // no se confunde con los colores del penacho); si no, la escala elegida
      function tinta(k) {
        if (!W.blanco) { return W.pal[k]; }
        var n = W.pal.length, a = n > 1 ? 0.35 + 0.65 * k / (n - 1) : 1;
        return "rgba(255,255,255," + a.toFixed(2) + ")";
      }
      function cuadro(ajusta) {                                  // un fotograma
        var t0 = performance.now();
        g.globalCompositeOperation = "destination-in"; g.fillStyle = "rgba(0,0,0,0.88)";
        g.fillRect(0, 0, cv.width, cv.height); g.globalCompositeOperation = "source-over";
        var B = cajaRejilla(), np = W.pal.length, cubos = [], k;
        for (k = 0; k < np; k++) { cubos.push([]); }
        for (var i = 0; i < parts.length; i++) {
          var p = parts[i], s = muestra(p.x, p.y);
          if (!s || p.a > VIDA) { parts[i] = nueva(B, false); continue; }
          var sp = Math.hypot(s[0], s[1]), d = pant(s[0], s[1]), dn = Math.hypot(d[0], d[1]);
          if (!dn || sp < 0.05) { p.a += 2; continue; }
          var r = Math.min(sp, W.vmax) / W.vmax, paso = 1.2 + 5.6 * r;   // px por fotograma
          var nx = p.x + d[0] / dn * paso, ny = p.y + d[1] / dn * paso;
          cubos[Math.min(np - 1, Math.floor(np * r))].push(p.x, p.y, nx, ny);
          p.x = nx; p.y = ny; p.a++;
        }
        var z = mapa.getZoom();
        g.lineWidth = 1.6 * Math.min(1.9, Math.max(1, 1 + (z - 11) * 0.25)); g.lineCap = "round";
        if (W.opciones && W.opciones.suelto) {                  // como antes (para medir)
          for (k = 0; k < np; k++) {
            for (var jj = 0; jj < cubos[k].length; jj += 4) {
              g.strokeStyle = tinta(k); g.beginPath(); g.moveTo(cubos[k][jj], cubos[k][jj + 1]);
              g.lineTo(cubos[k][jj + 2], cubos[k][jj + 3]); g.stroke();
            }
          }
          cubos = [];
        }
        for (k = 0; k < cubos.length; k++) {
          var c = cubos[k];
          if (!c.length) { continue; }
          g.strokeStyle = tinta(k); g.beginPath();
          for (var j = 0; j < c.length; j += 4) { g.moveTo(c[j], c[j + 1]); g.lineTo(c[j + 2], c[j + 3]); }
          g.stroke();
        }
        var ms = performance.now() - t0;                        // ajuste al equipo
        msMedia = msMedia ? msMedia * 0.9 + ms * 0.1 : ms;
        cuadros++; msTotal += ms;
        if (!ajusta) { return ms; }
        if (msMedia > 14 && parts.length > NMIN) {
          parts.length = Math.max(NMIN, Math.floor(parts.length * 0.85));
        } else if (msMedia < 6 && parts.length < objetivo) {
          for (var q = 0, nq = Math.ceil(parts.length * 0.05); q < nq; q++) { parts.push(nueva(B, true)); }
        }
        return ms;
      }
      function para() { if (anim) { cancelAnimationFrame(anim); anim = null; } }
      function dibuja() {
        if (!W || modo === "particulas" || !modo) { return; }
        var t0 = performance.now();
        g.clearRect(0, 0, cv.width, cv.height);
        if (modo === "flechas") { flechas(); } else { lineas(); }
        msDibujo = performance.now() - t0;
      }
      function pon(m) {
        para(); modo = m; g.clearRect(0, 0, cv.width, cv.height);
        if (!W || !m) { return; }
        geom();
        if (m === "particulas") { siembra(); anim = requestAnimationFrame(particulas); } else { dibuja(); }
        info();
      }
      mapa.on("zoomstart movestart", function () { para(); g.clearRect(0, 0, cv.width, cv.height); });
      mapa.on("moveend zoomend resize", function () { if (modo) { pon(modo); } });
      // recuadro con la hora y la escala de colores
      var Info = L.Control.extend({
        options: {position: "bottomleft"},
        onAdd: function () { var d = L.DomUtil.create("div", "mapa-viento"); d.style.display = "none"; return d; }
      });
      var caja = new Info(); mapa.addControl(caja);
      function info() {
        var d = caja.getContainer();
        if (!W || !modo) { d.style.display = "none"; return; }
        var h = Math.min(fa, W.horas.length - 1), lim = [];
        for (var k = 0; k < W.pal.length; k++) {
          var a = (W.vmax * k / W.pal.length).toFixed(1).replace(".", ","),
              b = k === W.pal.length - 1 ? "+" : "–" + (W.vmax * (k + 1) / W.pal.length).toFixed(1).replace(".", ",");
          lim.push("<span style='display:inline-block;width:10px;height:10px;background:" + W.pal[k]
                   + ";margin:0 3px 0 6px'></span>" + a + b);
        }
        d.style.display = "block";
        d.innerHTML = "<b>Viento</b> · media " + String(W.media[h]).replace(".", ",") + " m/s · máx. "
          + String(W.maxima[h]).replace(".", ",") + " m/s"
          + (W.blanco ? "" : "<br><span class='sec'>m/s:" + lim.join("") + "</span>");
      }
      var capas = {};
      var FORMAS = [["particulas", "Viento · partículas"], ["lineas", "Viento · líneas de corriente"],
                    ["flechas", "Viento · flechas"]];
      FORMAS.forEach(function (e) {
          var c = L.layerGroup();
          c.onAdd = function () {
            // fuera del clic: dentro, Leaflet no actualiza las casillas y la anterior volvía a entrar
            setTimeout(function () {
              Object.keys(capas).forEach(function (k) { if (k !== modo && mapa.hasLayer(capas[k])) { mapa.removeLayer(capas[k]); } });
            }, 0);
            pon(e[0]); enviar({evento: "formaViento", modo: e[0]}); return this;
          };
          c.onRemove = function () { if (modo === e[0]) { para(); modo = null; g.clearRect(0, 0, cv.width, cv.height); info(); } return this; };
          capas[e[0]] = c;
        });
      var enControl = false;
      return {
        set: function (datos) {
          W = datos; NX = W.nx; NY = W.ny; NC = NX * NY; CL = W.clip || [0, NX - 1, 0, NY - 1];
          U = W.u.map(dec); Vv = W.v.map(dec); Uc = new Float32Array(NC); Vc = new Float32Array(NC);
          fa = Math.min(fa, U.length - 1); ff = 0; campo(); campoLocal();
          if (!enControl) {
            FORMAS.forEach(function (e) { control.addOverlay(capas[e[0]], e[1]); });
            enControl = true;
          }
          W.modo = W.modo || "particulas";
          if (mapa.hasLayer(capas[W.modo])) { pon(W.modo); } else { capas[W.modo].addTo(mapa); }
        },
        hora: function (a, frac) { if (!W) { return; } fa = a; ff = frac || 0; campo(); campoLocal(); dibuja(); info(); },
        // la biblioteca del motor de la planta ha llegado
        refresca: function () { if (W) { campoLocal(); if (modo) { pon(modo); } } },
        // el viento en un punto (pruebas)
        en: function (lat, lon) { if (!W) { return null; } geom(); var p = pto(lat, lon); return muestra(p.x, p.y); },
        // forma, color, escala y cantidad, sin volver a cargar el viento
        estilo: function (e) {
          if (!W) { return; }
          W.blanco = e.blanco; W.factor = e.factor; W.modo = e.modo; W.pal = e.pal;
          if (mapa.hasLayer(capas[e.modo])) { pon(e.modo); } else { capas[e.modo].addTo(mapa); }
        },
        quitar: function () {
          Object.keys(capas).forEach(function (k) { if (mapa.hasLayer(capas[k])) { mapa.removeLayer(capas[k]); } });
          if (enControl) { FORMAS.forEach(function (e) { control.removeLayer(capas[e[0]]); }); enControl = false; }
          W = null; info();
        },
        // medición (pruebas): n fotogramas seguidos con las partículas actuales, sin ajuste
        bench: function (n) {
          if (modo !== "particulas") { return null; }
          var t0 = performance.now();
          for (var i = 0; i < n; i++) { cuadro(false); }
          return {ms_por_cuadro: Math.round((performance.now() - t0) / n * 100) / 100,
                  particulas: parts.length, lienzo: [cv.width, cv.height], zoom: mapa.getZoom()};
        },
        estado: function () { return {modo: modo, hora: fa, frac: ff, nx: NX, ny: NY, particulas: parts.length,
                                       objetivo: objetivo, ms_media: Math.round(msMedia * 10) / 10,
                                       cuadros: cuadros, ms_por_cuadro: cuadros ? Math.round(msTotal / cuadros * 10) / 10 : 0,
                                       ms_dibujo: Math.round(msDibujo * 10) / 10, blanco: !!(W && W.blanco),
                                       local: !!(VL && W), direcciones_local: VL ? VL.U.length : 0,
                                       zoom: mapa.getZoom()}; }
      };
    }
    mapaApp.setViento = function (datos) { if (!V) { V = crearViento(); } V.set(datos); };
    mapaApp.vientoHora = function (a, frac) { if (V) { V.hora(a, frac); } };
    mapaApp.quitarViento = function () { if (V) { V.quitar(); } };
    mapaApp.vientoEstilo = function (e) { if (V) { V.estilo(e); } };
    mapaApp.estadoViento = function () { return V ? V.estado() : null; };
    mapaApp.benchViento = function (n) { return V ? V.bench(n || 60) : null; };
    mapaApp.vientoEn = function (lat, lon) { return V ? V.en(lat, lon) : null; };
    mapaApp.setVientoLocal = function (d) {
      function dec(b64) {
        var s = atob(b64), n = s.length, b = new Uint8Array(n);
        for (var i = 0; i < n; i++) { b[i] = s.charCodeAt(i); }
        var e = new Int16Array(b.buffer), f = new Float32Array(e.length);
        for (var k = 0; k < e.length; k++) { f[k] = e[k] === d.solido ? NaN : e[k] * d.escala; }
        return f;
      }
      VL = {nx: d.nx, ny: d.ny, dx: d.dx, cx: d.cx, cy: d.cy, ic: (d.cx - d.x0) / d.dx, jc: (d.cy - d.y0) / d.dx,
            i2: (d.cx2 - d.x0) / d.dx, j2: (d.cy2 - d.y0) / d.dx, esq: d.esquinas, r: d.radio, rb: d.radio_borde, paso: d.paso,
            U: d.u.map(dec), V: d.v.map(dec), Lu: new Float32Array(d.nx * d.ny), Lv: new Float32Array(d.nx * d.ny)};
      if (V) { V.refresca(); }
    };

    // ── Penacho de un plan, hora a hora ─────────────────────────────────────────────────
    // Una imagen por hora con FUNDIDO DE COMPOSICIÓN CONSTANTE entre horas (la opacidad total
    // no cambia: no parpadea) y el panel de la simulación con los iconos del cajón (tiempo,
    // termómetro, brújula en la planta). Receta del cajón.
    var PN = null;
    function crearPenacho() {
      var grupo = L.layerGroup(), ovs = [], P = null, OP = 0.72, fa_ = 0, ff_ = 0, enControl = false;
      var Panel = L.Control.extend({
        options: {position: "bottomright"},
        onAdd: function () {
          var d = L.DomUtil.create("div", "mapa-wx"); d.style.display = "none";
          L.DomEvent.disableClickPropagation(d); return d;
        }
      });
      var panel = new Panel(); mapa.addControl(panel);
      var NS = '<text x="55" y="16" fill="#fff" font-size="11" text-anchor="middle">N</text>'
        + '<text x="55" y="103" fill="#fff" font-size="11" text-anchor="middle">S</text>'
        + '<text x="101" y="59" fill="#fff" font-size="11" text-anchor="middle">E</text>'
        + '<text x="9" y="59" fill="#fff" font-size="11" text-anchor="middle">O</text>';
      function montaPanel() {
        panel.getContainer().innerHTML =
          '<div class="wxb"><div id="wxic"></div><div id="wxtxt" class="cap">—</div></div>'
          + '<div class="wxb">' + P.termometro + '<div id="thtxt" class="cap">—</div></div>'
          + '<div class="wxb"><svg width="96" height="96" viewBox="0 0 110 110">'
          + '<circle cx="55" cy="55" r="50" fill="#ffffff18" stroke="#ffffff99"/>' + NS
          + '<g id="warrow" transform="rotate(0 55 55)"><line id="warl" x1="55" y1="55" x2="55" y2="20" '
          + 'stroke="#ffcc00" stroke-width="4"/><polygon id="warh" points="55,10 47,24 63,24" fill="#ffcc00"/></g>'
          + '</svg><div id="wtxt" class="cap">—</div></div>';
      }
      function tcol(t) { var f = Math.min(1, Math.max(0, (t + 5) / 45)); return "hsl(" + Math.round(240 * (1 - f)) + ",75%,50%)"; }
      function lerpang(a, b, f) { var d = ((b - a + 540) % 360) - 180; return (a + d * f + 360) % 360; }
      function coma(x, n) { return x.toFixed(n).replace(".", ","); }
      function meteo(a, frac) {
        var b = Math.min(a + 1, P.meteo.length - 1), A = P.meteo[a], B = P.meteo[b];
        var wd = lerpang(A.wd, B.wd, frac), ws = A.ws + (B.ws - A.ws) * frac, tm = A.t + (B.t - A.t) * frac;
        var ar = document.getElementById("warrow");
        if (ar) {
          var Lg = 16 + 30 * Math.min(1, ws / (P.wsmax || 1)), tip = 55 - Lg;
          document.getElementById("warl").setAttribute("y2", tip + 8);
          document.getElementById("warh").setAttribute("points", "55," + tip + " 47," + (tip + 12) + " 63," + (tip + 12));
          ar.setAttribute("transform", "rotate(" + ((wd + 180) % 360) + " 55 55)");
          document.getElementById("wtxt").textContent = "del " + Math.round(wd) + "° · " + coma(ws, 1) + " m/s";
        }
        var mc = document.getElementById("thmerc"), bb = document.getElementById("thbulb");
        if (mc) {
          var fr = (P.tmax > P.tmin) ? Math.min(1, Math.max(0, (tm - P.tmin) / (P.tmax - P.tmin))) : 0.5, h = fr * 82;
          mc.setAttribute("y", 94 - h); mc.setAttribute("height", h);
          var c = tcol(tm); mc.setAttribute("fill", c); if (bb) { bb.setAttribute("fill", c); }
          document.getElementById("thtxt").textContent = coma(tm, 1) + " °C";
        }
        var wi = document.getElementById("wxic");
        if (wi) { wi.innerHTML = P.iconos[A.icono] || ""; document.getElementById("wxtxt").textContent = A.tiempo; }
      }
      function hayTiempo() { return !!(P && P.meteo); }
      function render(a, frac) {
        if (!P || !ovs.length) { return; }
        a = Math.max(0, Math.min(a, ovs.length - 1));
        var b = Math.min(a + 1, ovs.length - 1), K = 1 - OP;
        var ab = (b !== a) ? OP * frac : 0, aa = (b !== a) ? (1 - K / (1 - ab)) : OP;
        for (var j = 0; j < ovs.length; j++) { ovs[j].setOpacity(j === a ? aa : ((j === b && b !== a) ? ab : 0)); }
        if (mapa.hasLayer(grupo) && hayTiempo()) { meteo(a, frac); }
        igualaLeyenda();                                         // el rótulo de cada hora cambia su ancho
      }
      grupo.on("add", function () { panel.getContainer().style.display = hayTiempo() ? "flex" : "none"; render(fa_, ff_); });
      grupo.on("remove", function () { panel.getContainer().style.display = "none"; igualaLeyenda(); });
      return {
        set: function (datos) {
          P = datos; OP = P.opacidad || 0.72;
          grupo.clearLayers(); ovs = [];
          P.frames.forEach(function (imagenes) {                // varias imágenes por hora: cerca, con más detalle
            var os = imagenes.map(function (u, k) {
              var o = L.imageOverlay(u, P.limites[k], {opacity: 0, interactive: false, className: claseEscala(P.escala)});
              grupo.addLayer(o);
              return o;
            });
            ovs.push({options: {opacity: 0}, setOpacity: function (a) {
              this.options.opacity = a; os.forEach(function (o) { o.setOpacity(a); });
            }});
          });
          if (hayTiempo()) { montaPanel(); }
          // grupo excluyente con las capas de media, máximo y P98 del día (penacho_mapa.GRUPO)
          capas["penacho"] = {capa: grupo, leyenda: P.leyenda, grupo: P.grupo || null};
          if (!enControl) { control.addOverlay(grupo, P.nombre); enControl = true; }
          if (P.visible === false) {                            // otra magnitud con otra capa a la vista
            if (mapa.hasLayer(grupo)) { mapa.removeLayer(grupo); }
          } else if (!mapa.hasLayer(grupo)) { grupo.addTo(mapa); }
          panel.getContainer().style.display = (hayTiempo() && mapa.hasLayer(grupo)) ? "flex" : "none";
          render(fa_, ff_); pintaLeyenda();
        },
        hora: function (a, frac) { fa_ = a; ff_ = frac || 0; render(fa_, ff_); },
        quitar: function () {
          if (mapa.hasLayer(grupo)) { mapa.removeLayer(grupo); }
          if (enControl) { control.removeLayer(grupo); enControl = false; }
          delete capas["penacho"]; P = null; pintaLeyenda();
        },
        estado: function () {
          return P ? {fotogramas: ovs.length, hora: fa_, frac: ff_, visible: mapa.hasLayer(grupo),
                      opacidades: ovs.map(function (o) { return Math.round(o.options.opacity * 100) / 100; })
                                     .filter(function (x) { return x > 0; })} : null;
        }
      };
    }
    mapaApp.setPenacho = function (d) { if (!PN) { PN = crearPenacho(); } PN.set(d); };
    mapaApp.penachoHora = function (a, frac) { if (PN) { PN.hora(a, frac); } };
    mapaApp.quitarPenacho = function () { if (PN) { PN.quitar(); } };
    mapaApp.estadoPenacho = function () { return PN ? PN.estado() : null; };

    var Caja = L.Control.extend({
      options: {position: "bottomleft"},
      onAdd: function () {
        var d = L.DomUtil.create("div", "mapa-coords");
        d.style.display = "none";
        return d;
      }
    });
    var caja = new Caja();
    mapa.addControl(caja);
    mapa.on("mousemove", function (e) {
      caja.getContainer().style.display = "block";
      caja.getContainer().innerHTML = e.latlng.lat.toFixed(5) + ", " + e.latlng.lng.toFixed(5);
    });
    mapa.on("click", function (e) {
      enviar({evento: "clic", lat: e.latlng.lat, lon: e.latlng.lng});
    });
    mapa.on("baselayerchange", function (e) { enviar({evento: "fondo", nombre: e.name}); });

    mapaApp.setEscalas(ESTADO.escalas);
    mapaApp.setPlanta(ESTADO.planta);
    mapaApp.setLimites(ESTADO.limites);
    mapaApp.centrar();
    enviar({evento: "listo"});
  }
  // Con los scripts ya ejecutados, sin esperar a las imágenes: «load» espera a todas las teselas y, con el
  // servidor lento o atascado, no había focos, ni capas, ni nada del mapa (medido, 2026-10-31).
  document.addEventListener("DOMContentLoaded", iniciar);
})();
</script>
"""


def _n(x, dec=0):
    """Número con coma decimal y espacio fino de miles."""
    return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")


def leyenda_html(titulo, leyenda):
    """HTML de la leyenda de una capa de imagen (ver terreno.imagenes_mapa)."""
    if leyenda["tipo"] == "continua":
        u = leyenda.get("unidad", "")
        return (f"<h4>{html.escape(titulo)}</h4>"
                f"<div class='barra' style='background:linear-gradient(to right,"
                f"{leyenda['gradiente']})'></div>"
                f"<div class='extremos'><span>{_n(leyenda['min'])} {u}</span>"
                f"<span>{_n(leyenda['max'])} {u}</span></div>")
    filas = "".join(
        f"<div class='clase'><span class='muestra' style='background:{c['color']}'></span>"
        f"{c['codigo']} · {html.escape(c['nombre'])}<span class='pct'>{_n(c['pct'], 1)} %</span>"
        f"</div>" for c in leyenda["clases"])
    return f"<h4>{html.escape(titulo)}</h4><div class='clases'>{filas}</div>"


def css_tema():
    """Los controles de Leaflet con los colores del tema (también para el plano de focos)."""
    return CSS_BASE.replace("__VARIABLES__", tema.css_variables())


def ficha_html(titulo, filas):
    """Contenido de una ficha del mapa: título y filas [(etiqueta, valor)]."""
    cuerpo = "".join(f"<tr><td>{html.escape(a)}</td><td>{html.escape(str(b))}</td></tr>" for a, b in filas)
    return f"<div class='mapa-ficha'><h4>{html.escape(titulo)}</h4><table>{cuerpo}</table></div>"


def datos_planta(emp):
    return {"lat": emp["lat"], "lon": emp["lon"], "nombre": emp["nombre"]}


def escribir_mapa_base(emp, limites, ruta=None, autonomo=True):
    """Genera el HTML del mapa base. `limites` = [[sur, oeste], [norte, este]] del terreno
    (el encuadre inicial). Devuelve la ruta del HTML (fuera de OneDrive)."""
    ruta = ruta or (config.DIR_WEB / "mapa_base.html")
    m = folium.Map(location=[emp["lat"], emp["lon"]], zoom_start=11, tiles=None,
                   control_scale=True, max_zoom=19)
    for i, (nombre, url, atr, nativo) in enumerate(fondos()):
        folium.TileLayer(tiles=url, attr=atr, name=nombre, overlay=False, control=True,
                         show=(i == 0), max_zoom=19, max_native_zoom=nativo).add_to(m)
    # Planta, núcleos y estaciones: SIEMPRE visibles y fuera del selector de capas (decisión
    # del usuario para planta y núcleos; las estaciones siguen el mismo criterio)
    g_planta = folium.FeatureGroup(name="Planta", show=True, control=False).add_to(m)
    g_nucleos = folium.FeatureGroup(name="Núcleos", show=True, control=False).add_to(m)
    g_estaciones = folium.FeatureGroup(name="Estaciones", show=True, control=False).add_to(m)
    control = folium.LayerControl(position="topright", collapsed=True).add_to(m)

    estado = {"planta": datos_planta(emp), "limites": limites, "escalas": tema.escalas_mapa()}
    js = (_JS.replace("__ESTADO__", json.dumps(estado))
             .replace("__MAPA__", m.get_name())
             .replace("__CONTROL__", control.get_name())
             .replace("__G_PLANTA__", g_planta.get_name())
             .replace("__G_NUCLEOS__", g_nucleos.get_name())
             .replace("__G_ESTACIONES__", g_estaciones.get_name()))
    m.get_root().header.add_child(folium.Element(css_tema() + _CSS))
    m.get_root().html.add_child(folium.Element(js))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(ruta))
    if autonomo:
        try:
            n_js, n_css = web.hacer_autonomo(ruta, config.DIR_WEB_ASSETS)
            log.debug(f"Mapa autónomo: {n_js} scripts y {n_css} hojas de estilo embebidos")
        except Exception as e:                      # el mapa sigue funcionando con CDN
            log.warning(f"No se pudo hacer autónomo el mapa (se usarán los CDN): {e!r}")
    return ruta


# ── rosa de los vientos en SVG (tooltip de las estaciones) ──────────────────────────────
def rosa_svg(obs, clases, era5=None, lado=230):
    """Rosa de los vientos: pétalos apilados por clase de velocidad (obs[sector][clase], % de
    todas las horas). Con `era5` (era5[sector], % de todas las horas) se le superpone una línea
    roja para comparar con un modelo; el tooltip del mapa ya no la usa (decisión del usuario).
    Sectores en sentido horario desde el norte GEOGRÁFICO (procedencia del viento)."""
    import math
    n = len(obs)
    c = lado / 2
    R = c - 16                                     # sitio para N, E, S, O
    tope = max(max(sum(f) for f in obs), max(era5) if era5 else 0.0, 1e-9)
    paso = 2 if tope <= 10 else 5 if tope <= 30 else 10
    tope = math.ceil(tope / paso) * paso

    def xy(ang, r):
        a = math.radians(ang)
        return c + r * math.sin(a), c - r * math.cos(a)

    def cuña(a0, a1, r0, r1):
        x0, y0 = xy(a0, r1)
        x1, y1 = xy(a1, r1)
        if r0 <= 0.01:
            return f"M{c:.1f} {c:.1f}L{x0:.1f} {y0:.1f}A{r1:.1f} {r1:.1f} 0 0 1 {x1:.1f} {y1:.1f}Z"
        x2, y2 = xy(a1, r0)
        x3, y3 = xy(a0, r0)
        return (f"M{x3:.1f} {y3:.1f}L{x0:.1f} {y0:.1f}A{r1:.1f} {r1:.1f} 0 0 1 {x1:.1f} "
                f"{y1:.1f}L{x2:.1f} {y2:.1f}A{r0:.1f} {r0:.1f} 0 0 0 {x3:.1f} {y3:.1f}Z")

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{lado}" height="{lado}" '
         f'viewBox="0 0 {lado} {lado}" style="display:block">']
    for v in range(paso, tope + 1, paso):          # anillos de frecuencia
        r = R * v / tope
        p.append(f'<circle cx="{c}" cy="{c}" r="{r:.1f}" fill="none" stroke="var(--apagado)" '
                 f'stroke-width="0.7" stroke-dasharray="2 2"/>')
        x, y = xy(22.5 * 1.5, r)
        p.append(f'<text x="{x + 2:.1f}" y="{y:.1f}" font-size="8" fill="var(--tenue)">{v} %</text>')
    for ang in range(0, 360, 45):
        x, y = xy(ang, R)
        p.append(f'<line x1="{c}" y1="{c}" x2="{x:.1f}" y2="{y:.1f}" stroke="var(--borde_fuerte)" '
                 f'stroke-width="0.6"/>')
    ancho = 360.0 / n
    for i, fila in enumerate(obs):
        a = i * ancho
        acum = 0.0
        for k, f in enumerate(fila):
            if f <= 0:
                continue
            r0, r1 = R * acum / tope, R * (acum + f) / tope
            p.append(f'<path d="{cuña(a - ancho * 0.4, a + ancho * 0.4, r0, r1)}" '
                     f'fill="{COLORES_VEL[k % len(COLORES_VEL)]}" stroke="var(--superficie)" '
                     f'stroke-width="0.4"/>')
            acum += f
    if era5:
        puntos = " ".join("{:.1f},{:.1f}".format(*xy(i * ancho, R * f / tope))
                          for i, f in enumerate(era5))
        p.append(f'<polygon points="{puntos}" fill="none" stroke="#c0392b" stroke-width="1.8" '
                 f'stroke-linejoin="round"/>')
    for ang, letra in ((0, "N"), (90, "E"), (180, "S"), (270, "O")):
        x, y = xy(ang, R + 9)
        p.append(f'<text x="{x:.1f}" y="{y + 3.5:.1f}" font-size="10" font-weight="bold" '
                 f'text-anchor="middle" fill="var(--texto)">{letra}</text>')
    p.append("</svg>")
    return "".join(p)


def leyenda_rosa(clases, calmas, altura_m):
    """Pie de la rosa: clases de velocidad y calmas de la estación."""
    lim = list(clases) + [None]
    chips = "".join(
        f"<span style='white-space:nowrap'>"
        f"<span style='display:inline-block;width:9px;height:9px;background:{COLORES_VEL[k]};"
        f"border-radius:2px;margin:0 2px 0 6px;vertical-align:-1px'></span>"
        + (f"{_n(lim[k], 1 if lim[k] % 1 else 0)}–{_n(lim[k + 1])}" if lim[k + 1] is not None
           else f"≥ {_n(lim[k])}")
        + "</span> "
        for k in range(len(clases)))
    h = f" a {_n(altura_m)} m" if altura_m else ""
    return (f"<div style='font-size:10.5px;line-height:15px;margin-top:2px;white-space:normal'>"
            f"Viento{h} (m/s): {chips}"
            + (f"<br>Calmas (&lt; 0,5 m/s): {_n(calmas, 1)} %" if calmas is not None else "")
            + "</div>")
