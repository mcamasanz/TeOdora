# -*- coding: utf-8 -*-
"""Ventana de los planes de operación (pedido del usuario, 2026-10-31: «planes diarios, semanales e
incluso mensuales de cada foco»). El operario los crea, guarda y carga; los focos no se tocan
(`operacion.focos`, decisión del usuario, 2026-10-25).

Como la ventana de focos: a la izquierda, los focos, cada uno con su plan; en el centro, el plano con el
foco elegido recuadrado (gui/focos_mapa.py; el usuario, 2026-10-31: «se pierde el mapa»); a la derecha, los
días del foco (uno, una semana o el calendario de un mes) y el perfil de 24 h de los días elegidos, con las
barras a golpe de ratón. Formato y cuentas en `operacion.planes`.

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
QLabel#diasemana { font-size:11px; font-weight:600; color:$tenue; }
QPushButton#plan { border:1px solid $borde; border-radius:0px; padding:6px 16px; background:$elevada; }
QPushButton#plan:hover { background:$hover; }
QPushButton#plan:checked { background:$acento; color:$sobre_acento; border-color:$acento; }
"""
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre")


def _pct(x):
    return f"{100 * x:.0f} %"



class CeldaDia(QtWidgets.QWidget):
    """Un día del plan: su nombre, la emisión media y las 24 barras en pequeño."""
    pulsada = QtCore.Signal(int, object)         # índice del día, modificadores del teclado

    def __init__(self, indice, texto, parent=None):
        super().__init__(parent)
        self.i, self.texto = indice, texto
        self.perfil, self.elegida = [0.0] * 24, False
        self.setMinimumSize(66, 46)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def poner(self, perfil, elegida):
        self.perfil, self.elegida = perfil, elegida
        self.update()

    def mousePressEvent(self, e):
        self.pulsada.emit(self.i, e.modifiers())

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        r = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QtGui.QPen(QtGui.QColor(c("acento") if self.elegida else c("borde")), 2 if self.elegida else 1))
        p.setBrush(QtGui.QColor(c("tinte") if self.elegida else c("elevada")))
        p.drawRoundedRect(r, 7, 7)
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
        self.resize(1400, 860)
        self.catalogo = F.cargar()
        self.esc = E.base(self.catalogo)
        self._sucio = False
        self.id_foco = None
        self.elegidos = {0}
        self.celdas = []
        self._copiado = None

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._cabecera())
        self.divisor = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.divisor.setChildrenCollapsible(False)
        self.divisor.addWidget(self._navegacion())
        self.mapa = VistaFocos()
        self.mapa.setMinimumWidth(360)
        self.divisor.addWidget(self.mapa)
        self.divisor.addWidget(self._derecha())
        self.divisor.setStretchFactor(1, 1)
        self.divisor.setSizes([300, 520, 580])
        lay.addWidget(self.divisor, 1)
        geom = self.ajustes.value("planes/geometria")
        if geom is not None:
            self.restoreGeometry(geom)
        div = self.ajustes.value("planes/divisor_v2")
        if div is not None:
            self.divisor.restoreState(div)
        self.mapa.listo.connect(self._mapa_listo)
        self.mapa.foco.connect(self._elegir_id)
        self.mapa.cargar(emp)
        self._rellenar_lista()
        self._rellenar_guardados()
        tema.manos(self)

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
        v.addWidget(QtWidgets.QLabel(f"FOCOS ({len(self.catalogo['focos'])})", objectName="seccion"))
        self.lista = QtWidgets.QListWidget(objectName="lista")
        self.lista.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.lista.currentRowChanged.connect(self._fila_elegida)
        v.addWidget(self.lista, 1)
        return w

    def _derecha(self):
        w = QtWidgets.QWidget(objectName="cuerpo_ficha")
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(8)
        self.lbl_foco = QtWidgets.QLabel(objectName="foco", wordWrap=True)
        v.addWidget(self.lbl_foco)
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
        fila.setSpacing(6)
        b = QtWidgets.QPushButton("Copiar día")
        b.clicked.connect(lambda: self._copiar())
        fila.addWidget(b)
        self.b_pegar = QtWidgets.QPushButton("Pegar")
        self.b_pegar.setEnabled(False)
        self.b_pegar.clicked.connect(lambda: self._aplicar(self._copiado))
        fila.addWidget(self.b_pegar)
        self.b_todos = QtWidgets.QPushButton("Igual en todos los días")
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
        self.mapa.set_focos(self.catalogo["focos"], encuadrar=True)
        if self.id_foco:
            self.mapa.elegir(self.id_foco, mostrar=False)

    def _elegir_id(self, id_foco):
        """Foco pinchado en el plano."""
        for k in range(self.lista.count()):
            if self.lista.item(k).data(QtCore.Qt.ItemDataRole.UserRole) == id_foco:
                self.lista.setCurrentRow(k)
                return

    def _mostrar_foco(self):
        foco, pf = self._foco(), self._pf()
        self.lbl_foco.setText(f"{foco.get('nombre') or foco['id']}  ·  {foco['id']}")
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
            w = CeldaDia(i, texto)
            w.setMinimumHeight(46 if pf["plan"] == "mensual" else 84)
            w.pulsada.connect(self._dia_pulsado)
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
                self.rejilla.addWidget(QtWidgets.QLabel(nombre[:3].upper(), objectName="diasemana"), 0, k)
                self.rejilla.setColumnStretch(k, 1)
            for d in range(n):
                celda(d, str(d + 1), 1 + (d + primero) // 7, (d + primero) % 7)
        self.elegidos = {i for i in self.elegidos if i < len(self.celdas)} or {0}

    def _refrescar(self):
        """Celdas, editor y textos desde el plan del foco."""
        pf = self._pf()
        for w in self.celdas:
            w.poner(E.perfil_dia(pf, w.i), w.i in self.elegidos)
        i = min(self.elegidos)
        self.editor.poner(E.perfil_dia(pf, i))
        if len(self.elegidos) > 1:
            self.lbl_dia.setText(f"{len(self.elegidos)} días elegidos")
        elif pf["plan"] == "diario":
            self.lbl_dia.setText("Todos los días")
        elif pf["plan"] == "semanal":
            self.lbl_dia.setText(E.DIAS_SEMANA[i])
        else:
            a, m = E.anio_mes(self._mes())
            self.lbl_dia.setText(f"{E.DIAS_SEMANA[dt.date(a, m, i + 1).weekday()]} {i + 1} de {MESES[m - 1]}")
        self.b_todos.setEnabled(pf["plan"] != "diario")
        it = self.lista.currentItem()
        if it is not None:
            self.lista.itemWidget(it).tipo.setText(self._texto_plan(self._foco()))

    # ── cambios ──────────────────────────────────────────────────────────────────────────
    def _marcar(self):
        self._sucio = True
        self.b_guardar.setEnabled(True)
        self.setWindowTitle(self.windowTitle().rstrip(" *") + " *")
        self._refrescar()

    def _dia_pulsado(self, i, mod):
        if mod & QtCore.Qt.KeyboardModifier.ShiftModifier:
            a = min(self.elegidos)
            self.elegidos = set(range(min(a, i), max(a, i) + 1))
        elif mod & QtCore.Qt.KeyboardModifier.ControlModifier:
            self.elegidos ^= {i}
            self.elegidos = self.elegidos or {i}
        else:
            self.elegidos = {i}
        self._refrescar()

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
        self._copiado = list(E.perfil_dia(self._pf(), min(self.elegidos)))
        self.b_pegar.setEnabled(True)

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
        self.ajustes.setValue("planes/divisor_v2", self.divisor.saveState())
        super().closeEvent(evento)
