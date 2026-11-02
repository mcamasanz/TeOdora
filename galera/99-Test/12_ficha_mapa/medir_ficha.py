# Genera las dos páginas con mapa y mide en cada una lo que tarda en irse una ficha, sin ventana en pantalla. Pide ENCE_GALERA_DATOS con una copia de los datos.
import json
import os
import sys
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parents[2]
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")

from PySide6 import QtCore, QtWidgets  # noqa: E402

QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: E402

from teodors import planta  # noqa: E402

planta.activar(RAIZ / "entrada")
from teodors.gui import focos_mapa, mapa_web  # noqa: E402

print("código:", Path(mapa_web.__file__).resolve())
AQUI = Path(os.environ["TEMP"]) / "ence_galera" / "99-Test" / "12_ficha_mapa"
AQUI.mkdir(parents=True, exist_ok=True)
emp = planta.cargar_emplazamiento()
c = [emp["lat"], emp["lon"]]
paginas = {"mapa principal": mapa_web.escribir_mapa_base(emp, [[c[0] - 0.22, c[1] - 0.29], [c[0] + 0.22, c[1] + 0.29]], AQUI / "base.html"),
           "plano de focos": focos_mapa.escribir_html(emp, AQUI / "focos.html")}

JS = r"""
(function () {
  window.__res = null;
  var clave = Object.keys(window).filter(function (k) { return /^map_[0-9a-f]+$/.test(k); })[0];
  var m = window[clave];
  function espera(ms) { return new Promise(function (ok) { setTimeout(ok, ms); }); }
  function ficha() { return document.querySelector(".leaflet-tooltip-pane .leaflet-tooltip"); }
  function seVe() { var f = ficha(); return !!f && parseFloat(getComputedStyle(f).opacity) > 0.01; }
  (async function () {
    var r = {opacidad_por_defecto: L.Tooltip.prototype.options.opacity, sigue: [], abierta: []};
    for (var k = 0; k < 12; k++) {
      var cm = L.circleMarker(m.getCenter(), {radius: 40}).addTo(m).bindTooltip("Una ficha de prueba", {sticky: true});
      cm.openTooltip();
      await espera(100);
      r.abierta.push(parseFloat(getComputedStyle(ficha()).opacity));
      var t = performance.now();
      cm.closeTooltip();
      while (seVe() && performance.now() - t < 1500) { await espera(1); }
      r.sigue.push(performance.now() - t);
      m.removeLayer(cm);
      await espera(260);
    }
    r.fade = m._fadeAnimated;
    window.__res = r;
  })().catch(function (e) { window.__res = {error: String(e)}; });
})(); 1
"""

app = QtWidgets.QApplication(sys.argv[:1])


def consulta(vista, codigo):
    caja, lazo = {}, QtCore.QEventLoop()

    def recibe(v):
        caja["v"] = v
        lazo.quit()

    vista.page().runJavaScript(codigo, 0, recibe)
    QtCore.QTimer.singleShot(5000, lazo.quit)
    lazo.exec()
    return caja.get("v")


fallos = 0
for nombre, ruta in paginas.items():
    vista = QWebEngineView()
    vista.resize(1600, 900)
    vista.show()
    lazo = QtCore.QEventLoop()
    vista.loadFinished.connect(lambda _ok, l=lazo: l.quit())
    vista.load(QtCore.QUrl.fromLocalFile(str(ruta)))
    QtCore.QTimer.singleShot(60000, lazo.quit)
    lazo.exec()
    t0 = time.time()
    while time.time() - t0 < 30 and not consulta(vista, "!!(window.L && document.readyState==='complete')"):
        pass
    consulta(vista, JS)
    res = None
    t0 = time.time()
    while time.time() - t0 < 60:
        v = consulta(vista, "window.__res ? JSON.stringify(window.__res) : ''")
        if v:
            res = json.loads(v)
            break
        p = QtCore.QEventLoop()
        QtCore.QTimer.singleShot(200, p.quit)
        p.exec()
    if not res or "error" in res:
        print(nombre, "ERROR", res)
        fallos += 1
    else:
        s = sorted(res["sigue"])
        bien = s[-1] < 30 and set(res["abierta"]) == {1}
        fallos += not bien
        print(f"{'OK ' if bien else 'MAL'} {nombre}: se va en {s[len(s) // 2]:.1f} ms (peor {s[-1]:.1f}) · abierta con opacidad {sorted(set(res['abierta']))} · opción por defecto {res['opacidad_por_defecto']} · fundido de Leaflet activo: {res['fade']}", flush=True)
    vista.close()
    vista.deleteLater()
print("FALLOS:", fallos)
app.quit()
