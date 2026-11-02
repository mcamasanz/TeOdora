# Dacame fuera de la tabla pero en el mapa; iconos de antes, con su glifo cargado, en los 4 estilos.
import json, os, shutil, sys, time
from pathlib import Path
AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "iconos"
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
COPIA = AQUI / "ENCE_Galera.ini.iconos"
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
from teodors.casos import receptores as receptores_mapa
_planta.asegurar_carpetas(); registro.configurar(_planta.DIR_LOGS, _planta.REGISTRO)
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


t = time.time()
while time.time() - t < 40 and not v.mapa.esta_listo():
    espera(0.3)
espera(8)
p = v.panel

# los iconos, en el mapa
datos = json.loads(js("""(function(){
  var az=document.querySelectorAll('.awesome-marker-icon-blue'), na=document.querySelectorAll('.awesome-marker-icon-orange'),
      am=document.querySelectorAll('.icono-industrial');
  var g=document.querySelector('.awesome-marker-icon-blue i'), f=document.querySelector('.icono-industrial i');
  var est=function(e,z){return getComputedStyle(e,z);};
  var fondo=az.length?est(az[0]).backgroundImage.slice(0,30):'';
  return JSON.stringify({azules:az.length,naranjas:na.length,amarillos:am.length,redondos:document.querySelectorAll('.mapa-nuc').length,
    letra_casa:g?est(g).fontFamily:'',glifo_casa:g?est(g,'::before').content:'',letra_fabrica:f?est(f).fontFamily:'',glifo_fabrica:f?est(f,'::before').content:'',
    fondo_marcador:fondo,fa_cargada:document.fonts.check('900 14px "Font Awesome 6 Free"')});})()"""))
print("Iconos:", datos, file=out, flush=True)
ok("Pueblos: casa azul", datos["azules"] == 40, datos["azules"])
ok("Industrias: fábrica amarilla (26 + Dacame)", datos["amarillos"] == 27, datos["amarillos"])
ok("Deportivos: balón naranja", datos["naranjas"] == 2, datos["naranjas"])
ok("Sin chapas redondas", datos["redondos"] == 0)
ok("Los iconos tienen su dibujo", datos["fa_cargada"] and datos["glifo_casa"] not in ("", "none", "normal") and datos["glifo_fabrica"] not in ("", "none", "normal")
   and "url" in datos["fondo_marcador"], f'{datos["glifo_casa"]} {datos["glifo_fabrica"]}')
foto("01_oscuro_inicio")

# Dacame en la lista, no; en el mapa, sí
n_dacame = js("""(function(){var n=0;for(var k in window){try{if(window[k] instanceof L.Map){window[k].eachLayer(function(l){
  if(l.getTooltip&&l.getTooltip()){var t=l.getTooltip().getContent();if(typeof t==='string'&&t.indexOf('Dacame')>=0)n++;}});}}catch(e){}}return n;})()""")
ok("Dacame sigue en el mapa, una vez", n_dacame == 1, n_dacame)
ok("Dacame sigue como receptor", sum("Dacame" in r["nombre"] for r in receptores_mapa.con_nombre()) == 1)
p.set_horizonte_meteo("reanalisis")
espera(1.5)
p.ir_a("simulacion")
espera(0.3)
t0 = time.time()
p.b_simular.click()
while v._trabajo_sim is not None and time.time() - t0 < 200:
    espera(0.2)
p.b_simular_periodo.click()      # ahora el penacho es de «Simular día»
while v._trabajo_sim is not None and time.time() - t0 < 500:
    espera(0.2)
espera(2)
filas = [p.res_anios.tabla.item(i, 0).text() for i in range(p.res_anios.tabla.rowCount())]
print("Tabla:", filas, file=out, flush=True)
ok("Tabla sin Dacame", filas and not any("Dacame" in f for f in filas))
ok("Tabla con la peor vivienda y Santa Bàrbara", "Peor vivienda (< 2 km)" in filas and "Santa Bàrbara" in filas)
ok("Mismo máximo", "423" in p.res_anios.lbl.text(), p.res_anios.lbl.text()[:75])
n_dacame = js("""(function(){var n=0;for(var k in window){try{if(window[k] instanceof L.Map){window[k].eachLayer(function(l){
  if(l.getTooltip&&l.getTooltip()){var t=l.getTooltip().getContent();if(typeof t==='string'&&t.indexOf('Dacame')>=0&&t.indexOf('ou_E')>=0)n++;}});}}catch(e){}}return n;})()""")
ok("Dacame lleva sus valores en el tooltip", n_dacame == 1, n_dacame)
# la capa de arriba y la planta de cerca
foto("02_oscuro_simulacion")
js("(function(){for(var k in window){try{if(window[k] instanceof L.Map){window[k].setView([40.69,0.474],14);}}catch(e){}}})()")
espera(4)
foto("03_oscuro_cerca")
v._ver_ajustes()
va = v._ventana_ajustes
va.hide()
for x in ("claro", "noche", "contraste", "oscuro"):
    va.tarjetas[x].click()
    espera(1.2)
    foto(f"04_{x}_cerca")
    ok(f"{x}: los mismos iconos", js("document.querySelectorAll('.awesome-marker-icon-blue,.icono-industrial,.awesome-marker-icon-orange').length") > 0)
fin()
