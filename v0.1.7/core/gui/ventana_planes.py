# -*- coding: utf-8 -*-
"""Ventana de los planes de operación (pedido del usuario, 2026-10-31: «planes diarios, semanales e
incluso mensuales de cada foco»). El operario los crea, guarda y carga; los focos no se tocan
(`operacion.focos`, decisión del usuario, 2026-10-25).

Tres columnas (usuario, 2026-11-09: «quitar el mapa interactivo y aprovechar todo el espacio del medio; lo desplazaría debajo de la
lista de focos para saber de qué foco hablamos, y ganamos espacio en el panel central para los calendarios»):

- A la izquierda, los focos, cada uno con su plan, y debajo el plano con el foco elegido recuadrado (gui/focos_mapa.py; el usuario,
  2026-10-31: «se pierde el mapa»), centrado en la planta y con todos los focos dentro.
- En el centro, los calendarios de la emisión con el plan abierto (lo que no se ha guardado, también), del olor o de un gas: arriba, el
  mes, cada día con la emisión media de la planta (el de la página Focos, `CalendarioEmision`), que lleva a su semana; debajo, esa semana
  como la de Outlook (`SemanaEmision`), con la operación del foco elegido y la emisión de toda la planta, hora a hora.
- A la derecha, los días del plan del foco (uno, una semana o el calendario de un mes) y el perfil de 24 h de los días elegidos, con las
  barras a golpe de ratón. Elegir un día en los calendarios del centro elige el suyo aquí, y los días con el perfil que se edita salen
  recuadrados en la semana. Un día se copia y se pega en muchos de golpe (usuario, 2026-11-09): se eligen arrastrando sobre los días (en
  el mes, un rectángulo de semanas y días de la semana), con la cabecera de un día de la semana (todos los lunes del mes), con
  «Laborables», «Fin de semana» o «Todos», o con Ctrl+clic; lo copiado se ve en un portapapeles y con el borde discontinuo en su día, y va
  también con Ctrl+C, Ctrl+V y Ctrl+A. Y la operación entera de un foco se copia a otros del mismo tipo («Copiar su operación a…»: pila 1
  a pila 2, o a todas; `focos.mismo_tipo`, `planes.copiar_operacion`).

Formato y cuentas en `operacion.planes`.

Aquí solo se CONFIGURA (el usuario, 2026-10-31): después de los focos queda elegir la meteorología, y se
simula desde el panel «Simulación» de la ventana principal.
"""
import calendar
import datetime as dt

from PySide6 import QtCore, QtGui, QtWidgets

from teodors import planta as config
from teodors.comun import registro
from teodors.gui import tema
from teodors.gui.focos_mapa import VistaFocos
from teodors.gui.tema import c
from teodors.gui.ventana_focos import ItemFoco
from teodors.gui.widgets import preguntar_si_guardar
from teodors.operacion import focos as F, planes as E

log = registro.get("planes")

ESTILO = tema.ESTILO_VENTANAS + """
QLabel#foco { font-size:17px; font-weight:600; }
QPushButton#diasemana { font-size:11px; font-weight:600; color:$tenue; background:transparent; border:none; border-radius:5px;
                        padding:2px 0px; }
QPushButton#diasemana:hover { color:$acento; background:$hover; }
QLabel#hecho { color:$acento; font-weight:600; }
QLabel#titulo_menu { font-size:14px; font-weight:600; }
QPushButton#plan { border:1px solid $borde; border-radius:0px; padding:6px 16px; background:$elevada; }
QPushButton#plan:hover { background:$hover; }
QPushButton#plan:checked { background:$acento; color:$sobre_acento; border-color:$acento; }
"""
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre")


def _pct(x):
    return f"{100 * x:.0f} %"



class CeldaDia(QtWidgets.QWidget):
    """Un día del plan: su nombre, la emisión media y las 24 barras en pequeño. Se elige con un clic y, arrastrando desde él, varios
    (`arrastrada`, con el ratón en la pantalla: la ventana sabe sobre qué día está). El día copiado lleva el borde discontinuo, como en una
    hoja de cálculo."""
    pulsada = QtCore.Signal(int, object)         # índice del día, modificadores del teclado
    arrastrada = QtCore.Signal(QtCore.QPoint)    # el ratón, aún pulsado, en coordenadas de la pantalla

    def __init__(self, indice, texto, fila=0, col=0, parent=None):
        super().__init__(parent)
        self.i, self.texto = indice, texto
        self.fila, self.col = fila, col          # su sitio en la rejilla: lo que se arrastra es un rectángulo de ella
        self.perfil, self.elegida, self.copiada = [0.0] * 24, False, False
        self.setMinimumSize(66, 46)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def poner(self, perfil, elegida, copiada=False):
        self.perfil, self.elegida, self.copiada = perfil, elegida, copiada
        self.update()

    def mousePressEvent(self, e):
        self.pulsada.emit(self.i, e.modifiers())

    def mouseMoveEvent(self, e):
        if e.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self.arrastrada.emit(self.mapToGlobal(e.position().toPoint()))

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        r = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QtGui.QPen(QtGui.QColor(c("acento") if self.elegida else c("borde")), 2 if self.elegida else 1))
        p.setBrush(QtGui.QColor(c("tinte") if self.elegida else c("elevada")))
        p.drawRoundedRect(r, 7, 7)
        if self.copiada:
            p.setPen(QtGui.QPen(QtGui.QColor(c("acento")), 1.5, QtCore.Qt.PenStyle.DashLine))
            p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(3.5, 3.5, -3.5, -3.5), 5, 5)
        p.setPen(QtGui.QColor(c("texto")))
        f = p.font()
        f.setPointSizeF(9)
        f.setBold(True)
        p.setFont(f)
        p.drawText(r.adjusted(7, 4, -6, 0), QtCore.Qt.AlignmentFlag.AlignLeft, self.texto)
        f.setBold(False)
        f.setPointSizeF(7.5)
        p.setFont(f)
        p.setPen(QtGui.QColor(c("tenue")))
        p.drawText(r.adjusted(7, 5, -6, 0), QtCore.Qt.AlignmentFlag.AlignRight, _pct(sum(self.perfil) / 24.0))
        x0, y1 = r.left() + 6, r.bottom() - 5
        ancho, alto = (r.width() - 12) / 24.0, r.height() - 30
        for k, v in enumerate(self.perfil):
            h = max(1.0, alto * min(v, 1.0))
            p.fillRect(QtCore.QRectF(x0 + k * ancho, y1 - h, max(ancho - 0.8, 1.0), h),
                       QtGui.QColor(c("acento") if v > 0 else c("barra_inactiva")))
        p.end()


