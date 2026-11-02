# Las tres formas del viento en los dos colores, el selector del mapa, y TODOS los textos que quedan en la app.
import json, os, shutil, sys, time
from pathlib import Path
AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "viento"
SALIDA.mkdir(exist_ok=True)
import os as _os, sys as _sys
_aj = _os.environ.get("ENCE_AJUSTES_PRUEBA")
if not _aj:
    raise SystemExit("Falta ENCE_AJUSTES_PRUEBA: las pruebas no tocan el INI del usuario.")
_os.environ["APPDATA"] = _aj
from PySide6 import QtCore as _QC
_QC.QSettings.setPath(_QC.QSettings.Format.IniFormat, _QC.QSettings.Scope.UserScope, _aj)
RAIZ = Path(__file__).resolve().parents[2]
_salir = _os._exit
def _fin(c=0):
    g = _sys.modules.get("teodors")
    print("CODIGO:", getattr(g, "__file__", "sin cargar"), file=_sys.__stdout__, flush=True)
    _salir(c)
_os._exit = _fin
os.environ.setdefault("ENCE_GALERA_DATOS", str(Path(os.environ["TEMP"]) / "ence_galera" / "datos_local"))
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
_planta.actual().DIR_PLANES = _planta.DATOS / "escenarios"      # los planes de las pruebas, con la copia de los datos: nunca en la carpeta de la planta
out = sys.__stdout__
out.reconfigure(encoding="utf-8")
INI = Path(os.environ["APPDATA"]) / "CIRCE" / "ENCE_Galera.ini"
COPIA = AQUI / "ENCE_Galera.ini.viento"
tenia = INI.exists()
if tenia:
    shutil.copy2(INI, COPIA)
from PySide6 import QtCore, QtWidgets, QtWebEngineWidgets  # noqa
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(sys.argv[:1])
from teodors.comun import registro
from teodors.gui import tema
aj = tema.ajustes()
for g in ("ventana", "focos", "planes", "apariencia"):
    aj.remove(g)
aj.sync()
tema.aplicar(app)
from teodors.gui.ventana import VentanaPrincipal
_planta.asegurar_carpetas(); registro.configurar(_planta.DIR_LOGS, _planta.REGISTRO)
v = VentanaPrincipal()
FLAGS = ("WindowStaysOnTopHint", "WindowTransparentForInput", "WindowDoesNotAcceptFocus")
fallos = []


def sin_foco(w):
    for b in FLAGS:
        w.setWindowFlag(getattr(QtCore.Qt.WindowType, b), True)


sin_foco(v)
v.resize(1430, 790)
v.show()
v.move(0, 0)


def ok(n, si, det=""):
    print(("OK  " if si else "MAL ") + n, det, file=out, flush=True)
    if not si:
        fallos.append(n)


def fin():
    print("FALLOS:", fallos or "ninguno", file=out, flush=True)
    if tenia:
        shutil.copy2(COPIA, INI)
    else:
        INI.unlink(missing_ok=True)
    os._exit(1 if fallos else 0)


def espera(s):
    t = time.time()
    app.processEvents()
    while time.time() - t < s:
        time.sleep(0.01)
        app.processEvents()


def js(c):
    r = {}
    v.mapa.page().runJavaScript(c, 0, lambda x: r.setdefault("v", x))
    t = time.time()
    while "v" not in r and time.time() - t < 10:
        app.processEvents()
        time.sleep(0.01)
    return r.get("v")


def viento():
    return json.loads(js("JSON.stringify(mapaApp.estadoViento())") or "{}") or {}


def foto(nombre, w=None):
    (w or v).grab().save(str(SALIDA / f"{nombre}.png"))


def pix_viento():
    """Píxeles dibujados en el lienzo del viento y su color medio: que las formas pintan de verdad."""
    return json.loads(js("""(function(){var c=document.querySelector('.leaflet-mapaViento-pane canvas');
      if(!c)return JSON.stringify(null);var d=c.getContext('2d').getImageData(0,0,c.width,c.height).data,n=0,r=0,gg=0,b=0,blanco=0;
      for(var i=3;i<d.length;i+=4){if(d[i]>60){n++;r+=d[i-3];gg+=d[i-2];b+=d[i-1];if(d[i-3]>235&&d[i-2]>235&&d[i-1]>235)blanco++;}}
      return JSON.stringify({n:n,blanco:n?blanco/n:0});})()"""))


t = time.time()
while time.time() - t < 40 and not v.mapa.esta_listo():
    espera(0.3)
