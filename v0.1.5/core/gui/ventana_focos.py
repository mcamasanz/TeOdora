# -*- coding: utf-8 -*-
"""Ventana de los focos de la planta (maqueta aprobada por el usuario el 2026-10-25: «es justo
como lo quiero»): pestañas verticales por foco a la izquierda, plano de la planta en el centro con
el foco elegido recuadrado y rotulado (gui/focos_mapa.py) y su ficha a la derecha según el modelo
(punto, superficie o volumen). La etiqueta «recalcula» marca lo que obliga a recalcular el foco.

Modo operario (por defecto): SOLO CONSULTA; el operario crea escenarios de operación, nunca focos
(decisión del usuario, 2026-10-25). Modo de edición (`planta.MODO_EDICION`; `gui.principal`, --<operacion.modo_edicion>): añadir y quitar focos,
dibujarlos en el plano y cambiar cualquier dato; «Guardar» escribe el focos.json de la planta (`operacion.focos`).
"""
from PySide6 import QtCore, QtGui, QtWidgets

from teodors import planta as config
from teodors.comun import registro
from teodors.comun.formato import num as _num
from teodors.gui import tema
from teodors.gui.focos_mapa import COLORES, VistaFocos
from teodors.gui.tema import c
from teodors.gui.widgets import preguntar_si_guardar
from teodors.operacion import focos as F
from teodors.planta import geo

log = registro.get("focos")


def _fmt(v):
    """Número para un campo: coma decimal, sin ceros de sobra, miles con espacio."""
    if v in (None, ""):
        return ""
    v = float(v)
    if v.is_integer() and abs(v) >= 1000:
        return _num(v)
    return f"{v:.6g}".replace(".", ",")


def _leer(texto):
    """«12,5», «12.5» o «30 000» → float; vacío → None."""
    t = texto.strip().replace(" ", "").replace(" ", "").replace(",", ".")
    return float(t) if t else None


def _cifra(v, unidad):
    if v is None:
        return "—"
    dec = 0 if abs(v) >= 100 else (1 if abs(v) >= 10 else (2 if abs(v) >= 0.1 else 4))
    return f"{_num(v, dec)} {unidad}"


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
    """Pestaña de la lista: nombre, tipo y modelo."""

    def __init__(self, foco, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 8, 6)
        txt = QtWidgets.QVBoxLayout()
        txt.setSpacing(0)
        self.nombre = _Recortado()
        self.nombre.setStyleSheet("font-weight:600;font-size:13px;background:transparent")
        self.tipo = _Recortado()
        tema.estilo(self.tipo, "color:$tenue;font-size:11.5px;background:transparent")
        txt.addWidget(self.nombre)
        txt.addWidget(self.tipo)
        lay.addLayout(txt, 1)
        self.modelo = QtWidgets.QLabel()
        lay.addWidget(self.modelo)
        self.poner(foco)

    def poner(self, foco):
        self.nombre.setText(foco.get("nombre") or foco["id"])
        self.tipo.setText(F.nombre_tipo(foco))
        relleno, borde = COLORES[foco["modelo"]]
        r, g, b = (int(relleno[k:k + 2], 16) for k in (1, 3, 5))
        self.modelo.setText(F.MODELOS[foco["modelo"]])
        tema.estilo(self.modelo, f"font-size:11px;color:$texto;border:1px solid {borde};"
                                 f"border-radius:9px;padding:1px 7px;"
                                 f"background:rgba({r},{g},{b},0.35)")


