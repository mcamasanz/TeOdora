# Cerrar la app con focos o planes abiertos, con la X de verdad (WM_CLOSE de Windows, no QWidget.close).
#   prueba_cierre.py <caso>      sin caso, los lanza todos, cada uno en su proceso
# Pide ENCE_GALERA_DATOS con una copia de los datos: nunca se guarda de verdad en focos.json.
import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
AQUI = Path(os.environ["TEMP"]) / "ence_galera" / "99-Test" / "11_cierre"
AQUI.mkdir(parents=True, exist_ok=True)
# Nunca el INI del usuario: Qt usa esta carpeta, también en cada caso
AJUSTES = AQUI / "ajustes"
AJUSTES.mkdir(parents=True, exist_ok=True)
CASOS = ("sin_cambios", "operador_nunca_pregunta", "principal_limpia", "principal_sucia_descartar", "principal_sucia_cancelar",
         "principal_minimizada", "x_planes_y_x_principal", "descartar_recupera", "descartar_plan_nuevo", "focos_guardar",
         "focos_guardar_falla", "base_sin_nombre")

if len(sys.argv) < 2:
    if not os.environ.get("ENCE_GALERA_DATOS"):
        sys.exit("Falta ENCE_GALERA_DATOS con una copia de los datos.")
    malos = []
    for c in CASOS:
        print(f"=== {c}", flush=True)
        r = subprocess.run([sys.executable, __file__, c], text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=150,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        for l in r.stdout.splitlines():
            if l.startswith(("OK", "MAL", "SIGUE", "TERMINA", "ERROR")):
                print("  " + l[:170], flush=True)
        if r.returncode != 0:
            malos.append(c)
            print("  salida", r.returncode, r.stderr[-600:], flush=True)
    print("CODIGO:", RAIZ)
    print("CASOS CON FALLOS:", malos or "ninguno")
    sys.exit(1 if malos else 0)

caso = sys.argv[1]
sys.argv = sys.argv[:1]
sys.stdout.reconfigure(encoding="utf-8")
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
from PySide6 import QtCore, QtWidgets, QtWebEngineWidgets  # noqa: E402,F401

QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope, str(AJUSTES))
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(sys.argv)
from teodors import planta as config  # noqa: E402
from teodors.operacion import focos as F  # noqa: E402
from teodors.comun import registro  # noqa: E402
from teodors.gui import tema  # noqa: E402

_planta.asegurar_carpetas(); registro.configurar(_planta.DIR_LOGS, _planta.REGISTRO)
tema.aplicar(app)
B = QtWidgets.QMessageBox.StandardButton
fallos = []
# Sin ventana principal, cerrar la única ventana no debe acabar la prueba antes de tiempo
app.setQuitOnLastWindowClosed(caso.startswith(("principal", "x_planes", "focos_guardar")))


def ok(nombre, si, detalle=""):
    print(("OK  " if si else "MAL ") + nombre, detalle, flush=True)
    if not si:
        fallos.append(nombre)


def fin():
    print("FALLOS:", fallos or "ninguno", flush=True)
    os._exit(1 if fallos else 0)


def x(ventana):
    """La X de la ventana, por donde entra de verdad: un WM_CLOSE de Windows."""
    ctypes.windll.user32.PostMessageW(int(ventana.winId()), 0x0010, 0, 0)


def modal():
    return app.activeModalWidget()


def contesta(boton):
    m = modal()
    if m is None:
        return False
    if isinstance(m, QtWidgets.QMessageBox):
        m.button(boton).click()
    else:
        m.reject()
    return True


def visibles():
    return sorted(type(w).__name__ for w in app.topLevelWidgets() if w.isVisible() and w.isWindow())


