# -*- coding: utf-8 -*-
"""Editor de los edificios de la planta: solo el usuario administrador (usuario, 2026-11-08: «poder configurar los edificios vía 3 caminos
[los descargados, el LiDAR y dibujar/modificar desde el usuario administrador], todo en Planta y en el menú de edificios»; «la creación sería a
través de polígonos y con la altura»).

- Izquierda: los edificios, con el color de su origen (descargados, LiDAR o dibujado) y su altura; «Nuevo» y «Eliminar»; las formas para dibujar
  (rectángulo, círculo de 36 lados, polígono) y las medidas de lo dibujado.
- Centro: la ortofoto con los edificios (`focos_mapa.VistaFocos`); el elegido, discontinuo. Pinchar uno lo elige.
- Derecha: el elegido: su nombre, su altura (con la que mide el LiDAR dentro de su polígono, para usarla con un clic), su origen y su área; y
  debajo, todos en 3D (`focos_graficos.VisorEdificios`; usuario, 2026-11-08: «como hicimos para los focos de punto»), el elegido resaltado:
  sigue cada cambio, y un clic en uno lo elige.

Dibujar con un edificio elegido le cambia la forma; sin ninguno, crea uno nuevo, con la altura del LiDAR si ve ahí un edificio (si no, uno
posterior al vuelo, `ALTURA_NUEVO_M` y un aviso para ponerla a mano). Lo tocado a mano pasa a
«dibujado» (`edificios_planta`): volver a traer los descargados o el LiDAR no lo pisa. Se trabaja sobre una copia: al guardar se escribe
`edificios_planta.json` y se rehace la estela de los focos punto (`edificios_planta.recalcular_focos`).
"""
import json

from PySide6 import QtCore, QtGui, QtWidgets

from teodors import planta as config
from teodors.comun import registro
from teodors.comun.formato import num as _num
from teodors.gui import tema
from teodors.gui.editor_focos import AYUDA_FORMA, ICONOS_FORMA, NOMBRES_FORMA, _dist, texto_medidas
from teodors.gui.focos_graficos import VisorEdificios
from teodors.gui.focos_mapa import VistaFocos
from teodors.gui.ventana_focos import PlanoEsperando
from teodors.gui.widgets import preguntar_si_guardar
from teodors.operacion import edificios_planta as EP
from teodors.operacion.estela import ALTURA_MIN_M
from teodors.planta import geo

log = registro.get("focos")

FORMAS = ("rectangulo", "circulo", "poligono")
COLOR_ORIGEN = {"catastro": "#8a9aa8", "lidar": "#6fbf73", "dibujo": "#e0a458"}
ALTURA_NUEVO_M = 6.0         # la de uno nuevo donde el LiDAR no ve un edificio, hasta que se ponga la suya


def _leer(texto):
    t = texto.strip().replace(" ", "").replace(" ", "").replace(",", ".")
    return float(t) if t else None


def como_foco(e):
    """Un edificio como lo dibuja el plano de los focos (`VistaFocos.set_focos`)."""
    return {"id": e["id"], "nombre": f"{e.get('nombre') or e['id']} · {_num(e['altura_m'], 1)} m", "modelo": "edificio",
            "ubicacion": {"poligono": e["poligono"]}}


