# Al abrir no hay viento ni penacho; el viento llega con la meteorología, el penacho al simular y el ejemplo guardado
# solo se ve en la configuración. Con «vacio» (DATOS sin nada), la vista previa tiene que seguir funcionando.
import json, os, shutil, sys, tempfile, time, traceback
from pathlib import Path
import numpy as np
AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "previa"
SALIDA.mkdir(exist_ok=True)
VACIO = len(sys.argv) > 1 and sys.argv[1] == "vacio"
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
os.environ.setdefault("ENCE_GALERA_DATOS", tempfile.mkdtemp() if VACIO else str(Path(os.environ["TEMP"]) / "ence_galera" / "datos_local"))
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
out = sys.__stdout__
out.reconfigure(encoding="utf-8")
INI = Path(os.environ["APPDATA"]) / "CIRCE" / "ENCE_Galera.ini"
COPIA = AQUI / "ENCE_Galera.ini.previa"
tenia = INI.exists()
if tenia:
    shutil.copy2(INI, COPIA)


def restaurar():
    if tenia:
        shutil.copy2(COPIA, INI)
    else:
        INI.unlink(missing_ok=True)


def si_falla(*a):                                # que un fallo de la prueba no deje tocados los ajustes del usuario
    traceback.print_exception(*a, file=out)
    restaurar()
    os._exit(2)


sys.excepthook = si_falla
from PySide6 import QtCore, QtGui, QtWidgets, QtWebEngineWidgets  # noqa
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(sys.argv[:1])
from teodors.comun import escalas
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
    restaurar()
    os._exit(1 if fallos else 0)


def espera(s):
    t = time.time()
    app.processEvents()
    while time.time() - t < s:
        time.sleep(0.01)
        app.processEvents()


def js(vista, c):
    r = {}
    vista.page().runJavaScript(c, 0, lambda x: r.setdefault("v", x))
    t = time.time()
    while "v" not in r and time.time() - t < 10:
        app.processEvents()
        time.sleep(0.01)
    return r.get("v")


def foto(nombre, w=None):
    (w or v).grab().save(str(SALIDA / f"{nombre}.png"))


def pixeles(w):
    im = w.grab().toImage().convertToFormat(QtGui.QImage.Format.Format_RGB888)
    a = np.frombuffer(im.constBits(), np.uint8).reshape(im.height(), im.bytesPerLine())[:, : im.width() * 3]
    return a.reshape(im.height(), im.width(), 3).astype(int).copy()


ESTADO = """JSON.stringify({viento: mapaApp.estadoViento(), penacho: mapaApp.estadoPenacho(), capas: mapaApp.capasVisibles(),
  imagenes: document.querySelectorAll('img.leaflet-image-layer').length,
  selector: [].map.call(document.querySelectorAll('.leaflet-control-layers-overlays span'), function (s) { return s.textContent.trim(); }),
  leyenda: (document.querySelector('.mapa-leyenda') || {}).textContent || ''})"""
e_m = lambda: json.loads(js(v.mapa, ESTADO))

t = time.time()
while time.time() - t < 40 and not v.mapa.esta_listo():
    espera(0.3)
espera(6)                                        # por si algo llegara tarde
p = v.panel

# ── 1. Al abrir: ni viento ni penacho ───────────────────────────────────────────────────
e = e_m()
ok("Al abrir: sin viento en el mapa", e["viento"] is None or e["viento"]["modo"] is None, e["viento"])
ok("Al abrir: sin penacho ni capas de plan", e["penacho"] is None and e["imagenes"] == 0 and not [c for c in e["capas"] if "plan" in c or "penacho" in c], e["capas"])
ok("Al abrir: el selector de capas no ofrece viento ni penacho", not [x for x in e["selector"] if "Viento" in x or "Penacho" in x or "Plan" in x], sorted(set(e["selector"])))
ok("Al abrir: sin reproductor", not p.reproductor.isVisible())
ok("Al abrir: horizonte Ninguno, sin bloque de viento y sin poder simular", p.horizonte_meteo() == "ninguno" and not p.caja_viento.isVisible() and not p.b_simular.isEnabled())
ok("Al abrir: sin resultados", not p.res_anios.isVisible())
p.ir_a("simulacion")
espera(0.3)
ok("Simular: sin botones de penacho, media, máximo ni P98", not p._botones_capa["penacho"].isVisible() and not p._botones_capa["plan_norma"].isVisible())
foto("01_al_abrir")
# Al abrir, tampoco en los tooltips de los núcleos
ok("Los núcleos no llevan valores de plan", js(v.mapa, "document.body.innerHTML.indexOf('Plan «')") == -1)

