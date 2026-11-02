# -*- coding: utf-8 -*-
"""Ventana principal: barra superior, panel (izquierda), mapa con su reproductor de tiempo (centro) y
registro de actividad (abajo, oculto al principio).

El mapa es la zona central y siempre rellena el espacio libre. Panel y actividad son
QDockWidget: se mueven a cualquier borde, se sacan a ventana flotante (p. ej. a otro
monitor), se ocultan y se vuelven a mostrar desde el menú, en Ver. «Solo mapa» (F11) deja el
mapa a pantalla completa. La disposición se guarda al cerrar y se recupera al abrir.

Al abrir, el mapa no tiene viento ni penacho (usuario, 2026-11-01): el viento llega al elegir la meteorología y el
penacho al simular; el ejemplo guardado solo se ve en la configuración (gui/vista_previa.py). Lo que antes solo iba
a la consola sale ahora en el mapa: el clic y las estaciones, en una ficha; los errores, en un aviso.

Se probó con el mapa también como panel acoplable (sin zona central) y se descartó por lo
medido: al ocultar el mapa quedaba un hueco gris de ~1055×650 px, y al ocultar la consola
el panel encogía de 339 a 166 px. Qt no admite bien una ventana sin zona central.

La planta y el dominio son FIJOS (decisión del usuario): la planta no se mueve desde la app
y el dominio es todo el terreno descargado.
"""
from PySide6 import QtCore, QtGui, QtWidgets

from teodors import planta as config
from teodors.casos import receptores as receptores_mapa
from teodors.comun import registro
from teodors.comun.formato import km as _km, num as _num
from teodors.fuentes import catastro as edificios, meteocat as estaciones, terreno
from teodors.gui import mapa_web, tema
from teodors.gui.consola import Consola
from teodors.gui.mapa import VistaMapa
from teodors.gui.panel import Panel, texto_anios
from teodors.gui.terminal import Terminal
from teodors.gui.trabajos import Trabajo, TrabajoTerreno
from teodors.gui.widgets import TituloDock, pregunta_abierta
from teodors.metricas import viento as validacion
from teodors.operacion import penacho_mapa, viento_mapa
from teodors.planta import geo

log = registro.get("gui")

_AREAS = QtCore.Qt.DockWidgetArea
# Elevación, uso del suelo y edificios son EXCLUYENTES (decisión del usuario): al activar una
# con su botón del panel, único sitio desde el que se activan, se desactiva la que hubiera.
GRUPO_TEMATICO = "tematica"


