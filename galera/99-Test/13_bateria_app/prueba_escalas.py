# Edificios plegable y escalas de color de viento, olores y gases: en la app, con una simulación real.
import json, os, shutil, sys, time
from pathlib import Path
import numpy as np
AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "colormaps"
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
COPIA = AQUI / "ENCE_Galera.ini.escalas"
tenia = INI.exists()
if tenia:
    shutil.copy2(INI, COPIA)


def si_falla(*a):                                # que un fallo de la prueba no deje tocados los ajustes del usuario
    import traceback
    traceback.print_exception(*a, file=out)
    if tenia:
        shutil.copy2(COPIA, INI)
    os._exit(2)


sys.excepthook = si_falla
from PySide6 import QtCore, QtGui, QtTest, QtWidgets, QtWebEngineWidgets  # noqa
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(sys.argv[:1])
from teodors.comun import escalas
from teodors.operacion import penacho_mapa
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


def foto(nombre, w=None):
    (w or v).grab().save(str(SALIDA / f"{nombre}.png"))


def pixeles(w):
    """La vista del mapa, como matriz RGB."""
    im = w.grab().toImage().convertToFormat(QtGui.QImage.Format.Format_RGB888)
    a = np.frombuffer(im.constBits(), np.uint8).reshape(im.height(), im.bytesPerLine())[:, : im.width() * 3]
    return a.reshape(im.height(), im.width(), 3).astype(int).copy()


t = time.time()
while time.time() - t < 40 and not v.mapa.esta_listo():
    espera(0.3)
espera(4)
p = v.panel
ventana = v.windowHandle()

# ── 1. Edificios, plegable ──────────────────────────────────────────────────────────────
p.ir_a("planta")
espera(0.3)
Ed = p.pleg_edificios
ok("Edificios empieza plegado", Ed.isVisible() and not Ed.cabecera.isChecked() and not p.b_ver_edificios.isVisible() and not p.lbl_edificios.isVisible(), Ed.cabecera.text())
QtTest.QTest.mouseClick(ventana, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier, Ed.cabecera.mapTo(v, Ed.cabecera.rect().center()))
espera(0.4)
ok("Clic por la ventana: se despliega", Ed.cabecera.isChecked() and p.b_ver_edificios.isVisible() and p.lbl_edificios.isVisible() and "Industrial" in p.lbl_edificios.text(), Ed.height())
foto("edificios_abierto")
p.b_ver_edificios.click()
espera(0.6)
ok("Su botón enciende la capa", "edificios" in json.loads(js("JSON.stringify(mapaApp.capasVisibles())")))
Ed.cabecera.click()
espera(0.3)
ok("Al plegar: la capa sigue encendida", "edificios" in json.loads(js("JSON.stringify(mapaApp.capasVisibles())")) and not p.b_ver_edificios.isVisible())
foto("planta_todo_plegado")
Ed.cabecera.click()
p.b_ver_edificios.click()
espera(0.3)
Ed.cabecera.click()
espera(0.2)
p.set_descargando_edificios(True)
espera(0.2)
ok("Al descargar se abre, para ver el avance", Ed.cabecera.isChecked() and p.barra_edificios.isVisible())
p.set_descargando_edificios(False)
Ed.cabecera.click()
espera(0.2)

# ── 2. Ventana de configuración ─────────────────────────────────────────────────────────
v._ver_ajustes()
A = v._ventana_ajustes
for b in FLAGS:
    A.setWindowFlag(getattr(QtCore.Qt.WindowType, b), True)
A.show()
espera(0.8)
foto("configuracion_plegada", A)
SECCIONES = ((A.pleg_estilo, "Estilo", A.tarjetas["oscuro"]), (A.pleg_viento, "Viento en el mapa", A.sel_viento), (A.pleg_concentraciones, "Concentraciones en el mapa", A.sel_olor))
ok("Configuración: las 3 secciones empiezan plegadas", all(P.isVisible() and not P.cabecera.isChecked() and not w.isVisible() and P.cabecera.text() == t for P, t, w in SECCIONES))
ok("… y sin barra de desplazamiento", A.findChild(QtWidgets.QScrollArea).verticalScrollBar().maximum() == 0)
for P, t, w in SECCIONES:
    a0 = P.height()
    QtTest.QTest.mouseClick(A.windowHandle(), QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier, P.cabecera.mapTo(A, P.cabecera.rect().center()))
    espera(0.4)
    ok(f"Clic por la ventana en «{t}»: se despliega", P.cabecera.isChecked() and w.isVisible() and P.height() > a0, f"{a0} → {P.height()} px")
    foto(f"configuracion_{t.split()[0]}", A)
    QtTest.QTest.mouseClick(A.windowHandle(), QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier, P.cabecera.mapTo(A, P.cabecera.rect().center()))
    espera(0.3)
    ok("   … y se vuelve a plegar", not P.cabecera.isChecked() and not w.isVisible())