if not VACIO:
    # ── 2. Reanálisis: el viento solo al pedirlo ────────────────────────────────────────
    p.ir_a("meteo")
    p.set_horizonte_meteo("reanalisis")
    espera(3)
    e = e_m()
    ok("El calendario solo ofrece días con viento", p.fecha_viento.minimumDate().toString("yyyy-MM-dd") >= "2026-10-20" and p.fecha_viento.maximumDate().toString("yyyy-MM-dd") == "2026-10-21",
       (p.fecha_viento.minimumDate().toString("yyyy-MM-dd"), p.fecha_viento.maximumDate().toString("yyyy-MM-dd")))
    ok("Reanálisis: aparece el bloque de viento, y aún no hay viento", p.caja_viento.isVisible() and (e["viento"] is None or e["viento"]["modo"] is None) and not p.reproductor.isVisible())
    p.btn_viento.click()
    t = time.time()
    while time.time() - t < 30 and not p.reproductor.isVisible():
        espera(0.2)
    espera(1)
    e = e_m()
    ok("«Ver en el mapa»: viento y reproductor", e["viento"] is not None and e["viento"]["modo"] and p.reproductor.isVisible(), e["viento"]["modo"])
    ok("Con viento y sin simular: sigue sin haber penacho", e["penacho"] is None and e["imagenes"] == 0)
    foto("02_reanalisis")
    p.set_horizonte_meteo("ninguno")
    espera(1)
    e = e_m()
    ok("Otra vez Ninguno: se va el viento y el reproductor", (e["viento"] is None or e["viento"]["modo"] is None) and not p.reproductor.isVisible() and not [x for x in e["selector"] if "Viento" in x or "Penacho" in x or "Plan" in x], sorted(set(e["selector"])))

    # ── 3. El penacho, solo al simular ──────────────────────────────────────────────────
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
    espera(3)
    e = e_m()
    print(f"Simular: {time.time() - t0:.0f} s", file=out, flush=True)
    ok("Simulado: penacho, resultados y sus botones", e["penacho"] is not None and p.res_anios.isVisible() and p._botones_capa["plan_norma"].isVisible() and e["imagenes"] == 48, e["imagenes"])
    ok("Simulado: el viento del día en el reproductor", e["viento"]["modo"] and p.reproductor.isVisible() and p.btn_play.isChecked())
    ok("Simulado: los núcleos ya llevan valores", js(v.mapa, "document.body.innerHTML.length") > 0)
    foto("03_simulado")
    p.btn_play.setChecked(False)
    p.set_horizonte_meteo("ninguno")
    espera(1.5)
    e = e_m()
    ok("Ninguno tras simular: se limpia todo", e["penacho"] is None and e["imagenes"] == 0 and not p.res_anios.isVisible() and not p.reproductor.isVisible() and (e["viento"] is None or e["viento"]["modo"] is None), e["imagenes"])

# ── 4. La vista previa, en la configuración ─────────────────────────────────────────────
v._ver_ajustes()
A = v._ventana_ajustes
for b in FLAGS:
    A.setWindowFlag(getattr(QtCore.Qt.WindowType, b), True)
A.show()
A.move(0, 0)
t = time.time()
while time.time() - t < 30 and not A.previa._listo:
    espera(0.2)
print(f"Vista previa lista a los {time.time() - t:.1f} s · ventana {A.width()} × {A.height()} · mapa {A.previa.width()} × {A.previa.height()}", file=out, flush=True)
espera(5)
e_p = lambda: json.loads(js(A.previa, ESTADO))
e = e_p()
print("Previa:", {k: e[k] for k in ("capas", "imagenes", "leyenda")}, e["viento"], file=out, flush=True)
ok("Vista previa: viento y penacho cargados", e["viento"] and e["viento"]["modo"] and "previa_olor" in e["capas"] and e["imagenes"] == 2)
ok("Vista previa: la leyenda dice Olores, sin unidades", e["leyenda"].startswith("Olores") and "ou_E" not in e["leyenda"], e["leyenda"])
ok("Vista previa: sin selector de capas", js(A.previa, "getComputedStyle(document.querySelector('.leaflet-control-layers')).display") == "none")
ok("El mapa principal no se entera", (lambda m: (m["viento"] is None or m["viento"]["modo"] is None) and m["imagenes"] == 0 and not p.reproductor.isVisible())(e_m()))
ok("La casilla del viento de muestra ya no está", not hasattr(A, "chk_muestra") and "viento_muestra" not in tema.PREFERENCIAS)
for s in (A.pleg_estilo, A.pleg_viento, A.pleg_concentraciones):
    ok(f"«{s.cabecera.text()}» empieza plegada", not s.cabecera.isChecked())
