# -*- coding: utf-8 -*-
"""Lo de la página Planta, dibujado (usuario, 2026-11-07: «mejorar el diseño de este panel», con los botones de las capas como estaban;
luego, «dale una vuelta estética»):

- `Miniatura`: la zona de la planta en imagen, el relieve sombreado o los usos del suelo de las capas del mapa, con la planta y una escala.
- `BarrasCota`: el reparto de la cota por franjas, una barra fina por franja con el color de la capa de elevación, y la de la planta señalada.
- `BarraUsos`: los grupos de usos del suelo en una barra al 100 %, con sus colores; al pasar por un tramo, su nombre, su % y sus clases.

Los colores del estilo, leídos al pintar (`tema.c`): cambian con el estilo sin rehacer nada."""
import math

from PySide6 import QtCore, QtGui, QtWidgets

from teodors.comun.formato import num as _num
from teodors.gui import tema


def _pct(x):
    return "< 0,1 %" if 0 < x < 0.05 else f"{_num(x, 1)} %"


def color_gradiente(paradas, t):
    """El color en `t` (0-1) de un degradado de paradas #rrggbb repartidas por igual."""
    t = min(max(float(t), 0.0), 1.0) * (len(paradas) - 1)
    k = min(int(t), len(paradas) - 2)
    a, b = QtGui.QColor(paradas[k]), QtGui.QColor(paradas[k + 1])
    f = t - k
    return QtGui.QColor(*(round(x + (y - x) * f) for x, y in ((a.red(), b.red()), (a.green(), b.green()), (a.blue(), b.blue()))))


