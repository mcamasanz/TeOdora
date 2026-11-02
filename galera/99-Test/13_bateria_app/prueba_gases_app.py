# Gases en la app: simular, elegir magnitud, capas, tabla, tooltips y ficha de los focos, con clics simulados.
import json, os, shutil, sys, time, traceback
from pathlib import Path
AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "gases"
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
COPIA = AQUI / "ENCE_Galera.ini.gases"
tenia = INI.exists()
if tenia:
    shutil.copy2(INI, COPIA)


def restaurar():
    if tenia:
        shutil.copy2(COPIA, INI)
    else:
        INI.unlink(missing_ok=True)


def si_falla(*a):
    traceback.print_exception(*a, file=out)
    restaurar()
    os._exit(2)


sys.excepthook = si_falla
from PySide6 import QtCore, QtGui, QtWidgets, QtWebEngineWidgets  # noqa
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(sys.argv[:1])
from teodors.operacion import focos as F
from teodors.comun import registro
from teodors.gui import tema
aj = tema.ajustes()
for g in ("ventana", "focos", "planes", "apariencia"):
    aj.remove(g)
aj.sync()
tema.aplicar(app)
from teodors.gui.ventana import VentanaPrincipal
_planta.asegurar_carpetas(); registro.configurar(_planta.DIR_LOGS, _planta.REGISTRO)
FLAGS = ("WindowStaysOnTopHint", "WindowTransparentForInput", "WindowDoesNotAcceptFocus")
v = VentanaPrincipal()
for b in FLAGS:
    v.setWindowFlag(getattr(QtCore.Qt.WindowType, b), True)
v.resize(1430, 900)
v.show()
v.move(0, 0)
fallos = []


def ok(n, si, det=""):
    print(("OK  " if si else "MAL ") + n, det, file=out, flush=True)
    if not si:
        fallos.append(n)


def fin():
    print("FALLOS:", fallos or "ninguno", file=out, flush=True)
    restaurar()
    os._exit(1 if fallos else 0)


def espera(s):
    t = time.time()
    app.processEvents()
    while time.time() - t < s:
        time.sleep(0.01)
        app.processEvents()


def js(c, vista=None):
    r = {}
    (vista or v.mapa).page().runJavaScript(c, 0, lambda x: r.setdefault("v", x))
    t = time.time()
    while "v" not in r and time.time() - t < 10:
        app.processEvents()
        time.sleep(0.01)
    return r.get("v")


ESTADO = """JSON.stringify((function(){var i=[].slice.call(document.querySelectorAll('img.leaflet-image-layer'));
  var c={};i.forEach(function(x){var k=(x.className.match(/escala-[a-z]+/)||['ninguna'])[0];c[k]=(c[k]||0)+1;});
  var l=document.querySelector('.mapa-leyenda');
  var pn=mapaApp.estadoPenacho();
  return {imagenes:i.length,clases:c,leyenda:l?l.innerText:'',penacho:pn?pn.visible:null,hora:pn?pn.hora:null};})())"""


def estado():
    return json.loads(js(ESTADO))


def foto(nombre, w=None):
    (w or v).grab().save(str(SALIDA / f"{nombre}.png"))


def elige(k):
    p.cmb_magnitud.setCurrentIndex(p.cmb_magnitud.findData(k))
    espera(1.5)


def cabecera():
    return [p.res_anios.tabla.horizontalHeaderItem(i).text() for i in range(p.res_anios.tabla.columnCount())]


t = time.time()
while time.time() - t < 40 and not v.mapa.esta_listo():
    espera(0.3)
espera(2)
p = v.panel
p.set_horizonte_meteo("reanalisis")
espera(1)
p.ir_a("simulacion")
espera(0.5)
ok("Antes de simular, sin selector", not p.cmb_magnitud.isVisible())
t0 = time.time()
p.b_simular.click()
while time.time() - t0 < 500 and v._resultados["anios"] is None:
    espera(0.2)
p.b_simular_periodo.click()      # ahora el penacho es de «Simular día»
while v._trabajo_sim is not None and time.time() - t0 < 500:
    espera(0.2)