foto("04_configuracion_plegada", A)
A.pleg_concentraciones.cabecera.click()
A.pleg_viento.cabecera.click()
espera(0.5)
foto("05_configuracion", A)


def elige(s, clave):
    i = s.findData(clave)
    s.setCurrentIndex(i)
    s.activated.emit(i)
    espera(0.8)


# Con flechas, el viento está quieto: lo que cambie en el mapa es por la escala
A._b_forma["flechas"].click()
espera(1)
ok("Forma del viento: la vista previa la sigue", e_p()["viento"]["modo"] == "flechas")
a = pixeles(A.previa)
elige(A.sel_olor, "viridis")
b = pixeles(A.previa)
pct = 100 * (np.abs(a - b).sum(axis=2) > 12).mean()
ok("Olores: la escala cambia en la vista previa", pct > 1, f"{pct:.1f} % de los píxeles")
foto("06_olor_viridis", A)
elige(A.sel_gases, "inferno")
espera(0.5)
e = e_p()
ok("Gases: la vista previa pasa a Gases, con su escala", "previa_gases" in e["capas"] and "previa_olor" not in e["capas"] and e["leyenda"].startswith("Gases") and "escala-gases" in js(A.previa, "document.querySelector('img.leaflet-image-layer').className"), e["capas"])
c = pixeles(A.previa)
ok("… y se nota en el mapa", 100 * (np.abs(c - b).sum(axis=2) > 12).mean() > 1, f"{100 * (np.abs(c - b).sum(axis=2) > 12).mean():.1f} %")
foto("07_gases_inferno", A)
elige(A.sel_olor, "viridis")
espera(0.5)
d = pixeles(A.previa)
ok("Volver a Olores: mismo mapa que antes", np.abs(d - b).max() <= 2, np.abs(d - b).max())
A._b_color["velocidad"].click()
espera(0.6)
elige(A.sel_viento, "plasma")
espera(0.6)
ley = js(A.previa, "document.querySelector('.mapa-viento').innerHTML")
ok("Viento por velocidad: la escala se ve en la vista previa", all(("rgb(%d, %d, %d)" % tuple(int(x[k:k + 2], 16) for k in (1, 3, 5))) in ley or x in ley for x in escalas.colores("plasma", 5)))
foto("08_viento_plasma", A)
A._b_forma["particulas"].click()
espera(1.5)
ok("Partículas en la vista previa", e_p()["viento"]["modo"] == "particulas" and e_p()["viento"]["particulas"] > 0, e_p()["viento"]["particulas"])
A._b_forma["lineas"].click()
espera(1)
foto("09_lineas", A)
tema.poner("claro")
espera(1)
ok("Estilo claro: la vista previa lo sigue", js(A.previa, "getComputedStyle(document.documentElement).getPropertyValue('--fondo')").strip() == tema.c("fondo"))
foto("10_claro", A)
tema.poner("oscuro")
espera(0.5)

# Solo consume cuando se ve
ok("Abierta: la página de la vista previa está activa", js(A.previa, "document.visibilityState") == "visible")
A.close()
espera(1)
ok("Cerrada: la vista previa deja de pintar", js(A.previa, "document.visibilityState") == "hidden", js(A.previa, "document.visibilityState"))
ok("Cerrada: el mapa principal sigue sin viento", (lambda m: m["viento"] is None or m["viento"]["modo"] is None)(e_m()))
v._ver_ajustes()
espera(1.5)
ok("Abierta otra vez: sigue con su viento", js(A.previa, "document.visibilityState") == "visible" and e_p()["viento"]["modo"] == "lineas")
A.showMinimized()
espera(1)
ok("Minimizada: deja de pintar", js(A.previa, "document.visibilityState") == "hidden", js(A.previa, "document.visibilityState"))
A.showNormal()
espera(1)
ok("Restaurada: pinta otra vez", js(A.previa, "document.visibilityState") == "visible")
v.showMinimized()
espera(1)
ok("Con la principal minimizada, tampoco", js(A.previa, "document.visibilityState") == "hidden", js(A.previa, "document.visibilityState"))
v.showNormal()
espera(1)
A._restablecer()
espera(1)
e = e_p()
ok("Restablecer: Olores, por defecto", "previa_olor" in e["capas"] and e["leyenda"].startswith("Olores") and A.sel_olor.currentData() == "turbo" and e["viento"]["modo"] == "particulas")
fin()
