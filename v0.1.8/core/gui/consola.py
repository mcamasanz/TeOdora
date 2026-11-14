# -*- coding: utf-8 -*-
"""Registro de actividad: enseña los avisos y errores del logger «teodors»; el detalle se queda en el
fichero de registro. De «Comprobar la herramienta» (`teodors.comprobar`), todo: también lo que sale bien, en el color del acento
(usuario, 2026-11-07: «que vaya soltando mensajes positivos o negativos en el log de actividad»). Todo llega por señales Qt, así que los workers en QThread pueden escribir sin
bloquear la interfaz. Va oculto al arrancar: los errores se avisan también en el mapa (señal `error`)."""
import html
import logging
from collections import deque

from PySide6 import QtCore, QtGui, QtWidgets

from teodors import planta as config
from teodors.comun import registro
from teodors.gui import tema

# nombres de color: se leen al escribir, y lo ya escrito se repinta al cambiar de estilo
_COLORES = {logging.DEBUG: "apagado", logging.WARNING: "aviso", logging.ERROR: "fallo",
            logging.CRITICAL: "fallo"}
_MAX_LINEAS = 5000
ENTERO = ("teodors.comprobar",)       # loggers de los que se enseña también lo informativo


class _Emisor(QtCore.QObject):
    registro = QtCore.Signal(int, str)
    error = QtCore.Signal(str)


class ManejadorQt(logging.Handler):
    """logging.Handler que reenvía cada mensaje a la consola por señal."""

    def __init__(self, emisor):
        super().__init__(logging.INFO)
        self.addFilter(lambda r: r.levelno >= logging.WARNING or r.name in ENTERO)
        self._emisor = emisor
        self.setFormatter(registro.FormatoES("%(asctime)s  %(nivel)-7s %(message)s",
                                             "%H:%M:%S"))

    def emit(self, record):
        try:
            self._emisor.registro.emit(record.levelno, self.format(record))
            if record.levelno >= logging.ERROR:
                self._emisor.error.emit(record.getMessage())
        except Exception:
            self.handleError(record)


class Consola(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._emisor = _Emisor()

        self.error = self._emisor.error
        self.texto = QtWidgets.QPlainTextEdit(readOnly=True, objectName="actividad")
        self.texto.setMaximumBlockCount(_MAX_LINEAS)
        self._lineas = deque(maxlen=_MAX_LINEAS)     # (color, texto ya escapado)
        fuente = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        fuente.setPointSize(9)
        self.texto.setFont(fuente)

        b_limpiar = QtWidgets.QToolButton(text="Limpiar")
        b_limpiar.clicked.connect(self._limpiar)
        b_logs = QtWidgets.QToolButton(text="Abrir registros")
        b_logs.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(str(config.DIR_LOGS))))
        barra = QtWidgets.QHBoxLayout()
        barra.setContentsMargins(8, 4, 8, 4)
        barra.setSpacing(8)
        barra.addStretch()
        barra.addWidget(b_logs)
        barra.addWidget(b_limpiar)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addLayout(barra)
        lay.addWidget(self.texto)

        self._emisor.registro.connect(self._añadir_registro)
        self.manejador = ManejadorQt(self._emisor)
        tema.avisos.cambiado.connect(self._repintar)

    def sizeHint(self):
        return QtCore.QSize(800, 170)

    def conectar(self):
        registro.get().addHandler(self.manejador)

    def desconectar(self):
        registro.get().removeHandler(self.manejador)

    def _limpiar(self):
        self.texto.clear()
        self._lineas.clear()

    def _escribe(self, color, texto):
        estilo = "white-space:pre-wrap;" + (f"color:{tema.c(color)};" if color else "")
        self.texto.appendHtml(f'<span style="{estilo}">{texto}</span>')

    def _repintar(self):
        """Un color de un estilo puede no leerse sobre el fondo de otro."""
        self.texto.clear()
        for color, texto in self._lineas:
            self._escribe(color, texto)
        self._al_final()

    def _al_final(self):
        barra = self.texto.verticalScrollBar()
        barra.setValue(barra.maximum())

    def _añadir_registro(self, nivel, mensaje):
        # pre-wrap: el HTML colapsa los espacios y desalinearía la columna del nivel
        color = "acento_claro" if nivel == logging.INFO and " ✓ " in mensaje[:24] else _COLORES.get(nivel)   # lo que sale bien
        linea = (color, html.escape(mensaje).replace("\n", "<br>"))
        self._lineas.append(linea)
        self._escribe(*linea)
        self._al_final()
