# -*- coding: utf-8 -*-
"""La barra de encima del mapa en la página Simular (usuario, 2026-11-17: «en simulación hay un panel superior en el mapa… un desplegable
con las variables a pintar, otro de si lo quieres ver como isolíneas o degradado, además otro de guardar imagen»; y luego, sus botones:
«variable, isolíneas o degradado, escala logarítmica o normal, rango de la escala, transparencia, encuadre a la nave, a la zona intermedia
o a la zona completa, copiar imagen y guardar imagen»). Sustituye a los botones del panel con los que se elegía qué se ve en el mapa y cómo.

Con iconos, como la de ParaView (usuario, el mismo día: «más botones con iconos, estilo paraview»; y, al ver el boceto, «muchísimo
mejor»): botones pequeños, solo con su dibujo, en grupos separados por una raya; al pasar el ratón, cada uno dice lo que hace. La variable
y la paleta de colores, en desplegables; la paleta y ver u ocultar la leyenda, propuestos con el boceto. La barra solo avisa de lo que se
elige (sus señales); lo pinta la ventana.
"""
from PySide6 import QtCore, QtGui, QtWidgets

from teodors.gui import tema
from teodors.gui.ventana_ajustes import SelectorEscala


def _num(x):
    """Un número del rango, con coma y sin ceros de más: 0,01 · 2,5 · 1000."""
    return f"{x:.6g}".replace(".", ",")


