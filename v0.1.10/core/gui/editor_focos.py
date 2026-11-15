# -*- coding: utf-8 -*-
"""Editor de un foco, nuevo o existente: solo el usuario administrador (usuario, 2026-11-08: «al modificar o crear se abre una ventana que le
ayuda a crear geométricamente el foco punto, superficie y volumen en el mapa, además de poder caracterizarlo; dispone de formas geométricas,
rectángulo o círculo, que puede poner sobre el mapa obteniendo el área de la superficie, y la ficha con las características»).

- Izquierda: el modelo, en tres tarjetas (al crearlo), las formas para dibujar su ubicación según el modelo (`FORMAS`) y sus medidas (el
  área; los lados de un rectángulo; el radio de un círculo), y la actividad: los focos ya guardados, de los tres modelos, para no repetir
  nombres (usuario, 2026-11-08). Un foco nuevo no tiene tipo de catálogo: su actividad es su nombre, que no puede estar vacío ni repetirse
  (`focos.nombre_repetido`).
- Centro: el plano de la planta con los demás focos y, discontinuo, el que se edita (`focos_mapa.VistaFocos.forma` y `borrador`).
- Derecha: la ficha con casillas (`ventana_focos.Ficha`), sin la operabilidad, que se configura en la operación.

Se trabaja sobre una copia: hasta «Guardar» no cambia nada. Al guardar, si cambia lo que fija la respuesta del modelo (`focos.huella`), el
foco queda pendiente de simular.
"""
import copy
import math
import threading

from PySide6 import QtCore, QtGui, QtWidgets

from teodors import planta as config
from teodors.comun import registro
from teodors.comun.formato import num as _num
from teodors.gui import tema
from teodors.gui.focos_mapa import COLORES, VistaFocos
from teodors.gui.ventana_focos import Ficha, PlanoEsperando
from teodors.gui.widgets import preguntar_si_guardar
from teodors.operacion import focos as F
from teodors.planta import geo

log = registro.get("focos")

# las formas con las que se dibuja la ubicación de cada modelo de foco
FORMAS = {"punto": ("punto",), "superficie": ("rectangulo", "circulo", "poligono"), "volumen": ("rectangulo", "poligono", "punto")}
NOMBRES_FORMA = {"rectangulo": "Rectángulo", "circulo": "Círculo", "poligono": "Polígono", "punto": "Punto"}
AYUDA_FORMA = {"rectangulo": "Dos clics: una esquina y la opuesta", "circulo": "Dos clics: el centro y el borde",
               "poligono": "Un clic por vértice; doble clic para terminar", "punto": "Un clic donde está el foco"}
ICONOS_FORMA = {"rectangulo": "forma_rect", "circulo": "forma_circ", "poligono": "f_superficie", "punto": "f_punto"}


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def ubicar(foco, forma, xy):
    """Pone en el foco la ubicación de una forma dibujada (`xy`: [(x, y)] en UTM), según su modelo, y devuelve sus medidas para enseñar
    ({"area", "largo", "ancho", "radio"}, las que tenga). Un rectángulo para un volumen fija también su largo y su ancho."""
    m, medidas = foco["modelo"], {}
    xs, ys = [p[0] for p in xy], [p[1] for p in xy]
    if m == "superficie":
        foco["ubicacion"] = {"poligono": [[round(x, 1), round(y, 1)] for x, y in xy]}
        (foco.get("superficie") or {}).pop("sobre", None)            # dibujada a mano: ya no es la boca de un edificio
        medidas["area"] = F.area_m2(foco)
    elif m == "volumen":
        if forma in ("rectangulo", "poligono") and len(xy) >= 3:
            # una pila no tiene por qué ir de este a oeste: su largo, por su lado más largo (con un polígono de cuatro clics, girada)
            i = max(range(len(xy)), key=lambda k: _dist(xy[k], xy[(k + 1) % len(xy)]))
            (x1, y1), (x2, y2) = xy[i], xy[(i + 1) % len(xy)]
            lado = _dist(xy[i], xy[(i + 1) % len(xy)])
            ex, ey = (x2 - x1) / lado, (y2 - y1) / lado
            nx, ny = -ey, ex
            us = [(x - x1) * ex + (y - y1) * ey for x, y in xy]
            ws = [(x - x1) * nx + (y - y1) * ny for x, y in xy]
            cu, cw = (max(us) + min(us)) / 2, (max(ws) + min(ws)) / 2
            foco["ubicacion"] = {"x": round(x1 + cu * ex + cw * nx, 1), "y": round(y1 + cu * ey + cw * ny, 1)}
            d = foco.setdefault("dimensiones", {})
            d.update(largo_m=round(max(us) - min(us), 1), ancho_m=round(max(ws) - min(ws), 1),
                     orientacion_deg=round(math.degrees(math.atan2(ex, ey)) % 180.0, 1))
            medidas["area"] = d["largo_m"] * d["ancho_m"]
        else:
            foco["ubicacion"] = {"x": round((min(xs) + max(xs)) / 2, 1), "y": round((min(ys) + max(ys)) / 2, 1)}
    else:
        foco["ubicacion"] = {"x": round(xy[0][0], 1), "y": round(xy[0][1], 1)}
    if m == "volumen" and (foco.get("dimensiones") or {}).get("largo_m") and forma != "punto":
        medidas.update(largo=foco["dimensiones"]["largo_m"], ancho=foco["dimensiones"]["ancho_m"])
    elif forma == "rectangulo" and len(xy) == 4:
        medidas.update(largo=_dist(xy[0], xy[1]), ancho=_dist(xy[1], xy[2]))
    if forma == "circulo" and len(xy) > 2:
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        medidas["radio"] = sum(_dist((cx, cy), p) for p in xy) / len(xy)
    return medidas


