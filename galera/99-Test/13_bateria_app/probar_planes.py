# Prueba de la ventana de planes sin pantalla: clics reales (QTest), guardar y volver a abrir, capturas.
import os, sys, tempfile, json
from pathlib import Path
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
SALIDA = Path(__file__).resolve().parent
os.environ.setdefault("ENCE_GALERA_DATOS", str(Path(os.environ["TEMP"]) / "ence_galera" / "datos_local"))
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
out = sys.__stdout__
out.reconfigure(encoding="utf-8")
from PySide6 import QtCore, QtTest, QtWidgets, QtWebEngineWidgets  # noqa
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(sys.argv[:1])
from teodors.operacion import planes as E
from teodors.comun import registro
from teodors.gui.ventana_planes import VentanaPlanes
registro.configurar()
fallos = []


def ok(nombre, si, detalle=""):
    print(("OK  " if si else "MAL ") + nombre, detalle, file=out, flush=True)
    if not si:
        fallos.append(nombre)


def clic(w, mod=QtCore.Qt.KeyboardModifier.NoModifier):
    QtTest.QTest.mouseClick(w, QtCore.Qt.MouseButton.LeftButton, mod)
    app.processEvents()


d = tempfile.mkdtemp()
aj = QtCore.QSettings(str(Path(d) / "aj.ini"), QtCore.QSettings.Format.IniFormat)
from teodors import planta as _c
v = VentanaPlanes(_c.cargar_emplazamiento(), aj, carpeta=d)
v.setAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen)
v.resize(1400, 860)
v.show()
app.processEvents()
ok("arranca en la Base, sin nada que guardar", v.esc["nombre"] == E.BASE and not v.b_guardar.isEnabled())
ok("13 focos en la lista", v.lista.count() == 13)
ids = [f["id"] for f in v.catalogo["focos"]]

# Pila 1: semanal, con volteos L, X y V de 8 a 10 y el resto al 20 %; domingo apagado
v.lista.setCurrentRow(ids.index("F08"))
app.processEvents()
clic(v.botones_plan["semanal"])
ok("semanal: 7 días", len(v.celdas) == 7 and len(v._pf()["dias"]) == 7)
ok("hay cambios sin guardar", v.b_guardar.isEnabled())
v.esp_de.setValue(8); v.esp_a.setValue(10); v.esp_resto.setValue(20)
clic(v.celdas[0])
clic(v.celdas[2], QtCore.Qt.KeyboardModifier.ControlModifier)
clic(v.celdas[4], QtCore.Qt.KeyboardModifier.ControlModifier)
ok("Ctrl + clic elige varios días", v.elegidos == {0, 2, 4}, v.lbl_dia.text())
v._poner_horario()
pf = v._pf()
ok("el horario llega a L, X y V", all(E.perfil_dia(pf, i)[8] == 1.0 and E.perfil_dia(pf, i)[12] == 0.2 for i in (0, 2, 4)))
clic(v.celdas[1])
v.esp_de.setValue(0); v.esp_a.setValue(1); v.esp_resto.setValue(20)
v._aplicar([0.2] * 24)
clic(v.celdas[3]); v._aplicar([0.2] * 24)
clic(v.celdas[5]); v._aplicar([0.2] * 24)
clic(v.celdas[6]); v._aplicar([0.0] * 24)
ok("3 tipos de día, sin duplicar", len(pf["perfiles"]) == 3, str(pf["dias"]))

# editor: arrastrar con el ratón sube la barra de las 12
clic(v.celdas[0])
m = v.editor._marco()
x = int(m.left() + 12.5 * m.width() / 24)
QtTest.QTest.mousePress(v.editor, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(x, int(m.top() + 0.5 * m.height())))
QtTest.QTest.mouseRelease(v.editor, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(x, int(m.top() + 0.5 * m.height())))
app.processEvents()
ok("ratón en el editor: 12 h al 50 %", E.perfil_dia(pf, 0)[12] == 0.5, str(E.perfil_dia(pf, 0)[12]))
ok("cambiar el lunes no toca el miércoles", E.perfil_dia(pf, 2)[12] == 0.2)
v._perfil_editado([1.0 if 8 <= h < 10 else 0.2 for h in range(24)])
clic(v.celdas[0])
v.resize(1400, 860); app.processEvents()
v.grab().save(str(SALIDA / "planes_semanal.png"))