def leer_num(texto):
    """Un número escrito con coma o con punto, o None si no lo es."""
    try:
        return float(texto.strip().replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def imagen_con_titulo(imagen, titulo, pie=""):
    """La imagen del mapa (con su leyenda y su escala) con su título encima y, si lo hay, un pie debajo: fondo blanco y texto oscuro, para
    pegarla en un correo o en un documento (copiar o guardar la imagen)."""
    margen, alto_t, alto_p = 12, 36, (24 if pie else 0)
    salida = QtGui.QImage(imagen.width(), imagen.height() + alto_t + alto_p, QtGui.QImage.Format.Format_RGB32)
    salida.fill(QtGui.QColor("#ffffff"))
    p = QtGui.QPainter(salida)
    letra = QtGui.QFont(QtWidgets.QApplication.font())
    letra.setPixelSize(16)
    letra.setBold(True)
    p.setFont(letra)
    p.setPen(QtGui.QColor("#1b1f24"))
    izquierda = QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
    p.drawText(QtCore.QRect(margen, 0, imagen.width() - 2 * margen, alto_t), izquierda, titulo)
    p.drawImage(0, alto_t, imagen)
    if pie:
        letra.setPixelSize(12)
        letra.setBold(False)
        p.setFont(letra)
        p.setPen(QtGui.QColor("#5b636e"))
        p.drawText(QtCore.QRect(margen, alto_t + imagen.height(), imagen.width() - 2 * margen, alto_p), izquierda, pie)
    p.end()
    return salida


class Flujo(QtWidgets.QLayout):
    """Los grupos de la barra en una fila; si no caben, siguen en la de abajo, como el texto. El de `a_la_derecha`, al final de la última."""

    def __init__(self, parent=None, margen=(10, 6, 10, 6), hueco=(8, 6)):
        super().__init__(parent)
        self._items, self._derecha = [], None
        self.setContentsMargins(*margen)
        self._hx, self._hy = hueco

    def addItem(self, item):
        self._items.append(item)

    def a_la_derecha(self, w):
        """Un grupo pegado al borde derecho, en la última fila (si no cabe en ella, en otra)."""
        self.addWidget(w)
        self._derecha = self._items[-1]

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        if not 0 <= i < len(self._items):
            return None
        it = self._items.pop(i)
        if it is self._derecha:
            self._derecha = None
        return it

    def expandingDirections(self):
        return QtCore.Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, ancho):
        return self._colocar(QtCore.QRect(0, 0, ancho, 0), probar=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._colocar(rect, probar=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        t = QtCore.QSize()
        for it in self._items:
            t = t.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return t + QtCore.QSize(m.left() + m.right(), m.top() + m.bottom())

    def _colocar(self, rect, probar):
        """Coloca los grupos (o, con `probar`, solo mide): de izquierda a derecha, bajando de fila si no caben. Devuelve el alto."""
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        filas, fila, x = [], [], r.x()
        for it in self._items:
            if it is self._derecha or (it.widget() is not None and it.widget().isHidden()):
                continue
            t = it.sizeHint()
            if fila and x + t.width() > r.right() + 1:
                filas.append(fila)
                fila, x = [], r.x()
            fila.append((it, x, t))
            x += t.width() + self._hx
        d = self._derecha
        if d is not None and not (d.widget() is not None and d.widget().isHidden()):
            t = d.sizeHint()
            if fila and x + t.width() > r.right() + 1:
                filas.append(fila)
                fila = []
            fila.append((d, max(r.x(), r.right() + 1 - t.width()), t))
        if fila:
            filas.append(fila)
        y = r.y()
        for fila in filas:                                    # cada fila, con sus grupos centrados en su alto
            alto = max(t.height() for _, _, t in fila)
            if not probar:
                for it, x, t in fila:
                    it.setGeometry(QtCore.QRect(QtCore.QPoint(x, y + (alto - t.height()) // 2), t))
            y += alto + self._hy
        return (y - self._hy if filas else r.y()) - rect.y() + m.bottom()


class BarraMapa(QtWidgets.QFrame):
    variable = QtCore.Signal(str)                 # la capa que se ve: «plan_norma», «dia_media», «penacho», «comp_maximo»…
    estilo = QtCore.Signal(str)                   # «isolineas» o «degradado»
    escala = QtCore.Signal(str)                   # «log» o «lineal»
    rango = QtCore.Signal(object)                 # (vmin, vmax), o None: el automático
    paleta = QtCore.Signal(str)                   # la paleta de colores del olor («turbo», «viridis»…): la de la configuración
    leyenda = QtCore.Signal(bool)                 # ver u ocultar la leyenda del mapa
    opacidad = QtCore.Signal(float)               # de 0 a 1
    encuadre = QtCore.Signal(str)                 # «nave», «intermedia» o «completa»
    copiar = QtCore.Signal()
    guardar = QtCore.Signal()

    # (clave, icono, ayuda)
    ESTILOS = (("isolineas", "isolineas", "Isolíneas: franjas de color entre niveles, con sus líneas"),
               ("degradado", "degradado", "Degradado: color continuo, como el penacho"))
    ESCALAS = (("log", "escala_log", "Escala logarítmica: un tramo por cada orden de magnitud (de 0,01 a 0,1, de 0,1 a 1…)"),
               ("lineal", "escala_lineal", "Escala normal: el color, en proporción al valor"))
    # los km, los de la ventana (`VentanaPrincipal.ENCUADRE_KM`)
    ENCUADRES = (("nave", "encuadre_nave", "Encuadrar la planta: 1 km alrededor"),
                 ("intermedia", "encuadre_intermedia", "Encuadrar la zona intermedia: 10 km alrededor de la planta"),
                 ("completa", "encuadre_completa", "Encuadrar todo el dominio de cálculo"))
    TRANSPARENCIA_MAX = 90                        # %: con más, casi no se vería
    HUECO = 17                                    # px entre dos grupos; en medio, su raya
    # en la escala logarítmica, «desde» no baja de aquí: lo de menos (también 0) se fija en este valor (usuario, 2026-11-17); el mismo que
    # el del cálculo (`simulacion.MINIMO_LOG`)
    MINIMO_LOG = 0.001

    def __init__(self, opacidad=0.85, parent=None):
        super().__init__(parent, objectName="barra_mapa")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Minimum)
        flujo = Flujo(self, margen=(10, 4, 10, 4), hueco=(self.HUECO, 4))
        self._escala_actual = "log"
        self._rango_mostrado, self._rango_auto = None, True
        # la variable: las del resultado que se ve (`poner_variables`)
        self.cmb_var = QtWidgets.QComboBox()
        self.cmb_var.setMinimumWidth(96)
        self.cmb_var.setPlaceholderText("Ninguna")
        self.cmb_var.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.cmb_var.setToolTip("La variable que se ve en el mapa")
        self.cmb_var.activated.connect(lambda i: self.variable.emit(self.cmb_var.itemData(i)))
        self.g_variable = self._grupo(self._etiqueta("capas", "La variable que se ve en el mapa"), self.cmb_var)
        # ver como y la escala: dos iconos cada uno, uno marcado
        self._b_estilo = self._opciones(self.ESTILOS, self.estilo.emit, "isolineas")
        self.g_estilo = self._grupo(*self._b_estilo.values())
        self._b_escala = self._opciones(self.ESCALAS, self._escala_elegida, "log")
        self.g_escala = self._grupo(*self._b_escala.values())
        # el rango: desde, hasta y volver al automático
        self.ed_min, self.ed_max = QtWidgets.QLineEdit(), QtWidgets.QLineEdit()
        for ed, ayuda in ((self.ed_min, "Desde: lo de debajo no se pinta"), (self.ed_max, "Hasta: lo de encima, con el color del final")):
            ed.setFixedWidth(58)                         # cabe «0,001» (el mínimo de la escala logarítmica)
            ed.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
            ed.setToolTip(ayuda)
            ed.editingFinished.connect(self._rango_escrito)
        self.b_auto = self._boton("rango_auto", "Volver al rango automático")
        self.b_auto.clicked.connect(lambda: self.rango.emit(None))
        self.g_rango = self._grupo(self.ed_min, QtWidgets.QLabel("–"), self.ed_max, self.b_auto)
        # la paleta de colores (la de la configuración) y la leyenda
        self.sel_paleta = SelectorEscala(self.paleta.emit, ancho=44, alto=12)
        self.sel_paleta.setToolTip("La paleta de colores del olor: la misma que en la configuración, y se queda para la próxima vez")
        self.b_leyenda = self._boton("leyenda", "Ver u ocultar la leyenda del mapa", marcado=True)
        self.b_leyenda.toggled.connect(self.leyenda.emit)
        self.g_paleta = self._grupo(self.sel_paleta, self.b_leyenda)
        # la transparencia
        self.sl_transp = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, minimum=0, maximum=self.TRANSPARENCIA_MAX)
        self.sl_transp.setFixedWidth(64)
        self.sl_transp.setValue(round(100 * (1 - opacidad)))
        self.sl_transp.setToolTip("La transparencia de lo simulado")
        self.lbl_transp = QtWidgets.QLabel(objectName="nota")
        self.lbl_transp.setFixedWidth(34)
        self.sl_transp.valueChanged.connect(self._transparencia)
        self.g_transp = self._grupo(self._etiqueta("transparencia", "La transparencia de lo simulado"), self.sl_transp, self.lbl_transp)
        self._transparencia(self.sl_transp.value(), avisar=False)
        # el encuadre: botones que mueven el mapa (no se quedan marcados)
        self._b_encuadre = {}
        for clave, icono, ayuda in self.ENCUADRES:
            b = self._boton(icono, ayuda)
            b.clicked.connect(lambda _=False, c=clave: self.encuadre.emit(c))
            self._b_encuadre[clave] = b
        self.g_encuadre = self._grupo(*self._b_encuadre.values())
        # la imagen, copiarla o guardarla con su título: al final de la barra
        self.b_copiar = self._boton("copiar", "Copiar la imagen del mapa, con su título y su leyenda, para pegarla en un correo o en un documento")
        self.b_copiar.clicked.connect(self.copiar)
        self.b_guardar = self._boton("camara", "Guardar la imagen del mapa, con su título y su leyenda, en un fichero PNG")
        self.b_guardar.clicked.connect(self.guardar)
        self.g_imagen = self._grupo(self.b_copiar, self.b_guardar)
        self._grupos = (self.g_variable, self.g_estilo, self.g_escala, self.g_rango, self.g_paleta, self.g_transp, self.g_encuadre,
                        self.g_imagen)
        for g in self._grupos[:-1]:
            flujo.addWidget(g)
        flujo.a_la_derecha(self.g_imagen)
        tema.manos(self)

    # ── construcción ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def _grupo(*widgets):
        """Un grupo de la barra: sus controles, juntos (las rayas entre grupos, en `paintEvent`)."""
        g = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(g)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(3)
        for w in widgets:
            h.addWidget(w)
        return g

    @staticmethod
    def _etiqueta(icono, ayuda):
        """El icono que dice de qué es un desplegable o un deslizador."""
        e = QtWidgets.QLabel()
        tema.pon_icono(e, icono, "tenue", 18)
        e.setToolTip(ayuda)
        return e

    @staticmethod
    def _boton(icono, ayuda, marcado=None):
        """Un botón con solo su icono; con `marcado` (True o False), de los que se quedan marcados."""
        b = QtWidgets.QToolButton(objectName="icono", checkable=marcado is not None, checked=bool(marcado))
        tema.pon_icono(b, icono, "texto", 20, activo="acento_claro" if marcado is not None else None)
        b.setIconSize(QtCore.QSize(20, 20))
        b.setToolTip(ayuda)
        return b

    def _opciones(self, opciones, al_elegir, marcada):
        """Botones excluyentes, a la vista: [(clave, icono, ayuda)]; al pulsar uno, `al_elegir(clave)`. Devuelve {clave: botón}."""
        grupo = QtWidgets.QButtonGroup(self, exclusive=True)
        botones = {}
        for clave, icono, ayuda in opciones:
            b = self._boton(icono, ayuda, marcado=clave == marcada)
            b.clicked.connect(lambda _=False, c=clave: al_elegir(c))
            grupo.addButton(b)
            botones[clave] = b
        return botones

    def paintEvent(self, evento):
        """El fondo y, entre dos grupos de la misma fila, una raya fina."""
        super().paintEvent(evento)
        p = QtGui.QPainter(self)
        p.setPen(QtGui.QPen(QtGui.QColor(tema.T["borde"]), 1))
        izquierda = self.layout().contentsMargins().left()
        for g in self._grupos:
            r = g.geometry()
            if g.isHidden() or r.left() <= izquierda:            # el primero de su fila, sin raya
                continue
            x = r.left() - (self.HUECO + 1) // 2
            p.drawLine(x, r.top() + 4, x, r.bottom() - 4)
        p.end()

    # ── lo que se elige ──────────────────────────────────────────────────────────────────
    def _escala_elegida(self, clave):
        if clave != self._escala_actual:
            self._escala_actual = clave
            self.escala.emit(clave)

    def _transparencia(self, valor, avisar=True):
        self.lbl_transp.setText(f"{valor} %")
        if avisar:
            self.opacidad.emit(1 - valor / 100)

    def _rango_escrito(self):
        """Al acabar de escribir el rango: si vale y ha cambiado, se avisa; si no vale, vuelve el de antes y se dice por qué. En la escala
        logarítmica, un «desde» por debajo de `MINIMO_LOG` (también 0) se fija en él, y se dice."""
        a, b = leer_num(self.ed_min.text()), leer_num(self.ed_max.text())
        motivo, nota = None, None
        if a is not None and self._escala_actual != "lineal" and a < self.MINIMO_LOG:
            a = self.MINIMO_LOG
            self.ed_min.setText(_num(a))
            nota = f"En la escala logarítmica, «desde» no baja de {_num(a)}."
        if a is None or b is None:
            motivo = "Escribe dos números: desde y hasta."
        elif b <= a:
            motivo = "«Hasta» tiene que ser mayor que «desde»."
        if motivo:
            self._pinta_rango()
            QtWidgets.QToolTip.showText(self.ed_min.mapToGlobal(QtCore.QPoint(0, self.ed_min.height())), motivo, self.ed_min)
            return
        if nota:
            QtWidgets.QToolTip.showText(self.ed_min.mapToGlobal(QtCore.QPoint(0, self.ed_min.height())), nota, self.ed_min)
        if self._rango_mostrado is None or (a, b) != tuple(self._rango_mostrado):
            self.rango.emit((a, b))

    # ── lo que pone la ventana ───────────────────────────────────────────────────────────
    def poner_variables(self, lista, encendida=None):
        """Las variables del desplegable, [(id de la capa, texto)], con `encendida` elegida (sin avisar)."""
        self.cmb_var.clear()
        for i, texto in lista:
            self.cmb_var.addItem(texto, i)
        self.cmb_var.setCurrentIndex(-1)
        self.marcar_variable(encendida, True)

    def variables(self):
        """[(id, texto)] de las variables del desplegable, en orden."""
        return [(self.cmb_var.itemData(k), self.cmb_var.itemText(k)) for k in range(self.cmb_var.count())]

    def marcar_variable(self, id_capa, si=True):
        """El mapa ha encendido o apagado una capa: el desplegable, al día (sin avisar). Si se apaga la que se ve, queda en «Ninguna»."""
        k = -1 if id_capa is None else self.cmb_var.findData(id_capa)
        if k < 0:
            return
        if si:
            self.cmb_var.setCurrentIndex(k)
        elif self.cmb_var.currentIndex() == k:
            self.cmb_var.setCurrentIndex(-1)

    def variable_marcada(self):
        k = self.cmb_var.currentIndex()
        return self.cmb_var.itemData(k) if k >= 0 else None

    def poner_estilo(self, clave):
        for c, b in self._b_estilo.items():
            b.setChecked(c == clave)

    def poner_escala(self, clave):
        self._escala_actual = clave
        for c, b in self._b_escala.items():
            b.setChecked(c == clave)

    def escala_actual(self):
        return self._escala_actual

    def poner_paleta(self, clave):
        """La paleta que está en uso (la de la configuración), elegida en su desplegable (sin avisar)."""
        self.sel_paleta.poner(clave)

    def leyenda_visible(self):
        return self.b_leyenda.isChecked()

    def poner_rango(self, vmin, vmax, automatico=True):
        """El rango con el que se ve la capa, en los dos campos; volver al automático, solo si está fijado a mano."""
        self._rango_mostrado, self._rango_auto = (vmin, vmax), automatico
        self._pinta_rango()

    def _pinta_rango(self):
        a, b = self._rango_mostrado or (None, None)
        for ed, v in ((self.ed_min, a), (self.ed_max, b)):
            ed.setText("" if v is None else _num(v))
        self.b_auto.setEnabled(not self._rango_auto)

    APAGADO = 0.35                                # la opacidad de lo apagado: los iconos solos casi no cambian al apagarse

    @classmethod
    def _activar(cls, w, si, motivo, controles=()):
        """Activa o apaga un grupo o un control: apagado, más tenue, y su ayuda (y la de sus `controles`) dice por qué."""
        w.setEnabled(si)
        if si and w.graphicsEffect() is not None:
            w.setGraphicsEffect(None)
        elif not si and w.graphicsEffect() is None:
            efecto = QtWidgets.QGraphicsOpacityEffect(w)
            efecto.setOpacity(cls.APAGADO)
            w.setGraphicsEffect(efecto)
        for c in (w, *controles):
            if c.property("ayuda") is None:
                c.setProperty("ayuda", c.toolTip())
            c.setToolTip(c.property("ayuda") if si else motivo)

    def _activar_grupo(self, g, si, motivo):
        self._activar(g, si, motivo, g.findChildren(QtWidgets.QWidget, options=QtCore.Qt.FindChildOption.FindDirectChildrenOnly))

    def set_escala_activa(self, si, motivo=""):
        """La escala y el rango, solo con la media, el máximo o el P98: el penacho hora a hora y el cambio de la comparación van con la suya."""
        for g in (self.g_escala, self.g_rango):
            self._activar_grupo(g, si, motivo)

    def set_estilo_activo(self, si, motivo=""):
        self._activar_grupo(self.g_estilo, si, motivo)

    def set_paleta_activa(self, si, motivo=""):
        """La paleta, salvo en la comparación (va con los colores del cambio en %); la leyenda, siempre."""
        self._activar(self.sel_paleta, si, motivo)

    def opacidad_actual(self):
        return 1 - self.sl_transp.value() / 100