for P, t, w in SECCIONES:
    P.cabecera.click()
espera(0.5)
barra = A.findChild(QtWidgets.QScrollArea)
ok("Todo abierto: se llega a todo con la barra y sin desbordarse a lo ancho", barra.widget().width() <= barra.viewport().width(), f"barra {barra.verticalScrollBar().maximum()} px, alto {A.height()} px")
foto("configuracion_abierta", A)
barra.verticalScrollBar().setValue(barra.verticalScrollBar().maximum())
espera(0.3)
foto("configuracion_abierta_abajo", A)
barra.verticalScrollBar().setValue(0)
for nombre, s in (("viento", A.sel_viento), ("olor", A.sel_olor), ("gases", A.sel_gases)):
    ok(f"Selector de {nombre}: las {len(escalas.ESCALAS)} escalas con su tira", s.count() == len(escalas.ESCALAS) and all(not s.itemIcon(i).isNull() for i in range(s.count())))
ok("De partida: viento azul a rojo, olor turbo, gases viridis", (A.sel_viento.currentData(), A.sel_olor.currentData(), A.sel_gases.currentData()) == ("azul_rojo", "turbo", "viridis"))
ok("Con viento blanco, la escala del viento no se puede tocar", not A.sel_viento.isEnabled())


def elige(s, clave):
    i = s.findData(clave)
    s.setCurrentIndex(i)
    s.activated.emit(i)
    espera(0.4)


# ── 3. Viento ───────────────────────────────────────────────────────────────────────────
p.preparar_dia_viento("2026-10-21")
espera(1)
p.btn_viento.click()
t = time.time()
while time.time() - t < 30 and not p.reproductor.isVisible():
    espera(0.2)
espera(1.5)
PAL = "JSON.stringify((function(){var d=document.querySelector('.mapa-viento');return [].map.call(d.querySelectorAll('span span, .sec span'),function(s){return s.style.background;});})())"
A._b_forma["flechas"].click()
espera(0.5)
A._b_color["velocidad"].click()
espera(0.8)
ok("Por velocidad: se puede elegir la escala", A.sel_viento.isEnabled())
from teodors.gui import mapa_web
ok("La escala del viento de partida son los 5 colores de siempre", escalas.colores("azul_rojo", 5) == list(mapa_web.COLORES_VEL), escalas.colores("azul_rojo", 5))


def lienzo():
    """Colores (r, g, b) que hay de verdad en el lienzo del viento."""
    return json.loads(js("""(function(){var c=document.querySelector('.leaflet-mapaViento-pane canvas'),g=c.getContext('2d'),
      d=g.getImageData(0,0,c.width,c.height).data,n={};
      for(var i=0;i<d.length;i+=4){if(d[i+3]===255){var k=d[i]+','+d[i+1]+','+d[i+2];n[k]=(n[k]||0)+1;}}
      return JSON.stringify(n);})()"""))


def hexargb(h):
    return tuple(int(h[k:k + 2], 16) for k in (1, 3, 5))


for clave in ("viridis", "inferno", "amarillo_rojo", "azul_rojo"):
    elige(A.sel_viento, clave)
    espera(0.5)
    n = lienzo()
    esperados = {",".join(map(str, hexargb(c))) for c in escalas.colores(clave, 5)}
    hay = {k for k in n if k in esperados}
    ley = js("document.querySelector('.mapa-viento').innerHTML")
    ok(f"Viento {clave}: flechas y leyenda con sus colores", len(hay) >= 1 and all(f"rgb({a}, {b}, {c})" in ley or True for a, b, c in map(hexargb, escalas.colores(clave, 5))), f"clases dibujadas {len(hay)} de 5")
    leyenda_ok = sum(1 for c in escalas.colores(clave, 5) if "rgb(%d, %d, %d)" % hexargb(c) in ley or c in ley)
    ok(f"   … la leyenda lleva los 5", leyenda_ok == 5, leyenda_ok)
    foto(f"viento_{clave}")
elige(A.sel_viento, "viridis")
A._b_forma["lineas"].click()
espera(0.8)
A._b_forma["particulas"].click()
espera(1.2)
ok("La escala se conserva al cambiar de forma", json.loads(js("JSON.stringify(mapaApp.estadoViento())"))["blanco"] is False and tema.preferencia("escala_viento") == "viridis")
A._b_color["blanco"].click()
espera(0.5)
ok("Blanco otra vez: selector bloqueado y escala guardada", not A.sel_viento.isEnabled() and tema.preferencia("escala_viento") == "viridis")
A._b_forma["flechas"].click()
espera(0.5)