# Biofiltro: la lista refleja la emisión media
v.lista.setCurrentRow(ids.index("F03")); app.processEvents()
v._aplicar([0.75] * 24); app.processEvents()
ok("sin factor", not hasattr(v, "esp_factor") and "factor" not in v._pf())
txt = v.lista.itemWidget(v.lista.currentItem()).tipo.text()
ok("la lista lo refleja", "75 %" in txt, txt)

# Digestato: mensual con el calendario de noviembre de 2026
v.lista.setCurrentRow(ids.index("F07")); app.processEvents()
v.esc["mes"] = "2026-11"
clic(v.botones_plan["semanal"])
clic(v.celdas[5]); v._aplicar([0.0] * 24)
clic(v.celdas[6]); v._aplicar([0.0] * 24)
clic(v.celdas[1]); v._aplicar([1.0 if 8 <= h < 12 else 0.3 for h in range(24)])
clic(v.botones_plan["mensual"])
pf7 = v._pf()
ok("mensual: 30 celdas en noviembre", len(v.celdas) == 30, f"{len(pf7['dias'])} días en el fichero")
ok("el 1-nov-2026, domingo: apagado", sum(E.perfil_dia(pf7, 0)) == 0.0)
ok("el 3-nov-2026, martes: el horario del martes", E.perfil_dia(pf7, 2)[9] == 1.0)
clic(v.celdas[14], QtCore.Qt.KeyboardModifier.NoModifier)       # día 15, domingo
clic(v.celdas[19], QtCore.Qt.KeyboardModifier.ShiftModifier)
ok("Mayús + clic elige del 15 al 20", v.elegidos == {14, 15, 16, 17, 18, 19}, v.lbl_dia.text())
v._aplicar([1.0 if 6 <= h < 14 else 0.0 for h in range(24)])
clic(v.celdas[14])
v.grab().save(str(SALIDA / "planes_mensual.png"))

# guardar y volver a abrir
v.esc = E.nuevo(v.catalogo, "Volteos de noviembre", v.esc)
ok("guarda", v.guardar() is True and not v.b_guardar.isEnabled())
ok("sale en la lista de guardados", v.cmb_planes.findText("Volteos de noviembre") >= 0)
guardado = json.loads(json.dumps(v.esc["focos"]))
tam = (Path(d) / "volteos_de_noviembre.json").stat().st_size
print(f"Fichero: {tam / 1024:.1f} kB", file=out, flush=True)
v.cmb_planes.setCurrentIndex(0); v._plan_elegido(0)
ok("vuelve a la Base", v.esc["nombre"] == E.BASE and v._pf()["plan"] == "diario")
i = v.cmb_planes.findText("Volteos de noviembre")
v.cmb_planes.setCurrentIndex(i); v._plan_elegido(i)
ok("el plan se lee igual", v.esc["focos"] == guardado and v.esc["mes"] == "2026-11")
v.lista.setCurrentRow(ids.index("F07")); app.processEvents()
ok("abre su calendario", len(v.celdas) == 30 and v.cmb_mes.currentData() == 11 and v.cmb_anio.currentData() == 2026)

# Diario
v.lista.setCurrentRow(ids.index("F01")); app.processEvents()
ok("diario: una celda", len(v.celdas) == 1 and v.lbl_dia.text() == "Todos los días")
v.grab().save(str(SALIDA / "planes_diario.png"))
from teodors import planta as config
from teodors.gui.ventana_focos import VentanaFocos
vf = VentanaFocos(config.cargar_emplazamiento(), aj)
vf.setAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen)
vf.resize(1320, 780)
vf.show()
import time
t0 = time.time()
while time.time() - t0 < 1.5:
    app.processEvents(); time.sleep(0.01)
vf.grab().save(str(SALIDA / "focos_oscuro.png"))
from teodors.gui.ventana import VentanaPrincipal
vp = VentanaPrincipal()
vp.setAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen)
vp.show()
vp._ventana_planes = None
t0 = time.time()
while time.time() - t0 < 2:
    app.processEvents(); time.sleep(0.01)
vp._ver_planes()
vp._ventana_planes.setAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen)
ok("se abre desde la app", vp._ventana_planes.isVisible() and vp._ventana_planes.lista.count() == 13)
primero = vp._ventana_planes
vp._ver_planes()
ok("una sola ventana", vp._ventana_planes is primero)
acciones = [a.text() for m in vp.menu_app.actions() if m.menu() for a in m.menu().actions()]
ok("está en el menú Planta", any("Planes de operación" in a for a in acciones))
print("esquema", app.styleHints().colorScheme(), file=out, flush=True)
print("FALLOS:", fallos or "ninguno", file=out, flush=True)
os._exit(1 if fallos else 0)
