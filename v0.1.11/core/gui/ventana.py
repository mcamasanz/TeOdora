# -*- coding: utf-8 -*-
"""Ventana principal: barra superior, panel (izquierda), mapa con su reproductor de tiempo (centro) y
registro de actividad (abajo, oculto al principio).

El mapa es la zona central y siempre rellena el espacio libre. Panel y actividad son
QDockWidget: se mueven a cualquier borde, se sacan a ventana flotante (p. ej. a otro
monitor) y se ocultan; se vuelven a mostrar con Ctrl+1, 2 y 3 (actividad y terminal, también desde el
riel del panel). La app no tiene menú (usuario, 2026-11-07). «Solo mapa» (F11) deja el
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
import html
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from teodors import planta as config
from teodors.casos import receptores as receptores_mapa
from teodors.comun import registro
from teodors.comun.formato import km as _km, num as _num
from teodors.fuentes import catastro as edificios, meteocat as estaciones, terreno
from teodors.gui import mapa_web, tema, widgets
from teodors.gui.barra_mapa import BarraMapa, imagen_con_titulo
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
    ESPERA_COMPROBAR_MS = 2000                   # de la ventana a la vista a la comprobación automática de la herramienta

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
        # la barra de encima del mapa (usuario, 2026-11-17): en Simular, con lo simulado o la comparación a la vista (`_poner_barra`)
        self._escala_mapa, self._rango_mapa, self._opacidad_mapa = "log", None, penacho_mapa.OPACIDAD
        self._rangos_vista, self._titulos_capa = {}, {}   # el rango con el que se pintó cada capa y su título (la imagen)
        self._leyenda_mapa = True                          # la leyenda, a la vista en el mapa (la barra la puede ocultar)
        # el peor punto de cada pueblo, el de su tabla (usuario, 2026-11-17): {columna: [...]}, lo último enviado al mapa y la columna de
        # las fichas de los núcleos
        self._peores, self._peores_mapa, self._col_nucleos = {}, None, None
        self.barra_mapa = BarraMapa(self._opacidad_mapa)
        self.barra_mapa.setVisible(False)
        v.addWidget(self.barra_mapa)
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

        self._atajos()
        self._comandos_terminal()
        self.setMenuWidget(self._barra_app())

        self.panel.verTerreno.connect(self.mapa.centrar)
        self.panel.verPlanta.connect(self.mapa.ver_planta)
        self.panel.descargarTerreno.connect(self._descargar_terreno)
        self.panel.descargarEdificios.connect(self._descargar_edificios)
        self.panel.importarEdificios.connect(self._importar_edificios)
        self.panel.editarEdificios.connect(self._editar_edificios)
        self.panel.horizonteMeteo.connect(self._horizonte_meteo)
        self.panel.vientoDia.connect(self._cargar_viento)
        self.panel.vientoHora.connect(self._hora_reproductor)
        self.panel.periodoCambiado.connect(self._periodo_cambiado)
        self.panel.prepararPeriodo.connect(self._preparar_periodo)
        self.panel.vientoPeriodo.connect(self._ver_viento_periodo)
        self.panel.simularPeriodo.connect(self._simular_periodo)
        self.panel.simularVientoEpisodio.connect(self._simular_viento_episodio)
        self.panel.cargarVientoEpisodio.connect(self._cargar_viento_episodio)
        self.panel.guardarVientoEpisodio.connect(self._guardar_viento_episodio)
        self.panel.paginaCambiada.connect(self._pagina_cambiada)
        self.mapa.clic.connect(self._clic_mapa)
        self.mapa.estacion.connect(self._clic_estacion)
        self.panel.verCapa.connect(self.mapa.ver_capa)                 # botones «Ver …»
        self.panel.verFocos.connect(self._ver_focos)
        self.panel.verPlanes.connect(self._ver_planes)
        self.panel.simular.connect(self._simular)
        self.panel.cancelarSimulacion.connect(self._cancelar_simulacion)
        self.panel.guardarResultados.connect(self._guardar_resultados)
        self.panel.informeComparacion.connect(self._informe_comparacion)
        self.panel.cargarResultados.connect(self._cargar_resultados)
        self.panel.estiloCapas.connect(lambda _: self._repintar_capas())
        self.panel.modoReanalisis.connect(self._modo_reanalisis)
        self.panel.compararEscenarios.connect(self._comparar)
        self.panel.cargarEscenario.connect(self._cargar_escenario)
        self.panel.magnitudComparada.connect(lambda _: self._poner_comparacion(self.panel.capa_encendida(self._ids_comparacion())))
        self.panel.magnitudElegida.connect(self._ver_magnitud)
        self.panel.ver3d.connect(self._ver_3d)
        self.panel.tituloPagina.connect(self._titulo_panel.lbl.setText)
        self.panel.verAjustes.connect(self._ver_ajustes)
        self.panel.comprobar.connect(self._comprobar)
        self.panel.verAyuda.connect(self._ver_ayuda)
        self.panel.verActividad.connect(lambda: self._alternar(self.dock_consola))
        self.panel.verTerminal.connect(lambda: self._alternar(self.dock_terminal))
        self.mapa.capa.connect(self.panel.set_capa_visible)            # y al revés, del selector
        self.mapa.capa.connect(self._capa_en_mapa)                      # y la barra de encima del mapa
        b = self.barra_mapa
        b.variable.connect(lambda i: self.mapa.ver_capa(i, True))
        b.estilo.connect(self.panel.elegir_estilo)
        b.escala.connect(self._escala_elegida)
        b.rango.connect(self._rango_elegido)
        b.paleta.connect(self._paleta_elegida)
        b.leyenda.connect(lambda _: self._poner_leyenda())
        b.opacidad.connect(self._opacidad_elegida)
        b.encuadre.connect(self._encuadrar)
        b.copiar.connect(lambda: self._imagen_mapa(copiar=True))
        b.guardar.connect(lambda: self._imagen_mapa(copiar=False))
        self.mapa.listo.connect(self._mapa_listo)
        self.mapa.formaViento.connect(self._forma_viento)

        self.terreno_info = None
        self._terreno_arr = None
        self._resumen = None
        self._trabajo = None
        self.edif_info, self._edif, self._edif_todos = None, None, None
        self._trabajo_edif = None
        self._trabajo_orto = None                # la ortofoto del plano de focos, la primera vez
        self._rosas, self._trabajo_rosas = None, None
        self._nombres, self._trabajo_nombres = {}, None    # nombre de cada núcleo
        self._trabajo_viento = None
        self._resumen_planta, self._trabajo_resumen = {}, None     # el viento de cada día en la planta, por serie (calendario)
        self._trabajo_comprobar = None
        self._trabajo_episodio, self._periodo_episodio = None, None   # el viento del episodio (modo queja)
        self._episodio_sin_guardar, self._horizonte_prev = False, None   # para avisar al cambiar de horizonte
        self._revirtiendo_horizonte = False                              # reentrada al volver al modo anterior tras Cancelar
        self._episodio_cancelado = False                                 # el viento del episodio se canceló: borrar tmp, no post-procesar
        self._rosas_dia = None                   # rosas de lo medido el día cargado en Reanálisis
        self._rosas_episodio = None              # rosas de lo medido en los días del Episodio/Predicción
        self._dia_viento = None                  # el día del viento que hay en el mapa
        self._animar_al_cargar = False
        self._ventana_focos = None
        self._ventana_planes = None
        self._ventana_ajustes = None
        self._editor_edificios = None
        tema.avisos.cambiado.connect(self._pinta_acciones)
        self._trabajo_sim, self._magnitud = None, None
        self._trabajo_archivo = None             # guardando o cargando unos resultados
        self._resultados_visibles = False        # lo simulado, en el mapa: solo en la página de Simular
        self._encendida_oculta = None            # la capa que se veía al salir de Simular
        self._comparacion, self._trabajo_comp = None, None      # la comparación de dos escenarios del reanálisis
        self._comparacion_visible, self._comp_oculta = False, None
        self._casos_otros = []                   # casos guardados fuera de su carpeta, abiertos para comparar
        self._resultados = {"anios": None, "periodo": None}      # lo simulado: los años del reanálisis, y un día, el episodio o la predicción
        self._valores = {}                       # los valores de cada resultado en cada receptor, para los tooltips
        self._trabajo_periodo, self._trabajo_3d, self._fallo_3d = None, None, None
        self.vista3d, self._en_3d, self._3d_horas, self._horas_mapa = None, False, None, None
        self._mensajes_arranque()
        self._cargar_focos()
        self._actualizar_planes()
        self._cargar_terreno_guardado()
        self._cargar_edificios_guardados()
        self._pinta_edificios_planta()
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

    def _atajos(self):
        """Los atajos de teclado, en la ventana. La app no tiene menú (usuario, 2026-11-07: no aportaba nada): lo que solo
        estaba en él se quitó, y su «Acerca de» va en el botón «Ayuda» del riel."""
        def atajo(texto, tecla, hacer=None):
            a = QtGui.QAction(texto, self)
            a.setShortcut(QtGui.QKeySequence(tecla))
            if hacer is not None:
                a.triggered.connect(hacer)
            self.addAction(a)
            return a

        self.acc_focos = atajo(self._texto_focos(), "Ctrl+Shift+F", self._ver_focos)
        atajo("Planes de operación…", "Ctrl+Shift+P", self._ver_planes)
        for i, dock in enumerate(self._docks, 1):         # el panel, la actividad y la terminal
            accion = dock.toggleViewAction()
            accion.setShortcut(QtGui.QKeySequence(f"Ctrl+{i}"))
            self.addAction(accion)
        self.acc_solo_mapa = atajo("Solo mapa", "F11")    # y el botón de la barra superior
        self.acc_solo_mapa.setCheckable(True)
        self._pinta_acciones()
        self.acc_solo_mapa.setToolTip("Solo mapa")
        self.acc_solo_mapa.toggled.connect(self._solo_mapa)
        atajo("Recargar mapa", "F5", lambda: self.mapa.cargar(self.emp, self._limites()))
        atajo("Configuración…", "Ctrl+,", self._ver_ajustes)

    def _barra_app(self):
        """Barra superior: la marca, la hora y «Solo mapa». La configuración y la ayuda, en el riel del panel (usuario, 2026-11-06)."""
        w = QtWidgets.QWidget(objectName="barra_app")
        w.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(14, 8, 10, 8)
        h.setSpacing(10)
        marca = QtWidgets.QLabel(objectName="marca")
        marca.setFixedSize(36, 36)
        marca.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        propio = tema.icono_planta()
        if propio is not None:                   # el de la planta, tal cual: sin el fondo del acento
            marca.setObjectName("marca_planta")
            marca.setPixmap(propio.pixmap(QtCore.QSize(36, 36), self.devicePixelRatioF()))
        else:
            tema.pon_icono(marca, "logo", "sobre_acento", 24)
        h.addWidget(marca)
        h.addWidget(QtWidgets.QLabel(config.APP_NOMBRE.split(" · ")[0], objectName="app_titulo"))
        # mientras dura la sesión del administrador (`_poner_admin`), con su nombre
        normal, admin = self._usuarios()
        self._lbl_admin = QtWidgets.QLabel(admin[1], objectName="admin_marca")
        self._lbl_admin.setToolTip(f"Usuario {admin[1]}")
        self._lbl_admin.setVisible(config.MODO_EDICION)
        h.addWidget(self._lbl_admin)
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
        # usuario, 2026-11-09: «siempre que se abra la app, que se lleve a cabo la comprobación de la herramienta de forma automática».
        # Con la ventana ya a la vista, para no retrasar el arranque; una vez por apertura (esto solo corre al mostrarse la primera vez)
        QtCore.QTimer.singleShot(self.ESPERA_COMPROBAR_MS, lambda: self._comprobar(al_abrir=True))

    @staticmethod
    def _alternar(dock):
        """Abre un panel de abajo, delante del otro si están los dos, o lo cierra. Tapado por la otra pestaña,
        Qt lo da por visible: lo que cuenta es si se ve algo de él."""
        if dock.isVisible() and not dock.visibleRegion().isEmpty():
            dock.hide()
        else:
            dock.show()
            dock.raise_()

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
            if not widgets.preguntar_si(self, "Descarga en curso", "Hay una descarga en curso. ¿Cancelarla y salir?"):
                evento.ignore()
                return
        # Cerrar la principal cierra la app: si no, seguiría viva con las otras ventanas. Cada una pregunta si tiene cambios
        # sin guardar y, si se cancela, la principal sigue abierta y no se cancela ningún trabajo.
        for v in (self._ventana_focos, self._ventana_planes, self._ventana_ajustes, self._editor_edificios):
            if v is not None and (pregunta_abierta(v) or not v.close()):
                evento.ignore()
                return
        for t in en_curso:
            t.cancelar()
            if not t.wait(20000):
                log.warning("La descarga no terminó a tiempo; se cierra igualmente.")
        if self._trabajo_rosas is not None and self._trabajo_rosas.isRunning():
            self._trabajo_rosas.wait(15000)          # cálculo corto: se espera sin preguntar
        for t in (self._trabajo_sim, self._trabajo_3d, self._trabajo_periodo, self._trabajo_comprobar, self._trabajo_archivo, self._trabajo_comp):
            if t is not None and t.isRunning():      # la comprobación, también: con la automática, se puede cerrar con ella en marcha
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
        self._leyenda_mapa = True                    # la página empieza con la leyenda a la vista
        self._poner_leyenda()
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

    def _comprobar(self, al_abrir=False):
        """Comprobar la herramienta (`operacion.comprobar`), en segundo plano: cada prueba se marca en Inicio al acabar y su mensaje va a la
        actividad, que se abre. Mientras, el botón la cancela. Al abrir la app se hace sola (`_disposicion_inicial`) y sin abrir la
        actividad, que solo sale si algo falla: entonces hace falta el detalle y qué hacer."""
        import json
        from teodors.operacion import comprobar
        if self._trabajo_comprobar is not None and self._trabajo_comprobar.isRunning():
            if not al_abrir:
                self._trabajo_comprobar.cancelar()
            return

        def correr(progreso=None, cancelado=None):
            return comprobar.ejecutar(progreso=lambda k, n, r: progreso(int(100 * k / max(n, 1)), json.dumps(r)), cancelado=cancelado)

        if al_abrir:
            log.info("Comprobando la herramienta, como cada vez que se abre la app…")
        else:
            self.dock_consola.show()
        self.panel.set_comprobando(True)
        t = Trabajo(correr, parent=self)
        t.progreso.connect(lambda pct, r: self.panel.set_prueba(pct, json.loads(r)))
        t.hecho.connect(self.panel.fin_comprobacion)
        if al_abrir:
            t.hecho.connect(lambda r: self.dock_consola.show() if any(
                c.get("estado") == comprobar.FALLO for c in (r or {}).get("categorias", {}).values()) else None)
        t.fallo.connect(lambda m: (log.error(f"No se pudo comprobar la herramienta: {m}"), self.panel.fin_comprobacion(None)))
        self._trabajo_comprobar = t
        t.start()

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
        modo = self.panel.horizonte_meteo()
        rean = modo == "reanalisis"
        epi = modo in ("queja", "prediccion")
        rosas = (self._rosas or {}).get("estaciones", {}) if rean else {}
        dia = (self._rosas_dia or {}) if rean else {}
        rosas_ep = (self._rosas_episodio or {}) if epi else {}       # rosa de lo medido en los días del episodio/predicción
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
            re = rosas_ep.get("estaciones", {}).get(e["codigo"])
            if re:                                                   # episodio/predicción: la rosa de sus días
                i0, i1 = rosas_ep["ini"], rosas_ep["fin"]
                etiq = f"{i0[8:10]}/{i0[5:7]}–{i1[8:10]}/{i1[5:7]}/{i1[:4]}" if i1 != i0 else f"{i0[8:10]}/{i0[5:7]}/{i0[:4]}"
                bloques.append((f"{etiq} ({_num(re['horas'])} h medidas)", re))
                altura, clases = re["altura_m"], rosas_ep["clases"]
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

    def _que_se_pierde(self, modo):
        """Qué se perdería al SALIR de `modo` (texto para el aviso, función de guardar), o (None, None) si no hay nada que perder.
        Avisa en los dos sentidos: con resultados de reanálisis simulados o cargados, o con el viento/penacho de un episodio o predicción."""
        if modo == "reanalisis" and self._resultados.get("anios") is not None:
            return "los resultados del reanálisis", self._guardar_resultados
        if modo in ("queja", "prediccion"):
            hay_viento = self._periodo_episodio is not None and self._episodio_sin_guardar
            hay_dispersion = self._resultados.get("periodo") is not None
            nom = "episodio" if modo == "queja" else "predicción"
            if hay_dispersion:                                       # hay penacho: «Guardar» guarda el CASO (dispersión), no solo el viento
                return f"la simulación de {nom} (el penacho animado)", self._guardar_resultados
            if hay_viento:
                return f"el viento del {nom}", self._guardar_viento_episodio
        return None, None

    def _horizonte_meteo(self, clave):
        """Cambio de opción en Meteorología: lo simulado era con la anterior."""
        from teodors.operacion import periodos
        if self._revirtiendo_horizonte:                  # reentrada tras Cancelar: solo recoloca el radio, no toca el estado
            self._revirtiendo_horizonte = False
            return
        # guarda en AMBOS sentidos: salir de un modo con resultados (simulados o cargados) lo REINICIA y los pierde
        prev = self._horizonte_prev
        perder, guardar = self._que_se_pierde(prev)
        if prev is not None and clave != prev and perder is not None:
            from PySide6 import QtWidgets
            box = QtWidgets.QMessageBox(self)
            box.setIcon(QtWidgets.QMessageBox.Icon.Question)
            box.setWindowTitle("Datos sin guardar")
            box.setText(f"Si cambias de modo se reinicia y perderás {perder}.\n"
                        "¿Quieres guardarlos antes de cambiar?")
            Rol = QtWidgets.QMessageBox.ButtonRole
            b_guardar = box.addButton("Guardar", Rol.AcceptRole)          # botones en español (los estándar de Qt salen en inglés)
            box.addButton("Descartar", Rol.DestructiveRole)
            b_cancelar = box.addButton("Cancelar", Rol.RejectRole)
            box.setDefaultButton(b_guardar)
            box.exec()
            clic = box.clickedButton()
            if clic is b_cancelar:
                self._revirtiendo_horizonte = True
                self.panel.set_horizonte_meteo(prev)     # cancelar: vuelve al modo anterior, no se pierde nada
                return
            if clic is b_guardar and guardar is not None:
                guardar()
            self._episodio_sin_guardar = False
        self._horizonte_prev = clave
        self.panel.mostrar_viento(clave == "reanalisis")
        self.panel.mostrar_periodo(clave)
        self.panel.mostrar_episodio(clave == "queja")
        self.mapa.quitar_viento()
        self.panel.ocultar_reproductor()                 # al cambiar de modo, fuera la animación (no hay viento cargado)
        if clave != "queja":                             # salir de Episodio: olvida su viento (se recarga con «Cargar viento»)
            self._periodo_episodio, self._episodio_sin_guardar = None, False
        self._dia_viento = None
        self._limpiar_simulacion()
        self._rosas_dia = None
        self._rosas_episodio = None               # se recalcula al ver el viento del episodio/predicción
        if clave in ("reanalisis", "queja", "prediccion"):
            self.panel.ir_a("meteo")
        if clave in periodos.DIAS:
            self._periodo_cambiado()
        if clave != "reanalisis":
            self._pintar_estaciones()
            return
        self._serie_viento = viento_mapa.serie_disponible()
        self.panel.set_viento_dias(viento_mapa.rango_dias(self._serie_viento) if self._serie_viento else None,
                                   viento_mapa.dia_inicial(self._serie_viento) if self._serie_viento else None)
        self._resumen_viento()
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

    def _resumen_viento(self):
        """El viento de cada día en la planta, para pintar el calendario de Meteorología (`viento_mapa.resumen_planta`). En segundo plano:
        la primera vez lee un mes por segundo; luego sale de la caché de LOCAL."""
        serie = self._serie_viento
        if serie is None:
            return
        if self._resumen_planta.get(serie) is not None:
            self.panel.set_resumen_viento(self._resumen_planta[serie])
            return
        if self._trabajo_resumen is not None and self._trabajo_resumen.isRunning():
            return

        def resumen(serie, progreso=None):
            datos = viento_mapa.serie_planta(serie, progreso=lambda k, n: progreso(int(100 * k / n), f"{k} de {n} meses"))
            return {"serie": serie, "resumen": viento_mapa.resumen_planta(datos)}

        def hecho(r):
            self._resumen_planta[r["serie"]] = r["resumen"]
            if r["serie"] == self._serie_viento:
                self.panel.set_resumen_viento(r["resumen"])

        def fallo(m):
            log.warning(f"No se pudo leer el viento de cada día en la planta: {m}")
            self.panel.set_resumen_viento(None)

        t = Trabajo(resumen, serie, parent=self)
        t.progreso.connect(self.panel.set_progreso_resumen)
        t.hecho.connect(hecho)
        t.fallo.connect(fallo)
        self._trabajo_resumen = t
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
        self.panel.set_viento_planta(d["horas"], d.get("planta"))
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
        """Iconos de los núcleos (pueblos, industria, deportivos) y de los pueblos que añade la planta (planta.json, «pueblos»: el mapa de
        usos no los tiene como núcleo; usuario, 2026-11-10). Tras simular un plan, el tooltip lleva la tabla de media, máximo y P98: la de un pueblo, la de su
        fila de la tabla (lo peor de sus receptores); la de lo demás, la de su punto."""
        vis = self._capa_visible()
        self._col_nucleos = vis[0] if vis else None
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
            texto += self._tabla_plan(n["x"], n["y"], pob if n["familia"] == "residencial" else None)
            if n["familia"] == "residencial":
                texto += self._linea_peor(pob, n["lat"], n["lon"])
            lista.append({"familia": n["familia"], "lat": n["lat"], "lon": n["lon"], "texto": texto})
        # los pueblos que añade la planta: el mapa de usos no los tiene como núcleo
        from teodors.operacion import pueblos
        for p in pueblos.centros():
            d, rumbo = geo.distancia_rumbo(self.emp["lat"], self.emp["lon"], p["lat"], p["lon"])
            texto = (f"<b style='font-size:13px'>{p['nombre']}</b>"
                     + (f" ({p['municipio']})" if p.get("municipio") and p["municipio"] != p["nombre"] else "") + "<br>"
                     + f"<b>Pueblo</b> (de la planta: el mapa de usos no lo tiene como núcleo)<br>{_num(p['ha'])} ha · a "
                     f"{_num(d / 1000, 1)} km al {rumbo} de la planta")
            texto += self._tabla_plan(p["x"], p["y"], p["nombre"]) + self._linea_peor(p["nombre"], p["lat"], p["lon"])
            lista.append({"familia": "residencial", "lat": p["lat"], "lon": p["lon"], "texto": texto})
        # los receptores con nombre: el uso del suelo no los ve
        for r in receptores_mapa.con_nombre():
            lat, lon = geo.a_geo(r["x"], r["y"])
            lista.append({"familia": "industrial", "lat": lat, "lon": lon,
                          "texto": f"<b style='font-size:13px'>{r['nombre']}</b>" + self._tabla_plan(r["x"], r["y"])})
        self.mapa.set_nucleos(lista)

    def _tabla_plan(self, x, y, pueblo=None):
        """Valores de lo simulado en ese receptor, para su tooltip: los años del reanálisis y el día, el episodio o la predicción. De un
        `pueblo`, los de su fila de la tabla del resultado, si la tiene: lo peor de sus receptores (operacion.pueblos), como en la tabla."""
        from teodors.operacion import simulacion as planes_calculo, periodos
        punto = (round(float(x), 1), round(float(y), 1))
        salen = ""
        if not self._resultados_visibles:
            return salen
        for cual, valores in self._valores.items():
            r = self._resultados.get(cual)
            if not r:
                continue
            m = r["magnitudes"][self._magnitud]
            fila = next((f for f in m.get("filas", []) if pueblo and f.get("tipo") == "pueblo" and f["nombre"] == pueblo), None)
            v = fila or valores.get(punto)
            if v:
                tramo = periodos.etiqueta(r["periodo"]) if r["periodo"] else texto_anios()
                salen += planes_calculo.tabla_punto(v, f"Plan «{r['nombre']}» · {tramo}" + (" · lo peor del pueblo" if fila else ""), m)
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
        huellas = []                                 # para el plano de la página Focos: las huellas de los edificios cercanos
        for g in (self._edif.geometry if self._edif is not None else []):
            huellas += [list(pol.exterior.coords) for pol in getattr(g, "geoms", [g]) if hasattr(pol, "exterior")]
        self.panel.set_huellas(huellas)
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
    # ── los edificios de la planta (usuario, 2026-11-08: tres caminos, los descargados, el LiDAR y dibujar o modificar, el administrador) ──
    def _pinta_edificios_planta(self):
        from teodors.operacion import edificios_planta as EP
        try:
            datos = EP.cargar()
            self.panel.set_edificios_planta(EP.resumen(datos), datos["edificios"])
        except (ValueError, OSError) as e:
            log.warning(f"No se pueden leer los edificios de la planta: {e}")

    def _importar_edificios(self, origen):
        """De los descargados o del LiDAR (solo el administrador): sustituyen a los que vinieran de esos dos caminos; los dibujados se quedan.
        Se guardan y se rehace la estela de los focos punto."""
        from teodors.operacion import edificios_planta as EP
        if not config.MODO_EDICION:
            return
        nombre = EP.nombre_origen(origen)
        try:
            datos = EP.cargar()
        except (ValueError, OSError) as e:
            log.error(f"No se pueden leer los edificios de la planta: {e}")
            return
        a_mano = sum(e.get("origen") == "dibujo" for e in datos["edificios"])
        if not widgets.preguntar_si(
                self, f"Edificios: {nombre}", f"¿Traer los edificios ({nombre}) alrededor de la planta?\nSustituyen a los de "
                f"{EP.nombre_origen('catastro')} y del LiDAR que haya" + (f"; los {a_mano} dibujados se quedan." if a_mano else ".")):
            return
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            nuevos = EP.desde_catastro() if origen == "catastro" else EP.desde_lidar()
            datos = EP.importar(datos, nuevos)
            EP.guardar(datos)
            cambiados = EP.recalcular_focos()
        except (ValueError, OSError) as e:
            log.error(f"No se pudieron traer los edificios ({nombre}): {e}")
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        log.info(f"Edificios de la planta: {len(nuevos)} ({nombre}); en total, {len(datos['edificios'])}."
                 + (f" Cambia la estela de {len(cambiados)} foco(s)." if cambiados else ""))
        self._edificios_cambiados(cambiados)

    def _editar_edificios(self):
        """El editor de los edificios de la planta (solo el administrador); uno solo: si está abierto, delante."""
        if not config.MODO_EDICION:
            return
        if self._editor_edificios is not None and self._editor_edificios.isVisible():
            self._editor_edificios.raise_()
            self._editor_edificios.activateWindow()
            return
        from teodors.gui.editor_edificios import EditorEdificios
        self._editor_edificios = EditorEdificios(self.emp, self.ajustes)
        self._editor_edificios.guardado.connect(self._edificios_cambiados)
        self._editor_edificios.show()

    def _edificios_cambiados(self, focos_cambiados):
        """Los edificios de la planta se han guardado (en su carpeta, `edificios_planta.json`: los tendrá al volver a abrir). En esta
        misma sesión (usuario, 2026-11-08): la página Planta con su 3D, la ventana de los focos y el panel 3D del editor de focos abierto; y
        los focos de la página Focos, si alguno ha cambiado de estela."""
        self._pinta_edificios_planta()
        if self._ventana_focos is not None:
            self._ventana_focos.edificios_cambiados()
        if focos_cambiados:
            self._cargar_focos()

    def _cargar_focos(self):
        from teodors.operacion import focos
        try:
            datos = focos.cargar()
        except (ValueError, OSError) as e:
            log.error(f"No se pudieron leer los focos ({config.FOCOS_JSON.name}): {e}")
            datos = None
        self.panel.set_focos(datos)
        if self._ventana_planes is not None:              # la operación, con los focos de ahora: uno nuevo, con la suya por defecto
            self._ventana_planes.focos_cambiados()
        if datos and datos["focos"]:
            log.info(f"Focos de emisión: {len(datos['focos'])}")
            self._ortofoto_focos(datos)

    def _ortofoto_focos(self, datos):
        """La ortofoto bajo el plano de la página Focos (usuario, 2026-11-08): la guardada con la planta o, si no cubre los focos, se pide
        una vez, en segundo plano. Sin ella, el plano lleva las huellas de los edificios."""
        from teodors.fuentes import ortofoto
        g = ortofoto.vigente(datos)
        if g is not None:
            self.panel.set_ortofoto(g)
            return
        if (ortofoto.fondo() is None or ortofoto.recuadros(datos) is None                  # sin fondos o sin focos ubicados
                or (self._trabajo_orto is not None and self._trabajo_orto.isRunning())):
            return
        log.info("Pidiendo la ortofoto del plano de focos (solo la primera vez)…")
        t = Trabajo(ortofoto.para_focos, datos, parent=self)
        t.hecho.connect(self.panel.set_ortofoto)
        t.fallo.connect(lambda m: log.warning(f"Sin la ortofoto del plano de focos: {m}"))
        self._trabajo_orto = t
        t.start()

    # ── usuarios: normal y administrador (usuario, 2026-11-08) ──────────────────────────────────────────────────────
    def _texto_focos(self):
        return "Focos de emisión…" + (f" ({config.pide('operacion', 'texto_modo_edicion')})" if config.MODO_EDICION else "")

    @staticmethod
    def _usuarios():
        """((comando, nombre) del usuario normal, (comando, nombre) del administrador), de planta.json: `operacion.usuario` y
        `texto_usuario`; `operacion.modo_edicion` y `texto_modo_edicion`."""
        op = config.bloque("operacion")
        return ((op.get("usuario", "normal"), op.get("texto_usuario", "normal")),
                (config.CLAVE_EDICION, config.pide("operacion", "texto_modo_edicion")))

    def _comandos_terminal(self):
        """Los comandos de la terminal. Ocultos (empiezan por «_» y no salen en `ayuda`): el de cada usuario, «_» y su comando en planta.json,
        que cambia a él (al administrador, con su contraseña), y `_clave`. El administrador tiene los permisos del antiguo modo de edición: añadir, quitar y cambiar focos."""
        from teodors.operacion import administrador
        t = self.terminal
        self._puerta = administrador.Puerta()
        (c_normal, n_normal), (c_admin, n_admin) = self._usuarios()

        def ayuda():
            return "Comandos: " + " · ".join(t.visibles())

        def admin():
            if config.MODO_EDICION:
                return f"Ya eres el usuario {n_admin}."
            if not administrador.hay_clave():
                return "Esta planta no tiene contraseña de administrador: la pone soporte (python -m teodors.operacion.administrador --clave)."
            espera = self._puerta.espera()
            if espera:
                return f"Demasiados intentos fallidos: espera {espera:.0f} s."
            t.pedir_clave(f"Contraseña del usuario {n_admin}:", self._clave_admin)
            return None

        def normal():
            if not config.MODO_EDICION:
                return f"Ya eres el usuario {n_normal}."
            return self._poner_admin(False) or f"Usuario {n_normal}."

        def clave():
            if not config.MODO_EDICION:
                return "Solo el administrador puede cambiar la contraseña."

            def segunda(nueva):
                def guardar(otra):
                    if otra != nueva:
                        return "No coinciden: no se ha cambiado nada."
                    try:
                        administrador.poner_clave(nueva)
                    except ValueError as e:
                        return f"No se ha cambiado: {e}."
                    log.info("Contraseña de administrador cambiada.")
                    return "Contraseña cambiada."
                t.pedir_clave("Otra vez:", guardar)
            t.pedir_clave("Contraseña nueva:", segunda)
            return None

        t.registrar("ayuda", ayuda)
        t.registrar("usuario", lambda: n_admin if config.MODO_EDICION else n_normal)
        for nombre, f in ((c_admin, admin), (c_normal, normal), ("clave", clave)):
            t.registrar(t.OCULTO + nombre, f)

    def _clave_admin(self, clave):
        if self._puerta.abrir(clave):
            return self._poner_admin(True) or f"Usuario {self._usuarios()[1][1]}."
        log.warning("Intento fallido de cambiar al usuario administrador.")
        espera = self._puerta.espera()
        return "Contraseña incorrecta." + (f" Demasiados intentos: espera {espera:.0f} s." if espera else "")

    def _poner_admin(self, activo):
        """Cambia de usuario. La ventana de los focos se rehace con los permisos nuevos: si está abierta, primero hay que cerrarla. Devuelve
        un texto si no se ha podido."""
        if self._ventana_focos is not None and self._ventana_focos.isVisible():
            return "Cierra antes la ventana de los focos."
        if self._ventana_focos is not None:
            self._ventana_focos.deleteLater()
            self._ventana_focos = None
        config.actual().MODO_EDICION = activo
        self.panel.set_admin(activo)
        self.acc_focos.setText(self._texto_focos())
        self._lbl_admin.setVisible(activo)
        log.info(f"Usuario {self._usuarios()[1 if activo else 0][1]}.")
        return None

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
            self._ventana_ajustes.escalasCambiadas.connect(lambda: self.barra_mapa.poner_paleta(tema.preferencia("escala_olor")))
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
        """Simula en segundo plano, siempre: aunque ya esté simulado con lo mismo (usuario, 2026-11-10: «si el usuario pide que lo vuelva a
        simular, lo vuelve a simular»). Lo ya simulado se ve sin calcular en «Comparar escenarios» y al cargar un caso guardado."""
        from teodors.operacion import simulacion as planes_calculo
        if self._trabajo_sim is not None:
            return
        esc, catalogo = self._leer_plan(ruta)
        if esc is None:
            return
        self._limpiar_simulacion(periodo is not None)
        self.panel.set_simulando(True, periodo is not None)
        log.info(f"Simulando el plan «{esc['nombre']}»…")
        if periodo is None:
            self._trabajo_sim = Trabajo(planes_calculo.calcular, esc, catalogo, parent=self)
        else:                                                        # episodio/predicción: calcula las respuestas (puff) si faltan y luego los estadísticos + penacho
            self._trabajo_sim = Trabajo(planes_calculo.calcular_periodo_preparando, esc, catalogo, periodo, parent=self)
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
        clave = self.panel.magnitud() or r["orden"][0]
        self._poner_magnitud(clave, "penacho" if p else "plan_norma")
        self.mapa.aviso(f"Caso «{r['caso']['nombre']}» cargado" if r.get("caso") else f"Plan «{r['nombre']}» simulado")
        if not p:
            return
        self._restaurar_viento_episodio(r)                           # si su viento 3D no está en tmp (caso cargado tras reiniciar), traerlo de casos/episodios
        if self._dia_viento == (p["ini"], p["dias"]):
            self.panel.animar()
        else:
            self._animar_al_cargar = True
            self._cargar_viento(p["ini"], r["serie"], p["dias"])

    def _restaurar_viento_episodio(self, r):
        """Si el caso es de episodio y su viento 3D no está en tmp (p. ej. se borró al reiniciar), lo recupera de `casos/episodios` para
        poder animarlo. Si el viento no llegó a guardarse, el penacho se ve igual pero sin la animación del viento."""
        p = r.get("periodo")
        if not p or p.get("modo") != "queja":
            return
        from teodors.casos import viento3d as vc
        from teodors.operacion import periodos
        if vc.dir_serie(r["serie"]).is_dir():                        # ya está en tmp
            return
        for v in periodos.vientos_episodio():                        # ¿hay un viento guardado con esa serie?
            if v.get("serie") == r["serie"]:
                try:
                    periodos.cargar_viento(v)                        # lo copia a tmp
                except Exception as e:                               # noqa: BLE001
                    log.warning(f"No se pudo recuperar el viento del episodio al cargar el caso: {e}")
                return

    def _ids_capas(self):
        from teodors.operacion import simulacion as planes_calculo
        return ["penacho"] + [f"{pre}_{c}" for pre in ("plan", "dia") for c in planes_calculo.CAPAS]

    def _poner_magnitud(self, clave, encendida):
        """Lleva al mapa las capas de una magnitud (el olor), con `encendida` a la vista; no se recalcula nada. Con otra escala o rango en la
        barra de encima del mapa, las del resultado que se ve se repintan de su resumen (`simulacion.vista_capa`)."""
        from teodors.operacion import simulacion as planes_calculo, periodos
        self._magnitud = clave
        self._valores, self._peores = {}, {}
        if not self._resultados_visibles:        # fuera de Simular: se pone al volver (`_resultados_segun_pagina`)
            self._encendida_oculta = encendida
            self._pintar_nucleos()
            self._poner_barra()
            return
        actual = "anios" if self.panel.horizonte_meteo() == "reanalisis" else "periodo"
        personal = self._escala_mapa != "log" or self._rango_mapa is not None
        self._rangos_vista = {}
        if personal:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            for cual, r in self._resultados.items():
                if r is None or clave not in r["magnitudes"]:
                    continue
                m = r["magnitudes"][clave]
                prefijo = "dia" if cual == "periodo" else "plan"
                nombre = periodos.etiqueta(r["periodo"]) if r["periodo"] else texto_anios()
                caso = (r.get("caso") or {}).get("nombre") or f"Plan «{r['nombre'] or 'Base'}»"
                hay = set()
                iso = cual in ("anios", "periodo") and self.panel.estilo_capas() == "isolineas"
                for c in m["capas"]:
                    hay.add(c["id"])
                    self._titulos_capa[c["id"]] = f"{caso} · {nombre} · {m['nombre']} · {c['titulo']} ({m['unidad']})"
                    vista = None
                    if personal and cual == actual:
                        try:
                            vista = planes_calculo.vista_capa(r, clave, c, self.panel.estilo_capas(), self._escala_mapa, self._rango_mapa)
                            self._rangos_vista[c["id"]] = vista["rango"]
                        except (OSError, ValueError, KeyError) as e:
                            log.warning(f"No se pudo repintar «{c['titulo']}» con esa escala o rango: {e}")
                    datos = vista["isolineas"] if vista is not None and "isolineas" in vista else (
                        planes_calculo.leer_isolineas(c) if iso and vista is None else None)
                    if datos is not None:
                        self.mapa.set_isolineas(c["id"], f"{nombre} · {c['titulo']}", datos,
                                                vista["leyenda"] if vista is not None else c["isolineas"]["leyenda"],
                                                visible=c["id"] == encendida, opacidad=self._opacidad_mapa, grupo=penacho_mapa.GRUPO,
                                                escala=c["escala"])
                    else:
                        imagenes, leyenda = (vista["imagenes"], vista["leyenda"]) if vista is not None else (c["imagenes"], c["leyenda"])
                        self.mapa.set_imagenes(c["id"], f"{nombre} · {c['titulo']}", imagenes, leyenda, visible=c["id"] == encendida,
                                               opacidad=self._opacidad_mapa, grupo=penacho_mapa.GRUPO, escala=c["escala"])
                    if c["id"] != encendida:
                        self.panel.set_capa_visible(c["id"], False)
                for capa in planes_calculo.CAPAS:
                    if f"{prefijo}_{capa}" not in hay:
                        self.mapa.quitar_capa(f"{prefijo}_{capa}")
                        self.panel.set_capa_visible(f"{prefijo}_{capa}", False)
                if m["penacho"]:
                    self._titulos_capa["penacho"] = f"{caso} · {nombre} · {m['nombre']} · penacho hora a hora"
                    self.mapa.set_penacho(dict(planes_calculo.datos_penacho(r, clave), visible=encendida == "penacho",
                                               opacidad=self._opacidad_mapa))
                    self.mapa.modo_penacho(self.panel.estilo_capas() == "isolineas")   # el penacho sigue el toggle Isolíneas/Degradado, como la media y el máximo
                    q = self.panel.hora_viento.value()
                    self.mapa.penacho_hora(q // 4, (q % 4) / 4)
                self._valores[cual] = planes_calculo.valores(r, clave)
                if cual == actual:
                    self._peores = planes_calculo.peores_puntos(r, clave)
        finally:
            if personal:
                QtWidgets.QApplication.restoreOverrideCursor()
        self._pintar_nucleos()
        self._poner_barra()

    def _ver_magnitud(self, clave):
        """Se ha elegido otra magnitud en el panel (que ya ha puesto sus tablas): sigue a la vista lo mismo (penacho, media, máximo o norma)."""
        if not clave or clave == self._magnitud or not any(self._resultados.values()):
            return
        self._poner_magnitud(clave, self.panel.capa_encendida(self._ids_capas()))

    def _repintar_capas(self):
        """Otro estilo de las capas (isolíneas o degradado) del reanálisis o del episodio: las mismas, con la que se veía a la vista."""
        if self._magnitud is not None and any(self._resultados.values()):
            self._poner_magnitud(self._magnitud, self.panel.capa_encendida(self._ids_capas()))

    # ── la barra de encima del mapa (usuario, 2026-11-17) ────────────────────────────────
    # el lado del cuadrado de cada encuadre, en km; «completa», todo el dominio (usuario: la nave, la zona intermedia y la zona completa)
    ENCUADRE_KM = {"nave": 1.0, "intermedia": 10.0}

    @staticmethod
    def _texto_capa(c):
        """El texto de una capa en la barra: «Media», «Máximo» y, la norma, su título («P98»)."""
        capa = c["id"].split("_", 1)[1]
        return {"media": "Media", "maximo": "Máximo"}.get(capa) or c.get("titulo") or capa

    def _poner_barra(self):
        """La barra de encima del mapa: solo en Simular y con lo simulado o la comparación a la vista. Sus variables, las del resultado que
        se ve (el de la opción de Meteorología); la escala y el rango, solo con la media, el máximo o el P98; «ver como», salvo en la
        comparación (sus franjas son de %)."""
        from teodors.gui.panel import solo_olor
        from teodors.operacion import simulacion as planes_calculo
        b = self.barra_mapa
        lista, m, es_comparacion = [], None, False
        if self.panel.pagina() == "simulacion":
            if self._comparacion_visible and self._comparacion is not None:
                m, es_comparacion = self._comparacion["magnitudes"][solo_olor(self._comparacion)], True
                lista = [(c["id"], self._texto_capa(c)) for c in m["capas"]]
            elif self._resultados_visibles:
                r = self._resultados.get("anios" if self.panel.horizonte_meteo() == "reanalisis" else "periodo")
                if r is not None and self._magnitud in r["magnitudes"]:
                    m = r["magnitudes"][self._magnitud]
                    lista = ([("penacho", "Penacho")] if m.get("penacho") else []) + [(c["id"], self._texto_capa(c)) for c in m["capas"]]
        b.setVisible(bool(lista))
        self._poner_leyenda()
        self._poner_peores()
        if not lista:
            return
        ids = [i for i, _ in lista]
        encendida = self.panel.capa_encendida(ids)
        if b.variables() != lista:
            b.poner_variables(lista, encendida)
        for i in ids:
            b.marcar_variable(i, i == encendida)
        b.poner_estilo(self.panel.estilo_capas())
        b.set_estilo_activo(not es_comparacion, "La comparación se ve en franjas: el cambio en %")
        b.poner_paleta(tema.preferencia("escala_olor"))
        b.set_paleta_activa(not es_comparacion, "La comparación va con sus colores: los del cambio en %")
        escala_si = not es_comparacion and encendida not in (None, "penacho")
        motivo = ("El cambio de la comparación va con su escala de %" if es_comparacion
                  else "El penacho hora a hora va con su escala de siempre" if encendida == "penacho" else "Elige primero una variable")
        b.set_escala_activa(escala_si, motivo)
        b.poner_escala(self._escala_mapa)
        if escala_si:
            vmin, vmax = self._rango_mapa or self._rangos_vista.get(encendida) or planes_calculo.rango_de_serie(m)
            b.poner_rango(vmin, vmax, automatico=self._rango_mapa is None)

    def _capa_en_mapa(self, id_capa, si):
        """El mapa ha encendido o apagado una capa (desde la barra o desde su selector): la barra, al día. Al cambiar de capa llegan dos
        avisos, el de la nueva y luego el de la que se apaga; con el primero, las dos siguen encendidas en el panel. Por eso la barra se
        rehace también con el segundo (usuario, 2026-11-17: de «Máximo» a «P98» se quedaba en «Ninguna»)."""
        self.barra_mapa.marcar_variable(id_capa, si)
        self._poner_barra()

    def _escala_elegida(self, escala):
        """Logarítmica o normal: el rango vuelve al automático de esa escala."""
        self._escala_mapa, self._rango_mapa = escala, None
        self._repintar_capas()

    def _rango_elegido(self, rango):
        """Otro rango (vmin, vmax), o None: el automático."""
        self._rango_mapa = tuple(rango) if rango else None
        self._repintar_capas()

    def _paleta_elegida(self, clave):
        """La paleta de colores del olor, elegida en la barra: es la de la configuración (se queda para la próxima vez y la usan también
        los informes). El mapa cambia de color sin rehacer nada."""
        tema.poner_preferencia("escala_olor", clave)
        self.mapa.set_escalas()
        if self._ventana_ajustes is not None:                 # abierta: que enseñe la misma
            self._ventana_ajustes.refrescar()
            self._ventana_ajustes.previa.set_escalas()

    def _capa_visible(self):
        """La capa de lo simulado que se ve en el mapa, si es la media, el máximo o el P98: (columna del resumen, su nombre, la magnitud); None
        fuera de Simular, con el penacho, con la comparación o sin nada encendido."""
        from teodors.operacion import simulacion as planes_calculo
        if self.panel.pagina() != "simulacion" or not self._resultados_visibles:
            return None
        r = self._resultados.get("anios" if self.panel.horizonte_meteo() == "reanalisis" else "periodo")
        m = (r or {}).get("magnitudes", {}).get(self._magnitud)
        if not m:
            return None
        encendida = self.panel.capa_encendida([c["id"] for c in m["capas"]])
        capa = next((c for c in m["capas"] if c["id"] == encendida), None)
        return None if capa is None else (planes_calculo.columna_capa(capa), capa["nombre"], m)

    def _poner_peores(self):
        """El peor punto de cada pueblo para la capa que se ve, un círculo blanco: el que da su valor en la tabla (usuario, 2026-11-17: la tabla
        de un pueblo «no cuadra» con el color de su marca, que está en su centro). Las fichas de los núcleos lo dicen también."""
        from teodors.operacion import simulacion as planes_calculo
        vis = self._capa_visible()
        lista = []
        if vis is not None:
            col, nombre, m = vis
            for p in self._peores.get(col, []):
                lat, lon = geo.a_geo(p["x"], p["y"])
                lista.append({"lat": float(lat), "lon": float(lon),
                              "texto": f"<b>{p['nombre']}</b> · su peor punto<br>{nombre}: {planes_calculo.cifra(p['valor'])} {m['unidad']}"
                                       "<br><span style='color:var(--tenue)'>Es el valor de la tabla del pueblo</span>"})
        firma = tuple((p["lat"], p["lon"], p["texto"]) for p in lista)
        if firma != self._peores_mapa:
            self._peores_mapa = firma
            self.mapa.set_peores(lista)
        if (vis[0] if vis else None) != self._col_nucleos:              # las fichas de los pueblos, con la capa que se ve
            self._pintar_nucleos()

    def _linea_peor(self, pueblo, lat, lon):
        """En la ficha de un pueblo, dónde está su peor punto (el de su tabla) para la capa que se ve, desde esa marca; "" si no hay."""
        vis = self._capa_visible()
        suyos = [p for p in self._peores.get(vis[0], []) if p["nombre"] == pueblo] if (vis and pueblo) else []
        if not suyos:
            return ""
        d, rumbo = min((geo.distancia_rumbo(lat, lon, *geo.a_geo(p["x"], p["y"])) for p in suyos), key=lambda t: t[0])
        donde = "aquí mismo" if d < 75 else f"a {_num(d / 1000, 1)} km de aquí, al {rumbo}"
        return (f"<div style='color:var(--tenue);margin-top:3px'>{vis[1]} de la tabla: el de su peor punto (el círculo blanco), "
                f"{donde}</div>")

    def _poner_leyenda(self):
        """La leyenda del mapa: oculta solo si la barra lo dice y la barra se ve; fuera de Simular, siempre a la vista."""
        si = self.barra_mapa.isHidden() or self.barra_mapa.leyenda_visible()
        if si != self._leyenda_mapa:
            self._leyenda_mapa = si
            self.mapa.ver_leyenda(si)

    def _opacidad_elegida(self, opacidad):
        """La transparencia de lo simulado: en el mapa al momento, sin rehacer nada, y para lo que se pinte después."""
        self._opacidad_mapa = float(opacidad)
        self.mapa.opacidad_grupo(penacho_mapa.GRUPO, self._opacidad_mapa)

    def _encuadrar(self, cual):
        """El mapa, encuadrado en la nave, en la zona intermedia o en todo el dominio (`ENCUADRE_KM`)."""
        if cual in self.ENCUADRE_KM:
            vertices, _ = geo.cuadrado_utm(self.emp["lat"], self.emp["lon"], self.ENCUADRE_KM[cual])
            lats, lons = [p[0] for p in vertices], [p[1] for p in vertices]
            limites = [[min(lats), min(lons)], [max(lats), max(lons)]]
        else:
            limites = self._limites()
        self.mapa.encuadrar(limites)

    def _titulo_imagen(self):
        """El título de la imagen del mapa: lo simulado (o la comparación) y la variable que se ve."""
        return self._titulos_capa.get(self.barra_mapa.variable_marcada()) or config.APP_NOMBRE

    def _carpeta_imagenes(self):
        """Dónde se propone guardar la imagen: la carpeta del caso abierto o, si no, la de las imágenes del usuario."""
        from teodors.operacion import simulacion as planes_calculo
        cual = "anios" if self.panel.horizonte_meteo() == "reanalisis" else "periodo"
        r = self._resultados.get(cual)
        if r is not None and r.get("caso") and r.get("carpeta"):
            return Path(r["carpeta"]).parent
        lugar = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.StandardLocation.PicturesLocation)
        return Path(lugar) if lugar else planes_calculo.dir_guardados()

    def _imagen_mapa(self, copiar):
        """La imagen del mapa tal como se ve (con su leyenda y su escala), con su título y la fecha: al portapapeles o a un PNG."""
        titulo = self._titulo_imagen()
        pie = f"{config.APP_NOMBRE} · {QtCore.QDateTime.currentDateTime().toString('dd/MM/yyyy HH:mm')}"
        imagen = imagen_con_titulo(self.mapa.grab().toImage(), titulo, pie)
        if copiar:
            QtWidgets.QApplication.clipboard().setImage(imagen)
            self.mapa.aviso("Imagen del mapa copiada: pégala en un correo o en un documento")
            return
        nombre = "".join(c if c.isalnum() or c in " -_" else "_" for c in titulo).strip()[:90] or "mapa"
        ruta, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Guardar la imagen del mapa", str(self._carpeta_imagenes() / f"{nombre}.png"),
                                                        "Imagen PNG (*.png)")
        if not ruta:
            return
        if not ruta.lower().endswith(".png"):
            ruta += ".png"
        if imagen.save(ruta, "PNG"):
            log.info(f"Imagen del mapa guardada en {ruta}")
            self.mapa.aviso(f"Imagen guardada: {Path(ruta).name}")
        else:
            self.mapa.aviso("No se pudo guardar la imagen", "fallo")

    def _cancelar_simulacion(self):
        if self._trabajo_sim is not None:
            log.info("Simulación: cancelando…")
            self._trabajo_sim.cancelar()

    # ── guardar y cargar resultados del reanálisis (usuario, 2026-11-09) ─────────────────
    def _guardar_resultados(self):
        """Guardar el caso (usuario, 2026-11-09): pide un nombre y crea «AAAA-MM-DD-nombre», en la carpeta de los casos del reanálisis
        (`simulacion.dir_guardados`), con los resultados y la operación de los focos en «resultados» (`simulacion.guardar_caso`); luego, a su
        lado, su informe en PDF (usuario, 2026-11-10), en otro proceso (`writer.informe.lanzar`)."""
        import datetime as dt
        from teodors.operacion import focos, periodos, simulacion as planes_calculo
        modo = self.panel.horizonte_meteo()
        r = self._resultados["anios" if modo == "reanalisis" else "periodo"]     # reanálisis o episodio/predicción, según el modo
        if r is None or self._trabajo_archivo is not None:
            return
        nombre, ok = QtWidgets.QInputDialog.getText(self, "Guardar resultados", "Nombre del caso (la carpeta será «AAAA-MM-DD-nombre»):",
                                                    text=(r.get("caso") or {}).get("nombre", "").split("-", 3)[-1] or r["nombre"] or "Base")
        if not ok:
            return
        pe = r.get("periodo")
        fecha = dt.date.fromisoformat(periodos.central_episodio(pe)) if pe else None   # episodio/predicción: la fecha de la queja
        try:
            carpeta = planes_calculo.carpeta_caso(nombre, fecha=fecha, modo=modo)      # casos/<modo>/<AAAA-MM-DD>-<nombre>
        except ValueError as e:
            self.panel.set_archivando(False, str(e))
            return
        if (carpeta / "resultados").exists() and QtWidgets.QMessageBox.question(
                self, "Guardar resultados", f"Ya hay un caso «{carpeta.name}».\n¿Sustituir sus resultados?") != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            catalogo = focos.cargar()
        except (ValueError, OSError):
            catalogo = None

        def hecho(info):
            self.mapa.aviso("Caso guardado")
            self._hacer_informe(info)                                                  # el informe en PDF: reanálisis y episodio (el de la queja)
        self._archivar(planes_calculo.guardar_caso, (r, carpeta, catalogo), "Guardando el caso…", hecho)

    def _informe_comparacion(self):
        """El informe en PDF de los dos escenarios comparados (usuario, 2026-11-10: lo común, la operación de los dos, los resultados de cada
        uno y la comparación), en la carpeta de los casos del reanálisis, en «comparaciones»: en otro proceso, con su avance en el panel."""
        import functools
        from teodors.writer import informe
        r = self._comparacion
        if r is None or self._trabajo_archivo is not None:
            return
        texto = f"Haciendo el informe de «{html.escape(r['otro']['nombre'])}» frente a «{html.escape(r['ref']['nombre'])}»…"

        def hecho(x):
            pdf = Path(x["pdf"])
            self.panel.set_archivando(False, f"Informe de la comparación: <b>{html.escape(pdf.name)}</b> · <a href='{pdf.as_uri()}'>abrirlo</a> · "
                                             f"<a href='{pdf.parent.as_uri()}'>abrir la carpeta</a>")
            self.mapa.aviso("Informe de la comparación hecho")

        def fallo(m):
            log.error(f"Informe de la comparación: {m}")
            self.panel.set_archivando(False, f"El informe de la comparación no se pudo hacer: {html.escape(m.splitlines()[0])}")
        self._archivar(functools.partial(informe.lanzar, otro=r["otro"]["carpeta"]), (r["ref"]["carpeta"],), texto, hecho, fallo, pasos=True)

    def _hacer_informe(self, info):
        """El informe en PDF de un caso recién guardado, en su carpeta, junto a «resultados»: en otro proceso, con su avance en el panel."""
        from teodors.writer import informe
        caso = Path(info["carpeta"])
        nombre, url = html.escape(caso.name), caso.as_uri()
        aviso = "" if info["focos"] else "<br>Sin los focos: han cambiado desde que se simuló."
        guardado = f"Guardado en <b>{nombre}</b> · <a href='{url}'>abrir la carpeta</a>"

        def hecho(r):
            self.panel.set_archivando(False, f"{guardado} · <a href='{Path(r['pdf']).as_uri()}'>abrir el informe</a>{aviso}")
            self.mapa.aviso("Informe hecho")

        def fallo(m):
            log.error(f"Informe del caso «{caso.name}»: {m}")
            self.panel.set_archivando(False, f"{guardado}{aviso}<br>El informe no se pudo hacer: {html.escape(m.splitlines()[0])}")
        self._archivar(informe.lanzar, (caso,), f"Guardado en <b>{nombre}</b>. Haciendo su informe…", hecho, fallo, pasos=True)

    def _cargar_resultados(self):
        """Cargar un caso guardado: se elige su carpeta (la de los casos del modo actual) y se enseña tal cual (`simulacion.cargar_caso`).
        El resultado cargado se coloca en reanálisis o en episodio/predicción según su `periodo` (lo hace `_simulado`)."""
        from teodors.operacion import simulacion as planes_calculo
        if self._trabajo_archivo is not None or self._trabajo_sim is not None:
            return
        modo = self.panel.horizonte_meteo()
        inicio = planes_calculo.dir_guardados(modo if modo in ("reanalisis", "queja", "prediccion") else "reanalisis")
        carpeta = QtWidgets.QFileDialog.getExistingDirectory(self, "Cargar un caso guardado", str(inicio if inicio.is_dir() else config.DATOS))
        if not carpeta:
            return

        def hecho(r):
            self.panel.set_archivando(False)
            self._limpiar_simulacion(r.get("periodo") is not None)   # limpia lo del mismo tipo (año o periodo) antes de poner lo cargado
            self._simulado(r)
        self._archivar(planes_calculo.cargar_caso, (carpeta,), "Cargando el caso…", hecho)

    def _archivar(self, funcion, args, texto, hecho, fallo=None, pasos=False):
        """Guarda o carga unos resultados (o hace un informe) en segundo plano; mientras, los botones esperan. `pasos`: el avance, con lo que
        va haciendo."""
        self.panel.set_archivando(True, texto)
        t = Trabajo(funcion, *args, parent=self)
        t.progreso.connect(lambda pct, m: self.panel.set_archivando(True, f"{texto} {pct} %" + (f" · {html.escape(m)}" if pasos and m else "")))
        t.hecho.connect(hecho)

        def fallo_defecto(m):
            log.error(f"{texto.rstrip('…')}: {m}")
            self.panel.set_archivando(False, f"No se pudo: {m}")
        t.fallo.connect(fallo or fallo_defecto)

        def fin():
            if self._trabajo_archivo is not t:                      # otro ha empezado al acabar este (el informe, tras guardar): es suyo
                return
            self._trabajo_archivo = None
            if self.panel._archivando:
                self.panel.set_archivando(False, self.panel.lbl_sim.text() if self.panel.lbl_sim.isVisible() else "")
        t.finished.connect(fin)
        self._trabajo_archivo = t
        t.start()

    def _simulacion_fallida(self, mensaje):
        if "cancelado" in mensaje.lower():
            log.info("Simulación cancelada.")
        else:
            log.error(f"No se pudo simular: {mensaje}")
        self.panel.set_fallo_simulacion(mensaje)

    def _fin_simulacion(self):
        self._trabajo_sim = None
        self.panel.fin_simulacion()

    def _limpiar_simulacion(self, periodo=None):
        """Quita lo simulado: `periodo` True, el día, el episodio o la predicción; False, los años del reanálisis; None, todo."""
        for prefijo, cual, es in (("plan", "anios", False), ("dia", "periodo", True)):
            if periodo is None or periodo == es:
                self._quitar_capas(prefijo)
                self._resultados[cual] = None
                self._valores.pop(cual, None)
        if periodo is None or periodo:
            self.mapa.quitar_penacho()
            self.panel.set_capa_visible("penacho", False)
        self.panel.limpiar_resultado(periodo)
        if not any(self._resultados.values()):
            self._magnitud = None
        self._pintar_nucleos()
        self._poner_barra()

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

    # ── episodio: su viento (descargar + simular 3D) ─────────────────────────────────────
    def _simular_viento_episodio(self):
        """Episodio: descarga (GFS + estaciones) y calcula el viento 3D de la ventana víspera/día/siguiente; mientras, el botón lo cancela."""
        import datetime as dt
        from teodors.operacion import periodos
        if self._trabajo_episodio is not None:
            self._episodio_cancelado = True                                           # al terminar: borra tmp y no post-procesa
            self.panel.set_estado_episodio("Cancelando…")
            self._trabajo_episodio.cancelar()
            return
        iso = self.panel.dia_episodio()
        if not iso:
            return
        dia = dt.date.fromisoformat(iso)
        p = periodos.nuevo("queja", (dia - dt.timedelta(days=1)).isoformat(), 3)      # víspera, día, siguiente
        self._periodo_episodio = p
        self._episodio_cancelado = False
        self.panel.set_preparando_episodio(True)
        self._trabajo_episodio = Trabajo(periodos.preparar_viento, p, parent=self)
        self._trabajo_episodio.progreso.connect(self.panel.set_progreso_episodio)
        self._trabajo_episodio.fallo.connect(self._episodio_fallido)
        self._trabajo_episodio.finished.connect(self._fin_viento_episodio)
        self._trabajo_episodio.start()

    def _episodio_fallido(self, mensaje):
        if "cancelado" not in mensaje:
            log.error(f"No se pudo preparar el viento del episodio: {mensaje}")
            self.mapa.aviso("No se pudo preparar el viento del episodio", "fallo")

    def _fin_viento_episodio(self):
        from teodors.operacion import periodos
        self._trabajo_episodio = None
        self.panel.set_preparando_episodio(False)
        if self._episodio_cancelado:                                # cancelado: borrar tmp y NO post-procesar (ni mapa ni calendario)
            self._episodio_cancelado = False
            if self._periodo_episodio is not None:
                periodos.borrar_viento_tmp(self._periodo_episodio)
            self._periodo_episodio, self._episodio_sin_guardar = None, False
            self.mapa.quitar_viento()
            self.panel.cal_episodio.poner_dias({})                  # calendario sin colores
            self.panel.set_estado_episodio("Cancelado: se ha borrado lo descargado y simulado.")
            return
        if self._periodo_episodio is None:
            return
        f = periodos.fuente(self._periodo_episodio)                  # disponibilidad / coherencia tras la descarga
        if not f:
            self.panel.set_estado_episodio("No hay viento para esos días (¿sin datos?)")
            return
        self.panel.b_guardar_viento.setEnabled(True)
        self._episodio_sin_guardar = True                            # recién calculado: sin guardar
        try:                                                         # postproceso: colorear el calendario con el viento del episodio
            from teodors.operacion import viento_mapa
            resumen = viento_mapa.resumen_planta(viento_mapa.serie_planta(self._periodo_episodio["serie"]))
            self.panel.colorear_episodio(resumen)
        except Exception as e:                                       # noqa: BLE001
            log.warning(f"No se pudo colorear el calendario del episodio: {e}")
        self._ver_viento_episodio_mapa()                             # el viento del episodio, en el mapa
        avisos = [a for a in [f.get("aviso")] if a]
        try:                                                         # coherencia de las estaciones (huecos, sin dato, atascado, divergencia)
            coh = periodos.coherencia_viento(self._periodo_episodio)
            avisos += coh.get("avisos", [])
            if coh.get("avisos"):
                log.warning("Coherencia del episodio: " + " | ".join(coh["avisos"]))
        except Exception as e:                                       # noqa: BLE001
            log.warning(f"coherencia: {e}")
        if avisos:
            self.panel.set_estado_episodio("Viento listo · avisos: " + "; ".join(avisos[:2]) + (f" (+{len(avisos) - 2})" if len(avisos) > 2 else ""))
        else:
            self.panel.set_estado_episodio("Viento listo · con estaciones, datos coherentes")
        # TODO (siguiente pieza): ver la evolución del viento en el mapa del panel Meteo

    def _cargar_viento_episodio(self):
        """Carga un viento de episodio ya calculado (sin re-descargar): colorea el calendario y elige su día central."""
        import datetime as dt
        from PySide6 import QtWidgets
        from teodors.operacion import periodos, viento_mapa
        vientos = periodos.vientos_episodio()
        if not vientos:
            self.panel.set_estado_episodio("No hay vientos de episodio guardados todavía")
            return
        ops = {f"{v['central']} · {v['dias']} días  ({v['serie']})": v for v in vientos}
        sel, ok = QtWidgets.QInputDialog.getItem(self, "Cargar viento del episodio", "Elige un viento ya calculado:",
                                                 list(ops), 0, False)
        if not ok or sel not in ops:
            return
        v = ops[sel]
        self._periodo_episodio = periodos.cargar_viento(v)          # copia el viento guardado a tmp y devuelve su periodo
        self.panel.cal_episodio.elegir(dt.date.fromisoformat(v["central"]))
        try:
            resumen = viento_mapa.resumen_planta(viento_mapa.serie_planta(v["serie"]))
            self.panel.colorear_episodio(resumen)
        except Exception as e:                                       # noqa: BLE001
            log.warning(f"No se pudo colorear al cargar el viento: {e}")
        self.panel.set_estado_episodio(f"Viento cargado · {v['central']}")
        self.panel.b_guardar_viento.setEnabled(True)
        self._episodio_sin_guardar = False                           # un viento cargado ya estaba guardado
        self._ver_viento_episodio_mapa()                             # y lo pone en el mapa

    def _guardar_viento_episodio(self):
        """Guarda el viento del episodio (que vive en tmp) de forma permanente en `casos/episodios/<fecha>/viento`."""
        from teodors.operacion import periodos
        p = self._periodo_episodio
        if p is None:
            return
        try:
            dest = periodos.guardar_viento(p)
        except Exception as e:                                       # noqa: BLE001
            log.error(f"No se pudo guardar el viento del episodio: {e}")
            self.panel.set_estado_episodio(f"No se pudo guardar el viento: {e}")
            return
        self._episodio_sin_guardar = False
        self.panel.set_estado_episodio(f"Viento guardado en «episodios/{dest.parent.name}» · recárgalo con «Cargar viento»")

    def _ver_viento_episodio_mapa(self):
        """Pone el viento del episodio (los días de la ventana) en el mapa, como el «Ver en el mapa» del reanálisis."""
        from teodors.operacion import viento_mapa
        p = self._periodo_episodio
        if p is None:
            return
        try:
            d = viento_mapa.datos_dia(p["ini"], p["serie"], dias=p["dias"])
            self.mapa.set_viento(d)
            self._dia_viento = (d["horas"][0][:10], len(d["horas"]) // 24)
            self.panel.btn_play.setChecked(False)
            self.panel.btn_lento.setChecked(False)
            self.panel.set_viento_listo(d["horas"])                 # enciende el reproductor: play + evolución hora a hora (72 h)
            self.panel.set_viento_planta(d["horas"], d.get("planta"))
        except Exception as e:                                       # noqa: BLE001
            log.warning(f"No se pudo ver el viento del episodio en el mapa: {e}")
        import datetime as dt
        try:                                                         # rosas de lo MEDIDO en los días del episodio: para el hover de las estaciones (y el informe)
            fin = (dt.date.fromisoformat(p["ini"]) + dt.timedelta(days=p["dias"] - 1)).isoformat()
            self._rosas_episodio = validacion.rosas_periodo(self.emp["lat"], self.emp["lon"], p["ini"], fin)
        except Exception as e:                                       # noqa: BLE001
            log.warning(f"No se pudieron calcular las rosas del episodio: {e}")
            self._rosas_episodio = None
        self._pintar_estaciones()

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
        self._viento_en_simular()
        self._resultados_segun_pagina()

    def _quitar_capas(self, prefijo):
        """Las capas de media, máximo y norma de un resultado («plan» o «dia»), fuera del mapa y del selector."""
        from teodors.operacion import simulacion as planes_calculo
        for capa in planes_calculo.CAPAS:
            self.mapa.quitar_capa(f"{prefijo}_{capa}")
            self.panel.set_capa_visible(f"{prefijo}_{capa}", False)

    def _resultados_segun_pagina(self):
        """Lo simulado solo se ve en Simular (usuario, 2026-11-09: que en Meteorología desaparezcan los resultados de olores y gases, para que
        nadie tome los de los años del reanálisis por los de un día suyo): en las demás páginas, fuera del mapa, del selector de capas y de
        las fichas de los núcleos; al volver, como estaba. Y en Simular, con el reanálisis, lo del modo: lo simulado o la comparación."""
        en_simular = self.panel.pagina() == "simulacion"
        comparar = self.panel.horizonte_meteo() == "reanalisis" and self.panel.modo_reanalisis() == "comparar"
        cambios = ((en_simular and not comparar, self._ver_simulado), (en_simular and comparar, self._ver_comparacion))
        for ver, poner in sorted(cambios, key=lambda c: c[0]):        # primero se quita lo que se va: nunca las dos a la vez
            poner(ver)
        self._poner_barra()                                            # la barra de encima del mapa, con lo que se ve

    def _ver_simulado(self, ver):
        """Lo simulado en el mapa, o fuera, recordando la capa que se veía."""
        if ver == self._resultados_visibles:
            return
        if not ver:
            self._encendida_oculta = self.panel.capa_encendida(self._ids_capas())
        self._resultados_visibles = ver
        if self._magnitud is None or not any(self._resultados.values()):
            return
        if ver:
            self._poner_magnitud(self._magnitud, self._encendida_oculta)
            return
        for prefijo in ("plan", "dia"):
            self._quitar_capas(prefijo)
        self.mapa.quitar_penacho()
        self.panel.set_capa_visible("penacho", False)
        self._valores = {}
        self._pintar_nucleos()

    # ── comparar escenarios del reanálisis (usuario, 2026-11-09) ─────────────────────────
    def _ids_comparacion(self):
        from teodors.operacion import simulacion as planes_calculo
        return [f"comp_{c}" for c in planes_calculo.CAPAS]

    def _modo_reanalisis(self, modo):
        """Simular o comparar: al comparar, los escenarios ya simulados en los desplegables; en el mapa, lo de ese modo.
        Al pasar de Simular (con resultados) a Comparar avisa: la comparación reinicia los resultados del reanálisis."""
        from teodors.operacion import comparacion
        if modo == "comparar" and self._resultados.get("anios") is not None:
            from PySide6 import QtWidgets
            box = QtWidgets.QMessageBox(self)
            box.setIcon(QtWidgets.QMessageBox.Icon.Question)
            box.setWindowTitle("Datos sin guardar")
            box.setText("Al comparar escenarios se reinician los resultados del reanálisis simulado.\n"
                        "¿Quieres guardarlos antes de comparar?")
            Rol = QtWidgets.QMessageBox.ButtonRole
            b_guardar = box.addButton("Guardar", Rol.AcceptRole)
            box.addButton("Descartar", Rol.DestructiveRole)
            b_cancelar = box.addButton("Cancelar", Rol.RejectRole)
            box.setDefaultButton(b_guardar)
            box.exec()
            clic = box.clickedButton()
            if clic is b_cancelar:
                self.panel.set_modo_reanalisis("simular")    # cancelar: vuelve a «Simular», no se pierde nada
                return
            if clic is b_guardar:
                self._guardar_resultados()
            self._limpiar_simulacion(False)                  # reinicia los resultados del reanálisis simulado
        if modo == "comparar":
            self.panel.set_escenarios(comparacion.escenarios(self._casos_otros))
        self._resultados_segun_pagina()

    def _ver_comparacion(self, ver):
        """La comparación en el mapa, o fuera, recordando la capa que se veía."""
        if ver == self._comparacion_visible:
            return
        if not ver:
            self._comp_oculta = self.panel.capa_encendida(self._ids_comparacion())
        self._comparacion_visible = ver
        if self._comparacion is None:
            return
        if ver:
            self._poner_comparacion(self._comp_oculta)
        else:
            self._quitar_capas("comp")

    def _poner_comparacion(self, encendida):
        """Las isolíneas del cambio de la magnitud elegida, con `encendida` a la vista."""
        import json
        r = self._comparacion
        if r is None:
            return
        if not self._comparacion_visible:
            self._comp_oculta = encendida
            return
        m = r["magnitudes"][self.panel.magnitud_comparada() or r["orden"][0]]
        hay = set()
        for c in m["capas"]:
            hay.add(c["id"])
            self._titulos_capa[c["id"]] = f"Cambio · {r['otro']['nombre']} frente a {r['ref']['nombre']} · {m['nombre']} · {c['titulo']} (%)"
            datos = json.loads(Path(c["ruta"]).read_text(encoding="utf-8"))
            self.mapa.set_isolineas(c["id"], f"Cambio · {m['nombre']} · {c['titulo']}", datos, c["leyenda"], visible=c["id"] == encendida,
                                    opacidad=self._opacidad_mapa, grupo=penacho_mapa.GRUPO)
            if c["id"] != encendida:
                self.panel.set_capa_visible(c["id"], False)
        for i in self._ids_comparacion():
            if i not in hay:
                self.mapa.quitar_capa(i)
                self.panel.set_capa_visible(i, False)
        self._poner_barra()

    def _comparar(self, ref, otro):
        """Compara dos escenarios ya simulados, en segundo plano (unos segundos: no se vuelve a calcular)."""
        from teodors.operacion import comparacion, simulacion as planes_calculo
        if self._trabajo_comp is not None or not ref or not otro:
            return
        self._quitar_capas("comp")
        self._comparacion = None
        self.panel.limpiar_comparacion()
        self.panel.set_comparando(True)
        log.info("Comparando dos escenarios del reanálisis…")
        t = Trabajo(comparacion.comparar, ref, otro, parent=self)
        t.progreso.connect(self.panel.set_progreso_simulacion)

        def hecho(r):
            self._comparacion = r
            self.panel.set_comparando(False)
            self.panel.set_comparacion(r, planes_calculo.cifra)
            self._poner_comparacion("comp_norma")
            self.mapa.aviso(f"«{r['otro']['nombre']}» frente a «{r['ref']['nombre']}»")

        def fallo(m):
            log.error(f"No se pudo comparar: {m}")
            self.panel.set_comparando(False)
            self.panel.set_fallo_comparacion(m.split(": ", 1)[-1] if m.startswith("ValueError") else m)

        def fin():
            self._trabajo_comp = None
            if self.panel._comparando:
                self.panel.set_comparando(False)
        t.hecho.connect(hecho)
        t.fallo.connect(fallo)
        t.finished.connect(fin)
        self._trabajo_comp = t
        t.start()

    def _cargar_escenario(self):
        """Un caso guardado de otra carpeta para compararlo (los de la carpeta de los casos ya están en la lista): se comprueba como «Cargar
        resultados» y se elige en el desplegable que lo pidió."""
        from teodors.operacion import comparacion, simulacion as planes_calculo
        if self._trabajo_archivo is not None:
            return
        inicio = planes_calculo.dir_guardados()
        carpeta = QtWidgets.QFileDialog.getExistingDirectory(self, "Abrir un caso guardado", str(inicio if inicio.is_dir() else config.DATOS))
        if not carpeta:
            return

        def hecho(r):
            self.panel.set_archivando(False)
            if r["carpeta"] not in self._casos_otros:
                self._casos_otros.append(r["carpeta"])
            self.panel.set_escenarios(comparacion.escenarios(self._casos_otros))
            self.panel.escenario_cargado(r["carpeta"])
        self._archivar(planes_calculo.cargar_caso, (carpeta,), "Abriendo el caso…", hecho)

    def _viento_en_simular(self):
        """En Simular con el reanálisis (usuario, 2026-11-09: «no existe la opción de simular un día ni ver la animación; en capas no puede
        salir las opciones de viento»): el viento del día, fuera del mapa y del selector de capas, y sin reproductor; al volver, como estaba."""
        sin = self.panel.pagina() == "simulacion" and self.panel.horizonte_meteo() == "reanalisis"
        self.mapa.ocultar_viento(sin)
        self.panel.set_sin_reproductor(sin)

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
    def _ver_ayuda(self):
        """El botón «Ayuda» del riel abrirá el manual de la app, que se hará más adelante (usuario, 2026-11-07). Mientras,
        lo que había en Ayuda del menú: la versión y las fuentes de datos con sus licencias, que la app tiene que dejar ver."""
        QtWidgets.QMessageBox.about(
            self, "Ayuda",
            f"<h3>{config.APP_NOMBRE}</h3><p>Versión {config.pide('identidad', 'version')} · {config.pide('identidad', 'entidad')}</p>"
            "<p><i>El manual de la app, en preparación.</i></p>"
            "<p><b>Fuentes de datos y licencias</b></p><ul>"
            + "".join(f"<li>{c}</li>" for c in config.pide("fuentes", "creditos")) +
            "<li>Leaflet (BSD-2), folium (MIT), pyproj (MIT)</li>"
            "<li>Qt / PySide6 (LGPL v3)</li></ul>")