class _Pintado(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        tema.avisos.cambiado.connect(self.update)
        self.setMouseTracking(True)

    def _letra(self, px, negrita=False):
        f = QtGui.QFont(self.font())
        f.setPixelSize(px)
        f.setBold(negrita)
        return f


class Miniatura(_Pintado):
    """La zona de la planta en una imagen: el relieve sombreado o los usos del suelo de las capas del mapa (las mismas imágenes), recortados
    alrededor de la planta, con su marca y una escala. Arriba a la derecha se cambia de una a otra (`poner_modo`)."""
    ALTO = 176
    MODOS = (("relieve", "Relieve"), ("usos", "Usos"))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.ALTO)
        self._fuentes, self._px, self._cache = {}, {}, {}
        self._bounds, self._punto, self._km = None, None, None
        self.modo = "relieve"
        self.botones = {}
        caja = QtWidgets.QHBoxLayout(self)
        caja.setContentsMargins(8, 8, 10, 8)
        caja.setSpacing(4)
        caja.addStretch()
        grupo = QtWidgets.QButtonGroup(self)
        for clave, texto in self.MODOS:
            b = QtWidgets.QPushButton(texto, objectName="seg_mini", checkable=True, checked=clave == self.modo)
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=clave: self.poner_modo(c))
            grupo.addButton(b)
            self.botones[clave] = b
            caja.addWidget(b, 0, QtCore.Qt.AlignmentFlag.AlignTop)

    def poner(self, imagenes, bounds, lat, lon, lado_km):
        """imagenes: {"relieve": ruta, "usos": ruta} (PNG en Web Mercator); bounds: [[lat0, lon0], [lat1, lon1]] de las imágenes."""
        self._fuentes = {k: str(v) for k, v in imagenes.items() if v}
        self._px, self._cache = {}, {}
        self._bounds, self._punto, self._km = bounds, (lat, lon), lado_km
        for clave, b in self.botones.items():
            b.setVisible(clave in self._fuentes and len(self._fuentes) > 1)
        if self.modo not in self._fuentes and self._fuentes:
            self.modo = next(iter(self._fuentes))
        self.update()

    def poner_modo(self, modo):
        self.modo = modo
        self.botones[modo].setChecked(True)
        self.update()

    def _imagen(self):
        if self.modo not in self._px and self.modo in self._fuentes:
            self._px[self.modo] = QtGui.QPixmap(self._fuentes[self.modo])
        return self._px.get(self.modo)

    def recorte(self, ancho_img, alto_img):
        """El trozo de la imagen alrededor de la planta, con la forma del widget (el 60 % del alto), dónde cae la planta en él (0-1) y qué
        parte del ancho de la imagen es."""
        (la0, lo0), (la1, lo1) = self._bounds
        lat, lon = self._punto
        y = lambda la: math.log(math.tan(math.pi / 4 + math.radians(la) / 2))
        fx = (lon - lo0) / (lo1 - lo0)
        fy = (y(la1) - y(lat)) / (y(la1) - y(la0))
        alto = alto_img * 0.6
        ancho = min(ancho_img, alto * max(self.width(), 1) / self.ALTO)
        alto = ancho * self.ALTO / max(self.width(), 1)
        x0 = min(max(fx * ancho_img - ancho / 2, 0), ancho_img - ancho)
        y0 = min(max(fy * alto_img - alto / 2, 0), alto_img - alto)
        return QtCore.QRectF(x0, y0, ancho, alto), ((fx * ancho_img - x0) / ancho, (fy * alto_img - y0) / alto), ancho / ancho_img

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        r = QtCore.QRectF(self.rect())
        marco = QtGui.QPainterPath()
        marco.addRoundedRect(r, 10, 10)
        oscuro = tema.TEMAS[tema.estilo_actual()]["esquema"] == "oscuro"
        p.fillPath(marco, QtGui.QColor("#1b3448" if oscuro else "#cfe2f0"))          # el mar, que en el relieve va transparente
        px = self._imagen()
        if px is None or px.isNull() or not self._bounds:
            p.setPen(QtGui.QColor(tema.c("tenue")))
            p.drawText(r, QtCore.Qt.AlignmentFlag.AlignCenter, "Sin terreno")
            return
        trozo, (fx, fy), parte = self.recorte(px.width(), px.height())
        clave = (self.modo, self.width())
        if clave not in self._cache:
            dpr = self.devicePixelRatioF()
            hecha = px.copy(trozo.toRect()).scaled(int(self.width() * dpr), int(self.ALTO * dpr),
                                                    QtCore.Qt.AspectRatioMode.IgnoreAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
            hecha.setDevicePixelRatio(dpr)
            self._cache[clave] = hecha
        p.setClipPath(marco)
        p.drawPixmap(0, 0, self._cache[clave])
        sombra = QtGui.QLinearGradient(0, self.ALTO - 46, 0, self.ALTO)                 # para que la escala se lea sobre cualquier fondo
        sombra.setColorAt(0, QtGui.QColor(0, 0, 0, 0))
        sombra.setColorAt(1, QtGui.QColor(0, 0, 0, 120))
        p.fillRect(QtCore.QRectF(0, self.ALTO - 46, self.width(), 46), sombra)
        # la planta: un punto blanco con borde oscuro y un halo blanco, que se ve sobre el relieve y sobre los usos
        cx, cy = fx * self.width(), fy * self.ALTO
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(255, 255, 255, 90))
        p.drawEllipse(QtCore.QPointF(cx, cy), 14, 14)
        p.setPen(QtGui.QPen(QtGui.QColor("#101412"), 2.5))
        p.setBrush(QtGui.QColor("#ffffff"))
        p.drawEllipse(QtCore.QPointF(cx, cy), 6, 6)
        # la escala: 5 km, o 2 si la vista es pequeña
        km_vista = self._km * parte
        paso = 5 if km_vista > 12 else 2
        largo = self.width() * paso / km_vista
        x, y = 12, self.ALTO - 14
        p.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 2, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.FlatCap))
        p.drawLine(QtCore.QPointF(x, y), QtCore.QPointF(x + largo, y))
        for xx in (x, x + largo):
            p.drawLine(QtCore.QPointF(xx, y - 4), QtCore.QPointF(xx, y + 1))
        p.setFont(self._letra(11, True))
        p.drawText(QtCore.QPointF(x + largo + 6, y + 4), f"{paso} km")


