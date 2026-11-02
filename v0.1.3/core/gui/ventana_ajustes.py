# -*- coding: utf-8 -*-
"""Ventana de configuración: el estilo de la app, cómo se ve el viento (pedido del usuario, 2026-10-31) y las
escalas de color del viento, los olores y los gases (2026-11-01), con un mapa al lado para ver cómo quedan.

Todo se aplica al momento y se guarda para la próxima vez: no hace falta reiniciar. Por eso es una ventana
normal y no un diálogo que bloquea: se ve cómo cambia la app detrás de ella."""
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from teodors import planta as config
from teodors.comun import escalas
from teodors.gui import tema
from teodors.gui.tema import c
from teodors.gui.widgets import Plegable


def _color(col, alfa=255):
    q = QtGui.QColor(col)
    q.setAlpha(alfa)
    return q


def _muestra_escala(clave, ancho=130, alto=14, densidad=2):
    """La escala en una tira, para elegirla viéndola."""
    n = ancho * densidad
    fila = (escalas.lut(clave)[np.linspace(0, 255, n).round().astype(int)] * 255).round().astype(np.uint8)
    img = QtGui.QImage(fila.tobytes(), n, 1, 3 * n, QtGui.QImage.Format.Format_RGB888)
    pm = QtGui.QPixmap.fromImage(img.scaled(n, alto * densidad))
    pm.setDevicePixelRatio(densidad)
    return pm


class SelectorEscala(QtWidgets.QComboBox):
    """Una escala de color, con su tira. La rueda del ratón desplaza la ventana: no cambia la escala sin querer."""

    def __init__(self, al_elegir, parent=None):
        super().__init__(parent)
        self.setIconSize(QtCore.QSize(130, 14))
        self.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        for clave, (nombre, _) in escalas.ESCALAS.items():
            self.addItem(QtGui.QIcon(_muestra_escala(clave)), nombre, clave)
        self.activated.connect(lambda i: al_elegir(self.itemData(i)))

    def poner(self, clave):
        self.setCurrentIndex(self.findData(clave))

    def wheelEvent(self, evento):
        evento.ignore()