class VentanaPrincipal(QtWidgets.QMainWindow):
    def __init__(self, dia_inicial=None, abrir_focos=False, abrir_planes=False):
        super().__init__()
        self._dia_inicial = dia_inicial          # «aaaa-mm-dd»: se carga al estar listo el mapa
        self._abrir_focos = abrir_focos          # --focos: la ventana de focos, al estar listo
        self._abrir_planes = abrir_planes        # --planes: la de los planes, al estar listo
        self.setWindowTitle(config.APP_NOMBRE)
        self.ajustes = tema.ajustes()
        self.emp = config.cargar_emplazamiento()

        # La consola primero, para que recoja los mensajes del arranque.
        self.consola = Consola()
        self.consola.conectar()
        self.panel = Panel(self.emp)
        self.mapa = VistaMapa()

        central = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self._central = QtWidgets.QStackedWidget()
        self._central.addWidget(self.mapa)
        v.addWidget(self._central, 1)
        v.addWidget(self.panel.reproductor)
        self.setCentralWidget(central)
        self.consola.error.connect(lambda m: self.mapa.aviso(m, "fallo"))   # está oculta: que se vea
        self.setDockNestingEnabled(True)
        self.setCorner(QtCore.Qt.Corner.BottomLeftCorner, _AREAS.LeftDockWidgetArea)
        self.dock_panel = self._dock("Panel", self.panel, _AREAS.LeftDockWidgetArea)
        self.dock_consola = self._dock("Actividad", self.consola, _AREAS.BottomDockWidgetArea)
        self.terminal = Terminal()
        self.dock_terminal = self._dock("Terminal", self.terminal, _AREAS.BottomDockWidgetArea)
        self.tabifyDockWidget(self.dock_consola, self.dock_terminal)
        self._docks = (self.dock_panel, self.dock_consola, self.dock_terminal)
        self.resize(1400, 860)
        geom = self.ajustes.value("ventana/geometria_v2")
        self.primera_vez = geom is None          # main.py la abre maximizada
        if geom is not None:
            self.restoreGeometry(geom)
        self._estado_defecto = None              # se toma al mostrar (ver showEvent)
        self._antes_de_solo_mapa = None

        self._menus()
        self.setMenuWidget(self._barra_app())

        self.panel.verTerreno.connect(self.mapa.centrar)
        self.panel.verPlanta.connect(self.mapa.ver_planta)
        self.panel.descargarTerreno.connect(self._descargar_terreno)
        self.panel.descargarEdificios.connect(self._descargar_edificios)
        self.panel.horizonteMeteo.connect(self._horizonte_meteo)
        self.panel.vientoDia.connect(self._cargar_viento)
        self.panel.vientoHora.connect(self._hora_reproductor)
        self.panel.periodoCambiado.connect(self._periodo_cambiado)
        self.panel.prepararPeriodo.connect(self._preparar_periodo)
        self.panel.vientoPeriodo.connect(self._ver_viento_periodo)
        self.panel.simularPeriodo.connect(self._simular_periodo)
        self.panel.paginaCambiada.connect(self._pagina_cambiada)
        self.mapa.clic.connect(self._clic_mapa)
        self.mapa.estacion.connect(self._clic_estacion)
        self.panel.verCapa.connect(self.mapa.ver_capa)                 # botones «Ver …»
        self.panel.verFocos.connect(self._ver_focos)
        self.panel.verPlanes.connect(self._ver_planes)
        self.panel.simular.connect(self._simular)
        self.panel.magnitudElegida.connect(self._ver_magnitud)
        self.panel.ver3d.connect(self._ver_3d)
        self.panel.tituloPagina.connect(self._titulo_panel.lbl.setText)
        self.panel.verActividad.connect(lambda: self._alternar(self.dock_consola))
        self.panel.verTerminal.connect(lambda: self._alternar(self.dock_terminal))
        self.mapa.capa.connect(self.panel.set_capa_visible)            # y al revés, del selector
        self.mapa.listo.connect(self._mapa_listo)
        self.mapa.formaViento.connect(self._forma_viento)

        self.terreno_info = None
        self._terreno_arr = None
        self._resumen = None
        self._trabajo = None
        self.edif_info, self._edif, self._edif_todos = None, None, None
        self._trabajo_edif = None
        self._rosas, self._trabajo_rosas = None, None
        self._nombres, self._trabajo_nombres = {}, None    # nombre de cada núcleo
        self._trabajo_viento = None
        self._rosas_dia = None                   # rosas de lo medido el día cargado en Reanálisis
        self._dia_viento = None                  # el día del viento que hay en el mapa
        self._animar_al_cargar = False
        self._ventana_focos = None
        self._ventana_planes = None
        self._ventana_ajustes = None
        tema.avisos.cambiado.connect(self._pinta_acciones)
        self._trabajo_sim, self._magnitud = None, None
        self._resultados = {"anios": None, "periodo": None}      # lo simulado: los años del reanálisis, y un día, el episodio o la predicción
        self._valores = {}                       # los valores de cada resultado en cada receptor, para los tooltips
        self._trabajo_periodo, self._trabajo_3d, self._fallo_3d = None, None, None
        self.vista3d, self._en_3d, self._3d_horas, self._horas_mapa = None, False, None, None
        self._mensajes_arranque()
        self._cargar_focos()
        self._actualizar_planes()
        self._cargar_terreno_guardado()
        self._cargar_edificios_guardados()
        self._cargar_estaciones()
        self.panel.ir_a("inicio")
        self.mapa.cargar(self.emp, self._limites())

    # ── construcción ─────────────────────────────────────────────────────────────────────
    def _dock(self, titulo, widget, area):
        dock = QtWidgets.QDockWidget(titulo, self)
        dock.setObjectName(f"dock_{titulo.lower()}")          # necesario para saveState
        dock.setWidget(widget)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
                         | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
                         | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.addDockWidget(area, dock)
        barra = TituloDock(dock, titulo)
        dock.setTitleBarWidget(barra)
        if area == _AREAS.LeftDockWidgetArea:
            self._titulo_panel = barra           # lleva el título de la página del panel
        return dock

    def _menus(self):
        barra = self.menu_app = QtWidgets.QMenu(self)
        m_archivo = barra.addMenu("&Archivo")
        m_archivo.addAction("Abrir carpeta de datos", lambda: self._abrir(config.DATOS))
        m_archivo.addAction("Abrir carpeta de registros", lambda: self._abrir(config.DIR_LOGS))
        m_archivo.addSeparator()
        m_archivo.addAction("Volver a descargar el terreno…", self._redescargar_terreno)
        m_archivo.addSeparator()
        m_archivo.addAction("Salir", QtGui.QKeySequence.StandardKey.Quit, self.close)

        m_planta = barra.addMenu("&Planta")
        m_planta.addAction("Focos de emisión…" + (f" ({config.pide('operacion', 'texto_modo_edicion')})" if config.MODO_EDICION else ""),
                           QtGui.QKeySequence("Ctrl+Shift+F"), self._ver_focos)
        m_planta.addAction("Planes de operación…", QtGui.QKeySequence("Ctrl+Shift+P"), self._ver_planes)

        m_ver = barra.addMenu("&Ver")
        for i, dock in enumerate(self._docks, 1):
            accion = dock.toggleViewAction()
            accion.setShortcut(QtGui.QKeySequence(f"Ctrl+{i}"))
            m_ver.addAction(accion)
        m_ver.addSeparator()
        self.acc_solo_mapa = m_ver.addAction("Solo mapa")
        self.acc_solo_mapa.setCheckable(True)
        self._pinta_acciones()
        self.acc_solo_mapa.setToolTip("Solo mapa")
        self.acc_solo_mapa.setShortcut(QtGui.QKeySequence("F11"))
        self.acc_solo_mapa.toggled.connect(self._solo_mapa)
        m_ver.addAction("Restablecer disposición", self._restablecer_disposicion)
        m_ver.addSeparator()
        m_ver.addAction("Recargar mapa", QtGui.QKeySequence("F5"),
                        lambda: self.mapa.cargar(self.emp, self._limites()))
        m_ver.addSeparator()
        m_ver.addAction("Configuración…", QtGui.QKeySequence("Ctrl+,"), self._ver_ajustes)

        m_ayuda = barra.addMenu("Ay&uda")
        m_ayuda.addAction("Acerca de y fuentes de datos", self._acerca_de)
        for m in (m_archivo, m_planta, m_ver, m_ayuda):      # sin barra de menús, los atajos van a la ventana
            self.addActions(m.actions())

    def _barra_app(self):
        """Barra superior: la marca, la hora y lo imprescindible. Los menús, en el botón de la derecha."""
        w = QtWidgets.QWidget(objectName="barra_app")
        w.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(14, 8, 10, 8)
        h.setSpacing(10)
        marca = QtWidgets.QLabel(objectName="marca")
        marca.setFixedSize(36, 36)
        marca.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        tema.pon_icono(marca, "logo", "sobre_acento", 24)
        h.addWidget(marca)
        h.addWidget(QtWidgets.QLabel(config.APP_NOMBRE.split(" · ")[0], objectName="app_titulo"))
        h.addStretch()
        v = QtWidgets.QVBoxLayout()
        v.setSpacing(0)
        self._lbl_hora = QtWidgets.QLabel(objectName="reloj", alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self._lbl_fecha = QtWidgets.QLabel(objectName="reloj_sub", alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        v.addWidget(self._lbl_hora)
        v.addWidget(self._lbl_fecha)
        h.addLayout(v)
        h.addSpacing(8)
        b = QtWidgets.QToolButton(objectName="icono")
        b.setDefaultAction(self.acc_solo_mapa)
        b.setIconSize(QtCore.QSize(20, 20))
        h.addWidget(b)
        b = QtWidgets.QToolButton(objectName="icono")
        tema.pon_icono(b, "ajustes", "tenue", 20)
        b.setIconSize(QtCore.QSize(20, 20))
        b.setToolTip("Configuración")
        b.clicked.connect(self._ver_ajustes)
        h.addWidget(b)
        m = QtWidgets.QToolButton(objectName="icono")
        tema.pon_icono(m, "menu", "tenue", 20)
        m.setIconSize(QtCore.QSize(20, 20))
        m.setToolTip("Menú")
        m.setMenu(self.menu_app)
        m.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        h.addWidget(m)
        tema.manos(w)
        self._reloj_app = QtCore.QTimer(self, interval=15000)
        self._reloj_app.timeout.connect(self._pon_hora)
        self._reloj_app.start()
        self._pon_hora()
        return w

    def _pinta_acciones(self):
        """Los iconos de las acciones: no son widgets, y al cambiar de estilo no se rehacen solos."""
        self.acc_solo_mapa.setIcon(tema.icono("solo_mapa", tema.c("tenue"), 20, activo=tema.c("acento_claro")))

    def _pon_hora(self):
        ahora = QtCore.QDateTime.currentDateTime()
        self._lbl_hora.setText(ahora.toString("HH:mm"))
        self._lbl_fecha.setText(QtCore.QLocale(QtCore.QLocale.Language.Spanish).toString(ahora.date(), "ddd d 'de' MMMM"))

    def _mensajes_arranque(self):
        log.info(f"{config.APP_NOMBRE} · versión {config.pide('identidad', 'version')}")
        lat, lon = self.emp["lat"], self.emp["lon"]
        log.info(f"Emplazamiento: {self.emp['nombre']} → {lat:.6f}, {lon:.6f}")
        g = geo.convergencia_deg(lat, lon)
        log.info(f"Proyección de trabajo {config.EPSG_UTM}; convergencia de meridianos "
                 f"γ = {g:+.2f}°".replace(".", ","))
        log.info(f"Carpeta de datos: {config.DATOS}")
        if not config.datos_disponibles():
            log.error(f"No se encuentra la carpeta de datos {config.DATOS}. Si está en la "
                      f"unidad de red, conéctate a {config.pide('identidad', 'red_datos')} y reinicia la "
                      f"app. Sin ella no hay terreno, edificios, estaciones ni viento.")
            QtCore.QTimer.singleShot(1500, lambda: QtWidgets.QMessageBox.warning(
                self, config.APP_NOMBRE,
                f"No se encuentra la carpeta de datos:\n{config.DATOS}\n\n"
                f"Si está en la unidad de red, conéctate a {config.pide('identidad', 'red_datos')} y "
                "vuelve a abrir la app."))
        log.info("Cargando mapa…")

    # ── disposición ──────────────────────────────────────────────────────────────────────
    def showEvent(self, evento):
        super().showEvent(evento)
        if self._estado_defecto is None:
            # resizeDocks solo surte efecto con la ventana ya dispuesta: se aplica aquí.
            QtCore.QTimer.singleShot(0, self._disposicion_inicial)

    def changeEvent(self, evento):
        if evento.type() == QtCore.QEvent.Type.WindowStateChange and hasattr(self, "panel"):
            QtCore.QTimer.singleShot(300, self._segun_minimizada)
        super().changeEvent(evento)

    def _segun_minimizada(self):
        """Minimizada no se ve nada: el mapa deja de pintar y el reproductor de avanzar (medido: 8 % → 0,1 %
        de CPU del equipo). Va con retardo porque Qt vuelve a poner visible la página justo al minimizar."""
        minimizada = self.isMinimized()
        self.mapa.page().setVisible(not minimizada)
        self.panel.dormir(minimizada)
        if self._ventana_ajustes is not None:
            self._ventana_ajustes.dormir(minimizada)

    def _proporciones_defecto(self):
        self.resizeDocks([self.dock_panel], [450], QtCore.Qt.Orientation.Horizontal)
        self.resizeDocks([self.dock_consola], [170], QtCore.Qt.Orientation.Vertical)

    def _disposicion_inicial(self):
        self._proporciones_defecto()
        self.dock_consola.hide()                 # actividad y terminal, a mano en el panel
        self.dock_terminal.hide()
        self._estado_defecto = self.saveState()
        estado = self.ajustes.value("ventana/estado_v3")
        if estado is not None:
            self.restoreState(estado)

    @staticmethod
    def _alternar(dock):
        """Abre un panel de abajo, delante del otro si están los dos, o lo cierra. Tapado por la otra pestaña,
        Qt lo da por visible: lo que cuenta es si se ve algo de él."""
        if dock.isVisible() and not dock.visibleRegion().isEmpty():
            dock.hide()
        else:
            dock.show()
            dock.raise_()

    def _restablecer_disposicion(self):
        self.acc_solo_mapa.setChecked(False)
        for dock in self._docks:
            dock.setFloating(False)
            dock.show()
        if self._estado_defecto is not None:
            self.restoreState(self._estado_defecto)
        self._proporciones_defecto()

    def _solo_mapa(self, activo):
        if activo:
            self._antes_de_solo_mapa = [d.isVisible() for d in self._docks]
            for d in self._docks:
                d.hide()
        else:
            for d, visible in zip(self._docks, self._antes_de_solo_mapa or ()):
                d.setVisible(visible)

    def closeEvent(self, evento):
        en_curso = [t for t in (self._trabajo, self._trabajo_edif)
                    if t is not None and t.isRunning()]
        if en_curso:
            r = QtWidgets.QMessageBox.question(
                self, "Descarga en curso", "Hay una descarga en curso. ¿Cancelarla y salir?")
            if r != QtWidgets.QMessageBox.StandardButton.Yes:
                evento.ignore()
                return
        # Cerrar la principal cierra la app: si no, seguiría viva con las otras ventanas. Cada una pregunta si tiene cambios
        # sin guardar y, si se cancela, la principal sigue abierta y no se cancela ningún trabajo.
        for v in (self._ventana_focos, self._ventana_planes, self._ventana_ajustes):
            if v is not None and (pregunta_abierta(v) or not v.close()):
                evento.ignore()
                return
        for t in en_curso:
            t.cancelar()
            if not t.wait(20000):
                log.warning("La descarga no terminó a tiempo; se cierra igualmente.")
        if self._trabajo_rosas is not None and self._trabajo_rosas.isRunning():
            self._trabajo_rosas.wait(15000)          # cálculo corto: se espera sin preguntar
        for t in (self._trabajo_sim, self._trabajo_3d, self._trabajo_periodo):
            if t is not None and t.isRunning():
                t.cancelar()
                t.wait(15000)
        self.ajustes.setValue("ventana/geometria_v2", self.saveGeometry())
        self.ajustes.setValue("ventana/estado_v3", self.saveState())
        self.ajustes.sync()                      # al salir de Python no siempre se destruye
        self.consola.desconectar()
        super().closeEvent(evento)

    # ── mapa ─────────────────────────────────────────────────────────────────────────────
    def _limites(self):
        """[[sur, oeste], [norte, este]] del terreno (descargado o por descargar)."""
        lado = self.terreno_info["lado_km"] if self.terreno_info else config.DOMINIO_DESCARGA_KM
        vertices, _ = geo.cuadrado_utm(self.emp["lat"], self.emp["lon"], lado)
        lats, lons = [v[0] for v in vertices], [v[1] for v in vertices]
        return [[min(lats), min(lons)], [max(lats), max(lons)]]

    def _mapa_listo(self):
        log.info("Mapa listo.")
        self._pintar_terreno(visible=False)          # también tras «Recargar mapa»
        self._pintar_edificios()
        self._pintar_estaciones()
        self._pintar_receptores()
        if self._abrir_focos:                    # arranque con --focos
            self._abrir_focos = False
            self._ver_focos()
        if self._abrir_planes:                   # arranque con --planes
            self._abrir_planes = False
            self._ver_planes()
        if self._dia_inicial:                    # arranque con --dia: ese día ya en el mapa
            dia, self._dia_inicial = self._dia_inicial, None
            log.info(f"Arranque con --dia {dia}: Reanálisis con el viento de ese día.")
            self.panel.preparar_dia_viento(dia)
            self._cargar_viento(dia)

    def _clic_mapa(self, lat, lon):
        """Un clic en el mapa: coordenadas, cota, uso del suelo y posición respecto a la planta."""
        x, y = geo.a_utm(lat, lon)
        ficha = [("Coordenadas", f"{lat:.5f}, {lon:.5f}"), ("UTM", f"{_num(x)} · {_num(y)} m")]
        if self._terreno_arr is not None:
            punto = terreno.describir_punto(*self._terreno_arr, lat, lon)
            if punto is None:
                ficha.append(("Terreno", "fuera del terreno descargado"))
            else:
                z, u, nombre = punto
                ficha += [("Cota", f"{_num(z)} m"), ("Uso del suelo", nombre)]
        if self._edif is not None:
            b = edificios.en_punto(self._edif, lat, lon)
            if b is not None:
                ficha.append(("Edificio", f"{b['uso']}, {int(b['plantas'])} planta(s), {_num(b['area_m2'])} m²"))
        d, rumbo = geo.distancia_rumbo(self.emp["lat"], self.emp["lon"], lat, lon)
        lugar = "junto a la planta" if d < 50 else f"a {_num(d / 1000, 1)} km al {rumbo} de la planta"
        ficha.append(("Situación", lugar))
        self.mapa.ficha(lat, lon, mapa_web.ficha_html("Este punto", ficha))

    # ── receptores de cálculo ────────────────────────────────────────────────────────────
    def _pintar_receptores(self, visible=False):
        """Malla de receptores (gui/receptores_mapa.py) como capa del selector, fuera del grupo de
        capas temáticas excluyentes (se puede ver encima de la elevación o del satélite)."""
        if self._resumen is None:
            return
        from teodors.casos import receptores
        ESTILOS = receptores.estilos()
        recs = receptores.malla(self._resumen["nucleos"], self._edif_todos)   # viviendas a 2 km
        res = receptores.resumen(recs)
        clases = list(ESTILOS)
        estilos = [{"color": ESTILOS[c][0], "radio": ESTILOS[c][1]}
                   for c in clases]
        puntos = [(la, lo, clases.index(c)) for la, lo, c in receptores.a_geo(recs)]
        filas = "".join(
            f"<div class='clase'><span class='muestra' style='background:"
            f"{ESTILOS[c][0]};border-radius:50%'></span>{ESTILOS[c][2]}"
            f"<span class='pct'>{_num(res['por_clase'].get(c, 0))}</span></div>"
            for c in clases)
        leyenda = (f"<h4>Receptores de cálculo · {_num(res['total'])}</h4>"
                   f"<div class='clases'>{filas}</div>")
        self.mapa.set_capa_puntos("receptores", "Receptores (malla de cálculo)", puntos, estilos,
                                  leyenda, visible=visible)
        log.info(f"Receptores de cálculo: {_num(res['total'])} · "
                 + " · ".join(f"{ESTILOS[c][2]}: {_num(res['por_clase'].get(c, 0))}"
                              for c in clases))

    # ── estaciones meteorológicas ────────────────────────────────────────────────────────
    def _cargar_estaciones(self):
        """Estaciones cercanas, solo de la caché (sin red al arrancar)."""
        try:
            self._estaciones = estaciones.para_mapa(self.emp["lat"], self.emp["lon"])
        except Exception as e:                      # el mapa sigue sin ellas
            log.warning(f"No se pudieron leer las estaciones de la caché: {e!r}")
            self._estaciones = []
        if self._estaciones:
            log.info(f"Estaciones {config.pide('estaciones', 'proveedor')} en el mapa: {len(self._estaciones)}")
        else:
            log.info(f"Sin estaciones {config.pide('estaciones', 'proveedor')} en la caché (python -m teodors.fuentes.descargar_meteocat).")

    @staticmethod
    def _anios(lista):
        if not lista:
            return "sin datos descargados"
        return f"datos {lista[0]}–{lista[-1]}" if len(lista) > 1 else f"datos {lista[0]}"

    def _pintar_estaciones(self):
        """Iconos de las estaciones. Con el horizonte «Reanálisis», el tooltip lleva además la
        rosa de lo MEDIDO el día cargado y la de los años del reanálisis (si están sus datos), a la
        altura del anemómetro. Sin nada de ERA5 en el tooltip, con ningún horizonte (decisión
        del usuario)."""
        rean = self.panel.horizonte_meteo() == "reanalisis"
        rosas = (self._rosas or {}).get("estaciones", {}) if rean else {}
        dia = (self._rosas_dia or {}) if rean else {}
        lista = []
        for e in self._estaciones:
            h = e["altura_viento_m"]
            texto = (f"<b>{e['nombre']}</b> ({e['codigo']}) · {config.pide('estaciones', 'proveedor')}<br>"
                     f"altitud {_num(e['altitud_m'])} m · "
                     + (f"viento a {_num(h)} m" if h else "sin viento") + "<br>"
                     f"a {_num(e['dist_m'] / 1000, 1)} km al {e['rumbo']} de la planta<br>"
                     f"{self._anios(e['anios'])}")
            bloques, altura, clases = [], None, None
            rd = dia.get("estaciones", {}).get(e["codigo"])
            if rd:
                d = dia["dia"]
                bloques.append((f"Día {d[8:10]}/{d[5:7]}/{d[:4]} ({_num(rd['horas'])} h medidas)", rd))
                altura, clases = rd["altura_m"], dia["clases"]
            r = rosas.get(e["codigo"])
            if r:
                bloques.append((f"{r['desde']}–{r['hasta']} ({_num(r['horas'])} h)", r))
                altura, clases = altura or r["altura_m"], clases or self._rosas["clases"]
            if bloques:
                lado = 230 if len(bloques) == 1 else 190
                texto += ("<div style='margin-top:4px;font-weight:600'>Rosa de los vientos</div>"
                          "<div style='display:flex;gap:10px'>"
                          + "".join(f"<div><div style='font-size:11px'>{t}</div>"
                                    + mapa_web.rosa_svg(b["obs"], clases, lado=lado)
                                    + f"<div style='font-size:10.5px'>Calmas (&lt; 0,5 m/s): "
                                      f"{_num(b['calmas'], 1)} %</div></div>"
                                    for t, b in bloques)
                          + "</div>" + mapa_web.leyenda_rosa(clases, None, altura))
            lista.append({"codigo": e["codigo"], "lat": e["lat"], "lon": e["lon"],
                          "texto": texto, "lateral": bool(bloques)})
        self.mapa.set_estaciones(lista)

    def _horizonte_meteo(self, clave):
        """Cambio de opción en Meteorología: lo simulado era con la anterior."""
        from teodors.operacion import periodos
        self.panel.mostrar_viento(clave == "reanalisis")
        self.panel.mostrar_periodo(clave)
        self.mapa.quitar_viento()
        self._dia_viento = None
        self._limpiar_simulacion()
        self._rosas_dia = None
        if clave in ("reanalisis", "queja", "prediccion"):
            self.panel.ir_a("meteo")
        if clave in periodos.DIAS:
            self._periodo_cambiado()
        if clave != "reanalisis":
            self._pintar_estaciones()
            return
        self.panel.set_dias_reanalisis(periodos.dias_reanalisis())
        self._serie_viento = viento_mapa.serie_disponible()
        self.panel.set_viento_dias(viento_mapa.rango_dias(self._serie_viento) if self._serie_viento else None,
                                   viento_mapa.dia_inicial(self._serie_viento) if self._serie_viento else None)
        if self._rosas is not None:
            self._pintar_estaciones()
            return
        if self._trabajo_rosas is not None and self._trabajo_rosas.isRunning():
            return
        log.info("Reanálisis: calculando las rosas de los vientos de las estaciones…")
        t = Trabajo(validacion.rosas_estaciones, self.emp["lat"], self.emp["lon"], parent=self)
        t.hecho.connect(self._rosas_hechas)
        t.fallo.connect(lambda m: log.error(f"No se pudieron calcular las rosas: {m}"))
        self._trabajo_rosas = t
        t.start()

    # ── viento en superficie (capa animada) ──────────────────────────────────────────────
    def _cargar_viento(self, fecha, serie=None, dias=1):
        """Carga en segundo plano el viento del nivel 1 de ese día o de esos días (serie de teOdors)."""
        if self._trabajo_viento is not None and self._trabajo_viento.isRunning():
            return
        self.panel.set_viento_cargando(True)
        serie = serie or getattr(self, "_serie_viento", None) or viento_mapa.serie_defecto()
        log.info(f"Viento en superficie: cargando el {fecha}, {dias} día(s) ({viento_mapa.titulos().get(serie, serie)})…")

        def dia_completo(f, progreso=None):
            """Viento del día y las rosas de lo medido ese día en las estaciones. Solo eso: el penacho se
            ve en Simular, con la operación de los focos (usuario, 2026-10-31)."""
            d = viento_mapa.datos_dia(f, serie, dias=dias)
            try:
                d["rosas_dia"] = validacion.rosas_dia(self.emp["lat"], self.emp["lon"], f) if dias == 1 and not serie.startswith("prediccion_") else None
            except Exception as e:                  # sin medidas de ese día: sin rosa del día
                log.warning(f"Sin rosas del día en las estaciones: {e!r}")
                d["rosas_dia"] = None
            return d

        t = Trabajo(dia_completo, fecha, parent=self)
        t.hecho.connect(self._viento_cargado)
        t.fallo.connect(lambda m: log.error(f"No se pudo cargar el viento: {m}"))
        t.finished.connect(lambda: self.panel.set_viento_cargando(False))
        self._trabajo_viento = t
        t.start()

    def _viento_cargado(self, d):
        self.mapa.set_viento(d)
        self._dia_viento = (d["horas"][0][:10], len(d["horas"]) // 24)
        self.panel.btn_play.setChecked(False)
        self.panel.btn_lento.setChecked(False)
        self._rosas_dia = d.get("rosas_dia")
        self._pintar_estaciones()
        self.panel.set_viento_listo(d["horas"])
        if self._animar_al_cargar:
            self._animar_al_cargar = False
            self.panel.animar()

    def _rosas_hechas(self, res):
        self._rosas = res
        self._pintar_estaciones()

    def _clic_estacion(self, codigo):
        e = next((s for s in self._estaciones if s["codigo"] == codigo), None)
        if e is None:
            return
        h = e["altura_viento_m"]
        self.mapa.ficha(e["lat"], e["lon"], mapa_web.ficha_html(
            f"{e['nombre']} ({e['codigo']})",
            [("Altitud", f"{_num(e['altitud_m'])} m"),
             ("Anemómetro", f"a {_num(h)} m" if h else "sin viento"),
             ("Situación", f"a {_num(e['dist_m'] / 1000, 1)} km al {e['rumbo']} de la planta"),
             ("Datos", self._anios(e["anios"]))]))

    # ── terreno ──────────────────────────────────────────────────────────────────────────
    def _cargar_terreno_guardado(self):
        info = terreno.ultimo_caso(self.emp["lat"], self.emp["lon"])
        self._usar_terreno(info)
        if info:
            lt = info["lado_km"]
            log.info(f"Terreno cargado del disco: {_km(lt)} × {_km(lt)} km ({_km(lt / 2)} km al "
                     f"centro) a {_num(info['res_m'])} m, descargado el {info['fecha'][:10]}.")
            n = self._resumen["nucleos"]
            cuenta = {f: sum(1 for k in n if k["familia"] == f) for f in terreno.FAMILIAS_NUCLEO}
            log.info(f"Núcleos {config.pide('fuentes', 'usos')}: {cuenta['residencial']} urbanos, "
                     f"{cuenta['industrial']} industriales y {cuenta['deportivo']} deportivos.")
        elif config.datos_disponibles():
            log.info("No hay terreno descargado para la planta.")

    def _usar_terreno(self, info, visible=False):
        self.terreno_info = info
        if info:
            self._terreno_arr = terreno.cargar(info)
            self._resumen = terreno.resumen(*self._terreno_arr, self.emp["lat"], self.emp["lon"])
            self._cargar_nombres(info)
        else:
            self._terreno_arr = self._resumen = None
        self.panel.set_terreno(info, self._resumen)
        self.mapa.set_limites(self._limites())
        if self.mapa.esta_listo():
            self._pintar_terreno(visible)

    def _pintar_terreno(self, visible=False):
        """Capas de elevación y usos (apagadas salvo `visible`) y los iconos de núcleos."""
        if not self.terreno_info:
            for id_capa in ("elevacion", "usos"):
                self.mapa.quitar_capa(id_capa)
            self.mapa.set_nucleos([])
            return
        for capa in self.terreno_info["capas_mapa"]:
            self.mapa.set_capa_imagen(capa, self.terreno_info["dir"],
                                      visible=visible and capa["id"] == "elevacion",
                                      opacidad=0.75 if capa["id"] == "elevacion" else 0.65,
                                      grupo=GRUPO_TEMATICO)
        self._pintar_nucleos()

    def _pintar_nucleos(self):
        """Iconos de los núcleos (pueblos, industria, deportivos). Tras simular un plan, el tooltip lleva
        la tabla de media, máximo y P98 en ese punto."""
        if not self._resumen:
            self.mapa.set_nucleos([])
            return
        lista = []
        for n in self._resumen["nucleos"]:
            nom = self._nombres.get(terreno.clave_nucleo(n), {})
            pob, mun = nom.get("poblacion"), nom.get("municipio")
            texto = ((f"<b style='font-size:13px'>{pob}</b>"
                      + (f" ({mun})" if mun and mun != pob else "") + "<br>" if pob else "")
                     + f"<b>{n['tipo']}</b><br>{_num(n['ha'])} ha · a "
                     f"{_num(n['dist_m'] / 1000, 1)} km al {n['rumbo']} de la planta")
            texto += self._tabla_plan(n["x"], n["y"])
            lista.append({"familia": n["familia"], "lat": n["lat"], "lon": n["lon"], "texto": texto})
        # los receptores con nombre: el uso del suelo no los ve
        for r in receptores_mapa.con_nombre():
            lat, lon = geo.a_geo(r["x"], r["y"])
            lista.append({"familia": "industrial", "lat": lat, "lon": lon,
                          "texto": f"<b style='font-size:13px'>{r['nombre']}</b>" + self._tabla_plan(r["x"], r["y"])})
        self.mapa.set_nucleos(lista)

    def _tabla_plan(self, x, y):
        """Valores de lo simulado en ese receptor, para su tooltip: los años del reanálisis y el día, el episodio o la predicción."""
        from teodors.operacion import simulacion as planes_calculo, periodos
        punto = (round(float(x), 1), round(float(y), 1))
        salen = ""
        for cual, valores in self._valores.items():
            v, r = valores.get(punto), self._resultados.get(cual)
            if v and r:
                tramo = periodos.etiqueta(r["periodo"]) if r["periodo"] else texto_anios()
                salen += planes_calculo.tabla_punto(v, f"Plan «{r['nombre']}» · {tramo}", r["magnitudes"][self._magnitud])
        return salen

    def _cargar_nombres(self, info):
        """Nombre de los núcleos: de la caché del terreno o, si faltan, de su servicio (una vez,
        en segundo plano; luego se repintan los iconos)."""
        lista = self._resumen["nucleos"]
        self._nombres = terreno.nombres_nucleos(info, lista)
        if (all(terreno.clave_nucleo(n) in self._nombres for n in lista)
                or not config.datos_disponibles()
                or (self._trabajo_nombres is not None and self._trabajo_nombres.isRunning())):
            return
        log.info(f"Pidiendo a {config.pide('fuentes', 'nombres_nucleos')} el nombre de los núcleos (solo la primera vez)…")
        t = Trabajo(terreno.nombres_nucleos, info, lista, True, parent=self)
        t.hecho.connect(lambda nombres: (setattr(self, "_nombres", nombres), self._pintar_nucleos(),
                                         log.info(f"Nombres de {len(nombres)} núcleos guardados.")))
        t.fallo.connect(lambda m: log.warning(f"Sin nombres de los núcleos: {m}"))
        self._trabajo_nombres = t
        t.start()

    # ── edificios ────────────────────────────────────────────────────────────────────────
    def _cargar_edificios_guardados(self):
        # Se descargan a 2 km (las viviendas son receptores), pero en el panel, en el mapa y para
        # los focos solo cuentan los cercanos (config.RADIO_EDIFICIOS_FOCOS_M; usuario, 2026-10-24)
        info, self._edif_todos = edificios.cargar(self.emp["lat"], self.emp["lon"])
        if self._edif_todos is None:
            self.edif_info, self._edif = None, None
        else:
            self._edif = edificios.cercanos(self._edif_todos)
            self.edif_info = dict(info, **edificios.resumen(self._edif),
                                  radio_m=config.RADIO_EDIFICIOS_FOCOS_M, n_descargados=info["n"],
                                  viviendas=int((self._edif_todos["uso"] == "Residencial").sum()))
        self.panel.set_edificios(self.edif_info)
        if self.edif_info:
            log.info(f"Edificios: {self.edif_info['n']} a menos de {_num(self.edif_info['radio_m'])} m de la planta.")

    def _pintar_edificios(self, visible=False):
        """Capa de edificios en el selector. Al arrancar, APAGADA (como elevación y usos:
        decisión del usuario); solo se enciende sola tras descargarla."""
        if self._edif is None:
            return
        from teodors.fuentes.catastro import USO_COLOR
        leyenda = mapa_web.leyenda_html(f"Edificios ({config.pide('fuentes', 'edificios')})", {"tipo": "clases", "clases": [
            {"codigo": n, "nombre": u, "pct": 100.0 * n / max(self.edif_info["n"], 1),
             "color": USO_COLOR.get(u, "#999999")}
            for u, n in self.edif_info["por_uso"].items()]})
        self.mapa.set_capa_geojson("edificios", f"Edificios ({config.pide('fuentes', 'edificios')})",
                                   edificios.geojson_mapa(self._edif), leyenda,
                                   visible=visible, grupo=GRUPO_TEMATICO)

    def _descargar_edificios(self):
        if not config.datos_disponibles():
            log.error(f"No se puede descargar: no se encuentra la carpeta de datos {config.DATOS} "
                      f"(¿unidad de red sin conectar?).")
            return
        if self._trabajo_edif is not None and self._trabajo_edif.isRunning():
            return
        log.info(f"Descargando edificios del {config.pide('fuentes', 'edificios')} a menos de "
                 f"{_km(config.RADIO_EDIFICIOS_KM)} km…")
        self.panel.set_descargando_edificios(True)
        t = Trabajo(edificios.descargar, self.emp["lat"], self.emp["lon"], parent=self)
        t.progreso.connect(self.panel.set_progreso_edificios)
        t.hecho.connect(lambda _: (self._cargar_edificios_guardados(),
                                   self._pintar_edificios(visible=True)))
        t.fallo.connect(lambda m: log.error(f"No se pudieron descargar los edificios: {m}"))
        t.finished.connect(lambda: self.panel.set_descargando_edificios(False))
        self._trabajo_edif = t
        t.start()

    def _redescargar_terreno(self):
        """Archivo → Volver a descargar: solo para mantenimiento (normalmente no hace falta)."""
        if self.terreno_info is not None:
            r = QtWidgets.QMessageBox.question(
                self, "Volver a descargar el terreno",
                f"El terreno ya está descargado (el {self.terreno_info['fecha'][:10]}) y se "
                f"carga del disco.\nSolo hace falta descargarlo de nuevo si los datos del {config.pide('fuentes', 'mdt')} o "
                f"de {config.pide('fuentes', 'usos')} han cambiado.\n\n¿Descargarlo de nuevo?")
            if r != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self._descargar_terreno()

    def _descargar_terreno(self):
        if not config.datos_disponibles():
            log.error(f"No se puede descargar: no se encuentra la carpeta de datos {config.DATOS} "
                      f"(¿unidad de red sin conectar?).")
            return
        if self._trabajo is not None and self._trabajo.isRunning():
            return
        lat, lon = self.emp["lat"], self.emp["lon"]
        ld = config.DOMINIO_DESCARGA_KM
        log.info(f"Descargando terreno y uso del suelo: {_km(ld)} × {_km(ld)} km a "
                 f"{_num(config.RES_TERRENO_M)} m…")
        self.panel.set_descargando(True)
        self._trabajo = TrabajoTerreno(lat, lon, ld, self)
        self._trabajo.progreso.connect(self.panel.set_progreso_terreno)
        self._trabajo.hecho.connect(self._terreno_hecho)
        self._trabajo.fallo.connect(self._terreno_fallo)
        self._trabajo.finished.connect(lambda: self.panel.set_descargando(False))
        self._trabajo.start()

    def _terreno_hecho(self, info):
        self._usar_terreno(info, visible=True)
        self.mapa.centrar()

    def _terreno_fallo(self, mensaje):
        if "cancelada" in mensaje:
            log.warning(mensaje)
            return
        log.error(f"No se pudo descargar el terreno: {mensaje}")
        QtWidgets.QMessageBox.warning(
            self, "Terreno", f"No se pudo descargar el terreno:\n{mensaje}\n\n"
            f"Si es un fallo del servidor del {config.pide('fuentes', 'mdt')}, suele ser temporal: reinténtalo en un minuto.")

    # ── focos de emisión ─────────────────────────────────────────────────────────────────
    def _cargar_focos(self):
        from teodors.operacion import focos
        try:
            datos = focos.cargar()
        except (ValueError, OSError) as e:
            log.error(f"No se pudieron leer los focos ({config.FOCOS_JSON.name}): {e}")
            datos = None
        self.panel.set_focos(datos)
        if datos and datos["focos"]:
            log.info(f"Focos de emisión: {len(datos['focos'])}")

    def _ver_focos(self):
        """Segunda ventana con los focos (una sola: si ya está abierta, se trae delante)."""
        if self._ventana_focos is None:
            from teodors.gui.ventana_focos import VentanaFocos
            self._ventana_focos = VentanaFocos(self.emp, self.ajustes)
            self._ventana_focos.guardado.connect(self._cargar_focos)
        self._ventana_focos.show()
        self._ventana_focos.raise_()
        self._ventana_focos.activateWindow()

    def _ver_ajustes(self):
        """Ventana de configuración (una sola: si ya está abierta, se trae delante)."""
        if self._ventana_ajustes is None:
            from teodors.gui.ventana_ajustes import VentanaAjustes
            self._ventana_ajustes = VentanaAjustes(self.emp, self)
            self._ventana_ajustes.vientoCambiado.connect(self.mapa.viento_estilo)
            self._ventana_ajustes.escalasCambiadas.connect(self.mapa.set_escalas)
        self._ventana_ajustes.refrescar()
        self._ventana_ajustes.show()
        self._ventana_ajustes.raise_()
        self._ventana_ajustes.activateWindow()

    def _forma_viento(self):
        """Forma del viento elegida en el selector del mapa: que la configuración lo enseñe igual."""
        if self._ventana_ajustes is not None:
            self._ventana_ajustes.refrescar()

    def _ver_planes(self):
        """Ventana de los planes de operación (una sola: si ya está abierta, se trae delante)."""
        if self._ventana_planes is None:
            from teodors.gui.ventana_planes import VentanaPlanes
            self._ventana_planes = VentanaPlanes(self.emp, self.ajustes)
            self._ventana_planes.guardado.connect(self._plan_guardado)
        self._ventana_planes.show()
        self._ventana_planes.raise_()
        self._ventana_planes.activateWindow()

    # ── simulación: plan + meteorología → resultados en el mapa ──────────────────────────
    def _actualizar_planes(self):
        from teodors.operacion import planes as escenarios, simulacion as planes_calculo
        self.panel.set_planes([(n, str(r)) for n, r, _ in escenarios.listar()], planes_calculo.disponible())

    def _plan_guardado(self):
        self._actualizar_planes()
        nombre = self._ventana_planes.esc.get("nombre")
        if any(r and r["nombre"] == nombre for r in self._resultados.values()):
            self.panel.set_resultado_caducado()

    def _leer_plan(self, ruta):
        from teodors.operacion import planes as escenarios, focos
        try:
            catalogo = focos.cargar()
            return (escenarios.cargar(ruta) if ruta else escenarios.base(catalogo)), catalogo
        except (ValueError, OSError) as e:
            log.error(f"No se pudo leer el plan: {e}")
            self.panel.set_simulando(False)
            self.panel.set_fallo_simulacion(str(e))
            return None, None

    def _simular(self, ruta):
        """Los años del reanálisis."""
        self._lanzar_simulacion(ruta, None)

    def _simular_periodo(self, ruta):
        """Un día del reanálisis, el episodio o la predicción."""
        p = self.panel.periodo_simulacion()
        if p is not None:
            self._lanzar_simulacion(ruta, p)

    def _lanzar_simulacion(self, ruta, periodo):
        """Si ya está simulado con lo mismo, se lee; si no, en segundo plano."""
        from teodors.operacion import simulacion as planes_calculo
        if self._trabajo_sim is not None:
            return
        esc, catalogo = self._leer_plan(ruta)
        if esc is None:
            return
        self._limpiar_simulacion(periodo is not None)
        guardado = planes_calculo.guardado(esc, catalogo, periodo)
        if guardado is not None:
            log.info(f"Plan «{esc['nombre']}»: leído lo ya simulado.")
            self._simulado(guardado)
            return
        self.panel.set_simulando(True, periodo is not None)
        log.info(f"Simulando el plan «{esc['nombre']}»…")
        if periodo is None:
            self._trabajo_sim = Trabajo(planes_calculo.calcular, esc, catalogo, parent=self)
        else:
            self._trabajo_sim = Trabajo(planes_calculo.calcular_periodo, esc, catalogo, periodo, parent=self)
        self._trabajo_sim.progreso.connect(self.panel.set_progreso_simulacion)
        self._trabajo_sim.hecho.connect(self._simulado)
        self._trabajo_sim.fallo.connect(self._simulacion_fallida)
        self._trabajo_sim.finished.connect(self._fin_simulacion)
        self._trabajo_sim.start()

    def _simulado(self, r):
        from teodors.operacion import simulacion as planes_calculo, periodos
        p = r["periodo"]
        self._resultados["periodo" if p else "anios"] = r
        self.panel.set_resultado(r, planes_calculo.cifra)
        clave = self.panel.cmb_magnitud.currentData() or r["orden"][0]
        self._poner_magnitud(clave, "penacho" if p else "plan_media")
        self.mapa.aviso(f"Plan «{r['nombre']}» simulado")
        if not p:
            return
        if self._dia_viento == (p["ini"], p["dias"]):
            self.panel.animar()
        else:
            self._animar_al_cargar = True
            self._cargar_viento(p["ini"], r["serie"], p["dias"])

    def _ids_capas(self):
        from teodors.operacion import simulacion as planes_calculo
        return ["penacho"] + [f"{pre}_{c}" for pre in ("plan", "dia") for c in planes_calculo.CAPAS]

    def _poner_magnitud(self, clave, encendida):
        """Lleva al mapa las capas de una magnitud (olor o un gas), con `encendida` a la vista; no se recalcula nada."""
        from teodors.operacion import simulacion as planes_calculo, periodos
        self._magnitud = clave
        self._valores = {}
        for cual, r in self._resultados.items():
            if r is None or clave not in r["magnitudes"]:
                continue
            m = r["magnitudes"][clave]
            prefijo = "dia" if cual == "periodo" else "plan"
            nombre = periodos.etiqueta(r["periodo"]) if r["periodo"] else texto_anios()
            hay = set()
            for c in m["capas"]:
                hay.add(c["id"])
                self.mapa.set_imagenes(c["id"], f"{nombre} · {c['titulo']}", c["imagenes"], c["leyenda"], visible=c["id"] == encendida,
                                       opacidad=penacho_mapa.OPACIDAD, grupo=penacho_mapa.GRUPO, escala=c["escala"])
                if c["id"] != encendida:
                    self.panel.set_capa_visible(c["id"], False)
            for capa in planes_calculo.CAPAS:
                if f"{prefijo}_{capa}" not in hay:
                    self.mapa.quitar_capa(f"{prefijo}_{capa}")
                    self.panel.set_capa_visible(f"{prefijo}_{capa}", False)
            if m["penacho"]:
                self.mapa.set_penacho(dict(planes_calculo.datos_penacho(r, clave), visible=encendida == "penacho"))
                q = self.panel.hora_viento.value()
                self.mapa.penacho_hora(q // 4, (q % 4) / 4)
            self._valores[cual] = planes_calculo.valores(r, clave)
        self._pintar_nucleos()

    def _ver_magnitud(self, clave):
        """Se ha elegido otra magnitud en el panel: sigue a la vista lo mismo (penacho, media, máximo o norma)."""
        from teodors.operacion import simulacion as planes_calculo
        if not clave or clave == self._magnitud or not any(self._resultados.values()):
            return
        self._poner_magnitud(clave, self.panel.capa_encendida(self._ids_capas()))
        for cual, bloque in (("anios", self.panel.res_anios), ("periodo", self.panel.res_periodo)):
            r = self._resultados[cual]
            if r is not None and clave in r["magnitudes"]:
                bloque.poner(r["magnitudes"][clave], planes_calculo.cifra)

    def _simulacion_fallida(self, mensaje):
        log.error(f"No se pudo simular: {mensaje}")
        self.panel.set_fallo_simulacion(mensaje)

    def _fin_simulacion(self):
        self._trabajo_sim = None
        self.panel.fin_simulacion()

    def _limpiar_simulacion(self, periodo=None):
        """Quita lo simulado: `periodo` True, el día, el episodio o la predicción; False, los años del reanálisis; None, todo."""
        from teodors.operacion import simulacion as planes_calculo
        for prefijo, cual, es in (("plan", "anios", False), ("dia", "periodo", True)):
            if periodo is None or periodo == es:
                for capa in planes_calculo.CAPAS:
                    self.mapa.quitar_capa(f"{prefijo}_{capa}")
                    self.panel.set_capa_visible(f"{prefijo}_{capa}", False)
                self._resultados[cual] = None
                self._valores.pop(cual, None)
        if periodo is None or periodo:
            self.mapa.quitar_penacho()
            self.panel.set_capa_visible("penacho", False)
        self.panel.limpiar_resultado(periodo)
        if not any(self._resultados.values()):
            self._magnitud = None
        self._pintar_nucleos()

    # ── episodio de queja y predicción: su periodo ───────────────────────────────────────
    def _periodo_cambiado(self):
        from teodors.operacion import periodos
        p = self.panel.periodo()
        if p is None:
            return
        self._limpiar_simulacion(True)
        self.panel.set_periodo_estado(periodos.listo(p))

    def _preparar_periodo(self):
        """Descarga la meteorología del periodo y calcula su viento y sus respuestas; mientras, el botón lo cancela."""
        from teodors.operacion import periodos
        if self._trabajo_periodo is not None:
            self._trabajo_periodo.cancelar()
            return
        p = self.panel.periodo()
        self.panel.set_preparando(True)
        self.panel.set_periodo_estado(False)
        self._trabajo_periodo = Trabajo(periodos.preparar, p, parent=self)
        self._trabajo_periodo.progreso.connect(self.panel.set_progreso_periodo)
        self._trabajo_periodo.fallo.connect(self._periodo_fallido)
        self._trabajo_periodo.finished.connect(self._fin_preparar)
        self._trabajo_periodo.start()

    def _periodo_fallido(self, mensaje):
        if "cancelado" not in mensaje:
            log.error(f"No se pudo preparar el periodo: {mensaje}")
            self.mapa.aviso("No se pudo preparar el periodo", "fallo")

    def _fin_preparar(self):
        from teodors.operacion import periodos
        self._trabajo_periodo = None
        self.panel.set_preparando(False)
        p = self.panel.periodo()
        if p is not None:
            self.panel.set_periodo_estado(periodos.listo(p))

    def _ver_viento_periodo(self):
        p = self.panel.periodo()
        if p is not None:
            self._cargar_viento(p["ini"], p["serie"], p["dias"])

    # ── el visor 3D: en la zona central, con el mismo reproductor ────────────────────────
    def _hora_reproductor(self, h, f):
        if self._en_3d:
            self.vista3d.hora(h, f)
        else:
            self.mapa.viento_hora(h, f)
            self.mapa.penacho_hora(h, f)

    def _pagina_cambiada(self, clave):
        from teodors.gui import penacho_3d
        if clave == "visor3d":
            self.panel.set_penachos(penacho_3d.lista())
        self._mostrar_3d(clave == "visor3d" and self._3d_horas is not None)

    def _mostrar_3d(self, si):
        """Del mapa al visor y al revés. El reproductor toma las horas del penacho abierto y, al volver, las del mapa."""
        if si == self._en_3d:
            return
        self._en_3d = si
        self.panel.btn_play.setChecked(False)
        if si:
            self._horas_mapa = self.panel.horas_reproductor()
            self._central.setCurrentWidget(self.vista3d)
            self.panel.set_viento_listo(self._3d_horas)
        else:
            self._central.setCurrentWidget(self.mapa)
            if self._horas_mapa:
                self.panel.set_viento_listo(self._horas_mapa)
            else:
                self.panel.ocultar_reproductor()

    def _ver_3d(self):
        """Abre el penacho elegido en el visor o, si aún no está, lanza el motor (gui/penacho_3d.py); mientras, el botón lo cancela."""
        from teodors.gui import penacho_3d
        if self._trabajo_3d is not None:
            self._trabajo_3d.cancelar()
            return
        elegido = self.panel.penacho_elegido()
        if elegido is None:
            return
        abierto = penacho_3d.abrir(*elegido)
        if abierto is not None:
            self._abrir_3d(abierto)
            return
        self.panel.set_calculando_3d(True)
        self._trabajo_3d = Trabajo(penacho_3d.calcular, *elegido, parent=self)
        self._trabajo_3d.progreso.connect(self.panel.set_progreso_3d)
        self._trabajo_3d.hecho.connect(self._abrir_3d)
        self._trabajo_3d.fallo.connect(self._3d_fallido)
        self._trabajo_3d.finished.connect(self._fin_3d)
        self._trabajo_3d.start()

    def _abrir_3d(self, r):
        from teodors.gui import penacho_3d
        if self.vista3d is None:
            from teodors.gui.vista_3d import Vista3D
            self.vista3d = Vista3D()
            self._central.addWidget(self.vista3d)
        self.panel.set_penachos(penacho_3d.lista())
        self._3d_horas = r["horas"]
        self.vista3d.poner(r["pagina"])
        if self._en_3d:
            self.panel.set_viento_listo(self._3d_horas)
        elif self.panel._pila.currentWidget() is self.panel._paginas["visor3d"]:
            self._mostrar_3d(True)

    def _3d_fallido(self, mensaje):
        if "cancelado" not in mensaje:
            log.error(f"No se pudo calcular en 3D: {mensaje}")
            self._fallo_3d = mensaje

    def _fin_3d(self):
        self._trabajo_3d = None
        self.panel.set_calculando_3d(False)
        if self._fallo_3d:
            self.panel.set_fallo_3d(self._fallo_3d)
            self._fallo_3d = None

    # ── varios ───────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _abrir(carpeta):
        carpeta.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(carpeta)))

    def _acerca_de(self):
        QtWidgets.QMessageBox.about(
            self, "Acerca de",
            f"<h3>{config.APP_NOMBRE}</h3><p>Versión {config.pide('identidad', 'version')} · {config.pide('identidad', 'entidad')}</p>"
            "<p><b>Fuentes de datos y licencias</b></p><ul>"
            + "".join(f"<li>{c}</li>" for c in config.pide("fuentes", "creditos")) +
            "<li>Leaflet (BSD-2), folium (MIT), pyproj (MIT)</li>"
            "<li>Qt / PySide6 (LGPL v3)</li></ul>")