def correr(guion, limite=70):
    """Lanza el guion (generador que da esperas en segundos) dentro de app.exec(), como la app de verdad: los
    diálogos abren sus propios bucles. Devuelve True si la aplicación ha terminado por sí sola."""
    g = guion()

    def paso():
        try:
            espera = next(g)
        except StopIteration:
            if not app.quitOnLastWindowClosed():      # casos sin ventana principal: acaban con el guion
                app.quit()
            return
        QtCore.QTimer.singleShot(int(espera * 1000), paso)
    QtCore.QTimer.singleShot(0, paso)

    def tope():
        print("SIGUE VIVA tras el tope:", visibles(), "| modal:", type(modal()).__name__, flush=True)
        ok("la app termina", False)
        fin()
    QtCore.QTimer.singleShot(limite * 1000, tope)
    app.exec()
    print("TERMINA: la app ha salido sola", flush=True)
    return True


def principal():
    from teodors.gui.ventana import VentanaPrincipal
    v = VentanaPrincipal()
    v.show()
    return v


def ensucia_plan(vp):
    vp._marcar()
    ok("el plan queda con cambios", vp._sucio)


def boton_es(m):
    return m.button(B.Save).text(), m.button(B.Discard).text(), m.button(B.Cancel).text()


if caso == "sin_cambios":
    # abrir, pasearse y cerrar no debe preguntar nada
    from teodors.gui.ventana_focos import VentanaFocos
    from teodors.gui.ventana_planes import VentanaPlanes
    aj = QtCore.QSettings(str(AQUI / "cierre_aj.ini"), QtCore.QSettings.Format.IniFormat)
    emp = config.cargar_emplazamiento()

    def guion():
        for circe in (False, True):
            config.actual().MODO_EDICION = circe
            v = VentanaFocos(emp, aj)
            v.show()
            yield 1.5
            for i in range(v.lista.count()):
                v.lista.setCurrentRow(i)
                yield 0.05
            ok(f"focos ({'CIRCE' if circe else 'operario'}): pasearse no marca cambios", not v._sucio)
            x(v)
            yield 0.6
            ok(f"focos ({'CIRCE' if circe else 'operario'}): se cierra sin preguntar", modal() is None and not v.isVisible())
            contesta(B.Discard)
            yield 0.3
        config.actual().MODO_EDICION = False
        vp = VentanaPlanes(emp, aj)
        vp.show()
        yield 1.5
        for i in range(vp.lista.count()):
            vp.lista.setCurrentRow(i)
            yield 0.05
        ok("planes: pasearse no marca cambios", not vp._sucio)
        x(vp)
        yield 0.6
        ok("planes: se cierra sin preguntar", modal() is None and not vp.isVisible())
        contesta(B.Discard)
        yield 0.3
    correr(guion)
    fin()

if caso == "operador_nunca_pregunta":
    # el operario no puede cambiar focos: aunque algo lo marcara, no hay nada que guardar
    from teodors.gui.ventana_focos import VentanaFocos
    aj = QtCore.QSettings(str(AQUI / "cierre_aj.ini"), QtCore.QSettings.Format.IniFormat)
    config.actual().MODO_EDICION = False
    v = VentanaFocos(config.cargar_emplazamiento(), aj)

    def guion():
        v.show()
        yield 1.5
        v._sucio = True
        x(v)
        yield 0.6
        ok("sin diálogo", modal() is None)
        contesta(B.Discard)
        yield 0.3
        ok("se cierra", not v.isVisible())
    correr(guion)
    fin()

if caso == "principal_limpia":
    v = principal()

    def guion():
        yield 5
        v._ver_focos()
        v._ver_planes()
        v._ver_ajustes()
        v.dock_consola.setFloating(True)
        v.dock_consola.show()
        yield 2
        print("ANTES:", visibles(), flush=True)
        x(v)
        yield 6
        ok("cerrar la principal cierra la app", False, f"siguen abiertas {visibles()}")
    if correr(guion):
        ok("cerrar la principal cierra la app", True)
    fin()

if caso == "principal_sucia_descartar":
    v = principal()

    def guion():
        yield 5
        v._ver_planes()
        yield 2
        ensucia_plan(v._ventana_planes)
        x(v)
        yield 1.5
        m = modal()
        ok("pregunta por el plan", isinstance(m, QtWidgets.QMessageBox) and "Plan" in m.windowTitle(), type(m).__name__)
        if isinstance(m, QtWidgets.QMessageBox):
            ok("botones en español", boton_es(m) == ("Guardar", "No guardar", "Cancelar"), str(boton_es(m)))
            ok("el diálogo se ve", m.isVisible())
        contesta(B.Discard)
        yield 6
        ok("tras contestar, la app se cierra", False, f"siguen abiertas {visibles()}")
    if correr(guion):
        ok("tras contestar, la app se cierra", True)
    fin()