print(f"Simular: {time.time() - t0:.1f} s", file=out, flush=True)
espera(2)
p.btn_play.setChecked(False)
nombres = [p.cmb_magnitud.itemText(i) for i in range(p.cmb_magnitud.count())]
print("Magnitudes:", nombres, file=out, flush=True)
ok("Selector con olor y los gases de los focos", nombres == ["Olor", "H₂S", "CH₃SH", "NH₃", "SO₂", "NOₓ", "CO"] and p.cmb_magnitud.isVisible(), nombres)
e = estado()
ok("Empieza en olor, con el penacho", e["penacho"] is True and e["leyenda"].startswith("Olor · penacho") and e["clases"].get("escala-olor") == 48, e)
ok("Olor: la tabla con su P98", cabecera() == ["Lugar", "Media", "Máx.", "P98"] and "ou_E/m³" in p.res_anios.lbl.text(), cabecera())
txt = p.res_anios.lbl.text()
print("Texto:", txt, file=out, flush=True)
ok("Dice qué focos están estimados y con qué gas", "Estimado por gases: " in txt and "Venteo de los digestores (H₂S)" in txt and "Salida del upgrading (H₂S)" in txt)
ok("Dice qué foco se queda fuera del olor", "Antorcha: sin emisión de olor" in txt)
foto("olor_penacho")

p.hora_viento.setValue(4 * 7)
espera(0.8)
elige("H2S")
e = estado()
ok("H₂S: sigue el penacho, en la misma hora", e["penacho"] is True and e["hora"] == 7, e)
ok("H₂S: leyenda y escala de gases", e["leyenda"].startswith("H₂S · penacho") and "µg/m³" in e["leyenda"] and e["clases"].get("escala-gases") == 48 and "escala-olor" not in e["clases"], e)
ok("H₂S: sin límite, con P98", cabecera()[3] == "P98", cabecera())
txt = p.res_anios.lbl.text()
ok("H₂S: máximo en µg/m³, sin estimados ni avisos del olor", "µg/m³" in txt and "Estimado" not in txt and "Sin calcular" not in txt, txt)
foto("h2s_penacho")

p._botones_capa["plan_norma"].click()
espera(1.5)
e = estado()
ok("P98 de H₂S: apaga el penacho", e["penacho"] is False and e["leyenda"].startswith("H₂S · Percentil 98") and e["clases"].get("escala-gases"), e)
foto("h2s_p98")
elige("NOx")
e = estado()
ok("NOₓ: sigue en la misma capa, con su norma", e["penacho"] is False and e["leyenda"].startswith("NOₓ · 19.ª hora más alta del peor año (límite 200)"), e)
ok("NOₓ: el botón dice norma y la tabla, sus criterios", p._botones_capa["plan_norma"].text() == "Ocultar norma" and cabecera()[3:] == ["1 h", "Año"], (p._botones_capa["plan_norma"].text(), cabecera()))
foto("nox_p998")
elige("SO2")
ok("SO₂: su norma", p._botones_capa["plan_norma"].text() == "Ocultar norma" and estado()["leyenda"].startswith("SO₂ · 25.ª hora más alta del peor año (límite 350)"), estado()["leyenda"])
elige("olor")
e = estado()
ok("Olor otra vez: P98 y su escala", p._botones_capa["plan_norma"].text() == "Ocultar P98" and e["leyenda"].startswith("Olor · Percentil 98") and e["clases"].get("escala-olor"), e)

p._botones_capa["plan_norma"].click()
espera(0.8)
elige("NH3")
e = estado()
ok("Sin ninguna capa a la vista, cambiar no enciende ninguna", e["penacho"] is False and e["imagenes"] == 0 and not any(b.isChecked() for b in p._botones_capa.values() if b.isVisible() and b.text().startswith("Ocultar")), e)
ok("Y el botón de NH₃ dice P98", p._botones_capa["plan_norma"].text() == "Ver P98")
p._botones_capa["penacho"].click()
espera(1.2)
ok("El penacho vuelve con el gas elegido", estado()["leyenda"].startswith("NH₃ · penacho"), estado()["leyenda"])

