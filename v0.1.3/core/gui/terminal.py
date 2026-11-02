# -*- coding: utf-8 -*-
"""Terminal de administrador: una línea para escribir comandos, junto a la actividad.

Solo ejecuta lo registrado con `registrar`, nunca Python ni órdenes del sistema, y lo que se escribe no
va al registro. Los comandos de administrador están por definir (usuario, 2026-10-31)."""
from PySide6 import QtCore, QtGui, QtWidgets


class Terminal(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._comandos = {}
        self._historial, self._pos = [], 0
        fuente = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        fuente.setPointSize(9)
        self.salida = QtWidgets.QPlainTextEdit(readOnly=True, objectName="actividad")
        self.salida.setMaximumBlockCount(5000)
        self.salida.setFont(fuente)
        marca = QtWidgets.QLabel(">", objectName="terminal_marca")
        marca.setFont(fuente)
        self.entrada = QtWidgets.QLineEdit(objectName="terminal")
        self.entrada.setFont(fuente)
        self.entrada.returnPressed.connect(self._ejecutar)
        self.entrada.installEventFilter(self)

        fila = QtWidgets.QFrame(objectName="terminal_fila")
        h = QtWidgets.QHBoxLayout(fila)
        h.setContentsMargins(10, 2, 8, 2)
        h.setSpacing(6)
        h.addWidget(marca)
        h.addWidget(self.entrada, 1)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self.salida, 1)
        v.addWidget(fila)
        self.registrar("limpiar", self.salida.clear)

    def sizeHint(self):
        return QtCore.QSize(800, 170)

    def registrar(self, nombre, funcion):
        """Añade un comando. `funcion(*palabras)` puede devolver un texto, que se escribe en la salida."""
        self._comandos[nombre.lower()] = funcion

    def showEvent(self, evento):
        super().showEvent(evento)
        self.entrada.setFocus()

    def _ejecutar(self):
        linea = self.entrada.text().strip()
        self.entrada.clear()
        if not linea:
            return
        self._historial.append(linea)
        self._pos = len(self._historial)
        self.salida.appendPlainText(f"> {linea}")
        nombre, *palabras = linea.split()
        funcion = self._comandos.get(nombre.lower())
        if funcion is None:
            self.salida.appendPlainText(f"{nombre}: comando desconocido")
            return
        try:
            respuesta = funcion(*palabras)
        except Exception as e:                       # un comando con fallos no debe tirar la app
            self.salida.appendPlainText(f"{nombre}: {e}")
            return
        if respuesta:
            self.salida.appendPlainText(str(respuesta))

    def eventFilter(self, objeto, evento):
        """Flechas arriba y abajo: los comandos anteriores."""
        if objeto is self.entrada and evento.type() == QtCore.QEvent.Type.KeyPress:
            paso = {QtCore.Qt.Key.Key_Up: -1, QtCore.Qt.Key.Key_Down: 1}.get(evento.key())
            if paso and self._historial:
                self._pos = max(0, min(len(self._historial), self._pos + paso))
                self.entrada.setText(self._historial[self._pos] if self._pos < len(self._historial) else "")
                return True
        return super().eventFilter(objeto, evento)