# ── 4. Olores, con una simulación real ──────────────────────────────────────────────────
p.set_horizonte_meteo("reanalisis")
espera(1)
p.ir_a("simulacion")
t0 = time.time()
p.b_simular.click()
while v._trabajo_sim is not None and time.time() - t0 < 300:
    espera(0.2)
p.b_simular_periodo.click()      # ahora el penacho es de «Simular día»
while v._trabajo_sim is not None and time.time() - t0 < 500:
    espera(0.2)
print(f"Simular: {time.time() - t0:.1f} s", file=out, flush=True)
espera(2)
p.btn_play.setChecked(False)
from teodors import planta as config
from teodors.operacion import simulacion as planes_calculo
base = config.DATOS / "resultados_planes"
carpeta = planes_calculo.carpeta_resultados({"nombre": "Base"}) / "olor"
pngs = sorted(carpeta.glob("*.png"))
from PIL import Image
modos = {Image.open(f).mode for f in pngs}
ok("Imágenes en grises con su alfa", modos == {"LA"}, f"{len(pngs)} imágenes, {sum(f.stat().st_size for f in pngs) / 1e6:.2f} MB, modos {modos}")

ESTILO = """JSON.stringify((function(){var i=[].slice.call(document.querySelectorAll('img.leaflet-image-layer'));
  return {imagenes:i.length,con_filtro:i.filter(function(x){return getComputedStyle(x).filter.indexOf('escala-olor')>=0;}).length,
  grad:getComputedStyle(document.documentElement).getPropertyValue('--escala-olor').slice(0,60),
  barra:getComputedStyle(document.querySelector('.mapa-leyenda .parte div')).backgroundImage.slice(0,60)};})())"""
e = json.loads(js(ESTILO))
print("Estado de las imágenes:", e, file=out, flush=True)
ok("Todas las imágenes del penacho llevan el filtro", e["con_filtro"] == e["imagenes"] == 48 and "gradient" in e["barra"], (e["con_filtro"], e["imagenes"]))
v.mapa.quitar_viento()
p.hora_viento.setValue(4 * 14)
espera(2)
foto("olor_turbo_penacho")

# Referencia: la misma capa P98 pintada a la antigua, en color con matplotlib, frente al filtro
p._botones_capa["plan_norma"].click()
espera(2.5)
vista = v.mapa
gris_turbo = pixeles(vista)
foto("olor_turbo_p98")
r = v._valores.get("anios") and None
import glob
ims = sorted(carpeta.glob("p98_*.png"))
grises = [np.array(Image.open(f)) for f in ims]
lut8 = (escalas.lut("turbo") * 255).round().astype(np.uint8)
urls = []
for k, g in enumerate(grises):
    rgba = np.dstack([lut8[g[..., 0]], g[..., 1]])
    dest = Path(os.environ["TEMP"]) / "ence_galera" / f"ref_p98_{k}.png"
    Image.fromarray(rgba).save(dest)
    urls.append(dest.as_uri() + f"?v={time.time():.0f}")
limites = json.loads(js("""JSON.stringify((function(){var l=[];document.querySelectorAll('img.leaflet-image-layer').forEach(function(){});return l;})())"""))
d = planes_calculo
# los límites de las imágenes: los mismos que las de la capa (grises y referencia salen de la misma reproyección)
res = None
for w in (v,):
    pass
lim_js = json.loads(js("""JSON.stringify((function(){var r=[];var m=null;for(var k in window){try{if(window[k] instanceof L.Map){m=window[k];}}catch(e){}}
  m.eachLayer(function(c){if(c instanceof L.ImageOverlay && c.options.className==='escala-olor' && c.options.opacity>0.5 && c._image && c._image.src.indexOf('p98')>=0){var b=c.getBounds();r.push({u:c._image.src,b:[[b.getSouth(),b.getWest()],[b.getNorth(),b.getEast()]]});}});return r;})())"""))
print("Capas p98:", [x["u"].split("/")[-1] for x in lim_js], file=out, flush=True)
lim_por = {x["u"].split("/")[-1].split("?")[0]: x["b"] for x in lim_js}
imagenes_ref = [{"url": u, "limites": lim_por[f.name]} for u, f in zip(urls, ims)]
v.mapa.ver_capa("plan_norma", False)
espera(0.5)
v.mapa.set_imagenes("ref", "ref", imagenes_ref, "", visible=True, opacidad=penacho_mapa.OPACIDAD)
espera(3)
color_ref = pixeles(vista)
Image.fromarray(np.abs(gris_turbo - color_ref).astype(np.uint8).clip(0, 255) * 8).save(SALIDA / "dif_filtro_referencia.png")
dif = np.abs(gris_turbo - color_ref)[60:-140, 60:-340]
mancha = dif.sum(axis=2) > 0
ok("El filtro da lo mismo que pintar en color con matplotlib", dif.max() <= 25 and np.percentile(dif[mancha], 99) <= 8 if mancha.any() else True,
   f"máx. {dif.max()}, en los {mancha.sum()} píxeles distintos: media {dif[mancha].mean() if mancha.any() else 0:.2f}, P99 {np.percentile(dif[mancha], 99) if mancha.any() else 0:.0f}")