class BarrasCota(_Pintado):
    """Una fila por franja de cota: su nombre, una barra fina y redondeada del largo de su % (con el color de esa cota en la capa de
    elevación) y el %. La franja de la planta, con su etiqueta."""
    FILA, NOMBRE, PCT = 26, 118, 50

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bandas, self._colores, self._planta = [], [], None

    def poner(self, bandas, colores, planta=None):
        """bandas: [{banda, pct}]; colores: un QColor por franja; planta: el índice de la franja de la planta (o None)."""
        self._bandas, self._colores, self._planta = list(bandas), list(colores), planta
        self.setFixedHeight(self.FILA * len(self._bandas))
        self.update()

    def paintEvent(self, _e):
        if not self._bandas:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        ancho = self.width() - self.NOMBRE - self.PCT - 6
        tope = max(b["pct"] for b in self._bandas) or 1
        texto, tenue = QtGui.QColor(tema.c("texto")), QtGui.QColor(tema.c("tenue"))
        for k, b in enumerate(self._bandas):
            y = k * self.FILA
            suya = k == self._planta
            letra = self._letra(12, suya)
            p.setFont(letra)
            p.setPen(texto if suya else tenue)
            p.drawText(QtCore.QRectF(0, y, self.NOMBRE, self.FILA), QtCore.Qt.AlignmentFlag.AlignVCenter, b["banda"])
            if suya:                                               # la etiqueta de la planta, tras el nombre
                x = QtGui.QFontMetrics(letra).horizontalAdvance(b["banda"]) + 6
                p.setFont(self._letra(10, True))
                w = p.fontMetrics().horizontalAdvance("planta") + 12
                pil = QtGui.QPainterPath()
                pil.addRoundedRect(QtCore.QRectF(x, y + 5, w, self.FILA - 10), 8, 8)
                p.fillPath(pil, QtGui.QColor(tema.c("acento")))
                p.setPen(QtGui.QColor(tema.c("sobre_acento")))
                p.drawText(QtCore.QRectF(x, y + 5, w, self.FILA - 10), QtCore.Qt.AlignmentFlag.AlignCenter, "planta")
            pista = QtGui.QPainterPath()
            pista.addRoundedRect(QtCore.QRectF(self.NOMBRE, y + 9, ancho, self.FILA - 18), 4, 4)
            p.fillPath(pista, QtGui.QColor(tema.c("elevada")))
            barra = QtGui.QPainterPath()
            barra.addRoundedRect(QtCore.QRectF(self.NOMBRE, y + 9, max(8.0, ancho * b["pct"] / tope), self.FILA - 18), 4, 4)
            p.fillPath(barra, self._colores[k] if k < len(self._colores) else QtGui.QColor(tema.c("acento")))
            p.setFont(letra)
            p.setPen(texto if suya else tenue)
            p.drawText(QtCore.QRectF(self.width() - self.PCT, y, self.PCT, self.FILA),
                       QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight, _pct(b["pct"]))

    def mouseMoveEvent(self, e):
        k = int(e.position().y() // self.FILA)
        if 0 <= k < len(self._bandas):
            b = self._bandas[k]
            QtWidgets.QToolTip.showText(e.globalPosition().toPoint(), f"<b>{b['banda']}</b>: {_pct(b['pct'])} de la tierra del dominio"
                                        + (" · aquí está la planta" if k == self._planta else ""), self)


class BarraUsos(_Pintado):
    """Los grupos de usos del suelo en una barra al 100 %, del mayor al menor, cada uno con su color."""
    ALTO = 14

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grupos = []
        self.setFixedHeight(self.ALTO)

    def poner(self, grupos):
        self._grupos = sorted((g for g in grupos if g["pct"] > 0), key=lambda g: -g["pct"])
        self.update()

    def _tramos(self):
        total = sum(g["pct"] for g in self._grupos) or 1
        x, salen = 0.0, []
        for g in self._grupos:
            w = self.width() * g["pct"] / total
            salen.append((QtCore.QRectF(x, 0, w, self.ALTO), g))
            x += w
        return salen

    def paintEvent(self, _e):
        if not self._grupos:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        recorte = QtGui.QPainterPath()
        recorte.addRoundedRect(QtCore.QRectF(self.rect()), 7, 7)
        p.setClipPath(recorte)
        separa = QtGui.QPen(QtGui.QColor(tema.c("superficie")), 1.5)
        for r, g in self._tramos():
            p.fillRect(r, QtGui.QColor(g["color"]))
            p.setPen(separa)
            p.drawLine(r.topRight(), r.bottomRight())

    def mouseMoveEvent(self, e):
        g = next((g for r, g in self._tramos() if r.contains(e.position())), None)
        if g is None:
            return
        clases = "".join(f"<br>· {c['nombre']}: {_pct(c['pct'])}" for c in g.get("clases", [])[:8])
        QtWidgets.QToolTip.showText(e.globalPosition().toPoint(), f"<b>{g['nombre']}</b>: {_pct(g['pct'])}{clases}", self)
