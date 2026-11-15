# -*- coding: utf-8 -*-
"""Lo de la página Focos, dibujado (usuario, 2026-11-07, en la línea de la página Planta; 2026-11-08: «imagen del mapa con los focos, y
seguido el botón de configuración del foco; después la lista de focos y un calendario igual que el del viento pero con olores y gases»):

- `PlanoFocos`: los focos con su forma real (superficies, volúmenes y puntos) sobre la ortofoto de la planta (`fuentes.ortofoto`; usuario,
  2026-11-08: «que se vea la imagen satélite y encima los focos») o, sin ella, sobre las huellas de los edificios; con escala y cuántos hay
  de cada modelo; al pasar por un foco, su nombre. Se le puede resaltar uno (el de la lista bajo el ratón).
- `BarrasEmision`: la lista de los focos: cada uno con la emisión de lo elegido (olor o un gas), de mayor a menor, en el color de su modelo.
- `CalendarioEmision`: el calendario del viento (`viento_planta.Calendario`), con cada día pintado por la emisión media de la planta con
  el plan de operación elegido y su perfil de 24 h en pequeño; `FranjaEmision`, las horas del día elegido, con la misma escala de color
  (usuario, 2026-11-08: las barras, con el mismo mapa de color que el calendario).
- `SemanaEmision`: una semana como la de Outlook, para la ventana de la operación (usuario, 2026-11-09): la operación del foco elegido como
  citas y, al lado, toda la planta hora a hora, en la escala del calendario.

Y los del editor de un foco punto (usuario, 2026-11-08: «un menú atractivo y práctico, sin definiciones secundarias»): `PanelEstela`, la
chimenea y los edificios de alrededor en perspectiva, con las 36 direcciones del viento en el suelo y la estela del viento elegido («combinar el
esquema de la chimenea con el radar de edificios, quedando como un panel casi tridimensional»); `OlorGases`, el olor que aporta cada gas, con el
dominante delante. Y `VisorEdificios`, los edificios de la planta en 3D (la página Planta y su editor), con la misma cámara (`_Visor3D`).

`COLORES` son los del plano de la ventana de focos (`focos_mapa`), que los toma de aquí. Este módulo no carga WebEngine."""
import math

from PySide6 import QtCore, QtGui, QtWidgets

from teodors.comun import escalas
from teodors.comun.formato import num as _num
from teodors.gui import tema
from teodors.gui.viento_planta import Calendario, Leyenda

# relleno y borde por modelo, los de la maqueta del plano de focos (2026-10-25)
COLORES = {"superficie": ("#8fb4c6", "#5d8ea6"), "punto": ("#d9822b", "#a14a04"),
           "volumen": ("#b9a6d6", "#7d68a6"),
           "edificio": ("#c9b48a", "#8a7444")}             # el editor de los edificios de la planta (no es un modelo de foco)
MODELOS = ("superficie", "punto", "volumen")                 # su orden en leyendas y franjas


def forma(foco):
    """La forma del foco en UTM: ("poligono", [(x, y), …]) o ("punto", (x, y)); None si no está ubicado. Igual que el plano de focos."""
    u = foco.get("ubicacion") or {}
    m = foco.get("modelo")
    if m == "superficie" and len(u.get("poligono") or []) >= 3:
        return "poligono", [tuple(p) for p in u["poligono"]]
    if u.get("x") is None or u.get("y") is None:
        return None
    if m == "volumen":
        from teodors.operacion import focos as F
        return "poligono", F.planta_volumen(foco)
    return "punto", (u["x"], u["y"])


def cifra_corta(v):
    """Una cifra corta: entera hasta las decenas de miles; luego, en miles («k», con un decimal) o en millones («M», con dos). Por debajo
    de 1 (los g/s de un gas), con dos cifras significativas."""
    if v >= 1e6:
        return f"{_num(v / 1e6, 2)} M"
    if v >= 1e4:
        return f"{_num(v / 1e3, 1)} k"
    if v >= 1 or v <= 0:
        return _num(v, 0 if v >= 10 else 1)
    return _num(v, min(6, 1 - math.floor(math.log10(v))))


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


class PlanoFocos(_Pintado):
    """El plano de la planta: las huellas de sus edificios y, encima, los focos con su forma, del color de su modelo. Encuadra los focos
    con un margen; la escala, abajo a la izquierda."""
    ALTO, MARGEN_M = 210, 18.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.ALTO)
        self._focos, self._huellas, self._resaltado, self._orto = [], [], None, None

    def poner(self, focos=None, huellas=None, ortofoto=None):
        """focos: los de focos.json; huellas: [[(x, y), …]] de los edificios cercanos, en UTM; ortofoto: la info de
        `fuentes.ortofoto` (con «ruta» y «recuadro»). None deja lo que había."""
        if focos is not None:
            self._focos = [(f, forma(f)) for f in focos]
            self._focos = [(f, g) for f, g in self._focos if g is not None]
        if huellas is not None:
            self._huellas = [list(h) for h in huellas]
        if ortofoto is not None:
            img = QtGui.QImage(str(ortofoto["ruta"]))
            self._orto = None if img.isNull() else (img, tuple(ortofoto["recuadro"]), ortofoto.get("credito", ""))
        self.update()

    def con_ortofoto(self):
        return self._orto is not None

    def resaltar(self, id_foco):
        """Resalta ese foco (None: ninguno), con su nombre."""
        if id_foco != self._resaltado:
            self._resaltado = id_foco
            self.update()

    def cuantos(self):
        """{modelo: cuántos focos ubicados hay}."""
        return {m: n for m in MODELOS if (n := sum(1 for f, _ in self._focos if f.get("modelo") == m))}

    def _encuadre(self):
        """(x0, y0, escala px/m, alto en m) del encuadre de los focos, con su margen, en la forma del widget."""
        xs, ys = [], []
        for _, (tipo, g) in self._focos:
            pts = g if tipo == "poligono" else [g]
            xs += [p[0] for p in pts]
            ys += [p[1] for p in pts]
        x0, x1 = min(xs) - self.MARGEN_M, max(xs) + self.MARGEN_M
        y0, y1 = min(ys) - self.MARGEN_M, max(ys) + self.MARGEN_M
        esc = min(self.width() / (x1 - x0), self.ALTO / (y1 - y0))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2                       # centrado
        return cx - self.width() / esc / 2, cy - self.ALTO / esc / 2, esc

    def _a_px(self, x, y, enc):
        x0, y0, esc = enc
        return QtCore.QPointF((x - x0) * esc, self.ALTO - (y - y0) * esc)

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        marco = QtGui.QPainterPath()
        marco.addRoundedRect(QtCore.QRectF(self.rect()), 10, 10)
        p.fillPath(marco, QtGui.QColor(tema.c("fondo")))
        if not self._focos:
            p.setPen(QtGui.QColor(tema.c("tenue")))
            p.drawText(QtCore.QRectF(self.rect()), QtCore.Qt.AlignmentFlag.AlignCenter, "Aún no hay focos ubicados")
            return
        p.setClipPath(marco)
        enc = self._encuadre()
        if self._orto is not None:
            self._pinta_ortofoto(p, enc)
        else:
            self._pinta_plano(p, enc)
        # los focos: primero las superficies, encima los volúmenes y los puntos; sobre la ortofoto, más opacos y con el borde más marcado
        sobre_foto = self._orto is not None
        orden = {"superficie": 0, "volumen": 1, "punto": 2}
        for f, (tipo, g) in sorted(self._focos, key=lambda t: orden.get(t[0].get("modelo"), 3)):
            relleno, borde = COLORES.get(f.get("modelo"), ("#999999", "#666666"))
            c = QtGui.QColor(relleno)
            c.setAlpha(225 if sobre_foto else 210)
            p.setBrush(c)
            p.setPen(QtGui.QPen(QtGui.QColor("#ffffff") if sobre_foto else QtGui.QColor(borde), 1.4 if sobre_foto else 1.6))
            if tipo == "poligono":
                p.drawPolygon(QtGui.QPolygonF([self._a_px(x, y, enc) for x, y in g]))
            else:
                p.drawEllipse(self._a_px(*g, enc), 5.5, 5.5)
        self._pinta_resaltado(p, enc)
        self._pinta_cuantos(p)
        self._pinta_escala(p, enc)

    def _pinta_ortofoto(self, p, enc):
        """La ortofoto, en su recuadro UTM; y su crédito, abajo a la derecha."""
        img, (x0, y0, x1, y1), credito = self._orto
        p.save()
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(QtCore.QRectF(self._a_px(x0, y1, enc), self._a_px(x1, y0, enc)), img)
        p.restore()
        if credito:
            p.setFont(self._letra(9))
            fm = p.fontMetrics()
            texto = fm.elidedText(credito, QtCore.Qt.TextElideMode.ElideRight, int(self.width() * 0.55))
            w = fm.horizontalAdvance(texto) + 10
            caja = QtCore.QRectF(self.width() - w - 6, self.ALTO - 20, w, 15)
            fondo = QtGui.QColor(tema.c("superficie"))
            fondo.setAlpha(200)
            camino = QtGui.QPainterPath()
            camino.addRoundedRect(caja, 7, 7)
            p.fillPath(camino, fondo)
            p.setPen(QtGui.QColor(tema.c("tenue")))
            p.drawText(caja, QtCore.Qt.AlignmentFlag.AlignCenter, texto)

    def _pinta_plano(self, p, enc):
        """Sin ortofoto: una rejilla tenue cada 10 m, como en un plano, y las huellas de los edificios."""
        rejilla = QtGui.QColor(tema.c("borde"))
        p.setPen(QtGui.QPen(rejilla, 0.6))
        x0, y0, esc = enc
        paso = 10.0
        xm = math.floor(x0 / paso) * paso
        while xm < x0 + self.width() / esc:
            q = self._a_px(xm, y0, enc)
            p.drawLine(QtCore.QPointF(q.x(), 0), QtCore.QPointF(q.x(), self.ALTO))
            xm += paso
        ym = math.floor(y0 / paso) * paso
        while ym < y0 + self.ALTO / esc:
            q = self._a_px(x0, ym, enc)
            p.drawLine(QtCore.QPointF(0, q.y()), QtCore.QPointF(self.width(), q.y()))
            ym += paso
        # los edificios
        p.setPen(QtGui.QPen(QtGui.QColor(tema.c("borde_fuerte")), 1))
        p.setBrush(QtGui.QColor(tema.c("elevada")))
        for h in self._huellas:
            p.drawPolygon(QtGui.QPolygonF([self._a_px(x, y, enc) for x, y in h]))

    def _pinta_escala(self, p, enc):
        """La escala, abajo a la izquierda, en una pastilla (sobre la ortofoto también se lee)."""
        esc = enc[2]
        metros = 20 if self.width() / esc > 60 else 10
        largo = metros * esc
        p.setFont(self._letra(11, True))
        ancho = largo + p.fontMetrics().horizontalAdvance(f"{metros} m") + 24
        caja = QtGui.QPainterPath()
        caja.addRoundedRect(QtCore.QRectF(6, self.ALTO - 26, ancho, 20), 10, 10)
        fondo = QtGui.QColor(tema.c("superficie"))
        fondo.setAlpha(210)
        p.fillPath(caja, fondo)
        x, y = 14, self.ALTO - 13
        p.setPen(QtGui.QPen(QtGui.QColor(tema.c("texto")), 2, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.FlatCap))
        p.drawLine(QtCore.QPointF(x, y), QtCore.QPointF(x + largo, y))
        for xx in (x, x + largo):
            p.drawLine(QtCore.QPointF(xx, y - 4), QtCore.QPointF(xx, y + 1))
        p.drawText(QtCore.QPointF(x + largo + 6, y + 4), f"{metros} m")

    def _pinta_resaltado(self, p, enc):
        """El foco resaltado: su contorno, grueso y del color del texto, y su nombre en una etiqueta."""
        f, g = next(((f, g) for f, g in self._focos if f.get("id") == self._resaltado), (None, None))
        if f is None:
            return
        tipo, g = g
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.setPen(QtGui.QPen(QtGui.QColor(tema.c("texto")), 2.6))
        if tipo == "poligono":
            pol = QtGui.QPolygonF([self._a_px(x, y, enc) for x, y in g])
            p.drawPolygon(pol)
            centro, arriba = pol.boundingRect().center(), pol.boundingRect().top()
        else:
            centro = self._a_px(*g, enc)
            p.drawEllipse(centro, 8.0, 8.0)
            arriba = centro.y() - 8
        p.setFont(self._letra(11, True))
        fm = p.fontMetrics()
        nombre = fm.elidedText(f.get("nombre") or str(f.get("id")), QtCore.Qt.TextElideMode.ElideRight, self.width() - 30)
        w, h = fm.horizontalAdvance(nombre) + 14, 20
        x = min(max(centro.x() - w / 2, 4), self.width() - w - 4)
        y = arriba - h - 4 if arriba - h - 4 > 34 else arriba + 4          # sin tapar la pastilla de arriba
        caja = QtGui.QPainterPath()
        caja.addRoundedRect(QtCore.QRectF(x, y, w, h), 6, 6)
        p.fillPath(caja, QtGui.QColor(tema.c("texto")))
        p.setPen(QtGui.QColor(tema.c("superficie")))
        p.drawText(QtCore.QRectF(x, y, w, h), QtCore.Qt.AlignmentFlag.AlignCenter, nombre)

    def _pinta_cuantos(self, p):
        """Arriba a la izquierda, en una pastilla: cuántos focos hay de cada modelo, con su color (la leyenda del plano y de la lista)."""
        textos = [(m, f"{n} {m}") for m, n in self.cuantos().items()]
        p.setFont(self._letra(11, True))
        fm = p.fontMetrics()
        ancho = sum(fm.horizontalAdvance(t) + 24 for _, t in textos) + 4
        caja = QtGui.QPainterPath()
        caja.addRoundedRect(QtCore.QRectF(8, 8, ancho, 22), 11, 11)
        fondo = QtGui.QColor(tema.c("superficie"))
        fondo.setAlpha(225)
        p.fillPath(caja, fondo)
        x = 16.0
        for m, t in textos:
            relleno, borde = COLORES[m]
            p.setBrush(QtGui.QColor(relleno))
            p.setPen(QtGui.QPen(QtGui.QColor(borde), 1.2))
            p.drawRoundedRect(QtCore.QRectF(x, 14, 10, 10), 3, 3)
            p.setPen(QtGui.QColor(tema.c("texto")))
            p.drawText(QtCore.QRectF(x + 14, 8, fm.horizontalAdvance(t) + 4, 22), QtCore.Qt.AlignmentFlag.AlignVCenter, t)
            x += fm.horizontalAdvance(t) + 24

    def foco_en(self, pos):
        """El foco bajo ese punto del widget (el de encima, si se tapan), o None."""
        if not self._focos:
            return None
        enc = self._encuadre()
        for f, (tipo, g) in sorted(self._focos, key=lambda t: -{"superficie": 0, "volumen": 1, "punto": 2}.get(t[0].get("modelo"), 3)):
            if tipo == "poligono":
                if QtGui.QPolygonF([self._a_px(x, y, enc) for x, y in g]).containsPoint(pos, QtCore.Qt.FillRule.OddEvenFill):
                    return f
            elif QtCore.QLineF(self._a_px(*g, enc), pos).length() <= 8:
                return f
        return None

    def mouseMoveEvent(self, e):
        f = self.foco_en(e.position())
        if f is None:
            QtWidgets.QToolTip.hideText()
            return
        QtWidgets.QToolTip.showText(e.globalPosition().toPoint(), f"<b>{f.get('nombre', f.get('id'))}</b><br>{f.get('modelo', '')}", self)