class MuestraCopiado(QtWidgets.QWidget):
    """Lo copiado, como un portapapeles a la vista: el perfil en pequeño, de qué día y de qué foco es, y su media. Sin nada copiado, cómo se
    hace (usuario, 2026-11-09: «copiar un día y seleccionar varios para poder pegar todos de golpe»)."""
    VACIO = "Copia un día (Ctrl+C), elige otros y pégalo en todos de golpe (Ctrl+V)"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.perfil, self.texto = None, self.VACIO
        self.setMinimumHeight(44)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

    def poner(self, perfil, texto=None):
        self.perfil, self.texto = perfil, texto or self.VACIO
        self.update()

    def sizeHint(self):
        return QtCore.QSize(320, 44)

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        r = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        lleno = self.perfil is not None
        p.setPen(QtGui.QPen(QtGui.QColor(c("acento") if lleno else c("borde")), 1.5 if lleno else 1, QtCore.Qt.PenStyle.DashLine))
        p.setBrush(QtGui.QColor(c("tinte") if lleno else c("elevada")))
        p.drawRoundedRect(r, 7, 7)
        f = p.font()
        f.setPointSizeF(8.5)
        texto = r.adjusted(12, 0, -12, 0)
        if lleno:
            x0, y1, ancho, alto = r.left() + 10, r.bottom() - 8, 3.4, r.height() - 16
            for k, v in enumerate(self.perfil):
                h = max(1.0, alto * min(v, 1.0))
                p.fillRect(QtCore.QRectF(x0 + k * (ancho + 1), y1 - h, ancho, h), QtGui.QColor(c("acento") if v > 0 else c("barra_inactiva")))
            texto = r.adjusted(10 + 24 * (ancho + 1) + 12, 0, -12, 0)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QtGui.QColor(c("texto")))
            p.drawText(texto, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter, _pct(sum(self.perfil) / 24.0))
            texto = texto.adjusted(0, 0, -p.fontMetrics().horizontalAdvance("100 %") - 10, 0)
            f.setBold(False)
        p.setFont(f)
        p.setPen(QtGui.QColor(c("texto") if lleno else c("tenue")))
        p.drawText(texto, QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.TextFlag.TextWordWrap,
                   self.texto)
        p.end()