class EditorEdificios(QtWidgets.QWidget):
    """La ventana de los edificios de la planta (solo el administrador). `guardado` dice cuántos focos punto han cambiado de estela."""
    guardado = QtCore.Signal(list)

    def __init__(self, emp, ajustes, parent=None):
        super().__init__(parent, QtCore.Qt.WindowType.Window)
        self.emp, self.ajustes = emp, ajustes
        self.datos = EP.cargar()
        self._original = json.dumps(self.datos["edificios"], sort_keys=True)
        self.sel, self._sucio, self._dibujando = None, False, False
        self.setWindowTitle(f"Edificios de la planta · {config.APP_NOMBRE}")
        tema.estilo(self, tema.ESTILO_VENTANAS)
        self.resize(1420, 880)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._cabecera())
        divisor = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        divisor.setChildrenCollapsible(False)
        divisor.addWidget(self._izquierda())
        self.mapa = VistaFocos()
        self.mapa.setMinimumWidth(380)
        divisor.addWidget(PlanoEsperando(self.mapa))
        divisor.addWidget(self._derecha())
        divisor.setStretchFactor(1, 1)
        divisor.setSizes([280, 760, 380])
        lay.addWidget(divisor, 1)
        geom = self.ajustes.value("editor_edificios/geometria")
        if geom is not None:
            self.restoreGeometry(geom)
        self.mapa.listo.connect(self._mapa_listo)
        self.mapa.foco.connect(self.elegir)
        self.mapa.forma_dibujada.connect(self._forma_dibujada)
        self.mapa.cargar(emp)
        self._pinta_lista()
        self._pinta_ficha()
        tema.manos(self)

    # ── construcción ─────────────────────────────────────────────────────────────────────────────────────────
    def _cabecera(self):
        w = QtWidgets.QWidget(objectName="cabecera")
        w.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(18, 10, 18, 10)
        h.addWidget(QtWidgets.QLabel("Edificios de la planta", objectName="titulo"), 1)
        h.addWidget(QtWidgets.QLabel(config.pide("operacion", "texto_modo_edicion"), objectName="admin_marca"))
        b = QtWidgets.QPushButton("Cancelar")
        b.clicked.connect(self.close)
        h.addWidget(b)
        self.b_guardar = QtWidgets.QPushButton("Guardar", objectName="primario")
        self.b_guardar.clicked.connect(self.guardar)
        h.addWidget(self.b_guardar)
        return w

    def _izquierda(self):
        w = QtWidgets.QWidget(objectName="nav")
        w.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        w.setMinimumWidth(250)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(8)
        v.addWidget(QtWidgets.QLabel("EDIFICIOS", objectName="seccion"))
        self.lista = QtWidgets.QListWidget(objectName="actividad_focos")
        self.lista.itemClicked.connect(lambda it: self.elegir(it.data(QtCore.Qt.ItemDataRole.UserRole)))
        v.addWidget(self.lista, 1)
        fila = QtWidgets.QHBoxLayout()
        self.b_nuevo = QtWidgets.QPushButton("+ Nuevo")
        self.b_nuevo.clicked.connect(self.nuevo)
        self.b_eliminar = QtWidgets.QPushButton("Eliminar")
        self.b_eliminar.clicked.connect(self.eliminar)
        fila.addWidget(self.b_nuevo)
        fila.addWidget(self.b_eliminar)
        v.addLayout(fila)
        v.addSpacing(6)
        self.lbl_dibujar = QtWidgets.QLabel("DIBUJAR", objectName="seccion")
        v.addWidget(self.lbl_dibujar)
        self.botones_forma = {}
        for forma in FORMAS:
            b = QtWidgets.QPushButton(NOMBRES_FORMA[forma])
            tema.pon_icono(b, ICONOS_FORMA[forma], "texto", 18)
            b.setToolTip(AYUDA_FORMA[forma])
            b.setStyleSheet("text-align:left;padding:8px 12px")
            b.clicked.connect(lambda _=False, fo=forma: self.mapa.forma(fo))
            v.addWidget(b)
            self.botones_forma[forma] = b
        self.lbl_medidas = QtWidgets.QLabel(objectName="cifra_v", wordWrap=True)
        self.lbl_medidas.setVisible(False)
        v.addWidget(self.lbl_medidas)
        return w

    def _derecha(self):
        w = QtWidgets.QWidget(objectName="cuerpo_ficha")
        w.setMinimumWidth(340)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(10)
        self.lbl_titulo = QtWidgets.QLabel(wordWrap=True)
        self.lbl_titulo.setStyleSheet("font-size:17px;font-weight:700")
        v.addWidget(self.lbl_titulo)
        self.lbl_origen = QtWidgets.QLabel(objectName="subtitulo")
        v.addWidget(self.lbl_origen)
        self.campos = QtWidgets.QWidget()
        c = QtWidgets.QVBoxLayout(self.campos)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(6)
        c.addWidget(QtWidgets.QLabel("Nombre"))
        self.lin_nombre = QtWidgets.QLineEdit(placeholderText="[nombre en la planta]")
        self.lin_nombre.editingFinished.connect(self._nombre_editado)
        c.addWidget(self.lin_nombre)
        c.addWidget(QtWidgets.QLabel("Altura"))
        fila = QtWidgets.QHBoxLayout()
        self.lin_altura = QtWidgets.QLineEdit(placeholderText="[m]")
        self.lin_altura.editingFinished.connect(self._altura_editada)
        fila.addWidget(self.lin_altura, 1)
        self.b_lidar = QtWidgets.QPushButton()
        self.b_lidar.setToolTip("La altura que mide el LiDAR dentro del polígono")
        self.b_lidar.clicked.connect(self._usar_lidar)
        fila.addWidget(self.b_lidar)
        c.addLayout(fila)
        self.lbl_aviso_lidar = QtWidgets.QLabel(wordWrap=True)
        c.addWidget(self.lbl_aviso_lidar)
        self.lbl_area = QtWidgets.QLabel(objectName="cifra_v")
        c.addWidget(self.lbl_area)
        v.addWidget(self.campos)
        self.lbl_vacio = QtWidgets.QLabel("Elige un edificio o dibuja uno nuevo con una forma.", objectName="nota", wordWrap=True)
        v.addWidget(self.lbl_vacio)
        v.addSpacing(6)
        self.visor = VisorEdificios(alto=380)
        self.visor.setMaximumHeight(470)
        self.visor.pulsado.connect(self.elegir)
        v.addWidget(self.visor, 1)
        v.addStretch()
        return w

    # ── la lista, la ficha y el plano ────────────────────────────────────────────────────────────────────────
    def _edificio(self, id_):
        return next((e for e in self.datos["edificios"] if e["id"] == id_), None)

    def _pinta_lista(self):
        self.lista.clear()
        for e in sorted(self.datos["edificios"], key=lambda e: -e["altura_m"]):
            it = QtWidgets.QListWidgetItem(f"{e.get('nombre') or e['id']}  ·  {_num(e['altura_m'], 1)} m")
            pm = QtGui.QPixmap(12, 12)
            pm.fill(QtGui.QColor(COLOR_ORIGEN.get(e.get("origen"), "#999999")))
            it.setIcon(QtGui.QIcon(pm))
            it.setToolTip(EP.nombre_origen(e.get("origen", "dibujo")))
            it.setData(QtCore.Qt.ItemDataRole.UserRole, e["id"])
            self.lista.addItem(it)
            if e["id"] == self.sel:
                it.setSelected(True)
        self.b_eliminar.setEnabled(self.sel is not None)

    def _pinta_ficha(self):
        self.visor.poner(self.datos["edificios"], self.sel)
        e = self._edificio(self.sel)
        self.campos.setVisible(e is not None)
        self.lbl_vacio.setVisible(e is None)
        if e is None:
            self.lbl_titulo.setText("Nuevo edificio" if self._dibujando else "Edificios de la planta")
            self.lbl_origen.setText(f"{len(self.datos['edificios'])} edificios")
            return
        self.lbl_titulo.setText(e.get("nombre") or e["id"])
        self.lbl_origen.setText(" · ".join([EP.nombre_origen(e.get("origen", "dibujo")), e["id"]] + ([f"ref. {e['ref']}"] if e.get("ref") else [])))
        self.lin_nombre.setText(e.get("nombre") or "")
        self.lin_altura.setText(_num(e["altura_m"], 1))
        self.lbl_area.setText(f"{_num(EP.area_m2(e), 0)} m²")
        h = EP.altura_lidar(e["poligono"])
        self.b_lidar.setText(f"LiDAR {_num(h, 1)} m" if h is not None else "LiDAR —")
        self.b_lidar.setEnabled(h is not None)
        self.b_lidar.setProperty("altura", h)
        no_ve = h is not None and h < ALTURA_MIN_M                     # el LiDAR ve suelo: un edificio posterior al vuelo
        self.lbl_aviso_lidar.setVisible(no_ve)
        if no_ve:
            tema.texto(self.lbl_aviso_lidar, f"<span style='color:$aviso'>El LiDAR solo mide {_num(h, 1)} m aquí: un edificio más bajo o "
                                             "posterior al vuelo. Pon su altura a mano.</span>")

    def _mapa_listo(self):
        self.mapa.js("document.querySelectorAll('.mapa-ley').forEach(function (e) { e.style.display = 'none'; })")
        self._pinta_mapa(encuadrar=True)

    def _pinta_mapa(self, encuadrar=False):
        self.mapa.set_focos([como_foco(e) for e in self.datos["edificios"] if len(e.get("poligono") or []) >= 3], encuadrar=encuadrar)
        if self.sel is not None:
            self.mapa.elegir(self.sel, mostrar=False)

    def elegir(self, id_):
        self.sel = id_ if self._edificio(id_) is not None else None
        self._dibujando = False
        self._pinta_lista()
        self._pinta_ficha()
        self.mapa.elegir(self.sel, mostrar=True)

    # ── cambios ──────────────────────────────────────────────────────────────────────────────────────────────
    def _marcar(self):
        self._sucio = json.dumps(self.datos["edificios"], sort_keys=True) != self._original
        titulo = self.windowTitle().rstrip(" *")
        self.setWindowTitle(titulo + (" *" if self._sucio else ""))

    def _a_mano(self, e):
        """Lo tocado a mano pasa a dibujado: volver a traer los descargados o el LiDAR no lo pisa."""
        e["origen"] = "dibujo"

    def nuevo(self):
        """Sin edificio elegido: lo que se dibuje será uno nuevo."""
        self.sel, self._dibujando = None, True
        self._pinta_lista()
        self._pinta_ficha()
        self.mapa.elegir(None, mostrar=False)
        self.mapa.forma("rectangulo")

    def eliminar(self):
        e = self._edificio(self.sel)
        if e is None:
            return
        self.datos["edificios"].remove(e)
        log.info(f"Edificio {e['id']} «{e.get('nombre')}» quitado (sin guardar).")
        self.sel = None
        self._pinta_lista()
        self._pinta_ficha()
        self._pinta_mapa()
        self._marcar()

    def _forma_dibujada(self, forma, puntos):
        xy = [tuple(round(v, 2) for v in geo.a_utm(la, lo)) for la, lo in puntos]
        if len(xy) < 3:
            return
        e = self._edificio(self.sel)
        if e is None:                                                  # uno nuevo, con la altura del LiDAR si lo cubre
            h = EP.altura_lidar([list(p) for p in xy])
            if h is not None and h < ALTURA_MIN_M:
                h = None
            e = {"id": EP.nuevo_id(self.datos), "nombre": "", "origen": "dibujo", "poligono": [list(p) for p in xy],
                 "altura_m": h if h is not None else ALTURA_NUEVO_M}
            self.datos["edificios"].append(e)
            self.sel = e["id"]
            log.info(f"Edificio {e['id']} nuevo, {NOMBRES_FORMA.get(forma, forma).lower()}" + (f", con la altura del LiDAR ({_num(h, 1)} m)"
                                                                                                 if h is not None else ""))
        else:
            e["poligono"] = [list(p) for p in xy]
            self._a_mano(e)
        medidas = {"area": EP.area_m2(e)}
        if forma == "rectangulo" and len(xy) == 4:
            medidas.update(largo=_dist(xy[0], xy[1]), ancho=_dist(xy[1], xy[2]))
        self.lbl_medidas.setText(texto_medidas(medidas))
        self.lbl_medidas.setVisible(True)
        self._dibujando = False
        self._pinta_lista()
        self._pinta_ficha()
        self._pinta_mapa()
        self._marcar()

    def _nombre_editado(self):
        e = self._edificio(self.sel)
        if e is None or (e.get("nombre") or "") == self.lin_nombre.text().strip():
            return
        e["nombre"] = self.lin_nombre.text().strip()
        self._a_mano(e)
        self._pinta_lista()
        self._pinta_ficha()
        self._pinta_mapa()
        self._marcar()

    def _altura_editada(self):
        e = self._edificio(self.sel)
        if e is None:
            return
        try:
            h = _leer(self.lin_altura.text())
        except ValueError:
            tema.estilo(self.lin_altura, "border:1px solid $fallo")
            return
        if h is None or h <= 0:
            tema.estilo(self.lin_altura, "border:1px solid $fallo")
            return
        tema.estilo(self.lin_altura, "")
        if abs(h - e["altura_m"]) < 1e-9:
            return
        e["altura_m"] = round(h, 1)
        self._a_mano(e)
        self._pinta_lista()
        self._pinta_ficha()
        self._pinta_mapa()
        self._marcar()

    def _usar_lidar(self):
        h = self.b_lidar.property("altura")
        if h is not None:
            self.lin_altura.setText(_num(h, 1))
            self._altura_editada()

    # ── guardar ──────────────────────────────────────────────────────────────────────────────────────────────
    def guardar(self, cerrar=True):
        """Escribe los edificios y rehace la estela de los focos punto; True si se guardó."""
        sin = [e["id"] for e in self.datos["edificios"] if len(e.get("poligono") or []) < 3]
        if sin:
            QtWidgets.QMessageBox.warning(self, "Guardar los edificios", f"Sin forma: {', '.join(sin)}. Dibújalos o elimínalos.")
            return False
        try:
            EP.guardar(self.datos)
            cambiados = EP.recalcular_focos()
        except (ValueError, OSError) as e:
            log.error(f"No se pudieron guardar los edificios: {e}")
            QtWidgets.QMessageBox.warning(self, "Guardar los edificios", str(e))
            return False
        log.info(f"Edificios de la planta guardados: {len(self.datos['edificios'])}." + (f" Cambia la estela de {len(cambiados)} foco(s)."
                                                                                       if cambiados else ""))
        self._original = json.dumps(self.datos["edificios"], sort_keys=True)
        self._marcar()
        self.guardado.emit(cambiados)
        if cerrar:
            self.close()
        return True

    def closeEvent(self, evento):
        if self._sucio:
            B = QtWidgets.QMessageBox.StandardButton
            r = preguntar_si_guardar(self, "Edificios sin guardar", "Hay cambios en los edificios sin guardar. ¿Guardarlos?")
            if r == B.Cancel or (r == B.Save and not self.guardar(cerrar=False)):
                evento.ignore()
                return
            self._sucio = False
        self.ajustes.setValue("editor_edificios/geometria", self.saveGeometry())
        super().closeEvent(evento)
