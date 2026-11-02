# Indicador de hora y valor en el editor de la ventana de planes, con eventos de ratón simulados y capturas fieles.
import os, sys, tempfile, time
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
SALIDA = Path(__file__).resolve().parent / "indicador"
SALIDA.mkdir(exist_ok=True)
os.environ.setdefault("ENCE_GALERA_DATOS", str(Path(os.environ["TEMP"]) / "ence_galera" / "datos_local"))
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
out = sys.__stdout__
out.reconfigure(encoding="utf-8")
from PySide6 import QtCore, QtGui, QtTest, QtWidgets, QtWebEngineWidgets  # noqa
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(sys.argv[:1])
from teodors import planta as config
from teodors.operacion import planes as E
from teodors.comun import registro
from teodors.gui import tema
from teodors.gui.ventana_planes import VentanaPlanes
_planta.asegurar_carpetas(); registro.configurar(_planta.DIR_LOGS, _planta.REGISTRO)
fallos = []
Boton = QtCore.Qt.MouseButton.LeftButton


def ok(nombre, si, detalle=""):
    print(("OK  " if si else "MAL ") + nombre, detalle, file=out, flush=True)
    if not si:
        fallos.append(nombre)


def espera(s=0.05):
    t0 = time.time()
    while time.time() - t0 < s:
        app.processEvents()
        time.sleep(0.005)


def punto(hora, valor):
    m = ed._marco()
    return QtCore.QPoint(int(m.left() + (hora + 0.5) * m.width() / 24), int(m.bottom() - valor * m.height()))


d = tempfile.mkdtemp()
aj = QtCore.QSettings(str(Path(d) / "aj.ini"), QtCore.QSettings.Format.IniFormat)
v = VentanaPlanes(config.cargar_emplazamiento(), aj, carpeta=d)
v.setWindowFlags(v.windowFlags() | QtCore.Qt.WindowType.WindowStaysOnTopHint | QtCore.Qt.WindowType.WindowTransparentForInput
                 | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus)
v.resize(1400, 860)
v.show()
espera(2.0)
ids = [f["id"] for f in v.catalogo["focos"]]
v.lista.setCurrentRow(ids.index("F08"))
espera()
ed = v.editor

ok("sin el factor en la ventana", not hasattr(v, "esp_factor") and not any(l.text() == "Factor:" for l in v.findChildren(QtWidgets.QLabel)))
ok("sin el factor en el plan", "factor" not in v._pf(), str(sorted(v._pf())))
ok("sin ratón no hay indicador", ed._activa is None)

# Pasar por encima enseña la barra sin cambiarla
antes = list(ed.v)
app.sendEvent(ed, QtGui.QMouseEvent(QtCore.QEvent.Type.MouseMove, QtCore.QPointF(punto(9, 0.3)), QtCore.QPointF(ed.mapToGlobal(punto(9, 0.3))),
                                    QtCore.Qt.MouseButton.NoButton, QtCore.Qt.MouseButton.NoButton, QtCore.Qt.KeyboardModifier.NoModifier))
espera()
ok("al pasar: la hora bajo el ratón", ed._activa == 9, str(ed._activa))
ok("al pasar: no cambia nada", ed.v == antes and not v.b_guardar.isEnabled())
ed.grab().save(str(SALIDA / "encima.png"))

# Arrastre: el valor sigue al ratón, también por encima de 100 % y por debajo de 0
QtTest.QTest.mousePress(ed, Boton, pos=punto(12, 0.65))
espera()
ok("al pulsar: 65 %", ed.v[12] == 0.65 and ed._activa == 12, str(ed.v[12]))
ed.grab().save(str(SALIDA / "pulsado.png"))
registrado = []
ed.cambiado.connect(registrado.append)
for valor, esperado in ((0.42, 0.40), (0.5, 0.5), (1.4, 1.0), (-0.5, 0.0), (0.97, 0.95)):
    ev = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseMove, QtCore.QPointF(punto(12, valor)), QtCore.QPointF(ed.mapToGlobal(punto(12, valor))),
                           QtCore.Qt.MouseButton.NoButton, Boton, QtCore.Qt.KeyboardModifier.NoModifier)
    app.sendEvent(ed, ev)
    espera()
    ok(f"al arrastrar a {valor}: {esperado}", abs(ed.v[12] - esperado) < 1e-9 and ed._activa == 12, str(ed.v[12]))
ed.grab().save(str(SALIDA / "arriba.png"))
ok("hasta soltar no se aplica", not registrado and not v.b_guardar.isEnabled())
QtTest.QTest.mouseRelease(ed, Boton, pos=punto(12, 0.97))
espera()
ok("al soltar se aplica", len(registrado) == 1 and E.perfil_dia(v._pf(), 0)[12] == 0.95 and v.b_guardar.isEnabled())

# Sale del editor: fuera el indicador
app.sendEvent(ed, QtCore.QEvent(QtCore.QEvent.Type.Leave))
espera()
ok("al salir se quita", ed._activa is None)

# Las esquinas: que el rótulo no se salga del editor en ningún estilo
ed.poner([1.0] * 24)
for clave in tema.TEMAS:
    tema.poner(clave)
    espera(0.2)
    for hora in (0, 23):
        for x in (0.0, 1.0):
            ed.v[hora] = x
            ed._activa = hora
            ed.repaint()
            img = ed.grab().toImage()
            ok(f"{clave}: {hora} h a {x:.0%}, se pinta", not img.isNull())
    ed.v[23] = 0.65
    ed._activa = 23
    ed.grab().save(str(SALIDA / f"{clave}_23h.png"))
    ed.v[0] = 1.0
    ed._activa = 0
    ed.grab().save(str(SALIDA / f"{clave}_0h.png"))
tema.poner("oscuro")
ed._activa = None
v._sucio = False        # si no, al cerrar sale el diálogo de cambios sin guardar y nadie lo contesta
v.close()
print("FALLOS:", fallos or "ninguno", file=out, flush=True)
os._exit(1 if fallos else 0)
