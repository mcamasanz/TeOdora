# -*- coding: utf-8 -*-
"""Ventana de los focos de la planta, para CONSULTARLOS (usuario, 2026-11-08: «la lista de los focos a la izquierda, el mapa en medio y a la
derecha la ficha que lo describe; debajo de la lista, los botones de crear, modificar y eliminar, solo accesibles con el usuario administrador»).

- Izquierda: los focos (`ItemFoco`), con el color de su modelo, su emisión de olor y ⟳ si su dispersión está por calcular (nuevo o
  modificado desde que se simuló: `simulacion.estado_respuestas`). Debajo, solo con el usuario administrador (`planta.MODO_EDICION`):
  «Crear», «Modificar» y «Eliminar».
- Centro: el plano de la planta con el foco elegido recuadrado y rotulado (`gui.focos_mapa`).
- Derecha: la ficha del foco (`FichaVista`), solo para leer: sus cifras según el modelo (punto, superficie o volumen), su emisión de olor y
  de gases (con su olor equivalente por Nagata), lo que le falta y, para el administrador, las observaciones de la visita. Sin la
  operabilidad (el horario y los eventos): eso se configura en la operación.

Crear y modificar abren el editor de focos (geometría en el mapa con rectángulos y círculos, y la ficha para caracterizarlo); `Ficha`, la
ficha con casillas, es la que usará. Un foco creado o modificado hay que volver a simularlo para el reanálisis.
"""
import html
import math

from PySide6 import QtCore, QtGui, QtWidgets

from teodors import planta as config
from teodors.comun import registro
from teodors.comun.formato import num as _num
from teodors.gui import tema, widgets
from teodors.gui.focos_graficos import cifra_corta
from teodors.gui.focos_mapa import COLORES, VistaFocos
from teodors.gui.tema import c
from teodors.operacion import focos as F

log = registro.get("focos")


def _fmt(v):
    """Número para un campo: coma decimal, sin ceros de sobra, miles con espacio."""
    if v in (None, ""):
        return ""
    v = float(v)
    if v.is_integer() and abs(v) >= 1000:
        return _num(v)
    s = f"{v:.6g}"
    if "e" in s:                                       # un gas en g/s, sin notación científica («5e-05»)
        s = f"{v:.12f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def _leer(texto):
    """«12,5», «12.5» o «30 000» → float; vacío → None."""
    t = texto.strip().replace(" ", "").replace(" ", "").replace(",", ".")
    return float(t) if t else None


def _cifra(v, unidad):
    if v is None:
        return "—"
    a = abs(v)
    if 0 < a < 0.1:                                    # dos cifras significativas (un gas de 5·10⁻⁵ g/s salía «0,0000»)
        return f"{_num(v, min(6, 1 - math.floor(math.log10(a))))} {unidad}"
    dec = 0 if a >= 100 else (1 if a >= 10 else 2)
    return f"{_num(v, dec)} {unidad}"


def _radio_elegido(al_elegir, clave):
    """Hueco del radio de una opción. Es una FÁBRICA, no `lambda si, c=clave: …`.

    Esa forma —un argumento obligatorio y otro con valor por defecto— es la de toda la vida para
    capturar la variable de un bucle, pero no sobrevive al compilado: en el `.exe` (Nuitka +
    PySide6) Qt no acierta con cuántos argumentos pasarle, la llama sin ninguno y el hueco revienta
    con un TypeError, así que el radio no hace nada. Se vio el 2026-11-18 en los botones de capa del
    mapa. Aquí la variable se captura por cierre y la lambda solo declara el argumento de la señal.
    Ver `gui.panel.Panel._capa_nombrada`."""
    return lambda si: si and al_elegir(clave)


class PerfilDia(QtWidgets.QWidget):
    """24 barras (hora oficial) del perfil del foco; solo para ver."""

    def __init__(self, perfil, parent=None):
        super().__init__(parent)
        self.perfil = perfil
        self.setMinimumHeight(58)

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height() - 14
        tope = max(1.0, max(self.perfil))
        ancho = w / 24.0
        for k, v in enumerate(self.perfil):
            alto = max(1.5, (h - 2) * v / tope)
            p.fillRect(QtCore.QRectF(k * ancho + 1, h - alto, ancho - 2, alto),
                       QtGui.QColor(c("acento") if v > 0 else c("barra_inactiva")))
        p.setPen(QtGui.QColor(c("tenue")))
        f = p.font()
        f.setPointSizeF(7.5)
        p.setFont(f)
        for hora in (0, 6, 12, 18):
            p.drawText(QtCore.QRectF(hora * ancho, h + 1, 30, 13), str(hora))
        p.drawText(QtCore.QRectF(w - 18, h + 1, 18, 13), QtCore.Qt.AlignmentFlag.AlignRight, "24")
        p.end()