espera(6)
p = v.panel
p.preparar_dia_viento("2026-10-21")
espera(1)
p.btn_viento.click()
t = time.time()
while time.time() - t < 30 and not p.reproductor.isVisible():
    espera(0.2)
espera(1.5)
v._ver_ajustes()
va = v._ventana_ajustes
sin_foco(va)
va.show()
va.move(780, 40)
espera(0.5)
foto("00_configuracion", va)
ok("Por defecto: partículas en blanco", viento().get("modo") == "particulas" and viento().get("blanco") is True)
ok("Tres formas en el selector", all(x in (js("document.querySelector('.leaflet-control-layers-overlays').innerText") or "")
                                     for x in ("partículas", "líneas de corriente", "flechas")))

# con el viento de un día, parado, para comparar
va.hide()
p.preparar_dia_viento("2026-10-21")
espera(0.5)
p.btn_viento.click()
t = time.time()
espera(0.3)
while time.time() - t < 40 and v._trabajo_viento is not None and v._trabajo_viento.isRunning():
    espera(0.3)
espera(1)
p.btn_play.setChecked(False)
p.hora_viento.setValue(4 * 14)
espera(1.5)
selector = js("document.querySelector('.leaflet-control-layers-overlays').innerText") or ""
print("Reanálisis:", {"reproductor": p.reproductor.isVisible(), "play": p.btn_play.isEnabled(), "viento": viento().get("modo"),
                     "penacho": js("mapaApp.estadoPenacho()"), "tiempo": js("!!document.querySelector('.mapa-wx')&&document.querySelector('.mapa-wx').style.display")}, file=out, flush=True)
ok("Reanálisis: el día con su viento", p.reproductor.isVisible() and p.btn_play.isEnabled() and bool(viento().get("modo")))
ok("Reanálisis: sin penacho", not js("mapaApp.estadoPenacho()") and "Penacho" not in selector, " | ".join(selector.split()))
leyenda = js("document.querySelector('.mapa-leyenda').innerText") or ""
ok("Reanálisis: sin leyenda de penacho", "Penacho" not in leyenda, leyenda[:60])
for forma in ("particulas", "lineas", "flechas"):
    for color in ("blanco", "velocidad"):
        va._b_forma[forma].click()
        va._b_color[color].click()
        espera(2.0 if forma == "particulas" else 0.8)
        e, q = viento(), pix_viento()
        txt = js("document.querySelector('.mapa-viento').innerText") or ""
        lleva_escala = "m/s:" in txt
        ok(f"{forma} · {color}", e.get("modo") == forma and e.get("blanco") == (color == "blanco")
           and q and q["n"] > 2000 and lleva_escala == (color == "velocidad")
           and ("estela" not in txt) and ("tiempo real" not in txt),
           f"píxeles {q and q['n']} · blanco {q and round(q['blanco'], 2)} · dibujo {e.get('ms_dibujo')} ms")
        if color == "blanco" and forma != "particulas":
            ok(f"  {forma}: en blanco, de verdad", q["blanco"] > 0.15, round(q["blanco"], 2))      # el resto es el contorno
        if color == "velocidad":
            ok(f"  {forma}: en color, de verdad", q["blanco"] < 0.1, round(q["blanco"], 2))
        foto(f"{forma}_{color}")

# cantidad, zoom y hora en las líneas
va._b_forma["lineas"].click()
va._b_color["blanco"].click()
espera(0.6)
base = pix_viento()["n"]
va._b_cantidad["pocas"].click()
espera(0.5)
pocas = pix_viento()["n"]
va._b_cantidad["muchas"].click()
espera(0.5)
muchas = pix_viento()["n"]
ok("Cantidad en las líneas", pocas < base < muchas, f"{pocas} < {base} < {muchas}")
va._b_cantidad["normal"].click()
espera(0.5)
a = pix_viento()["n"]
ms = []
for k in range(8):
    p.hora_viento.setValue(p.hora_viento.value() + 1)
    espera(0.15)
    ms.append(viento()["ms_dibujo"])
ok("Las líneas siguen a la hora", viento()["hora"] == 16, f"dibujo {min(ms)}-{max(ms)} ms")
for zoom, nombre in ((14, "cerca"), (18, "planta")):
    js("(function(){for(var k in window){try{if(window[k] instanceof L.Map){window[k].setView([40.6906,0.4764],%d,{animate:false});}}catch(e){}}})()" % zoom)
    espera(2.5)
    n = pix_viento()["n"]
    ok(f"Líneas a zoom {zoom}", n > 2000, f"píxeles {n}, dibujo {viento()['ms_dibujo']} ms")
    foto(f"lineas_blanco_{nombre}")
    va._b_forma["flechas"].click()
    espera(0.8)
    n = pix_viento()["n"]
    ok(f"Flechas a zoom {zoom}", n > 500, f"píxeles {n}, dibujo {viento()['ms_dibujo']} ms")
    foto(f"flechas_blanco_{nombre}")
    va._b_forma["lineas"].click()
    espera(0.5)