class BarrasEmision(_Pintado):
    """La lista de los focos: una fila por foco con un cuadrito del color de su modelo, su nombre, una barra del largo de su emisión y la
    cifra, de mayor a menor. Avisa del foco bajo el ratón (`sobre`, su id o None), para resaltarlo en el plano."""
    sobre = QtCore.Signal(object)
    FILA, NOMBRE, VALOR = 24, 156, 58

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filas, self._unidad, self._sobre = [], "ou_E/s", None

    def poner(self, filas, unidad="ou_E/s"):
        """filas: [(id, nombre, modelo, emisión)]; los que no tienen dato, al final y sin barra."""
        self._filas = sorted(filas, key=lambda t: -(t[3] if t[3] is not None else -1))
        self._unidad = unidad
        self.setFixedHeight(self.FILA * len(self._filas))
        self.update()

    def filas(self):
        return self._filas

    def paintEvent(self, _e):
        if not self._filas:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        tope = max((t[3] for t in self._filas if t[3]), default=1) or 1
        ancho = self.width() - self.NOMBRE - self.VALOR - 6
        texto, tenue = QtGui.QColor(tema.c("texto")), QtGui.QColor(tema.c("tenue"))
        for k, (id_foco, nombre, modelo, v) in enumerate(self._filas):
            y = k * self.FILA
            if id_foco == self._sobre:
                marco = QtGui.QPainterPath()
                marco.addRoundedRect(QtCore.QRectF(0, y + 1, self.width(), self.FILA - 2), 6, 6)
                p.fillPath(marco, QtGui.QColor(tema.c("hover")))
            relleno, borde = COLORES.get(modelo, ("#999999", "#666666"))
            p.setBrush(QtGui.QColor(relleno))
            p.setPen(QtGui.QPen(QtGui.QColor(borde), 1.2))
            p.drawRoundedRect(QtCore.QRectF(4, y + self.FILA / 2 - 5, 10, 10), 3, 3)
            p.setFont(self._letra(12))
            p.setPen(texto)
            fm = p.fontMetrics()
            p.drawText(QtCore.QRectF(20, y, self.NOMBRE - 26, self.FILA), QtCore.Qt.AlignmentFlag.AlignVCenter,
                       fm.elidedText(nombre, QtCore.Qt.TextElideMode.ElideRight, self.NOMBRE - 28))
            pista = QtGui.QPainterPath()
            pista.addRoundedRect(QtCore.QRectF(self.NOMBRE, y + 8, ancho, self.FILA - 16), 4, 4)
            p.fillPath(pista, QtGui.QColor(tema.c("elevada")))
            if v:
                barra = QtGui.QPainterPath()
                barra.addRoundedRect(QtCore.QRectF(self.NOMBRE, y + 8, max(6.0, ancho * v / tope), self.FILA - 16), 4, 4)
                p.fillPath(barra, QtGui.QColor(relleno))
            p.setPen(texto if v else tenue)
            p.setFont(self._letra(12, bool(v)))
            p.drawText(QtCore.QRectF(self.width() - self.VALOR, y, self.VALOR, self.FILA),
                       QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight, cifra_corta(v) if v else "—")

    def _fila(self, pos):
        k = int(pos.y() // self.FILA)
        return self._filas[k] if 0 <= k < len(self._filas) and pos.y() >= 0 else None

    def _marcar(self, id_foco):
        if id_foco != self._sobre:
            self._sobre = id_foco
            self.sobre.emit(id_foco)
            self.update()

    def mouseMoveEvent(self, e):
        fila = self._fila(e.position())
        self._marcar(fila[0] if fila else None)
        if fila:
            _, nombre, modelo, v = fila
            QtWidgets.QToolTip.showText(e.globalPosition().toPoint(), f"<b>{nombre}</b> · {modelo}<br>"
                                        + (f"{_num(v, 0 if v >= 10 else 3)} {self._unidad}" if v else "sin dato"), self)

    def leaveEvent(self, _e):
        self._marcar(None)


# ── la emisión de la planta día a día ────────────────────────────────────────────────────────────────────────────
def color_emision(escala, t, alfa=255):
    """El color de t (de 0 a 1, la parte de la emisión máxima) en la escala de la configuración: `escala_olor` o `escala_gases`."""
    lut = escalas.lut(tema.preferencia(escala))
    r, g, b = (lut[int(min(max(t, 0.0), 1.0) * 255)] * 255).round().astype(int)
    return QtGui.QColor(int(r), int(g), int(b), alfa)


def _hora(h):
    return f"{h:02d}:00"


class CalendarioEmision(Calendario):
    """El calendario de la emisión: cada día pintado por la emisión media de la planta con el plan elegido (de 0 a la máxima, la de todos
    los focos al 100 %) y su perfil de 24 h en pequeño, abajo, como el del viento con su flecha. Lo de cada día sale de
    `operacion.planes.emision_dias`."""

    def __init__(self, parent=None):
        self._escala, self._tope, self._unidad = "escala_olor", 1.0, "ou_E/s"
        super().__init__(Leyenda("Emisión media del día, ou_E/s", self._color, self._marcas), parent)

    def poner_escala(self, escala, tope, unidad):
        """escala: «escala_olor» o «escala_gases»; tope: la emisión máxima de la planta; unidad: la de la emisión."""
        self._escala, self._tope, self._unidad = escala, tope or 1.0, unidad
        self.leyenda.poner(f"Emisión media del día, {unidad}")
        self.rejilla.update()

    def _color(self, t):
        return color_emision(self._escala, t)

    def _marcas(self):
        return [(0.0, "0"), (0.5, cifra_corta(self._tope / 2)), (1.0, cifra_corta(self._tope))]

    def color_dia(self, info):
        return self._color(info["media"] / self._tope)

    def dibujar_dia(self, p, r, info, color):
        """El perfil del día: 24 barritas pegadas, abajo, del alto de cada hora sobre la máxima."""
        horas = info.get("horas") or []
        if not horas:
            return
        x0, ancho = r.left() + 5, r.width() - 10
        base, alto = r.bottom() - 3, r.height() * 0.36
        camino = QtGui.QPainterPath(QtCore.QPointF(x0, base))
        paso = ancho / len(horas)
        for k, v in enumerate(horas):
            y = base - alto * min(v / self._tope, 1.0)
            camino.lineTo(x0 + k * paso, y)
            camino.lineTo(x0 + (k + 1) * paso, y)
        camino.lineTo(x0 + ancho, base)
        camino.closeSubpath()
        c = QtGui.QColor(color)
        c.setAlpha(150)
        p.fillPath(camino, c)

    def texto_dia(self, info):
        if not info["media"]:
            return "Sin emisión"
        horas = info.get("horas") or [info["media"]]
        alta = max(range(len(horas)), key=lambda k: horas[k])
        pico = ("igual todo el día" if max(horas) - min(horas) <= 1e-9 * max(horas)
                else f"máxima {cifra_corta(horas[alta])} a las {_hora(alta)}")
        return f"Media {cifra_corta(info['media'])} {self._unidad} · {pico}"


class FranjaEmision(_Pintado):
    """Las 24 horas del día elegido del calendario de emisión (hora oficial): una barra por hora, de su alto y su color en la escala del
    calendario (de 0 a la emisión máxima de la planta), como la del viento; al pasar por encima, cuánto pone cada modelo de foco."""
    ABAJO = 16

    def __init__(self, parent=None):
        super().__init__(parent)
        self._modelos, self._tope, self._unidad, self._escala = {}, 1.0, "ou_E/s", "escala_olor"
        self.setFixedHeight(72)

    def poner(self, modelos, tope, unidad, escala="escala_olor"):
        """modelos: {modelo: [24]}, lo de `emision_dias`; tope: la emisión máxima de la planta; escala: la del calendario."""
        self._modelos, self._tope, self._unidad, self._escala = modelos or {}, tope or 1.0, unidad, escala
        self.update()

    def horas(self):
        """La emisión de toda la planta en cada hora."""
        return [sum((self._modelos.get(m) or [0.0] * 24)[k] for m in self._modelos) for k in range(24)]

    def _columna(self):
        return self.width() / 24

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w = self._columna()
        alto = self.height() - self.ABAJO - 2
        base = 2 + alto
        tenue = QtGui.QColor(tema.c("tenue"))
        p.setPen(QtGui.QPen(QtGui.QColor(tema.c("borde")), 1))
        p.drawLine(QtCore.QPointF(0, base + 0.5), QtCore.QPointF(self.width(), base + 0.5))
        p.setFont(self._letra(10))
        for k, v in enumerate(self.horas() if self._modelos else []):
            x = k * w
            if v > 0:
                t = min(v / self._tope, 1.0)
                h = max(2.0, alto * t)
                barra = QtGui.QPainterPath()
                barra.addRoundedRect(QtCore.QRectF(x + w * 0.18, base - h, w * 0.64, h), 2, 2)
                p.fillPath(barra, color_emision(self._escala, t))
        for k in range(24):
            x = k * w
            if k % 3 == 0:
                p.setPen(tenue)
                p.drawText(QtCore.QRectF(x - 6, base + 2, w + 12, self.ABAJO - 2), QtCore.Qt.AlignmentFlag.AlignCenter, f"{k}")

    def mouseMoveEvent(self, e):
        k = int(e.position().x() // self._columna())
        if not 0 <= k < 24 or not self._modelos:
            QtWidgets.QToolTip.hideText()
            return
        partes = [(m, self._modelos[m][k]) for m in MODELOS if m in self._modelos]
        total = sum(v for _, v in partes)
        texto = (f"<b>{_hora(k)} – {_hora(k + 1) if k < 23 else '24:00'}</b> · {cifra_corta(total) if total else '0'} {self._unidad}"
                 + "".join(f"<br><span style='color:{COLORES[m][1]}'>■</span> {m}: {cifra_corta(v)}" for m, v in partes if v))
        QtWidgets.QToolTip.showText(e.globalPosition().toPoint(), texto, self)


DIAS_CORTOS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")


class SemanaEmision(_Pintado):
    """Una semana como la de un calendario de Outlook (usuario, 2026-11-09: «un calendario tipo Outlook con las emisiones de ese foco y las
    del resto»): los 7 días en columnas y las 24 horas hacia abajo (hora oficial). En cada día, a la izquierda, la operación del foco elegido
    como citas: las horas seguidas con el mismo % de su emisión, un bloque del color de su modelo, más lleno cuanto más emite, con su % y sus
    horas (apagado, nada); a la derecha, toda la planta hora a hora (de 0 a la emisión máxima, la de todos los focos al 100 %), con la parte
    del foco en su color. Los días con el perfil que se edita, recuadrados; hoy, con su número resaltado. Un clic en un día lo elige
    (`dia_pulsado`)."""
    dia_pulsado = QtCore.Signal(str, object)     # "aaaa-mm-dd", modificadores del teclado
    IZQ, ARRIBA, ABAJO, HUECO = 40, 46, 26, 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dias, self._foco, self._planta, self._factores = [], [], [], []
        self._nombre, self._modelo, self._tope, self._unidad, self._marcados = "", "superficie", 1.0, "ou_E/s", set()
        self._escala, self._sobre = "escala_olor", None
        self.setMinimumSize(420, 24 * 15 + self.ARRIBA + self.ABAJO)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def poner(self, dias, foco, planta, factores, nombre, modelo, tope, unidad, marcados=(), escala="escala_olor"):
        """dias: las 7 fechas (date), de lunes a domingo; foco y planta: [[24 horas] por día] de lo que emiten el foco y toda la planta, en
        `unidad`; factores: [[24] por día], el % de la emisión del foco (de 0 a 1), su operación; tope: la emisión máxima de la planta;
        marcados: las fechas con el perfil que se edita; escala: la del calendario («escala_olor» o «escala_gases»)."""
        self._dias, self._foco, self._planta, self._factores = list(dias), foco, planta, factores
        self._nombre, self._modelo, self._tope, self._unidad = nombre, modelo, tope or 1.0, unidad
        self._marcados, self._escala = set(marcados), escala
        self.update()

    def bloques(self, k):
        """Las citas del foco el día k: [(hora de inicio, hora de fin, factor)], las horas seguidas con el mismo factor; sin las apagadas."""
        fs = self._factores[k] if k < len(self._factores) else []
        salida, h0 = [], 0
        for h in range(1, len(fs) + 1):
            if h == len(fs) or abs(fs[h] - fs[h0]) > 1e-9:
                if fs[h0] > 1e-9:
                    salida.append((h0, h, fs[h0]))
                h0 = h
        return salida

    def _geo(self):
        """(ancho de un día, alto de una hora, y de la primera hora)."""
        w = (self.width() - self.IZQ - 6 * self.HUECO) / 7
        return w, (self.height() - self.ARRIBA - self.ABAJO) / 24, self.ARRIBA

    def _en(self, pos):
        """(día, hora) bajo el ratón, o None."""
        w, hh, y0 = self._geo()
        x = pos.x() - self.IZQ
        k, h = int(x // (w + self.HUECO)), int((pos.y() - y0) // hh)
        if not self._dias or not 0 <= k < 7 or x - k * (w + self.HUECO) > w or not 0 <= h < 24:
            return None
        return k, h

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w, hh, y0 = self._geo()
        tenue, borde = QtGui.QColor(tema.c("tenue")), QtGui.QColor(tema.c("borde"))
        relleno, linea = QtGui.QColor(COLORES.get(self._modelo, COLORES["superficie"])[0]), QtGui.QColor(
            COLORES.get(self._modelo, COLORES["superficie"])[1])
        y1 = y0 + 24 * hh
        # las horas, a la izquierda, y sus líneas: cada 3 h, más marcadas cada 6
        p.setFont(self._letra(10))
        for h in range(0, 25, 3):
            y = y0 + h * hh
            p.setPen(tenue)
            p.drawText(QtCore.QRectF(0, y - 7, self.IZQ - 8, 14), QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter,
                       f"{h:02d}:00" if h < 24 else "24:00")
        hoy = QtCore.QDate.currentDate().toPython()
        for k, d in enumerate(self._dias):
            x = self.IZQ + k * (w + self.HUECO)
            col = QtCore.QRectF(x, y0, w, 24 * hh)
            marcado = d in self._marcados
            caja = QtGui.QPainterPath()
            caja.addRoundedRect(col, 8, 8)
            p.fillPath(caja, QtGui.QColor(tema.c("tinte" if marcado else "elevada")))
            p.setPen(QtGui.QPen(borde, 1, QtCore.Qt.PenStyle.DotLine))
            for h in range(3, 24, 3):
                y = y0 + h * hh
                p.drawLine(QtCore.QPointF(x + 4, y), QtCore.QPointF(x + w - 4, y))
            # la cabecera del día: su nombre y su número (hoy, en una pastilla del acento)
            p.setPen(tenue)
            p.setFont(self._letra(10, True))
            p.drawText(QtCore.QRectF(x, 2, w, 16), QtCore.Qt.AlignmentFlag.AlignCenter, DIAS_CORTOS[d.weekday()].upper())
            num = QtCore.QRectF(x + w / 2 - 14, 19, 28, 22)
            if d == hoy:
                pastilla = QtGui.QPainterPath()
                pastilla.addRoundedRect(num, 11, 11)
                p.fillPath(pastilla, QtGui.QColor(tema.c("acento")))
                p.setPen(QtGui.QColor(tema.c("sobre_acento")))
            else:
                p.setPen(QtGui.QColor(tema.c("texto")))
            p.setFont(self._letra(15, True))
            p.drawText(num, QtCore.Qt.AlignmentFlag.AlignCenter, str(d.day))
            # a la derecha, toda la planta hora a hora, de su largo y su color en la escala del calendario (como las barras de la página
            # Focos), con la parte del foco en su color, delante
            carril = QtCore.QRectF(x + w * 0.58, y0, w * 0.42 - 5, 24 * hh)
            for h in range(24):
                total = self._planta[k][h] if k < len(self._planta) else 0.0
                suyo = self._foco[k][h] if k < len(self._foco) else 0.0
                if total <= 0:
                    continue
                y, alto = y0 + h * hh + 1, max(hh - 2, 1.0)
                t = min(total / self._tope, 1.0)
                largo = max(carril.width() * t, 2.0)
                barra = QtGui.QPainterPath()
                barra.addRoundedRect(QtCore.QRectF(carril.left(), y, largo, alto), 2, 2)
                p.fillPath(barra, color_emision(self._escala, t, 190))
                if suyo > 0:
                    p.fillRect(QtCore.QRectF(carril.left(), y, max(largo * suyo / total, 3.0), alto), linea)
            # a la izquierda, la operación del foco: sus citas
            for h0, h1, f in self.bloques(k):
                r = QtCore.QRectF(x + 4, y0 + h0 * hh + 1.5, w * 0.58 - 8, (h1 - h0) * hh - 3)
                cita = QtGui.QPainterPath()
                cita.addRoundedRect(r, 5, 5)
                alfa = 0.3 + 0.65 * min(f, 1.0)
                c = QtGui.QColor(relleno)
                c.setAlphaF(alfa)
                p.fillPath(cita, c)
                p.fillRect(QtCore.QRectF(r.left(), r.top() + 2, 3.5, r.height() - 4), linea)
                if r.height() >= 16:
                    visto = _mezcla(tema.c("tinte" if marcado else "elevada"), relleno, alfa)        # el texto, el que se lee encima
                    p.setPen(QtGui.QColor("#16201c" if visto.lightnessF() > 0.55 else "#f2f5f3"))
                    p.setFont(self._letra(11, True))
                    p.drawText(r.adjusted(8, 2, -2, 0), QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop,
                               f"{round(f * 100)} %")
                    if r.height() >= 32:
                        p.setFont(self._letra(10))
                        p.drawText(r.adjusted(8, 17, -2, 0), QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop,
                                   f"{h0}–{h1} h")
            if marcado:
                p.setPen(QtGui.QPen(QtGui.QColor(tema.c("acento")), 2))
                p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(col.adjusted(1, 1, -1, -1), 8, 8)
            if self._sobre is not None and self._sobre[0] == k:
                h = self._sobre[1]
                p.setPen(QtGui.QPen(QtGui.QColor(tema.c("texto")), 1))
                p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(QtCore.QRectF(x + 1, y0 + h * hh, w - 2, hh), 3, 3)
        # la leyenda, abajo
        p.setFont(self._letra(10))
        x = self.IZQ
        for muestra, texto in ((relleno, f"{self._nombre}: su operación (% de su emisión)"),
                               (color_emision(self._escala, 0.85, 190), f"toda la planta, {self._unidad} (delante, la parte del foco)")):
            p.fillRect(QtCore.QRectF(x, y1 + 9, 12, 9), muestra)
            p.setPen(tenue)
            ancho = p.fontMetrics().horizontalAdvance(texto)
            p.drawText(QtCore.QRectF(x + 17, y1 + 5, ancho + 4, 16), QtCore.Qt.AlignmentFlag.AlignVCenter, texto)
            x += ancho + 40

    def mouseMoveEvent(self, e):
        donde = self._en(e.position())
        if donde != self._sobre:
            self._sobre = donde
            self.update()
        if donde is None:
            QtWidgets.QToolTip.hideText()
            return
        k, h = donde
        d = self._dias[k]
        f = self._factores[k][h] if k < len(self._factores) else 0.0
        suyo, total = self._foco[k][h], self._planta[k][h]
        texto = (f"<b>{DIAS_CORTOS[d.weekday()].capitalize()} {d.day}/{d.month} · {h}–{h + 1} h</b><br>"
                 f"<span style='color:{COLORES.get(self._modelo, COLORES['superficie'])[1]}'>■</span> {self._nombre}: "
                 + (f"{round(f * 100)} % de su emisión, {cifra_corta(suyo)} {self._unidad}" if f > 0 else "apagado")
                 + f"<br>Toda la planta: {cifra_corta(total)} {self._unidad}"
                 + (f" (el foco, {round(100 * suyo / total)} %)" if total > 0 and suyo > 0 else ""))
        QtWidgets.QToolTip.showText(e.globalPosition().toPoint(), texto, self)

    def leaveEvent(self, _e):
        self._sobre = None
        self.update()

    def mouseReleaseEvent(self, e):
        donde = self._en(e.position())
        if donde is not None:
            self.dia_pulsado.emit(self._dias[donde[0]].isoformat(), e.modifiers())


# ── el editor de focos: la chimenea de un foco punto ────────────────────────────────────────────────────────────────
def _mezcla(a, b, t, alfa=255):
    """El color entre a (t = 0) y b (t = 1)."""
    a, b = QtGui.QColor(a), QtGui.QColor(b)
    t = min(max(t, 0.0), 1.0)
    return QtGui.QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                        round(a.blue() + (b.blue() - a.blue()) * t), alfa)


def _envolvente(puntos):
    """La envolvente convexa de unos puntos (x, y), en sentido antihorario."""
    pts = sorted(set(puntos))
    if len(pts) <= 2:
        return pts

    def giro(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    abajo, arriba = [], []
    for q in pts:
        while len(abajo) >= 2 and giro(abajo[-2], abajo[-1], q) <= 0:
            abajo.pop()
        abajo.append(q)
    for q in reversed(pts):
        while len(arriba) >= 2 and giro(arriba[-2], arriba[-1], q) <= 0:
            arriba.pop()
        arriba.append(q)
    return abajo[:-1] + arriba[:-1]


def _antihorario(pts):
    area = sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))
    return list(pts) if area <= 0 else list(reversed(pts))       # la suma de arriba es −2·área: positiva, horario


class _Visor3D(_Pintado):
    """Lo común de los visores 3D dibujados (la chimenea con sus edificios, `PanelEstela`; los edificios de la planta, `VisorEdificios`): una
    cámara que mira al centro desde un azimut y una elevación, con acercamiento y desplazamiento. Arrastrar con el botón izquierdo gira (a los
    lados) e inclina (arriba y abajo); con el derecho, el central o Mayúsculas, desplaza; la rueda acerca dejando quieto lo que hay bajo el
    ratón; doble clic, la vista de partida. Las alturas van ×`EXAGERA` frente al suelo, con su escala abajo a la izquierda. Cada visor pone su
    encuadre (`_geo`, con `_encuadre`)."""
    ELEV = 34.0                            # grados sobre el horizonte de la vista de partida
    ELEV_MIN, ELEV_MAX = 10.0, 85.0
    ZOOM_MIN, ZOOM_MAX = 0.5, 5.0
    EXAGERA = 2.0                          # las alturas, frente a las distancias en el suelo

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        self._arrastre = None
        self.vista_inicial()

    def vista_inicial(self):
        """El norte al fondo, a `ELEV` sobre el horizonte, sin acercar ni mover."""
        self._az, self._elev, self._zoom, self._mueve = 0.0, self.ELEV, 1.0, QtCore.QPointF(0.0, 0.0)
        self.update()

    def vista(self):
        """(azimut, elevación, acercamiento, desplazamiento en px) de la vista."""
        return self._az, self._elev, self._zoom, (self._mueve.x(), self._mueve.y())

    def estado_vista(self):
        """Cómo se está mirando, para seguir igual en otro visor (la ficha rehecha)."""
        return {"vista": self.vista()}

    def poner_vista(self, estado):
        az, elev, zoom, (dx, dy) = estado["vista"]
        self._az, self._elev, self._zoom, self._mueve = az, elev, zoom, QtCore.QPointF(dx, dy)
        self.update()

    # ── proyección ───────────────────────────────────────────────────────────────────────────────────────────
    def _geo(self):
        raise NotImplementedError

    def _encuadre(self, R, Rt, zmax):
        """(centro x, centro y, escala px/m, sen y cos de la elevación, R, Rt): el suelo de radio `Rt` y lo más alto, `zmax`, caben con la
        elevación de partida (girar o inclinar no cambia el tamaño), centrados en el alto que sobre."""
        W, H = self.width(), self.height()
        e0 = math.radians(self.ELEV)
        alto = 2 * Rt * math.sin(e0) + zmax * math.cos(e0) * self.EXAGERA
        s0 = min((W - 40) / (2 * Rt), (H - 78) / alto)
        sobra = max(0.0, H - 78 - s0 * alto)
        cy0 = H - 30 - sobra / 2 - Rt * s0 * math.sin(e0)
        el = math.radians(self._elev)
        return (W / 2 + self._mueve.x(), cy0 + self._mueve.y(), s0 * self._zoom, math.sin(el), math.cos(el), R, Rt)

    def _p(self, g, x, y, z=0.0):
        cx, cy, s, sinE, cosE = g[:5]
        a = math.radians(self._az)
        u = x * math.cos(a) - y * math.sin(a)
        v = x * math.sin(a) + y * math.cos(a)
        return QtCore.QPointF(cx + s * u, cy - s * (v * sinE + z * self.EXAGERA * cosE))

    def _prof(self, x, y):
        a = math.radians(self._az)
        return x * math.sin(a) + y * math.cos(a)

    def _al_suelo(self, g, px, py):
        cx, cy, s, sinE = g[:4]
        u, v = (px - cx) / s, (cy - py) / (s * sinE)
        a = math.radians(self._az)
        return u * math.cos(a) + v * math.sin(a), -u * math.sin(a) + v * math.cos(a)

    def _anillo(self, g, r, n=72):
        return QtGui.QPolygonF([self._p(g, r * math.sin(2 * math.pi * k / n), r * math.cos(2 * math.pi * k / n)) for k in range(n)])

    # ── dibujo ───────────────────────────────────────────────────────────────────────────────────────────────
    def _suelo(self, p, g, anillos):
        """El disco del suelo, con los anillos de distancia que quepan."""
        R = g[5]
        p.setPen(QtGui.QPen(QtGui.QColor(tema.c("borde")), 1.0))
        p.setBrush(_mezcla(tema.c("fondo"), tema.c("elevada"), 0.8))
        p.drawPolygon(self._anillo(g, R))
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.setFont(self._letra(10))
        for d in anillos:
            if d < R * 0.92 and d * g[2] >= 20:
                p.setPen(QtGui.QPen(QtGui.QColor(tema.c("borde_fuerte")), 0.8, QtCore.Qt.PenStyle.DotLine))
                p.drawPolygon(self._anillo(g, d))
                p.setPen(QtGui.QColor(tema.c("tenue")))
                p.drawText(self._p(g, d * 0.71, -d * 0.71) + QtCore.QPointF(3, 12), f"{d} m")

    def _cardinales(self, p, g, r):
        p.setFont(self._letra(11, True))
        p.setPen(QtGui.QColor(tema.c("texto")))
        for letra, ang in (("N", 0), ("E", 90), ("S", 180), ("O", 270)):
            t = math.radians(ang)
            c = self._p(g, r * math.sin(t), r * math.cos(t))
            p.drawText(QtCore.QRectF(c.x() - 10, c.y() - 8, 20, 16), QtCore.Qt.AlignmentFlag.AlignCenter, letra)

    def _extruir(self, p, g, pts, h, base):
        """Un edificio de planta `pts` (antihoraria, relativa al centro) y altura `h`: las caras que se ven, con luz del noroeste, y el techo
        (que devuelve)."""
        a = math.radians(self._az)
        caras = []
        for i in range(len(pts)):
            (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % len(pts)]
            nx, ny = y2 - y1, -(x2 - x1)                                   # hacia fuera (antihorario)
            if nx * math.sin(a) + ny * math.cos(a) >= 0:                  # de espaldas a quien mira
                continue
            caras.append((self._prof((x1 + x2) / 2, (y1 + y2) / 2), x1, y1, x2, y2, nx, ny))
        borde = QtGui.QColor(tema.c("borde_fuerte"))
        for _, x1, y1, x2, y2, nx, ny in sorted(caras, reverse=True):
            luz = (-0.55 * nx + 0.83 * ny) / (math.hypot(nx, ny) or 1.0)     # luz del noroeste
            p.setBrush(base.darker(round(150 - 30 * luz)))
            p.setPen(QtGui.QPen(borde, 0.7))
            p.drawPolygon(QtGui.QPolygonF([self._p(g, x1, y1), self._p(g, x2, y2), self._p(g, x2, y2, h), self._p(g, x1, y1, h)]))
        techo = QtGui.QPolygonF([self._p(g, x, y, h) for x, y in pts])
        p.setBrush(base.lighter(112))
        p.setPen(QtGui.QPen(borde, 0.9))
        p.drawPolygon(techo)
        return techo

    def _cifra_techo(self, p, techo, h):
        caja = techo.boundingRect()
        if caja.width() > 26 and caja.height() > 10:
            p.setFont(self._letra(10, True))
            p.setPen(QtGui.QColor("#1b1f22"))
            p.drawText(caja, QtCore.Qt.AlignmentFlag.AlignCenter, f"{_num(h, 0)} m")

    def _escala(self, p, g):
        """La escala de las alturas, abajo a la izquierda: 10 m (las alturas van ×`EXAGERA` frente al suelo)."""
        abajo = QtCore.QPointF(16, self.height() - 22)
        largo = 10.0 * g[2] * self.EXAGERA * g[4]
        p.setPen(QtGui.QPen(QtGui.QColor(tema.c("tenue")), 1.2))
        p.drawLine(abajo, abajo - QtCore.QPointF(0, largo))
        for y in (0.0, largo):
            p.drawLine(abajo - QtCore.QPointF(3, y), abajo - QtCore.QPointF(-3, y))
        p.setFont(self._letra(10))
        p.drawText(abajo - QtCore.QPointF(-6, largo / 2 - 4), "10 m")

    # ── ratón ────────────────────────────────────────────────────────────────────────────────────────────────
    def _empezar_arrastre(self, e):
        mover = e.button() != QtCore.Qt.MouseButton.LeftButton or bool(e.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier)
        self._arrastre = ("mover" if mover else "girar", e.position(), self._az, self._elev, QtCore.QPointF(self._mueve))
        self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor if mover else QtCore.Qt.CursorShape.ClosedHandCursor)

    def mousePressEvent(self, e):
        self._empezar_arrastre(e)

    def _arrastrar(self, e):
        """Gira e inclina, o desplaza, si se está arrastrando; True si lo ha hecho."""
        if self._arrastre is None:
            return False
        modo, ini, az0, el0, mueve0 = self._arrastre
        d = e.position() - ini
        if modo == "mover":
            self._mueve = mueve0 + d
        else:
            self._az = (az0 + d.x() * 0.5) % 360.0
            self._elev = min(self.ELEV_MAX, max(self.ELEV_MIN, el0 + d.y() * 0.3))
        self.update()
        return True

    def mouseReleaseEvent(self, _e):
        self._arrastre = None
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)

    def mouseDoubleClickEvent(self, _e):
        self.vista_inicial()

    def wheelEvent(self, e):
        """La rueda acerca o aleja, dejando quieto lo que hay bajo el ratón."""
        z0 = self._zoom
        z1 = min(self.ZOOM_MAX, max(self.ZOOM_MIN, z0 * 1.15 ** (e.angleDelta().y() / 120.0)))
        if z1 == z0:
            return
        g = self._geo()
        base = QtCore.QPointF(g[0], g[1]) - self._mueve                  # el centro sin desplazar
        raton = e.position()
        self._mueve = raton - base - (raton - base - self._mueve) * (z1 / z0)
        self._zoom = z1
        self.update()

    def contextMenuEvent(self, e):
        e.accept()                                                       # el botón derecho mueve: sin menú