class TarjetaEstilo(QtWidgets.QAbstractButton):
    """Un estilo: una miniatura de la app pintada con SUS colores y su nombre."""
    ALTO_MINIATURA = 118

    def __init__(self, clave, parent=None):
        super().__init__(parent)
        self.clave = clave
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(270, self.ALTO_MINIATURA + 44)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover)

    def _miniatura(self, p, r):
        """La app en pequeño, con el estilo de esta tarjeta y no con el que está en uso."""
        t = tema.TEMAS[self.clave]["colores"]
        camino = QtGui.QPainterPath()
        camino.addRoundedRect(QtCore.QRectF(r), 8, 8)
        p.save()
        p.setClipPath(camino)
        p.fillRect(r, QtGui.QColor(t["fondo"]))
        barra = 15
        p.fillRect(r.x(), r.y(), r.width(), barra, QtGui.QColor(t["superficie"]))
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(t["acento"]))
        p.drawRoundedRect(r.x() + 5, r.y() + 3, 9, 9, 2, 2)
        p.setBrush(QtGui.QColor(t["texto"]))
        p.drawRoundedRect(r.x() + 18, r.y() + 6, 44, 3, 1, 1)
        arriba = r.y() + barra
        alto = r.height() - barra
        # barra de iconos
        p.fillRect(r.x(), arriba, 16, alto, QtGui.QColor(t["superficie"]))
        for k in range(4):
            p.setBrush(QtGui.QColor(t["acento"] if k == 0 else t["apagado"]))
            p.drawEllipse(r.x() + 5, arriba + 7 + 13 * k, 6, 6)
        # panel, con dos tarjetas
        x, ancho = r.x() + 21, 68
        for k, h in enumerate((34, 40)):
            y = arriba + 5 + k * 40
            p.setPen(QtGui.QPen(QtGui.QColor(t["borde"]), 1))
            p.setBrush(QtGui.QColor(t["superficie"]))
            p.drawRoundedRect(x, y, ancho, h, 3, 3)
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(QtGui.QColor(t["texto"]))
            p.drawRoundedRect(x + 5, y + 6, 34, 3, 1, 1)
            p.setBrush(QtGui.QColor(t["tenue"]))
            p.drawRoundedRect(x + 5, y + 13, 56, 2, 1, 1)
            p.drawRoundedRect(x + 5, y + 18, 44, 2, 1, 1)
            if k == 1:
                p.setBrush(QtGui.QColor(t["acento"]))
                p.drawRoundedRect(x + 5, y + 26, 58, 9, 3, 3)
        # mapa: siempre la misma ortofoto, cambia lo que hay encima
        xm = x + ancho + 5
        repro = 15
        mapa = QtCore.QRect(xm, arriba, r.right() - xm + 1, alto - repro)
        g = QtGui.QLinearGradient(QtCore.QPointF(mapa.topLeft()), QtCore.QPointF(mapa.bottomRight()))
        g.setColorAt(0, QtGui.QColor("#4f6b3f"))
        g.setColorAt(0.55, QtGui.QColor("#8a7a55"))
        g.setColorAt(1, QtGui.QColor("#35566b"))
        p.fillRect(mapa, g)
        cx, cy = mapa.x() + mapa.width() * 0.34, mapa.y() + mapa.height() * 0.36
        penacho = QtGui.QPolygonF([QtCore.QPointF(cx, cy), QtCore.QPointF(cx + 62, cy + 20),
                                   QtCore.QPointF(cx + 36, cy + 42)])
        g2 = QtGui.QLinearGradient(QtCore.QPointF(cx, cy), QtCore.QPointF(cx + 54, cy + 32))
        g2.setColorAt(0, _color("#fb7f22", 230))
        g2.setColorAt(0.5, _color("#3ef08e", 170))
        g2.setColorAt(1, _color("#4669db", 40))
        p.setBrush(g2)
        p.drawPolygon(penacho)
        p.setBrush(QtGui.QColor(t["acento"]))
        p.setPen(QtGui.QPen(QtGui.QColor(t["sobre_acento"]), 1))
        p.drawEllipse(QtCore.QPointF(cx, cy), 4, 4)
        p.setPen(QtGui.QPen(QtGui.QColor(t["fam_residencial"]), 2))
        p.setBrush(QtGui.QColor(t["fondo"]))
        p.drawEllipse(QtCore.QPointF(mapa.x() + mapa.width() * 0.78, mapa.y() + 13), 4, 4)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(t["superficie"]))
        p.drawRoundedRect(mapa.x() + 5, mapa.bottom() - 16, 34, 12, 3, 3)
        # reproductor
        y = mapa.bottom() + 1
        p.fillRect(xm, y, mapa.width(), repro, QtGui.QColor(t["superficie"]))
        p.setBrush(QtGui.QColor(t["acento"]))
        p.drawEllipse(xm + 5, y + 3, 9, 9)
        p.setBrush(QtGui.QColor(t["barra_inactiva"]))
        p.drawRoundedRect(xm + 19, y + 6, mapa.width() - 26, 3, 1, 1)
        p.setBrush(QtGui.QColor(t["acento"]))
        p.drawRoundedRect(xm + 19, y + 6, (mapa.width() - 26) // 2, 3, 1, 1)
        p.restore()
        p.setPen(QtGui.QPen(QtGui.QColor(t["borde"] if self.clave != "contraste" else t["borde_fuerte"]), 1))
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.drawPath(camino)

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        marco = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        elegida, encima = self.isChecked(), self.underMouse()
        p.setPen(QtGui.QPen(QtGui.QColor(c("acento") if elegida else c("borde_fuerte") if encima else c("borde")),
                            2 if elegida else 1))
        p.setBrush(QtGui.QColor(c("tinte") if elegida else c("superficie")))
        p.drawRoundedRect(marco, 12, 12)
        self._miniatura(p, QtCore.QRect(10, 10, self.width() - 20, self.ALTO_MINIATURA))
        y = self.ALTO_MINIATURA + 16
        fuente = QtGui.QFont(self.font())
        fuente.setWeight(QtGui.QFont.Weight.DemiBold)
        fuente.setPixelSize(14)
        p.setFont(fuente)
        p.setPen(QtGui.QColor(c("texto")))
        p.drawText(QtCore.QRect(12, y, self.width() - 44, 20),
                   QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter,
                   tema.TEMAS[self.clave]["nombre"])
        if elegida:                                  # marca de «en uso»
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(QtGui.QColor(c("acento")))
            p.drawEllipse(self.width() - 32, y + 1, 18, 18)
            p.setPen(QtGui.QPen(QtGui.QColor(c("sobre_acento")), 2, QtCore.Qt.PenStyle.SolidLine,
                                QtCore.Qt.PenCapStyle.RoundCap, QtCore.Qt.PenJoinStyle.RoundJoin))
            x0, y0 = self.width() - 32, y + 1
            p.drawPolyline(QtGui.QPolygonF([QtCore.QPointF(x0 + 5, y0 + 9.5), QtCore.QPointF(x0 + 8, y0 + 12.5),
                                            QtCore.QPointF(x0 + 13, y0 + 6)]))
        p.end()


class VentanaAjustes(QtWidgets.QWidget):
    """Una sola, no modal: la app se ve cambiar detrás."""
    vientoCambiado = QtCore.Signal()             # forma, color, escala o cantidad
    escalasCambiadas = QtCore.Signal()           # escala de los olores o de los gases

    def __init__(self, emp, parent=None):
        super().__init__(parent, QtCore.Qt.WindowType.Window)
        self.setWindowTitle(f"Configuración · {config.APP_NOMBRE}")
        tema.estilo(self, tema.ESTILO_VENTANAS)
        self.setObjectName("ajustes")
        pantalla = self.screen().availableGeometry()
        self.resize(min(1290, pantalla.width() - 40), min(720, pantalla.height() - 60))
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._cabecera())
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(0)
        area = QtWidgets.QScrollArea(widgetResizable=True)
        area.setFixedWidth(640)
        area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        hoja = QtWidgets.QWidget(objectName="pagina")
        v = QtWidgets.QVBoxLayout(hoja)
        v.setContentsMargins(18, 16, 18, 18)
        v.setSpacing(10)
        self.pleg_estilo = Plegable("Estilo")
        self.pleg_estilo.cuerpo.addLayout(self._estilos())
        self.pleg_viento = self._viento()
        self.pleg_concentraciones = self._concentraciones()
        for seccion in (self.pleg_estilo, self.pleg_viento, self.pleg_concentraciones):
            v.addWidget(seccion)
        v.addStretch()
        area.setWidget(hoja)
        fila.addWidget(area)
        from teodors.gui.vista_previa import VistaPrevia       # solo aquí: trae mapa_web y, con él, folium
        self.previa = VistaPrevia(emp)
        fila.addWidget(self.previa, 1)
        lay.addLayout(fila, 1)
        self.vientoCambiado.connect(self.previa.viento_estilo)
        self.escalasCambiadas.connect(self.previa.set_escalas)
        self.refrescar()
        tema.manos(self)
        tema.avisos.cambiado.connect(self._repintar_tarjetas)

    # ── construcción ─────────────────────────────────────────────────────────────────────
    def _cabecera(self):
        w = QtWidgets.QWidget(objectName="cabecera")
        w.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(18, 10, 18, 10)
        h.addWidget(QtWidgets.QLabel("Configuración", objectName="titulo"), 1)
        b = QtWidgets.QPushButton("Restablecer")
        b.clicked.connect(self._restablecer)
        h.addWidget(b)
        b = QtWidgets.QPushButton("Cerrar")
        b.clicked.connect(self.close)
        h.addWidget(b)
        return w

    def _estilos(self):
        rejilla = QtWidgets.QGridLayout()
        rejilla.setSpacing(10)
        self._grupo_estilos = QtWidgets.QButtonGroup(self, exclusive=True)
        self.tarjetas = {}
        for i, clave in enumerate(tema.TEMAS):
            t = TarjetaEstilo(clave)
            t.clicked.connect(lambda _=False, k=clave: self._elegir_estilo(k))
            self._grupo_estilos.addButton(t)
            self.tarjetas[clave] = t
            rejilla.addWidget(t, i // 2, i % 2)
        return rejilla

    def _segmentos(self, opciones, al_elegir):
        """Botones pegados, uno marcado. Devuelve el layout y {clave: botón}."""
        h = QtWidgets.QHBoxLayout()
        h.setSpacing(0)
        grupo = QtWidgets.QButtonGroup(self, exclusive=True)
        botones = {}
        for clave, texto in opciones:
            b = QtWidgets.QPushButton(texto, objectName="segmento", checkable=True)
            b.clicked.connect(lambda _=False, k=clave: al_elegir(k))
            grupo.addButton(b)
            botones[clave] = b
            h.addWidget(b)
        h.addStretch()
        return h, botones

    @staticmethod
    def _formulario(seccion):
        f = QtWidgets.QFormLayout()
        f.setHorizontalSpacing(16)
        f.setVerticalSpacing(10)
        seccion.cuerpo.addLayout(f)
        return f

    def _viento(self):
        sec = Plegable("Viento en el mapa")
        f = self._formulario(sec)
        h, self._b_forma = self._segmentos((("particulas", "Partículas"), ("lineas", "Líneas de corriente"),
                                            ("flechas", "Flechas")),
                                           lambda k: self._elegir_viento("viento_forma", k))
        f.addRow("Forma:", h)
        h, self._b_color = self._segmentos((("blanco", "Blanco"), ("velocidad", "Por velocidad")),
                                           lambda k: self._elegir_viento("viento_color", k))
        f.addRow("Color:", h)
        self.sel_viento = SelectorEscala(lambda k: self._elegir_viento("escala_viento", k))
        f.addRow("Escala:", self._a_la_izquierda(self.sel_viento))
        h, self._b_cantidad = self._segmentos((("pocas", "Poca"), ("normal", "Normal"), ("muchas", "Mucha")),
                                              lambda k: self._elegir_viento("viento_cantidad", k))
        f.addRow("Cantidad:", h)
        return sec

    @staticmethod
    def _a_la_izquierda(w):
        h = QtWidgets.QHBoxLayout()
        h.addWidget(w)
        h.addStretch()
        return h

    def _concentraciones(self):
        sec = Plegable("Concentraciones en el mapa")
        f = self._formulario(sec)
        self.sel_olor = SelectorEscala(lambda k: self._elegir_escala("olor", k))
        f.addRow("Olores:", self._a_la_izquierda(self.sel_olor))
        self.sel_gases = SelectorEscala(lambda k: self._elegir_escala("gases", k))
        f.addRow("Gases:", self._a_la_izquierda(self.sel_gases))
        return sec

    # ── lo elegido ───────────────────────────────────────────────────────────────────────
    def refrescar(self):
        """Marca lo que está en uso."""
        self.tarjetas[tema.estilo_actual()].setChecked(True)
        self._b_forma[tema.preferencia("viento_forma")].setChecked(True)
        self._b_color[tema.preferencia("viento_color")].setChecked(True)
        self._b_cantidad[tema.preferencia("viento_cantidad")].setChecked(True)
        self.sel_viento.poner(tema.preferencia("escala_viento"))
        self.sel_viento.setEnabled(tema.preferencia("viento_color") == "velocidad")
        self.sel_olor.poner(tema.preferencia("escala_olor"))
        self.sel_gases.poner(tema.preferencia("escala_gases"))

    def _repintar_tarjetas(self):
        for t in self.tarjetas.values():
            t.update()

    def _elegir_estilo(self, clave):
        if clave != tema.estilo_actual():
            tema.poner(clave)

    def _elegir_viento(self, preferencia, valor):
        tema.poner_preferencia(preferencia, valor)
        self.sel_viento.setEnabled(tema.preferencia("viento_color") == "velocidad")
        self.vientoCambiado.emit()

    def _elegir_escala(self, magnitud, valor):
        tema.poner_preferencia(f"escala_{magnitud}", valor)
        self.escalasCambiadas.emit()
        self.previa.ver_escala(magnitud)

    # ── el mapa, solo cuando se ve ───────────────────────────────────────────────────────
    def changeEvent(self, evento):
        if evento.type() == QtCore.QEvent.Type.WindowStateChange:
            # con retardo: Qt vuelve a poner visible la página justo al minimizar (ventana._segun_minimizada)
            QtCore.QTimer.singleShot(300, lambda: self.dormir(self.isMinimized()))
        super().changeEvent(evento)

    def dormir(self, si):
        self.previa.page().setVisible(self.isVisible() and not si)

    def _restablecer(self):
        self._elegir_estilo(tema.ESTILO_DEFECTO)
        for clave, valor in tema.PREFERENCIAS.items():
            tema.poner_preferencia(clave, valor)
        self.vientoCambiado.emit()
        self.escalasCambiadas.emit()
        self.previa.ver_escala("olor")
        self.refrescar()