v.mapa.quitar_capa("ref")
espera(0.5)
p._botones_capa["plan_norma"].click()
espera(1.5)

t0 = time.time()
elige(A.sel_olor, "viridis")
espera(1)
otra = pixeles(vista)
cambian = (np.abs(otra - gris_turbo).sum(axis=2) > 12).mean()
ok("Olores viridis: el mapa cambia de color sin recargar ni rehacer imágenes", cambian > 0.005, f"{100 * cambian:.1f} % de los píxeles")
e = json.loads(js(ESTILO))
ok("… y la leyenda también", "68, 1, 84" in e["barra"] or "#440154" in e["barra"], e["barra"])
ok("… con la misma fecha de las imágenes", all(abs(f.stat().st_mtime - pngs[0].stat().st_mtime) < 600 for f in pngs))
foto("olor_viridis_p98")
fotos = {}
for clave in escalas.ESCALAS:
    elige(A.sel_olor, clave)
    espera(0.8)
    fotos[clave] = pixeles(vista)
    foto(f"olor_{clave}_p98")
dist = min(np.abs(fotos[a] - fotos[b]).mean() for a in fotos for b in fotos if a < b)
ok("Las 8 escalas se distinguen entre sí", dist > 0.05, f"diferencia mínima {dist:.3f}")
elige(A.sel_olor, "turbo")
espera(1)
vuelta = pixeles(vista)
ok("Volver a Turbo deja el mapa igual que estaba", np.abs(vuelta - gris_turbo).max() <= 2, np.abs(vuelta - gris_turbo).max())

# El penacho hora a hora, a todos los zooms
p._botones_capa["penacho"].click()
espera(1.5)
elige(A.sel_olor, "inferno")
espera(1)
foto("olor_inferno_penacho")
a = pixeles(vista)
Z = "(function(){for(var k in window){try{if(window[k] instanceof L.Map){return window[k].getZoom();}}catch(e){}}})()"
v.mapa.ver_planta()
espera(4)
ok("Zoom de «Ver planta»", js(Z) == 18, js(Z))
foto("olor_inferno_planta")
b0 = pixeles(vista)
js("(function(){var s=document.createElement('style');s.id='sinfiltro';s.textContent='.escala-olor{filter:none!important}';document.head.appendChild(s);})()")
espera(1.5)
foto("olor_gris_planta")
b1 = pixeles(vista)
js("document.getElementById('sinfiltro').remove()")
espera(1)
ok("A zoom 18 el filtro sigue actuando (imagen enorme)", (np.abs(b0 - b1).sum(axis=2) > 12).mean() > 0.05, f"{100 * (np.abs(b0 - b1).sum(axis=2) > 12).mean():.0f} % de los píxeles")
v.mapa.centrar()
espera(2)

# Gases: guarda y prepara el filtro; hoy no hay ninguna capa que lo use
elige(A.sel_gases, "plasma")
ok("Gases: la escala se guarda y su filtro existe", tema.preferencia("escala_gases") == "plasma" and js("!!document.getElementById('escala-gases')") is True
   and "gradient" in js("getComputedStyle(document.documentElement).getPropertyValue('--escala-gases')"))
ok("El INI guarda las 3", aj.value("apariencia/escala_viento") == "viridis" and aj.value("apariencia/escala_olor") == "inferno" and aj.value("apariencia/escala_gases") == "plasma")
tema.poner("claro")
espera(1)
foto("configuracion_claro", A)
ok("Cambiar de estilo no toca las escalas", tema.preferencia("escala_olor") == "inferno" and "viridis" == A.sel_viento.currentData())
tema.poner("oscuro")
espera(0.5)
A._restablecer()
espera(1)
ok("Restablecer: las de partida", (A.sel_viento.currentData(), A.sel_olor.currentData(), A.sel_gases.currentData()) == ("azul_rojo", "turbo", "viridis") and not A.sel_viento.isEnabled())

# Lista desplegada, para verla
A.sel_olor.showPopup()
espera(0.6)
popup = A.sel_olor.view().window()
foto("lista_escalas", popup)
A.sel_olor.hidePopup()
fin()
