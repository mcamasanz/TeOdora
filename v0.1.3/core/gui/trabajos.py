# -*- coding: utf-8 -*-
"""Trabajos largos en segundo plano (QThread): la interfaz nunca se bloquea (guía 08)."""
import inspect
import traceback

from PySide6 import QtCore

from teodors.comun import registro
from teodors.comun.errores import Cancelado

log = registro.get("trabajos")


class Trabajo(QtCore.QThread):
    """Ejecuta `funcion(*args, progreso=…)` en un hilo. Si la función admite `cancelado`,
    se le pasa también y `cancelar()` la detiene."""
    progreso = QtCore.Signal(int, str)
    hecho = QtCore.Signal(dict)
    fallo = QtCore.Signal(str)

    def __init__(self, funcion, *args, parent=None):
        super().__init__(parent)
        self._funcion, self._args = funcion, args
        self._cancelar = False

    def cancelar(self):
        self._cancelar = True

    def run(self):
        kw = {"progreso": self.progreso.emit}
        if "cancelado" in inspect.signature(self._funcion).parameters:
            kw["cancelado"] = lambda: self._cancelar
        try:
            self.hecho.emit(self._funcion(*self._args, **kw))
        except Cancelado:
            self.fallo.emit("Descarga cancelada.")
        except Exception as e:                       # noqa: BLE001 (se informa al usuario)
            log.debug("Detalle del fallo:\n" + traceback.format_exc())
            self.fallo.emit(f"{type(e).__name__}: {e}")


def TrabajoTerreno(lat, lon, lado_km, parent=None):
    """Descarga el terreno y los usos del suelo del dominio (terreno.descargar)."""
    from teodors.fuentes import terreno
    return Trabajo(terreno.descargar, lat, lon, lado_km, parent=parent)