class PanelEstela(_Visor3D):
    """La chimenea y los edificios de alrededor en perspectiva (usuario, 2026-11-08: «combinar el esquema de la chimenea con el radar de
    edificios, quedando como un panel casi tridimensional que ayude a entender los conceptos de la estela, dependiente de los edificios cercanos
    y sus alturas»). En el suelo, la corona de las 36 procedencias del viento (en el color del aviso, las que meten la chimenea en una estela; en
    el del acento, las que tienen edificio y la dejan libre). Los edificios, con su altura (`operacion.estela`), del gris al color del aviso según
    la de la chimenea; la chimenea, a escala, sin humo (usuario, 2026-11-08: «ya se entiende»). Para el viento elegido (un clic en la corona;
    al empezar, el peor), su flecha y, en el suelo, la zona de influencia del edificio que manda (de 2 L a barlovento a 5 L a sotavento), y la
    chimenea, fantasma, hasta la altura a la que saldría libre (alto + 1,5 L). Las alturas, ×2 para que se lean frente al radio, con su escala
    vertical a un lado. Se mueve como un visor 3D: arrastrar gira e inclina; con el botón derecho (o Mayúsculas), desplaza; la rueda acerca;
    doble clic, la vista de partida."""
    ALTO = 410
    ANILLOS = (10, 25, 50, 100)

    def __init__(self, parent=None):
        self._estado, self._xy, self._alto, self._diam, self._orient = "sin_punto", (0.0, 0.0), None, None, "vertical"
        self._ed, self._est, self._filas, self._radio = [], None, [], 40.0
        self._desde, self._sobre, self._techos, self._desde_a_mano = None, None, [], False
        super().__init__(parent)
        self.setMinimumHeight(self.ALTO)
        self.setMinimumWidth(320)

    def estado_vista(self):
        """Cómo se está mirando (la vista y el viento elegido a mano, si lo hay), para seguir igual en otro panel."""
        return {"vista": self.vista(), "desde": self._desde if self._desde_a_mano else None}

    def poner_vista(self, estado):
        super().poner_vista(estado)
        if estado.get("desde") is not None:
            self.elegir(estado["desde"])

    # ── datos ────────────────────────────────────────────────────────────────────────────────────────────────
    def poner(self, foco, edificios, estela, estado="ok"):
        """`foco`: el del editor (su posición, altura y salida); `edificios`, de `estela.edificios_cerca` (con vértices); `estela`, de
        `estela.calcular`; `estado`: «ok», «sin_punto», «calculando» o «sin_edificios»."""
        from teodors.operacion import estela as E
        u, s = foco.get("ubicacion") or {}, foco.get("salida") or {}
        x, y = u.get("x", 0.0), u.get("y", 0.0)
        self._xy, self._alto, self._diam = (x, y), foco.get("altura_m"), s.get("diametro_m")
        self._orient = s.get("orientacion") or "vertical"
        todos = [dict(e, rel=_antihorario([(a - x, b - y) for a, b in e["verts"]])) for e in (edificios or [])]
        self._est, self._estado = estela, estado
        self._filas = E.por_viento(estela, self._alto) if estela else []
        lejos = [max(math.hypot(a, b) for a, b in e["rel"]) for e in todos if e["dist_m"] <= 5 * e["altura_m"]]
        self._radio = min(150.0, max(30.0, 1.05 * max(lejos, default=30.0)))
        self._ed = [e for e in todos if max(math.hypot(a, b) for a, b in e["rel"]) <= self._radio * 1.02]     # los que se salen del suelo, no
        if self._desde is None or not self._desde_a_mano:         # el elegido a mano se queda al mover la chimenea; si no, el peor de aquí
            self._desde = self._peor()
        self.update()

    def _peor(self):
        """El viento con el que la chimenea queda más hundida en una estela; si con ninguno, el primero con edificio; si no, el del oeste."""
        dentro = [f for f in self._filas if f["dentro"]]
        if dentro:
            return max(dentro, key=lambda f: f["libre_m"] - (self._alto or 0.0))["desde"]
        return next((f["desde"] for f in self._filas if f["alto"] > 0), 270.0)

    def estado(self):
        return self._estado

    def filas(self):
        return self._filas

    def elegido(self):
        return self._desde

    def elegir(self, desde):
        """El viento elegido (a mano): se queda aunque se mueva la chimenea."""
        self._desde, self._desde_a_mano = float(desde), True
        self.update()

    def _fila(self):
        if not self._filas or self._desde is None:
            return None
        return self._filas[(round(self._desde / 10.0) - 1) % 36]

    def _zona(self):
        """La zona de la estela con el viento elegido: (su huella [(x, y)], su techo, el edificio que manda), o None."""
        f = self._fila()
        if not f or f["alto"] <= 0:
            return None
        hb, L = f["alto"], min(f["alto"], f["ancho"])
        cand = [e for e in self._ed if abs(e["altura_m"] - hb) <= 0.3]
        if not cand:
            return None
        e = min(cand, key=lambda e: min(math.hypot(a, b) for a, b in e["rel"]))
        t = math.radians(self._desde)
        fx, fy = -math.sin(t), -math.cos(t)                                # hacia donde va el viento
        pts = [(a + k * L * fx, b + k * L * fy) for a, b in e["rel"] for k in (-2.0, 0.0, 5.0)]
        return _envolvente(pts), hb + 1.5 * L, e

    # ── proyección ───────────────────────────────────────────────────────────────────────────────────────────
    def _geo(self):
        R = self._radio
        f = self._fila()
        libre = f["libre_m"] if f else 0.0
        zmax = max([self._alto or 0.0, 4.0] + [e["altura_m"] for e in self._ed]
                   + [min(libre, 2.4 * max(self._alto or 0.0, 4.0))])
        return self._encuadre(R, R * 1.14, zmax)

    def _sector(self, g, desde, r0, r1):
        angs = [math.radians(desde - 4.6 + 9.2 * k / 4) for k in range(5)]
        pts = [self._p(g, r1 * math.sin(t), r1 * math.cos(t)) for t in angs] + [self._p(g, r0 * math.sin(t), r0 * math.cos(t)) for t in reversed(angs)]
        return QtGui.QPolygonF(pts)

    def _color_edificio(self, h):
        t = h / self._alto if self._alto else 0.6
        return _mezcla("#8c949a", tema.c("aviso"), (t - 0.45) / 0.55)

    # ── dibujo ───────────────────────────────────────────────────────────────────────────────────────────────
    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        marco = QtGui.QPainterPath()
        marco.addRoundedRect(QtCore.QRectF(self.rect()), 12, 12)
        p.fillPath(marco, QtGui.QColor(tema.c("fondo")))
        g = self._geo()
        R, Rt = g[5], g[6]
        texto, aviso = QtGui.QColor(tema.c("texto")), QtGui.QColor(tema.c("aviso"))
        self._suelo(p, g, self.ANILLOS)                                  # el suelo y las distancias
        # la corona de los vientos
        for k in range(36):
            desde = 10.0 * (k + 1)
            f = self._filas[k] if self._filas else None
            if f and f["dentro"]:
                falta = 1.0 - (self._alto or 0.0) / f["libre_m"] if f["libre_m"] else 1.0
                color = QtGui.QColor(aviso)
                color.setAlpha(round(110 + 145 * min(max(falta, 0.0), 1.0)))
            elif f and f["alto"] > 0:
                color = QtGui.QColor(tema.c("acento"))
                color.setAlpha(120)
            else:
                color = QtGui.QColor(tema.c("elevada"))
            if desde == self._sobre:
                color = color.lighter(125)
            elegido = self._desde is not None and abs(desde - self._desde) < 1
            p.setPen(QtGui.QPen(texto, 1.8) if elegido else QtCore.Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawPolygon(self._sector(g, desde, R * 1.02, Rt))
        self._cardinales(p, g, Rt * 1.07)
        if self._estado == "sin_punto":
            self._rotulo(p, g, "Marca la chimenea en el mapa")
            return
        # la flecha del viento elegido, en el suelo
        if self._desde is not None:
            t = math.radians(self._desde)
            ini, fin = self._p(g, R * 0.97 * math.sin(t), R * 0.97 * math.cos(t)), self._p(g, R * 0.62 * math.sin(t), R * 0.62 * math.cos(t))
            col = QtGui.QColor(tema.c("acento_claro"))
            p.setPen(QtGui.QPen(col, 3.0, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap))
            p.drawLine(ini, fin)
            ang = math.atan2(fin.y() - ini.y(), fin.x() - ini.x())
            p.setBrush(col)
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.drawPolygon(QtGui.QPolygonF([fin + QtCore.QPointF(5 * math.cos(ang), 5 * math.sin(ang)),
                                           fin + QtCore.QPointF(9 * math.cos(ang + 2.5), 9 * math.sin(ang + 2.5)),
                                           fin + QtCore.QPointF(9 * math.cos(ang - 2.5), 9 * math.sin(ang - 2.5))]))
        # la zona de influencia del edificio que manda, en el suelo y sin salirse de él
        zona = self._zona()
        if zona:
            recorte = QtGui.QPainterPath()
            recorte.addPolygon(self._anillo(g, R))
            p.save()
            p.setClipPath(recorte)
            col = QtGui.QColor(aviso)
            col.setAlpha(60)
            p.setBrush(col)
            col = QtGui.QColor(aviso)
            col.setAlpha(210)
            p.setPen(QtGui.QPen(col, 1.2, QtCore.Qt.PenStyle.DashLine))
            p.drawPolygon(QtGui.QPolygonF([self._p(g, x, y) for x, y in zona[0]]))
            p.restore()
        # los edificios (de lejos a cerca), la chimenea con su penacho y los de delante de ella
        self._techos = []
        orden = sorted(self._ed, key=lambda e: -sum(self._prof(a, b) for a, b in e["rel"]) / len(e["rel"]))
        detras = [e for e in orden if sum(self._prof(a, b) for a, b in e["rel"]) / len(e["rel"]) > 0]
        for e in detras:
            self._edificio(p, g, e)
        self._chimenea(p, g)
        for e in orden:
            if e not in detras:
                self._edificio(p, g, e)
        self._escala(p, g)
        self._leyenda(p)
        if self._estado in ("calculando", "sin_edificios"):
            self._rotulo(p, g, {"calculando": "Buscando edificios…", "sin_edificios": "Sin edificios cerca"}[self._estado])

    def _rotulo(self, p, g, txt):
        p.setFont(self._letra(12, True))
        p.setPen(QtGui.QColor(tema.c("tenue")))
        c = self._p(g, 0, 0)
        p.drawText(QtCore.QRectF(0, c.y() + 14, self.width(), 20), QtCore.Qt.AlignmentFlag.AlignCenter, txt)

    def _edificio(self, p, g, e):
        h = e["altura_m"]
        techo = self._extruir(p, g, e["rel"], h, self._color_edificio(h))
        self._techos.append((techo, e))
        self._cifra_techo(p, techo, h)

    def _chimenea(self, p, g):
        s = g[2]
        h = self._alto or 0.0
        alto = h or 4.0
        w = max(2.8, (self._diam or 0.6) / 2 * s)
        pie, cima = self._p(g, 0, 0), self._p(g, 0, 0, alto)
        relleno, linea = COLORES["punto"]
        grad = QtGui.QLinearGradient(pie.x() - w, 0, pie.x() + w, 0)
        grad.setColorAt(0.0, QtGui.QColor(relleno).darker(135))
        grad.setColorAt(0.45, QtGui.QColor(relleno).lighter(118))
        grad.setColorAt(1.0, QtGui.QColor(relleno).darker(150))
        p.setPen(QtGui.QPen(QtGui.QColor(linea), 1.2, QtCore.Qt.PenStyle.SolidLine if h else QtCore.Qt.PenStyle.DashLine))
        p.setBrush(grad if h else QtCore.Qt.BrushStyle.NoBrush)
        p.drawRect(QtCore.QRectF(cima.x() - w, cima.y(), 2 * w, pie.y() - cima.y()))
        ry = w * g[3]
        p.setBrush(QtGui.QColor(relleno).darker(170) if h else QtCore.Qt.BrushStyle.NoBrush)
        p.drawEllipse(cima, w, ry)
        # la boca, según hacia dónde sale: un sombrerete encima, o un codo de lado (y hacia abajo)
        if h and self._orient == "sombrerete":
            tapa = self._p(g, 0, 0, alto + 1.0)
            p.setBrush(QtGui.QColor(relleno))
            p.drawLine(cima, tapa)
            p.drawEllipse(tapa, w * 1.9, w * 1.9 * g[3] + 1.5)
        elif h and self._orient in ("horizontal", "abajo"):
            p.setBrush(grad)
            p.drawRect(QtCore.QRectF(cima.x() - w, cima.y() - 2 * w, 4.2 * w, 2 * w))
            if self._orient == "abajo":
                p.drawRect(QtCore.QRectF(cima.x() + 1.4 * w, cima.y() - w, 1.8 * w, 2.6 * w))
        f = self._fila()
        # la chimenea que saldría libre, fantasma
        libre = f["libre_m"] if f else 0.0
        col = QtGui.QColor(tema.c("aviso"))
        if h and libre > h:
            arriba = self._p(g, 0, 0, libre)
            p.setPen(QtGui.QPen(col, 1.3, QtCore.Qt.PenStyle.DashLine))
            p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            p.drawRect(QtCore.QRectF(arriba.x() - w, arriba.y(), 2 * w, cima.y() - arriba.y()))
            p.drawEllipse(arriba, w, ry)
            p.setFont(self._letra(11, True))
            p.drawText(QtCore.QPointF(arriba.x() + w + 6, arriba.y() + 4), f"libre a {_num(libre, 0 if libre >= 10 else 1)} m")
        # su altura (sin humo: usuario, 2026-11-08, «no es necesario el humo de la chimenea, ya se entiende»)
        p.setFont(self._letra(12, True))
        p.setPen(QtGui.QColor(tema.c("texto")))
        p.drawText(QtCore.QPointF(cima.x() + w + 6, cima.y() + 4), f"{_num(h, 1)} m" if h else "? m")

    def _leyenda(self, p):
        from teodors.operacion import estela as E
        f = self._fila()
        if self._desde is None:
            return
        p.setFont(self._letra(13, True))
        p.setPen(QtGui.QColor(tema.c("texto")))
        p.drawText(QtCore.QPointF(14, 22), f"Viento del {E.angulo_texto(self._desde)}")
        p.setFont(self._letra(12, True))
        if f and f["dentro"]:
            p.setPen(QtGui.QColor(tema.c("aviso")))
            txt = f"en la estela de un edificio de {_num(f['alto'], 0)} m"
        elif f and f["alto"] > 0:
            p.setPen(QtGui.QColor(tema.c("acento_claro")))
            txt = "fuera de la estela"
        else:
            p.setPen(QtGui.QColor(tema.c("tenue")))
            txt = "sin edificios a barlovento" if self._filas else ""
        p.drawText(QtCore.QPointF(14, 40), txt)

    # ── ratón ────────────────────────────────────────────────────────────────────────────────────────────────
    def _sector_en(self, pos):
        g = self._geo()
        x, y = self._al_suelo(g, pos.x(), pos.y())
        r = math.hypot(x, y)
        if g[5] * 1.0 <= r <= g[6] * 1.04:
            return (round((math.degrees(math.atan2(x, y)) % 360.0) / 10.0) % 36 or 36) * 10.0
        return None

    def mousePressEvent(self, e):
        """Clic en la corona: ese viento. Si no, arrastrar con el botón izquierdo gira (a los lados) e inclina (arriba y abajo); con el derecho,
        el central o Mayúsculas, mueve (usuario, 2026-11-08: «si pudieras girar y mover el 3D ya sería increíble»)."""
        izq = e.button() == QtCore.Qt.MouseButton.LeftButton
        mover = not izq or bool(e.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier)
        desde = self._sector_en(e.position()) if izq and not mover else None
        if desde is not None and self._estado != "sin_punto":
            self.elegir(desde)
            return
        self._empezar_arrastre(e)

    def mouseMoveEvent(self, e):
        from teodors.operacion import estela as E
        if self._arrastrar(e):
            return
        desde = self._sector_en(e.position())
        if desde != self._sobre:
            self._sobre = desde
            self.update()
        texto = ""
        if desde is not None and self._filas:
            f = self._filas[round(desde / 10.0) - 1]
            texto = f"<b>Viento del {E.angulo_texto(desde)}</b> ({_num(desde, 0)}°)<br>"
            texto += (f"edificio de {_num(f['alto'], 1)} m · ancho {_num(f['ancho'], 0)} m<br>libre a {_num(f['libre_m'], 1)} m · "
                      + ("<span style='color:%s'>en la estela</span>" % tema.c("aviso") if f["dentro"] else "libre")) if f["alto"] > 0 else "sin edificio"
        else:
            for techo, ed in reversed(self._techos):
                if techo.containsPoint(e.position(), QtCore.Qt.FillRule.OddEvenFill):
                    texto = f"<b>{_num(ed['altura_m'], 1)} m</b> ({ed['fuente']})<br>a {_num(ed['dist_m'], 0)} m"
                    break
        if texto:
            QtWidgets.QToolTip.showText(e.globalPosition().toPoint(), texto, self)
        else:
            QtWidgets.QToolTip.hideText()

    def leaveEvent(self, _e):
        if self._sobre is not None:
            self._sobre = None
            self.update()


class VisorEdificios(_Visor3D):
    """Los edificios de la planta en 3D (usuario, 2026-11-08: «lo ideal es introducir el visor 3D de estos edificios, como hicimos para los
    focos de punto, en el menú de edificios de planta»): sobre el suelo, con sus distancias y los puntos cardinales, cada edificio levantado con
    su altura, en el color de los edificios del plano; el elegido, en el del acento y con su nombre encima. Al pasar por uno, su nombre, su
    altura, su origen y su área; un clic lo elige (`pulsado`). Se mueve como el de la chimenea (`_Visor3D`). El encuadre se queda mientras los
    edificios quepan: cambiar uno no mueve la vista."""
    ALTO = 300
    EXAGERA = 1.5
    ANILLOS = (25, 50, 100, 200)
    pulsado = QtCore.Signal(str)

    def __init__(self, parent=None, alto=None):
        self._ed, self._sel, self._sobre, self._siluetas = [], None, None, []
        self._centro, self._radio, self._pulsado_en = None, 40.0, None
        super().__init__(parent)
        self.setMinimumHeight(alto or self.ALTO)
        self.setMinimumWidth(240)

    def poner(self, edificios, elegido=None, encuadrar=False):
        """`edificios`: los de `operacion.edificios_planta` (su «poligono» en UTM); `elegido`, el id del que se resalta."""
        validos = [e for e in edificios or [] if len(e.get("poligono") or []) >= 3]
        verts = [(x, y) for e in validos for x, y in e["poligono"]]
        c = self._centro
        if verts and (encuadrar or c is None or max(math.hypot(x - c[0], y - c[1]) for x, y in verts) > self._radio * 0.98):
            xs, ys = [x for x, _ in verts], [y for _, y in verts]
            c = self._centro = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
            self._radio = max(30.0, 1.12 * max(math.hypot(x - c[0], y - c[1]) for x, y in verts))
        cx, cy = c or (0.0, 0.0)
        self._ed = [dict(e, rel=_antihorario([(a - cx, b - cy) for a, b in e["poligono"]])) for e in validos]
        self._sel = elegido
        self.update()

    def elegir(self, id_):
        self._sel = id_
        self.update()

    def elegido(self):
        return self._sel

    def edificios(self):
        return self._ed

    def _geo(self):
        return self._encuadre(self._radio, self._radio * 1.08, max([4.0] + [e["altura_m"] for e in self._ed]))

    # ── dibujo ───────────────────────────────────────────────────────────────────────────────────────────────
    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        marco = QtGui.QPainterPath()
        marco.addRoundedRect(QtCore.QRectF(self.rect()), 12, 12)
        p.fillPath(marco, QtGui.QColor(tema.c("fondo")))
        g = self._geo()
        self._suelo(p, g, self.ANILLOS)
        self._cardinales(p, g, g[6])
        self._siluetas = []
        if not self._ed:
            p.setFont(self._letra(12, True))
            p.setPen(QtGui.QColor(tema.c("tenue")))
            c = self._p(g, 0, 0)
            p.drawText(QtCore.QRectF(0, c.y() - 10, self.width(), 20), QtCore.Qt.AlignmentFlag.AlignCenter, "Sin edificios de la planta")
            return
        elegido = None
        for e in sorted(self._ed, key=lambda e: -sum(self._prof(a, b) for a, b in e["rel"]) / len(e["rel"])):     # de lejos a cerca
            base = QtGui.QColor(COLORES["edificio"][0])
            if e["id"] == self._sel:
                base, elegido = QtGui.QColor(tema.c("acento")), e
            elif e["id"] == self._sobre:
                base = base.lighter(115)
            h = e["altura_m"]
            techo = self._extruir(p, g, e["rel"], h, base)
            self._cifra_techo(p, techo, h)
            silueta = [self._p(g, a, b, z) for a, b in e["rel"] for z in (0.0, h)]
            self._siluetas.append((QtGui.QPolygonF([QtCore.QPointF(*q) for q in _envolvente([(q.x(), q.y()) for q in silueta])]), e, techo))
        if elegido is not None:
            self._etiqueta(p, next(t for _, e, t in self._siluetas if e is elegido), elegido)
        self._escala(p, g)
        self._leyenda(p)

    def _etiqueta(self, p, techo, e):
        """El nombre y la altura del elegido, en una pastilla encima de su techo (como en el plano)."""
        txt = f"{e.get('nombre') or e['id']} · {_num(e['altura_m'], 1)} m"
        p.setFont(self._letra(11, True))
        fm = QtGui.QFontMetrics(p.font())
        w, h = fm.horizontalAdvance(txt) + 16, fm.height() + 6
        caja = techo.boundingRect()
        x = min(max(caja.center().x() - w / 2, 6), self.width() - w - 6)
        r = QtCore.QRectF(x, max(caja.top() - h - 6, 4), w, h)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(tema.c("acento")))
        p.drawRoundedRect(r, h / 2, h / 2)
        p.setPen(QtGui.QColor("#10201a"))
        p.drawText(r, QtCore.Qt.AlignmentFlag.AlignCenter, txt)

    def _leyenda(self, p):
        alto = max(self._ed, key=lambda e: e["altura_m"])
        n = len(self._ed)
        p.setFont(self._letra(13, True))
        p.setPen(QtGui.QColor(tema.c("texto")))
        p.drawText(QtCore.QPointF(14, 22), f"{n} edificio{'s' if n != 1 else ''}")
        p.setFont(self._letra(11))
        p.setPen(QtGui.QColor(tema.c("tenue")))
        p.drawText(QtCore.QPointF(14, 39), f"el más alto, {alto.get('nombre') or alto['id']} ({_num(alto['altura_m'], 1)} m)")
        p.setFont(self._letra(10))
        p.drawText(QtCore.QRectF(0, self.height() - 22, self.width() - 12, 16), QtCore.Qt.AlignmentFlag.AlignRight,
                   "arrastra para girar · rueda para acercar")

    # ── ratón ────────────────────────────────────────────────────────────────────────────────────────────────
    def edificio_en(self, pos):
        """El edificio bajo `pos` (el más cercano a quien mira), o None."""
        for silueta, e, _ in reversed(self._siluetas):
            if silueta.containsPoint(QtCore.QPointF(pos), QtCore.Qt.FillRule.OddEvenFill):
                return e
        return None

    def mousePressEvent(self, e):
        self._pulsado_en = e.position()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        """Un clic (sin arrastrar) en un edificio lo elige."""
        ini, self._pulsado_en = self._pulsado_en, None
        super().mouseReleaseEvent(e)
        if ini is None or e.button() != QtCore.Qt.MouseButton.LeftButton or (e.position() - ini).manhattanLength() > 4:
            return
        ed = self.edificio_en(e.position())
        if ed is not None:
            self.elegir(ed["id"])
            self.pulsado.emit(ed["id"])

    def mouseMoveEvent(self, e):
        from teodors.operacion.edificios_planta import nombre_origen
        if self._arrastrar(e):
            return
        ed = self.edificio_en(e.position())
        id_ = ed["id"] if ed else None
        if id_ != self._sobre:
            self._sobre = id_
            self.update()
        if ed is None:
            QtWidgets.QToolTip.hideText()
            return
        pts = ed["rel"]
        area = abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))) / 2
        QtWidgets.QToolTip.showText(e.globalPosition().toPoint(), f"<b>{ed.get('nombre') or ed['id']}</b><br>{_num(ed['altura_m'], 1)} m · "
                                    f"{_num(area, 0)} m² · {nombre_origen(ed.get('origen', 'dibujo'))}", self)

    def leaveEvent(self, _e):
        if self._sobre is not None:
            self._sobre = None
            self.update()


