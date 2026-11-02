# Emplazamiento en todas las páginas, plegables de Planta y leyenda alineada con el icono del tiempo.
import json, os, shutil, sys, time
from pathlib import Path
AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "emplazamiento"
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
out = sys.__stdout__
out.reconfigure(encoding="utf-8")
INI = Path(os.environ["APPDATA"]) / "CIRCE" / "ENCE_Galera.ini"
COPIA = AQUI / "ENCE_Galera.ini.emplazamiento"
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
from teodors.gui.widgets import Tarjeta
registro.configurar()
v = VentanaPrincipal()
for b in ("WindowStaysOnTopHint", "WindowTransparentForInput", "WindowDoesNotAcceptFocus"):
    v.setWindowFlag(getattr(QtCore.Qt.WindowType, b), True)
v.resize(1430, 790)
v.show()
v.move(0, 0)
fallos = []


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


def foto(nombre):
    v.grab().save(str(SALIDA / f"{nombre}.png"))


ZOOM = "(function(){for(var k in window){try{if(window[k] instanceof L.Map){return window[k].getZoom();}}catch(e){}}})()"
t = time.time()
while time.time() - t < 40 and not v.mapa.esta_listo():
    espera(0.3)
espera(5)
p = v.panel


def boton(texto):
    return [b for b in p.findChildren(QtWidgets.QPushButton) if b.text() == texto]


# ── 1. Emplazamiento en todas las páginas ───────────────────────────────────────────────
ok("Una sola tarjeta de emplazamiento y un solo juego de botones", len(boton("Ver planta")) == 1 and len(boton("Ver toda la zona")) == 1
   and sum(1 for w in p.findChildren(QtWidgets.QLabel) if w.text() == "Emplazamiento") == 1)
tarjeta = next(w for w in p.findChildren(QtWidgets.QLabel) if w.text() == "Emplazamiento").parent()
posicion = None
for clave, _, _, titulo in p.PAGINAS:
    p.ir_a(clave)
    espera(0.2)
    aqui = tarjeta.mapTo(p, QtCore.QPoint(0, 0))
    ok(f"{titulo}: emplazamiento y botones a la vista, en el mismo sitio", tarjeta.isVisible() and boton("Ver planta")[0].isVisible()
       and boton("Ver toda la zona")[0].isVisible() and p.lbl_lat.isVisible() and p.lbl_utm.isVisible() and posicion in (None, aqui), (aqui.x(), aqui.y(), tarjeta.height()))
    posicion = aqui
    foto(f"pagina_{clave}")
p.ir_a("meteo")
boton("Ver planta")[0].click()
espera(1.5)
zp = js(ZOOM)
boton("Ver toda la zona")[0].click()
espera(1.5)
zz = js(ZOOM)
ok("Sus botones funcionan desde otra página", zp == 18 and zz < 13, f"zoom {zp} y {zz}")


def borde_derecho(w):
    return w.mapTo(p, QtCore.QPoint(w.width(), 0)).x()


# ── 2. Plegables de Planta ──────────────────────────────────────────────────────────────
p.ir_a("planta")
espera(0.3)
E, U = p.pleg_elevacion, p.pleg_usos
ok("Títulos", E.cabecera.text() == "Elevación" and U.cabecera.text() == "Usos del suelo")
ok("Empiezan plegados", not p.lbl_cotas.isVisible() and not p.b_ver_elevacion.isVisible() and not p.arbol_usos.isVisible() and not p.b_ver_usos.isVisible()
   and E.isVisible() and U.isVisible())
ok("Edificios también plegado", p.pleg_edificios.isVisible() and not p.b_ver_edificios.isVisible())
foto("planta_plegada")
alto0 = E.height()
E.cabecera.click()
espera(0.3)
ok("Elevación se despliega", p.lbl_cotas.isVisible() and p.b_ver_elevacion.isVisible() and E.height() > alto0 and "1 437" in p.lbl_cotas.text(), E.height())
ok("Usos sigue plegado", not p.arbol_usos.isVisible())
U.cabecera.click()
espera(0.5)
ok("Usos se despliega: árbol, botón y núcleos", p.arbol_usos.isVisible() and p.b_ver_usos.isVisible() and p.lbl_nucleos.isVisible() and "núcleos urbanos" in p.lbl_nucleos.text())
n = p.arbol_usos.topLevelItemCount()
ok("Se ven todos los grupos del árbol", p.arbol_usos.height() >= n * p.arbol_usos.sizeHintForRow(0), f"{n} grupos, {p.arbol_usos.height()} px")
area = p._paginas["planta"]
ok("Con todo abierto hay barra de desplazamiento", area.verticalScrollBar().maximum() > 0, area.verticalScrollBar().maximum())
espera(0.2)
ok("… y las tarjetas siguen alineadas con el emplazamiento", abs(borde_derecho(E) - borde_derecho(tarjeta)) <= 1, (borde_derecho(E), borde_derecho(tarjeta)))
ok("Sin desbordarse a lo ancho", area.widget().width() <= area.viewport().width())
foto("planta_abierta")
area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
espera(0.3)
foto("planta_abierta_abajo")
area.verticalScrollBar().setValue(0)

