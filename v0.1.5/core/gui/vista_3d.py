# -*- coding: utf-8 -*-
"""El visor 3D en la zona central, en lugar del mapa (decisión del usuario, 2026-11-01): el penacho de gui/penacho_3d.py, con WebGL y el
mismo reproductor que el mapa. Oculta, la página no pinta (Chromium lo sabe: QStackedWidget la esconde)."""
from PySide6 import QtCore, QtGui
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from teodors.gui import tema
from teodors.gui.mapa import PaginaMapa


class Vista3D(QWebEngineView):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pagina = PaginaMapa(self)
        self.setPage(self._pagina)
        self._pagina.setBackgroundColor(QtGui.QColor(tema.c("fondo")))
        self._pagina.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self._listo = False
        self._hora = (0, 0.0)
        self.loadFinished.connect(self._cargada)
        tema.avisos.cambiado.connect(self.set_tema)

    def _js(self, codigo):
        self._pagina.runJavaScript(codigo)

    def set_tema(self):
        """Otro estilo: cambian las variables de color y no se recarga nada."""
        self._pagina.setBackgroundColor(QtGui.QColor(tema.c("fondo")))
        self._js(tema.js_variables() + f";window.visor && visor.fondo('{tema.c('fondo')}')")

    def poner(self, ruta):
        """Abre la página de un penacho."""
        self._listo = False
        self.setUrl(QtCore.QUrl.fromLocalFile(str(ruta)))

    def _cargada(self, _ok):
        self._listo = True
        self.hora(*self._hora)

    def hora(self, h, f=0.0):
        """Hora del periodo y fracción hacia la siguiente, como el penacho del mapa."""
        self._hora = (h, f)
        if self._listo:
            self._js(f"window.visor && visor.hora({int(h)}, {float(f):.3f})")