class PanelSuperficie(_Visor3D):
    """Un foco de superficie en 3D, con los edificios de la planta de alrededor (usuario, 2026-11-08: «focos de superficies, desde piscinas,
    superficies de tanques abiertos; también debemos poder verlo en 3D»). A ras de suelo (una balsa, una piscina), su lámina, hundida, con sus
    taludes; en alto (la boca de un tanque abierto, un biofiltro), su cuerpo levantado hasta la altura de emisión y la lámina encima. El agua,
    azul; un biofiltro, del color de su lecho. Encima, su área y lo que emite. El edificio en cuya boca está (o el que queda debajo) no se
    pinta aparte: es su cuerpo. Al pasar, el nombre y la altura de cada edificio; con un tanque abierto, un clic en uno lo elige
    (`edificio_pulsado`): la superficie pasa a su boca. Se mueve como los otros visores (`_Visor3D`)."""
    ALTO = 360
    EXAGERA = 1.5
    ANILLOS = (10, 25, 50, 100)
    PROFUNDIDAD = 1.2                      # m: lo que se hunde la lámina de una balsa (solo para verla como tal)
    COLOR_LAMINA = {"balsa": "#4f97bf", "tanque": "#5a8fa8", "biofiltro": "#7d8a4e"}
    edificio_pulsado = QtCore.Signal(str)

    def __init__(self, parent=None):
        self._pol, self._h, self._clase, self._sobre, self._etiqueta_txt = [], 0.0, "balsa", None, ""
        self._ed, self._centro, self._radio, self._siluetas, self._encima, self._pulsado_en = [], None, 40.0, [], None, None
        super().__init__(parent)
        self.setMinimumHeight(self.ALTO)
        self.setMinimumWidth(320)

    # ── datos ────────────────────────────────────────────────────────────────────────────────────────────────
    def poner(self, foco, edificios, etiqueta=""):
        """`foco`: la superficie (su polígono, su altura y su clase); `edificios`: los de `edificios_planta` (con «poligono»); `etiqueta`,
        lo que se escribe encima (su área y su emisión)."""
        from teodors.operacion import focos as F
        pol = (foco.get("ubicacion") or {}).get("poligono") or []
        self._clase, self._sobre = F.clase_superficie(foco), (foco.get("superficie") or {}).get("sobre")
        self._h = max(float(foco.get("altura_m") or 0.0), 0.0)
        self._etiqueta_txt = etiqueta
        eds = [e for e in edificios or [] if len(e.get("poligono") or []) >= 3]
        if len(pol) >= 3:
            cx, cy = sum(x for x, _ in pol) / len(pol), sum(y for _, y in pol) / len(pol)
            lado = max(math.hypot(x - cx, y - cy) for x, y in pol)
            self._centro, self._radio = (cx, cy), min(150.0, max(45.0, 2.6 * lado))      # con lo que tiene alrededor
        elif eds and self._centro is None:                              # sin dibujar: la planta entera, para elegir dónde
            xs = [x for e in eds for x, _ in e["poligono"]]
            ys = [y for e in eds for _, y in e["poligono"]]
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            self._centro = (cx, cy)
            self._radio = max(30.0, 1.1 * max(math.hypot(x - cx, y - cy) for x, y in zip(xs, ys)))
        cx, cy = self._centro or (0.0, 0.0)
        self._pol = _antihorario([(x - cx, y - cy) for x, y in pol]) if len(pol) >= 3 else []
        dentro = QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in self._pol])
        self._ed = []
        for e in eds:
            rel = _antihorario([(x - cx, y - cy) for x, y in e["poligono"]])
            if max(math.hypot(a, b) for a, b in rel) > self._radio * 1.02:
                continue
            mx, my = sum(a for a, _ in rel) / len(rel), sum(b for _, b in rel) / len(rel)
            if e["id"] == self._sobre or (self._pol and dentro.containsPoint(QtCore.QPointF(mx, my), QtCore.Qt.FillRule.OddEvenFill)):
                continue                                                # el cuerpo de la superficie: se pinta con ella
            self._ed.append(dict(e, rel=rel))
        self.update()

    def edificios(self):
        return self._ed

    def _geo(self):
        return self._encuadre(self._radio, self._radio * 1.08, max([4.0, self._h] + [e["altura_m"] for e in self._ed]))

    # ── dibujo ───────────────────────────────────────────────────────────────────────────────────────────────
    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        marco = QtGui.QPainterPath()
        marco.addRoundedRect(QtCore.QRectF(self.rect()), 12, 12)
        p.fillPath(marco, QtGui.QColor(tema.c("fondo")))
        g = self._geo()
        self._suelo(p, g, self.ANILLOS)
        self._cardinales(p, g, g[6])
        self._siluetas = []
        prof = (lambda pts: sum(self._prof(a, b) for a, b in pts) / len(pts))
        cosas = [(prof(e["rel"]), "edificio", e) for e in self._ed]
        if self._pol:
            cosas.append((prof(self._pol), "superficie", None))
        techo_sup = None
        for _, que, e in sorted(cosas, key=lambda c: -c[0]):               # de lejos a cerca
            if que == "superficie":
                techo_sup = self._superficie(p, g)
                continue
            base = QtGui.QColor(COLORES["edificio"][0])
            if e["id"] == self._encima:
                base = base.lighter(115)
            techo = self._extruir(p, g, e["rel"], e["altura_m"], base)
            self._cifra_techo(p, techo, e["altura_m"])
            silueta = [self._p(g, a, b, z) for a, b in e["rel"] for z in (0.0, e["altura_m"])]
            self._siluetas.append((QtGui.QPolygonF([QtCore.QPointF(*q) for q in _envolvente([(q.x(), q.y()) for q in silueta])]), e))
        if techo_sup is not None and self._etiqueta_txt:
            self._pastilla(p, techo_sup, self._etiqueta_txt)
        self._escala(p, g)
        self._leyenda(p)
        if not self._pol:
            p.setFont(self._letra(12, True))
            p.setPen(QtGui.QColor(tema.c("tenue")))
            txt = "Dibújala en el mapa" + (" o pincha un depósito" if self._clase == "tanque" and self._ed else "")
            p.drawText(QtCore.QRectF(0, self.height() - 52, self.width(), 18), QtCore.Qt.AlignmentFlag.AlignCenter, txt)

    def _superficie(self, p, g):
        """El cuerpo (en alto) o el vaso (a ras de suelo) y la lámina; devuelve la lámina proyectada."""
        lamina = QtGui.QColor(self.COLOR_LAMINA.get(self._clase, self.COLOR_LAMINA["balsa"]))
        borde = QtGui.QColor(tema.c("borde_fuerte"))
        if self._h > 0.3:                                          # en alto: su cuerpo, como un edificio, y la lámina en la boca
            cuerpo = QtGui.QColor(COLORES["edificio"][0] if self._clase == "tanque" else "#8d7f6a")
            techo = self._extruir(p, g, self._pol, self._h, cuerpo)
            z = self._h
        else:                                                      # a ras de suelo: el vaso, con los taludes de dentro que se ven
            a = math.radians(self._az)
            z = -self.PROFUNDIDAD
            caras = []
            for i in range(len(self._pol)):
                (x1, y1), (x2, y2) = self._pol[i], self._pol[(i + 1) % len(self._pol)]
                nx, ny = y2 - y1, -(x2 - x1)
                if nx * math.sin(a) + ny * math.cos(a) < 0:            # los de delante quedan tapados por el suelo
                    continue
                caras.append((self._prof((x1 + x2) / 2, (y1 + y2) / 2), x1, y1, x2, y2))
            talud = QtGui.QColor("#9b8a6e")
            for _, x1, y1, x2, y2 in sorted(caras, reverse=True):
                p.setBrush(talud.darker(118))
                p.setPen(QtGui.QPen(borde, 0.6))
                p.drawPolygon(QtGui.QPolygonF([self._p(g, x1, y1), self._p(g, x2, y2), self._p(g, x2, y2, z), self._p(g, x1, y1, z)]))
            techo = None
        agua = QtGui.QPolygonF([self._p(g, x, y, z) for x, y in self._pol])
        p.setBrush(lamina)
        p.setPen(QtGui.QPen(lamina.darker(140), 1.0))
        p.drawPolygon(agua)
        # unas ondas en el agua; en un biofiltro, el grano de su lecho (corteza, astilla), recortados a la lámina
        camino = QtGui.QPainterPath()
        camino.addPolygon(agua)
        p.save()
        p.setClipPath(camino)
        caja = agua.boundingRect()
        if self._clase == "biofiltro":
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            claro, oscuro = lamina.lighter(135), lamina.darker(135)
            paso = 5.0
            fila = 0
            y = caja.top() + 2
            while y < caja.bottom():
                x = caja.left() + (paso / 2 if fila % 2 else 0.0) + 1
                while x < caja.right():
                    k = int(x * 7 + y * 13) % 5                              # un grano irregular, siempre igual
                    p.setBrush(claro if k < 2 else oscuro)
                    p.drawEllipse(QtCore.QPointF(x, y), 1.1 + 0.25 * k, 0.8 + 0.15 * k)
                    x += paso
                y += paso * 0.8
                fila += 1
        else:
            p.setPen(QtGui.QPen(lamina.lighter(135), 1.0))
            paso = max(7.0, caja.height() / 6)
            y = caja.top() + paso / 2
            while y < caja.bottom():
                onda = QtGui.QPainterPath(QtCore.QPointF(caja.left(), y))
                x = caja.left()
                while x < caja.right():
                    onda.quadTo(QtCore.QPointF(x + 6, y - 2.5), QtCore.QPointF(x + 12, y))
                    onda.quadTo(QtCore.QPointF(x + 18, y + 2.5), QtCore.QPointF(x + 24, y))
                    x += 24
                p.drawPath(onda)
                y += paso
        p.restore()
        if self._clase == "biofiltro":                              # el aire tratado, que lo atraviesa y sale por todo el lecho
            self._aire(p, g, z)
        if self._h <= 0.3:                                          # el borde del vaso, a ras de suelo
            p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            p.setPen(QtGui.QPen(QtGui.QColor("#d8c9a8"), 1.6))
            p.drawPolygon(QtGui.QPolygonF([self._p(g, x, y) for x, y in self._pol]))
        return agua if techo is None else techo

    def _aire(self, p, g, z):
        """Unas flechas que suben desde el lecho de un biofiltro: el aire de la nave, tratado, sale por toda su superficie (despacio: sin
        sobreelevación, como un área)."""
        xs, ys = [a for a, _ in self._pol], [b for _, b in self._pol]
        dentro = QtGui.QPolygonF([QtCore.QPointF(a, b) for a, b in self._pol])
        alto = max(2.5, 0.35 * min(max(xs) - min(xs), max(ys) - min(ys)))
        col = QtGui.QColor(tema.c("acento_claro"))
        col.setAlpha(170)
        p.setPen(QtGui.QPen(col, 1.6, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap))
        n = 3
        for i in range(n):
            for j in range(n):
                a = min(xs) + (i + 0.5) / n * (max(xs) - min(xs))
                b = min(ys) + (j + 0.5) / n * (max(ys) - min(ys))
                if not dentro.containsPoint(QtCore.QPointF(a, b), QtCore.Qt.FillRule.OddEvenFill):
                    continue
                ini, fin = self._p(g, a, b, z + 0.4), self._p(g, a, b, z + alto)
                p.drawLine(ini, fin)
                p.drawLine(fin, fin + QtCore.QPointF(-3.5, 4.5))
                p.drawLine(fin, fin + QtCore.QPointF(3.5, 4.5))

    def _pastilla(self, p, sitio, txt):
        p.setFont(self._letra(11, True))
        fm = QtGui.QFontMetrics(p.font())
        w, h = fm.horizontalAdvance(txt) + 16, fm.height() + 6
        caja = sitio.boundingRect()
        x = min(max(caja.center().x() - w / 2, 6), self.width() - w - 6)
        r = QtCore.QRectF(x, max(caja.top() - h - 8, 48), w, h)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(COLORES["superficie"][1]))
        p.drawRoundedRect(r, h / 2, h / 2)
        p.setPen(QtGui.QColor("#ffffff"))
        p.drawText(r, QtCore.Qt.AlignmentFlag.AlignCenter, txt)

    def _leyenda(self, p):
        from teodors.operacion import focos as F
        p.setFont(self._letra(13, True))
        p.setPen(QtGui.QColor(tema.c("texto")))
        p.drawText(QtCore.QPointF(14, 22), F.CLASES_SUPERFICIE[self._clase][0])
        p.setFont(self._letra(11))
        p.setPen(QtGui.QColor(tema.c("tenue")))
        donde = "a ras de suelo" if self._h <= 0.3 else f"emite a {_num(self._h, 1)} m del suelo"
        p.drawText(QtCore.QPointF(14, 39), donde if self._pol else "sin dibujar")
        p.setFont(self._letra(10))
        p.drawText(QtCore.QRectF(0, self.height() - 22, self.width() - 12, 16), QtCore.Qt.AlignmentFlag.AlignRight,
                   "arrastra para girar · rueda para acercar")

    # ── ratón ────────────────────────────────────────────────────────────────────────────────────────────────
    def edificio_en(self, pos):
        for silueta, e in reversed(self._siluetas):
            if silueta.containsPoint(QtCore.QPointF(pos), QtCore.Qt.FillRule.OddEvenFill):
                return e
        return None

    def mousePressEvent(self, e):
        self._pulsado_en = e.position()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        """Con un tanque abierto, un clic (sin arrastrar) en un edificio lo elige: la superficie pasa a su boca."""
        ini, self._pulsado_en = self._pulsado_en, None
        super().mouseReleaseEvent(e)
        if self._clase != "tanque" or ini is None or e.button() != QtCore.Qt.MouseButton.LeftButton \
                or (e.position() - ini).manhattanLength() > 4:
            return
        ed = self.edificio_en(e.position())
        if ed is not None:
            self.edificio_pulsado.emit(ed["id"])

    def mouseMoveEvent(self, e):
        if self._arrastrar(e):
            return
        ed = self.edificio_en(e.position())
        id_ = ed["id"] if ed else None
        if id_ != self._encima:
            self._encima = id_
            self.update()
        if ed is None:
            QtWidgets.QToolTip.hideText()
            return
        extra = "<br>un clic: la superficie, en su boca" if self._clase == "tanque" else ""
        QtWidgets.QToolTip.showText(e.globalPosition().toPoint(), f"<b>{ed.get('nombre') or ed['id']}</b> · {_num(ed['altura_m'], 1)} m{extra}", self)

    def leaveEvent(self, _e):
        if self._encima is not None:
            self._encima = None
            self.update()


