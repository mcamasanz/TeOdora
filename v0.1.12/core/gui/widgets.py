# -*- coding: utf-8 -*-
"""Widgets pequeños reutilizables de la interfaz (aspecto en gui/tema.py)."""
from PySide6 import QtCore, QtWidgets

from teodors.gui import tema


def preguntar_si(padre, titulo, texto):
    """¿Sí o no?, con los botones en castellano (Qt no trae su traducción: saldría «Yes»/«No»). True si «Sí»."""
    B = QtWidgets.QMessageBox.StandardButton
    caja = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Question, titulo, texto, B.Yes | B.No, padre)
    caja.setDefaultButton(B.Yes)
    caja.button(B.Yes).setText("Sí")
    caja.button(B.No).setText("No")
    if padre is not None:
        padre._pregunta = caja
    try:
        caja.exec()
        boton = caja.clickedButton()
        return boton is not None and caja.standardButton(boton) == B.Yes
    finally:
        if padre is not None:
            padre._pregunta = None
        caja.deleteLater()


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


class Indicador(QtWidgets.QWidget):
    """El estado de una categoría de «Comprobar la herramienta»: un círculo de puntos en espera, un arco que gira mientras se comprueba y,
    al acabar, ✓, ⚠ o ✗ en el color de cada uno. Se pinta a mano: los colores, del estilo en uso."""
    ICONO = {"ok": ("ok", "acento_claro"), "aviso": ("aviso", "aviso"), "fallo": ("fallo", "fallo")}

    def __init__(self, lado=24, parent=None):
        super().__init__(parent)
        self.setFixedSize(lado, lado)
        self.estado, self._angulo = "pendiente", 0
        self._reloj = QtCore.QTimer(self, interval=40)
        self._reloj.timeout.connect(self._gira)
        tema.avisos.cambiado.connect(self.update)

    def poner(self, estado):
        self.estado = estado
        if estado == "en_curso":
            self._reloj.start()
        else:
            self._reloj.stop()
        self.update()

    def girando(self):
        return self._reloj.isActive()

    def _gira(self):
        self._angulo = (self._angulo + 24) % 360
        self.update()

    def paintEvent(self, _e):
        from PySide6 import QtGui
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        lado = self.width()
        r = QtCore.QRectF(2.5, 2.5, lado - 5, lado - 5)
        if self.estado in self.ICONO:
            nombre, color = self.ICONO[self.estado]
            p.drawPixmap(0, 0, tema.pixmap(nombre, tema.c(color), lado))
        elif self.estado == "en_curso":
            fondo = QtGui.QColor(tema.c("acento"))
            fondo.setAlphaF(0.22)
            p.setPen(QtGui.QPen(fondo, 2.6))
            p.drawEllipse(r)
            p.setPen(QtGui.QPen(QtGui.QColor(tema.c("acento")), 2.6, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap))
            p.drawArc(r, int(-self._angulo * 16), 100 * 16)
        else:
            p.setPen(QtGui.QPen(QtGui.QColor(tema.c("apagado")), 1.8, QtCore.Qt.PenStyle.DotLine, QtCore.Qt.PenCapStyle.RoundCap))
            p.drawEllipse(r)


class TarjetaCategoria(QtWidgets.QFrame):
    """Una categoría de «Comprobar la herramienta», en la página de inicio (usuario, 2026-11-07: que se vea que se está trabajando en ese
    apartado hasta que sale bien o mal, y sin descripciones: si falla, basta su código). Su icono, su nombre y el indicador: en espera,
    comprobándose (gira, y una barra fina cuenta sus pruebas) o, al acabar, ✓, ⚠ o ✗ y sus códigos en etiquetas de color."""

    def __init__(self, nombre, icono, total, parent=None):
        super().__init__(parent, objectName="cat")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        self.total, self.hechas, self.codigos = total, 0, []
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(10, 9, 12, 9)
        h.setSpacing(10)
        self.ico = QtWidgets.QLabel(objectName="cat_ico")
        self.ico.setFixedSize(34, 34)
        self.ico.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._icono = icono
        h.addWidget(self.ico, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        v = QtWidgets.QVBoxLayout()
        v.setSpacing(4)
        v.addStretch()
        self.titulo = QtWidgets.QLabel(nombre, objectName="cat_t")
        v.addWidget(self.titulo)
        self._chips = QtWidgets.QHBoxLayout()
        self._chips.setSpacing(4)
        self._chips.addStretch()
        v.addLayout(self._chips)
        self.barra = QtWidgets.QProgressBar(objectName="cat_barra", minimum=0, maximum=max(total, 1), textVisible=False)
        self.barra.setVisible(False)
        v.addWidget(self.barra)
        v.addStretch()
        h.addLayout(v, 1)
        self.indicador = Indicador()
        h.addWidget(self.indicador, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.estado = None
        self.reiniciar()

    def _poner_estado(self, estado):
        self.estado = estado
        self.setProperty("estado", estado)
        self.style().unpolish(self)
        self.style().polish(self)
        self.indicador.poner(estado)
        color = {"en_curso": "acento_claro", "aviso": "aviso", "fallo": "fallo"}.get(estado, "tenue")
        tema.pon_icono(self.ico, self._icono, color, 20)

    def reiniciar(self):
        """En espera: sin comprobar."""
        self.hechas, self.codigos = 0, []
        self._chips_de([])
        self.barra.setVisible(False)
        self.barra.setValue(0)
        self._poner_estado("pendiente")

    def empezar(self):
        """Se está comprobando: el indicador gira y la barra cuenta las pruebas."""
        if self.estado != "en_curso":
            self._poner_estado("en_curso")
        self.barra.setVisible(True)

    def prueba_hecha(self, codigos):
        """Una prueba más de la categoría, con sus códigos (los de otra categoría no llegan aquí)."""
        self.hechas += 1
        self.codigos = sorted(set(self.codigos) | set(codigos))
        self.barra.setValue(self.hechas)

    def acabar(self, estado, codigos, que=None):
        """El resultado: `estado` "ok", "aviso" o "fallo"; `codigos`, los suyos; `que`, {código: (gravedad, qué pasa)} para las etiquetas."""
        self.codigos = list(codigos)
        self.barra.setVisible(False)
        self._poner_estado(estado)
        self._chips_de([(c, (que or {}).get(c, ("fallo", ""))) for c in self.codigos])

    def _chips_de(self, lista):
        while self._chips.count() > 1:
            w = self._chips.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        for k, (codigo, (grav, texto)) in enumerate(lista):
            chip = QtWidgets.QLabel(codigo, objectName="chip_fallo" if grav == "fallo" else "chip_aviso")
            chip.setToolTip(f"<b>{codigo}</b> · {texto}" if texto else codigo)
            self._chips.insertWidget(k, chip)


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
