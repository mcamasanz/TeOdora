# -*- coding: utf-8 -*-
"""Widgets pequeños reutilizables de la interfaz (aspecto en gui/tema.py)."""
from PySide6 import QtCore, QtWidgets

from teodors.gui import tema


def preguntar_si_guardar(ventana, titulo, texto):
    """¿Guardar, no guardar o cancelar? Sale delante de `ventana`, aunque estuviera minimizada o tapada, y se queda encima.
    Bloquea solo esa ventana: con un diálogo de toda la app, la X de las demás no responde y parece que no se puede cerrar.
    Devuelve el botón pulsado."""
    if ventana.isMinimized():
        ventana.showNormal()
    ventana.raise_()
    ventana.activateWindow()
    B = QtWidgets.QMessageBox.StandardButton
    caja = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Question, titulo, texto, B.Save | B.Discard | B.Cancel, ventana)
    caja.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
    caja.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint)     # pinchar en la principal no debe taparlo
    caja.setDefaultButton(B.Save)
    caja.button(B.Save).setText("Guardar")
    caja.button(B.Discard).setText("No guardar")
    caja.button(B.Cancel).setText("Cancelar")
    ventana._pregunta = caja
    try:
        caja.exec()
        boton = caja.clickedButton()
        return caja.standardButton(boton) if boton is not None else B.Cancel
    finally:
        ventana._pregunta = None
        caja.deleteLater()


def pregunta_abierta(ventana):
    """Si `ventana` ya está preguntando, lleva el diálogo delante y devuelve True. Hay que mirarlo ANTES de llamar a su close():
    con la pregunta abierta, close() devuelve True sin hacer nada y se daría por cerrada una ventana con cambios sin contestar."""
    caja = getattr(ventana, "_pregunta", None)
    if caja is None:
        return False
    if ventana.isMinimized():
        ventana.showNormal()
    ventana.raise_()
    caja.raise_()
    caja.activateWindow()
    return True


class Tarjeta(QtWidgets.QFrame):
    """Bloque de contenido del panel, con título opcional. Se rellena con `tarjeta.cuerpo` (QVBoxLayout)."""

    def __init__(self, titulo=None, parent=None):
        super().__init__(parent, objectName="tarjeta")
        self.cuerpo = QtWidgets.QVBoxLayout(self)
        self.cuerpo.setContentsMargins(14, 12, 14, 14)
        self.cuerpo.setSpacing(8)
        if titulo:
            self.titulo = QtWidgets.QLabel(titulo, objectName="titulo_tarjeta", wordWrap=True)
            self.cuerpo.addWidget(self.titulo)


class Plegable(QtWidgets.QFrame):
    """Bloque del panel que se pliega al pulsar su cabecera; empieza plegado. Se rellena con `.cuerpo` (QVBoxLayout)."""

    def __init__(self, titulo, parent=None):
        super().__init__(parent, objectName="tarjeta")
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.cabecera = QtWidgets.QPushButton(titulo, objectName="plegable", checkable=True)
        self.cabecera.setIconSize(QtCore.QSize(16, 16))
        self.cabecera.toggled.connect(self._pinta)
        v.addWidget(self.cabecera)
        self._hoja = QtWidgets.QWidget()
        self.cuerpo = QtWidgets.QVBoxLayout(self._hoja)
        self.cuerpo.setContentsMargins(14, 2, 14, 14)
        self.cuerpo.setSpacing(8)
        v.addWidget(self._hoja)
        self._pinta(False)

    def _pinta(self, abierto):
        self._hoja.setVisible(abierto)
        tema.pon_icono(self.cabecera, "chevron_abajo" if abierto else "chevron", "tenue", 16)


class FilaPaso(QtWidgets.QFrame):
    """Un paso del flujo, en la página de inicio: número, título, estado y flecha. Se pulsa entero."""
    pulsada = QtCore.Signal()

    def __init__(self, numero, titulo, parent=None):
        super().__init__(parent, objectName="paso")
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(10, 9, 10, 9)
        h.setSpacing(10)
        self.num = QtWidgets.QLabel(str(numero), objectName="paso_num")
        self.num.setFixedSize(26, 26)
        self.num.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        h.addWidget(self.num)
        v = QtWidgets.QVBoxLayout()
        v.setSpacing(1)
        v.addWidget(QtWidgets.QLabel(titulo, objectName="titulo_tarjeta"))
        self.lbl = QtWidgets.QLabel(objectName="nota", wordWrap=True)
        v.addWidget(self.lbl)
        h.addLayout(v, 1)
        flecha = QtWidgets.QLabel()
        tema.pon_icono(flecha, "chevron", "tenue", 16)
        h.addWidget(flecha)

    def poner(self, texto, hecho=False):
        self.lbl.setText(texto)
        self.num.setProperty("hecho", hecho)
        self.num.style().unpolish(self.num)
        self.num.style().polish(self.num)

    def mouseReleaseEvent(self, e):
        if self.rect().contains(e.position().toPoint()):
            self.pulsada.emit()


class TituloDock(QtWidgets.QWidget):
    """Barra de título de los paneles acoplables: se arrastra para moverlo y tiene sus dos botones."""

    def __init__(self, dock, titulo="", parent=None):
        super().__init__(parent, objectName="titulo_dock")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(14, 8, 8, 8)
        h.setSpacing(2)
        self.lbl = QtWidgets.QLabel(titulo, objectName="titulo_dock_t")
        h.addWidget(self.lbl, 1)
        for nombre, ayuda, accion in (
                ("flotar", "Sacar a una ventana",
                 lambda: dock.setFloating(not dock.isFloating())),
                ("cerrar", "Ocultar", dock.hide)):
            b = QtWidgets.QToolButton(objectName="icono")
            tema.pon_icono(b, nombre, "tenue", 16)
            b.setIconSize(QtCore.QSize(16, 16))
            b.setToolTip(ayuda)
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, a=accion: a())
            h.addWidget(b)
