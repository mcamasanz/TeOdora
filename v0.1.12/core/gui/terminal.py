# -*- coding: utf-8 -*-
"""Terminal: una línea para escribir comandos, junto a la actividad (usuario, 2026-11-08: «mi idea de terminal es poder hacer diferentes
comandos ocultos, como el cambio de usuario»; «deben ser palabras protegidas que comiencen por "_", para que no se descubran»). Los
comandos los registra la ventana; los que empiezan por «_» son ocultos: `ayuda` no los lista.

Solo ejecuta lo registrado con `registrar`, nunca Python ni órdenes del sistema, y lo que se escribe no va al registro. Una contraseña
(`pedir_clave`) no se ve al escribirla, no sale en la terminal y no queda en el historial; Esc la cancela."""
from PySide6 import QtCore, QtGui, QtWidgets


class Terminal(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._comandos = {}
        self._historial, self._pos = [], 0
        self._pidiendo = None                        # la función que recibe la contraseña que se está escribiendo
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

    OCULTO = "_"                                     # un comando que empieza así es oculto

    def registrar(self, nombre, funcion):
        """Añade un comando. `funcion(*palabras)` puede devolver un texto, que se escribe en la salida. Si empieza por «_», es oculto."""
        self._comandos[nombre.lower()] = funcion

    def visibles(self):
        """Los comandos que no son ocultos (los que no empiezan por «_»), por orden alfabético."""
        return sorted(c for c in self._comandos if not c.startswith(self.OCULTO))

    def pedir_clave(self, texto, al_recibir):
        """Lo siguiente que se escriba es una contraseña: va a `al_recibir(clave)`, que puede devolver un texto para la salida."""
        self._pidiendo = al_recibir
        self.salida.appendPlainText(texto)
        self.entrada.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.entrada.setPlaceholderText("contraseña · Esc para cancelar")
        self.entrada.setFocus()

    def pidiendo_clave(self):
        return self._pidiendo is not None

    def _fin_clave(self):
        self._pidiendo = None
        self.entrada.clear()
        self.entrada.setEchoMode(QtWidgets.QLineEdit.EchoMode.Normal)
        self.entrada.setPlaceholderText("")

    def showEvent(self, evento):
        super().showEvent(evento)
        self.entrada.setFocus()

    def _ejecutar(self):
        if self._pidiendo is not None:               # una contraseña: ni se escribe en la salida ni queda en el historial
            clave, funcion = self.entrada.text(), self._pidiendo
            self._fin_clave()
            self.salida.appendPlainText("> ••••••")
            try:
                respuesta = funcion(clave)
            except Exception as e:                   # noqa: BLE001 (un comando con fallos no debe tirar la app)
                respuesta = f"{type(e).__name__}: {e}"
            if respuesta:
                self.salida.appendPlainText(str(respuesta))
            return
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
        """Flechas arriba y abajo: los comandos anteriores (no mientras se escribe una contraseña); Esc cancela la contraseña."""
        if objeto is self.entrada and evento.type() == QtCore.QEvent.Type.KeyPress and self._pidiendo is not None:
            if evento.key() == QtCore.Qt.Key.Key_Escape:
                self._fin_clave()
                self.salida.appendPlainText("Cancelado.")
                return True
            if evento.key() in (QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Down):
                return True
        if objeto is self.entrada and evento.type() == QtCore.QEvent.Type.KeyPress:
            paso = {QtCore.Qt.Key.Key_Up: -1, QtCore.Qt.Key.Key_Down: 1}.get(evento.key())
            if paso and self._historial:
                self._pos = max(0, min(len(self._historial), self._pos + paso))
                self.entrada.setText(self._historial[self._pos] if self._pos < len(self._historial) else "")
                return True
        return super().eventFilter(objeto, evento)
