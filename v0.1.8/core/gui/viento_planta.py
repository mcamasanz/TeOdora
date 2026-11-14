# -*- coding: utf-8 -*-
"""El viento EN LA PLANTA, dibujado para la página de Meteorología → Reanálisis (usuario, 2026-11-07: «hacerla mucho más atractiva»):

- `CalendarioViento`: un mes, siempre abierto, cada día pintado con su viento medio en la planta y una flecha hacia donde sopla. Pinchar
  un día lo elige y el doble clic lo abre en el mapa. Es un `Calendario`, que lleva todo menos cómo se pinta cada día: el de la emisión de
  la página Focos (`focos_graficos.CalendarioEmision`) es otro.
- `FranjaHoras`: las 24 horas del día cargado, una barra por hora con su flecha; marca la hora del reproductor y lleva a la que se pinche.

Los datos salen de `operacion.viento_mapa` (`resumen_planta` y `datos_dia(...)["planta"]`). Los colores, del estilo en uso (`tema.c`) y de la
escala del viento elegida en la configuración, leídos al pintar: cambian con el estilo sin rehacer nada."""
import datetime as dt
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from teodors.comun import escalas
from teodors.comun.formato import num as _num
from teodors.gui import tema

VMAX = 8.0                        # m/s: tope de la escala de color, el de la capa del viento (`viento_mapa.VMAX`)
DIAS_SEMANA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def fecha_larga(d):
    """date → «sábado, 1 de enero de 2000»."""
    return f"{DIAS_SEMANA[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}"


def color_velocidad(ws, alfa=255):
    """El color de una velocidad en la escala del viento elegida en la configuración (de 0 a `VMAX`)."""
    lut = escalas.lut(tema.preferencia("escala_viento"))
    r, g, b = (lut[int(np.clip(ws / VMAX, 0.0, 1.0) * 255)] * 255).round().astype(int)
    return QtGui.QColor(int(r), int(g), int(b), alfa)


def _mezcla(c, fondo, alfa):
    """El color `c` sobre `fondo` con opacidad `alfa` (0-1), ya mezclado: para elegir el color del texto encima."""
    return QtGui.QColor(*(round(alfa * a + (1 - alfa) * b) for a, b in
                          ((c.red(), fondo.red()), (c.green(), fondo.green()), (c.blue(), fondo.blue()))))


def _texto_sobre(c):
    """Negro o blanco, el que se lea mejor sobre `c`."""
    lum = 0.2126 * c.redF() ** 2.2 + 0.7152 * c.greenF() ** 2.2 + 0.0722 * c.blueF() ** 2.2
    return QtGui.QColor("#101412") if lum > 0.28 else QtGui.QColor("#ffffff")


def flecha(p, cx, cy, largo, hacia, color, grosor=1.6):
    """Flecha centrada en (cx, cy) que apunta hacia `hacia` (grados desde el norte, en sentido horario)."""
    p.save()
    p.translate(cx, cy)
    p.rotate(hacia)
    p.setPen(QtGui.QPen(color, grosor, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap,
                        QtCore.Qt.PenJoinStyle.RoundJoin))
    m, a = largo / 2, max(2.5, largo * 0.32)
    p.drawLine(QtCore.QPointF(0, m), QtCore.QPointF(0, -m))
    p.drawPolyline([QtCore.QPointF(-a * 0.8, -m + a), QtCore.QPointF(0, -m), QtCore.QPointF(a * 0.8, -m + a)])
    p.restore()


