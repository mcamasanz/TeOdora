# Capas temáticas solo desde los botones del panel, y la terminal.
import json, os, shutil, sys, time
from pathlib import Path
AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "terminal"
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
COPIA = AQUI / "ENCE_Galera.ini.terminal"
tenia = INI.exists()
if tenia:
    shutil.copy2(INI, COPIA)                     # con los ajustes del usuario: su disposición guardada no tenía terminal
from PySide6 import QtCore, QtTest, QtWidgets, QtWebEngineWidgets  # noqa
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(sys.argv[:1])
from teodors import planta as config
from teodors.comun import registro
from teodors.gui import tema
aj = tema.ajustes()                              # disposición de partida: la guardada puede traer la terminal abierta
aj.remove("ventana")
aj.sync()
tema.aplicar(app)
from teodors.gui.ventana import VentanaPrincipal
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


def visibles():
    return sorted(json.loads(js("JSON.stringify(mapaApp.capasVisibles())")))


t = time.time()
while time.time() - t < 40 and not v.mapa.esta_listo():
    espera(0.3)
espera(5)
p = v.panel
selector = js("document.querySelector('.leaflet-control-layers-overlays').innerText") or ""
print("Selector:", selector.replace("\n", " | "), file=out, flush=True)
for nombre in ("Elevación", "Uso del suelo", "Edificios"):
    ok(f"{nombre}: fuera del selector", nombre not in selector)
ok("Al abrir: receptores en el selector y aún sin viento", "Receptores" in selector and "Viento" not in selector)
ok("Ninguna capa temática encendida al abrir", not ({"elevacion", "usos", "edificios"} & set(visibles())))

# los botones, con clics de verdad
p.ir_a("planta")
espera(0.3)
p.b_ver_elevacion.click()
espera(0.6)
ok("Botón elevación", "elevacion" in visibles() and p.b_ver_elevacion.text() == "Ocultar elevación", visibles())
ley = js("document.querySelector('.mapa-leyenda').innerText") or ""
ok("Con su leyenda", "Elevación" in ley, ley[:50].replace("\n", " "))
v.grab().save(str(SALIDA / "elevacion.png"))
p.b_ver_usos.click()
espera(0.6)
ok("Botón usos: apaga elevación, y su botón", "usos" in visibles() and "elevacion" not in visibles()
   and not p.b_ver_elevacion.isChecked() and p.b_ver_elevacion.text() == "Ver elevación", visibles())
p.b_ver_edificios.click()
espera(1)
ok("Botón edificios: apaga usos, y su botón", "edificios" in visibles() and "usos" not in visibles() and not p.b_ver_usos.isChecked(), visibles())
p.b_ver_edificios.click()
espera(0.5)
ok("Se apagan todas", not ({"elevacion", "usos", "edificios"} & set(visibles())) and not p.b_ver_edificios.isChecked())
ley = js("document.querySelector('.mapa-leyenda').innerText") or ""
ok("Sin leyenda al apagar", not ley.strip(), ley[:40])
p.b_ver_elevacion.click()
espera(0.4)
v.mapa.set_capa_imagen(v.terreno_info["capas_mapa"][0], v.terreno_info["dir"], visible=False, grupo="tematica")
espera(0.5)
ok("Al volver a crearla no se duplica ni entra en el selector", "Elevación" not in (js("document.querySelector('.leaflet-control-layers-overlays').innerText") or ""))
if p.b_ver_elevacion.isChecked():
    p.b_ver_elevacion.click()

# Actividad: solo avisos y errores
txt = v.consola.texto.toPlainText()
ok("Actividad sin mensajes informativos", "INFO" not in txt, repr(txt[:80]))