p.b_ver_elevacion.click()
espera(0.8)
ok("Botón de elevación", "elevacion" in json.loads(js("JSON.stringify(mapaApp.capasVisibles())")))
E.cabecera.click()
espera(0.3)
ok("Al plegar, la capa sigue encendida", "elevacion" in json.loads(js("JSON.stringify(mapaApp.capasVisibles())")) and not p.lbl_cotas.isVisible())
foto("planta_elevacion_plegada")
E.cabecera.click()
espera(0.2)
p.b_ver_elevacion.click()
espera(0.5)
U.cabecera.click()
E.cabecera.click()
espera(1)
ok("Plegados otra vez: sin barra y alineado", area.verticalScrollBar().maximum() == 0 and abs(borde_derecho(E) - borde_derecho(tarjeta)) <= 1,
   (area.verticalScrollBar().maximum(), borde_derecho(E), borde_derecho(tarjeta)))

p.set_terreno(None)
espera(0.2)
ok("Sin terreno: sin plegables y con botón de descarga", not E.isVisible() and not U.isVisible() and p.b_terreno.isVisible())
p.set_terreno(v.terreno_info, v._resumen)
espera(0.2)
ok("Con terreno otra vez", E.isVisible() and U.isVisible() and not p.b_terreno.isVisible())

# ── 3. La leyenda hasta el icono del tiempo ─────────────────────────────────────────────
MIDE = """(function(){var w=document.querySelector('.mapa-wx .wxb').getBoundingClientRect(),
  l=document.querySelector('.mapa-leyenda').getBoundingClientRect(),
  b=document.querySelector('.mapa-leyenda .parte div').getBoundingClientRect(),
  x=document.querySelector('.mapa-wx').getBoundingClientRect();
  return JSON.stringify({wx:w.left,ley:l.left,der_wx:x.right,der_ley:l.right,barra:b.width,alto:l.height,arriba:l.top,tope:x.bottom});})()"""
p.set_horizonte_meteo("reanalisis")
espera(1)
p.ir_a("simulacion")
t0 = time.time()
p.b_simular.click()
while v._trabajo_sim is not None and time.time() - t0 < 200:
    espera(0.2)
p.b_simular_periodo.click()      # ahora el penacho es de «Simular día»
while v._trabajo_sim is not None and time.time() - t0 < 500:
    espera(0.2)
espera(2)
p.btn_play.setChecked(False)
difs, anchos = [], []
for h in range(24):
    p.hora_viento.setValue(4 * h)
    espera(0.12)
    d = json.loads(js(MIDE))
    difs.append(abs(d["wx"] - d["ley"]))
    anchos.append(d["der_ley"] - d["ley"])
ok("Las 24 horas: la leyenda empieza donde el icono de día o noche", max(difs) <= 1, f"desfase máx. {max(difs):.1f} px, ancho {min(anchos):.0f}-{max(anchos):.0f} px")
d = json.loads(js(MIDE))
print("Medidas:", d, file=out, flush=True)
ok("Y acaban a la par, sin solaparse", abs(d["der_wx"] - d["der_ley"]) <= 1 and d["tope"] <= d["arriba"])
ok("La barra de color ocupa la tarjeta", d["barra"] >= d["der_ley"] - d["ley"] - 30, d["barra"])
p.hora_viento.setValue(4 * 14)
espera(2)
foto("leyenda_penacho")

p._botones_capa["plan_norma"].click()
espera(0.8)
ok("Con el P98, sin panel del tiempo: vuelve a su ancho", js("document.querySelector('.mapa-leyenda').style.minWidth") == "", js("document.querySelector('.mapa-leyenda').offsetWidth"))
foto("leyenda_p98")
p._botones_capa["penacho"].click()
espera(0.8)
d = json.loads(js(MIDE))
ok("Con el penacho otra vez: alineada", abs(d["wx"] - d["ley"]) <= 1, abs(d["wx"] - d["ley"]))

p.ir_a("planta")
p.pleg_usos.cabecera.click()
p.b_ver_usos.click()
espera(1.5)
d = json.loads(js(MIDE))
ok("Con usos del suelo también: la leyenda puede ser más ancha, nunca más estrecha", d["ley"] <= d["wx"] + 1, (d["ley"], d["wx"]))
foto("leyenda_usos_y_penacho")
p.b_ver_usos.click()
espera(0.8)
d = json.loads(js(MIDE))
ok("Sin usos: alineada", abs(d["wx"] - d["ley"]) <= 1)
p.pleg_usos.cabecera.click()

v.resize(1180, 680)
espera(1.5)
d = json.loads(js(MIDE))
ok("En una ventana más pequeña: alineada", abs(d["wx"] - d["ley"]) <= 1, abs(d["wx"] - d["ley"]))
foto("ventana_pequena")
v.resize(1430, 790)
espera(1)
tema.poner("claro")
espera(1)
d = json.loads(js(MIDE))
ok("En estilo claro: alineada", abs(d["wx"] - d["ley"]) <= 1)
for clave in ("inicio", "planta", "simulacion"):
    p.ir_a(clave)
    espera(0.3)
    foto(f"claro_{clave}")
p.pleg_elevacion.cabecera.click()
espera(0.2)
foto("claro_plegable")
p.pleg_elevacion.cabecera.click()
tema.poner("oscuro")
espera(0.5)
fin()