def _solido_volumen(foco, cx, cy):
    """El sólido de un volumen respecto a (cx, cy): {"caras": [[(x, y, z)…]…] (testeros, taludes y cima, sin la base), "partes": las rayas
    entre sus volúmenes del motor en el suelo, "eje", "centro", "huella" (su planta, QPolygonF), "medidas" (largo, ancho, alto)}; None sin
    su centro o sus medidas."""
    from teodors.operacion import focos as F
    u, d = foco.get("ubicacion") or {}, foco.get("dimensiones") or {}
    s, largo, ancho = F.seccion(foco), d.get("largo_m"), d.get("ancho_m")
    if not ("x" in u and "y" in u and s and largo):
        return None
    t = math.radians(F.rumbo(foco))
    ex, ey, nx, ny = math.sin(t), math.cos(t), math.cos(t), -math.sin(t)
    ox, oy, mitad = u["x"] - cx, u["y"] - cy, largo / 2

    def P(a, v, z):
        return (ox + a * nx + v * ex, oy + a * ny + v * ey, z)
    caras = [[P(a, -mitad, z) for a, z in s], [P(a, mitad, z) for a, z in s]]                         # los testeros
    for i in range(1, len(s)):                                                                          # los taludes, la cima (sin la base)
        (a1, z1), (a2, z2) = s[i], s[(i + 1) % len(s)]
        caras.append([P(a1, -mitad, z1), P(a2, -mitad, z2), P(a2, mitad, z2), P(a1, mitad, z1)])
    alto = max(z for _, z in s)
    huella = QtGui.QPolygonF([QtCore.QPointF(*P(a, v, 0.0)[:2]) for a, v in ((-ancho / 2, -mitad), (ancho / 2, -mitad),
                                                                               (ancho / 2, mitad), (-ancho / 2, mitad))])
    partes = []
    n = len(F.partes_volumen(foco))
    if n > 1:                                    # las rayas entre los volúmenes del motor, en el suelo, asomando a los dos lados de la pila
        paso, fuera = largo / n, ancho / 2 + max(1.5, 0.3 * ancho)
        partes = [(P(-fuera, -mitad + k * paso, 0.0), P(fuera, -mitad + k * paso, 0.0)) for k in range(1, n)]
    return {"caras": caras, "partes": partes, "eje": (P(0.0, -mitad, 0.0), P(0.0, mitad, 0.0)), "centro": (ox, oy, alto / 3),
            "huella": huella, "medidas": (largo, ancho, alto)}