class Ficha(QtWidgets.QWidget):
    """Ficha de un foco según su modelo. Cambia el diccionario del foco EN SU SITIO."""
    cambiado = QtCore.Signal(str)        # clave de primer nivel que ha cambiado
    rehacer = QtCore.Signal()            # volver a montar la ficha (cambio de modo, de unidad…)
    ubicar = QtCore.Signal()             # dibujar la ubicación en el plano

    def __init__(self, foco, editable, recalcular, parent=None):
        super().__init__(parent)
        self.setObjectName("cuerpo_ficha")
        self.f, self.ed = foco, editable
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
        cab.addWidget(QtWidgets.QLabel(f"{F.nombre_tipo(foco)} · {F.MODELOS[foco['modelo']]} · "
                                       f"{foco['id']}", objectName="subtitulo", wordWrap=True))
        lay.addLayout(cab)
        self.lbl_estado = QtWidgets.QLabel(wordWrap=True, objectName="estado_falta")
        lay.addWidget(self.lbl_estado)
        self._recalcular = recalcular

        self._identificacion()
        {"punto": self._punto, "superficie": self._superficie, "volumen": self._volumen}[foco["modelo"]]()
        self._funcionamiento()
        self._olor()
        self._gases()
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
        if recalcula:
            tag = QtWidgets.QLabel("recalcula", objectName="recalcula")
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
            r.toggled.connect(lambda si, c=clave: si and al_elegir(c))
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
        caja.addWidget(self._campo("Nombre", ("nombre",), "[nombre en la planta]", numero=False))
        caja.addWidget(self._campo("Unidad de la planta", ("unidad",), "[unidad]", numero=False))
        fila = QtWidgets.QHBoxLayout()
        fila.addWidget(self._etiqueta("Ubicación", recalcula=True), 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.lbl_ubicacion = QtWidgets.QLabel(objectName="nota")
        fila.addWidget(self.lbl_ubicacion, 1)
        if self.ed:
            b = QtWidgets.QPushButton("Dibujar en el mapa" if self.f["modelo"] == "superficie"
                                      else "Marcar en el mapa")
            b.clicked.connect(self.ubicar)
            fila.addWidget(b)
        caja.addLayout(fila)

    def _punto(self):
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

    def _superficie(self):
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

    def _volumen(self):
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
        m, tipo = self.f["modelo"], self.f.get("tipo")
        defecto = ("ou_E/m3" if (m == "punto" or tipo == "biofiltro")
                   else ("ou_E/(s·m2)" if m == "superficie" else "ou_E/s"))
        o.setdefault("unidad", defecto)
        texto = {"ou_E/m3": "Olfatometría a la salida", "ou_E/(s·m2)": "Olfatometría por m²",
                 "ou_E/s": "Olfatometría, emisión total"}[o["unidad"]]
        campos = [self._valor_unidad(("olor",), list(F.UNIDADES_OLOR), texto),
                  self._campo("Fecha de la medida", ("olor", "fecha"), "[dd/mm/aaaa]", numero=False)]
        unidades = [o["unidad"]] + [g.get("unidad", "ppm") for g in self.f.get("gases") or []]
        if m != "punto" and set(unidades) & set(F.UNIDADES_CONCENTRACION):
            campos.append(self._campo("Caudal tratado" if tipo == "biofiltro" else "Caudal",
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

    def _gases(self):
        caja = self._seccion("Gases")
        lista = self.f.setdefault("gases", [])
        self.lbl_gases = []
        for k, g in enumerate(lista):
            fila = QtWidgets.QHBoxLayout()
            fila.setSpacing(4)
            fila.addWidget(self._combo([(n, F.NOMBRES.get(n, n)) for n in F.GASES], g.get("gas"),
                                       lambda c, g=g: self._cambia_gas(g, "gas", c)))
            e = QtWidgets.QLineEdit(_fmt(g.get("valor")), readOnly=not self.ed)
            e.setPlaceholderText("[valor]")
            if self.ed:
                e.editingFinished.connect(lambda e=e, g=g: self._valor_gas(e, g))
            fila.addWidget(e, 1)
            fila.addWidget(self._combo([(u, u.replace("m3", "m³").replace("m2", "m²"))
                                        for u in F.UNIDADES_GAS], g.get("unidad", "ppm"),
                                       lambda u, g=g: self._cambia_gas(g, "unidad", u)))
            r = QtWidgets.QLabel(objectName="nota")
            r.setMinimumWidth(70)
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
            b = QtWidgets.QPushButton("+ Añadir gas")
            b.clicked.connect(lambda: (lista.append({"gas": "H2S", "valor": None, "unidad": "ppm"}),
                                       self.cambiado.emit("gases"), self.rehacer.emit()))
            caja.addWidget(b, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)

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
        if m == "punto":
            s, q = f.get("salida") or {}, F.caudal_m3_s(f)
            area = F.area_m2(f)
            partes = []
            if q and area and not s.get("velocidad_m_s"):
                partes.append(f"velocidad calculada con el caudal: {_cifra(q / area, 'm/s')}")
            if q and not s.get("caudal_m3_h"):
                partes.append(f"caudal a la temperatura de salida: {_cifra(q * 3600, 'm³/h')}")
            self.lbl_salida.setText(" · ".join(partes))
            self.lbl_salida.setVisible(bool(partes))
        if not self._horas_mal():
            self.perfil.perfil = F.perfil(f)
            self.perfil.update()
        # olor en lo que usa el modelo (regla 1: en las áreas, por m²)
        q, gs, medido = F.olor_ouE_s(f), F.gases_g_s(f), F.olor_medido(f) is not None
        if q is None:
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
        falta = F.pendientes(f)
        partes = []
        if self._recalcular(f):
            partes.append("⚠ Hay que recalcular este foco.")
        if falta:
            partes.append("Falta: " + ", ".join(falta) + ".")
        self.lbl_estado.setText(" ".join(partes))
        self.lbl_estado.setVisible(bool(partes))


class VentanaFocos(QtWidgets.QWidget):
    """Segunda ventana (no modal) con los focos de la planta."""
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
        self.divisor.addWidget(self.mapa)
        self.area_ficha = QtWidgets.QScrollArea(objectName="ficha")
        self.area_ficha.setWidgetResizable(True)
        # la ficha más ancha pide 454 px (dos columnas de campos con su «recalcula») + la barra de desplazamiento
        self.area_ficha.setMinimumWidth(470)
        self.area_ficha.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.area_ficha.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.divisor.addWidget(self.area_ficha)
        self.divisor.setStretchFactor(1, 1)
        self.divisor.setSizes([300, 620, 480])
        lay.addWidget(self.divisor, 1)

        geom = self.ajustes.value("focos/geometria")
        if geom is not None:
            self.restoreGeometry(geom)
        div = self.ajustes.value("focos/divisor_v2")
        if div is not None:
            self.divisor.restoreState(div)

        self.mapa.listo.connect(self._mapa_listo)
        self.mapa.foco.connect(self._elegir_id)
        self.mapa.ubicacion.connect(self._ubicacion_dibujada)
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
        self._huellas = {f["id"]: F.huella(f) for f in self.datos["focos"]}
        self._sucio = False

    def _recalcular(self, foco):
        """¿Ha cambiado (desde que se abrió) algo que obliga a recalcular el foco?"""
        h0 = self._huellas.get(foco["id"])
        return h0 is not None and h0 != F.huella(foco)

    def _foco(self, id_foco):
        return next((f for f in self.datos["focos"] if f["id"] == id_foco), None)

    # ── construcción ─────────────────────────────────────────────────────────────────────
    def _cabecera(self):
        w = QtWidgets.QWidget(objectName="cabecera")
        w.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(18, 10, 18, 10)
        h.addWidget(QtWidgets.QLabel("Focos de la planta", objectName="titulo"), 1)
        b_cerrar = QtWidgets.QPushButton("Cerrar")
        b_cerrar.clicked.connect(self.close)
        h.addWidget(b_cerrar)
        if self.editable:
            self.b_guardar = QtWidgets.QPushButton("Guardar", objectName="primario")
            self.b_guardar.setEnabled(False)
            self.b_guardar.clicked.connect(self.guardar)
            h.addWidget(self.b_guardar)
        return w

    def _navegacion(self):
        w = QtWidgets.QWidget(objectName="nav")
        w.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        w.setMinimumWidth(220)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(10, 12, 10, 12)
        v.setSpacing(6)
        self.lbl_n = QtWidgets.QLabel(objectName="seccion")
        v.addWidget(self.lbl_n)
        self.lista = QtWidgets.QListWidget(objectName="lista")
        self.lista.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.lista.currentRowChanged.connect(self._fila_elegida)
        v.addWidget(self.lista, 1)
        if self.editable:
            b = QtWidgets.QPushButton("+ Añadir foco", objectName="anadir")
            menu = QtWidgets.QMenu(b)
            for clave, (nombre, modelos, _) in F.TIPOS.items():
                if len(modelos) == 1:
                    menu.addAction(f"{nombre}  ·  {modelos[0]}",
                                   lambda c=clave, m=modelos[0]: self._anadir(c, m))
                else:
                    sub = menu.addMenu(f"{nombre}  ·  {' o '.join(modelos)}")
                    for m in modelos:
                        sub.addAction(F.MODELOS[m], lambda c=clave, m=m: self._anadir(c, m))
            b.setMenu(menu)
            v.addWidget(b)
            self.b_quitar = QtWidgets.QPushButton("Quitar el foco elegido")
            self.b_quitar.clicked.connect(self._quitar)
            v.addWidget(self.b_quitar)
        return w

    def _rellenar(self, elegir=None):
        """Lista de pestañas y plano desde self.datos."""
        focos = self.datos["focos"]
        self.lbl_n.setText(f"FOCOS ({len(focos)})")
        self.lista.blockSignals(True)
        self.lista.clear()
        for f in focos:
            it = QtWidgets.QListWidgetItem()
            it.setData(QtCore.Qt.ItemDataRole.UserRole, f["id"])
            it.setSizeHint(QtCore.QSize(200, 50))
            self.lista.addItem(it)
            self.lista.setItemWidget(it, ItemFoco(f))
        self.lista.blockSignals(False)
        if not focos:
            self._mostrar_ficha(None)
        else:
            ids = [f["id"] for f in focos]
            self.lista.setCurrentRow(ids.index(elegir) if elegir in ids else 0)   # → _fila_elegida
        self.mapa.set_focos(focos, encuadrar=False)
        if self.lista.currentItem() is not None:
            self.mapa.elegir(self._id_actual(), mostrar=False)

    def _mapa_listo(self):
        self.mapa.set_focos(self.datos["focos"], encuadrar=True)
        if self._id_actual():
            self.mapa.elegir(self._id_actual(), mostrar=False)

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

    def _elegir_id(self, id_foco):
        for k in range(self.lista.count()):
            if self.lista.item(k).data(QtCore.Qt.ItemDataRole.UserRole) == id_foco:
                self.lista.setCurrentRow(k)
                return

    def _mostrar_ficha(self, foco, scroll=0):
        if foco is None:
            vacio = QtWidgets.QLabel(
                "Aún no hay focos.", wordWrap=True)
            vacio.setContentsMargins(16, 16, 16, 16)
            vacio.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
            self.area_ficha.setWidget(vacio)
            return
        ficha = Ficha(foco, self.editable, self._recalcular)
        ficha.cambiado.connect(lambda clave, f=foco: self._cambiado(f, clave))
        ficha.rehacer.connect(lambda f=foco: QtCore.QTimer.singleShot(0, lambda: self._rehacer(f)))
        ficha.ubicar.connect(lambda f=foco: self.mapa.dibujar(f["modelo"]))
        self.area_ficha.setWidget(ficha)
        self.area_ficha.verticalScrollBar().setValue(scroll)

    def _rehacer(self, foco):
        """Vuelve a montar la ficha del foco (otro modo u otra unidad) sin perder el sitio."""
        if foco is self._foco(self._id_actual()):
            self._mostrar_ficha(foco, self.area_ficha.verticalScrollBar().value())

    # ── cambios (solo modo de edición) ────────────────────────────────────────────────────────
    def _cambiado(self, foco, clave):
        self._marcar_sucio()
        if clave in ("nombre", "tipo"):
            it = self.lista.currentItem()
            if it is not None:
                self.lista.itemWidget(it).poner(foco)
        if clave in ("nombre", "ubicacion", "dimensiones"):
            self.mapa.set_focos(self.datos["focos"])
            self.mapa.elegir(foco["id"], mostrar=False)

    def _marcar_sucio(self):
        self._sucio = True
        if self.editable:
            self.b_guardar.setEnabled(True)
            self.setWindowTitle(self.windowTitle().rstrip(" *") + " *")

    def _ubicacion_dibujada(self, puntos):
        foco = self._foco(self._id_actual())
        if foco is None or not puntos:
            return
        xy = [tuple(round(c, 1) for c in geo.a_utm(la, lo)) for la, lo in puntos]
        if foco["modelo"] == "superficie":
            foco["ubicacion"] = {"poligono": [list(p) for p in xy]}
        else:
            foco["ubicacion"] = {"x": xy[0][0], "y": xy[0][1]}
        log.info(f"Foco {foco['id']} ({foco.get('nombre')}): ubicación nueva "
                 + (f"({len(xy)} vértices, {_num(F.area_m2(foco))} m²)" if len(xy) > 1
                    else f"UTM {_num(xy[0][0], 1)} · {_num(xy[0][1], 1)} m"))
        self._cambiado(foco, "ubicacion")
        self._rehacer(foco)

    def _anadir(self, tipo, modelo):
        foco = F.nuevo(self.datos, tipo, modelo)
        self.datos["focos"].append(foco)
        self._marcar_sucio()
        self._rellenar(elegir=foco["id"])
        log.info(f"Foco nuevo {foco['id']}: {F.nombre_tipo(foco)} ({modelo}). Ubícalo en el plano.")
        self.mapa.dibujar(modelo)

    def _quitar(self):
        foco = self._foco(self._id_actual())
        if foco is None:
            return
        r = QtWidgets.QMessageBox.question(
            self, "Quitar foco", f"¿Quitar el foco {foco['id']} «{foco.get('nombre')}»?\n"
            "Los escenarios que lo usen dejarán de tenerlo en cuenta.")
        if r != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.datos["focos"].remove(foco)
        self._marcar_sucio()
        self._rellenar()

    def guardar(self):
        """Guarda los focos. True si no queda nada por guardar."""
        if not self.editable:
            return True
        cambiados = [f["id"] for f in self.datos["focos"] if self._recalcular(f)]
        nuevos = [f["id"] for f in self.datos["focos"] if f["id"] not in self._huellas]
        try:
            ruta = F.guardar(self.datos)
        except (ValueError, OSError) as e:
            log.error(f"No se pudieron guardar los focos: {e}")
            QtWidgets.QMessageBox.warning(self, "Guardar los focos", str(e))
            return False
        log.info(f"Focos guardados en {ruta} ({len(self.datos['focos'])} focos)."
                 + (f" Hay que calcular: {', '.join(nuevos + cambiados)}." if nuevos + cambiados else ""))
        self._huellas = {f["id"]: F.huella(f) for f in self.datos["focos"]}
        self._sucio = False
        self.b_guardar.setEnabled(False)
        self.setWindowTitle(self.windowTitle().rstrip(" *"))
        self.guardado.emit()
        return True

    def closeEvent(self, evento):
        if self._sucio and self.editable:
            B = QtWidgets.QMessageBox.StandardButton
            r = preguntar_si_guardar(self, "Focos sin guardar", "Hay cambios en los focos sin guardar. ¿Guardarlos?")
            if r == B.Cancel or (r == B.Save and not self.guardar()):
                evento.ignore()
                return
            if r == B.Discard:
                self._recargar()
                self._rellenar()
                self.b_guardar.setEnabled(False)
                self.setWindowTitle(self.windowTitle().rstrip(" *"))
        self.ajustes.setValue("focos/geometria", self.saveGeometry())
        self.ajustes.setValue("focos/divisor_v2", self.divisor.saveState())
        super().closeEvent(evento)