def texto_medidas(medidas):
    partes = []
    if medidas.get("area"):
        partes.append(f"Área: {_num(medidas['area'], 0 if medidas['area'] >= 100 else 1)} m²")
    if medidas.get("largo") and medidas.get("ancho"):
        partes.append(f"{_num(medidas['largo'], 1)} × {_num(medidas['ancho'], 1)} m")
    if medidas.get("radio"):
        partes.append(f"Radio: {_num(medidas['radio'], 1)} m")
    return "\n".join(partes)


class EditorFoco(QtWidgets.QWidget):
    """La ventana para crear (`foco` None) o modificar un foco. `datos`: el catálogo de la ventana de los focos (se copia)."""
    guardado = QtCore.Signal(str)                # id del foco guardado

    def __init__(self, emp, ajustes, datos, foco=None, parent=None):
        super().__init__(parent, QtCore.Qt.WindowType.Window)
        self.emp, self.ajustes = emp, ajustes
        self.datos = copy.deepcopy(datos)
        self.nuevo = foco is None
        if self.nuevo:                           # sin tipo de catálogo: la actividad es su nombre (usuario, 2026-11-08)
            self.f = F.nuevo(self.datos, None, "punto")
            self._huella0 = None
        else:
            self.f = next(f for f in self.datos["focos"] if f["id"] == foco["id"])
            self._huella0 = F.huella(foco)
        self._sucio, self._medidas = False, {}
        self.setWindowTitle(("Nuevo foco" if self.nuevo else f"Modificar «{self.f.get('nombre') or self.f['id']}»")
                            + f" · {config.APP_NOMBRE}")
        tema.estilo(self, tema.ESTILO_VENTANAS)
        self.resize(1420, 880)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._cabecera())
        self.divisor = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.divisor.setChildrenCollapsible(False)
        self.divisor.addWidget(self._herramientas())
        self.mapa = VistaFocos()
        self.mapa.setMinimumWidth(380)
        self.plano = PlanoEsperando(self.mapa)
        self.divisor.addWidget(self.plano)
        self.area_ficha = QtWidgets.QScrollArea(objectName="ficha")
        self.area_ficha.setWidgetResizable(True)
        self.area_ficha.setMinimumWidth(470)
        self.area_ficha.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.area_ficha.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.divisor.addWidget(self.area_ficha)
        self.divisor.setStretchFactor(1, 1)
        self.divisor.setSizes([260, 680, 480])
        lay.addWidget(self.divisor, 1)
        geom = self.ajustes.value("editor_focos/geometria")
        if geom is not None:
            self.restoreGeometry(geom)

        self.mapa.listo.connect(self._mapa_listo)
        self.mapa.forma_dibujada.connect(self._forma_dibujada)
        self.mapa.cargar(emp)
        self._poner_formas()
        self._mostrar_ficha()
        tema.manos(self)
        # los edificios, el LiDAR y el cálculo de la estela, ya cargados cuando se marque la chimenea (si no, el primer punto tarda ~1 s)
        from teodors.operacion import estela
        threading.Thread(target=estela.precargar, name="precargar_estela", daemon=True).start()

    # ── construcción ─────────────────────────────────────────────────────────────────────
    def _cabecera(self):
        w = QtWidgets.QWidget(objectName="cabecera")
        w.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(18, 10, 18, 10)
        self.lbl_titulo = QtWidgets.QLabel("Nuevo foco" if self.nuevo else "Modificar el foco", objectName="titulo")
        h.addWidget(self.lbl_titulo, 1)
        h.addWidget(QtWidgets.QLabel(config.pide("operacion", "texto_modo_edicion"), objectName="admin_marca"))
        b = QtWidgets.QPushButton("Cancelar")
        b.clicked.connect(self.close)
        h.addWidget(b)
        self.b_guardar = QtWidgets.QPushButton("Crear el foco" if self.nuevo else "Guardar", objectName="primario")
        self.b_guardar.clicked.connect(self.guardar)
        h.addWidget(self.b_guardar)
        return w

    def _herramientas(self):
        w = QtWidgets.QWidget(objectName="nav")
        w.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        w.setMinimumWidth(230)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(8)
        # el modelo, en tres tarjetas; la actividad, en botones (usuario, 2026-11-08: «los desplegables son poco atractivos»)
        v.addWidget(QtWidgets.QLabel("MODELO", objectName="seccion"))
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(6)
        self.botones_modelo = {}
        for m, icono in (("punto", "f_punto"), ("superficie", "f_superficie"), ("volumen", "f_volumen")):
            b = QtWidgets.QToolButton(objectName="tile_modelo", checkable=True)
            b.setText(F.MODELOS[m])
            tema.pon_icono(b, icono, "texto", 26)
            b.setIconSize(QtCore.QSize(26, 26))
            b.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            b.clicked.connect(lambda _=False, mm=m: self._elegir_modelo(mm))
            fila.addWidget(b, 1)
            self.botones_modelo[m] = b
        v.addLayout(fila)
        v.addSpacing(8)
        v.addWidget(QtWidgets.QLabel("GEOMETRÍA EN EL MAPA", objectName="seccion"))
        self.caja_formas = QtWidgets.QVBoxLayout()
        self.caja_formas.setSpacing(6)
        v.addLayout(self.caja_formas)
        self.lbl_medidas = QtWidgets.QLabel(objectName="cifra_v", wordWrap=True)
        self.lbl_medidas.setVisible(False)
        v.addSpacing(6)
        v.addWidget(self.lbl_medidas)
        # la actividad: los focos ya guardados, de los tres modelos, para no repetir nombres (usuario, 2026-11-08: «que no se pisen los nombres
        # al crear nuevos equipos»); sin ninguno guardado, no sale
        v.addSpacing(8)
        self.lbl_actividad = QtWidgets.QLabel("ACTIVIDAD", objectName="seccion")
        v.addWidget(self.lbl_actividad)
        self.lista_actividad = QtWidgets.QListWidget(objectName="actividad_focos")
        self.lista_actividad.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.lista_actividad.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        v.addWidget(self.lista_actividad, 1)
        self.lbl_repetido = QtWidgets.QLabel(wordWrap=True)
        tema.estilo(self.lbl_repetido, "color:$fallo;font-weight:600")
        self.lbl_repetido.setVisible(False)
        v.addWidget(self.lbl_repetido)
        v.addStretch(0)                          # sin focos guardados (la lista oculta), lo de arriba sigue arriba
        self._pinta_eleccion()
        self._pinta_actividad()
        return w

    def _pinta_eleccion(self):
        """La tarjeta del modelo del foco, marcada. Un foco existente no cambia de modelo (se crea otro)."""
        for m, b in self.botones_modelo.items():
            b.setChecked(m == self.f["modelo"])
            b.setEnabled(self.nuevo)

    def _pinta_actividad(self):
        """Los focos guardados (menos el que se edita), con el color de su modelo; el que se llama como este, marcado."""
        otros = [f for f in self.datos["focos"] if f["id"] != self.f["id"]]
        repe = F.nombre_repetido(self.datos, self.f)
        self.lista_actividad.clear()
        for f in sorted(otros, key=lambda f: (str(f.get("nombre") or f["id"])).casefold()):
            it = QtWidgets.QListWidgetItem(f.get("nombre") or f["id"])
            relleno, borde = COLORES[f["modelo"]]
            pm = QtGui.QPixmap(12, 12)
            pm.fill(QtGui.QColor(relleno))
            it.setIcon(QtGui.QIcon(pm))
            it.setToolTip(F.subtitulo(f))
            if repe is not None and f["id"] == repe["id"]:
                it.setForeground(QtGui.QColor(tema.c("fallo")))
            self.lista_actividad.addItem(it)
        self.lbl_actividad.setVisible(bool(otros))
        self.lista_actividad.setVisible(bool(otros))
        self.lbl_repetido.setText(f"«{repe['nombre']}» ya existe" if repe else "")
        self.lbl_repetido.setVisible(repe is not None)

    def _poner_formas(self):
        """Un botón por cada forma que admite el modelo del foco."""
        while self.caja_formas.count():
            w = self.caja_formas.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        self.botones_forma = {}
        for forma in FORMAS[self.f["modelo"]]:
            b = QtWidgets.QPushButton(NOMBRES_FORMA[forma])
            tema.pon_icono(b, ICONOS_FORMA[forma], "texto", 18)
            b.setToolTip(AYUDA_FORMA[forma])
            b.setStyleSheet("text-align:left;padding:8px 12px")
            b.clicked.connect(lambda _=False, fo=forma: self.mapa.forma(fo))
            self.caja_formas.addWidget(b)
            self.botones_forma[forma] = b

    def _mostrar_ficha(self, scroll=0):
        """La ficha del foco, nueva; el panel 3D de un punto conserva cómo se miraba (giro, inclinación, acercamiento y viento elegido)."""
        anterior = getattr(getattr(self, "ficha", None), "panel", None)
        estado = anterior.estado_vista() if anterior is not None else None
        self.ficha = Ficha(self.f, True, self._recalcula, operabilidad=False, dibujo=False)
        if estado is not None and hasattr(self.ficha, "panel"):
            self.ficha.panel.poner_vista(estado)
        # la columna de la ficha, tan ancha como la pida (sin barra horizontal, lo que no cupiera se cortaría)
        self.area_ficha.setMinimumWidth(max(470, self.ficha.minimumSizeHint().width() + self.area_ficha.verticalScrollBar().sizeHint().width() + 6))
        self.ficha.cambiado.connect(self._cambiado)
        self.ficha.rehacer.connect(lambda: QtCore.QTimer.singleShot(0, lambda: self._mostrar_ficha(self.area_ficha.verticalScrollBar().value())))
        self.area_ficha.setWidget(self.ficha)
        self.area_ficha.verticalScrollBar().setValue(scroll)

    # ── cambios ──────────────────────────────────────────────────────────────────────────
    def _recalcula(self, foco):
        """¿Cambia lo que fija su respuesta? (siempre, si es nuevo): habrá que simularlo."""
        return self._huella0 is None or self._huella0 != F.huella(foco)

    def _marcar(self):
        self._sucio = True
        if not self.windowTitle().endswith(" *"):
            self.setWindowTitle(self.windowTitle() + " *")

    def _cambiado(self, clave):
        self._marcar()
        if clave in ("nombre", "ubicacion", "dimensiones"):
            # en la boca de un edificio (se elige en la ficha, no en el plano): el plano va a ella
            self._pinta_borrador(encuadrar=clave == "ubicacion" and bool((self.f.get("superficie") or {}).get("sobre")))
        if clave == "nombre":
            self._pinta_actividad()

    def _elegir_modelo(self, modelo):
        """Otro modelo (al crear): se conserva el nombre; lo demás se pierde."""
        if not self.nuevo or modelo == self.f["modelo"]:
            self._pinta_eleccion()
            return
        nombre, unidad = self.f.get("nombre", ""), self.f.get("unidad", "")
        self.f = F.nuevo(self.datos, None, modelo)
        self.f.update(nombre=nombre, unidad=unidad)
        self._rehacer_todo()

    def _rehacer_todo(self):
        self._pinta_eleccion()
        self._pinta_actividad()
        self._medidas = {}
        self.lbl_medidas.setVisible(False)
        self._poner_formas()
        self._mostrar_ficha()
        self._pinta_borrador()
        self._marcar()

    def _forma_dibujada(self, forma, puntos):
        xy = [geo.a_utm(la, lo) for la, lo in puntos]
        self._medidas = ubicar(self.f, forma, xy)
        texto = texto_medidas(self._medidas)
        self.lbl_medidas.setText(texto)
        self.lbl_medidas.setVisible(bool(texto))
        log.info(f"Foco {self.f['id']}: {NOMBRES_FORMA.get(forma, forma).lower()} en el mapa" + (f" · {texto.replace(chr(10), ' · ')}" if texto else ""))
        if self.f["modelo"] == "punto":                   # moverlo no rehace la ficha: el panel 3D sigue como estaba, ~0,1 s
            self.ficha.refrescar()
            self._cambiado("ubicacion")
            return
        self._mostrar_ficha(self.area_ficha.verticalScrollBar().value())
        self._pinta_borrador()
        self._marcar()

    def edificios_cambiados(self):
        """Los edificios de la planta se han guardado en esta sesión. La estela de los focos punto ya guardados la acaba de rehacer y guardar
        `edificios_planta.recalcular_focos`: se trae a la copia de este editor (si no, guardar el foco la desharía). La de este foco se
        recalcula en su panel 3D, que sigue mirando como estaba."""
        try:
            guardados = {f["id"]: f for f in F.cargar()["focos"]}
        except (ValueError, OSError) as e:
            log.warning(f"No se pudieron releer los focos tras cambiar los edificios: {e}")
            guardados = {}
        for f in self.datos["focos"]:
            g = guardados.get(f["id"])
            if g is None or f is self.f:
                continue
            claves = ("edificios",) if f.get("modelo") == "punto" else ("ubicacion", "altura_m", "superficie")   # la boca de un tanque
            for k in claves:
                if k in g:
                    f[k] = copy.deepcopy(g[k])
                else:
                    f.pop(k, None)
        sobre = (self.f.get("superficie") or {}).get("sobre") if self.f.get("modelo") == "superficie" else None
        if sobre:                                     # la boca de un edificio de la planta: le sigue (o, si ya no está, se queda)
            from teodors.operacion import edificios_planta as EP
            e = next((e for e in EP.cargar()["edificios"] if e["id"] == sobre), None)
            if e is None:
                self.f["superficie"].pop("sobre")
            cambia = e is None or F.poner_sobre(self.f, e)
            if cambia:
                self._mostrar_ficha(self.area_ficha.verticalScrollBar().value())
                self._pinta_borrador()
                self._marcar()
                return
        if hasattr(self.ficha, "edificios_cambiados"):
            self.ficha.edificios_cambiados()

    # ── el plano ─────────────────────────────────────────────────────────────────────────
    def _mapa_listo(self):
        otros = [f for f in self.datos["focos"] if f["id"] != self.f["id"]]
        self.mapa.set_focos(otros, encuadrar=True)
        self._pinta_borrador(encuadrar=True)

    def _pinta_borrador(self, encuadrar=False):
        self.mapa.borrador(self.f, encuadrar)

    # ── guardar ──────────────────────────────────────────────────────────────────────────
    def guardar(self, cerrar=True):
        """Pone el foco en el catálogo y lo guarda (y, con `cerrar`, cierra el editor). True si se guardó. Si le falta algo se guarda igual,
        y lo dice el registro: se completa después."""
        falta = F.pendientes(self.f)
        if not str(self.f.get("nombre") or "").strip():
            QtWidgets.QMessageBox.warning(self, "Guardar el foco", "Falta su nombre.")
            return False
        repe = F.nombre_repetido(self.datos, self.f)
        if repe is not None:
            QtWidgets.QMessageBox.warning(self, "Guardar el foco", f"Ya hay un foco «{repe['nombre']}»: elige otro nombre.")
            return False
        if not (self.f.get("ubicacion") or {}):
            QtWidgets.QMessageBox.warning(self, "Guardar el foco", "Falta su ubicación: dibújalo en el mapa con una de las formas.")
            return False
        if not (self.f.get("funcionamiento") or {}).get("modo"):       # nace con su operación por defecto (se cambia en la operación)
            self.f["funcionamiento"] = F.funcionamiento_defecto(self.f)
        if self.nuevo:
            self.datos["focos"].append(self.f)
        try:
            ruta = F.guardar(self.datos)
        except (ValueError, OSError) as e:
            if self.nuevo:
                self.datos["focos"].remove(self.f)
            log.error(f"No se pudo guardar el foco: {e}")
            QtWidgets.QMessageBox.warning(self, "Guardar el foco", str(e))
            return False
        simular = self._recalcula(self.f)
        log.info(f"Foco {self.f['id']} «{self.f.get('nombre')}» {'creado' if self.nuevo else 'guardado'} ({ruta})."
                 + (" Pendiente de simular." if simular else "") + (f" Le falta: {'; '.join(falta)}." if falta else ""))
        self._sucio = False
        self.nuevo = False
        self.guardado.emit(self.f["id"])
        if cerrar:
            self.close()
        return True

    def closeEvent(self, evento):
        if self._sucio:
            B = QtWidgets.QMessageBox.StandardButton
            r = preguntar_si_guardar(self, "Foco sin guardar", "Hay cambios en el foco sin guardar. ¿Guardarlos?")
            if r == B.Cancel or (r == B.Save and not self.guardar(cerrar=False)):
                evento.ignore()
                return
            self._sucio = False
        self.ajustes.setValue("editor_focos/geometria", self.saveGeometry())
        super().closeEvent(evento)