class PanelVolumen(_Visor3D):
    """Un foco de volumen en 3D, con los edificios de la planta de alrededor (usuario, 2026-11-08: «pasamos a volúmenes donde añadiremos las
    pilas de compostaje»). Una pila o hilera, a lo largo de su eje y con su sección (triangular, o con la cima plana), del color y el grano del
    compost; una nave, una caja del color de los edificios. Una raya discontinua a la altura a la que emite y, en el suelo, discontinuos, los
    volúmenes en que la ve el motor (una pila larga, una fila: `focos.partes_volumen`). Encima, lo que emite. Se mueve como los otros."""
    ALTO = 360
    EXAGERA = 1.5
    ANILLOS = (10, 25, 50, 100)
    COLOR = {"pila": "#7b5a3c", "nave": COLORES["edificio"][0]}

    def __init__(self, parent=None):
        self._caras, self._partes, self._eje, self._clase, self._etiqueta_txt = [], [], None, "pila", ""
        self._medidas, self._h, self._ed, self._centro, self._radio = None, None, [], None, 40.0
        self._siluetas, self._encima, self._centro_solido = [], None, (0.0, 0.0, 0.0)
        self._az0, self._tocada = 0.0, False
        super().__init__(parent)
        self.setMinimumHeight(self.ALTO)
        self.setMinimumWidth(320)

    def vista_inicial(self):
        """Mirándolo de costado, a lo ancho de su largo (una hilera vista por su testero no se entiende)."""
        super().vista_inicial()
        self._az = getattr(self, "_az0", 0.0)

    def estado_vista(self):
        return dict(super().estado_vista(), tocada=self._tocada)

    def poner_vista(self, estado):
        """La vista de otro visor (la ficha rehecha); si nadie la había girado, sigue de costado a este volumen."""
        super().poner_vista(estado)
        self._tocada = estado.get("tocada", False)                     # la de otra clase de visor (la chimenea): de costado
        if not self._tocada:
            self._az = self._az0

    def _empezar_arrastre(self, e):
        self._tocada = True
        super()._empezar_arrastre(e)

    def poner(self, foco, edificios, etiqueta=""):
        """`foco`: el volumen (su centro, sus medidas, su rumbo, su clase); `edificios`: los de `edificios_planta`; `etiqueta`, lo que se
        escribe encima."""
        from teodors.operacion import focos as F
        u, d = foco.get("ubicacion") or {}, foco.get("dimensiones") or {}
        self._az0 = (F.rumbo(foco) - 65.0) % 360.0                     # de costado, con su testero a la vista
        if not self._tocada:                                            # mientras no se gire a mano, de costado
            self._az = self._az0
        self._clase, self._etiqueta_txt, self._h = F.clase_volumen(foco), etiqueta, F.altura_emision(foco)
        s, largo, ancho = F.seccion(foco), d.get("largo_m"), d.get("ancho_m")
        eds = [e for e in edificios or [] if len(e.get("poligono") or []) >= 3]
        if "x" in u and "y" in u:
            lado = max(largo or 10.0, ancho or 10.0) / 2
            self._centro, self._radio = (u["x"], u["y"]), min(150.0, max(45.0, 2.6 * lado))
        elif eds and self._centro is None:                              # sin ubicar: la planta entera
            xs = [x for e in eds for x, _ in e["poligono"]]
            ys = [y for e in eds for _, y in e["poligono"]]
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            self._centro = (cx, cy)
            self._radio = max(30.0, 1.1 * max(math.hypot(x - cx, y - cy) for x, y in zip(xs, ys)))
        cx, cy = self._centro or (0.0, 0.0)
        self._caras, self._partes, self._eje, self._medidas = [], [], None, None
        huella = None
        solido = _solido_volumen(foco, cx, cy)
        if solido:
            self._caras, self._partes, self._eje = solido["caras"], solido["partes"], solido["eje"]
            self._centro_solido, self._medidas, huella = solido["centro"], solido["medidas"], solido["huella"]
        self._ed = []
        for e in eds:
            rel = _antihorario([(x - cx, y - cy) for x, y in e["poligono"]])
            if max(math.hypot(a, b) for a, b in rel) > self._radio * 1.02:
                continue
            mx, my = sum(a for a, _ in rel) / len(rel), sum(b for _, b in rel) / len(rel)
            if huella is not None and huella.containsPoint(QtCore.QPointF(mx, my), QtCore.Qt.FillRule.OddEvenFill):
                continue                                                # una nave dibujada sobre su edificio: es ella
            self._ed.append(dict(e, rel=rel))
        self.update()

    def edificios(self):
        return self._ed

    def partes(self):
        return len(self._partes) + 1 if self._caras else 0

    def _geo(self):
        alto = self._medidas[2] if self._medidas else 4.0
        return self._encuadre(self._radio, self._radio * 1.08, max([4.0, alto] + [e["altura_m"] for e in self._ed]))

    # ── dibujo ───────────────────────────────────────────────────────────────────────────────────────────────
    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        marco = QtGui.QPainterPath()
        marco.addRoundedRect(QtCore.QRectF(self.rect()), 12, 12)
        p.fillPath(marco, QtGui.QColor(tema.c("fondo")))
        g = self._geo()
        self._suelo(p, g, self.ANILLOS)
        self._cardinales(p, g, g[6])
        self._siluetas = []
        prof = (lambda pts: sum(self._prof(a, b) for a, b in pts) / len(pts))
        cosas = [(prof(e["rel"]), "edificio", e) for e in self._ed]
        if self._caras:
            cosas.append((self._prof(*self._centro_solido[:2]), "volumen", None))
        cima = None
        for _, que, e in sorted(cosas, key=lambda c: -c[0]):
            if que == "volumen":
                cima = self._volumen(p, g)
                continue
            base = QtGui.QColor(COLORES["edificio"][0])
            if e["id"] == self._encima:
                base = base.lighter(115)
            techo = self._extruir(p, g, e["rel"], e["altura_m"], base)
            self._cifra_techo(p, techo, e["altura_m"])
            silueta = [self._p(g, a, b, z) for a, b in e["rel"] for z in (0.0, e["altura_m"])]
            self._siluetas.append((QtGui.QPolygonF([QtCore.QPointF(*q) for q in _envolvente([(q.x(), q.y()) for q in silueta])]), e))
        if cima is not None and self._etiqueta_txt:
            PanelSuperficie._pastilla(self, p, cima, self._etiqueta_txt)
        self._escala(p, g)
        self._leyenda(p)
        if not self._caras:
            p.setFont(self._letra(12, True))
            p.setPen(QtGui.QColor(tema.c("tenue")))
            p.drawText(QtCore.QRectF(0, self.height() - 52, self.width(), 18), QtCore.Qt.AlignmentFlag.AlignCenter,
                       "Dibújalo en el mapa y pon su alto")

    def _volumen(self, p, g):
        """Las caras que se ven (luz del noroeste y de arriba), el grano del compost, los volúmenes del motor y la altura de emisión;
        devuelve la silueta proyectada."""
        a, e0 = math.radians(self._az), math.radians(self._elev)
        vista = (-math.sin(a) * math.cos(e0), -math.cos(a) * math.cos(e0), math.sin(e0))
        base = QtGui.QColor(self.COLOR.get(self._clase, self.COLOR["nave"]))
        borde = QtGui.QColor(tema.c("borde_fuerte"))
        cx, cy, cz = self._centro_solido
        # en el suelo, la raya del eje y las de los volúmenes del motor
        p.setPen(QtGui.QPen(QtGui.QColor(tema.c("acento_claro")), 1.0, QtCore.Qt.PenStyle.DashLine))
        for q1, q2 in self._partes:
            p.drawLine(self._p(g, *q1), self._p(g, *q2))
        visibles = []
        for cara in self._caras:
            nx = ny = nz = 0.0                                       # la normal (Newell), hacia fuera del sólido
            for i in range(len(cara)):
                (x1, y1, z1), (x2, y2, z2) = cara[i], cara[(i + 1) % len(cara)]
                nx += (y1 - y2) * (z1 + z2)
                ny += (z1 - z2) * (x1 + x2)
                nz += (x1 - x2) * (y1 + y2)
            mx, my, mz = (sum(c[k] for c in cara) / len(cara) for k in range(3))
            if nx * (mx - cx) + ny * (my - cy) + nz * (mz - cz) < 0:
                nx, ny, nz = -nx, -ny, -nz
            if nx * vista[0] + ny * vista[1] + nz * vista[2] <= 0:
                continue
            modulo = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            luz = (-0.55 * nx + 0.83 * ny + 1.1 * nz) / modulo
            visibles.append((self._prof(mx, my), cara, luz))
        silueta = []
        for _, cara, luz in sorted(visibles, key=lambda v: -v[0]):
            poli = QtGui.QPolygonF([self._p(g, x, y, z) for x, y, z in cara])
            silueta += [poli.at(i) for i in range(poli.count())]
            color = base.lighter(round(100 + 18 * max(luz, 0.0))) if luz > 0 else base.darker(round(115 - 40 * luz))
            p.setBrush(color)
            p.setPen(QtGui.QPen(borde, 0.8))
            p.drawPolygon(poli)
            if self._clase == "pila":                                # el grano del compost, recortado a la cara
                camino = QtGui.QPainterPath()
                camino.addPolygon(poli)
                p.save()
                p.setClipPath(camino)
                p.setPen(QtCore.Qt.PenStyle.NoPen)
                caja = poli.boundingRect()
                y = caja.top() + 2
                fila = 0
                while y < caja.bottom():
                    x = caja.left() + (2.5 if fila % 2 else 0.0) + 1
                    while x < caja.right():
                        k = int(x * 7 + y * 13) % 5
                        p.setBrush(color.lighter(125) if k < 2 else color.darker(130))
                        p.drawEllipse(QtCore.QPointF(x, y), 0.9 + 0.2 * k, 0.7 + 0.12 * k)
                        x += 5.0
                    y += 4.0
                    fila += 1
                p.restore()
        # a la altura a la que emite, una raya a lo largo del eje
        if self._h and self._eje:
            (x1, y1, _), (x2, y2, _) = self._eje
            col = QtGui.QColor(tema.c("acento_claro"))
            p.setPen(QtGui.QPen(col, 1.6, QtCore.Qt.PenStyle.DashLine))
            ini, fin = self._p(g, x1, y1, self._h), self._p(g, x2, y2, self._h)
            p.drawLine(ini, fin)
            p.setFont(self._letra(10, True))
            p.drawText(fin + QtCore.QPointF(5, 4), f"{_num(self._h, 1)} m")
        caja = QtGui.QPolygonF([QtCore.QPointF(*q) for q in _envolvente([(q.x(), q.y()) for q in silueta])]) if silueta else QtGui.QPolygonF()
        return caja

    def _leyenda(self, p):
        from teodors.operacion import focos as F
        p.setFont(self._letra(13, True))
        p.setPen(QtGui.QColor(tema.c("texto")))
        p.drawText(QtCore.QPointF(14, 22), F.CLASES_VOLUMEN[self._clase])
        p.setFont(self._letra(11))
        p.setPen(QtGui.QColor(tema.c("tenue")))
        if self._medidas:
            largo, ancho, alto = self._medidas
            txt = f"{_num(largo, 0)} × {_num(ancho, 0)} × {_num(alto, 1)} m"
            if self.partes() > 1:
                txt += f" · en {self.partes()} volúmenes en el modelo"
            p.drawText(QtCore.QPointF(14, 39), txt)
        p.setFont(self._letra(10))
        p.drawText(QtCore.QRectF(0, self.height() - 22, self.width() - 12, 16), QtCore.Qt.AlignmentFlag.AlignRight,
                   "arrastra para girar · rueda para acercar")

    def edificio_en(self, pos):
        for silueta, e in reversed(self._siluetas):
            if silueta.containsPoint(QtCore.QPointF(pos), QtCore.Qt.FillRule.OddEvenFill):
                return e
        return None

    def mouseMoveEvent(self, e):
        if self._arrastrar(e):
            return
        ed = self.edificio_en(e.position())
        id_ = ed["id"] if ed else None
        if id_ != self._encima:
            self._encima = id_
            self.update()
        if ed is None:
            QtWidgets.QToolTip.hideText()
            return
        QtWidgets.QToolTip.showText(e.globalPosition().toPoint(), f"<b>{ed.get('nombre') or ed['id']}</b> · {_num(ed['altura_m'], 1)} m", self)

    def leaveEvent(self, _e):
        if self._encima is not None:
            self._encima = None
            self.update()


