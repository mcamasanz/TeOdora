# El main.py de verdad, con todas sus opciones: arranca, abre las ventanas, cierra guardando y sin errores.
import os, runpy, shutil, sys, time
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
AQUI = Path(__file__).resolve().parent
os.environ.setdefault("ENCE_GALERA_DATOS", str(Path(os.environ["TEMP"]) / "ence_galera" / "datos_local"))
INI = Path(os.environ["APPDATA"]) / "CIRCE" / "ENCE_Galera.ini"
COPIA = AQUI / "ENCE_Galera.ini.copia"
if INI.exists():
    shutil.copy2(INI, COPIA)                     # los ajustes del usuario quedan como estaban
    print("Ajustes guardados aparte", flush=True)
sys.stdout.reconfigure(encoding="utf-8")
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
from PySide6 import QtCore, QtWidgets, QtWebEngineWidgets  # noqa

casos = sys.argv[1:] or ["--dia 2026-10-21 --circe --focos --planes"]
sys.argv = ["main.py"] + casos[0].split()
original = QtWidgets.QApplication.exec
inicio = time.time()
resultado = {}


def revisar():
    app = QtWidgets.QApplication.instance()
    principal = [w for w in app.topLevelWidgets() if type(w).__name__ == "VentanaPrincipal"][0]
    print("Ventanas:", [(type(w).__name__, w.windowTitle()) for w in app.topLevelWidgets()
                        if w.isVisible() and w.isWindow()], flush=True)
    print("Primera vez:", principal.primera_vez, "| maximizada:", principal.isMaximized(), "| icono:",
          not app.windowIcon().isNull(), flush=True)
    print("Página:", principal._titulo_panel.lbl.text(), "| día:", principal.panel.lbl_dia_repro.text(),
          "| horizonte:", principal.panel.horizonte_meteo(), flush=True)
    from teodors import planta as config
    resultado["logs"] = config.DIR_LOGS
    for w in app.topLevelWidgets():
        if w is not principal and w.isVisible() and w.isWindow():
            w.close()
    principal.close()


def exec_falso(*_):
    QtCore.QTimer.singleShot(14000, revisar)
    return original()


QtWidgets.QApplication.exec = staticmethod(exec_falso)
try:
    runpy.run_path(str(RAIZ / "main.py"), run_name="__main__")
except SystemExit as e:
    print("Salida:", e.code, flush=True)

ini_nuevo = INI.read_text(encoding="utf-8", errors="replace") if INI.exists() else ""
print("Ajustes guardados al cerrar:", [k for k in ("geometria_v2", "estado_v3", "divisor_v2") if k in ini_nuevo], flush=True)
if COPIA.exists():
    shutil.copy2(COPIA, INI)
    print("Ajustes del usuario restaurados", flush=True)
else:
    INI.unlink(missing_ok=True)
logs = sorted(Path(resultado["logs"]).glob("*.log"), key=lambda p: p.stat().st_mtime)
if logs:
    lineas = logs[-1].read_text(encoding="utf-8", errors="replace").splitlines()
    malas = [l for l in lineas[-400:] if any(k in l for k in ("ERROR", "Traceback", "[mapa JS]", "WARNING"))]
    print(f"Registro {logs[-1].name}: {len(malas)} líneas de aviso o error entre las últimas 400", flush=True)
    for l in malas[-15:]:
        print("   ", l[:200], flush=True)
os._exit(0)