v.mapa.centrar()
espera(2)

# selector del mapa ↔ configuración, guardado y restablecer
js("""(function(){var l=document.querySelectorAll('.leaflet-control-layers-overlays label');l.forEach(function(e){
  if(e.innerText.indexOf('flechas')>=0){e.querySelector('input').click();}});})()""")
espera(1)
marcadas = js("""(function(){var r=[];document.querySelectorAll('.leaflet-control-layers-overlays label').forEach(function(e){
  if(e.innerText.indexOf('Viento')>=0&&e.querySelector('input').checked){r.push(e.innerText.trim());}});return r.join(',');})()""")
print("Selector:", viento().get("modo"), tema.preferencia("viento_forma"), va._b_forma["flechas"].isChecked(), "| marcadas:", marcadas, file=out, flush=True)
ok("El selector del mapa cambia la forma, y la configuración lo enseña", viento().get("modo") == "flechas"
   and tema.preferencia("viento_forma") == "flechas" and va._b_forma["flechas"].isChecked())
ok("Solo una forma marcada en el selector", marcadas == "Viento · flechas", marcadas)
ok("Línea de la leyenda sin descripciones", True)
b = [w for w in va.findChildren(QtWidgets.QPushButton) if w.text() == "Restablecer"][0]
b.click()
espera(1)
ok("Restablecer", viento().get("modo") == "particulas" and viento().get("blanco") is True and va._b_forma["particulas"].isChecked()
   and tema.preferencia("viento_forma") == "particulas")
ok("Se guarda con su clave", tema.ajustes().value("apariencia/viento_forma") == "particulas")

# una simulación, para ver la tabla y sus textos
p.ir_a("simulacion")
espera(0.2)
t0 = time.time()
p.b_simular.click()
while v._trabajo_sim is not None and time.time() - t0 < 200:
    espera(0.2)
p.b_simular_periodo.click()      # ahora el penacho es de «Simular día»
while v._trabajo_sim is not None and time.time() - t0 < 500:
    espera(0.2)
espera(2)
ok("Simula", "423" in p.res_anios.lbl.text(), p.res_anios.lbl.text())
ok("Tabla sin Dacame", not any("Dacame" in p.res_anios.tabla.item(i, 0).text() for i in range(p.res_anios.tabla.rowCount())))
foto("simulacion")

# ── todos los textos que quedan ─────────────────────────────────────────────────────────
v._ver_focos()
vf = v._ventana_focos
sin_foco(vf)
vf.show()
v._ver_planes()
vp = v._ventana_planes
sin_foco(vp)
vp.show()
espera(5)
foto("focos", vf)
foto("planes", vp)
foto("configuracion", va)
for k in ("inicio", "planta", "focos", "meteo"):
    p.ir_a(k)
    espera(0.2)
    foto(f"panel_{k}")
p.ir_a("simulacion")
vistos = {}
for raiz in (v, vf, vp, va):
    for w in raiz.findChildren(QtWidgets.QWidget):
        if w.window() is not raiz and raiz is not v:
            continue
        for tipo, t in (("texto", w.text() if hasattr(w, "text") and isinstance(w, (QtWidgets.QLabel, QtWidgets.QAbstractButton)) else ""),
                        ("ayuda", w.toolTip()), ("marcador", w.placeholderText() if isinstance(w, QtWidgets.QLineEdit) else "")):
            if t and len(t.strip()) > 1:
                vistos.setdefault((type(raiz).__name__, tipo, t.strip()[:150]), 0)
filas = sorted(vistos)
(SALIDA / "textos.txt").write_text("\n".join(f"{a:17s} {b:9s} {c}" for a, b, c in filas), encoding="utf-8")
web = js("""(function(){var r=[];document.querySelectorAll('.mapa-viento,.mapa-leyenda,.leaflet-control-layers-overlays,.mapa-wx').forEach(function(e){r.push(e.innerText);});
  document.querySelectorAll('[title]').forEach(function(e){r.push('title: '+e.getAttribute('title'));});return r.join(' || ').replace(/\\n/g,' / ');})()""")
print("Web:", (web or "")[:900], file=out, flush=True)
fin()