class CurvaViento(_Pintado):
    """El factor de lo que emite un foco con cada viento, (u / u_ref)^β (usuario, 2026-11-08: «una correlación en función del viento»):
    la curva de 0 a 12 m/s, el punto de la medida (factor 1) y unas guías con el factor a 2, 5 y 10 m/s."""
    U_MAX = 12.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(130)
        self._beta, self._ref = None, None

    def poner(self, beta, ref):
        self._beta = float(beta) if beta not in (None, "") else None
        self._ref = float(ref) if ref else None
        self.update()

    def factor(self, u):
        if self._beta is None or not self._ref:
            return None
        return (max(u, 0.0) / self._ref) ** self._beta

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        marco = QtGui.QPainterPath()
        marco.addRoundedRect(QtCore.QRectF(self.rect()), 10, 10)
        p.fillPath(marco, QtGui.QColor(tema.c("fondo")))
        izq, der, arriba, abajo = 34.0, self.width() - 12.0, 12.0, self.height() - 22.0
        tope = max(2.0, self.factor(self.U_MAX) or 1.0) * 1.08
        X = lambda u: izq + (der - izq) * u / self.U_MAX                                  # noqa: E731
        Y = lambda f: abajo - (abajo - arriba) * f / tope                                # noqa: E731
        tenue = QtGui.QColor(tema.c("tenue"))
        p.setFont(self._letra(10))
        p.setPen(QtGui.QPen(QtGui.QColor(tema.c("borde")), 1.0))
        p.drawLine(QtCore.QPointF(izq, abajo), QtCore.QPointF(der, abajo))
        p.drawLine(QtCore.QPointF(izq, arriba), QtCore.QPointF(izq, abajo))
        p.setPen(tenue)
        for u in (0, 2, 4, 6, 8, 10):
            p.drawText(QtCore.QRectF(X(u) - 12, abajo + 3, 24, 14), QtCore.Qt.AlignmentFlag.AlignCenter, str(u))
        p.drawText(QtCore.QRectF(X(12) - 30, abajo + 3, 30, 14), QtCore.Qt.AlignmentFlag.AlignRight, "m/s")
        p.drawText(QtCore.QRectF(0, Y(1.0) - 7, izq - 4, 14), QtCore.Qt.AlignmentFlag.AlignRight, "×1")
        p.setPen(QtGui.QPen(QtGui.QColor(tema.c("borde_fuerte")), 0.8, QtCore.Qt.PenStyle.DotLine))
        p.drawLine(QtCore.QPointF(izq, Y(1.0)), QtCore.QPointF(der, Y(1.0)))
        if self.factor(1.0) is None:
            return
        acento = QtGui.QColor(tema.c("acento_claro"))
        camino = QtGui.QPainterPath(QtCore.QPointF(X(0.0), Y(self.factor(0.0))))
        for k in range(1, 121):
            u = self.U_MAX * k / 120
            camino.lineTo(QtCore.QPointF(X(u), Y(self.factor(u))))
        p.setPen(QtGui.QPen(acento, 2.0))
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.drawPath(camino)
        for u in (2.0, 5.0, 10.0):                                                      # las guías, con su factor
            f = self.factor(u)
            p.setPen(QtGui.QPen(QtGui.QColor(tema.c("borde_fuerte")), 0.8, QtCore.Qt.PenStyle.DashLine))
            p.drawLine(QtCore.QPointF(X(u), abajo), QtCore.QPointF(X(u), Y(f)))
            p.setPen(QtGui.QColor(tema.c("texto")))
            p.setFont(self._letra(10, True))
            p.drawText(QtCore.QPointF(X(u) + 4, Y(f) - 4), f"×{_num(f, 1)}")
        p.setBrush(acento)                                                              # la medida: factor 1
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.drawEllipse(QtCore.QPointF(X(self._ref), Y(1.0)), 3.5, 3.5)