# Tooltips de los núcleos, con la magnitud elegida
from teodors.operacion import simulacion as planes_calculo
ok("Valores de la magnitud elegida", v._magnitud == "NH3" and len(v._valores.get("anios")) > 1000)
texto = v._tabla_plan(*next(iter(v._valores.get("anios"))))
ok("Tooltip con la magnitud y su unidad", "NH₃ (µg/m³)" in texto and "P98" in texto, texto[:150])

# Los valores de la tabla son los del fichero de esa magnitud
r = v._resultados["anios"]
for k in r["orden"]:
    m = r["magnitudes"][k]
    print(f"  {m['nombre']:<6} máx. {m['maximos']['maximo']:.4g} {m['unidad']} · {m['focos']} focos", file=out, flush=True)
print(f"Tiempo: {r['segundos']} s (series {r['segundos_serie']} s)", file=out, flush=True)

# Limpiar al cambiar de meteorología
p.set_horizonte_meteo("ninguno")
espera(1.5)
e = estado()
ok("Ninguno: se limpia y el selector desaparece", e["imagenes"] == 0 and not p.res_anios.isVisible() and v._resultados["anios"] is None, e)

# La ficha de los focos
from teodors.gui.ventana_focos import VentanaFocos
vf = VentanaFocos(v.emp, v.ajustes)
for b in FLAGS:
    vf.setWindowFlag(getattr(QtCore.Qt.WindowType, b), True)
vf.show()
espera(2)


def ficha_de(i):
    vf._elegir_id(i)
    espera(0.6)
    return next(w for w in vf.findChildren(QtWidgets.QWidget) if hasattr(w, "lbl_olor") and w.isVisible())


def texto_olor(i):
    return ficha_de(i).lbl_olor.text()


t = texto_olor("F04")
ok("Ficha: venteo, olor estimado por H₂S", "estimada por H₂S" in t, t)
foto("ficha_venteo", vf)
t = texto_olor("F03")
ok("Ficha: biofiltro, olfatometría", "Emisión de olor:" in t and "estimada" not in t, t)
t = texto_olor("F12")
ok("Ficha: antorcha, sin olor pero sin aviso de que faltan datos", "Sin emisión de olor" in t and "Faltan" not in t, t)
ok("Ficha: nada de «medido o estimado» por elegir", not [b.text() for b in vf.findChildren(QtWidgets.QRadioButton) if b.isVisible() and "gas dominante" in b.text()])
etiquetas = [l.text() for l in vf.findChildren(QtWidgets.QLabel) if l.isVisible()]
ok("Ficha de un punto: caudal normal", any("Caudal normal" in x for x in etiquetas), [x for x in etiquetas if "audal" in x])
foto("ficha_antorcha", vf)
vf.close()
espera(0.5)

# Modo CIRCE: añadir un gas sin tocar los focos guardados
from teodors import planta as config
config.actual().MODO_EDICION = True
vc = VentanaFocos(v.emp, v.ajustes)
for b in FLAGS:
    vc.setWindowFlag(getattr(QtCore.Qt.WindowType, b), True)
vc.show()
espera(2)
vf = vc
fi = ficha_de("F02")
foco = fi.f
ok("CIRCE: el pretratamiento no tiene gases", foco["gases"] == [] and "Emisión de olor:" in fi.lbl_olor.text())
foco["olor"].pop("valor", None)
foco["gases"].append({"gas": "H2S", "valor": 0.002, "unidad": "g/s"})
foco["gases"].append({"gas": "CH3SH", "valor": 0.002, "unidad": "g/s"})
fi.refrescar()
ok("CIRCE: sin olfatometría y con gases, estima por el dominante", "estimada por CH₃SH" in fi.lbl_olor.text(), fi.lbl_olor.text())
ok("CIRCE: sin pendientes", F.pendientes(foco) == [], F.pendientes(foco))
vc.close()
config.actual().MODO_EDICION = False
guardado = json.loads(config.FOCOS_JSON.read_text(encoding="utf-8"))
ok("El fichero de focos no se ha tocado", next(f for f in guardado["focos"] if f["id"] == "F02")["gases"] == [])
fin()
