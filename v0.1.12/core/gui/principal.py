# -*- coding: utf-8 -*-
"""Arranque de la aplicación de una planta: lo que hace el main.py de cada planta después de activarla.

    --dia AAAA-MM-DD   abre en Meteorología → Reanálisis con el viento de ese día ya cargado en el mapa
    --focos, --planes  abre también la ventana de los focos o la de los planes

La app arranca siempre con el usuario normal: el administrador (los permisos del antiguo modo de edición) se abre desde la terminal de la
app, con su contraseña (`operacion.administrador`; usuario, 2026-11-08). Ya no hay opción de la línea de órdenes para eso.

Importar esto no carga Qt: PySide6 se importa en `main`.
"""
import sys
import traceback

from teodors import planta as config
from teodors.comun import registro

# Lo que la interfaz lee de planta.json, además de lo que pide `planta` al activarla. Se mira al arrancar: si no, el error saldría al abrir un diálogo o en un fallo de descarga
CAMPOS = (("identidad", "ajustes"), ("identidad", "app_id"), ("identidad", "version"), ("identidad", "entidad"), ("identidad", "red_datos"),
          ("proyeccion", "zona_horaria"), ("fuentes", "mdt"), ("fuentes", "usos"), ("fuentes", "edificios"), ("fuentes", "nombres_nucleos"), ("fuentes", "fondos"), ("fuentes", "creditos"),
          ("estaciones", "proveedor"), ("operacion", "texto_modo_edicion"))


def comprobar_planta():
    """Si a la planta le falta algo que la interfaz va a leer, el error dice qué."""
    for bloque, clave in CAMPOS:
        config.pide(bloque, clave)


def opciones(argv):
    """Quita de la lista `argv` las opciones de la aplicación y las devuelve; lo demás se queda, para Qt."""
    def marca(nombre):
        hay = nombre in argv
        if hay:
            argv.remove(nombre)
        return hay

    dia = None
    if "--dia" in argv:
        i = argv.index("--dia")
        dia = argv[i + 1] if i + 1 < len(argv) else None
        del argv[i:i + 2]
    return {"dia": dia, "focos": marca("--focos"), "planes": marca("--planes")}


def main():
    for flujo in (sys.stdout, sys.stderr):             # la consola cp1252 rompe con «γ», «·»
        if flujo is not None and hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")

    comprobar_planta()
    op = opciones(sys.argv)

    from PySide6 import QtCore, QtWidgets
    from PySide6 import QtWebEngineWidgets  # noqa: F401  (debe cargarse antes de QApplication)

    config.asegurar_carpetas()
    log = registro.configurar(config.DIR_LOGS, config.REGISTRO)

    def _excepcion(tipo, valor, tb):
        log.error("Error no controlado:\n" + "".join(traceback.format_exception(tipo, valor, tb)))
    sys.excepthook = _excepcion

    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    if sys.platform == "win32":                         # su propio icono en la barra de tareas, no el de Python
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(config.pide("identidad", "app_id"))
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(config.APP_NOMBRE)
    app.setOrganizationName(config.ORGANIZACION)
    from teodors.gui import tema
    tema.aplicar(app)

    from teodors.gui.ventana import VentanaPrincipal
    ventana = VentanaPrincipal(dia_inicial=op["dia"], abrir_focos=op["focos"], abrir_planes=op["planes"])
    if ventana.primera_vez:
        ventana.showMaximized()
    else:
        ventana.show()
    return app.exec()
