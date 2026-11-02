# -*- coding: utf-8 -*-
"""Tanda 8, humo: el main.py de la planta, entero y sin ventanas de verdad, llega a crear la ventana principal y se cierra sin errores en el registro.

    python humo_tanda8.py [--circe --focos --planes --dia AAAA-MM-DD]      con ENCE_GALERA_DATOS

Plataforma offscreen: nada sale en la pantalla. El contenido web sale en blanco, así que esto NO comprueba el mapa: para eso están las pruebas de clics.
Ajustes, registro y páginas, en una carpeta temporal: nunca el INI del usuario. Con T8_PAQUETES, otro cargador de teOdors (la copia de desarrollo).
"""
import json
import os
import re
import runpy
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
trabajo = Path(tempfile.mkdtemp(prefix="humo_t8_"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QPA_FONTDIR"] = r"C:\Windows\Fonts"
os.environ["ENCE_GALERA_LOCAL"] = str(trabajo / "local")
sys.stdout.reconfigure(encoding="utf-8")
if not os.environ.get("ENCE_GALERA_DATOS"):
    sys.exit("Falta ENCE_GALERA_DATOS con una copia de los datos.")
if os.environ.get("T8_PAQUETES"):
    sys.path.insert(0, os.environ["T8_PAQUETES"])
    import teodors  # noqa: F401

# Las librerías del mapa, de la caché de la app si está: así no salen a la red
cache = Path(os.environ.get("TEMP", "")) / "ence_galera" / "web_assets"
if cache.is_dir():
    shutil.copytree(cache, trabajo / "local" / "web_assets")

from PySide6 import QtCore, QtWidgets  # noqa: E402

QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope, str(trabajo / "ajustes"))

exec_real = QtWidgets.QApplication.exec
salida = {}


def exec_con_tope(*_a):
    """El bucle de la app de verdad, unos segundos; después se cierra como lo haría la X."""
    app = QtWidgets.QApplication.instance()

    def cerrar():
        ventanas = {type(w).__name__: w for w in app.topLevelWidgets() if w.isWindow() and w.isVisible()}
        salida["ventanas"] = sorted(ventanas)
        salida["titulos"] = sorted(w.windowTitle() for w in ventanas.values() if w.windowTitle())
        v = ventanas.get("VentanaPrincipal")
        salida["listo"] = v is not None and v.mapa._listo
        salida["dia"] = v is not None and v._dia_inicial
        if v is not None:
            v.close()
        QtCore.QTimer.singleShot(1500, app.quit)
    QtCore.QTimer.singleShot(int(float(os.environ.get("T8_SEGUNDOS", "12")) * 1000), cerrar)
    return exec_real()


QtWidgets.QApplication.exec = exec_con_tope
sys.argv = [str(RAIZ / "main.py")] + sys.argv[1:]
codigo = 0
try:
    runpy.run_path(str(RAIZ / "main.py"), run_name="__main__")
except SystemExit as e:
    codigo = e.code

ini = trabajo / "ajustes" / "CIRCE" / "ENCE_Galera.ini"
registros = sorted((trabajo / "local" / "logs").glob("*.log"))
texto = "".join(f.read_text(encoding="utf-8") for f in registros)
malos = [l for l in texto.splitlines() if re.search(r" (ERROR|CRÍTICO) ", l)]
avisos = [l for l in texto.splitlines() if " AVISO " in l]
print(json.dumps(salida, ensure_ascii=False))
print("código de salida:", codigo)
print("registro:", [f.name for f in registros], f"{len(texto.splitlines())} líneas")
print("ajustes en la carpeta temporal, con su nombre de siempre:", ini.is_file())
print("avisos:", len(avisos))
for l in avisos[:15]:
    print("  ", l[:200])
print("errores:", len(malos))
for l in malos[:15]:
    print("  ", l[:400])
bien = codigo in (0, None) and "VentanaPrincipal" in salida.get("ventanas", []) and not malos and ini.is_file()
print("RESULTADO:", "bien" if bien else "MAL")
sys.exit(0 if bien else 1)