class ListaCopiarFoco(QtWidgets.QWidget):
    """Lo de dentro del menú «Copiar su operación a…» (usuario, 2026-11-09: «copiar una operabilidad de un foco, del mismo tipo, a otro: por
    ejemplo, pila 1 a pila 2»): los otros focos del mismo tipo, cada uno con la operación que tiene ahora, para marcar uno, varios o todos, y
    el botón que la copia. Marcar no cierra el menú. Si solo hay otro, ya va marcado."""
    copiar = QtCore.Signal(list)                 # los focos marcados
    cerrar = QtCore.Signal()

    def __init__(self, nombre, texto_plan, clase, otros, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(6)
        v.addWidget(QtWidgets.QLabel(f"Copiar la operación de {nombre}", objectName="titulo_menu"))
        v.addWidget(QtWidgets.QLabel(f"{texto_plan}  →  a otros focos del mismo tipo ({clase.lower()})", objectName="nota"))
        self.todos = QtWidgets.QCheckBox("Todos")
        self.todos.toggled.connect(self._todos)
        self.todos.setVisible(len(otros) > 1)
        v.addWidget(self.todos)
        rejilla = QtWidgets.QGridLayout()
        rejilla.setHorizontalSpacing(18)
        rejilla.setVerticalSpacing(6)
        self.marcas = {}
        for k, (id_foco, nombre_otro, plan_otro) in enumerate(otros):
            cb = QtWidgets.QCheckBox(nombre_otro)
            cb.toggled.connect(self._contar)
            rejilla.addWidget(cb, k, 0)
            rejilla.addWidget(QtWidgets.QLabel(plan_otro, objectName="nota"), k, 1, QtCore.Qt.AlignmentFlag.AlignRight)
            self.marcas[id_foco] = cb
        v.addLayout(rejilla)
        v.addSpacing(4)
        fila = QtWidgets.QHBoxLayout()
        fila.addStretch()
        b = QtWidgets.QPushButton("Cancelar")
        b.clicked.connect(self.cerrar)
        fila.addWidget(b)
        self.b_copiar = QtWidgets.QPushButton("Copiar", objectName="primario")
        self.b_copiar.clicked.connect(lambda: self.copiar.emit(self.elegidos()))
        fila.addWidget(self.b_copiar)
        v.addLayout(fila)
        if len(otros) == 1:
            next(iter(self.marcas.values())).setChecked(True)
        self._contar()
        tema.manos(self)

    def elegidos(self):
        return [k for k, cb in self.marcas.items() if cb.isChecked()]

    def _todos(self, si):
        for cb in self.marcas.values():
            cb.setChecked(si)

    def _contar(self):
        n = len(self.elegidos())
        self.b_copiar.setEnabled(n > 0)
        self.b_copiar.setText(f"Copiar a {n} foco{'s' if n != 1 else ''}" if n else "Copiar")
        self.todos.blockSignals(True)
        self.todos.setChecked(n == len(self.marcas))
        self.todos.blockSignals(False)


class EditorPerfil(QtWidgets.QWidget):
    """Perfil de 24 h (hora oficial) con las barras a golpe de ratón: de 0 a 100 %, de 5 en 5. La barra bajo el
    ratón enseña su hora y su valor, también mientras se arrastra."""
    cambiado = QtCore.Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.v = [0.0] * 24
        self._pulsado = False
        self._activa = None                      # hora de la barra que enseña su valor
        self.setMouseTracking(True)

    def poner(self, perfil):
        self.v = [float(x) for x in perfil]
        self.update()

    def _marco(self):
        return QtCore.QRectF(34, 8, max(self.width() - 42, 24), max(self.height() - 30, 20))

    def _hora(self, pos):
        m = self._marco()
        h = int((pos.x() - m.left()) // (m.width() / 24.0))
        return h if 0 <= h < 24 else None

    def _desde_raton(self, pos):
        m = self._marco()
        h = self._hora(pos)
        if h is not None:
            self.v[h] = round(min(max((m.bottom() - pos.y()) / m.height(), 0.0), 1.0) * 20) / 20
            self._activa = h
            self.update()

    def mousePressEvent(self, e):
        self._pulsado = True
        self._desde_raton(e.position())

    def mouseMoveEvent(self, e):
        if self._pulsado:
            self._desde_raton(e.position())
            return
        h = self._hora(e.position())
        if h != self._activa:
            self._activa = h
            self.update()

    def mouseReleaseEvent(self, e):
        if self._pulsado:
            self._pulsado = False
            self._activa = self._hora(e.position())
            self.cambiado.emit(list(self.v))

    def leaveEvent(self, _):
        if not self._pulsado:
            self._activa = None
            self.update()

    def _pinta_valor(self, p, m, ancho):
        """Hora y valor de la barra activa, con una línea hasta la escala."""
        k, x = self._activa, self.v[self._activa]
        y = m.bottom() - m.height() * min(x, 1.0)
        p.setPen(QtGui.QPen(QtGui.QColor(c("texto")), 1, QtCore.Qt.PenStyle.DashLine))
        p.drawLine(QtCore.QPointF(m.left(), y), QtCore.QPointF(m.left() + k * ancho, y))
        f = p.font()
        f.setPixelSize(13)
        f.setBold(True)
        p.setFont(f)
        texto = f"{k}-{k + 1} h · {_pct(x)}"
        medida = p.fontMetrics()
        w, h = medida.horizontalAdvance(texto) + 16, medida.height() + 8
        izq = min(max(m.left() + (k + 0.5) * ancho - w / 2, m.left()), m.right() - w)
        arriba = y - h - 5 if y - h - 5 >= 0 else y + 5     # si no cabe encima de la barra, dentro de ella
        r = QtCore.QRectF(izq, arriba, w, h)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(c("texto")))
        p.drawRoundedRect(r, 5, 5)
        p.setPen(QtGui.QColor(c("fondo")))
        p.drawText(r, QtCore.Qt.AlignmentFlag.AlignCenter, texto)

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        m = self._marco()
        f = p.font()
        f.setPointSizeF(8)
        p.setFont(f)
        for nivel in (0, 0.25, 0.5, 0.75, 1.0):
            y = m.bottom() - nivel * m.height()
            p.setPen(QtGui.QColor(c("borde")))
            p.drawLine(QtCore.QPointF(m.left(), y), QtCore.QPointF(m.right(), y))
            p.setPen(QtGui.QColor(c("tenue")))
            p.drawText(QtCore.QRectF(0, y - 7, 30, 14), QtCore.Qt.AlignmentFlag.AlignRight
                       | QtCore.Qt.AlignmentFlag.AlignVCenter, f"{int(nivel * 100)}")
        ancho = m.width() / 24.0
        for k, x in enumerate(self.v):
            h = max(1.5, m.height() * x)
            color = "acento_claro" if k == self._activa else "acento" if x > 0 else "barra_inactiva"
            p.fillRect(QtCore.QRectF(m.left() + k * ancho + 1, m.bottom() - h, ancho - 2, h), QtGui.QColor(c(color)))
        p.setPen(QtGui.QColor(c("tenue")))
        for hora in range(0, 25, 3):
            p.drawText(QtCore.QRectF(m.left() + hora * ancho - 14, m.bottom() + 3, 28, 14),
                       QtCore.Qt.AlignmentFlag.AlignHCenter, str(hora))
        if self._activa is not None:
            self._pinta_valor(p, m, ancho)
        p.end()


class VentanaPlanes(QtWidgets.QWidget):
    """Segunda ventana (no modal) con los planes de operación."""
    guardado = QtCore.Signal()

    def __init__(self, emp, ajustes, carpeta=None, parent=None):
        super().__init__(parent, QtCore.Qt.WindowType.Window)
        self.ajustes, self.carpeta = ajustes, carpeta
        self.setWindowTitle(f"Planes de operación · {config.APP_NOMBRE}")
        tema.estilo(self, ESTILO)
        self.resize(1600, 920)
        self.catalogo = F.cargar()
        self.esc = E.base(self.catalogo)
        self._sucio = False
        self.id_foco = None
        self.elegidos = {0}
        self.celdas = []
        self._copiado = None                              # el perfil copiado (24 factores): se pega en este foco o en otro
        self._origen = None                               # de dónde: (foco, plan, mes, día), para recuadrarlo
        self._texto_copiado = ""
        self._menu_foco = None                            # el de «Copiar su operación a…», mientras está abierto
        self._ancla = 0                                   # el último día pulsado: Mayúsculas elige el tramo desde él
        self._arrastre = None                             # (día de partida, lo elegido de antes, si se quita): arrastrando
        self._t_aviso = QtCore.QTimer(self, singleShot=True, interval=2600)
        self._mag = "olor"                                # lo que pintan los calendarios del centro: el olor o un gas
        self._dia = dt.date.today()                       # el día elegido en ellos: su semana es la que se ve
        self.botones_mag = {}

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._cabecera())
        self.divisor = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.divisor.setChildrenCollapsible(False)
        self.divisor.addWidget(self._navegacion())
        self.divisor.addWidget(self._centro())
        self.divisor.addWidget(self._derecha())
        self.divisor.setStretchFactor(1, 1)
        self.divisor.setSizes([290, 750, 560])
        lay.addWidget(self.divisor, 1)
        geom = self.ajustes.value("planes/geometria")
        if geom is not None:
            self.restoreGeometry(geom)
        div = self.ajustes.value("planes/divisor_v3")
        if div is not None:
            self.divisor.restoreState(div)
        self.mapa.listo.connect(self._mapa_listo)
        self.mapa.foco.connect(self._elegir_id)
        self.mapa.cargar(emp)
        self._poner_magnitudes()
        self._rellenar_lista()
        self._rellenar_guardados()
        tema.manos(self)
        K = QtGui.QKeySequence.StandardKey
        for tecla, accion in ((K.Copy, self._copiar), (K.Paste, self._pegar), (K.SelectAll, lambda: self._elegir_grupo("todos", False))):
            QtGui.QShortcut(QtGui.QKeySequence(tecla), self).activated.connect(accion)

    # ── construcción ─────────────────────────────────────────────────────────────────────
    def _cabecera(self):
        w = QtWidgets.QWidget(objectName="cabecera")
        w.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(18, 10, 18, 10)
        h.addWidget(QtWidgets.QLabel("Planes de operación", objectName="titulo"), 1)
        h.addWidget(QtWidgets.QLabel("Plan:"))
        self.cmb_planes = QtWidgets.QComboBox()
        self.cmb_planes.setMinimumWidth(240)
        self.cmb_planes.activated.connect(self._plan_elegido)
        h.addWidget(self.cmb_planes)
        for texto, accion in (("Nuevo…", self.nuevo), ("Duplicar…", self.duplicar)):
            b = QtWidgets.QPushButton(texto)
            b.clicked.connect(accion)
            h.addWidget(b)
        self.b_guardar = QtWidgets.QPushButton("Guardar", objectName="primario")
        self.b_guardar.setEnabled(False)
        self.b_guardar.clicked.connect(self.guardar)
        h.addWidget(self.b_guardar)
        b = QtWidgets.QPushButton("Cerrar")
        b.clicked.connect(self.close)
        h.addWidget(b)
        return w

    def _navegacion(self):
        w = QtWidgets.QWidget(objectName="nav")
        w.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        w.setMinimumWidth(220)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(10, 12, 10, 12)
        v.setSpacing(6)
        self.lbl_n = QtWidgets.QLabel(f"FOCOS ({len(self.catalogo['focos'])})", objectName="seccion")
        v.addWidget(self.lbl_n)
        self.lista = QtWidgets.QListWidget(objectName="lista")
        self.lista.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.lista.currentRowChanged.connect(self._fila_elegida)
        # debajo, el plano con el foco elegido, para saber de cuál se habla (usuario, 2026-11-09); entre los dos, un divisor
        abajo = QtWidgets.QWidget()
        va = QtWidgets.QVBoxLayout(abajo)
        va.setContentsMargins(0, 6, 0, 0)
        va.setSpacing(6)
        va.addWidget(QtWidgets.QLabel("DÓNDE ESTÁ", objectName="seccion"))
        self.mapa = VistaFocos()
        self.mapa.setMinimumHeight(200)
        va.addWidget(self.mapa, 1)
        self.divisor_nav = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.divisor_nav.setChildrenCollapsible(False)
        self.divisor_nav.addWidget(self.lista)
        self.divisor_nav.addWidget(abajo)
        self.divisor_nav.setSizes([450, 380])
        v.addWidget(self.divisor_nav, 1)
        return w

    def _centro(self):
        """Los calendarios de la emisión con el plan abierto, del olor o de un gas: el mes, arriba, y la semana del día elegido, debajo."""
        from teodors.gui.focos_graficos import CalendarioEmision, SemanaEmision
        w = QtWidgets.QWidget(objectName="centro")
        w.setMinimumWidth(520)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(18, 12, 18, 12)
        v.setSpacing(8)
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(6)
        self.lbl_calendario = QtWidgets.QLabel(objectName="seccion")
        fila.addWidget(self.lbl_calendario)
        fila.addStretch()
        self.fila_mag = QtWidgets.QHBoxLayout()
        self.fila_mag.setSpacing(6)
        fila.addLayout(self.fila_mag)
        v.addLayout(fila)
        self.cal = CalendarioEmision()
        self.cal.elegido_cambiado.connect(lambda iso: self._dia_elegido(dt.date.fromisoformat(iso)))
        v.addWidget(self.cal)
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(4)
        self.lbl_semana = QtWidgets.QLabel(objectName="foco")
        fila.addWidget(self.lbl_semana)
        fila.addStretch()
        for ico, ayuda, paso in (("chevron_izq", "Semana anterior", -7), (None, "Hoy", 0), ("chevron", "Semana siguiente", 7)):
            if ico is None:
                b = QtWidgets.QPushButton("Hoy")
                b.setToolTip("La semana de hoy")
            else:
                b = QtWidgets.QToolButton(objectName="icono")
                tema.pon_icono(b, ico, "texto", 16)
                b.setIconSize(QtCore.QSize(16, 16))
                b.setToolTip(ayuda)
            b.clicked.connect(lambda _=False, s=paso: self._dia_elegido(self._dia + dt.timedelta(days=s) if s else dt.date.today()))
            fila.addWidget(b)
        v.addLayout(fila)
        self.semana = SemanaEmision()
        self.semana.dia_pulsado.connect(lambda iso, mod: self._dia_elegido(dt.date.fromisoformat(iso), mod))
        v.addWidget(self.semana, 1)
        return w

    def _poner_magnitudes(self):
        """Un botón por lo que se emite (el olor y cada gas que emite algún foco), como en la página Focos. Se queda lo elegido si sigue."""
        try:
            mags = [(m["clave"], m["nombre"]) for m in F.magnitudes(self.catalogo)]
        except Exception as e:                                 # noqa: BLE001 (un foco a medias no tumba la ventana)
            log.warning("No se sabe qué emiten los focos: %s", e)
            mags = []
        mags = mags or [("olor", "Olor")]
        while self.fila_mag.count():
            b = self.fila_mag.takeAt(0).widget()
            if b is not None:
                b.deleteLater()
        self.botones_mag = {}
        for clave, nombre in mags:
            b = QtWidgets.QPushButton(nombre, objectName="chip_mag", checkable=True)
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=clave: self._elegir_magnitud(c))
            self.fila_mag.addWidget(b)
            self.botones_mag[clave] = b
        if self._mag not in self.botones_mag:
            self._mag = mags[0][0]
        self.botones_mag[self._mag].setChecked(True)

    def _elegir_magnitud(self, clave):
        self._mag = clave
        for k, b in self.botones_mag.items():
            b.setChecked(k == clave)
        self._pinta_calendarios()

    def _dia_elegido(self, dia, mod=None):
        """Un día elegido en los calendarios del centro (o con las flechas de la semana): se ve su semana y, en el plan del foco, se elige
        el día que le toca (con Mayúsculas o Control, como en las celdas de los días)."""
        self._dia = dia
        pf = self._pf() if self.id_foco else None
        if pf is not None:
            i = E.indice_dia(pf, dia)
            if i < len(self.celdas):
                self._dia_pulsado(i, mod if mod is not None else QtCore.Qt.KeyboardModifier.NoModifier)
                return
        self._pinta_calendarios()

    def _semana(self):
        """Las 7 fechas, de lunes a domingo, de la semana del día elegido."""
        lunes = self._dia - dt.timedelta(days=self._dia.weekday())
        return [lunes + dt.timedelta(days=k) for k in range(7)]

    def _pinta_calendarios(self):
        """El mes y la semana con el plan abierto (también lo no guardado) y lo elegido (el olor o un gas)."""
        if not hasattr(self, "semana"):
            return
        mag, unidad = self._mag, E.unidad_emision(self._mag)
        nombre = "olor" if mag == "olor" else F.NOMBRES.get(mag, mag)
        self.lbl_calendario.setText(f"CALENDARIO DE EMISIÓN · {nombre.upper() if mag == 'olor' else nombre}")
        cat, esc = self.catalogo, self.esc
        semana = self._semana()
        ini, fin = E.dias_calendario(esc)
        ini, fin = min(ini, semana[0]), max(fin, semana[-1])
        try:
            dias = E.emision_dias(esc, cat, mag, [ini + dt.timedelta(days=k) for k in range((fin - ini).days + 1)])
            tope = E.emision_maxima(cat, mag)
        except Exception as e:                                 # noqa: BLE001 (un foco o un plan a medias no tumba la ventana)
            log.warning("No se pueden pintar los calendarios de emisión: %s", e)
            dias, tope = {}, 0.0
        self.cal.poner_escala("escala_olor" if mag == "olor" else "escala_gases", tope, unidad)
        self.cal.poner_rango(ini, fin)
        self.cal.poner_dias(dias)
        self.cal.elegir(self._dia)
        foco = self._foco() if self.id_foco else None
        planta = [(dias.get(d.isoformat()) or {}).get("horas") or [0.0] * 24 for d in semana]
        if foco is None:
            self.semana.poner(semana, [[0.0] * 24] * 7, planta, [[0.0] * 24] * 7, "", "superficie", tope, unidad)
            self.lbl_semana.setText(self._texto_semana(semana))
            return
        pf = self._pf()
        try:
            suyo = E.emision_dias(esc, {"focos": [foco]}, mag, semana)
        except Exception as e:                                 # noqa: BLE001
            log.warning("No se puede calcular la emisión del foco: %s", e)
            suyo = {}
        factores = [list(E.perfil_dia(pf, E.indice_dia(pf, d))) for d in semana]
        marcados = [d for d in semana if E.indice_dia(pf, d) in self.elegidos]
        self.semana.poner(semana, [(suyo.get(d.isoformat()) or {}).get("horas") or [0.0] * 24 for d in semana], planta, factores,
                          foco.get("nombre") or foco["id"], foco.get("modelo"), tope, unidad, marcados,
                          "escala_olor" if mag == "olor" else "escala_gases")
        self.lbl_semana.setText(self._texto_semana(semana))

    @staticmethod
    def _texto_semana(semana):
        a, b = semana[0], semana[-1]
        if a.month == b.month:
            return f"Semana del {a.day} al {b.day} de {MESES[b.month - 1]} de {b.year}"
        return f"Semana del {a.day} de {MESES[a.month - 1]} al {b.day} de {MESES[b.month - 1]} de {b.year}"

    def _derecha(self):
        w = QtWidgets.QWidget(objectName="cuerpo_ficha")
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(8)
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(8)
        self.lbl_foco = QtWidgets.QLabel(objectName="foco", wordWrap=True)
        fila.addWidget(self.lbl_foco, 1)
        self.lbl_copiada = QtWidgets.QLabel(objectName="hecho")              # «Copiada a 3 focos», un momento
        fila.addWidget(self.lbl_copiada)
        # toda la operación del foco a otros del mismo tipo: pila 1 a pila 2 (usuario, 2026-11-09)
        self.b_copiar_foco = QtWidgets.QPushButton("Copiar su operación a…")
        self.b_copiar_foco.clicked.connect(self._menu_copiar_foco)
        fila.addWidget(self.b_copiar_foco, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        v.addLayout(fila)
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(0)
        self.grupo_plan = QtWidgets.QButtonGroup(self)
        self.botones_plan = {}
        for clave, texto in E.NOMBRES_PLAN.items():
            b = QtWidgets.QPushButton(texto, objectName="plan", checkable=True)
            b.clicked.connect(lambda _=False, c=clave: self._cambiar_plan(c))
            self.grupo_plan.addButton(b)
            self.botones_plan[clave] = b
            fila.addWidget(b)
        fila.addSpacing(16)
        self.lbl_mes = QtWidgets.QLabel("Mes: ")
        fila.addWidget(self.lbl_mes)
        self.cmb_mes = QtWidgets.QComboBox()
        self.cmb_anio = QtWidgets.QComboBox()
        for k, m in enumerate(MESES):
            self.cmb_mes.addItem(m, k + 1)
        hoy = dt.date.today().year
        for a in range(hoy, hoy + 3):
            self.cmb_anio.addItem(str(a), a)
        self.cmb_mes.activated.connect(lambda _: self._mes_cambiado())
        self.cmb_anio.activated.connect(lambda _: self._mes_cambiado())
        fila.addWidget(self.cmb_mes)
        fila.addWidget(self.cmb_anio)
        fila.addStretch()
        v.addLayout(fila)
        self.rejilla_w = QtWidgets.QWidget()
        self.rejilla = QtWidgets.QGridLayout(self.rejilla_w)
        self.rejilla.setContentsMargins(0, 0, 0, 0)
        self.rejilla.setSpacing(6)
        v.addWidget(self.rejilla_w)
        # varios días de una vez, sin teclas: los de diario no tienen dónde elegir (usuario, 2026-11-09)
        self.fila_elegir = QtWidgets.QWidget()
        fila = QtWidgets.QHBoxLayout(self.fila_elegir)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(6)
        fila.addWidget(QtWidgets.QLabel("ELEGIR", objectName="seccion"))
        self.botones_elegir = {}
        for clave, texto, ayuda in (("laborables", "Laborables", "De lunes a viernes"), ("finde", "Fin de semana", "Sábados y domingos"),
                                    ("todos", "Todos", "Todos los días (Ctrl+A)")):
            b = QtWidgets.QPushButton(texto, objectName="chip_mag")
            b.setToolTip(f"{ayuda} · con Ctrl, se suman a los elegidos")
            b.clicked.connect(lambda _=False, k=clave: self._elegir_grupo(k))
            fila.addWidget(b)
            self.botones_elegir[clave] = b
        fila.addSpacing(6)
        self.lbl_ayuda = QtWidgets.QLabel("o arrastra sobre los días; Ctrl+clic suma o quita uno", objectName="nota", wordWrap=True)
        self.lbl_ayuda.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        fila.addWidget(self.lbl_ayuda, 1)
        v.addWidget(self.fila_elegir)
        fila = QtWidgets.QHBoxLayout()
        self.lbl_dia = QtWidgets.QLabel(objectName="foco")
        fila.addWidget(self.lbl_dia)
        fila.addStretch()
        fila.addWidget(QtWidgets.QLabel("% de la emisión", objectName="nota"))
        v.addLayout(fila)
        self.editor = EditorPerfil()
        self.editor.setMinimumHeight(110)
        self.editor.cambiado.connect(self._perfil_editado)
        v.addWidget(self.editor, 1)
        v.addWidget(QtWidgets.QLabel("PONER DE UNA VEZ", objectName="seccion"))
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(6)
        for texto, accion in (("Todo el día", lambda: self._aplicar([1.0] * 24)),
                              ("Apagado", lambda: self._aplicar([0.0] * 24)),
                              ("Como en su ficha", self._como_ficha)):
            b = QtWidgets.QPushButton(texto)
            b.clicked.connect(accion)
            fila.addWidget(b)
        fila.addStretch()
        v.addLayout(fila)
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(6)
        self.esp_de = QtWidgets.QSpinBox(minimum=0, maximum=23, value=8, suffix=" h")
        self.esp_a = QtWidgets.QSpinBox(minimum=1, maximum=24, value=16, suffix=" h")
        self.esp_resto = QtWidgets.QSpinBox(minimum=0, maximum=100, singleStep=5, value=20, suffix=" %")
        for e in (self.esp_de, self.esp_a, self.esp_resto):
            e.setMinimumWidth(92)                # las flechas de Windows 11 tapan el número si no
        fila.addWidget(QtWidgets.QLabel("De"))
        fila.addWidget(self.esp_de)
        fila.addWidget(QtWidgets.QLabel("a"))
        fila.addWidget(self.esp_a)
        fila.addWidget(QtWidgets.QLabel("al 100 %; resto al"))
        fila.addWidget(self.esp_resto)
        b = QtWidgets.QPushButton("Poner")
        b.clicked.connect(self._poner_horario)
        fila.addWidget(b)
        fila.addStretch()
        v.addLayout(fila)
        fila = QtWidgets.QHBoxLayout()
        fila.addWidget(QtWidgets.QLabel("COPIAR Y PEGAR", objectName="seccion"))
        fila.addStretch()
        self.lbl_hecho = QtWidgets.QLabel(objectName="hecho")              # «Pegado en 16 días», un momento
        self._t_aviso.timeout.connect(self.lbl_hecho.clear)
        self._t_aviso.timeout.connect(self.lbl_copiada.clear)
        fila.addWidget(self.lbl_hecho)
        v.addLayout(fila)
        self.muestra = MuestraCopiado()
        v.addWidget(self.muestra)
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(6)
        self.b_copiar = QtWidgets.QPushButton("Copiar día")
        self.b_copiar.setToolTip("Copia el perfil del día elegido (Ctrl+C); con varios, el del primero")
        self.b_copiar.clicked.connect(lambda: self._copiar())
        fila.addWidget(self.b_copiar)
        self.b_pegar = QtWidgets.QPushButton("Pegar")
        self.b_pegar.setToolTip("Pega lo copiado en todos los días elegidos (Ctrl+V), también en otro foco")
        self.b_pegar.setEnabled(False)
        self.b_pegar.clicked.connect(lambda: self._pegar())
        fila.addWidget(self.b_pegar)
        self.b_todos = QtWidgets.QPushButton("Igual en todos los días")
        self.b_todos.setToolTip("El perfil que se ve, en todos los días del plan")
        self.b_todos.clicked.connect(self._a_todos)
        fila.addWidget(self.b_todos)
        fila.addStretch()
        v.addLayout(fila)
        area = QtWidgets.QScrollArea(objectName="ficha")
        area.setWidgetResizable(True)
        area.setMinimumWidth(560)              # 7 columnas de día: que quepan sin cortarse
        area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        area.setWidget(w)
        return area

    # ── datos ────────────────────────────────────────────────────────────────────────────
    def _foco(self):
        return next((f for f in self.catalogo["focos"] if f["id"] == self.id_foco), None)

    def _pf(self):
        return E.plan_foco(self._foco(), self.esc)

    def _rellenar_guardados(self, elegir=None):
        self.cmb_planes.blockSignals(True)
        self.cmb_planes.clear()
        self.cmb_planes.addItem(E.BASE, None)
        for nombre, ruta, _ in E.listar(self.carpeta):
            self.cmb_planes.addItem(nombre, str(ruta))
        i = self.cmb_planes.findText(elegir or self.esc.get("nombre", ""))
        self.cmb_planes.setCurrentIndex(max(i, 0))
        self.cmb_planes.blockSignals(False)

    def _rellenar_lista(self):
        fila = max(self.lista.currentRow(), 0)
        self.lista.blockSignals(True)
        self.lista.clear()
        for f in self.catalogo["focos"]:
            it = QtWidgets.QListWidgetItem()
            it.setData(QtCore.Qt.ItemDataRole.UserRole, f["id"])
            it.setSizeHint(QtCore.QSize(200, 50))
            self.lista.addItem(it)
            item = ItemFoco(f)
            item.tipo.setText(self._texto_plan(f))
            self.lista.setItemWidget(it, item)
        self.lista.blockSignals(False)
        if self.catalogo["focos"]:
            self.lista.setCurrentRow(min(fila, self.lista.count() - 1))
            self._fila_elegida(self.lista.currentRow())

    def focos_cambiados(self):
        """Se han guardado los focos (uno creado, cambiado o eliminado) con esta ventana ya hecha: la lista, el plano y el plan, con ellos.
        Un foco nuevo trae su operación por defecto, la de su ficha (`focos.funcionamiento_defecto`), y aquí se cambia (usuario,
        2026-11-09: «cada vez que se crea un foco debe crearse una operabilidad por defecto, que luego se modifica en la operación»)."""
        try:
            self.catalogo = F.cargar()
        except (ValueError, OSError) as e:
            log.error(f"No se pudieron leer los focos: {e}")
            return
        ids = {f["id"] for f in self.catalogo["focos"]}
        if self.esc.get("nombre") == E.BASE and not self._sucio:
            self.esc = E.base(self.catalogo)                  # la Base es la de las fichas: sale otra vez de ellas
        else:                                                 # un plan abierto: los nuevos con su operación; los eliminados, fuera
            self.esc["focos"] = {k: v for k, v in (self.esc.get("focos") or {}).items() if k in ids}
            for f in self.catalogo["focos"]:
                E.plan_foco(f, self.esc)
        self.lbl_n.setText(f"FOCOS ({len(self.catalogo['focos'])})")
        if self.id_foco not in ids:
            self.id_foco = None
        self._poner_magnitudes()                                   # un foco nuevo puede emitir otro gas
        self._rellenar_lista()
        self.mapa.set_focos(self.catalogo["focos"], encuadrar=False)
        if self.id_foco:
            self.mapa.elegir(self.id_foco, mostrar=False)

    def _texto_plan(self, foco):
        pf = E.plan_foco(foco, self.esc)
        return f"{E.NOMBRES_PLAN[pf['plan']]} · {_pct(E.nivel_medio(pf))}"

    # ── elegir y ver ─────────────────────────────────────────────────────────────────────
    def _fila_elegida(self, fila):
        if fila < 0:
            return
        self.id_foco = self.lista.item(fila).data(QtCore.Qt.ItemDataRole.UserRole)
        self.elegidos = {0}
        self._mostrar_foco()
        self.mapa.elegir(self.id_foco)

    def _mapa_listo(self):
        self.mapa.sin_leyenda()                                             # los colores de los modelos ya van en la lista
        self.mapa.set_focos(self.catalogo["focos"], encuadrar=False)       # la vista, la de la planta (`showEvent`)
        if self.id_foco:
            self.mapa.elegir(self.id_foco, mostrar=False)

    def showEvent(self, evento):
        """Cada vez que se abre, el plano con la vista de «Ver la planta» (usuario, 2026-11-09), con todos los focos dentro: es pequeño."""
        super().showEvent(evento)
        if not evento.spontaneous():
            self.mapa.ver_planta(entera=True)

    def _elegir_id(self, id_foco):
        """Foco pinchado en el plano."""
        for k in range(self.lista.count()):
            if self.lista.item(k).data(QtCore.Qt.ItemDataRole.UserRole) == id_foco:
                self.lista.setCurrentRow(k)
                return

    def _mostrar_foco(self):
        foco, pf = self._foco(), self._pf()
        self.lbl_foco.setText(f"{foco.get('nombre') or foco['id']}  ·  {foco['id']}")
        otros = self._otros_mismo_tipo()
        self.b_copiar_foco.setEnabled(bool(otros))
        self.b_copiar_foco.setToolTip(f"Toda la operación de este foco a otros del mismo tipo ({F.nombre_clase(foco).lower()})" if otros
                                      else f"No hay otro foco del mismo tipo ({F.nombre_clase(foco).lower()})")
        self.botones_plan[pf["plan"]].setChecked(True)
        mensual = pf["plan"] == "mensual"
        for w in (self.lbl_mes, self.cmb_mes, self.cmb_anio):
            w.setVisible(mensual)
        if mensual:
            a, m = E.anio_mes(self._mes())
            self.cmb_mes.setCurrentIndex(m - 1)
            i = self.cmb_anio.findData(a)
            if i < 0:
                self.cmb_anio.addItem(str(a), a)
                i = self.cmb_anio.count() - 1
            self.cmb_anio.setCurrentIndex(i)
        self._montar_rejilla()
        self._refrescar()

    def _mes(self):
        """El mes del plan; si aún no tiene, el que viene."""
        if not self.esc.get("mes"):
            h = dt.date.today().replace(day=1) + dt.timedelta(days=32)
            self.esc["mes"] = f"{h.year}-{h.month:02d}"
        return self.esc["mes"]

    def _montar_rejilla(self):
        while self.rejilla.count():
            it = self.rejilla.takeAt(0)
            if it.widget():
                it.widget().setParent(None)
        for c in range(7):
            self.rejilla.setColumnStretch(c, 0)
        pf = self._pf()
        self.celdas = []

        def celda(i, texto, r, c, ancho=1):
            w = CeldaDia(i, texto, r, c)
            w.setMinimumHeight(46 if pf["plan"] == "mensual" else 84)
            w.pulsada.connect(self._dia_pulsado)
            w.arrastrada.connect(self._dia_arrastrado)
            self.rejilla.addWidget(w, r, c, 1, ancho)
            self.celdas.append(w)

        if pf["plan"] == "diario":
            celda(0, "Todos los días", 0, 0, 7)
        elif pf["plan"] == "semanal":
            for k, nombre in enumerate(E.DIAS_SEMANA):
                celda(k, nombre[:3], 0, k)
                self.rejilla.setColumnStretch(k, 1)
        else:
            a, m = E.anio_mes(self._mes())
            primero, n = calendar.monthrange(a, m)
            for k, nombre in enumerate(E.DIAS_SEMANA):
                b = QtWidgets.QPushButton(nombre[:3].upper(), objectName="diasemana")        # todos esos días del mes, de un clic
                b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
                b.setToolTip(f"Elegir todos los {self._plural(nombre)} del mes · con Ctrl, se suman a los elegidos")
                b.clicked.connect(lambda _=False, k=k: self._elegir_columna(k))
                self.rejilla.addWidget(b, 0, k)
                self.rejilla.setColumnStretch(k, 1)
            for d in range(n):
                celda(d, str(d + 1), 1 + (d + primero) // 7, (d + primero) % 7)
        self.fila_elegir.setVisible(pf["plan"] != "diario")
        self.elegidos = {i for i in self.elegidos if i < len(self.celdas)} or {0}
        self._ancla = min(self.elegidos)
        self._arrastre = None

    @staticmethod
    def _plural(nombre):
        n = nombre.lower()
        return n if n.endswith("s") else n + "s"

    def _refrescar(self):
        """Celdas, editor y textos desde el plan del foco."""
        pf = self._pf()
        aqui = self._donde()
        for w in self.celdas:
            w.poner(E.perfil_dia(pf, w.i), w.i in self.elegidos, self._origen == aqui + (w.i,))
        i, n = min(self.elegidos), len(self.elegidos)
        self.editor.poner(E.perfil_dia(pf, i))
        if n > 1:                     # con perfiles distintos, se ve (y se edita sobre) el del primero: que se sepa cuál
            distintos = len({tuple(E.perfil_dia(pf, k)) for k in self.elegidos}) > 1
            self.lbl_dia.setText(f"{n} días elegidos" + (f" · se ve el {self._nombre_dia(i, corto=True).lower()}" if distintos else ""))
        else:
            self.lbl_dia.setText(self._nombre_dia(i))
        self.b_todos.setEnabled(pf["plan"] != "diario")
        self.b_pegar.setEnabled(self._copiado is not None)
        self.b_pegar.setText(f"Pegar en {n} día{'s' if n != 1 else ''}" if self._copiado is not None else "Pegar")
        self.muestra.poner(self._copiado, self._texto_copiado if self._copiado is not None else None)
        it = self.lista.currentItem()
        if it is not None:
            self.lista.itemWidget(it).tipo.setText(self._texto_plan(self._foco()))
        self._pinta_calendarios()

    # ── cambios ──────────────────────────────────────────────────────────────────────────
    def _marcar(self):
        self._sucio = True
        self.b_guardar.setEnabled(True)
        self.setWindowTitle(self.windowTitle().rstrip(" *") + " *")
        self._refrescar()

    def _nombre_dia(self, i, corto=False):
        """«Lunes», «Lunes 2 de noviembre» (o «Lunes 2», corto) o «Todos los días», según el plan."""
        plan = self._pf()["plan"]
        if plan == "diario":
            return "Todos los días"
        if plan == "semanal":
            return E.DIAS_SEMANA[i]
        a, m = E.anio_mes(self._mes())
        texto = f"{E.DIAS_SEMANA[dt.date(a, m, i + 1).weekday()]} {i + 1}"
        return texto if corto else f"{texto} de {MESES[m - 1]}"

    def _donde(self):
        """El foco, el plan y su mes: con el día, el sitio de lo copiado."""
        plan = self._pf()["plan"]
        return (self.id_foco, plan, self._mes() if plan == "mensual" else None)

    def _dia_pulsado(self, i, mod):
        """Un día pulsado, aquí o en los calendarios del centro: solo él; con Ctrl, se suma o se quita; con Mayúsculas, el tramo desde el
        último pulsado. Si se arrastra luego (`_dia_arrastrado`), se suma (o se quita) el rectángulo de días."""
        M = QtCore.Qt.KeyboardModifier
        self._arrastre = None
        if mod & M.ShiftModifier:
            a = self._ancla if self._ancla < len(self.celdas) else min(self.elegidos)
            self.elegidos = set(range(min(a, i), max(a, i) + 1))
        elif mod & M.ControlModifier:
            quitar = i in self.elegidos and len(self.elegidos) > 1
            base = self.elegidos - {i}
            self.elegidos = base if quitar else base | {i}
            self._ancla, self._arrastre = i, (i, base, quitar)
        else:
            self._ancla, self._arrastre = i, (i, set(), False)
            self.elegidos = {i}
        self._refrescar()

    def _dia_arrastrado(self, punto):
        """Arrastrando desde un día, el rectángulo de la rejilla hasta el que hay bajo el ratón: en el mes, por semanas y días de la semana
        (de martes a viernes de varias semanas, de un tirón), como en una hoja de cálculo."""
        if self._arrastre is None:
            return
        w = self.rejilla_w.childAt(self.rejilla_w.mapFromGlobal(punto))
        if not isinstance(w, CeldaDia):
            return                                     # entre dos días o fuera de la rejilla: se queda como está
        i0, base, quitar = self._arrastre
        a = self.celdas[i0]
        filas = range(min(a.fila, w.fila), max(a.fila, w.fila) + 1)
        cols = range(min(a.col, w.col), max(a.col, w.col) + 1)
        caja = {x.i for x in self.celdas if x.fila in filas and x.col in cols}
        nuevos = ((base - caja) if quitar else (base | caja)) or {w.i}
        if nuevos != self.elegidos:
            self.elegidos = nuevos
            self._refrescar()

    def _dias_semana_plan(self):
        """El día de la semana (0, el lunes) de cada día del plan; en el diario, ninguno."""
        pf = self._pf()
        if pf["plan"] == "semanal":
            return list(range(7))
        if pf["plan"] == "mensual":
            a, m = E.anio_mes(self._mes())
            primero, n = calendar.monthrange(a, m)
            return [(primero + d) % 7 for d in range(n)]
        return [None]

    def _elegir(self, dias, sumar=None):
        """Elegir esos días; con Ctrl pulsado (o `sumar`), sumados a los que ya lo están."""
        if not dias or not self.id_foco:
            return
        if sumar is None:
            sumar = bool(QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.KeyboardModifier.ControlModifier)
        self.elegidos = (self.elegidos | set(dias)) if sumar else set(dias)
        self._ancla, self._arrastre = min(dias), None
        self._refrescar()

    def _elegir_columna(self, k, sumar=None):
        """Todos los lunes (o martes…) del mes: la cabecera de su columna."""
        self._elegir({i for i, d in enumerate(self._dias_semana_plan()) if d == k}, sumar)

    def _elegir_grupo(self, clave, sumar=None):
        """Los laborables, el fin de semana o todos los días del plan."""
        quiere = {"laborables": range(5), "finde": (5, 6), "todos": range(7)}[clave]
        self._elegir({i for i, d in enumerate(self._dias_semana_plan()) if d is None or d in quiere}, sumar)

    def _cambiar_plan(self, plan):
        pf = self._pf()
        if plan == pf["plan"]:
            return
        E.cambiar_plan(pf, plan, self._mes() if "mensual" in (plan, pf["plan"]) else None)
        self.elegidos = {0}
        self._mostrar_foco()
        self._marcar()

    def _mes_cambiado(self):
        self.esc["mes"] = f"{self.cmb_anio.currentData()}-{self.cmb_mes.currentData():02d}"
        self.elegidos = {0}
        self._montar_rejilla()
        self._marcar()

    def _perfil_editado(self, perfil):
        self._aplicar(perfil)

    def _aplicar(self, perfil):
        E.poner_perfil(self._pf(), sorted(self.elegidos), perfil)
        self._marcar()

    def _como_ficha(self):
        self._aplicar(F.perfil(self._foco()))

    def _poner_horario(self):
        de, a, resto = self.esp_de.value(), self.esp_a.value(), self.esp_resto.value() / 100.0
        if a <= de:
            QtWidgets.QMessageBox.warning(self, "Horario", "La hora final tiene que ser mayor que la inicial.")
            return
        self._aplicar([1.0 if de <= h < a else resto for h in range(24)])

    def _copiar(self):
        """El perfil del día elegido (del primero, si hay varios) al portapapeles de la ventana; se queda al cambiar de foco."""
        if not self.id_foco:
            return
        i, foco = min(self.elegidos), self._foco()
        self._copiado = list(E.perfil_dia(self._pf(), i))
        self._origen = self._donde() + (i,)
        self._texto_copiado = f"Copiado: {self._nombre_dia(i)} · {foco.get('nombre') or foco['id']}"
        self._refrescar()

    def _pegar(self):
        """Lo copiado, en todos los días elegidos de una vez (usuario, 2026-11-09)."""
        if self._copiado is None or not self.id_foco:
            return
        n = len(self.elegidos)
        self._aplicar(list(self._copiado))
        self.lbl_hecho.setText(f"Pegado en {n} día{'s' if n != 1 else ''}")
        self._t_aviso.start()

    def _otros_mismo_tipo(self):
        foco = self._foco()
        return [f for f in self.catalogo["focos"] if foco is not None and f["id"] != foco["id"] and F.mismo_tipo(foco, f)]

    def _menu_copiar_foco(self):
        """El menú de «Copiar su operación a…»: los otros focos del mismo tipo, para marcar (`ListaCopiarFoco`), bajo el botón y a su derecha."""
        foco, otros = self._foco(), self._otros_mismo_tipo()
        if foco is None or not otros:
            return
        menu = QtWidgets.QMenu(self)
        lista = ListaCopiarFoco(foco.get("nombre") or foco["id"], self._texto_plan(foco), F.nombre_clase(foco),
                                [(f["id"], f.get("nombre") or f["id"], self._texto_plan(f)) for f in otros])
        accion = QtWidgets.QWidgetAction(menu)
        accion.setDefaultWidget(lista)
        menu.addAction(accion)
        lista.cerrar.connect(menu.close)
        lista.copiar.connect(lambda ids: (menu.close(), self._copiar_foco(ids)))
        self._menu_foco = menu
        b = self.b_copiar_foco
        menu.popup(b.mapToGlobal(QtCore.QPoint(b.width() - menu.sizeHint().width(), b.height() + 4)))

    def _copiar_foco(self, ids):
        """La operación del foco elegido en esos otros (`planes.copiar_operacion`); el plan, sin guardar, como cualquier cambio."""
        if not ids or not self.id_foco:
            return
        self._pf()                                                  # que el foco de origen figure en el plan
        E.copiar_operacion(self.esc, self.id_foco, ids)
        for k in range(self.lista.count()):                         # la operación de cada fila, al día
            it = self.lista.item(k)
            f = next((f for f in self.catalogo["focos"] if f["id"] == it.data(QtCore.Qt.ItemDataRole.UserRole)), None)
            if f is not None:
                self.lista.itemWidget(it).tipo.setText(self._texto_plan(f))
        n = len(ids)
        self.lbl_copiada.setText(f"Copiada a {n} foco{'s' if n != 1 else ''}")
        self._t_aviso.start()
        self._marcar()

    def _a_todos(self):
        antes, perfil = self.elegidos, list(self.editor.v)
        self.elegidos = set(range(len(self._pf()["dias"])))
        self._aplicar(perfil)
        self.elegidos = antes
        self._refrescar()

    # ── planes guardados ─────────────────────────────────────────────────────────────────
    def _seguir_sin_guardar(self):
        """¿Se puede dejar el plan abierto? Pregunta si hay cambios sin guardar."""
        if not self._sucio:
            return True
        B = QtWidgets.QMessageBox.StandardButton
        r = preguntar_si_guardar(self, "Plan sin guardar", "Hay cambios sin guardar. ¿Guardarlos?")
        if r == B.Cancel:
            return False
        return self.guardar() if r == B.Save else True

    def _abrir(self, esc):
        self.esc = esc
        self._sucio = False
        self.b_guardar.setEnabled(False)
        self.setWindowTitle(self.windowTitle().rstrip(" *"))
        self._rellenar_lista()

    def _plan_elegido(self, _):
        ruta = self.cmb_planes.currentData()
        if not self._seguir_sin_guardar():
            self._rellenar_guardados()
            return
        try:
            self._abrir(E.cargar(ruta) if ruta else E.base(self.catalogo))
            log.info(f"Plan «{self.esc['nombre']}» abierto.")
        except (ValueError, OSError) as e:
            log.error(f"No se pudo abrir el plan: {e}")
        self._rellenar_guardados()

    def _pedir_nombre(self, titulo, propuesta=""):
        nombre, ok = QtWidgets.QInputDialog.getText(self, titulo, "Nombre del plan:", text=propuesta)
        nombre = nombre.strip()
        if not ok or not nombre:
            return None
        if nombre == E.BASE:
            QtWidgets.QMessageBox.warning(self, titulo, "«Base» es el plan de las fichas: elige otro nombre.")
            return None
        return nombre

    def nuevo(self):
        if not self._seguir_sin_guardar():
            return
        nombre = self._pedir_nombre("Plan nuevo")
        if nombre:
            self._abrir(E.nuevo(self.catalogo, nombre))
            self._marcar()
            self._rellenar_guardados()

    def duplicar(self):
        nombre = self._pedir_nombre("Duplicar el plan", f"{self.esc.get('nombre')} (copia)")
        if nombre:
            copia = E.nuevo(self.catalogo, nombre, self.esc)
            self._abrir(copia)
            self._marcar()
            self._rellenar_guardados()

    def guardar(self):
        """Guarda el plan abierto; si es la Base, pide un nombre. True si se ha guardado."""
        if self.esc.get("nombre") == E.BASE:
            nombre = self._pedir_nombre("Guardar el plan")
            if not nombre:
                return False
            self.esc = E.nuevo(self.catalogo, nombre, self.esc)
        try:
            ruta = E.guardar(self.esc, self.carpeta)
        except (ValueError, OSError) as e:
            log.error(f"No se pudo guardar el plan: {e}")
            QtWidgets.QMessageBox.warning(self, "Guardar el plan", str(e))
            return False
        log.info(f"Plan «{self.esc['nombre']}» guardado en {ruta}.")
        self._sucio = False
        self.b_guardar.setEnabled(False)
        self.setWindowTitle(self.windowTitle().rstrip(" *"))
        self._rellenar_guardados(self.esc["nombre"])
        self.guardado.emit()
        return True

    def _volver_a_lo_guardado(self):
        """Tras «No guardar» al cerrar: al volver a abrir, el plan como estaba guardado (la Base, si nunca se guardó)."""
        ruta = next((r for n, r, _ in E.listar(self.carpeta) if n == self.esc.get("nombre")), None)
        try:
            self._abrir(E.cargar(ruta) if ruta else E.base(self.catalogo))
        except (ValueError, OSError) as e:
            log.error(f"No se pudo volver a abrir el plan: {e}")
            self._abrir(E.base(self.catalogo))
        self._rellenar_guardados()

    def closeEvent(self, evento):
        if not self._seguir_sin_guardar():
            evento.ignore()
            return
        if self._sucio:
            self._volver_a_lo_guardado()
        self.ajustes.setValue("planes/geometria", self.saveGeometry())
        self.ajustes.setValue("planes/divisor_v3", self.divisor.saveState())
        super().closeEvent(evento)