if caso == "principal_sucia_cancelar":
    v = principal()

    def guion():
        yield 5
        v._ver_planes()
        vp = v._ventana_planes
        yield 2
        ensucia_plan(vp)
        x(v)
        yield 1.5
        contesta(B.Cancel)
        yield 1.5
        ok("cancelar deja la principal abierta", v.isVisible())
        ok("cancelar deja los planes abiertos y sin perder cambios", vp.isVisible() and vp._sucio)
        ok("sin diálogos colgando", modal() is None)
        vp._sucio = False
        x(v)
        yield 6
        ok("sin cambios ya se cierra todo", False, f"siguen abiertas {visibles()}")
    if correr(guion):
        ok("sin cambios ya se cierra todo", True)
    fin()

if caso == "principal_minimizada":
    # el diálogo no puede quedarse escondido en una ventana minimizada
    v = principal()

    def guion():
        yield 5
        v._ver_planes()
        vp = v._ventana_planes
        yield 2
        ensucia_plan(vp)
        vp.showMinimized()
        yield 1
        x(v)
        yield 1.5
        ok("la ventana que pregunta vuelve a la vista", vp.isVisible() and not vp.isMinimized())
        ok("el diálogo se ve", modal() is not None and modal().isVisible())
        contesta(B.Discard)
        yield 6
        ok("tras contestar, la app se cierra", False, f"siguen abiertas {visibles()}")
    if correr(guion):
        ok("tras contestar, la app se cierra", True)
    fin()

if caso == "x_planes_y_x_principal":
    # con el diálogo de planes abierto, la X de la principal no debe quedarse muerta ni abrir otro diálogo
    v = principal()
    llegado = []

    def guion():
        yield 5
        v._ver_planes()
        vp = v._ventana_planes
        yield 2
        ensucia_plan(vp)
        x(vp)
        yield 1.5
        m = modal()
        ok("pregunta", m is not None)
        ok("el diálogo solo bloquea su ventana", m is not None and m.windowModality() == QtCore.Qt.WindowModality.WindowModal,
           str(m.windowModality()) if m else "")
        ok("el diálogo queda siempre encima (Windows)", m is not None and bool(ctypes.windll.user32.GetWindowLongW(int(m.winId()), -20) & 0x8))
        x(v)
        yield 1.5
        ok("la X de la principal no cierra nada sin contestar", v.isVisible() and vp.isVisible() and vp._sucio)
        ok("la X de la principal no abre otro diálogo", modal() is m and len([w for w in app.topLevelWidgets() if isinstance(w, QtWidgets.QMessageBox) and w.isVisible()]) == 1)
        ok("la principal sigue abierta mientras se contesta", v.isVisible())
        contesta(B.Discard)
        yield 1.5
        ok("planes cerrada, principal abierta", not vp.isVisible() and v.isVisible(), str(visibles()))
        ok("sin diálogos colgando", modal() is None)
        llegado.append(1)
        x(v)
        yield 6
        ok("la principal ya se cierra", False, f"siguen abiertas {visibles()}")
    if correr(guion):
        ok("la app solo termina al final, con todo contestado", bool(llegado))
    fin()