# la terminal
term = v.terminal
ok("Terminal oculta al abrir", not v.dock_terminal.isVisible() and not v.dock_consola.isVisible())
ok("En el menú Ver", any(a.text() == "Terminal" for m in v.menu_app.actions() if m.menu() for a in m.menu().actions()))
botones = {b.text(): b for b in p.findChildren(QtWidgets.QToolButton) if b.objectName() == "riel_b"}
botones["Terminal"].click()
espera(0.6)
ok("El botón del panel la abre", v.dock_terminal.isVisible())


def escribe(texto):
    QtTest.QTest.keyClicks(term.entrada, texto)
    QtTest.QTest.keyClick(term.entrada, QtCore.Qt.Key.Key_Return)
    app.processEvents()


escribe("hola mundo")
ok("Comando desconocido", "hola: comando desconocido" in term.salida.toPlainText() and term.entrada.text() == "", term.salida.toPlainText().replace("\n", " | "))
term.registrar("doble", lambda n: str(2 * int(n)))
escribe("DOBLE 21")
ok("Comando registrado, con argumentos y sin distinguir mayúsculas", term.salida.toPlainText().endswith("42"))
escribe("doble x")
ok("Un comando con fallo no tira la app", "doble: invalid literal" in term.salida.toPlainText())
QtTest.QTest.keyClick(term.entrada, QtCore.Qt.Key.Key_Up)
ok("Flecha arriba: el anterior", term.entrada.text() == "doble x", term.entrada.text())
QtTest.QTest.keyClick(term.entrada, QtCore.Qt.Key.Key_Up)
ok("Otra vez: el de antes", term.entrada.text() == "DOBLE 21", term.entrada.text())
QtTest.QTest.keyClick(term.entrada, QtCore.Qt.Key.Key_Down)
QtTest.QTest.keyClick(term.entrada, QtCore.Qt.Key.Key_Down)
ok("Abajo hasta el final: vacío", term.entrada.text() == "")
escribe("import os; os.system('echo pirata')")
ok("No ejecuta Python", "import: comando desconocido" in term.salida.toPlainText())
espera(0.3)
v.grab().save(str(SALIDA / "terminal.png"))
registro_hoy = sorted(config.DIR_LOGS.glob("*.log"), key=lambda q: q.stat().st_mtime)[-1].read_text(encoding="utf-8", errors="replace")
ok("Lo escrito no va al registro", "hola mundo" not in registro_hoy)
escribe("limpiar")
ok("limpiar", term.salida.toPlainText() == "")

# con Actividad: pestañas
botones["Actividad"].click()
espera(0.5)
ok("Actividad delante, en pestañas", v.dock_consola.isVisible() and v.dock_terminal in v.tabifiedDockWidgets(v.dock_consola),
   [d.windowTitle() for d in v.tabifiedDockWidgets(v.dock_consola)])
v.grab().save(str(SALIDA / "pestanas.png"))
botones["Terminal"].click()
espera(0.5)
ok("Terminal delante otra vez", v.dock_terminal.isVisible() and not v.dock_terminal.visibleRegion().isEmpty()
   and v.dock_consola.visibleRegion().isEmpty())
v.grab().save(str(SALIDA / "pestanas_terminal.png"))
botones["Terminal"].click()
espera(0.5)
ok("Otro clic la cierra y queda Actividad", not v.dock_terminal.isVisible() and v.dock_consola.isVisible()
   and not v.dock_consola.visibleRegion().isEmpty())
botones["Terminal"].click()
espera(0.5)
ok("Y la vuelve a abrir, delante", not v.dock_terminal.visibleRegion().isEmpty())
tema.poner("claro")
espera(0.5)
escribe("otra")
v.grab().save(str(SALIDA / "terminal_claro.png"))
tema.poner("oscuro")
v.acc_solo_mapa.trigger()
espera(0.5)
ok("Solo mapa la oculta", not v.dock_terminal.isVisible())
v.acc_solo_mapa.trigger()
espera(0.5)
ok("Al volver sigue", v.dock_terminal.isVisible() or v.dock_consola.isVisible())
fin()