class _Recortado(QtWidgets.QLabel):
    """Una línea que, si no cabe, acaba en «…»; solo entonces, el texto entero sale al pasar el ratón."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)

    def paintEvent(self, _):
        visible = self.fontMetrics().elidedText(self.text(), QtCore.Qt.TextElideMode.ElideRight, self.width())
        self.setToolTip("" if visible == self.text() else self.text())
        p = QtGui.QPainter(self)
        p.setPen(self.palette().color(self.foregroundRole()))
        p.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter, visible)
        p.end()


class ItemFoco(QtWidgets.QWidget):
    """Una fila de la lista: un cuadrito del color de su modelo, el nombre y, debajo, lo que diga quien la usa (`tipo`: aquí, la emisión de
    olor; en la ventana de planes, el plan); a la derecha, ⟳ si hay que simularlo (`pendiente`)."""

    def __init__(self, foco, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 8, 6)
        lay.setSpacing(9)
        self.cuadro = QtWidgets.QLabel()
        self.cuadro.setFixedSize(12, 12)
        lay.addWidget(self.cuadro, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        txt = QtWidgets.QVBoxLayout()
        txt.setSpacing(0)
        self.nombre = _Recortado()
        self.nombre.setStyleSheet("font-weight:600;font-size:13px;background:transparent")
        self.tipo = _Recortado()
        tema.estilo(self.tipo, "color:$tenue;font-size:11.5px;background:transparent")
        txt.addWidget(self.nombre)
        txt.addWidget(self.tipo)
        lay.addLayout(txt, 1)
        self.marca = QtWidgets.QLabel("⟳")
        tema.estilo(self.marca, "color:$aviso;font-size:15px;font-weight:700;background:transparent")
        self.marca.setVisible(False)
        lay.addWidget(self.marca)
        self.poner(foco)

    def poner(self, foco):
        self.nombre.setText(foco.get("nombre") or foco["id"])
        self.tipo.setText(F.nombre_tipo(foco))
        relleno, borde = COLORES[foco["modelo"]]
        self.cuadro.setStyleSheet(f"background:{relleno};border:1.5px solid {borde};border-radius:3px")
        self.cuadro.setToolTip(F.MODELOS[foco["modelo"]])

    def pendiente(self, estado):
        """estado: el de `simulacion.estado_respuestas` («ok», «sin_calcular» o «cambiado»)."""
        self.marca.setVisible(estado != "ok")
        self.marca.setToolTip({"sin_calcular": "Sin simular: hay que calcular su dispersión para el reanálisis",
                               "cambiado": "Modificado desde que se simuló: hay que volver a calcular su dispersión"}.get(estado, ""))


class Ficha(QtWidgets.QWidget):
    """Ficha de un foco según su modelo. Cambia el diccionario del foco EN SU SITIO."""
    cambiado = QtCore.Signal(str)        # clave de primer nivel que ha cambiado
    rehacer = QtCore.Signal()            # volver a montar la ficha (cambio de modo, de unidad…)
    ubicar = QtCore.Signal()             # dibujar la ubicación en el plano

    def __init__(self, foco, editable, recalcular, parent=None, operabilidad=True, dibujo=True):
        """`operabilidad`: con la sección del funcionamiento (el editor de focos no la lleva: se configura en la operación); `dibujo`: con
        el botón de dibujar la ubicación (el editor tiene sus formas aparte)."""
        super().__init__(parent)
        self.setObjectName("cuerpo_ficha")
        self.f, self.ed, self._dibujo, self._operabilidad = foco, editable, dibujo, operabilidad
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 20)
        lay.setSpacing(12)
        self._lay = lay

        cab = QtWidgets.QVBoxLayout()
        cab.setSpacing(2)
        t = QtWidgets.QLabel(foco.get("nombre") or foco["id"])
        t.setStyleSheet("font-size:17px;font-weight:700")
        t.setWordWrap(True)
        cab.addWidget(t)
        cab.addWidget(QtWidgets.QLabel(F.subtitulo(foco), objectName="subtitulo", wordWrap=True))
        lay.addLayout(cab)
        self.lbl_estado = QtWidgets.QLabel(wordWrap=True, objectName="estado_falta")
        lay.addWidget(self.lbl_estado)
        self._recalcular = recalcular

        self._identificacion()
        {"punto": self._punto, "superficie": self._superficie, "volumen": self._volumen}[foco["modelo"]]()
        if operabilidad:
            self._funcionamiento()
            self._olor()
            self._gases()
        else:                                    # el editor: los gases primero; la olfatometría, opcional
            self._emision_editor()
        self._observaciones()
        lay.addStretch()
        self.refrescar()

    # ── piezas ───────────────────────────────────────────────────────────────────────────
    def _seccion(self, titulo):
        caja = QtWidgets.QVBoxLayout()
        caja.setSpacing(6)
        caja.addWidget(QtWidgets.QLabel(titulo.upper(), objectName="seccion"))
        self._lay.addLayout(caja)
        return caja

    def _etiqueta(self, texto, recalcula=False):
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        h.addWidget(QtWidgets.QLabel(texto))
        # discreto (usuario, 2026-11-08: más atractivo); en el editor, nada: al guardar un foco se simula solo (usuario, 2026-11-08)
        if recalcula and self._operabilidad:
            tag = QtWidgets.QLabel("⟳", objectName="recalcula")
            tag.setToolTip("Cambiarlo obliga a volver a simular el foco")
            h.addWidget(tag)
        h.addStretch()
        return w

    def _valor(self, ruta):
        d = self.f
        for k in ruta[:-1]:
            d = d.get(k) or {}
        return d.get(ruta[-1])

    def _poner(self, ruta, v):
        d = self.f
        for k in ruta[:-1]:
            if not isinstance(d.get(k), dict):
                d[k] = {}
            d = d[k]
        d[ruta[-1]] = v

    def _linea(self, ruta, numero=True, ph=""):
        v = self._valor(ruta)
        e = QtWidgets.QLineEdit(_fmt(v) if numero else (v or ""))
        e.setPlaceholderText(ph)
        e.setReadOnly(not self.ed)
        e.setMinimumWidth(60)
        if self.ed:
            e.editingFinished.connect(lambda e=e, r=ruta, n=numero: self._editado(e, r, n))
        return e

    def _editado(self, e, ruta, numero):
        if numero:
            try:
                v = _leer(e.text())
            except ValueError:
                tema.estilo(e, "border:1px solid $fallo")
                e.setToolTip("Número no válido (p. ej. 12,5)")
                return
            tema.estilo(e, "")
            e.setToolTip("")
        else:
            v = e.text().strip()
        if self._valor(ruta) == v:
            return
        self._poner(ruta, v)
        if ruta == ("altura_m",) and (self.f.get("superficie") or {}).pop("sobre", None):
            log.info(f"Foco {self.f['id']}: altura escrita a mano; ya no sigue a su edificio.")
        self.cambiado.emit(ruta[0])
        self.refrescar()

    def _campo(self, texto, ruta, ph="", recalcula=False, numero=True):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)
        v.addWidget(self._etiqueta(texto, recalcula))
        v.addWidget(self._linea(ruta, numero, ph))
        return w

    @staticmethod
    def _rejilla(caja, campos, columnas=2):
        g = QtWidgets.QGridLayout()
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(8)
        for i, c in enumerate(campos):
            g.addWidget(c, i // columnas, i % columnas)
        for k in range(columnas):
            g.setColumnStretch(k, 1)
        caja.addLayout(g)

    def _radios(self, caja, opciones, actual, al_elegir):
        largas = sum(len(t) for _, t in opciones) > 40      # en una fila no cabrían en una ficha estrecha
        fila = QtWidgets.QVBoxLayout() if largas else QtWidgets.QHBoxLayout()
        fila.setSpacing(6 if largas else 14)
        grupo = QtWidgets.QButtonGroup(self)
        for clave, texto in opciones:
            r = QtWidgets.QRadioButton(texto)
            r.setChecked(clave == actual)
            r.setEnabled(self.ed or clave == actual)
            grupo.addButton(r)
            r.toggled.connect(_radio_elegido(al_elegir, clave))
            fila.addWidget(r)
        fila.addStretch()
        caja.addLayout(fila)

    def _combo(self, opciones, actual, al_elegir):
        c = QtWidgets.QComboBox()
        for clave, texto in opciones:
            c.addItem(texto, clave)
        i = c.findData(actual)
        c.setCurrentIndex(max(i, 0))
        c.setEnabled(self.ed)
        c.currentIndexChanged.connect(lambda _: al_elegir(c.currentData()))
        return c

    # ── secciones ────────────────────────────────────────────────────────────────────────
    def _identificacion(self):
        caja = self._seccion("Identificación y ubicación")
        self._rejilla(caja, [self._campo("Nombre", ("nombre",), "[nombre en la planta]", numero=False),
                             self._campo("Unidad de la planta", ("unidad",), "[unidad]", numero=False)])
        fila = QtWidgets.QHBoxLayout()
        fila.addWidget(self._etiqueta("Ubicación", recalcula=True), 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.lbl_ubicacion = QtWidgets.QLabel(objectName="nota")
        fila.addWidget(self.lbl_ubicacion, 1)
        if self.ed and self._dibujo:
            b = QtWidgets.QPushButton("Dibujar en el mapa" if self.f["modelo"] == "superficie"
                                      else "Marcar en el mapa")
            b.clicked.connect(self.ubicar)
            fila.addWidget(b)
        caja.addLayout(fila)

    # el caudal de un punto: uno solo de sus tres datos (`focos.caudal_m3_s` toma el primero que haya)
    CAUDALES = (("velocidad_m_s", "Velocidad", "[m/s]"), ("caudal_m3_h", "Caudal", "[m³/h]"), ("caudal_Nm3_h", "Caudal normal", "[Nm³/h]"),
                ("caudal_kg_h", "Caudal másico", "[kg/h]"), ("caudal_m3_m2_h", "Caudal por m²", "[m³/(m²·h)]"))
    UNIDADES_CAUDAL = (("caudal_m3_h", "m³/h"), ("caudal_Nm3_h", "Nm³/h"), ("caudal_kg_h", "kg/h"))

    def _punto_editor(self):
        """El punto en el editor (usuario, 2026-11-08: «un menú atractivo y práctico sin definiciones secundarias»). Arriba, la chimenea y los
        edificios de alrededor en perspectiva (`focos_graficos.PanelEstela`: «combinar el esquema de la chimenea con el radar de edificios, quedando
        como un panel casi tridimensional que ayude a entender los conceptos de la estela»); los edificios no se escriben, los pone el código con
        los descargados (`operacion.estela`) al marcar la chimenea. Debajo, su altura, su diámetro y hacia dónde sale, y el gas de salida."""
        from teodors.gui.focos_graficos import PanelEstela
        s = self.f.setdefault("salida", {})
        if not s.get("orientacion") and self.ed:
            s["orientacion"] = "vertical"
        caja = self._seccion("Chimenea y edificios")
        self.panel = PanelEstela()
        caja.addWidget(self.panel)
        self.lbl_estela = QtWidgets.QLabel(objectName="cifra_v", wordWrap=True, textFormat=QtCore.Qt.TextFormat.RichText)
        caja.addWidget(self.lbl_estela)
        self._rejilla(caja, [self._campo("Altura", ("altura_m",), "[m]", True),
                             self._campo("Diámetro", ("salida", "diametro_m"), "[m]", True)])
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(6)
        grupo = QtWidgets.QButtonGroup(self)
        self.botones_orientacion = {}
        for clave, (texto, _) in F.ORIENTACIONES.items():
            b = QtWidgets.QToolButton(objectName="tile_modelo", checkable=True, text=texto)
            tema.pon_icono(b, "sal_" + clave, "texto", 24, activo="acento_claro")
            b.setIconSize(QtCore.QSize(24, 24))
            b.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            b.setChecked(clave == (s.get("orientacion") or "vertical"))
            b.setEnabled(self.ed)
            grupo.addButton(b)
            b.clicked.connect(lambda _=False, c=clave: self._orientacion(c))
            fila.addWidget(b, 1)
            self.botones_orientacion[clave] = b
        caja.addLayout(fila)
        self._salida_editor()
        self._clave_estela, self._edificios, self._edificios_xy, self._estado_estela = None, [], None, "sin_punto"

    def _salida_editor(self, por_m2=False, solo_caudal=False):
        """El gas de salida (usuario, 2026-11-08: «me parece bien que permitas poner caudal o velocidad para que en función del diámetro se pueda
        reconvertir en una o en otra; lo que no me convence es el diseño»): en una fila, la temperatura, la velocidad y el caudal (real, m³/h, o
        normal, Nm³/h). Se escribe la velocidad o el caudal; el otro sale calculado, en gris, con el diámetro y la temperatura. Una superficie
        (`por_m2`; usuario, 2026-11-08: «falta velocidad o caudal por área; además de temperatura y gases de salida como en el punto»), lo
        mismo con el caudal por m² (m³/(m²·h): su velocidad en m/h) en lugar de la velocidad, y con su área. Una nave (`solo_caudal`), su
        caudal de ventilación, sin velocidad."""
        caja = self._seccion("Gas de salida")
        s = self.f.setdefault("salida", {})
        self._clave_vel = "caudal_m3_m2_h" if por_m2 else "velocidad_m_s"
        self._clave_caudal = next((k for k in ("caudal_m3_h", "caudal_Nm3_h", "caudal_kg_h", self._clave_vel) if s.get(k) not in (None, "")),
                                  self._clave_vel)
        self._unidad_caudal = self._clave_caudal if self._clave_caudal != self._clave_vel else "caudal_m3_h"
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(8)

        def bloque(etiqueta, campo, ancho=1):
            w = QtWidgets.QWidget()
            v = QtWidgets.QVBoxLayout(w)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(3)
            v.addWidget(self._etiqueta(etiqueta))
            if isinstance(campo, QtWidgets.QWidget):
                v.addWidget(campo)
            else:
                v.addLayout(campo)
            fila.addWidget(w, ancho)
        bloque("Temperatura", self._linea(("salida", "temperatura_C"), ph="[°C]"))
        self.lin_vel = QtWidgets.QLineEdit(_fmt(s.get(self._clave_vel)), readOnly=not self.ed)
        self.lin_vel.editingFinished.connect(lambda: self._flujo_editado(self._clave_vel, self.lin_vel))
        if por_m2:
            self.lin_vel.setToolTip("m³ por m² y hora: el aire que la atraviesa (un biofiltro) o el que la barre en la medida (cámara de flujo "
                                    "o túnel); su velocidad, en m/h")
        if solo_caudal:
            self.lin_vel.setVisible(False)                          # sigue ahí (el cálculo la usa), sin verse
        else:
            bloque("Caudal por m²" if por_m2 else "Velocidad", self.lin_vel)
            igual = QtWidgets.QLabel("⇄")
            tema.estilo(igual, "color:$tenue;font-size:16px;padding-top:18px")
            fila.addWidget(igual)
        caudal = QtWidgets.QHBoxLayout()
        caudal.setSpacing(4)
        self.lin_caudal = QtWidgets.QLineEdit(_fmt(s.get(self._unidad_caudal)), readOnly=not self.ed)
        self.lin_caudal.editingFinished.connect(lambda: self._flujo_editado(self._unidad_caudal, self.lin_caudal))
        caudal.addWidget(self.lin_caudal, 1)
        self.combo_caudal = self._combo(list(self.UNIDADES_CAUDAL), self._unidad_caudal, self._unidad)
        caudal.addWidget(self.combo_caudal)
        bloque("Caudal de ventilación" if solo_caudal else "Caudal", caudal, 2)
        caja.addLayout(fila)
        # su composición, para su densidad (usuario, 2026-11-08: «para el gas de salida poner CO₂, CO, metano, H₂, etano y su composición para
        # calcular la densidad»; «añade O₂ y N₂, no aire»): un % por componente, que suman el 100 %; la barra, la mezcla; debajo, su densidad
        from teodors.gui.focos_graficos import BarraComposicion
        comp = F.composicion(self.f)
        caja.addWidget(QtWidgets.QLabel("COMPOSICIÓN", objectName="grupo_ficha"))
        rejilla = QtWidgets.QGridLayout()
        rejilla.setHorizontalSpacing(6)
        rejilla.setVerticalSpacing(6)
        self.lin_comp = {}
        for k, (clave, (nombre, _)) in enumerate(F.GAS_SALIDA.items()):
            w = QtWidgets.QWidget()
            v = QtWidgets.QVBoxLayout(w)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(3)
            v.addWidget(QtWidgets.QLabel(f"{nombre} %"))
            e = QtWidgets.QLineEdit(_fmt(comp.get(clave)), readOnly=not self.ed)
            e.setPlaceholderText("0")
            e.editingFinished.connect(lambda c=clave, e=e: self._comp_editada(c, e))
            v.addWidget(e)
            rejilla.addWidget(w, k // 4, k % 4)
            self.lin_comp[clave] = e
        for c in range(4):
            rejilla.setColumnStretch(c, 1)
        caja.addLayout(rejilla)
        self.barra_comp = BarraComposicion()
        caja.addWidget(self.barra_comp)
        self.lbl_densidad = QtWidgets.QLabel(objectName="cifra_v", textFormat=QtCore.Qt.TextFormat.RichText)
        caja.addWidget(self.lbl_densidad)

    def _comp_editada(self, clave, linea):
        try:
            v = _leer(linea.text())
        except ValueError:
            tema.estilo(linea, "border:1px solid $fallo")
            return
        if v is not None and not 0.0 <= v <= 100.0:
            tema.estilo(linea, "border:1px solid $fallo")
            return
        tema.estilo(linea, "")
        s = self.f.setdefault("salida", {})
        comp = s.setdefault("composicion", dict(F.composicion(self.f)))       # sin ella, se parte de la de por defecto, que es la que se ve
        if (comp.get(clave) or None) == (v or None):
            return
        if v:
            comp[clave] = v
        else:
            comp.pop(clave, None)
        self.cambiado.emit("salida")
        self.refrescar()

    def _flujo_editado(self, clave, linea):
        """La velocidad o el caudal escritos: es el dato que cuenta y los otros se vacían (`focos.caudal_m3_s` toma el que haya)."""
        try:
            v = _leer(linea.text())
        except ValueError:
            tema.estilo(linea, "border:1px solid $fallo")
            return
        tema.estilo(linea, "")
        s = self.f.setdefault("salida", {})
        if v is None and self._clave_caudal != clave:               # se ha salido de la casilla calculada sin escribir
            return
        if s.get(clave) == v and self._clave_caudal == clave:
            return
        for c, _, _ in self.CAUDALES:
            s[c] = None
        s[clave] = v
        self._clave_caudal = clave
        self.cambiado.emit("salida")
        self.refrescar()

    def _unidad(self, clave):
        """m³/h, Nm³/h o kg/h: si el caudal es el dato escrito, la misma cifra pasa a la otra unidad."""
        self._unidad_caudal = clave
        s = self.f.setdefault("salida", {})
        if self._clave_caudal in dict(self.UNIDADES_CAUDAL) and self._clave_caudal != clave:
            v = s.get(self._clave_caudal)
            for c, _, _ in self.CAUDALES:
                s[c] = None
            s[clave] = v
            self._clave_caudal = clave
            self.cambiado.emit("salida")
        self.refrescar()

    def _orientacion(self, clave):
        s = self.f.setdefault("salida", {})
        if s.get("orientacion") == clave:
            return
        s["orientacion"] = clave
        self.cambiado.emit("salida")
        self.refrescar()

    def _calcular_estela(self):
        """Los edificios de alrededor de la chimenea y su estela (`operacion.estela`), con su posición y su altura de ahora; solo si ha
        cambiado alguna de las dos. Lo calculado queda en el foco («edificios»): es lo que lee el motor."""
        from teodors.operacion import estela as E
        u, alto = self.f.get("ubicacion") or {}, self.f.get("altura_m")
        if "x" not in u or "y" not in u:
            self._estado_estela = "sin_punto"
            self.panel.poner(self.f, [], None, "sin_punto")
            self._pinta_estela(None)
            return
        clave = (round(u["x"], 1), round(u["y"], 1), alto)
        if clave == self._clave_estela:
            return
        self._clave_estela = clave
        est = None
        try:
            if self._edificios_xy != clave[:2]:
                self._edificios, self._edificios_xy = E.edificios_cerca(u["x"], u["y"]), clave[:2]
            est = E.calcular(u["x"], u["y"], alto, self._edificios) if alto else None
        except Exception as e:                                       # noqa: BLE001 — una huella rara no puede tumbar el editor
            log.warning(f"No se pudo calcular la estela de los edificios del foco {self.f['id']}: {e}")
        if self.ed:
            previa = self.f.get("edificios")
            if est is None:
                self.f.pop("edificios", None)
            else:
                self.f["edificios"] = est
            if previa != self.f.get("edificios"):
                self.cambiado.emit("edificios")
        self._estado_estela = "ok" if self._edificios else "sin_edificios"
        self.panel.poner(self.f, self._edificios, self.f.get("edificios"), self._estado_estela)
        self._pinta_estela(self.f.get("edificios"))

    def edificios_cambiados(self):
        """Los edificios de la planta se han guardado en esta sesión (usuario, 2026-11-08: «que en la misma sesión se actualice en el panel de
        focos del visor 3D»): se vuelven a buscar y la estela se recalcula (un punto) o se repinta (una superficie), con la vista del panel
        como estaba."""
        if not hasattr(self, "panel"):
            return
        if self.f["modelo"] == "punto":
            self._clave_estela, self._edificios_xy = None, None
            self._calcular_estela()
            return
        from teodors.operacion import edificios_planta as EP
        try:
            self._edificios_planta = EP.cargar()["edificios"]
        except (ValueError, OSError):
            self._edificios_planta = []
        (self._pinta_superficie if self.f["modelo"] == "superficie" else self._pinta_volumen)()

    def _pinta_estela(self, est):
        from teodors.operacion import estela as E
        alto = self.f.get("altura_m")
        if not est or not alto:
            self.lbl_estela.setVisible(False)
            return
        n, libre = E.resumen(est, alto)
        if n:
            tema.texto(self.lbl_estela, f"<span style='color:$aviso'>En la estela con {n} de 36 vientos</span> · libre a "
                                        f"{_num(libre, 0 if libre >= 10 else 1)} m")
        else:
            tema.texto(self.lbl_estela, "<span style='color:$acento_claro'>Libre con todos los vientos</span>")
        self.lbl_estela.setVisible(True)

    def _punto(self):
        if not self._operabilidad:                         # el editor de focos
            self._punto_editor()
            return
        caja = self._seccion("Salida (punto)")
        self._rejilla(caja, [
            self._campo("Altura", ("altura_m",), "[m]", True),
            self._campo("Diámetro", ("salida", "diametro_m"), "[m]", True),
            self._campo("Velocidad de salida", ("salida", "velocidad_m_s"), "[m/s]", True),
            self._campo("Caudal", ("salida", "caudal_m3_h"), "[m³/h]", True),
            self._campo("Caudal normal", ("salida", "caudal_Nm3_h"), "[Nm³/h]", True),
            self._campo("Temperatura", ("salida", "temperatura_C"), "[°C]", True)])
        self.lbl_salida = QtWidgets.QLabel(objectName="nota", wordWrap=True)
        caja.addWidget(self.lbl_salida)
        self._rejilla(caja, [
            self._campo("Edificio cercano", ("edificio", "nombre"), "[edificio]", numero=False),
            self._campo("Su altura real", ("edificio", "altura_m"), "[m]", True)])

    def _superficie_editor(self):
        """La superficie en el editor (usuario, 2026-11-08: «focos de superficies, desde piscinas, superficies de tanques abiertos; también
        debemos poder verlo en 3D»). Como en AERMOD y CALPUFF, una fuente de área: su contorno, su altura de emisión y lo que emite por m²,
        sin sobreelevación ni efecto edificio. Arriba, en 3D con los edificios de la planta (`focos_graficos.PanelSuperficie`); debajo, su
        clase en tres baldosas (balsa o piscina, a ras de suelo; tanque abierto, por su boca; biofiltro), los edificios de la planta para
        poner un tanque en su boca con un clic (su contorno y su altura, que le siguen: `focos.poner_sobre`), y su altura y su área."""
        from teodors.gui.focos_graficos import PanelSuperficie
        from teodors.operacion import edificios_planta as EP
        sup = self.f.setdefault("superficie", {})
        if self.ed and not sup.get("clase"):
            sup["clase"] = F.clase_superficie(self.f)
        caja = self._seccion("Superficie y edificios")
        self.panel = PanelSuperficie()
        self.panel.edificio_pulsado.connect(self._sobre)
        caja.addWidget(self.panel)
        self.lbl_superficie = QtWidgets.QLabel(objectName="cifra_v", wordWrap=True, textFormat=QtCore.Qt.TextFormat.RichText)
        caja.addWidget(self.lbl_superficie)
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(6)
        grupo = QtWidgets.QButtonGroup(self)
        self.botones_clase = {}
        clase = F.clase_superficie(self.f)
        for clave, (texto, _) in F.CLASES_SUPERFICIE.items():
            b = QtWidgets.QToolButton(objectName="tile_modelo", checkable=True, text=texto)
            tema.pon_icono(b, "sup_" + clave, "texto", 24, activo="acento_claro")
            b.setIconSize(QtCore.QSize(24, 24))
            b.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            b.setChecked(clave == clase)
            b.setEnabled(self.ed)
            grupo.addButton(b)
            b.clicked.connect(lambda _=False, c=clave: self._clase(c))
            fila.addWidget(b, 1)
            self.botones_clase[clave] = b
        caja.addLayout(fila)
        # un tanque abierto, en la boca de un edificio de la planta: uno por botón (un clic en el 3D hace lo mismo)
        try:
            self._edificios_planta = EP.cargar()["edificios"]
        except (ValueError, OSError):
            self._edificios_planta = []
        self.botones_sobre = {}
        if clase == "tanque" and self._edificios_planta:
            caja.addWidget(QtWidgets.QLabel("EN LA BOCA DE UN EDIFICIO DE LA PLANTA", objectName="grupo_ficha"))
            rejilla = QtWidgets.QGridLayout()
            rejilla.setHorizontalSpacing(6)
            rejilla.setVerticalSpacing(6)
            orden = sorted(self._edificios_planta, key=lambda e: (not EP.redondo(EP.poligono(e)), -e["altura_m"]))
            for k, e in enumerate(orden):
                b = QtWidgets.QPushButton(f"{e.get('nombre') or e['id']} · {_num(e['altura_m'], 1)} m", checkable=True)
                b.setChecked(e["id"] == sup.get("sobre"))
                b.setEnabled(self.ed)
                b.setToolTip("Su contorno y su altura: la boca del tanque, que les sigue si cambian")
                b.clicked.connect(lambda _=False, i=e["id"]: self._sobre(i))
                rejilla.addWidget(b, k // 2, k % 2)
                self.botones_sobre[e["id"]] = b
            caja.addLayout(rejilla)
        area = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(area)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)
        v.addWidget(self._etiqueta("Área"))
        self.lin_area = QtWidgets.QLineEdit(readOnly=True)
        v.addWidget(self.lin_area)
        self._rejilla(caja, [self._campo("Altura de emisión", ("altura_m",), "[m]", True), area])
        # su gas de salida, como el de un punto (usuario, 2026-11-08): la temperatura, el caudal por m² ⇄ el caudal y la composición
        self._salida_editor(por_m2=True)
        self._viento_editor()

    def _viento_editor(self):
        """Lo que emite según el viento (usuario, 2026-11-08: «tenemos que dejar una correlación en función del viento, en superficies y en
        volúmenes»): constante, o creciendo con el viento como (u / u_ref)^β, la corrección de lo medido con túnel de viento a u_ref. Con
        ella, su exponente, el viento de la medida y la curva del factor con cada viento (`focos_graficos.CurvaViento`)."""
        from teodors.gui.focos_graficos import CurvaViento
        caja = self._seccion("Emisión con el viento")
        ev = self.f.get("emision_viento")
        activo = self.f["modelo"] == "superficie" and F.es_biofiltro(self.f)
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(6)
        grupo = QtWidgets.QButtonGroup(self)
        self.botones_viento = {}
        for clave, texto in (("constante", "Constante"), ("viento", "Crece con el viento")):
            b = QtWidgets.QToolButton(objectName="tile_modelo", checkable=True, text=texto)
            tema.pon_icono(b, "viento_" + clave, "texto", 24, activo="acento_claro")
            b.setIconSize(QtCore.QSize(24, 24))
            b.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            b.setChecked((clave == "viento") == (ev is not None))
            b.setEnabled(self.ed and not (activo and clave == "viento" and ev is None))
            grupo.addButton(b)
            b.clicked.connect(lambda _=False, c=clave: self._modo_viento(c))
            fila.addWidget(b, 1)
            self.botones_viento[clave] = b
        caja.addLayout(fila)
        if activo:                               # una fuente activa: el aire sale empujado, no lo arrastra el viento (DGR IX/3018)
            caja.addWidget(QtWidgets.QLabel("Un biofiltro es una fuente activa: lo que emite no depende del viento.", objectName="nota",
                                            wordWrap=True))
        if ev is None:
            return
        exp = self._campo("Exponente", ("emision_viento", "exponente"), "[β]")
        exp.setToolTip("0,5 en una lámina líquida (capa límite laminar); en una pila, entre 0 y 0,5")
        ref = self._campo("Viento de la medida", ("emision_viento", "viento_ref_m_s"), "[m/s]")
        ref.setToolTip("La velocidad del aire dentro del túnel o la campana al medir (0,3 m/s en un túnel tipo UNSW)")
        self._rejilla(caja, [exp, ref])
        self.curva_viento = CurvaViento()
        caja.addWidget(self.curva_viento)
        self.lbl_viento = QtWidgets.QLabel(objectName="nota", wordWrap=True, textFormat=QtCore.Qt.TextFormat.RichText)
        caja.addWidget(self.lbl_viento)

    def _modo_viento(self, modo):
        if (modo == "viento") == (self.f.get("emision_viento") is not None):
            return
        if modo == "viento":
            self.f["emision_viento"] = {"exponente": F.VIENTO_EXPONENTE, "viento_ref_m_s": F.VIENTO_REF_M_S}
        else:
            self.f.pop("emision_viento", None)
        self.cambiado.emit("emision_viento")
        self.rehacer.emit()

    def _clase(self, clase):
        """Otra clase de superficie: su altura de emisión por defecto (salvo la de un tanque, que es la suya) y la unidad de su olfatometría
        si aún no tiene medida; lejos de un tanque, sin el enlace a su edificio."""
        sup = self.f.setdefault("superficie", {})
        if sup.get("clase") == clase:
            return
        unidad_antes = F.unidad_olor(self.f)
        sup["clase"] = clase
        if clase != "tanque":
            sup.pop("sobre", None)
        h = F.CLASES_SUPERFICIE[clase][1]
        if h is not None:
            self.f["altura_m"] = h
        o = self.f.setdefault("olor", {})
        if o.get("valor") in (None, "") and o.get("unidad", unidad_antes) == unidad_antes:
            o["unidad"] = F.unidad_olor(self.f)
        self.cambiado.emit("superficie")
        self.rehacer.emit()

    def _sobre(self, id_edificio):
        """La superficie, en la boca de ese edificio de la planta (un tanque abierto)."""
        e = next((e for e in self._edificios_planta if e["id"] == id_edificio), None)
        if e is None or not self.ed:
            return
        self.f.setdefault("superficie", {})["clase"] = "tanque"
        if F.poner_sobre(self.f, e):
            log.info(f"Foco {self.f['id']}: en la boca de «{e.get('nombre') or e['id']}» ({_num(e['altura_m'], 1)} m).")
            self.cambiado.emit("ubicacion")
        self.rehacer.emit()

    def _pinta_superficie(self):
        f = self.f
        a, q = F.area_m2(f), F.olor_ouE_s(f)
        etiqueta = (f"{_num(a, 0)} m²" + (f" · {cifra_corta(q)} ou_E/s" if q else "")) if a else ""
        self.panel.poner(f, getattr(self, "_edificios_planta", []), etiqueta)
        if not a:
            tema.texto(self.lbl_superficie, "<span style='color:$tenue'>Sin dibujar: con una forma en el mapa"
                       + (", o en la boca de un edificio" if F.clase_superficie(f) == "tanque" else "") + "</span>")
            return
        h = f.get("altura_m")
        donde = "a ras de suelo" if not h else f"a {_num(h, 1)} m"
        sobre = (f.get("superficie") or {}).get("sobre")
        e = next((e for e in getattr(self, "_edificios_planta", []) if e["id"] == sobre), None)
        txt = f"{_num(a, 0)} m² {donde}"
        if e is not None:
            txt += f" <span style='color:$tenue;font-weight:400'>· boca de {html.escape(e.get('nombre') or e['id'])}</span>"
        if q:
            txt += f" · {_cifra(q, 'ou_E/s')} <span style='color:$tenue;font-weight:400'>({_cifra(F.por_m2(f, q), 'ou_E/(s·m²)')})</span>"
        caudal = F.caudal_m3_s(f) if F.es_biofiltro(f) else None
        if caudal:                     # un biofiltro: su carga superficial, el aire tratado por m² de lecho (con la que se dimensiona)
            txt += (f"<br><span style='color:$tenue;font-weight:400'>carga {_num(caudal * 3600 / a, 0)} m³/(m²·h) · "
                    f"{_num(caudal * 3600, 0)} m³/h tratados</span>")
        tema.texto(self.lbl_superficie, txt)

    def _superficie(self):
        if not self._operabilidad:                         # el editor de focos
            self._superficie_editor()
            return
        caja = self._seccion("Superficie")
        area = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(area)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)
        v.addWidget(self._etiqueta("Área"))
        self.lin_area = QtWidgets.QLineEdit(readOnly=True)
        v.addWidget(self.lin_area)
        campos = [area, self._campo("Altura de emisión", ("altura_m",), "[m]", True)]
        if self.f.get("tipo") == "pila":
            campos.append(self._campo("Material y fase", ("material",), "[digestato · fase]",
                                      numero=False))
        self._rejilla(caja, campos)

    def _volumen_editor(self):
        """El volumen en el editor (usuario, 2026-11-08: «pasamos a volúmenes donde añadiremos las pilas de compostaje»). Como en AERMOD y
        CALPUFF: su centro, sus medidas, su altura de emisión (sin dato, a media altura) y sus σ iniciales, sin sobreelevación; una pila
        alargada va al motor como una fila de volúmenes. Arriba, en 3D con los edificios de la planta (`focos_graficos.PanelVolumen`); debajo,
        su clase (pila o hilera; nave), la sección de una pila (hilera o meseta), sus medidas y su rumbo, lo que emite (la piel de una pila,
        la planta de una nave) y su gas de salida, como el de un punto: una pila, con su caudal por m²; una nave, con su ventilación."""
        from teodors.gui.focos_graficos import PanelVolumen
        from teodors.operacion import edificios_planta as EP
        vol = self.f.setdefault("volumen", {})
        if self.ed and not vol.get("clase"):
            vol["clase"] = F.clase_volumen(self.f)
        clase = F.clase_volumen(self.f)
        caja = self._seccion("Volumen y edificios")
        self.panel = PanelVolumen()
        caja.addWidget(self.panel)
        self.lbl_volumen = QtWidgets.QLabel(objectName="cifra_v", wordWrap=True, textFormat=QtCore.Qt.TextFormat.RichText)
        caja.addWidget(self.lbl_volumen)
        try:
            self._edificios_planta = EP.cargar()["edificios"]
        except (ValueError, OSError):
            self._edificios_planta = []

        def baldosas(opciones, actual, al_elegir, prefijo, guardar):
            fila = QtWidgets.QHBoxLayout()
            fila.setSpacing(6)
            grupo = QtWidgets.QButtonGroup(self)
            for clave, texto in opciones:
                b = QtWidgets.QToolButton(objectName="tile_modelo", checkable=True, text=texto)
                tema.pon_icono(b, prefijo + clave, "texto", 24, activo="acento_claro")
                b.setIconSize(QtCore.QSize(24, 24))
                b.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
                b.setChecked(clave == actual)
                b.setEnabled(self.ed)
                grupo.addButton(b)
                b.clicked.connect(lambda _=False, c=clave: al_elegir(c))
                fila.addWidget(b, 1)
                guardar[clave] = b
            caja.addLayout(fila)
        self.botones_clase, self.botones_seccion = {}, {}
        baldosas(list(F.CLASES_VOLUMEN.items()), clase, self._clase_volumen, "vol_", self.botones_clase)
        if clase == "pila":
            caja.addWidget(QtWidgets.QLabel("SECCIÓN", objectName="grupo_ficha"))
            baldosas(list(F.SECCIONES_PILA.items()), vol.get("seccion") or "hilera", self._seccion_pila, "sec_", self.botones_seccion)
        altura = self._campo("Altura de emisión", ("altura_m",), "[m]", True)
        self.lin_altura_vol = altura.findChild(QtWidgets.QLineEdit)          # sin dato, la mitad de su alto, en gris
        self._rejilla(caja, [self._campo("Largo", ("dimensiones", "largo_m"), "[m]", True),
                             self._campo("Ancho", ("dimensiones", "ancho_m"), "[m]", True),
                             self._campo("Alto", ("dimensiones", "alto_m"), "[m]", True),
                             self._campo("Rumbo del largo", ("dimensiones", "orientacion_deg"), "[° desde el N]", True),
                             altura], columnas=3)
        area = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(area)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)
        v.addWidget(self._etiqueta("Piel que emite" if clase == "pila" else "Planta"))
        self.lin_area = QtWidgets.QLineEdit(readOnly=True)
        v.addWidget(self.lin_area)
        self._rejilla(caja, [area])
        self._salida_editor(por_m2=clase == "pila", solo_caudal=clase != "pila")
        self._viento_editor()

    def _clase_volumen(self, clase):
        vol = self.f.setdefault("volumen", {})
        if vol.get("clase") == clase:
            return
        vol["clase"] = clase
        if clase == "pila":
            vol.setdefault("seccion", "hilera")
        self.cambiado.emit("volumen")
        self.rehacer.emit()

    def _seccion_pila(self, seccion):
        vol = self.f.setdefault("volumen", {})
        if vol.get("seccion") == seccion:
            return
        vol["seccion"] = seccion
        self.cambiado.emit("volumen")
        self.refrescar()

    def _pinta_volumen(self):
        f = self.f
        a, q = F.area_m2(f), F.olor_ouE_s(f)
        pila = F.clase_volumen(f) == "pila"
        etiqueta = (f"{_num(a, 0)} m²" if (a and pila) else "") + (f"{' · ' if a and pila else ''}{cifra_corta(q)} ou_E/s" if q else "")
        self.panel.poner(f, getattr(self, "_edificios_planta", []), etiqueta)
        h = F.altura_emision(f)
        if F.seccion(f) is None or "x" not in (f.get("ubicacion") or {}):
            tema.texto(self.lbl_volumen, "<span style='color:$tenue'>Sin terminar: dibújalo en el mapa y pon su largo, su ancho y su alto</span>")
            return
        partes = len(F.partes_volumen(f))
        txt = (f"{_num(a, 0)} m² de piel" if pila else f"{_num(a, 0)} m² de planta") + (f" · emite a {_num(h, 1)} m" if h else "")
        if partes > 1:
            txt += f" <span style='color:$tenue;font-weight:400'>· {partes} volúmenes en el modelo</span>"
        if q:
            txt += f" · {_cifra(q, 'ou_E/s')}"
        tema.texto(self.lbl_volumen, txt)

    def _volumen(self):
        if not self._operabilidad:                         # el editor de focos
            self._volumen_editor()
            return
        caja = self._seccion("Volumen")
        self._rejilla(caja, [
            self._campo("Largo", ("dimensiones", "largo_m"), "[m]", True),
            self._campo("Ancho", ("dimensiones", "ancho_m"), "[m]", True),
            self._campo("Alto", ("dimensiones", "alto_m"), "[m]", True),
            self._campo("Altura de emisión", ("altura_m",), "[m]", True)])

    def _funcionamiento(self):
        caja = self._seccion("Funcionamiento")
        fn = self.f.setdefault("funcionamiento", {"modo": "continuo"})

        def elegir(modo):
            fn["modo"] = modo
            self.cambiado.emit("funcionamiento")
            self.rehacer.emit()
        self._radios(caja, list(F.FUNCIONAMIENTO.items()), fn.get("modo"), elegir)
        if fn.get("modo") == "horario":
            pila = self.f.get("tipo") == "pila"
            self._rejilla(caja, [
                self._campo("Horas de volteo" if pila else "Horas (hora oficial)",
                            ("funcionamiento", "horas"), "8, 16" if pila else "8-16", numero=False),
                self._campo("Fuera de esas horas", ("funcionamiento", "fuera_pct"),
                            "[% de la emisión]")])
        elif fn.get("modo") == "eventos":
            self._rejilla(caja, [
                self._campo("Frecuencia", ("funcionamiento", "veces_mes"), "[veces al mes]"),
                self._campo("Duración", ("funcionamiento", "duracion_min"), "[min]")])
        caja.addWidget(QtWidgets.QLabel("Perfil del día", objectName="nota"))
        self.perfil = PerfilDia(F.perfil(self.f) if not self._horas_mal() else [0.0] * 24)
        caja.addWidget(self.perfil)

    def _horas_mal(self):
        try:
            F.perfil(self.f)
            return False
        except ValueError:
            return True

    def _olor(self):
        caja = self._seccion("Olor")
        o = self.f.setdefault("olor", {})
        m = self.f["modelo"]
        o.setdefault("unidad", F.unidad_olor(self.f))
        texto = {"ou_E/m3": "Olfatometría a la salida", "ou_E/(s·m2)": "Olfatometría por m²",
                 "ou_E/s": "Olfatometría, emisión total"}[o["unidad"]]
        campos = [self._valor_unidad(("olor",), list(F.UNIDADES_OLOR), texto),
                  self._campo("Fecha de la medida", ("olor", "fecha"), "[dd/mm/aaaa]", numero=False)]
        unidades = [o["unidad"]] + [g.get("unidad", "ppm") for g in self.f.get("gases") or []]
        if m != "punto" and set(unidades) & set(F.UNIDADES_CONCENTRACION):
            campos.append(self._campo("Caudal tratado" if F.es_biofiltro(self.f) else "Caudal",
                                      ("olor", "caudal_m3_h"), "[m³/h]"))
        self._rejilla(caja, campos)
        self.lbl_olor = QtWidgets.QLabel(wordWrap=True)
        caja.addWidget(self.lbl_olor)

    def _valor_unidad(self, ruta, unidades, texto):
        """Valor y su unidad (desplegable) de la medida en `ruta` ({"valor", "unidad"})."""
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)
        v.addWidget(self._etiqueta(texto))
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(4)
        fila.addWidget(self._linea(ruta + ("valor",)), 1)
        nombres = {"ou_E/m3": "ou_E/m³", "ou_E/(s·m2)": "ou_E/(s·m²)", "mg/m3": "mg/m³",
                   "mg/(s·m2)": "mg/(s·m²)"}
        fila.addWidget(self._combo([(u, nombres.get(u, u)) for u in unidades],
                                   self._valor(ruta + ("unidad",)),
                                   lambda u: (self._cambia(ruta + ("unidad",), u), self.rehacer.emit())))
        v.addLayout(fila)
        return w

    def _cambia(self, ruta, v):
        if self._valor(ruta) != v:
            self._poner(ruta, v)
            self.cambiado.emit(ruta[0])
            self.refrescar()

    def _emision_editor(self):
        """La emisión en el editor (usuario, 2026-11-08: «cada foco queda caracterizado por los gases que lo conforman y las cantidades de cada
        uno, y luego en base a su correlación de masa a olor, el que tenga mayores unidades olfativas es el que predomina en el olor»): los
        gases con lo medido, el olor que aporta cada uno (`focos_graficos.OlorGases`) y el del foco. La olfatometría, si la hay, manda."""
        from teodors.gui.focos_graficos import OlorGases
        caja = self._gases("Emisión")
        self.olor_gases = OlorGases()
        caja.addWidget(self.olor_gases)
        self.lbl_olor = QtWidgets.QLabel(wordWrap=True, objectName="cifra_v", textFormat=QtCore.Qt.TextFormat.RichText)
        caja.addWidget(self.lbl_olor)
        o = self.f.setdefault("olor", {})
        o.setdefault("unidad", F.unidad_olor(self.f))
        caja.addWidget(QtWidgets.QLabel("OLFATOMETRÍA", objectName="grupo_ficha"))
        # el caudal de una concentración va en su gas de salida (punto, superficie y volumen): aquí no se repite
        self._rejilla(caja, [self._valor_unidad(("olor",), list(F.UNIDADES_OLOR), "Medida"),
                             self._campo("Fecha", ("olor", "fecha"), "[dd/mm/aaaa]", numero=False)])

    def _gases(self, titulo="Gases"):
        caja = self._seccion(titulo)
        lista = self.f.setdefault("gases", [])
        self.lbl_gases, self.lbl_masas = [], []
        for k, g in enumerate(lista):
            fila = QtWidgets.QHBoxLayout()
            fila.setSpacing(4)
            gas = self._combo([(n, F.NOMBRES.get(n, n)) for n in F.GASES], g.get("gas"), lambda c, g=g: self._cambia_gas(g, "gas", c))
            # los 223 de Nagata: con el nombre más largo, la ficha se salía por la derecha; la lista, eso sí, ancha
            gas.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            gas.setMinimumContentsLength(7)
            gas.view().setMinimumWidth(gas.view().sizeHintForColumn(0) + 36)
            fila.addWidget(gas, 2)
            # su masa molar (usuario, 2026-11-08: «una nueva columna que sea el peso molecular»): la de la tabla de Nagata (PubChem)
            masa = QtWidgets.QLabel(objectName="nota")
            masa.setMinimumWidth(66)
            masa.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            self.lbl_masas.append((g, masa))
            fila.addWidget(masa)
            e = QtWidgets.QLineEdit(_fmt(g.get("valor")), readOnly=not self.ed)
            e.setPlaceholderText("[valor]")
            e.setMinimumWidth(64)                      # con «mg/(m²·h)» al lado (una superficie), el valor no se aplasta
            if self.ed:
                e.editingFinished.connect(lambda e=e, g=g: self._valor_gas(e, g))
            fila.addWidget(e, 1)
            unidades = list(F.unidades_gas(self.f))
            if g.get("unidad") and g["unidad"] not in unidades:          # una de antes, que ya no toca a este foco: que se vea
                unidades.append(g["unidad"])
            fila.addWidget(self._combo([(u, u.replace("m3", "m³").replace("m2", "m²")) for u in unidades], g.get("unidad", unidades[0]),
                                       lambda u, g=g: self._cambia_gas(g, "unidad", u)))
            r = QtWidgets.QLabel(objectName="nota")
            r.setMinimumWidth(72)                      # «= 0,071 g/s», entero
            self.lbl_gases.append((g, r))
            fila.addWidget(r)
            if self.ed:
                quitar = QtWidgets.QToolButton(text="×")
                quitar.setToolTip("Quitar este gas")
                quitar.clicked.connect(lambda _=False, k=k: (lista.pop(k), self.cambiado.emit("gases"),
                                                            self.rehacer.emit()))
                fila.addWidget(quitar)
            caja.addLayout(fila)
        if not lista and not self.ed:
            caja.addWidget(QtWidgets.QLabel("Sin gases medidos.", objectName="nota"))
        if self.ed:
            fila = QtWidgets.QHBoxLayout()
            fila.setSpacing(6)
            b = QtWidgets.QPushButton("+ Añadir gas")
            b.clicked.connect(lambda: (lista.append({"gas": "H2S", "valor": None, "unidad": F.unidad_gas(self.f)}),
                                       self.cambiado.emit("gases"), self.rehacer.emit()))
            fila.addWidget(b)
            # una superficie se define por sus gases (usuario, 2026-11-08): los típicos de su clase, de una vez, sin valor
            faltan = [k for k in F.GASES_TIPICOS.get(F.clase_superficie(self.f), ()) if k in F.GASES
                      and k not in {g.get("gas") for g in lista}] if self.f["modelo"] == "superficie" else []
            if faltan:
                clase = F.CLASES_SUPERFICIE[F.clase_superficie(self.f)][0].lower()
                t = QtWidgets.QPushButton(f"+ Gases típicos ({len(faltan)})")
                t.setToolTip(f"Los de un {clase}: " + ", ".join(F.NOMBRES.get(k, k) for k in faltan))
                t.clicked.connect(lambda: (F.poner_gases_tipicos(self.f), self.cambiado.emit("gases"), self.rehacer.emit()))
                fila.addWidget(t)
            fila.addStretch()
            caja.addLayout(fila)
        return caja

    def _cambia_gas(self, g, clave, v):
        if g.get(clave) != v:
            g[clave] = v
            self.cambiado.emit("gases")
            self.refrescar()
            if clave == "unidad":                  # una concentración necesita el caudal
                self.rehacer.emit()

    def _valor_gas(self, e, g):
        try:
            v = _leer(e.text())
        except ValueError:
            tema.estilo(e, "border:1px solid $fallo")
            return
        tema.estilo(e, "")
        self._cambia_gas(g, "valor", v)

    def _observaciones(self):
        caja = self._seccion("Observaciones de la visita")
        t = QtWidgets.QPlainTextEdit(self.f.get("observaciones", ""))
        t.setPlaceholderText("[notas, fotos, dudas pendientes]")
        t.setReadOnly(not self.ed)
        t.setFixedHeight(76)
        if self.ed:
            t.textChanged.connect(lambda: (self.f.__setitem__("observaciones", t.toPlainText()),
                                           self.cambiado.emit("observaciones")))
        caja.addWidget(t)

    # ── lo que se calcula ────────────────────────────────────────────────────────────────
    def refrescar(self):
        f, m = self.f, self.f["modelo"]
        u = f.get("ubicacion") or {}
        if m == "superficie":
            n = len(u.get("poligono") or [])
            a = F.area_m2(f)
            self.lbl_ubicacion.setText(f"polígono de {n} vértices" if n >= 3 else "sin dibujar")
            self.lin_area.setText(f"{_num(a)} m²" if a else "")
        elif "x" in u and "y" in u:
            self.lbl_ubicacion.setText(f"UTM {_num(u['x'], 1)} · {_num(u['y'], 1)} m")
        else:
            self.lbl_ubicacion.setText("sin marcar")
        if hasattr(self, "panel") and m == "punto":        # la chimenea, ya; los edificios, después de pintar la ficha (la 1.ª vez, ~1 s)
            self.panel.poner(f, self._edificios, f.get("edificios"), self._estado_estela)
            QtCore.QTimer.singleShot(0, self, self._calcular_estela)
        if hasattr(self, "lin_vel"):                        # lo no escrito, calculado y en gris
            q, area, s = F.caudal_m3_s(f), F.area_m2(f), f.get("salida") or {}
            por_m2 = self._clave_vel == "caudal_m3_m2_h"                   # una superficie: m³/(m²·h) en lugar de m/s
            vel = (q * (3600.0 if por_m2 else 1.0) / area) if (q and area) else None
            factor = {"caudal_Nm3_h": F.T_NORMAL_K / F.temperatura_K(f), "caudal_kg_h": F.densidad_salida(f) or 0.0}.get(self._unidad_caudal, 1.0)
            caudal = q * 3600 * factor if q else None
            calc_vel, calc_caudal = self._clave_caudal != self._clave_vel, self._clave_caudal == self._clave_vel
            if calc_vel:
                self.lin_vel.setText("")
            if calc_caudal:
                self.lin_caudal.setText("")
            self.lin_vel.setPlaceholderText(f"≈ {_fmt(round(vel, 1))}" if (calc_vel and vel) else ("[m³/(m²·h)]" if por_m2 else "[m/s]"))
            self.lin_caudal.setPlaceholderText(f"≈ {_num(caudal, 0)}" if (calc_caudal and caudal) else "[caudal]")
            comp, m_mol, rho = F.composicion(f), F.masa_molar_salida(f), F.densidad_salida(f)
            self.barra_comp.poner(comp)
            if m_mol is None:
                tema.texto(self.lbl_densidad, f"<span style='color:$fallo'>La composición suma {_num(sum(comp.values()), 1)} %</span>")
            else:
                tema.texto(self.lbl_densidad, f"{_num(rho, 2)} kg/m³ <span style='color:$tenue;font-weight:400'>· {_num(m_mol, 1)} g/mol"
                                              f" · a {_num(F.temperatura_K(f) - 273.15, 0)} °C</span>")
        elif m == "punto":
            s, q = f.get("salida") or {}, F.caudal_m3_s(f)
            area = F.area_m2(f)
            partes = []
            if q and area and not s.get("velocidad_m_s"):
                partes.append(f"velocidad calculada con el caudal: {_cifra(q / area, 'm/s')}")
            if q and not s.get("caudal_m3_h"):
                partes.append(f"caudal a la temperatura de salida: {_cifra(q * 3600, 'm³/h')}")
            self.lbl_salida.setText(" · ".join(partes))
            self.lbl_salida.setVisible(bool(partes))
        if hasattr(self, "perfil") and not self._horas_mal():
            self.perfil.perfil = F.perfil(f)
            self.perfil.update()
        if hasattr(self, "panel") and m == "superficie":   # una superficie, en 3D con los edificios de la planta (y su emisión encima)
            self._pinta_superficie()
        if hasattr(self, "curva_viento"):                  # su emisión con el viento: la curva y unas cifras
            ev = f.get("emision_viento") or {}
            self.curva_viento.poner(ev.get("exponente"), ev.get("viento_ref_m_s"))
            if F.factor_viento(f, 5.0) != 1.0 or ev.get("exponente") == 0:
                cifras = " · ".join(f"×{_num(F.factor_viento(f, u), 1)} con {_num(u, 0)} m/s" for u in (2.0, 5.0, 10.0))
                tema.texto(self.lbl_viento, f"{cifras}<br><span style='color:$tenue'>Con el viento junto a la superficie, no el de 10 m. "
                                            "Aún no entra en la simulación: se aplicará con el viento de cada hora.</span>")
            else:
                tema.texto(self.lbl_viento, "<span style='color:$fallo'>Faltan el exponente y el viento de la medida</span>")
        if hasattr(self, "panel") and m == "volumen":      # un volumen, igual; su altura de emisión, sin dato, la mitad de su alto
            self._pinta_volumen()
            a, h = F.area_m2(f), F.altura_emision(f)
            self.lin_area.setText(f"{_num(a, 0)} m²" if a else "")
            self.lin_altura_vol.setPlaceholderText(f"≈ {_fmt(round(h, 1))}" if (h and f.get("altura_m") in (None, "")) else "[m]")
        # olor en lo que usa el modelo (regla 1: en las áreas, por m²)
        q, gs, medido = F.olor_ouE_s(f), F.gases_g_s(f), F.olor_medido(f) is not None
        if hasattr(self, "olor_gases"):                    # el editor: el olor de cada gas y el del foco
            self.olor_gases.poner([(F.NOMBRES.get(g, g), v * 1e6 / F.ug_por_ouE(g) if F.ug_por_ouE(g) else None) for g, v in gs.items()])
            if q is None:
                tema.texto(self.lbl_olor, "<span style='color:$tenue'>Sin olor: falta lo que emite</span>")
            else:
                origen = "olfatometría" if medido else F.NOMBRES.get(F.gas_dominante(f)[1], F.gas_dominante(f)[1])
                txt = f"Olor del foco: {_cifra(q, 'ou_E/s')} <span style='color:$tenue;font-weight:400'>· {origen}</span>"
                if m == "superficie":
                    txt += f" <span style='color:$tenue;font-weight:400'>· {_cifra(F.por_m2(f, q), 'ou_E/(s·m²)')}</span>"
                tema.texto(self.lbl_olor, txt)
        elif q is None:
            tema.texto(self.lbl_olor, "Sin emisión de olor." if gs else
                       "<span style='color:$aviso'>Faltan datos para la emisión de olor.</span>")
        else:
            txt = (f"<b>Emisión de olor: {_cifra(q, 'ou_E/s')}</b>" if medido else
                   f"<b>Emisión de olor estimada por {F.NOMBRES.get(F.gas_dominante(f)[1], F.gas_dominante(f)[1])}: "
                   f"{_cifra(q, 'ou_E/s')}</b>")
            if m == "superficie":
                txt += f" · {_cifra(F.por_m2(f, q), 'ou_E/(s·m²)')}"
            tema.texto(self.lbl_olor, txt)
        for g, lbl in self.lbl_gases:
            v = gs.get(g.get("gas"))
            lbl.setText("" if v is None else f"= {_cifra(v, 'g/s')}")
        for g, lbl in self.lbl_masas:
            m_mol = F.GASES.get(g.get("gas"), (None,))[0]
            lbl.setText(f"{_num(m_mol, 1)} g/mol" if m_mol else "")
        falta = F.pendientes(f, operacion=self._operabilidad)
        partes = []
        if self._recalcular(f) and self._operabilidad:      # el editor no lo dice: guardar un foco lo simula (usuario, 2026-11-08)
            partes.append("⟳ Habrá que simularlo para el reanálisis.")
        if falta:
            partes.append("Falta: " + ", ".join(falta) + ".")
        self.lbl_estado.setText(" ".join(partes))
        self.lbl_estado.setVisible(bool(partes))


class PlanoEsperando(QtWidgets.QStackedWidget):
    """El plano de los focos con «Cargando el plano…» encima hasta que avisa de que está listo: la primera vez tarda unos segundos (el motor
    de la página web), y un hueco vacío parecía que no salía."""

    def __init__(self, mapa, parent=None):
        super().__init__(parent)
        self.espera = QtWidgets.QLabel("Cargando el plano…", alignment=QtCore.Qt.AlignmentFlag.AlignCenter, objectName="nota")
        self.addWidget(self.espera)
        self.addWidget(mapa)
        mapa.listo.connect(lambda: self.setCurrentWidget(mapa))


class FichaVista(QtWidgets.QWidget):
    """La ficha de un foco, para leer: sus cifras según el modelo, su emisión de olor y de gases y lo que le falta. Sin casillas ni la
    operabilidad (usuario, 2026-11-08). Las observaciones de la visita, solo para el administrador. Arriba, sus características (con su
    propia barra si no caben); abajo, siempre a la vista, el foco en 3D con los edificios de la planta, el mismo visor del editor, para mirar
    (usuario, 2026-11-08: «cuando seleccionas un foco, en el panel derecho las características principales arriba y abajo el visor 3D»)."""
    ALTO_VISOR = 330

    def __init__(self, foco, estado="ok", admin=False, parent=None):
        super().__init__(parent)
        self.setObjectName("cuerpo_ficha")
        self.f = foco
        fuera = QtWidgets.QVBoxLayout(self)
        fuera.setContentsMargins(0, 0, 0, 0)
        fuera.setSpacing(0)
        datos = QtWidgets.QWidget(objectName="cuerpo_ficha")
        self.area_datos = QtWidgets.QScrollArea(objectName="ficha")
        self.area_datos.setWidgetResizable(True)
        self.area_datos.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.area_datos.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.area_datos.setMinimumHeight(140)
        self.area_datos.setWidget(datos)
        fuera.addWidget(self.area_datos, 1)
        lay = QtWidgets.QVBoxLayout(datos)
        lay.setContentsMargins(18, 16, 18, 12)
        lay.setSpacing(12)
        self._lay = lay
        cab = QtWidgets.QVBoxLayout()
        cab.setSpacing(2)
        t = QtWidgets.QLabel(foco.get("nombre") or foco["id"], wordWrap=True)
        t.setStyleSheet("font-size:18px;font-weight:700")
        cab.addWidget(t)
        cab.addWidget(QtWidgets.QLabel(F.subtitulo(foco), objectName="subtitulo", wordWrap=True))
        if foco.get("unidad"):
            cab.addWidget(QtWidgets.QLabel(foco["unidad"], objectName="nota", wordWrap=True))
        lay.addLayout(cab)
        avisos = []
        if estado != "ok":
            avisos.append("⟳ " + {"sin_calcular": "Sin simular: hay que calcular su dispersión para el reanálisis.",
                                  "cambiado": "Modificado desde que se simuló: hay que volver a calcular su dispersión."}[estado])
        falta = F.pendientes(foco, operacion=False)              # la operabilidad, en la operación
        if falta:
            avisos.append("Falta: " + "; ".join(falta) + ".")
        self.lbl_avisos = QtWidgets.QLabel(wordWrap=True, textFormat=QtCore.Qt.TextFormat.RichText)
        tema.texto(self.lbl_avisos, "<br>".join(f"<span style='color:$aviso'>{html.escape(a)}</span>" for a in avisos))
        self.lbl_avisos.setVisible(bool(avisos))
        lay.addWidget(self.lbl_avisos)
        self._cifras()
        self._emision()
        if admin and (foco.get("observaciones") or "").strip():
            lay.addWidget(QtWidgets.QLabel("OBSERVACIONES DE LA VISITA", objectName="seccion"))
            lay.addWidget(QtWidgets.QLabel(foco["observaciones"], wordWrap=True))
        lay.addStretch()
        # abajo, el foco en 3D
        abajo = QtWidgets.QWidget(objectName="cuerpo_ficha")
        v = QtWidgets.QVBoxLayout(abajo)
        v.setContentsMargins(18, 6, 18, 16)
        v.setSpacing(6)
        v.addWidget(QtWidgets.QLabel("EN 3D", objectName="seccion"))
        self.visor = self._visor()
        self.visor.setMinimumHeight(self.ALTO_VISOR)
        self.visor.setMaximumHeight(self.ALTO_VISOR)
        v.addWidget(self.visor)
        fuera.addWidget(abajo)

    def _visor(self):
        """El visor 3D del editor según su modelo, con los edificios de la planta: la chimenea con su estela (la guardada), la superficie o
        el volumen, con lo que emite encima. Para mirar: girar, mover, acercar; no cambia el foco."""
        from teodors.gui import focos_graficos as G
        from teodors.operacion import edificios_planta as EP
        f, m = self.f, self.f["modelo"]
        try:
            eds = EP.cargar()["edificios"]
        except (ValueError, OSError):
            eds = []
        q, a = F.olor_ouE_s(f), F.area_m2(f)
        if m == "punto":
            from teodors.operacion import estela as E
            visor = G.PanelEstela()
            u = f.get("ubicacion") or {}
            if "x" not in u or "y" not in u:
                visor.poner(f, [], None, "sin_punto")
                return visor
            try:
                cerca = E.edificios_cerca(u["x"], u["y"])
            except Exception as e:                                     # noqa: BLE001 — sin edificios, el visor igual
                log.warning(f"Sin los edificios de alrededor del foco {f['id']}: {e}")
                cerca = []
            visor.poner(f, cerca, f.get("edificios"), "ok" if cerca else "sin_edificios")
            return visor
        pila = m == "volumen" and F.clase_volumen(f) == "pila"
        etiqueta = " · ".join(([f"{_num(a, 0)} m²"] if a and (m == "superficie" or pila) else []) + ([f"{cifra_corta(q)} ou_E/s"] if q else []))
        visor = G.PanelSuperficie() if m == "superficie" else G.PanelVolumen()
        visor.poner(f, eds, etiqueta)
        return visor

    # ── las cifras, según el modelo ──────────────────────────────────────────────────────────────────────────
    def cifras(self):
        """[(icono, valor, qué es)] del foco, según su modelo; los datos que faltan, «—»."""
        f, m = self.f, self.f["modelo"]
        alt = f.get("altura_m")
        altura = ("altura", _cifra(alt, "m") if alt not in (None, "") else "—", "altura de emisión")
        if m == "punto":
            s = f.get("salida") or {}
            q = F.caudal_m3_s(f)
            area = F.area_m2(f)
            v = s.get("velocidad_m_s") or (q / area if q and area else None)
            t = s.get("temperatura_C")
            filas = [altura, ("diametro", _cifra(s.get("diametro_m"), "m"), "diámetro"),
                     ("caudal", _cifra(q * 3600 if q else None, "m³/h"), "caudal a la salida"),
                     ("velocidad", _cifra(v, "m/s"), "velocidad de salida"),
                     ("temperatura", "—" if t in (None, "") else f"{_num(t)} °C", "temperatura")]
            o = s.get("orientacion") or "vertical"
            filas.append(("sal_" + o, F.ORIENTACIONES.get(o, F.ORIENTACIONES["vertical"])[0], "hacia dónde sale"))
            if f.get("edificios"):                               # la estela de los edificios, que calcula el editor
                from teodors.operacion import estela as E
                n, libre = E.resumen(f["edificios"], alt)
                filas += [("edificio", f"{n} de 36", "vientos en la estela de un edificio"),
                          ("altura", _cifra(libre, "m") if libre else "—", "altura para salir libre")]
            return filas
        if m == "superficie":
            clase = F.clase_superficie(f)
            filas = [("sup_" + clase, F.CLASES_SUPERFICIE[clase][0], "clase"), ("f_superficie", _cifra(F.area_m2(f), "m²"), "área"),
                     ("altura", "a ras de suelo" if alt in (None, "") or not float(alt) else _cifra(alt, "m"), "altura de emisión")]
            sobre = (f.get("superficie") or {}).get("sobre")
            if sobre:
                from teodors.operacion import edificios_planta as EP
                try:
                    e = next((e for e in EP.cargar()["edificios"] if e["id"] == sobre), None)
                except (ValueError, OSError):
                    e = None
                filas.append(("edificio", (e.get("nombre") or e["id"]) if e else sobre, "en la boca de"))
            if f.get("material"):
                filas.append(("material", f["material"], "material y fase"))
            return filas + self._cifras_salida() + self._cifra_viento()
        clase = F.clase_volumen(f)
        d = f.get("dimensiones") or {}
        medidas = " × ".join(_num(d[k], 1) for k in ("largo_m", "ancho_m", "alto_m") if d.get(k))
        pila = clase == "pila" and f.get("volumen")
        h = F.altura_emision(f)
        seccion = (f.get("volumen") or {}).get("seccion") or "hilera"
        filas = [("sec_" + seccion, F.SECCIONES_PILA[seccion], "pila o hilera") if pila else ("vol_" + clase, F.CLASES_VOLUMEN[clase], "clase"),
                 ("f_volumen", f"{medidas} m" if medidas else "—", "largo × ancho × alto"),
                 ("f_superficie", _cifra(F.area_m2(f), "m²"), "piel que emite" if pila else "planta del volumen"),
                 ("altura", _cifra(h, "m") if h not in (None, "") else "—", "altura de emisión")]
        if (f.get("ubicacion") or {}).get("x") is not None and d.get("largo_m") and d.get("ancho_m"):
            filas.append(("rumbo", f"{_num(F.rumbo(f), 0)}°", "rumbo del largo"))
            n = len(F.partes_volumen(f))
            if n > 1:
                filas.append(("f_volumen", str(n), "volúmenes en el modelo"))
        return filas + self._cifras_salida() + self._cifra_viento()

    def _cifras_salida(self):
        """El gas de salida de una superficie o un volumen, si lo tiene: su caudal y su temperatura."""
        f, s = self.f, self.f.get("salida") or {}
        filas = []
        q = F.caudal_m3_s(f)
        if q:
            filas.append(("caudal", _cifra(q * 3600, "m³/h"), "caudal de salida"))
        if s.get("temperatura_C") not in (None, ""):
            filas.append(("temperatura", f"{_num(s['temperatura_C'])} °C", "temperatura"))
        return filas

    def _cifra_viento(self):
        """Lo que emite con el viento: constante, o (u / u_ref)^β."""
        ev = self.f.get("emision_viento")
        if not ev:
            return [("viento_constante", "Constante", "emisión con el viento")]
        return [("viento_viento", f"×{_num(F.factor_viento(self.f, 5.0), 1)} con 5 m/s", "emisión con el viento")]

    def _cifras(self):
        rejilla = QtWidgets.QGridLayout()
        rejilla.setHorizontalSpacing(8)
        rejilla.setVerticalSpacing(8)
        for k, (icono, valor, que) in enumerate(self.cifras()):
            caja = QtWidgets.QFrame(objectName="cifra")
            v = QtWidgets.QVBoxLayout(caja)
            v.setContentsMargins(10, 8, 10, 8)
            v.setSpacing(2)
            arriba = QtWidgets.QHBoxLayout()
            arriba.setSpacing(7)
            ico = QtWidgets.QLabel()
            tema.pon_icono(ico, icono, "acento", 18)
            val = QtWidgets.QLabel(valor, objectName="cifra_v", wordWrap=True)
            arriba.addWidget(ico, 0, QtCore.Qt.AlignmentFlag.AlignTop)
            arriba.addWidget(val, 1)
            v.addLayout(arriba)
            v.addWidget(QtWidgets.QLabel(que, objectName="nota", wordWrap=True))
            rejilla.addWidget(caja, k // 2, k % 2)
        for c in range(2):
            rejilla.setColumnStretch(c, 1)
        self._lay.addLayout(rejilla)

    # ── la emisión ───────────────────────────────────────────────────────────────────────────────────────────
    def _emision(self):
        f = self.f
        self._lay.addWidget(QtWidgets.QLabel("EMISIÓN", objectName="seccion"))
        q, medido = F.olor_ouE_s(f), F.olor_medido(f) is not None
        o = f.get("olor") or {}
        grande = QtWidgets.QLabel(objectName="cifra_v", textFormat=QtCore.Qt.TextFormat.RichText)
        detalle = QtWidgets.QLabel(objectName="nota", wordWrap=True)
        if q is None:
            grande.setText("Sin emisión de olor")
        else:
            grande.setText(f"Olor {_cifra(q, 'ou_E/s')}")
            partes = []
            if medido:
                partes.append(f"olfatometría: {_fmt(o.get('valor'))} {o.get('unidad', '').replace('m3', 'm³').replace('m2', 'm²')}"
                              + (f" ({o['fecha']})" if o.get("fecha") else ""))
            else:
                gas = F.gas_dominante(f)[1]
                partes.append(f"estimada por su {F.NOMBRES.get(gas, gas)} (umbral de Nagata)")
            if f["modelo"] == "superficie" and not (medido and o.get("unidad") == "ou_E/(s·m2)"):     # si no es ya el dato
                partes.append(_cifra(F.por_m2(f, q), "ou_E/(s·m²)"))
            detalle.setText(" · ".join(partes))
        self._lay.addWidget(grande)
        self._lay.addWidget(detalle)
        self.filas_gases = self.gases()
        if not self.filas_gases:
            return
        rejilla = QtWidgets.QGridLayout()
        rejilla.setHorizontalSpacing(12)
        rejilla.setVerticalSpacing(4)
        for c, t in enumerate(("Gas", "Medido", "Emisión", "Olor equivalente")):
            rejilla.addWidget(QtWidgets.QLabel(t, objectName="seccion"), 0, c)
        for k, (nombre, medida, g_s, ou) in enumerate(self.filas_gases, 1):
            for c, t in enumerate((nombre, medida, _cifra(g_s, "g/s"), _cifra(ou, "ou_E/s"))):
                rejilla.addWidget(QtWidgets.QLabel(t), k, c)
        rejilla.setColumnStretch(3, 1)
        self._lay.addLayout(rejilla)

    def gases(self):
        """[(nombre, lo medido con su unidad, g/s, ou_E/s equivalentes por Nagata)] de sus gases, del de más olor al de menos."""
        gs = F.gases_g_s(self.f)
        filas = []
        for g in self.f.get("gases") or []:
            clave = g.get("gas")
            g_s = gs.get(clave)
            umbral = F.ug_por_ouE(clave) if clave in F.GASES else None
            ou = g_s * 1e6 / umbral if (g_s is not None and umbral) else None
            filas.append((F.NOMBRES.get(clave, str(clave)), f"{_fmt(g.get('valor'))} {g.get('unidad', '')}".replace("m3", "m³")
                          .replace("m2", "m²"), g_s, ou))
        return sorted(filas, key=lambda t: -(t[3] or 0))


class VentanaFocos(QtWidgets.QWidget):
    """Segunda ventana (no modal) con los focos de la planta, para consultarlos. Con el usuario administrador, además, crear, modificar y
    eliminar (debajo de la lista)."""
    guardado = QtCore.Signal()

    def __init__(self, emp, ajustes, parent=None):
        super().__init__(parent, QtCore.Qt.WindowType.Window)
        self.emp, self.ajustes = emp, ajustes
        self.editable = config.MODO_EDICION
        self.setWindowTitle(f"Focos de la planta · {config.APP_NOMBRE}"
                            + (f" · {config.pide('operacion', 'texto_modo_edicion')}" if self.editable else ""))
        tema.estilo(self, tema.ESTILO_VENTANAS)
        self.resize(1400, 860)
        self._recargar()

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._cabecera())
        self.divisor = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.divisor.setChildrenCollapsible(False)
        self.divisor.addWidget(self._navegacion())
        self.mapa = VistaFocos()
        self.mapa.setMinimumWidth(360)
        self.plano = PlanoEsperando(self.mapa)
        self.divisor.addWidget(self.plano)
        self.area_ficha = QtWidgets.QScrollArea(objectName="ficha")
        self.area_ficha.setWidgetResizable(True)
        self.area_ficha.setMinimumWidth(380)
        self.area_ficha.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.area_ficha.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.divisor.addWidget(self.area_ficha)
        self.divisor.setStretchFactor(1, 1)
        self.divisor.setSizes([300, 640, 440])
        lay.addWidget(self.divisor, 1)

        geom = self.ajustes.value("focos/geometria")
        if geom is not None:
            self.restoreGeometry(geom)
        div = self.ajustes.value("focos/divisor_v3")
        if div is not None:
            self.divisor.restoreState(div)
        self.mapa.listo.connect(self._mapa_listo)
        self.mapa.foco.connect(self._elegir_id)
        self.mapa.cargar(emp)
        self._rellenar()
        tema.manos(self)

    # ── datos ────────────────────────────────────────────────────────────────────────────
    def _recargar(self):
        try:
            self.datos = F.cargar()
        except (ValueError, OSError) as e:
            log.error(f"No se pudo leer {config.FOCOS_JSON.name}: {e}")
            self.datos = F.vacio()
        from teodors.operacion import simulacion
        try:
            self.estados = simulacion.estado_respuestas(self.datos)
        except Exception as e:                                  # noqa: BLE001 (sin saber si está simulado, se ve igual)
            log.warning(f"No se sabe qué focos están simulados: {e}")
            self.estados = {}

    def _foco(self, id_foco):
        return next((f for f in self.datos["focos"] if f["id"] == id_foco), None)

    # ── construcción ─────────────────────────────────────────────────────────────────────
    def _cabecera(self):
        w = QtWidgets.QWidget(objectName="cabecera")
        w.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(18, 10, 18, 10)
        h.addWidget(QtWidgets.QLabel("Focos de la planta", objectName="titulo"), 1)
        if self.editable:
            h.addWidget(QtWidgets.QLabel(config.pide("operacion", "texto_modo_edicion"), objectName="admin_marca"))
        b_cerrar = QtWidgets.QPushButton("Cerrar")
        b_cerrar.clicked.connect(self.close)
        h.addWidget(b_cerrar)
        return w

    def _navegacion(self):
        w = QtWidgets.QWidget(objectName="nav")
        w.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        w.setMinimumWidth(240)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(10, 12, 10, 12)
        v.setSpacing(6)
        self.lbl_n = QtWidgets.QLabel(objectName="seccion")
        v.addWidget(self.lbl_n)
        self.lista = QtWidgets.QListWidget(objectName="lista")
        self.lista.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.lista.currentRowChanged.connect(self._fila_elegida)
        # debajo, todos los focos en 3D, con los edificios (usuario, 2026-11-08: «debajo de la lista de focos, el visor 3D con todos los
        # focos»); entre los dos, un divisor que se arrastra
        from teodors.gui.focos_graficos import VisorFocos3D
        abajo = QtWidgets.QWidget()
        va = QtWidgets.QVBoxLayout(abajo)
        va.setContentsMargins(0, 6, 0, 0)
        va.setSpacing(6)
        va.addWidget(QtWidgets.QLabel("EN 3D", objectName="seccion"))
        self.visor_planta = VisorFocos3D()
        self.visor_planta.pulsado.connect(self._elegir_id)
        va.addWidget(self.visor_planta, 1)
        self.divisor_nav = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.divisor_nav.setChildrenCollapsible(False)
        self.divisor_nav.addWidget(self.lista)
        self.divisor_nav.addWidget(abajo)
        self.divisor_nav.setStretchFactor(0, 1)
        self.divisor_nav.setStretchFactor(1, 1)
        self.divisor_nav.setSizes([420, 380])
        v.addWidget(self.divisor_nav, 1)
        self.b_crear = self.b_modificar = self.b_eliminar = None
        if self.editable:                                   # solo el administrador: crear, modificar y eliminar
            fila = QtWidgets.QHBoxLayout()
            fila.setSpacing(6)
            self.b_crear = QtWidgets.QPushButton("Crear", objectName="primario")
            self.b_modificar = QtWidgets.QPushButton("Modificar")
            self.b_eliminar = QtWidgets.QPushButton("Eliminar")
            self.b_crear.setToolTip("Un foco nuevo: su geometría en el mapa y su ficha")
            self.b_modificar.setToolTip("Cambiar la geometría o la ficha del foco elegido")
            self.b_eliminar.setToolTip("Quitar el foco elegido de la planta")
            self.b_crear.clicked.connect(self.crear)
            self.b_modificar.clicked.connect(self.modificar)
            self.b_eliminar.clicked.connect(self.eliminar)
            for b in (self.b_crear, self.b_modificar, self.b_eliminar):
                fila.addWidget(b, 1)
            v.addLayout(fila)
        return w

    def _texto_emision(self, foco):
        try:
            q = F.olor_ouE_s(foco)
        except (ValueError, TypeError, KeyError):
            q = None
        return f"{cifra_corta(q)} ou_E/s" if q else "sin olor"

    def _rellenar(self, elegir=None):
        """La lista y el plano desde self.datos."""
        focos = self.datos["focos"]
        self.lbl_n.setText(f"FOCOS ({len(focos)})")
        self.lista.blockSignals(True)
        self.lista.clear()
        for f in focos:
            it = QtWidgets.QListWidgetItem()
            it.setData(QtCore.Qt.ItemDataRole.UserRole, f["id"])
            it.setSizeHint(QtCore.QSize(200, 50))
            self.lista.addItem(it)
            item = ItemFoco(f)
            item.tipo.setText(self._texto_emision(f))
            item.pendiente(self.estados.get(f["id"], "ok"))
            self.lista.setItemWidget(it, item)
        self.lista.blockSignals(False)
        if not focos:
            self._mostrar_ficha(None)
        else:
            ids = [f["id"] for f in focos]
            self.lista.setCurrentRow(ids.index(elegir) if elegir in ids else 0)   # → _fila_elegida
        for b in (self.b_modificar, self.b_eliminar):
            if b is not None:
                b.setEnabled(bool(focos))
        self.mapa.set_focos(focos, encuadrar=False)
        if self.lista.currentItem() is not None:
            self.mapa.elegir(self._id_actual(), mostrar=False)
        from teodors.operacion import edificios_planta as EP
        try:
            eds = EP.cargar()["edificios"]
        except (ValueError, OSError):
            eds = []
        self.visor_planta.poner(focos, eds, self._id_actual())

    def _mapa_listo(self):
        self.mapa.set_focos(self.datos["focos"], encuadrar=False)          # la vista, la de la planta (`showEvent`)
        if self._id_actual():
            self.mapa.elegir(self._id_actual(), mostrar=False)

    def showEvent(self, evento):
        """Cada vez que se abre, el plano con la vista de «Ver la planta» (usuario, 2026-11-09)."""
        super().showEvent(evento)
        if not evento.spontaneous():
            self.mapa.ver_planta()

    def _id_actual(self):
        it = self.lista.currentItem()
        return it.data(QtCore.Qt.ItemDataRole.UserRole) if it is not None else None

    # ── elegir y ver ─────────────────────────────────────────────────────────────────────
    def _fila_elegida(self, fila):
        if fila < 0:
            return
        id_foco = self.lista.item(fila).data(QtCore.Qt.ItemDataRole.UserRole)
        self._mostrar_ficha(self._foco(id_foco))
        self.mapa.elegir(id_foco)
        if hasattr(self, "visor_planta"):
            self.visor_planta.elegir(id_foco)

    def _elegir_id(self, id_foco):
        for k in range(self.lista.count()):
            if self.lista.item(k).data(QtCore.Qt.ItemDataRole.UserRole) == id_foco:
                self.lista.setCurrentRow(k)
                return

    def _mostrar_ficha(self, foco):
        if foco is None:
            vacio = QtWidgets.QLabel("Aún no hay focos.", wordWrap=True)
            vacio.setContentsMargins(16, 16, 16, 16)
            vacio.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
            self.area_ficha.setWidget(vacio)
            return
        self.ficha = FichaVista(foco, self.estados.get(foco["id"], "ok"), self.editable)
        self.area_ficha.setWidget(self.ficha)

    # ── crear, modificar y eliminar: solo el administrador ───────────────────────────────────────────────────
    def crear(self):
        self._editor(None)

    def modificar(self):
        foco = self._foco(self._id_actual())
        if foco is not None:
            self._editor(foco)

    def _editor(self, foco):
        """El editor de focos (`gui.editor_focos`): crea (foco None) o modifica; al guardar, la lista se rehace con él elegido."""
        if not self.editable:
            return
        from teodors.gui.editor_focos import EditorFoco
        self.editor = EditorFoco(self.emp, self.ajustes, self.datos, foco)
        self.editor.guardado.connect(self._editado)
        self.editor.show()
        self.editor.raise_()
        self.editor.activateWindow()

    def _editado(self, id_foco):
        self._recargar()
        self._rellenar(elegir=id_foco)
        self.guardado.emit()

    def edificios_cambiados(self):
        """Los edificios de la planta se han guardado: la estela de los focos punto, ya recalculada y guardada
        (`edificios_planta.recalcular_focos`), en la lista y en la ficha; y en el editor abierto, en su panel 3D."""
        self._recargar()
        self._rellenar(elegir=self._id_actual())
        editor = getattr(self, "editor", None)
        if editor is not None and editor.isVisible():                 # cerrado, se queda oculto: no hace falta
            editor.edificios_cambiados()

    def eliminar(self):
        foco = self._foco(self._id_actual())
        if not self.editable or foco is None:
            return
        if not widgets.preguntar_si(self, "Eliminar foco", f"¿Eliminar el foco {foco['id']} «{foco.get('nombre')}» de la planta?\n"
                                    "Los planes que lo usen dejarán de tenerlo en cuenta."):
            return
        self.datos["focos"].remove(foco)
        try:
            ruta = F.guardar(self.datos)
        except (ValueError, OSError) as e:
            self.datos["focos"].append(foco)
            log.error(f"No se pudo eliminar el foco: {e}")
            QtWidgets.QMessageBox.warning(self, "Eliminar foco", str(e))
            return
        log.info(f"Foco {foco['id']} «{foco.get('nombre')}» eliminado ({ruta}).")
        self._recargar()
        self._rellenar()
        self.guardado.emit()

    def closeEvent(self, evento):
        self.ajustes.setValue("focos/geometria", self.saveGeometry())
        self.ajustes.setValue("focos/divisor_v3", self.divisor.saveState())
        super().closeEvent(evento)