if caso in ("descartar_recupera", "descartar_plan_nuevo"):
    from teodors.operacion import planes as E
    from teodors.gui.ventana_planes import VentanaPlanes
    import tempfile
    aj = QtCore.QSettings(str(AQUI / "cierre_aj.ini"), QtCore.QSettings.Format.IniFormat)
    d = tempfile.mkdtemp()
    vp = VentanaPlanes(config.cargar_emplazamiento(), aj, carpeta=d)

    def guion():
        vp.show()
        yield 1.5
        if caso == "descartar_recupera":
            vp.esc = E.nuevo(vp.catalogo, "Guardado")
            ok("guardar", vp.guardar())
            antes = E.cargar(E.ruta("Guardado", d)) if hasattr(E, "ruta") else None
            perfil = vp._pf()["perfiles"][0]
            original = perfil[3]
            perfil[3] = 0.123 if original != 0.123 else 0.456
            vp._marcar()
            x(vp)
            yield 1
            contesta(B.Discard)
            yield 1
            ok("se cierra", not vp.isVisible())
            ok("no queda marcado", not vp._sucio)
            ok("título sin asterisco", not vp.windowTitle().endswith("*"), vp.windowTitle())
            vp.show()
            yield 0.5
            ok("al reabrir, lo guardado", vp.esc.get("nombre") == "Guardado" and vp._pf()["perfiles"][0][3] == original,
               f"{vp.esc.get('nombre')} {vp._pf()['perfiles'][0][3]} frente a {original}")
            vp._sucio = False
            x(vp)
            yield 0.5
            ok("cerrar otra vez no pregunta", modal() is None)
        else:
            vp._abrir(E.nuevo(vp.catalogo, "Nuevo sin guardar"))
            vp._marcar()
            x(vp)
            yield 1
            contesta(B.Discard)
            yield 1
            ok("no queda marcado", not vp._sucio)
            ok("vuelve a la Base", vp.esc.get("nombre") == E.BASE, str(vp.esc.get("nombre")))
    correr(guion)
    fin()

if caso in ("focos_guardar", "focos_guardar_falla"):
    config.actual().MODO_EDICION = True
    llamadas = []

    def guardar_falso(datos):
        llamadas.append(len(datos["focos"]))
        if caso == "focos_guardar_falla":
            raise OSError("disco bloqueado")
        return config.FOCOS_JSON
    F.guardar = guardar_falso
    v = principal()

    def guion():
        yield 5
        v._ver_focos()
        vf = v._ventana_focos
        yield 2
        vf._marcar_sucio()
        x(v)
        yield 1.5
        m = modal()
        ok("pregunta por los focos", isinstance(m, QtWidgets.QMessageBox) and "Focos" in m.windowTitle())
        contesta(B.Save)
        yield 1.5
        ok("ha intentado guardar una vez", len(llamadas) == 1, str(llamadas))
        if caso == "focos_guardar_falla":
            m = modal()
            ok("avisa del fallo", isinstance(m, QtWidgets.QMessageBox) and "disco bloqueado" in m.text(), m.text() if m else "sin aviso")
            if m is not None:
                m.button(B.Ok).click() if m.button(B.Ok) else m.reject()
            yield 1
            ok("no pierde los cambios: sigue abierta y marcada", vf.isVisible() and vf._sucio)
            ok("la principal sigue abierta", v.isVisible())
            vf._sucio = False
            x(v)
        yield 6
        ok("la app se cierra", False, f"siguen abiertas {visibles()}")
    if correr(guion):
        ok("la app se cierra", True)
        ok("ha intentado guardar una sola vez", len(llamadas) == 1, str(llamadas))
    fin()

if caso == "base_sin_nombre":
    # guardar la Base pide un nombre; cancelar el nombre no debe cerrar ni perder nada
    from teodors.gui.ventana_planes import VentanaPlanes
    import tempfile
    aj = QtCore.QSettings(str(AQUI / "cierre_aj.ini"), QtCore.QSettings.Format.IniFormat)
    vp = VentanaPlanes(config.cargar_emplazamiento(), aj, carpeta=tempfile.mkdtemp())

    def guion():
        vp.show()
        yield 1.5
        ensucia_plan(vp)
        x(vp)
        yield 1
        contesta(B.Save)
        yield 1
        ok("pide un nombre", isinstance(modal(), QtWidgets.QInputDialog), type(modal()).__name__)
        contesta(B.Cancel)
        yield 1
        ok("sigue abierta y con cambios", vp.isVisible() and vp._sucio)
        ok("sin diálogos colgando", modal() is None)
        vp._sucio = False
        x(vp)
        yield 0.6
    correr(guion)
    fin()

sys.exit(f"caso desconocido: {caso}")