class VisorFocos3D(_Visor3D):
    """Todos los focos de la planta en 3D, con sus edificios (usuario, 2026-11-08: «debajo de la lista de focos, el visor 3D con todos los
    focos ya sería increíble»): las balsas hundidas, un tanque abierto en su boca, el biofiltro con su aire, las pilas con su sección y su
    grano, las chimeneas, y los edificios. Lo dibujan los mismos métodos que los visores del editor (`PanelSuperficie._superficie`,
    `PanelVolumen._volumen`). El elegido, perfilado en el color del acento y con su nombre encima; al pasar, su nombre y su olor; un clic lo
    elige (`pulsado`). Se mueve como los otros."""
    ALTO = 260
    ELEV = 42.0                            # algo más desde arriba que los otros: se ve la planta entera
    EXAGERA = 1.5
    ANILLOS = (50, 100, 200)
    COLOR_LAMINA = PanelSuperficie.COLOR_LAMINA
    PROFUNDIDAD = PanelSuperficie.PROFUNDIDAD
    COLOR = PanelVolumen.COLOR
    _aire = PanelSuperficie._aire
    _superficie_de = PanelSuperficie._superficie
    _volumen_de = PanelVolumen._volumen
    _pastilla = PanelSuperficie._pastilla
    pulsado = QtCore.Signal(str)

    def __init__(self, parent=None):
        self._focos, self._ed, self._sel, self._encima, self._siluetas = [], [], None, None, []
        self._centro, self._radio, self._pulsado_en = None, 60.0, None
        # lo que leen los métodos de dibujo de los otros visores, puesto para cada foco antes de pintarlo
        self._pol, self._h, self._clase, self._caras, self._partes, self._eje = [], 0.0, "balsa", [], [], None
        self._centro_solido = (0.0, 0.0, 0.0)
        super().__init__(parent)
        self.setMinimumHeight(self.ALTO)
        self.setMinimumWidth(220)

    def vista_inicial(self):
        super().vista_inicial()
        self._zoom = 1.1                       # el suelo hasta lo más lejano sobra a los lados: algo más cerca

    def poner(self, focos, edificios, elegido=None):
        """`focos`: los de la planta; `edificios`: los de `edificios_planta`; `elegido`, el id del que se resalta."""
        from teodors.operacion import focos as F
        eds = [e for e in edificios or [] if len(e.get("poligono") or []) >= 3]
        puntos = [tuple(v) for e in eds for v in e["poligono"]]
        for f in focos:
            u = f.get("ubicacion") or {}
            if f.get("modelo") == "superficie":
                puntos += [tuple(v) for v in u.get("poligono") or []]
            elif f.get("modelo") == "volumen" and "x" in u:
                puntos += F.planta_volumen(f)
            elif "x" in u and "y" in u:
                puntos.append((u["x"], u["y"]))
        if puntos:
            xs, ys = [x for x, _ in puntos], [y for _, y in puntos]
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            self._centro = (cx, cy)
            self._radio = max(40.0, 1.08 * max(math.hypot(x - cx, y - cy) for x, y in puntos))
        cx, cy = self._centro or (0.0, 0.0)
        cuerpos = set()
        self._focos = []
        for f in focos:
            u, m = f.get("ubicacion") or {}, f.get("modelo")
            d = {"id": f["id"], "nombre": f.get("nombre") or f["id"], "modelo": m, "olor": F.olor_ouE_s(f)}
            if m == "superficie" and len(u.get("poligono") or []) >= 3:
                d.update(pol=_antihorario([(x - cx, y - cy) for x, y in u["poligono"]]), h=max(float(f.get("altura_m") or 0.0), 0.0),
                         clase=F.clase_superficie(f))
                sobre = (f.get("superficie") or {}).get("sobre")
                if sobre:
                    cuerpos.add(sobre)
            elif m == "volumen":
                solido = _solido_volumen(f, cx, cy)
                if solido is None:
                    continue
                d.update(solido=solido, clase=F.clase_volumen(f))
            elif m == "punto" and "x" in u and "y" in u:
                d.update(xy=(u["x"] - cx, u["y"] - cy), h=float(f.get("altura_m") or 0.0), diam=(f.get("salida") or {}).get("diametro_m") or 0.6)
            else:
                continue
            self._focos.append(d)
        self._ed = [dict(e, rel=_antihorario([(x - cx, y - cy) for x, y in e["poligono"]])) for e in eds if e["id"] not in cuerpos]
        self._sel = elegido
        self.update()

    def elegir(self, id_foco):
        self._sel = id_foco
        self.update()

    def elegido(self):
        return self._sel

    def focos(self):
        return self._focos

    def _geo(self):
        alto = [f["h"] for f in self._focos if "h" in f] + [f["solido"]["medidas"][2] for f in self._focos if "solido" in f]
        return self._encuadre(self._radio, self._radio * 1.08, max([4.0] + alto + [e["altura_m"] for e in self._ed]))

    def _prof_de(self, f):
        if "pol" in f:
            return sum(self._prof(a, b) for a, b in f["pol"]) / len(f["pol"])
        if "solido" in f:
            return self._prof(*f["solido"]["centro"][:2])
        return self._prof(*f["xy"])

    # ── dibujo ───────────────────────────────────────────────────────────────────────────────────────────────
    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        marco = QtGui.QPainterPath()
        marco.addRoundedRect(QtCore.QRectF(self.rect()), 12, 12)
        p.fillPath(marco, QtGui.QColor(tema.c("fondo")))
        g = self._geo()
        self._suelo(p, g, self.ANILLOS)
        self._cardinales(p, g, g[6])
        self._siluetas = []
        cosas = [(sum(self._prof(a, b) for a, b in e["rel"]) / len(e["rel"]), "edificio", e) for e in self._ed]
        cosas += [(self._prof_de(f), "foco", f) for f in self._focos]
        elegida = None
        for _, que, x in sorted(cosas, key=lambda c: -c[0]):                                  # de lejos a cerca
            if que == "edificio":
                self._extruir(p, g, x["rel"], x["altura_m"], QtGui.QColor(COLORES["edificio"][0]))
                continue
            silueta = self._foco(p, g, x)
            self._siluetas.append((silueta, x))
            if x["id"] == self._sel:
                elegida = (silueta, x)
            elif x["id"] == self._encima:
                p.setPen(QtGui.QPen(QtGui.QColor(tema.c("texto")), 1.2))
                p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                p.drawPolygon(silueta)
        if elegida is not None:                                                                # el elegido, perfilado y con su nombre
            p.setPen(QtGui.QPen(QtGui.QColor(tema.c("acento")), 2.2))
            p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            p.drawPolygon(elegida[0])
            self._pastilla(p, elegida[0], elegida[1]["nombre"])
        self._escala(p, g)
        p.setFont(self._letra(13, True))
        p.setPen(QtGui.QColor(tema.c("texto")))
        n = len(self._focos)
        p.drawText(QtCore.QPointF(14, 22), f"{n} foco{'s' if n != 1 else ''}")
        p.setFont(self._letra(10))
        p.setPen(QtGui.QColor(tema.c("tenue")))
        p.drawText(QtCore.QRectF(0, self.height() - 22, self.width() - 12, 16), QtCore.Qt.AlignmentFlag.AlignRight, "un clic elige · arrastra gira")

    def _foco(self, p, g, f):
        """Un foco, con los métodos de su visor; devuelve su silueta proyectada."""
        if "pol" in f:
            self._pol, self._h, self._clase = f["pol"], f["h"], f["clase"]
            self._superficie_de(p, g)
            pts = [self._p(g, a, b, z) for a, b in f["pol"] for z in ({0.0, f["h"]} if f["h"] > 0.3 else {-self.PROFUNDIDAD, 0.0})]
        elif "solido" in f:
            s = f["solido"]
            self._caras, self._partes, self._eje, self._centro_solido = s["caras"], [], None, s["centro"]
            self._clase, self._h = f["clase"], None
            return self._volumen_de(p, g)
        else:                                                                                 # una chimenea
            (x, y), h = f["xy"], f["h"] or 4.0
            pie, cima = self._p(g, x, y), self._p(g, x, y, h)
            w = max(2.2, f["diam"] / 2 * g[2])
            relleno, linea = COLORES["punto"]
            p.setPen(QtGui.QPen(QtGui.QColor(linea), 1.0))
            p.setBrush(QtGui.QColor(relleno))
            p.drawRect(QtCore.QRectF(cima.x() - w, cima.y(), 2 * w, pie.y() - cima.y()))
            p.setBrush(QtGui.QColor(relleno).darker(160))
            p.drawEllipse(cima, w, w * g[3])
            return QtGui.QPolygonF([QtCore.QPointF(cima.x() - w - 2, cima.y() - 3), QtCore.QPointF(cima.x() + w + 2, cima.y() - 3),
                                    QtCore.QPointF(pie.x() + w + 2, pie.y() + 2), QtCore.QPointF(pie.x() - w - 2, pie.y() + 2)])
        return QtGui.QPolygonF([QtCore.QPointF(*q) for q in _envolvente([(q.x(), q.y()) for q in pts])])

    # ── ratón ────────────────────────────────────────────────────────────────────────────────────────────────
    def foco_en(self, pos):
        for silueta, f in reversed(self._siluetas):
            if silueta.containsPoint(QtCore.QPointF(pos), QtCore.Qt.FillRule.OddEvenFill):
                return f
        return None

    def mousePressEvent(self, e):
        self._pulsado_en = e.position()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        ini, self._pulsado_en = self._pulsado_en, None
        super().mouseReleaseEvent(e)
        if ini is None or e.button() != QtCore.Qt.MouseButton.LeftButton or (e.position() - ini).manhattanLength() > 4:
            return
        f = self.foco_en(e.position())
        if f is not None:
            self.elegir(f["id"])
            self.pulsado.emit(f["id"])

    def mouseMoveEvent(self, e):
        if self._arrastrar(e):
            return
        f = self.foco_en(e.position())
        id_ = f["id"] if f else None
        if id_ != self._encima:
            self._encima = id_
            self.update()
        if f is None:
            QtWidgets.QToolTip.hideText()
            return
        olor = f"{cifra_corta(f['olor'])} ou_E/s" if f.get("olor") else "sin olor"
        QtWidgets.QToolTip.showText(e.globalPosition().toPoint(), f"<b>{f['nombre']}</b><br>{olor}", self)

    def leaveEvent(self, _e):
        if self._encima is not None:
            self._encima = None
            self.update()


class BarraComposicion(_Pintado):
    """La mezcla del gas de salida de un punto en una barra: un tramo por componente (% en volumen), con su nombre si cabe (usuario, 2026-11-08:
    «su composición para calcular la densidad»; «añade O₂ y N₂, no aire»). Lo que falta hasta el 100 %, rayado; si pasa del 100 %, la barra en
    el color del fallo."""
    COLORES = {"CO2": "#7f8c99", "CO": "#5b6168", "CH4": "#6fbf73", "H2": "#7fc4e8", "C2H6": "#e0a458", "O2": "#9fd3c7", "N2": "#cfd5da",
               "falta": "#00000000"}
    NOMBRES = {"CO2": "CO₂", "CO": "CO", "CH4": "CH₄", "H2": "H₂", "C2H6": "C₂H₆", "O2": "O₂", "N2": "N₂", "falta": "falta"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self._comp = {}

    def poner(self, comp):
        self._comp = {k: v for k, v in comp.items() if v > 0}
        self.update()

    def suma(self):
        return sum(self._comp.values())

    def tramos(self):
        """[(componente, %)] que se pintan, en orden, con lo que falta hasta el 100 % al final («falta»)."""
        falta = 100.0 - self.suma()
        return list(self._comp.items()) + ([("falta", falta)] if falta > 1e-9 else [])

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        caja = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        marco = QtGui.QPainterPath()
        marco.addRoundedRect(caja, 7, 7)
        if self.suma() > 100.0 + 1e-9:
            p.fillPath(marco, QtGui.QColor(tema.c("fallo")))
            p.setFont(self._letra(11, True))
            p.setPen(QtGui.QColor("#ffffff"))
            p.drawText(caja, QtCore.Qt.AlignmentFlag.AlignCenter, f"{_num(self.suma(), 1)} %")
            return
        p.save()
        p.setClipPath(marco)
        x = caja.left()
        p.setFont(self._letra(11, True))
        for k, v in self.tramos():
            w = caja.width() * v / 100.0
            if k == "falta":
                p.fillRect(QtCore.QRectF(x, caja.top(), w, caja.height()),
                           QtGui.QBrush(QtGui.QColor(tema.c("borde_fuerte")), QtCore.Qt.BrushStyle.BDiagPattern))
            else:
                p.fillRect(QtCore.QRectF(x, caja.top(), w, caja.height()), QtGui.QColor(self.COLORES[k]))
            txt = f"{self.NOMBRES[k]} {_num(v, 0 if v >= 10 or v == int(v) else 1)} %"
            if p.fontMetrics().horizontalAdvance(txt) + 10 < w:
                c = QtGui.QColor(self.COLORES[k])
                oscuro = k != "falta" and 0.3 * c.red() + 0.59 * c.green() + 0.11 * c.blue() < 125
                p.setPen(QtGui.QColor("#ffffff" if oscuro else ("#1b1f22" if k != "falta" else tema.c("texto"))))
                p.drawText(QtCore.QRectF(x, caja.top(), w, caja.height()), QtCore.Qt.AlignmentFlag.AlignCenter, txt)
            x += w
        p.restore()

    def mouseMoveEvent(self, e):
        x = 0.0
        for k, v in self.tramos():
            w = self.width() * v / 100.0
            if x <= e.position().x() < x + w:
                QtWidgets.QToolTip.showText(e.globalPosition().toPoint(), f"{self.NOMBRES[k]} {_num(v, 1)} %", self)
                return
            x += w


class OlorGases(_Pintado):
    """El olor que aporta cada gas del foco, en ou_E/s por su umbral de Nagata, de mayor a menor y en escala logarítmica de cuatro órdenes. El
    primero es el dominante, que da el olor del foco (usuario, 2026-11-08: «el que tenga mayores unidades olfativas es el que predomina en el
    olor»), en el color del acento."""
    FILA, NOMBRE, VALOR = 24, 112, 104
    DECADAS = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filas = []

    def poner(self, filas):
        """filas: [(nombre, ou_E/s o None)]."""
        self._filas = sorted(filas, key=lambda t: -(t[1] or 0))
        self.setFixedHeight(self.FILA * len(self._filas) + 2)
        self.setVisible(bool(self._filas))
        self.update()

    def filas(self):
        return self._filas

    def paintEvent(self, _e):
        if not self._filas:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        tope = max((v for _, v in self._filas if v), default=0)
        ancho = self.width() - self.NOMBRE - self.VALOR - 8
        texto, tenue = QtGui.QColor(tema.c("texto")), QtGui.QColor(tema.c("tenue"))
        for k, (nombre, v) in enumerate(self._filas):
            y = k * self.FILA
            dominante = k == 0 and bool(v)
            p.setFont(self._letra(12, dominante))
            p.setPen(texto)
            p.drawText(QtCore.QRectF(2, y, self.NOMBRE - 6, self.FILA), QtCore.Qt.AlignmentFlag.AlignVCenter,
                       p.fontMetrics().elidedText(nombre, QtCore.Qt.TextElideMode.ElideRight, self.NOMBRE - 8))
            pista = QtGui.QPainterPath()
            pista.addRoundedRect(QtCore.QRectF(self.NOMBRE, y + 7, ancho, self.FILA - 14), 4, 4)
            p.fillPath(pista, QtGui.QColor(tema.c("elevada")))
            if v and tope:
                t = 1.0 + math.log10(v / tope) / self.DECADAS
                barra = QtGui.QPainterPath()
                barra.addRoundedRect(QtCore.QRectF(self.NOMBRE, y + 7, max(6.0, ancho * min(max(t, 0.0), 1.0)), self.FILA - 14), 4, 4)
                p.fillPath(barra, QtGui.QColor(tema.c("acento") if dominante else tema.c("barra_inactiva")))
            p.setPen(texto if v else tenue)
            p.drawText(QtCore.QRectF(self.width() - self.VALOR, y, self.VALOR, self.FILA),
                       QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight,
                       f"{cifra_corta(v)} ou_E/s" if v else "—")