class _Pintado(QtWidgets.QWidget):
    """Un widget que se pinta a mano y se repinta al cambiar de estilo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        tema.avisos.cambiado.connect(self.update)

    def _letra(self, px, negrita=False):
        f = QtGui.QFont(self.font())
        f.setPixelSize(px)
        f.setBold(negrita)
        return f


# ── el calendario del viento ─────────────────────────────────────────────────────────────────────────────────────
class _Rejilla(_Pintado):
    """Las 6 semanas del mes de un `Calendario`, pintadas a mano."""
    ESPACIO, CABECERA = 4, 20

    def __init__(self, cal):
        super().__init__(cal)
        self._cal = cal
        self._sobre = None
        self.setMouseTracking(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)          # las flechas del teclado mueven el día
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

    def _celda(self):
        w = (self.width() - 6 * self.ESPACIO) / 7
        return w, min(34.0, max(26.0, w * 0.74))

    def sizeHint(self):
        return QtCore.QSize(300, self.CABECERA + 6 * 32 + 5 * self.ESPACIO)

    def heightForWidth(self, ancho):
        h = min(34.0, max(26.0, (ancho - 6 * self.ESPACIO) / 7 * 0.74))
        return int(self.CABECERA + 6 * h + 5 * self.ESPACIO)

    def hasHeightForWidth(self):
        return True

    def resizeEvent(self, e):
        self.setFixedHeight(self.heightForWidth(self.width()))
        super().resizeEvent(e)

    def dias(self):
        """[(fecha, QRectF)] de las 6 semanas que se ven, de lunes a domingo."""
        a, m = self._cal.mes()
        primero = dt.date(a, m, 1)
        ini = primero - dt.timedelta(days=primero.weekday())
        w, h = self._celda()
        return [(ini + dt.timedelta(days=k),
                 QtCore.QRectF((k % 7) * (w + self.ESPACIO), self.CABECERA + (k // 7) * (h + self.ESPACIO), w, h))
                for k in range(42)]

    def _en(self, pos):
        return next((d for d, r in self.dias() if r.contains(pos)), None)

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        cal = self._cal
        _, mes = cal.mes()
        w, _h = self._celda()
        fondo = QtGui.QColor(tema.c("elevada"))
        tenue = QtGui.QColor(tema.c("tenue"))
        p.setFont(self._letra(11, True))
        p.setPen(tenue)
        for k, t in enumerate("LMXJVSD"):
            p.drawText(QtCore.QRectF(k * (w + self.ESPACIO), 0, w, self.CABECERA - 4), QtCore.Qt.AlignmentFlag.AlignCenter, t)
        for d, r in self.dias():
            info = cal.info(d)
            dentro, del_mes = cal.dentro(d), d.month == mes
            sel, sobre = d == cal.elegido(), d == self._sobre and dentro
            camino = QtGui.QPainterPath()
            camino.addRoundedRect(r, 7, 7)
            if not del_mes:                                    # los de los meses de al lado: solo el número, tenue
                info = None
                texto = QtGui.QColor(tema.c("apagado"))
            elif info is not None:
                relleno = _mezcla(cal.color_dia(info), QtGui.QColor(tema.c("superficie")), 0.9)
                p.fillPath(camino, relleno)
                texto = _texto_sobre(relleno)
            else:
                p.fillPath(camino, fondo if dentro else QtGui.QColor(tema.c("superficie")))
                texto = QtGui.QColor(tema.c("texto" if dentro else "apagado"))
            if sel or sobre:
                p.setPen(QtGui.QPen(QtGui.QColor(tema.c("texto" if sel else "borde_fuerte")), 2.2 if sel else 1.2))
                p.drawPath(camino)
            p.setPen(texto)
            p.setFont(self._letra(11, sel))
            p.drawText(r.adjusted(5, 3, -3, -3), QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop, str(d.day))
            if info is not None:
                cal.dibujar_dia(p, r, info, texto)

    def mouseMoveEvent(self, e):
        d = self._en(e.position())
        if d != self._sobre:
            self._sobre = d
            self.update()
        info = self._cal.info(d) if d else None
        if d is None or not self._cal.dentro(d):
            QtWidgets.QToolTip.hideText()
            return
        texto = f"<b>{fecha_larga(d).capitalize()}</b>" + (f"<br>{self._cal.texto_dia(info)}" if info else "")
        QtWidgets.QToolTip.showText(e.globalPosition().toPoint(), texto, self)

    def leaveEvent(self, _e):
        self._sobre = None
        self.update()

    def mouseReleaseEvent(self, e):
        d = self._en(e.position())
        if d is not None and self._cal.dentro(d):
            self._cal.elegir(d, avisar=True)

    TECLAS = {QtCore.Qt.Key.Key_Left: -1, QtCore.Qt.Key.Key_Right: 1, QtCore.Qt.Key.Key_Up: -7, QtCore.Qt.Key.Key_Down: 7}

    def keyPressEvent(self, e):
        """Flechas: el día de al lado (izquierda, derecha) o la semana (arriba, abajo); Intro: verlo en el mapa."""
        d = self._cal.elegido()
        if d is not None and e.key() in self.TECLAS:
            self._cal.elegir(d + dt.timedelta(days=self.TECLAS[e.key()]), avisar=True)
        elif d is not None and e.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            self._cal.abrir.emit(d.isoformat())
        else:
            super().keyPressEvent(e)

    def mouseDoubleClickEvent(self, e):
        d = self._en(e.position())
        if d is not None and self._cal.dentro(d):
            if d != self._cal.elegido():                   # el que se abre es el del doble clic, llegue o no antes su clic
                self._cal.elegir(d, avisar=True)
            self._cal.abrir.emit(d.isoformat())


class Leyenda(_Pintado):
    """La escala de color de un calendario: su nombre, la barra de colores y sus marcas. `color(t)` da el color de t, de 0 a 1, y
    `marcas()`, [(t, texto)]: se leen al pintar, así siguen al estilo y a la escala."""

    def __init__(self, texto, color, marcas, parent=None):
        super().__init__(parent)
        self.poner(texto, color, marcas)
        self.setFixedHeight(30)

    def poner(self, texto, color=None, marcas=None):
        self._texto = texto
        self._color = color or self._color
        self._marcas = marcas or self._marcas
        self.update()

    def texto(self):
        return self._texto

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        tenue = QtGui.QColor(tema.c("tenue"))
        p.setFont(self._letra(10))
        fm = p.fontMetrics()
        ancho_txt = fm.horizontalAdvance(self._texto) + 10
        x0, x1 = ancho_txt, self.width() - 8
        grad = QtGui.QLinearGradient(x0, 0, x1, 0)
        for k in range(9):
            grad.setColorAt(k / 8, self._color(k / 8))
        camino = QtGui.QPainterPath()
        camino.addRoundedRect(QtCore.QRectF(x0, 4, x1 - x0, 7), 3.5, 3.5)
        p.fillPath(camino, grad)
        p.setPen(tenue)
        p.drawText(QtCore.QRectF(0, 0, ancho_txt - 6, 15), QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft,
                   self._texto)
        for t, txt in self._marcas():
            ancho = fm.horizontalAdvance(txt) + 6
            x = min(max(x0 + (x1 - x0) * t - ancho / 2, x0 - 4), self.width() - ancho)      # sin salirse por los lados
            p.drawText(QtCore.QRectF(x, 13, ancho, 14), QtCore.Qt.AlignmentFlag.AlignCenter, txt)


class Calendario(QtWidgets.QWidget):
    """Un calendario siempre abierto: un mes, con cada día pintado por sus datos. Se cambia de mes con las flechas o desde el título (año
    y mes). Pinchar un día lo elige; el doble clic, además, lo abre. Con el calendario pinchado, las flechas del teclado mueven el día (y
    la semana) e Intro lo abre. Lo que lleva cada día lo dicen `color_dia`, `dibujar_dia` y `texto_dia`, de cada calendario."""
    elegido_cambiado = QtCore.Signal(str)        # "aaaa-mm-dd", al pinchar un día (no al elegirlo desde el código)
    abrir = QtCore.Signal(str)                   # "aaaa-mm-dd", doble clic o Intro

    def __init__(self, leyenda, parent=None):
        super().__init__(parent)
        self._dias, self._rango, self._sel = {}, None, None
        hoy = dt.date.today()
        self._mes = (hoy.year, hoy.month)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        cab = QtWidgets.QHBoxLayout()
        cab.setSpacing(4)
        self.b_ant, self.b_sig = QtWidgets.QToolButton(objectName="icono"), QtWidgets.QToolButton(objectName="icono")
        for b, ico, ayuda, paso in ((self.b_ant, "chevron_izq", "Mes anterior", -1), (self.b_sig, "chevron", "Mes siguiente", 1)):
            tema.pon_icono(b, ico, "texto", 16)
            b.setIconSize(QtCore.QSize(16, 16))
            b.setToolTip(ayuda)
            b.clicked.connect(lambda _=False, s=paso: self._mover(s))
        self.b_titulo = QtWidgets.QToolButton(objectName="cal_titulo")
        self.b_titulo.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.b_titulo.setToolTip("Ir a otro mes")
        self.b_titulo.setMenu(QtWidgets.QMenu(self.b_titulo))
        self.b_titulo.menu().aboutToShow.connect(self._menu_meses)
        cab.addStretch()                                     # las flechas del mes, junto a su nombre: las de los lados son las del día
        cab.addWidget(self.b_ant)
        cab.addWidget(self.b_titulo)
        cab.addWidget(self.b_sig)
        cab.addStretch()
        v.addLayout(cab)
        self.rejilla = _Rejilla(self)
        v.addWidget(self.rejilla)
        self.leyenda = leyenda
        v.addWidget(self.leyenda)
        tema.manos(self)
        self._pinta_cabecera()

    # lo de cada calendario
    def color_dia(self, info):
        """El color del día."""
        raise NotImplementedError

    def dibujar_dia(self, p, r, info, color):
        """Lo que va encima del color, en el rectángulo `r`, en `color` (el que se lee sobre el del día)."""

    def texto_dia(self, info):
        """Lo que dice el día al pasar por encima, después de su fecha."""
        return ""

    # lo que se consulta
    def mes(self):
        return self._mes

    def elegido(self):
        return self._sel

    def info(self, d):
        return self._dias.get(d.isoformat()) if d else None

    def dentro(self, d):
        return self._rango is not None and self._rango[0] <= d <= self._rango[1]

    # lo que se pone
    def poner_rango(self, ini, fin):
        """Primer y último día con viento (date): fuera de ellos no se elige nada."""
        self._rango = (ini, fin) if ini and fin else None
        self._pinta_cabecera()
        self.rejilla.update()

    def poner_dias(self, dias):
        """{"aaaa-mm-dd": {"media", "maxima", "hora_max", "wd", "rumbo", "calmas"}}: lo de `viento_mapa.resumen_planta`."""
        self._dias = dias or {}
        self.rejilla.update()

    def ir_a_mes(self, anio, mes):
        self._mes = (anio, mes)
        self._pinta_cabecera()
        self.rejilla.update()

    def elegir(self, d, avisar=False):
        """Elige el día `d` (date) y enseña su mes; con `avisar`, como si se hubiera pinchado. Fuera del rango, el día más cercano."""
        if self._rango is not None:
            d = min(max(d, self._rango[0]), self._rango[1])
        if avisar and d == self._sel:
            return                                             # en el borde del rango: nada cambia
        self._sel = d
        self.ir_a_mes(d.year, d.month)
        if avisar:
            self.elegido_cambiado.emit(d.isoformat())

    def _mover(self, paso):
        a, m = self._mes
        m += paso
        a, m = a + (m - 1) // 12, (m - 1) % 12 + 1
        self.ir_a_mes(a, m)

    def _limite(self, a, m):
        """¿Tiene el mes (a, m) algún día dentro del rango?"""
        if self._rango is None:
            return False
        ini, fin = self._rango
        return (ini.year, ini.month) <= (a, m) <= (fin.year, fin.month)

    def _pinta_cabecera(self):
        a, m = self._mes
        self.b_titulo.setText(f"{MESES[m - 1].capitalize()} {a}")
        self.b_ant.setEnabled(self._limite(a - (m == 1), 12 if m == 1 else m - 1))
        self.b_sig.setEnabled(self._limite(a + (m == 12), 1 if m == 12 else m + 1))

    def _menu_meses(self):
        """El menú del título: un submenú por año con sus meses (los que tienen viento)."""
        menu = self.b_titulo.menu()
        menu.clear()
        if self._rango is None:
            return
        ini, fin = self._rango
        for a in range(ini.year, fin.year + 1):
            sub = menu.addMenu(str(a))
            for m in range(1, 13):
                if self._limite(a, m):
                    acc = sub.addAction(MESES[m - 1].capitalize())
                    acc.setCheckable(True)
                    acc.setChecked((a, m) == self._mes)
                    acc.triggered.connect(lambda _=False, a=a, m=m: self.ir_a_mes(a, m))


class CalendarioViento(Calendario):
    """El calendario del viento: cada día pintado por su viento medio en la planta, con una flecha hacia donde sopla. El doble clic lo
    abre en el mapa."""

    def __init__(self, parent=None):
        marcas = [(v / VMAX, f"{v}" if v < VMAX else f"≥ {v}") for v in range(0, int(VMAX) + 1, 2)]
        super().__init__(Leyenda("Viento medio del día, m/s", lambda t: color_velocidad(VMAX * t), lambda: marcas), parent)

    def color_dia(self, info):
        return color_velocidad(info["media"])

    def dibujar_dia(self, p, r, info, color):
        if info.get("wd") is not None:
            lado = min(r.width(), r.height())
            flecha(p, r.right() - lado * 0.34, r.bottom() - lado * 0.36, lado * 0.42, (info["wd"] + 180) % 360, color, 1.5)

    def texto_dia(self, info):
        return (f"Media {_num(info['media'], 1)} m/s · máxima {_num(info['maxima'], 1)} m/s a las {info['hora_max']} UTC"
                + (f"<br>Sopla sobre todo del {info['rumbo']}" if info.get("rumbo") else "<br>En calma todo el día")
                + (f" · {info['calmas']} h en calma" if info["calmas"] else ""))


# ── las horas del día cargado ────────────────────────────────────────────────────────────────────────────────────
class FranjaHoras(_Pintado):
    """Las horas del día cargado en la planta: una barra por hora (su alto y su color, la velocidad) con una flecha hacia donde sopla
    encima. La hora del reproductor va marcada (`marcar`) y pinchar una hora lleva a ella (`hora`)."""
    hora = QtCore.Signal(int)
    ARRIBA, ABAJO = 20, 16                      # sitio de las flechas y de las horas

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ws, self._wd, self._horas, self._actual = [], [], [], None
        self.setFixedHeight(82)
        self.setMouseTracking(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def poner(self, horas, ws, wd):
        """horas: ["aaaa-mm-dd HH:MM", …] (UTC); se quedan las 24 del primer día."""
        n = min(24, len(horas))
        self._horas, self._ws, self._wd = list(horas[:n]), list(ws[:n]), list(wd[:n])
        self.update()

    def horas(self):
        return self._horas

    def marcar(self, h):
        if h != self._actual:
            self._actual = h
            self.update()

    def _columna(self):
        n = max(len(self._ws), 1)
        return self.width() / n

    def paintEvent(self, _e):
        if not self._ws:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w = self._columna()
        alto = self.height() - self.ARRIBA - self.ABAJO
        tope = max(VMAX, max(self._ws))
        tenue = QtGui.QColor(tema.c("tenue"))
        base = self.ARRIBA + alto
        p.setPen(QtGui.QPen(QtGui.QColor(tema.c("borde")), 1))
        p.drawLine(QtCore.QPointF(0, base + 0.5), QtCore.QPointF(self.width(), base + 0.5))
        p.setFont(self._letra(10))
        for k, (ws, wd) in enumerate(zip(self._ws, self._wd)):
            x = k * w
            if k == self._actual:
                marco = QtGui.QPainterPath()
                marco.addRoundedRect(QtCore.QRectF(x + 0.5, 1, w - 1, self.height() - 2), 5, 5)
                p.fillPath(marco, QtGui.QColor(tema.c("tinte")))
            h = max(2.0, alto * ws / tope)
            barra = QtGui.QPainterPath()
            barra.addRoundedRect(QtCore.QRectF(x + w * 0.18, base - h, w * 0.64, h), 2, 2)
            p.fillPath(barra, color_velocidad(ws))
            if ws >= 0.5:
                flecha(p, x + w / 2, self.ARRIBA / 2 + 1, min(14.0, w * 0.8), (wd + 180) % 360,
                       QtGui.QColor(tema.c("texto" if k == self._actual else "tenue")), 1.4)
            else:
                p.setPen(tenue)
                p.drawText(QtCore.QRectF(x, 2, w, self.ARRIBA - 4), QtCore.Qt.AlignmentFlag.AlignCenter, "·")
            if k % 3 == 0:
                p.setPen(QtGui.QColor(tema.c("texto")) if k == self._actual else tenue)
                p.drawText(QtCore.QRectF(x - 6, base + 2, w + 12, self.ABAJO - 2), QtCore.Qt.AlignmentFlag.AlignCenter,
                           self._horas[k][11:13])

    def _en(self, pos):
        k = int(pos.x() // self._columna())
        return k if 0 <= k < len(self._ws) else None

    def mouseMoveEvent(self, e):
        k = self._en(e.position())
        if k is None:
            QtWidgets.QToolTip.hideText()
            return
        from teodors.operacion.viento_mapa import rumbo
        ws, wd = self._ws[k], self._wd[k]
        texto = (f"<b>{self._horas[k][11:16]} UTC</b><br>{_num(ws, 1)} m/s"
                 + (f" del {rumbo(wd)} ({_num(wd)}°)" if ws >= 0.5 else " · calma"))
        QtWidgets.QToolTip.showText(e.globalPosition().toPoint(), texto, self)

    def mouseReleaseEvent(self, e):
        k = self._en(e.position())
        if k is not None:
            self.hora.emit(k)
