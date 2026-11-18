# -*- coding: utf-8 -*-
"""Panel izquierdo: una barra de iconos con una página por tema (rama interfaz-moderna, 2026-10-31):
Inicio, Planta y, en el orden de uso, Focos → Meteorología → Simulación. Sustituye a la lista de
secciones plegables. Debajo de las páginas, ajustes, ayuda, actividad y terminal.
Bajo el mapa, el reproductor de tiempo (`Panel.reproductor`).

La planta y el dominio son FIJOS (decisión del usuario): no hay controles para moverlos."""
import datetime as dt
import html
import time
from zoneinfo import ZoneInfo

from PySide6 import QtCore, QtGui, QtWidgets

from teodors import planta as config
from teodors.comun import registro
from teodors.comun.formato import km as _km, num as _num
from teodors.gui import tema
from teodors.gui.viento_planta import CalendarioViento, FranjaHoras, fecha_larga
from teodors.gui.widgets import FilaPaso, Tarjeta, TarjetaCategoria
from teodors.operacion import periodos
from teodors.planta import geo

log = registro.get("gui")

NOMBRE_NUCLEO = {"residencial": ("núcleo urbano", "núcleos urbanos"),
                 "industrial": ("núcleo industrial", "núcleos industriales"),
                 "deportivo": ("espacio deportivo", "espacios deportivos")}


def _margen_con_barra(v):
    """Hueco de `rangeChanged` que deja sitio a la barra de desplazamiento cuando hace falta.

    Es una FÁBRICA, no `lambda _a, b, v=v: …`: una lambda con argumentos obligatorios Y otro con
    valor por defecto no sobrevive al compilado (ver `Panel._capa_nombrada`)."""
    return lambda _a, maximo: v.setContentsMargins(12, 10, 2 if maximo > 0 else 12, 12)


def _pct(x):
    return "< 0,1 %" if 0 < x < 0.05 else f"{_num(x, 1)} %"


def _punto_familia(familia):
    """Punto del color de esa familia de núcleos."""
    return f"<span style='color:$fam_{familia}'>●</span>"


def solo_olor(r):
    """La magnitud que se ve de un resultado o de una comparación: el olor (usuario, 2026-11-17: «a partir de la v0.1.11 se dejarán de
    visualizar los resultados para diferentes gases, solo se visualizan los resultados de olor») o, si no lo tiene, la primera."""
    return "olor" if "olor" in r["magnitudes"] else r["orden"][0]


def texto_anios(p=False):
    """El periodo del reanálisis, en un texto: el de las respuestas de la serie (`simulacion.periodo_reanalisis`, o `p` si ya se ha
    leído), «N años» si son años completos y si no «d/m/aaaa – d/m/aaaa»; sin ellas, los años de planta.json, «N años»."""
    from teodors.operacion import simulacion
    if p is False:
        p = simulacion.periodo_reanalisis()
    if p is None:
        n = len(config.REANALISIS_ANIOS)
    elif p["incompletos"] or p["huecos"]:
        ini, fin = (dt.date.fromisoformat(p[k]) for k in ("ini", "fin"))
        return f"{ini.day}/{ini.month}/{ini.year} – {fin.day}/{fin.month}/{fin.year}"
    else:
        n = len(p["anios"])
    return f"{n} años" if n != 1 else "1 año"


class CeldaValor(QtWidgets.QTableWidgetItem):
    """Celda de una concentración: se ordena por su valor, no por el texto con formato («< 0,01», «1,2»)."""

    def __init__(self, valor, texto):
        super().__init__(texto)
        self.valor = valor

    def __lt__(self, otra):
        return self.valor < otra.valor


class BloqueResultado(QtWidgets.QWidget):
    """Lo que da una simulación en una magnitud: su máximo, las capas del mapa y la tabla de lugares, que sale ordenada por la media y
    se ordena por la columna que se pulse, primero de más a menos. Las columnas son las de gui/normativa.py. Con `pueblos` (el reanálisis,
    que elige sus capas en «En el mapa»; usuario, 2026-11-09: «los resultados tabulados deben ser de los pueblos»), solo la tabla de los pueblos,
    con su distancia y de peor a mejor por el P98, y, si los hay, los avisos de lo estimado o sin calcular."""
    KM = {"clave": "km", "titulo": "km", "nombre": "Distancia a la planta (la parte más cercana del pueblo)", "tipo": "km", "limite": None, "capa": None}

    def __init__(self, panel, prefijo, penacho=False, pueblos=False, solo_pueblos=False):
        super().__init__()
        self.prefijo = prefijo
        self.pueblos = pueblos
        self.solo_pueblos = solo_pueblos          # como `pueblos` para la tabla, pero conservando los botones de capa (el episodio)
        self._m, self._cifra = None, None
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        self.lbl = QtWidgets.QLabel(wordWrap=True)
        v.addWidget(self.lbl)
        # las capas (el penacho, la media, el máximo y la norma): las elige la barra de encima del mapa (usuario, 2026-11-17); sus botones,
        # ocultos, llevan cuál está encendida
        if penacho:
            panel._boton_capa("penacho", "penacho", oculto=True)
        self.botones = {}
        if not pueblos:
            for capa, nombre in (("media", "media"), ("maximo", "máximo"), ("norma", "norma")):
                self.botones[capa] = panel._boton_capa(f"{prefijo}_{capa}", nombre, oculto=True)
        self._panel = panel
        self.tabla = QtWidgets.QTableWidget(0, 1)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.tabla.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tabla.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tabla.setWordWrap(False)             # recortado, con el nombre entero en su ayuda
        cab = self.tabla.horizontalHeader()
        cab.setSectionsClickable(True)
        cab.setSortIndicatorShown(True)
        cab.setSortIndicator(1, QtCore.Qt.SortOrder.DescendingOrder)
        v.addWidget(self.tabla)
        self.setVisible(False)
        tema.avisos.cambiado.connect(self._otro_estilo)

    def _otro_estilo(self):
        if self._m is not None:
            self.poner(self._m, self._cifra)     # lo que pasa de su límite va en el color de aviso de cada estilo

    def _columnas(self, m):
        return ([self.KM] if (self.pueblos or self.solo_pueblos) else []) + m["columnas"]

    def orden_por_media(self):
        self.tabla.horizontalHeader().setSortIndicator(1, QtCore.Qt.SortOrder.DescendingOrder)

    def orden_inicial(self, m):
        """Por la media o, con los pueblos, de peor a mejor por el P98 (el estadístico de su capa «norma»)."""
        if not self.pueblos:
            self.orden_por_media()
            return
        cols = self._columnas(m)
        k = next((k for k, c in enumerate(cols, 1) if c["capa"] == "norma"), 2)
        self.tabla.horizontalHeader().setSortIndicator(k, QtCore.Qt.SortOrder.DescendingOrder)

    def poner(self, m, cifra):
        from teodors.operacion import simulacion as PC
        self._m, self._cifra = m, cifra
        if self.solo_pueblos:                     # el episodio: solo la tabla de los pueblos, sin la cabecera ni la lista de gases (usuario, 2026-11-13)
            partes = []
        elif self.pueblos:                        # en una línea, encima de la tabla; la lista, al pasar por encima
            partes = []
            if m["estimados"]:
                partes.append(f"Olor estimado por sus gases en {len(m['estimados'])} foco{'s' if len(m['estimados']) != 1 else ''}")
            if m["fuera"]:
                partes.append(f"{len(m['fuera'])} sin calcular")
            self.lbl.setToolTip("\n".join(([f"Estimado por gases: {'; '.join(m['estimados'])}"] if m["estimados"] else [])
                                          + ([f"Sin calcular: {'; '.join(m['fuera'])}"] if m["fuera"] else [])))
            self.lbl.setObjectName("nota")
        else:
            partes = [f"Máximo: <b>{cifra(m['maximos']['maximo'])} {m['unidad']}</b>"]
            if m["estimados"]:
                partes.append("Estimado por gases: " + html.escape("; ".join(m["estimados"])))
            if m["fuera"]:
                partes.append("Sin calcular: " + html.escape("; ".join(m["fuera"])))
        self.lbl.setText((" · " if self.pueblos else "<br>").join(partes))
        self.lbl.setVisible(bool(partes))
        cols = self._columnas(m)
        norma = next((c for c in cols if c["capa"] == "norma"), None)
        if not self.pueblos:
            self.botones["norma"].setVisible(norma is not None)
            if norma is not None:
                self._panel.nombrar_capa(f"{self.prefijo}_norma", "P98" if norma["clave"] == "p98" else "norma")
        filas = [f for f in m["filas"] if f.get("tipo") == "pueblo"] if (self.pueblos or self.solo_pueblos) else m["filas"]
        T = self.tabla
        T.setSortingEnabled(False)                # con el orden puesto, las filas se moverían mientras se rellenan
        T.setColumnCount(1 + len(cols))
        T.setHorizontalHeaderLabels(["Pueblo" if self.pueblos else "Lugar"] + [c["titulo"] for c in cols])
        cab = T.horizontalHeader()
        cab.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        varios_dias = any(len(h) > 5 for h in m["horas_txt"])
        for k, c in enumerate(cols, 1):
            # el panel es estrecho: el sitio, para los nombres
            cab.setSectionResizeMode(k, QtWidgets.QHeaderView.ResizeMode.Fixed)
            T.setColumnWidth(k, {"hora": 88 if varios_dias else 62, "horas": 62, "km": 46}.get(c["tipo"], 58))
            cabecera = T.horizontalHeaderItem(k)
            cabecera.setToolTip(c["nombre"])
            cabecera.setData(QtCore.Qt.ItemDataRole.InitialSortOrderRole,
                             QtCore.Qt.SortOrder.AscendingOrder if c["tipo"] == "km" else QtCore.Qt.SortOrder.DescendingOrder)
        T.setRowCount(len(filas))
        for i, f in enumerate(filas):
            nombre = QtWidgets.QTableWidgetItem(f["nombre"])
            nombre.setToolTip(f["nombre"])
            T.setItem(i, 0, nombre)
            for k, c in enumerate(cols, 1):
                v = f[c["clave"]]
                it = CeldaValor(v, _num(v, 1) if c["tipo"] == "km" else PC.texto_celda(c, v, m))
                it.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if PC.supera(c, v):
                    it.setForeground(QtGui.QBrush(QtGui.QColor(tema.c("aviso"))))
                    letra = it.font()
                    letra.setBold(True)
                    it.setFont(letra)
                T.setItem(i, k, it)
        if not 0 <= cab.sortIndicatorSection() < T.columnCount():
            self.orden_inicial(m)                 # esa columna no existe en esta magnitud
        T.setSortingEnabled(True)                 # ordena con la columna que hubiera elegida
        T.resizeRowsToContents()                  # sin barra de desplazamiento: se ven todas las filas
        T.setFixedHeight(cab.sizeHint().height() + sum(T.rowHeight(i) for i in range(len(filas))) + 2 * T.frameWidth())


def _con_signo(x):
    """«+12», «−34», «0»: un cambio en %, redondeado y con su signo."""
    r = round(x)
    return f"+{_num(r)}" if r > 0 else f"−{_num(-r)}" if r < 0 else "0"


def _g(v):
    return f"{v:g}".replace(".", ",")


class TablaCambio(QtWidgets.QTableWidget):
    """Los pueblos en una comparación de escenarios (usuario, 2026-11-09): el valor en cada uno y el cambio en %, de un estadístico. Sale del que
    más cambia al que menos (lo que no se da, al final) y se ordena por la columna que se pulse."""
    AZUL, ROJO = "#4393c3", "#d6604d"

    def __init__(self):
        super().__init__(0, 5, objectName="tabla_cambio")
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWordWrap(False)
        cab = self.horizontalHeader()
        cab.setSectionsClickable(True)
        cab.setSortIndicatorShown(False)
        cab.sectionClicked.connect(self._ordenar)
        self._orden = None

    def _ordenar(self, k):
        """Por esa columna; la primera vez, de más a menos (los nombres y la distancia, de menos a más), y luego al revés."""
        cab = self.horizontalHeader()
        if self._orden and self._orden[0] == k:
            orden = QtCore.Qt.SortOrder.AscendingOrder if self._orden[1] == QtCore.Qt.SortOrder.DescendingOrder else QtCore.Qt.SortOrder.DescendingOrder
        else:
            orden = QtCore.Qt.SortOrder.AscendingOrder if k in (0, 1) else QtCore.Qt.SortOrder.DescendingOrder
        self._orden = (k, orden)
        cab.setSortIndicatorShown(True)
        cab.setSortIndicator(k, orden)
        self.sortItems(k, orden)

    def poner(self, m, clave, nombres, cifra):
        """Los pueblos de la magnitud `m` de la comparación con el estadístico `clave`; `nombres`, (referencia, comparado)."""
        filas = [f for f in m["pueblos"] if clave in f]
        filas.sort(key=lambda f: (f[clave][2] is None, -abs(f[clave][2] or 0.0)))
        self._orden = None
        self.horizontalHeader().setSortIndicatorShown(False)
        self.setHorizontalHeaderLabels(["Pueblo", "km", "Ref.", "Comp.", "Cambio"])
        cab = self.horizontalHeader()
        cab.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for k, ancho in ((1, 42), (2, 54), (3, 54), (4, 64)):
            cab.setSectionResizeMode(k, QtWidgets.QHeaderView.ResizeMode.Fixed)
            self.setColumnWidth(k, ancho)
        for k, ayuda in ((2, f"Referencia: {nombres[0]} ({m['unidad']})"), (3, f"Comparado: {nombres[1]} ({m['unidad']})"),
                         (4, f"(comparado − referencia) / referencia, en %; «—» si los dos están por debajo de {_g(m['umbral'])} {m['unidad']}")):
            self.horizontalHeaderItem(k).setToolTip(ayuda)
        self.setRowCount(len(filas))
        for i, f in enumerate(filas):
            a, b, pct = f[clave]
            nombre = QtWidgets.QTableWidgetItem(f["nombre"])
            nombre.setToolTip(f["nombre"])
            self.setItem(i, 0, nombre)
            for k, (valor, texto) in enumerate(((f["km"], _num(f["km"], 1)), (a, cifra(a)), (b, cifra(b)),
                                                (pct if pct is not None else -1e9, "—" if pct is None else f"{_con_signo(pct)} %")), 1):
                it = CeldaValor(valor, texto)
                it.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if k == 4 and pct is not None and abs(pct) >= 10:
                    it.setForeground(QtGui.QBrush(QtGui.QColor(self.AZUL if pct < 0 else self.ROJO)))
                    letra = it.font()
                    letra.setBold(True)
                    it.setFont(letra)
                self.setItem(i, k, it)
        self.resizeRowsToContents()
        self.setFixedHeight(cab.sizeHint().height() + sum(self.rowHeight(i) for i in range(len(filas))) + 2 * self.frameWidth())


class Panel(QtWidgets.QWidget):
    # (clave, texto de la barra, icono, título de la página)
    PAGINAS = (("inicio", "Inicio", "inicio", "Inicio"), ("planta", "Planta", "planta", "La planta y su entorno"),
               ("focos", "Focos", "focos", "Focos y planes"), ("meteo", "Meteo", "meteo", "Meteorología"),
               ("simulacion", "Simular", "simulacion", "Simulación"), ("visor3d", "3D", "visor3d", "Visor 3D"))
    tituloPagina = QtCore.Signal(str)
    paginaCambiada = QtCore.Signal(str)
    verAjustes = QtCore.Signal()                 # abrir la ventana de configuración
    comprobar = QtCore.Signal()                  # comprobar la herramienta (o cancelar la comprobación en marcha)
    verAyuda = QtCore.Signal()                   # abrir la ayuda: el manual de la app
    verActividad = QtCore.Signal()               # abrir o cerrar el registro de actividad
    verTerminal = QtCore.Signal()                # abrir o cerrar la terminal
    verTerreno = QtCore.Signal()
    verPlanta = QtCore.Signal()
    descargarTerreno = QtCore.Signal()
    descargarEdificios = QtCore.Signal()
    importarEdificios = QtCore.Signal(str)       # los edificios de la planta, del «catastro» o del «lidar» (el administrador)
    editarEdificios = QtCore.Signal()            # abrir el editor de los edificios de la planta (el administrador)
    horizonteMeteo = QtCore.Signal(str)          # "ninguno" | "reanalisis" | "queja" | "prediccion"
    periodoCambiado = QtCore.Signal()            # otro día o número de días del episodio o la predicción
    prepararPeriodo = QtCore.Signal()            # descargar y calcular su viento y sus respuestas (o cancelarlo)
    vientoPeriodo = QtCore.Signal()              # ver su viento en el mapa
    simularVientoEpisodio = QtCore.Signal()      # episodio: descargar + comprobar + simular el viento 3D
    cargarVientoEpisodio = QtCore.Signal()       # episodio: cargar un viento ya guardado
    guardarVientoEpisodio = QtCore.Signal()      # episodio: guardar el viento calculado
    vientoDia = QtCore.Signal(str)               # "aaaa-mm-dd": cargar el viento de ese día
    vientoHora = QtCore.Signal(int, float)       # hora del día y fracción (animación)
    verCapa = QtCore.Signal(str, bool)           # botones «Ver …»: id de la capa, encender
    verFocos = QtCore.Signal()                   # abrir la ventana de los focos
    verPlanes = QtCore.Signal()                  # abrir la ventana de los planes de operación
    simular = QtCore.Signal(object)              # los años del reanálisis: ruta del plan (None = la Base)
    simularPeriodo = QtCore.Signal(object)       # el episodio o la predicción: ruta del plan
    cancelarSimulacion = QtCore.Signal()         # el botón principal, mientras se simula
    guardarResultados = QtCore.Signal()          # lo simulado del reanálisis, a un .zip
    cargarResultados = QtCore.Signal()           # unos resultados guardados, de un .zip
    estiloCapas = QtCore.Signal(str)             # «isolineas» o «degradado»: la media, el máximo y el P98 del reanálisis en el mapa
    modoReanalisis = QtCore.Signal(str)          # «simular» o «comparar» (escenarios ya simulados)
    compararEscenarios = QtCore.Signal(object, object)    # las carpetas de los dos escenarios: referencia y comparado
    cargarEscenario = QtCore.Signal()            # un escenario guardado (.zip), para compararlo
    informeComparacion = QtCore.Signal()         # el informe en PDF de los dos escenarios comparados (usuario, 2026-11-10)
    magnitudComparada = QtCore.Signal(str)       # el olor o un gas, en la comparación
    ver3d = QtCore.Signal()                      # abrir o calcular el penacho elegido en el visor 3D (o cancelarlo)
    magnitudElegida = QtCore.Signal(str)         # olor o un gas, en los resultados de la simulación

    def __init__(self, emp, parent=None):
        super().__init__(parent)
        self._estado = {}                             # lo que resume la página de inicio
        self._crear_reproductor()
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._barra_paginas())
        # El emplazamiento, fijo encima de las páginas: se ve en todas (usuario, 2026-10-31)
        derecha = QtWidgets.QWidget(objectName="pagina")
        col = QtWidgets.QVBoxLayout(derecha)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        arriba = QtWidgets.QVBoxLayout()
        arriba.setContentsMargins(12, 12, 12, 0)
        arriba.addWidget(self._seccion_emplazamiento())
        col.addLayout(arriba)
        self._pila = QtWidgets.QStackedWidget()
        col.addWidget(self._pila, 1)
        lay.addWidget(derecha, 1)
        terreno = self._seccion_terreno()             # crea también los plegables
        # Focos antes que meteo (usuario, 2026-10-29) y Simulación lo último (2026-10-31)
        contenidos = {"inicio": self._seccion_inicio(),
                      "planta": [terreno, self.tarj_elevacion, self.tarj_usos, self._seccion_edificios()],
                      "focos": self._seccion_focos(),
                      "meteo": [self._seccion_meteo(), self._bloque_viento(), self._bloque_episodio(), self._bloque_periodo()],
                      "simulacion": self._seccion_simulacion(),
                      "visor3d": [self._seccion_visor()]}
        self._paginas = {}
        for clave, _, _, _ in self.PAGINAS:
            area = QtWidgets.QScrollArea(widgetResizable=True)
            area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            hoja = QtWidgets.QWidget(objectName="pagina")
            v = QtWidgets.QVBoxLayout(hoja)
            v.setContentsMargins(12, 10, 12, 12)
            v.setSpacing(10)
            # el margen deja sitio a la barra de desplazamiento: las tarjetas siguen alineadas con el emplazamiento
            area.verticalScrollBar().rangeChanged.connect(_margen_con_barra(v))
            for w in contenidos[clave]:
                v.addWidget(w)
            v.addStretch()
            area.setWidget(hoja)
            self._paginas[clave] = area
            self._pila.addWidget(area)
        tema.manos(self)
        tema.manos(self.reproductor)
        self.set_emplazamiento(emp)
        self.set_terreno(None)
        self.set_edificios(None)

    # ── Páginas ──────────────────────────────────────────────────────────────────────────
    def _barra_paginas(self):
        """El riel: las páginas y, abajo, ajustes, ayuda, actividad y terminal (usuario: la configuración estaba en la barra
        superior, 2026-11-06; el menú de la app, que no aportaba nada, se quitó, y su «Ayuda» tiene botón, 2026-11-07)."""
        riel = QtWidgets.QFrame(objectName="riel")
        riel.setFixedWidth(70)
        v = QtWidgets.QVBoxLayout(riel)
        v.setContentsMargins(6, 8, 6, 8)
        v.setSpacing(4)

        def boton(texto, ico, pagina=False):
            b = QtWidgets.QToolButton(objectName="riel_b", text=texto, checkable=pagina)
            b.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            tema.pon_icono(b, ico, "tenue", 22, activo="acento_claro" if pagina else None)
            b.setIconSize(QtCore.QSize(22, 22))
            b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            v.addWidget(b)
            return b

        self._grupo_paginas = QtWidgets.QButtonGroup(self, exclusive=True)
        self._b_pagina = {}
        for clave, texto, ico, titulo in self.PAGINAS:
            b = boton(texto, ico, pagina=True)
            b.clicked.connect(lambda _=False, k=clave: self.ir_a(k))
            self._grupo_paginas.addButton(b)
            self._b_pagina[clave] = b
        v.addStretch()
        # «Configuración» no cabe en el riel (67 px de texto en 54): se rotula «Ajustes» y la ayuda lo dice entero
        self.b_ajustes = boton("Ajustes", "ajustes")
        self.b_ajustes.setToolTip("Configuración")
        self.b_ajustes.clicked.connect(self.verAjustes)
        self.b_ayuda = boton("Ayuda", "ayuda")
        self.b_ayuda.setToolTip("Ayuda y manual de la app")
        self.b_ayuda.clicked.connect(self.verAyuda)
        for texto, ico, senal in (("Actividad", "actividad", self.verActividad),
                                  ("Terminal", "terminal", self.verTerminal)):
            boton(texto, ico).clicked.connect(senal)
        return riel

    def pagina(self):
        """La clave de la página que se ve."""
        return next(k for k, a in self._paginas.items() if a is self._pila.currentWidget())

    def ir_a(self, clave):
        """Enseña una página del panel."""
        self._pila.setCurrentWidget(self._paginas[clave])
        self._b_pagina[clave].setChecked(True)
        self.tituloPagina.emit(next(t for k, _, _, t in self.PAGINAS if k == clave))
        self.paginaCambiada.emit(clave)

    # ── Inicio ───────────────────────────────────────────────────────────────────────────
    def _seccion_inicio(self):
        pasos = Tarjeta("Simular un plan")
        self.pasos = {}
        for n, (clave, titulo) in enumerate((("focos", "Focos y plan de operación"), ("meteo", "Meteorología"),
                                             ("simulacion", "Simulación")), 1):
            f = FilaPaso(n, titulo)
            f.pulsada.connect(lambda k=clave: self.ir_a(k))
            self.pasos[clave] = f
            pasos.cuerpo.addWidget(f)
        return [pasos, self._seccion_comprobar()]

    # el icono de cada categoría de «Comprobar la herramienta»
    ICONOS_COMPROBAR = {"INS": "paquete", "ENT": "carpeta", "VIE": "meteo", "DIS": "visor3d", "MET": "descarga", "RED": "red"}

    def _seccion_comprobar(self):
        """Comprobar la herramienta (usuario, 2026-11-07): las mini rutinas de `operacion.comprobar`, por categorías. Cada una, una tarjeta que
        enseña que se está trabajando en ella (gira, y una barra cuenta sus pruebas) hasta que sale bien o mal, con los códigos de lo que
        falla en etiquetas, sin descripciones (usuario, 2026-11-07); qué significa cada código, al pasar por encima; el detalle y qué hacer, en
        la actividad."""
        from teodors.operacion import comprobar
        sec = Tarjeta("Comprobar la herramienta")
        self.b_comprobar = QtWidgets.QPushButton("Comprobar", objectName="primario")
        self.b_comprobar.clicked.connect(self.comprobar)
        sec.cuerpo.addWidget(self.b_comprobar)
        total = {}
        for _, _, cat, _ in comprobar.pruebas():
            total[cat] = total.get(cat, 0) + 1
        self.categorias = {}
        for cat, nombre in comprobar.CATEGORIAS:
            t = TarjetaCategoria(nombre, self.ICONOS_COMPROBAR[cat], total.get(cat, 1))
            self.categorias[cat] = t
            sec.cuerpo.addWidget(t)
        self._comprobando = False
        return sec

    def set_comprobando(self, si):
        """Empieza (todas las categorías, en espera) o acaba una comprobación; mientras, el botón la cancela."""
        self._comprobando = si
        self.b_comprobar.setText("Cancelar" if si else "Volver a comprobar")
        if si:
            for t in self.categorias.values():
                t.reiniciar()

    @staticmethod
    def _que(codigos):
        from teodors.operacion import comprobar
        return {c: comprobar.CODIGOS[c][:2] for c in codigos}

    def set_prueba(self, pct, resultado):
        """Lo que va saliendo de cada prueba: {categoria, estado ("en_curso" al empezar), codigos [(código, detalle)]}. Una categoría se da
        por acabada al hacer todas sus pruebas."""
        from teodors.operacion import comprobar
        t = self.categorias.get(resultado["categoria"])
        if t is None:
            return
        if resultado["estado"] == "en_curso":
            t.empezar()
            return
        t.prueba_hecha([c for c, _ in resultado["codigos"]])
        if t.hechas >= t.total:
            t.acabar(comprobar.estado_de(t.codigos), t.codigos, self._que(t.codigos))

    def fin_comprobacion(self, r):
        """El resultado (`comprobar.ejecutar`), que manda sobre lo que ha ido saliendo (lleva, por ejemplo, el «sin internet»); o None si
        falló. Lo que no se llegó a comprobar vuelve a «en espera». Sin resumen ni descripciones: cada código, en su categoría."""
        self.set_comprobando(False)
        for cat, t in self.categorias.items():
            c = (r or {}).get("categorias", {}).get(cat)
            if c is not None:
                t.acabar(c["estado"], c["codigos"], self._que(c["codigos"]))
            elif t.estado == "en_curso":
                t.reiniciar()

    def _pintar_inicio(self):
        if not hasattr(self, "pasos"):
            return
        e = self._estado
        n = e.get("focos", 0)
        planes = e.get("planes", 0)
        self.pasos["focos"].poner(
            (f"{n} focos" if n else "Aún no hay focos")
            + f" · {planes} plan{'es' if planes != 1 else ''} guardado{'s' if planes != 1 else ''}", bool(n))
        h = e.get("horizonte", "ninguno")
        self.pasos["meteo"].poner(f"{periodos.MODOS[h]} elegido" if h == "reanalisis" or h == "queja" else
                                  f"{periodos.MODOS[h]} elegida" if h == "prediccion" else "Sin elegir", h != "ninguno")
        if e.get("simulado"):
            self.pasos["simulacion"].poner(f"Último: «{e['simulado']}»", True)
        elif h == "ninguno":
            self.pasos["simulacion"].poner("Falta la meteorología")
        else:
            self.pasos["simulacion"].poner("Listo para simular")

    # ── Emplazamiento ────────────────────────────────────────────────────────────────────
    def _seccion_emplazamiento(self):
        """Fijo encima de todas las páginas, y en poco sitio (usuario, 2026-11-07): el nombre y, debajo, las coordenadas, para copiarlas,
        y los botones de ver la planta y toda la zona. La flecha despliega el resto: latitud, longitud y UTM, que se pueden seleccionar."""
        sec = Tarjeta()
        sec.cuerpo.setContentsMargins(14, 10, 8, 8)
        sec.cuerpo.setSpacing(2)
        self.lbl_nombre = QtWidgets.QLabel(objectName="emplazamiento_t", wordWrap=True)
        sec.cuerpo.addWidget(self.lbl_nombre)
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(2)
        self.lbl_coords = QtWidgets.QLabel(objectName="nota")
        self.lbl_coords.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        fila.addWidget(self.lbl_coords)

        def boton(ico, ayuda, hacer, check=False):
            b = QtWidgets.QToolButton(objectName="icono", checkable=check)
            tema.pon_icono(b, ico, "tenue", 18, activo="acento_claro" if check else None)
            b.setIconSize(QtCore.QSize(18, 18))
            b.setToolTip(ayuda)
            b.clicked.connect(hacer)
            fila.addWidget(b)
            return b
        self.b_copiar = boton("copiar", "Copiar las coordenadas (latitud, longitud)", lambda: self._copiar_coordenadas())
        fila.addStretch()
        self.b_ver_planta = boton("planta", "Ver la planta en el mapa", lambda: self.verPlanta.emit())
        self.b_ver_zona = boton("solo_mapa", "Ver toda la zona", lambda: self.verTerreno.emit())
        self.b_mas_emp = boton("chevron_abajo", "Más datos del emplazamiento", lambda si: self._detalle_emp.setVisible(si), check=True)
        sec.cuerpo.addLayout(fila)

        self._detalle_emp = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(self._detalle_emp)
        form.setContentsMargins(0, 4, 0, 4)
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.lbl_lat, self.lbl_lon = QtWidgets.QLabel(), QtWidgets.QLabel()
        self.lbl_utm = QtWidgets.QLabel()
        for w in (self.lbl_lat, self.lbl_lon, self.lbl_utm):
            w.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        huso = config.EPSG_UTM.split(":")[1][-2:]
        form.addRow("Latitud:", self.lbl_lat)
        form.addRow("Longitud:", self.lbl_lon)
        form.addRow(f"UTM {huso} (X, Y):", self.lbl_utm)
        # sin la línea de la convergencia de meridianos (usuario, 2026-10-24): es un detalle
        # interno de los cálculos (planta.geo.dir_geo_a_rejilla), no del emplazamiento
        self._detalle_emp.setVisible(False)
        sec.cuerpo.addWidget(self._detalle_emp)
        return sec

    def _copiar_coordenadas(self):
        QtWidgets.QApplication.clipboard().setText(self.lbl_coords.text())
        QtWidgets.QToolTip.showText(self.b_copiar.mapToGlobal(QtCore.QPoint(0, self.b_copiar.height())), "Copiadas", self.b_copiar)

    def set_emplazamiento(self, emp):
        lat, lon = emp["lat"], emp["lon"]
        x, y = geo.a_utm(lat, lon)
        self.lbl_nombre.setText(emp["nombre"])
        # coordenadas con punto decimal, como en cualquier SIG (se pueden copiar y pegar)
        self.lbl_coords.setText(f"{lat:.6f}, {lon:.6f}")
        self.lbl_lat.setText(f"{lat:.6f}°")
        self.lbl_lon.setText(f"{lon:.6f}°")
        self.lbl_utm.setText(f"{_num(x)} · {_num(y)} m")

    # ── Terreno y uso del suelo ──────────────────────────────────────────────────────────
    # las cifras de la ficha: (clave, icono, texto de debajo). La cuarta, lo que rodea la planta (usuario, 2026-11-16: «en lugar de decir
    # lo de los 867 edificios a menos de 2 km, prefiero que ponga rodeado de olivares»); los edificios siguen en su sección
    CIFRAS = (("cota", "relieve", "cota de la planta"), ("dominio", "dominio", "terreno"),
              ("nucleo", "casas", "núcleo urbano más cercano"), ("alrededor", "arbol", "lo que rodea la planta"))

    def _tarjeta_cifra(self, icono, nota, grande=True):
        """Una cifra con su icono en un cuadro del color del acento: (marco, valor, texto)."""
        caja = QtWidgets.QFrame(objectName="cifra")
        h = QtWidgets.QHBoxLayout(caja)
        h.setContentsMargins(8, 8, 10, 8)
        h.setSpacing(9)
        ico = QtWidgets.QLabel(objectName="cifra_ico", alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        ico.setFixedSize(30, 30)
        tema.pon_icono(ico, icono, "acento_claro", 18)
        h.addWidget(ico, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        v = QtWidgets.QVBoxLayout()
        v.setSpacing(0)
        valor = QtWidgets.QLabel("—", objectName="cifra_v" if grande else "cifra_p")
        texto = QtWidgets.QLabel(nota, objectName="nota", wordWrap=True)
        v.addWidget(valor)
        v.addWidget(texto)
        h.addLayout(v, 1)
        return caja, valor, texto

    def _seccion_terreno(self):
        """La página Planta (usuario, 2026-11-07: «mejorar el diseño de este panel», con sus botones de las capas; luego, «dale una vuelta
        estética»; «una imagen por cada panel de terreno y de usos del suelo»): arriba, cuatro cifras con su icono; la elevación, con la
        imagen del relieve (con la planta y la escala) y sus barras finas por franja; los usos del suelo, con la imagen de sus usos, una barra
        al 100 % y los cinco primeros; y los núcleos, en tres cifras, y los edificios de al lado, en etiquetas. Todo a la vista. Las fechas
        de descarga, al pasar por encima."""
        from teodors.gui.planta_graficos import BarrasCota, BarraUsos, Miniatura
        sec = Tarjeta()
        sec.cuerpo.setContentsMargins(10, 10, 10, 10)
        self.tarj_ficha = sec
        rejilla = QtWidgets.QGridLayout()
        rejilla.setSpacing(8)
        self.cifras = {}
        for k, (clave, icono, nota) in enumerate(self.CIFRAS):
            caja, valor, texto = self._tarjeta_cifra(icono, nota)
            self.cifras[clave] = (valor, texto)
            rejilla.addWidget(caja, k // 2, k % 2)
        sec.cuerpo.addLayout(rejilla)
        self.lbl_terreno = QtWidgets.QLabel(wordWrap=True, textFormat=QtCore.Qt.TextFormat.RichText)
        sec.cuerpo.addWidget(self.lbl_terreno)
        self.barra_terreno = QtWidgets.QProgressBar(textVisible=True)
        self.barra_terreno.setRange(0, 100)
        self.barra_terreno.hide()
        sec.cuerpo.addWidget(self.barra_terreno)
        lado = config.DOMINIO_DESCARGA_KM
        self.b_terreno = QtWidgets.QPushButton(
            f"Descargar terreno y uso del suelo ({_km(lado)} × {_km(lado)} km)")
        self.b_terreno.clicked.connect(self.descargarTerreno)
        sec.cuerpo.addWidget(self.b_terreno)

        self.tarj_elevacion = Tarjeta("Elevación")
        self.mini_relieve = Miniatura()
        self.tarj_elevacion.cuerpo.addWidget(self.mini_relieve)
        self.barras_cota = BarrasCota()
        self.tarj_elevacion.cuerpo.addWidget(self.barras_cota)
        self.b_ver_elevacion = self._boton_capa("elevacion", "elevación")
        self.tarj_elevacion.cuerpo.addWidget(self.b_ver_elevacion)

        self.tarj_usos = Tarjeta("Usos del suelo")
        self.mini_usos = Miniatura()
        self.tarj_usos.cuerpo.addWidget(self.mini_usos)
        self.barra_usos = BarraUsos()
        self.tarj_usos.cuerpo.addWidget(self.barra_usos)
        self.leyenda_usos = QtWidgets.QGridLayout()
        self.leyenda_usos.setHorizontalSpacing(8)
        self.leyenda_usos.setVerticalSpacing(3)
        self.leyenda_usos.setColumnStretch(0, 1)
        self.tarj_usos.cuerpo.addLayout(self.leyenda_usos)
        self.b_ver_usos = self._boton_capa("usos", "usos del suelo")
        self.tarj_usos.cuerpo.addWidget(self.b_ver_usos)
        return sec

    def _cifra(self, clave, valor, nota=None):
        v, n = self.cifras[clave]
        v.setText(valor)
        if nota is not None:
            n.setText(nota)

    # cuántos usos del suelo salen con nombre; los demás, juntos en «Otros»
    USOS_A_LA_VISTA = 5

    def set_terreno(self, info, resumen=None):
        """Muestra el terreno cargado y su resumen. Si no hay, ofrece descargarlo (una vez)."""
        from pathlib import Path
        from teodors.fuentes import terreno as T
        from teodors.gui.planta_graficos import color_gradiente
        self.b_terreno.setVisible(info is None)
        for w in (self.tarj_elevacion, self.tarj_usos):
            w.setVisible(info is not None)
        self.lbl_terreno.setVisible(info is None)
        if info is None:
            tema.texto(self.lbl_terreno, "<span style='color:$aviso'>Sin descargar.</span>")
            for clave in ("cota", "dominio", "nucleo", "alrededor"):
                self._cifra(clave, "—")
            self.tarj_ficha.setToolTip("")
            return
        lado, e, p = info["lado_km"], info["estadisticas"], info.get("planta", {})
        self.tarj_ficha.setToolTip(f"Terreno descargado el {info['fecha'][:16].replace('T', ' ')}")
        capas = {c["id"]: c for c in info.get("capas_mapa", [])}
        emp = config.cargar_emplazamiento()
        for mini, capa, modo in ((self.mini_relieve, "elevacion", "relieve"), (self.mini_usos, "usos", "usos")):
            c = capas.get(capa)                    # cada tarjeta, con la imagen de su capa del mapa
            if c is not None:
                mini.poner({modo: Path(info["dir"]) / c["png"]}, c["bounds"], emp["lat"], emp["lon"], lado)
            mini.setVisible(c is not None)
        self._cifra("dominio", f"{_km(lado)} × {_km(lado)} km", f"terreno, a {_num(info['res_m'])} m")
        if p.get("z") is not None:
            self._cifra("cota", f"{_num(p['z'])} m", f"cota de la planta · {p.get('uso_nombre', '').lower()}".rstrip(" ·"))
        nucleos = (resumen or {}).get("nucleos", [])
        # los urbanos, con los pueblos que añade la planta y su nombre si se sabe (usuario, 2026-11-16: daba un núcleo a 3,2 km, y el más
        # cercano era un pueblo de la planta, a 1,4 km, que el mapa de usos no ve; el mapa y los informes ya lo tenían)
        from teodors.operacion import pueblos
        try:
            nombres = T.nombres_nucleos(info, [])           # la caché del terreno, sin pedir nada a la red
        except (OSError, ValueError):
            nombres = {}
        urbanos = pueblos.urbanos(nucleos, emp["lat"], emp["lon"], nombres)
        cerca = urbanos[0] if urbanos else None
        self._cifra("nucleo", f"{_num(cerca['dist_m'] / 1000, 1)} km {cerca['rumbo']}" if cerca else "—",
                    f"{cerca['nombre']}, núcleo urbano más cercano" if cerca and cerca["nombre"] else "núcleo urbano más cercano")
        # lo que rodea la planta: el uso del suelo que más hay cerca (`terreno.alrededor`)
        al = (resumen or {}).get("alrededor")
        if al:
            rodea = "rodean" if al["nombre"].split()[0].rstrip(",").endswith("s") else "rodea"      # «Olivares», «Mosaico de cultivos»
            # espacios que no se parten: la nota no corta «79 %» ni «500 m» (la tarjeta es estrecha)
            self._cifra("alrededor", al["nombre"], f"{rodea} la planta · {_num(al['pct'])} % a {_num(al['radio_m'])} m")
        else:
            self._cifra("alrededor", "—", "lo que rodea la planta")

        # la elevación: una barra por franja, con el color de esa cota en la capa del mapa, y la franja de la planta señalada
        bandas = (resumen or {}).get("bandas", [])
        capa = capas.get("elevacion")
        z0, z1 = (capa["leyenda"]["min"], capa["leyenda"]["max"]) if capa else (e["z_min"], e["z_max"])
        paradas = [x.strip() for x in capa["leyenda"]["gradiente"].split(",")] if capa else [tema.c("acento"), tema.c("acento")]
        cortes = list(T.BANDAS_COTA)
        limites = [z0, *cortes, z1]
        colores = [color_gradiente(paradas, ((a + b) / 2 - z0) / max(z1 - z0, 1)) for a, b in zip(limites, limites[1:])]
        suya = sum(1 for c in cortes if p["z"] >= c) if p.get("z") is not None else None
        self.barras_cota.poner(bandas, colores, suya)
        self.tarj_elevacion.titulo.setText(f"Elevación · {_num(e['z_min'])} a {_num(e['z_max'])} m")

        # los usos del suelo: la barra al 100 % y los primeros con su color y su %; los demás, juntos
        grupos = sorted((g for g in (resumen or {}).get("grupos", []) if g["pct"] > 0), key=lambda g: -g["pct"])
        self.barra_usos.poner(grupos)
        while self.leyenda_usos.count():
            w = self.leyenda_usos.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        vista, resto = grupos[:self.USOS_A_LA_VISTA], grupos[self.USOS_A_LA_VISTA:]
        filas = [(g["color"], g["nombre"], g["pct"], g.get("clases", [])) for g in vista]
        if resto:
            filas.append((tema.c("apagado"), f"Otros ({len(resto)})", sum(g["pct"] for g in resto),
                          [{"nombre": g["nombre"], "pct": g["pct"]} for g in resto]))
        for k, (color, nombre, pct, clases) in enumerate(filas):
            et = QtWidgets.QLabel(textFormat=QtCore.Qt.TextFormat.RichText)
            et.setText(f"<span style='color:{color};font-size:15px'>●</span>&nbsp; {html.escape(nombre)}")
            et.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
            et.setToolTip(f"<b>{html.escape(nombre)}</b><br>" + "<br>".join(f"{html.escape(c['nombre'])}: {_pct(c['pct'])}" for c in clases))
            valor = QtWidgets.QLabel(f"<b>{_pct(pct)}</b>", alignment=QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            self.leyenda_usos.addWidget(et, k, 0)
            self.leyenda_usos.addWidget(valor, k, 1)

        # los núcleos: cuántos de cada familia y a qué distancia está el más cercano; los urbanos, con los pueblos de la planta
        for familia, (valor, texto) in self.cifras_nucleos.items():
            de_tipo = urbanos if familia == "residencial" else [n for n in nucleos if n["familia"] == familia]
            uno, varios = NOMBRE_NUCLEO[familia]
            valor.setText(str(len(de_tipo)))
            c = de_tipo[0] if de_tipo else None      # vienen ordenados por distancia
            texto.setText(f"{(varios if len(de_tipo) != 1 else uno).split()[-1]}" + (f"<br>a {_num(c['dist_m'] / 1000, 1)} km {c['rumbo']}" if c else ""))

    # ── Meteorología ─────────────────────────────────────────────────────────────────────
    HORIZONTES = (("ninguno", "Ninguno", True), ("reanalisis", "Reanálisis", True), ("queja", "Episodio", True),
                  ("prediccion", "Predicción", True), ("presente", "Tiempo real  ·  pendiente", False))

    def _horizonte_pulsado(self, clave):
        """Hueco del radio de horizonte meteorológico. FÁBRICA: ver `_capa_nombrada`."""
        return lambda si: si and self.horizonteMeteo.emit(clave)

    def _seccion_meteo(self):
        """Las opciones en dos columnas (2026-11-07): así el calendario del viento del reanálisis cabe debajo sin desplazar la página."""
        sec = Tarjeta("Horizonte")
        self._grupo_meteo = QtWidgets.QButtonGroup(self)
        self._radios_meteo = {}
        rejilla = QtWidgets.QGridLayout()
        rejilla.setSpacing(6)
        for k, (clave, texto, activo) in enumerate(self.HORIZONTES):
            r = QtWidgets.QRadioButton(texto, enabled=activo, checked=(clave == "ninguno"), objectName="opcion_h")
            r.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Fixed)
            r.setToolTip(texto)
            self._grupo_meteo.addButton(r)
            self._radios_meteo[clave] = r
            ultimo = k == len(self.HORIZONTES) - 1 and k % 2 == 0
            rejilla.addWidget(r, k // 2, k % 2, 1, 2 if ultimo else 1)       # el último, solo, a todo lo ancho
            r.toggled.connect(self._horizonte_pulsado(clave))
        rejilla.setColumnStretch(0, 1)
        rejilla.setColumnStretch(1, 1)
        sec.cuerpo.addLayout(rejilla)
        return sec

    # ── viento en superficie (capa animada del mapa) ─────────────────────────────────────
    def _bloque_viento(self):
        """El día del reanálisis (usuario, 2026-11-07: «más manejable a la hora de moverte por el calendario, ya desplegado debajo del
        día seleccionado, y ver en mapa»): el calendario del viento siempre abierto y el botón, que lleva la fecha elegida. Sin el día en
        letra ni su resumen encima (usuario, mismo día: «para ganar espacio al cargar el día y poder ver el viento de ese día»): el resumen
        sale al pasar por cada día, y de día en día se va con las flechas del teclado. Cargado el día, sus horas en la planta
        (`FranjaHoras`), que mueven el reproductor."""
        caja = Tarjeta("Viento de un día")
        self.calendario = CalendarioViento()
        self.calendario.elegido_cambiado.connect(lambda _: self._dia_viento_elegido())
        self.calendario.abrir.connect(lambda _: self._ver_dia_viento())
        caja.cuerpo.addWidget(self.calendario)
        self.barra_resumen = QtWidgets.QProgressBar(minimum=0, maximum=100, textVisible=False)
        self.barra_resumen.setFixedHeight(6)
        self.lbl_resumen = QtWidgets.QLabel(objectName="nota", wordWrap=True)
        for w in (self.barra_resumen, self.lbl_resumen):
            w.setVisible(False)
            caja.cuerpo.addWidget(w)
        self.btn_viento = QtWidgets.QPushButton("Ver en el mapa", objectName="primario")
        self.btn_viento.clicked.connect(self._ver_dia_viento)
        caja.cuerpo.addWidget(self.btn_viento)
        self.franja = FranjaHoras()
        self.franja.hora.connect(lambda h: self.hora_viento.setValue(4 * h))
        self.franja.setVisible(False)
        caja.cuerpo.addWidget(self.franja)
        self._dia_cargado, self._cargando_viento = None, False
        caja.setVisible(False)
        self.caja_viento = caja
        return caja

    def dia_viento(self):
        """El día elegido en el calendario del viento, «aaaa-mm-dd» (None si aún no hay viento)."""
        d = self.calendario.elegido()
        return d.isoformat() if d else None

    def _ver_dia_viento(self):
        if self.dia_viento() and not self._cargando_viento:
            self.vientoDia.emit(self.dia_viento())

    def _dia_viento_elegido(self):
        """Otro día en el calendario: el botón, con su fecha y según esté o no en el mapa."""
        self._pinta_btn_viento()

    def _pinta_btn_viento(self):
        d = self.calendario.elegido()
        en_mapa = self._dia_cargado is not None and self._dia_cargado == self.dia_viento()
        fecha = f"{d:%d/%m/%Y}" if d else ""
        self.btn_viento.setText("Cargando…" if self._cargando_viento else f"{fecha} en el mapa" if en_mapa else
                                f"Ver el {fecha} en el mapa" if d else "Ver en el mapa")
        self.btn_viento.setToolTip(fecha_larga(d).capitalize() + " (día en UTC)" if d else "")
        self.btn_viento.setEnabled(d is not None and not self._cargando_viento and not en_mapa)

    def set_resumen_viento(self, r):
        """El viento de cada día en la planta (`viento_mapa.resumen_planta`) para pintar el calendario; None si no se pudo."""
        self.barra_resumen.setVisible(False)
        self.lbl_resumen.setVisible(False)
        self.calendario.poner_dias((r or {}).get("dias"))
        self._dia_viento_elegido()

    def set_progreso_resumen(self, pct, mensaje):
        """Mientras se lee por primera vez el viento de la planta de toda la serie."""
        self.barra_resumen.setVisible(True)
        self.barra_resumen.setValue(pct)
        self.lbl_resumen.setVisible(True)
        self.lbl_resumen.setText(f"Leyendo el viento de cada día para pintar el calendario: {mensaje} (solo la primera vez)")

    def set_viento_planta(self, horas, planta):
        """Cargado un día: sus horas en la planta (`datos_dia(...)["planta"]`) en la franja, y el botón, «En el mapa»."""
        self._dia_cargado = horas[0][:10] if horas else None
        if planta:
            self.franja.poner(horas, planta["ws"], planta["wd"])
        self.franja.setVisible(bool(planta))
        self._pinta_btn_viento()

    # ── episodio de queja y predicción: su periodo ───────────────────────────────────────
    def _bloque_periodo(self):
        caja = Tarjeta("Periodo")
        self.lbl_fecha_periodo = QtWidgets.QLabel("Día inicial (UTC):")
        self.fecha_periodo = QtWidgets.QDateEdit(calendarPopup=True)
        self.fecha_periodo.setDisplayFormat("dd/MM/yyyy")
        tema.calendario(self.fecha_periodo.calendarWidget())
        hoy = QtCore.QDate.currentDate().addDays(-1)
        self.fecha_periodo.setDateRange(QtCore.QDate(config.REANALISIS_ANIOS[0], 1, 2), hoy)
        self.fecha_periodo.setDate(hoy)
        self.cmb_dias = QtWidgets.QComboBox()
        fila = QtWidgets.QHBoxLayout()
        fila.addWidget(self.lbl_fecha_periodo)
        fila.addWidget(self.fecha_periodo, 1)
        fila.addWidget(QtWidgets.QLabel("Días:"))
        fila.addWidget(self.cmb_dias)
        caja.cuerpo.addLayout(fila)
        self.lbl_periodo = QtWidgets.QLabel(wordWrap=True)
        caja.cuerpo.addWidget(self.lbl_periodo)
        self.b_preparar = QtWidgets.QPushButton("Preparar")
        self.b_preparar.clicked.connect(self.prepararPeriodo)
        caja.cuerpo.addWidget(self.b_preparar)
        self.barra_periodo = QtWidgets.QProgressBar(minimum=0, maximum=100)
        self.barra_periodo.setVisible(False)
        caja.cuerpo.addWidget(self.barra_periodo)
        self.b_ver_periodo = QtWidgets.QPushButton("Ver en el mapa")
        self.b_ver_periodo.clicked.connect(self.vientoPeriodo)
        caja.cuerpo.addWidget(self.b_ver_periodo)
        self.fecha_periodo.dateChanged.connect(lambda _: self.periodoCambiado.emit())
        self.cmb_dias.activated.connect(lambda _: self.periodoCambiado.emit())
        caja.setVisible(False)
        self.caja_periodo = caja
        self._preparando = False
        return caja

    # ── episodio: su día y los botones de viento ─────────────────────────────────────────
    def _bloque_episodio(self):
        """El episodio (modo 'queja'): calendario del día (como el del viento pero vacío hasta simular/cargar el viento) y tres botones:
        Simular viento (descargar + comprobar + simular 3D), Cargar viento y Guardar viento. El calendario se pinta (intensidad + flecha)
        cuando hay viento del episodio."""
        caja = Tarjeta("Día del episodio")
        self.cal_episodio = CalendarioViento()
        self.cal_episodio.poner_rango(dt.date(config.REANALISIS_ANIOS[-1] + 1, 1, 1), dt.date.today())    # desde el año tras el reanálisis hasta hoy
        self.cal_episodio.poner_dias({})                                                                  # sin viento aún: días neutros
        self.cal_episodio.elegido_cambiado.connect(lambda _: self.periodoCambiado.emit())
        caja.cuerpo.addWidget(self.cal_episodio)
        self.lbl_episodio = QtWidgets.QLabel("Sin colores hasta simular o cargar el viento", objectName="nota", wordWrap=True)
        caja.cuerpo.addWidget(self.lbl_episodio)
        self.b_sim_viento = QtWidgets.QPushButton("Simular viento", objectName="primario")
        self.b_cargar_viento = QtWidgets.QPushButton("Cargar viento")
        self.b_guardar_viento = QtWidgets.QPushButton("Guardar viento")
        self.b_guardar_viento.setEnabled(False)                                                          # hasta que haya viento calculado
        self.b_sim_viento.clicked.connect(self.simularVientoEpisodio)
        self.b_cargar_viento.clicked.connect(self.cargarVientoEpisodio)
        self.b_guardar_viento.clicked.connect(self.guardarVientoEpisodio)
        caja.cuerpo.addWidget(self.b_sim_viento)                                                          # primera fila: a todo lo ancho
        fila = QtWidgets.QHBoxLayout()                                                                    # segunda fila: guardar y cargar, a mitad
        fila.addWidget(self.b_guardar_viento)
        fila.addWidget(self.b_cargar_viento)
        caja.cuerpo.addLayout(fila)
        self.barra_episodio = QtWidgets.QProgressBar(minimum=0, maximum=100)
        self.barra_episodio.setVisible(False)
        caja.cuerpo.addWidget(self.barra_episodio)
        caja.setVisible(False)
        self.caja_episodio = caja
        return caja

    def dia_episodio(self):
        """El día elegido en el calendario del episodio, «aaaa-mm-dd» (None si no hay)."""
        d = self.cal_episodio.elegido()
        return d.isoformat() if d else None

    def mostrar_episodio(self, si):
        """El bloque del episodio, solo con el horizonte 'queja'."""
        self.caja_episodio.setVisible(si)

    def set_preparando_episodio(self, si):
        """Mientras se descarga/simula el viento del episodio: la barra visible y el botón como «Cancelar»."""
        self.barra_episodio.setVisible(si)
        self.b_sim_viento.setText("Cancelar" if si else "Simular viento")
        self.b_cargar_viento.setEnabled(not si)

    def set_progreso_episodio(self, pct, texto=""):
        self.barra_episodio.setValue(int(pct))
        if texto:
            self.lbl_episodio.setText(texto)

    def set_estado_episodio(self, texto):
        self.lbl_episodio.setText(texto)
        self._actualizar_simular()          # el viento del episodio cambió de estado (listo/cargado/cancelado): refresca el botón «Simular episodio»

    def colorear_episodio(self, resumen):
        """Pinta el calendario del episodio con el viento del episodio (intensidad + flecha), como el del reanálisis."""
        self.cal_episodio.poner_dias((resumen or {}).get("dias"))

    def mostrar_periodo(self, modo):
        """El bloque del periodo, según la modalidad; nada en las demás."""
        si = modo == "prediccion"                            # queja tiene su propio bloque (episodio); aquí, solo la predicción
        self.caja_periodo.setVisible(si)
        if not si:
            return
        self.cmb_dias.clear()
        for n in periodos.DIAS[modo]:
            self.cmb_dias.addItem(str(n), n)
        self.cmb_dias.setCurrentIndex(self.cmb_dias.findData(periodos.DIAS_DEFECTO[modo]))
        queja = modo == "queja"
        self.lbl_fecha_periodo.setVisible(queja)
        self.fecha_periodo.setVisible(queja)

    def periodo(self):
        """El periodo elegido en Meteorología (episodio o predicción); None en las demás."""
        modo = self.horizonte_meteo()
        if modo == "queja":
            iso = self.dia_episodio()                        # del calendario del episodio: víspera, día, siguiente
            if not iso:
                return None
            return periodos.nuevo(modo, (dt.date.fromisoformat(iso) - dt.timedelta(days=1)).isoformat(), 3)
        if modo == "prediccion":
            return periodos.nuevo(modo, periodos.inicio_prediccion(), self.cmb_dias.currentData() or 3)
        return None

    def set_periodo_estado(self, listo):
        p = self.periodo()
        if p is None:
            return
        previo = "Ejecución de las 00 UTC del " + f"{p['ini'][8:10]}/{p['ini'][5:7]}/{p['ini'][:4]}<br>" if p["modo"] == "prediccion" else ""
        aviso = periodos.fuente(p).get("aviso") if listo else None
        self.lbl_periodo.setText(previo + (f"{periodos.etiqueta(p)}: <b>{'listo' if listo else 'sin preparar'}</b>")
                                 + (f"<br>{html.escape(aviso)}" if aviso else ""))
        self.b_preparar.setText("Cancelar" if self._preparando else ("Volver a preparar" if listo else "Preparar"))
        self.b_ver_periodo.setEnabled(listo and not self._preparando)
        self.fecha_periodo.setEnabled(not self._preparando)
        self.cmb_dias.setEnabled(not self._preparando)
        self._actualizar_simular()

    def set_preparando(self, si):
        self._preparando = si
        self.barra_periodo.setVisible(si)
        self.barra_periodo.setValue(0)

    def set_progreso_periodo(self, pct, mensaje):
        self.barra_periodo.setValue(pct)
        self.lbl_periodo.setText(mensaje)

    def _crear_reproductor(self):
        """Barra de tiempo bajo el mapa: aparece en cuanto hay un día cargado."""
        self.reproductor = QtWidgets.QFrame(objectName="reproductor")
        h = QtWidgets.QHBoxLayout(self.reproductor)
        h.setContentsMargins(14, 8, 14, 8)
        h.setSpacing(12)
        self.btn_play = QtWidgets.QPushButton(objectName="play", enabled=False, checkable=True)
        self.btn_play.setFixedSize(36, 36)
        tema.pon_icono(self.btn_play, "play", "sobre_acento", 18)
        self.btn_play.setIconSize(QtCore.QSize(18, 18))
        h.addWidget(self.btn_play)
        self.lbl_hora_viento = QtWidgets.QLabel("—", objectName="hora_grande")
        self.lbl_hora_viento.setMinimumWidth(200)
        h.addWidget(self.lbl_hora_viento)
        # en CUARTOS DE HORA: entre dos horas se interpola por cercanía (viento) o se funde
        # (penacho)
        self.hora_viento = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, minimum=0,
                                             maximum=92, enabled=False, pageStep=4)
        h.addWidget(self.hora_viento, 1)
        self.lbl_dia_repro = QtWidgets.QLabel(objectName="nota")
        h.addWidget(self.lbl_dia_repro)
        self.btn_lento = QtWidgets.QPushButton("Lento", checkable=True)
        h.addWidget(self.btn_lento)
        # 15 min cada 125 ms = 2 h por segundo (usuario, 2026-10-24: primero ×4 desde 250 ms,
        # «muy rápido», luego ×0,5)
        self._reloj = QtCore.QTimer(self, interval=125)
        self._reloj.timeout.connect(self._avanza_viento)
        self.btn_lento.toggled.connect(lambda si: self._reloj.setInterval(1000 if si else 125))
        self.hora_viento.valueChanged.connect(self._hora_viento_cambiada)
        self.btn_play.toggled.connect(self._play_viento)
        self.reproductor.setVisible(False)

    def dormir(self, si):
        """Con la ventana minimizada el reproductor no avanza; al volver sigue donde estaba."""
        if si:
            self._reloj.stop()
        elif self.btn_play.isChecked():
            self._reloj.start()

    def animar(self):
        """Pone en marcha el reproductor, a velocidad normal."""
        self.btn_lento.setChecked(False)
        self.btn_play.setChecked(True)

    def set_viento_dias(self, rango, dia_inicial=None):
        """Primer y último día con viento (viento_mapa.rango_dias): limitan el calendario (y, si se da, el día con el
        que se abre). None si no hay ninguno."""
        if not rango:
            self.calendario.poner_rango(None, None)
            self._dia_viento_elegido()
            return
        ini, fin = (d.date() if hasattr(d, "date") else d for d in rango)
        self.calendario.poner_rango(ini, fin)
        if self.calendario.elegido() is None:
            d = dia_inicial if dia_inicial is not None else ini
            self.calendario.elegir(d.date() if hasattr(d, "date") else d)
        else:
            self.calendario.elegir(self.calendario.elegido())    # dentro del rango nuevo
        self._dia_viento_elegido()

    def set_viento_cargando(self, si):
        self._cargando_viento = si
        self._pinta_btn_viento()

    def set_viento_listo(self, horas):
        """Tras cargar un periodo: horas = ['aaaa-mm-dd HH:MM', …], con las 00 del día siguiente si está."""
        self._horas_viento = horas
        zona = ZoneInfo(config.pide("proyeccion", "zona_horaria"))
        self._horas_oficial = [dt.datetime.fromisoformat(h).replace(tzinfo=dt.timezone.utc).astimezone(zona) for h in horas]
        self.hora_viento.setEnabled(True)
        self.btn_play.setEnabled(True)
        self.reproductor.setVisible(True)
        # de 00:00 a 23:45 si está la hora siguiente; si no, hasta la última hora
        n = len(horas)
        self.hora_viento.setMaximum(4 * (n - 1) - 1 if n % 24 == 1 and n > 1 else 4 * max(0, n - 1))
        self._hora_viento_cambiada(self.hora_viento.value())

    def _hora_viento_cambiada(self, q):
        horas = getattr(self, "_horas_viento", None)
        if not horas:
            return
        h, f = q // 4, (q % 4) / 4
        k = min(h, len(horas) - 1)
        m = f"{15 * (q % 4):02d}"
        self.lbl_hora_viento.setText(f"{horas[k][11:13]}:{m} UTC · {self._horas_oficial[k]:%H}:{m} oficial")
        self.lbl_dia_repro.setText(f"{self._horas_oficial[k]:%d/%m/%Y}")
        fr = self.franja.horas()
        self.franja.marcar(h if fr and h < len(fr) and fr[0][:10] == horas[0][:10] else None)
        self.vientoHora.emit(h, f)

    def horas_reproductor(self):
        return getattr(self, "_horas_viento", None)

    def ocultar_reproductor(self):
        self.btn_play.setChecked(False)
        self._horas_viento = None
        self.reproductor.setVisible(False)

    def set_sin_reproductor(self, si):
        """Simular con el reanálisis: sin el reproductor (son sus años, no hay horas que mover); al salir, vuelve si hay un día cargado."""
        if si:
            self.btn_play.setChecked(False)
        self.reproductor.setVisible(not si and bool(self.horas_reproductor()))

    def _play_viento(self, si):
        tema.pon_icono(self.btn_play, "pausa" if si else "play", "sobre_acento", 18)
        if si:
            self._reloj.start()
        else:
            self._reloj.stop()

    def _avanza_viento(self):
        """Un cuarto de hora más (al final del día vuelve a las 00:00)."""
        s = self.hora_viento
        s.setValue((s.value() + 1) % (s.maximum() + 1))

    def mostrar_viento(self, si):
        """El día del reanálisis, con ese horizonte. Al cambiar de horizonte se quita el viento del mapa: el día ya no está cargado."""
        self.caja_viento.setVisible(si)
        self.set_viento_planta([], None)
        if not si:
            self.ocultar_reproductor()

    def horizonte_meteo(self):
        return next(c for c, r in self._radios_meteo.items() if r.isChecked())

    def set_horizonte_meteo(self, clave):
        self._radios_meteo[clave].setChecked(True)

    def preparar_dia_viento(self, fecha):
        """Página de meteorología, horizonte Reanálisis y `fecha` («aaaa-mm-dd») en el calendario
        (arranque con --dia)."""
        self.ir_a("meteo")
        self.set_horizonte_meteo("reanalisis")
        self.calendario.elegir(dt.date.fromisoformat(fecha))
        self._dia_viento_elegido()

    # ── Núcleos y edificios ──────────────────────────────────────────────────────────────
    # el icono de cada familia de núcleos (con su color, el de su punto en el mapa)
    ICONOS_NUCLEO = {"residencial": "casas", "industrial": "fabrica", "deportivo": "deporte"}

    def _seccion_edificios(self):
        """Los núcleos de población, en tres cifras (cuántos de cada familia y el más cercano), y los edificios de al lado de la planta: solo
        cuántos hay de cada uso y el botón (decisión del usuario, 2026-10-24), en etiquetas; la fecha de descarga, al pasar por encima."""
        r = config.RADIO_EDIFICIOS_KM
        sec = Tarjeta("Núcleos y edificios")
        self.tarj_edificios = sec
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(6)
        self.cifras_nucleos = {}
        for familia in NOMBRE_NUCLEO:
            caja = QtWidgets.QFrame(objectName="cifra")
            v = QtWidgets.QVBoxLayout(caja)
            v.setContentsMargins(9, 8, 9, 8)
            v.setSpacing(2)
            arriba = QtWidgets.QHBoxLayout()
            arriba.setSpacing(6)
            ico = QtWidgets.QLabel()
            tema.pon_icono(ico, self.ICONOS_NUCLEO[familia], f"fam_{familia}", 18)
            valor = QtWidgets.QLabel("—", objectName="cifra_v")
            arriba.addWidget(ico)
            arriba.addWidget(valor)
            arriba.addStretch()
            v.addLayout(arriba)
            texto = QtWidgets.QLabel(objectName="nota", textFormat=QtCore.Qt.TextFormat.RichText)
            v.addWidget(texto)
            self.cifras_nucleos[familia] = (valor, texto)
            fila.addWidget(caja, 1)
        sec.cuerpo.addLayout(fila)
        sec.cuerpo.addSpacing(4)
        sec.cuerpo.addWidget(QtWidgets.QLabel(
            f"EDIFICIOS A MENOS DE {_num(config.RADIO_EDIFICIOS_FOCOS_M)} M ({config.pide('fuentes', 'edificios').upper()})", objectName="seccion"))
        self.lbl_edificios = QtWidgets.QLabel(wordWrap=True, textFormat=QtCore.Qt.TextFormat.RichText)
        sec.cuerpo.addWidget(self.lbl_edificios)
        self.barra_edificios = QtWidgets.QProgressBar(textVisible=True)
        self.barra_edificios.setRange(0, 100)
        self.barra_edificios.hide()
        sec.cuerpo.addWidget(self.barra_edificios)
        self.b_edificios = QtWidgets.QPushButton(f"Descargar edificios ({_km(r)} km)")
        self.b_edificios.clicked.connect(self.descargarEdificios)
        sec.cuerpo.addWidget(self.b_edificios)
        self.b_ver_edificios = self._boton_capa("edificios", "edificios")
        sec.cuerpo.addWidget(self.b_ver_edificios)
        # los edificios de la planta, los de la estela de las chimeneas (usuario, 2026-11-08: «configurar los edificios vía 3 caminos [los
        # descargados, el LiDAR y dibujar/modificar desde el usuario administrador], todo en Planta y en el menú de edificios»): cuántos de cada
        # origen, en 3D (usuario, 2026-11-08: «el visor 3D de estos edificios, como hicimos para los focos de punto, en el menú de edificios
        # de planta»; los ve también el usuario normal) y, para el administrador, los tres caminos
        sec.cuerpo.addSpacing(4)
        sec.cuerpo.addWidget(QtWidgets.QLabel("EDIFICIOS DE LA PLANTA", objectName="seccion"))
        self.lbl_edificios_planta = QtWidgets.QLabel(wordWrap=True, textFormat=QtCore.Qt.TextFormat.RichText)
        sec.cuerpo.addWidget(self.lbl_edificios_planta)
        from teodors.gui.focos_graficos import VisorEdificios
        self.visor_edificios = VisorEdificios(alto=250)
        sec.cuerpo.addWidget(self.visor_edificios)
        self.fila_edificios_admin = QtWidgets.QWidget()
        fila = QtWidgets.QHBoxLayout(self.fila_edificios_admin)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(6)
        self.botones_edificios = {}
        from teodors.operacion.edificios_planta import nombre_origen
        fuente = nombre_origen("catastro")
        for clave, texto, ayuda in (("catastro", f"De {fuente}", f"Las huellas y las alturas de {fuente} (plantas × 3 m)"),
                                    ("lidar", "Del LiDAR", f"Las huellas de {fuente} con la altura que mide el LiDAR, y lo que el LiDAR ve y {fuente} "
                                                           "no tiene"),
                                    ("dibujo", "Dibujar…", "Crear, redibujar, cambiar la altura o eliminar edificios en el plano")):
            b = QtWidgets.QPushButton(texto, objectName="primario" if clave == "dibujo" else "")
            b.setToolTip(ayuda)
            b.clicked.connect(self.editarEdificios if clave == "dibujo" else (lambda _=False, c=clave: self.importarEdificios.emit(c)))
            fila.addWidget(b, 1)
            self.botones_edificios[clave] = b
        sec.cuerpo.addWidget(self.fila_edificios_admin)
        self.fila_edificios_admin.setVisible(bool(config.MODO_EDICION))
        self.set_edificios_planta(None)
        return sec

    def set_edificios_planta(self, resumen, edificios=None):
        """Cuántos edificios tiene la planta y de qué origen (`edificios_planta.resumen`) y, en 3D, `edificios` (los de
        `edificios_planta.cargar`); None o ninguno: la estela usa los descargados, y sin visor."""
        hay = bool(resumen and resumen.get("total"))
        self.visor_edificios.setVisible(hay and bool(edificios))
        if hay and edificios:
            self.visor_edificios.poner(edificios, self.visor_edificios.elegido(), encuadrar=True)
        if not hay:
            tema.texto(self.lbl_edificios_planta, "<span style='color:$tenue'>Sin edificios propios: la estela usa los descargados, con la "
                                                  "altura del LiDAR.</span>")
            return
        from teodors.operacion.edificios_planta import nombre_origen
        def parte(o, k):
            if o == "dibujo":
                return f"{k} dibujado{'s' if k != 1 else ''}"
            return f"{k} {'del' if o == 'lidar' else 'de'} {nombre_origen(o)}"
        partes = [parte(o, k) for o, k in resumen["por_origen"].items() if k]
        tema.texto(self.lbl_edificios_planta, f"<b>{resumen['total']} edificios</b> · " + " · ".join(partes))

    def set_edificios(self, info):
        from teodors.fuentes.catastro import USO_COLOR
        self.b_edificios.setVisible(info is None)
        self.b_ver_edificios.setVisible(info is not None)
        if info is None:
            tema.texto(self.lbl_edificios, "<span style='color:$aviso'>Sin descargar.</span>")
            self.lbl_edificios.setToolTip("")
            return
        # (los edificios ya no van en la ficha de arriba: su cifra es ahora lo que rodea la planta; usuario, 2026-11-16)
        # solo el número por categoría y el botón (decisión del usuario, 2026-10-24), en etiquetas; la fecha, al pasar por encima
        tema.texto(self.lbl_edificios, "&nbsp;&nbsp;".join(
            f"<span style='color:{USO_COLOR.get(u, '#999')};font-size:15px'>●</span>&nbsp;{html.escape(u)}&nbsp;<b>{k}</b>"
            for u, k in info["por_uso"].items()) or "<span style='color:$tenue'>Ninguno</span>")
        self.lbl_edificios.setToolTip(f"Descargados el {info['fecha'][:16].replace('T', ' ')}")

    # ── Focos de emisión (el operario los consulta; se cambian en el modo de edición) ────────────────────
    def _seccion_focos(self):
        """La página Focos (usuario, 2026-11-08: «imagen del mapa con los focos, y seguido el botón de configuración del foco (altura,
        caudal, temperatura, especies, área, volumen, punto). Después la lista de focos y un calendario igual que el del viento pero con
        olores y gases, y debajo de él el botón de configuración de la operabilidad»; después: «la lista también dependerá del plan
        seleccionado, como en el calendario: que primero salga el calendario y luego el total de emisiones»). Encima del calendario, el plan
        y lo que se mira (el olor o un gas), que valen para los dos; la lista, lo que emite cada foco el día elegido en el calendario."""
        from teodors.gui.focos_graficos import BarrasEmision, CalendarioEmision, FranjaEmision, PlanoFocos
        self._catalogo, self._mag, self._tope_emision, self._esc_emision = None, "olor", 0.0, {}
        sec = Tarjeta("Focos de emisión")
        self.tarj_focos = sec
        self.plano_focos = PlanoFocos()
        sec.cuerpo.addWidget(self.plano_focos)
        # del mismo color que «Configurar la operación…» (usuario, 2026-11-08)
        self.b_conf_focos = QtWidgets.QPushButton(self._texto_conf_focos(config.MODO_EDICION), objectName="primario")
        tema.pon_icono(self.b_conf_focos, "focos", "sobre_acento", 16)
        self.b_conf_focos.setToolTip("Altura, caudal, temperatura, especies y geometría (área, volumen o punto) de cada foco")
        self.b_conf_focos.clicked.connect(self.verFocos)
        sec.cuerpo.addWidget(self.b_conf_focos)

        self.tarj_lista_focos = Tarjeta("Emisión por foco")
        self.barras_emision = BarrasEmision()
        self.barras_emision.sobre.connect(self.plano_focos.resaltar)
        self.tarj_lista_focos.cuerpo.addWidget(self.barras_emision)

        self.tarj_operacion = Tarjeta("Calendario de emisión")
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(8)
        fila.addWidget(QtWidgets.QLabel("Plan", objectName="nota"))
        self.cmb_plan_focos = QtWidgets.QComboBox()
        self.cmb_plan_focos.addItem("Base", None)
        self.cmb_plan_focos.currentIndexChanged.connect(lambda _: self._pintar_emision())
        fila.addWidget(self.cmb_plan_focos, 1)
        self.tarj_operacion.cuerpo.addLayout(fila)
        self.rejilla_mag = QtWidgets.QGridLayout()                # el olor o un gas: para el calendario y para la lista
        self.rejilla_mag.setSpacing(6)
        self.tarj_operacion.cuerpo.addLayout(self.rejilla_mag)
        self.botones_mag = {}
        self.cal_emision = CalendarioEmision()
        self.cal_emision.elegido_cambiado.connect(self._dia_emision)
        self.tarj_operacion.cuerpo.addWidget(self.cal_emision)
        self.franja_emision = FranjaEmision()
        self.tarj_operacion.cuerpo.addWidget(self.franja_emision)
        self.b_operacion = QtWidgets.QPushButton("Configurar la operación…", objectName="primario")
        tema.pon_icono(self.b_operacion, "calendario", "sobre_acento", 16)
        self.b_operacion.setToolTip("Los planes de operación: cuánto emite cada foco cada día y a cada hora")
        self.b_operacion.clicked.connect(self.verPlanes)
        self.tarj_operacion.cuerpo.addWidget(self.b_operacion)
        for t in (self.tarj_lista_focos, self.tarj_operacion):
            t.setVisible(False)                                 # hasta que lleguen los focos (set_focos)
        return [sec, self.tarj_operacion, self.tarj_lista_focos]

    def set_focos(self, datos):
        focos = (datos or {}).get("focos", [])
        self._catalogo = datos if focos else None
        self.plano_focos.poner(focos=focos)
        self.tarj_focos.setToolTip(f"Focos actualizados el {datos.get('actualizado', '?')}" if focos else "")
        for t in (self.tarj_lista_focos, self.tarj_operacion):
            t.setVisible(bool(focos))
        self._estado.update(focos=len(focos))
        self._pintar_inicio()
        if focos:
            self._poner_magnitudes()
            self._pintar_emision()

    def set_admin(self, activo):
        """El usuario cambia (normal o administrador): el botón de los focos dice si se configuran o se consultan; los tres caminos de los
        edificios de la planta, solo el administrador."""
        self.b_conf_focos.setText(self._texto_conf_focos(activo))
        self.fila_edificios_admin.setVisible(bool(activo))

    @staticmethod
    def _texto_conf_focos(activo):
        """El botón de los focos: el administrador los configura; el usuario normal solo los ve (usuario, 2026-11-09: «en el panel lateral
        debe poner ver focos, ya que el usuario no puede modificarlos»)."""
        return f"Configurar los focos ({config.pide('operacion', 'texto_modo_edicion')})…" if activo else "Ver focos…"

    def set_huellas(self, huellas):
        """Las huellas de los edificios cercanos a la planta ([[(x, y), …]] en UTM), para el plano de los focos."""
        self.plano_focos.poner(huellas=huellas)

    def set_ortofoto(self, ortofoto):
        """La ortofoto bajo el plano de los focos: la info de `fuentes.ortofoto` (con «ruta»)."""
        if ortofoto:
            self.plano_focos.poner(ortofoto=ortofoto)

    def _poner_magnitudes(self):
        """Un botón por lo que se emite (el olor y cada gas que emite algún foco), encima del calendario: en una fila o, si son muchos, en
        dos. Se queda lo elegido si sigue."""
        from teodors.operacion import focos as F
        try:
            mags = [(m["clave"], m["nombre"]) for m in F.magnitudes(self._catalogo)]
        except Exception as e:                                 # noqa: BLE001 (un foco a medias no tumba la página)
            log.warning("No se sabe qué emiten los focos: %s", e)
            mags = []
        mags = mags or [("olor", "Olor")]
        while self.rejilla_mag.count():
            w = self.rejilla_mag.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        self.botones_mag = {}
        por_fila = len(mags) if len(mags) <= 6 else -(-len(mags) // 2)
        for k, (clave, nombre) in enumerate(mags):
            b = QtWidgets.QPushButton(nombre, objectName="chip_mag", checkable=True)
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=clave: self._elegir_magnitud(c))
            self.rejilla_mag.addWidget(b, k // por_fila, k % por_fila)
            self.botones_mag[clave] = b
        for c in range(8):
            self.rejilla_mag.setColumnStretch(c, 1 if c == por_fila else 0)
        if self._mag not in self.botones_mag:
            self._mag = mags[0][0]
        self.botones_mag[self._mag].setChecked(True)
        for b in self.botones_mag.values():
            b.setVisible(len(mags) > 1)

    def _elegir_magnitud(self, clave):
        self._mag = clave
        for c, b in self.botones_mag.items():
            b.setChecked(c == clave)
        self._pintar_emision()

    def _plan_calendario(self):
        """El plan que pinta el calendario: el elegido encima de él o, si no se puede leer, la Base."""
        from teodors.operacion import planes as E
        ruta = self.cmb_plan_focos.currentData()
        if ruta:
            try:
                return E.cargar(ruta)
            except (ValueError, OSError) as e:
                log.warning("No se puede leer el plan %s: %s", ruta, e)
        return E.base(self._catalogo)

    def _pintar_emision(self):
        """El calendario de emisión y la lista de los focos, con lo elegido (el olor o un gas) y el plan del calendario."""
        from teodors.operacion import focos as F, planes as E
        cat = self._catalogo
        if not cat:
            return
        mag, unidad = self._mag, E.unidad_emision(self._mag)
        nombre = "olor" if mag == "olor" else F.NOMBRES.get(mag, mag)
        esc = self._plan_calendario()
        self._esc_emision = esc
        ini, fin = E.dias_calendario(esc)
        try:
            dias = E.emision_dias(esc, cat, mag, [ini + dt.timedelta(days=k) for k in range((fin - ini).days + 1)])
            tope = E.emision_maxima(cat, mag)
        except Exception as e:                                 # noqa: BLE001 (un foco o un plan a medias no tumba la página)
            log.warning("No se puede pintar el calendario de emisión: %s", e)
            dias, tope = {}, 0.0
        self._tope_emision = tope
        self.tarj_operacion.titulo.setText(f"Calendario de emisión · {nombre}")
        cal = self.cal_emision
        cal.poner_escala("escala_olor" if mag == "olor" else "escala_gases", tope, unidad)
        cal.poner_rango(ini, fin)
        cal.poner_dias(dias)
        cal.elegir(cal.elegido() or dt.date.today())
        self._dia_emision(cal.elegido().isoformat())

    def _dia_emision(self, iso):
        """El día elegido en el calendario de emisión: sus horas, en la franja; y lo que emite cada foco ese día con el plan, en la lista."""
        from teodors.operacion import focos as F, planes as E
        dia = dt.date.fromisoformat(iso)
        info = self.cal_emision.info(dia) or {}
        unidad = E.unidad_emision(self._mag)
        self.franja_emision.poner(info.get("modelos"), self._tope_emision, unidad, "escala_olor" if self._mag == "olor" else "escala_gases")
        cat = self._catalogo
        if not cat:
            return
        try:
            por_foco = E.emision_focos_dia(self._esc_emision, cat, self._mag, dia)
        except Exception as e:                                 # noqa: BLE001 (un foco a medias no tumba la página)
            log.warning("No se puede calcular la emisión de cada foco: %s", e)
            por_foco = {}
        self.barras_emision.poner([(f.get("id"), f.get("nombre") or str(f.get("id")), f.get("modelo"), por_foco.get(f.get("id")))
                                   for f in cat["focos"]], unidad)
        nombre = "olor" if self._mag == "olor" else F.NOMBRES.get(self._mag, self._mag)
        self.tarj_lista_focos.titulo.setText(f"Emisión por foco · {dia.day}/{dia.month}/{dia.year} · {nombre}, {unidad}")

    # ── Simulación ───────────────────────────────────────────────────────────────────────
    def _seccion_simulacion(self):
        """Simular (usuario, 2026-11-09: «organizar mucho mejor el panel de simular, lo veo poco organizado y algo caótico»). Con el
        reanálisis, el plan y tres botones: «Simular reanálisis», «Guardar resultados» y «Cargar resultados»; al acabar, debajo, la tabla
        del olor y de cada contaminante con su media, su máximo y su P98, lo que se ve en el mapa (cuál de las tres, en isolíneas rellenas
        o en degradado) y los lugares. Sin un día ni su penacho: son sus años; el penacho hora a hora es del episodio de queja y de la
        predicción, que simulan su periodo con el mismo botón."""
        sec = Tarjeta("Simular")
        self.tarj_simular = sec
        # con el reanálisis, dos modos (usuario, 2026-11-09): simular un escenario o comparar dos ya simulados
        self.fila_modo = QtWidgets.QWidget()
        fm = QtWidgets.QHBoxLayout(self.fila_modo)
        fm.setContentsMargins(0, 0, 0, 0)
        fm.setSpacing(6)
        self._grupo_modo = QtWidgets.QButtonGroup(self, exclusive=True)
        self._b_modo = {}
        for clave, texto in (("simular", "Simular escenario"), ("comparar", "Comparar escenarios")):
            b = QtWidgets.QPushButton(texto, objectName="chip_mag", checkable=True, checked=clave == "simular")
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=clave: self._elegir_modo(c))
            self._grupo_modo.addButton(b)
            self._b_modo[clave] = b
            fm.addWidget(b)
        fm.addStretch()
        sec.cuerpo.addWidget(self.fila_modo)
        self._modo = "simular"
        self.lbl_sim_meteo = QtWidgets.QLabel(objectName="nota", wordWrap=True)
        sec.cuerpo.addWidget(self.lbl_sim_meteo)
        self.caja_simular = QtWidgets.QWidget()
        cs = QtWidgets.QVBoxLayout(self.caja_simular)
        cs.setContentsMargins(0, 0, 0, 0)
        cs.setSpacing(8)
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(8)
        fila.addWidget(QtWidgets.QLabel("Plan de operación"))
        self.cmb_plan = QtWidgets.QComboBox()
        fila.addWidget(self.cmb_plan, 1)
        cs.addLayout(fila)
        self.b_simular = QtWidgets.QPushButton("Simular reanálisis", objectName="primario")
        self.b_simular.clicked.connect(self._pulsar_simular)
        cs.addWidget(self.b_simular)
        self.fila_archivo = QtWidgets.QWidget()
        f2 = QtWidgets.QHBoxLayout(self.fila_archivo)
        f2.setContentsMargins(0, 0, 0, 0)
        f2.setSpacing(8)
        self.b_guardar_res = QtWidgets.QPushButton("Guardar resultados")
        tema.pon_icono(self.b_guardar_res, "descarga", "texto", 15)
        self.b_guardar_res.setToolTip("Guardar este caso con un nombre: una carpeta «AAAA-MM-DD-nombre» con los resultados y la operación de los focos")
        self.b_guardar_res.clicked.connect(self.guardarResultados)
        self.b_cargar_res = QtWidgets.QPushButton("Cargar resultados")
        tema.pon_icono(self.b_cargar_res, "carpeta", "texto", 15)
        self.b_cargar_res.setToolTip("Abrir un caso guardado y verlo en el mapa")
        self.b_cargar_res.clicked.connect(self.cargarResultados)
        for b in (self.b_guardar_res, self.b_cargar_res):
            b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Fixed)
            f2.addWidget(b, 1)
        cs.addWidget(self.fila_archivo)
        sec.cuerpo.addWidget(self.caja_simular)
        # comparar: dos escenarios ya simulados o guardados, y el botón
        self.caja_comparar = QtWidgets.QWidget()
        cc = QtWidgets.QGridLayout(self.caja_comparar)
        cc.setContentsMargins(0, 0, 0, 0)
        cc.setHorizontalSpacing(8)
        cc.setVerticalSpacing(8)
        self.cmb_ref, self.cmb_comp = QtWidgets.QComboBox(), QtWidgets.QComboBox()
        for fila_, (texto, cmb, ayuda) in enumerate((("Referencia", self.cmb_ref, "El escenario del que se parte: el cambio se mide respecto a él"),
                                                      ("Comparar con", self.cmb_comp, "El escenario distinto: cuánto sube o baja respecto a la referencia"))):
            etiqueta = QtWidgets.QLabel(texto)
            etiqueta.setToolTip(ayuda)
            cmb.setToolTip(ayuda)
            cmb.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            cmb.activated.connect(lambda _=0, c=cmb: self._escenario_elegido(c))
            cc.addWidget(etiqueta, fila_, 0)
            cc.addWidget(cmb, fila_, 1)
        cc.setColumnStretch(1, 1)
        self.b_comparar = QtWidgets.QPushButton("Comparar escenarios", objectName="primario")
        self.b_comparar.clicked.connect(lambda: self.compararEscenarios.emit(self.cmb_ref.currentData(), self.cmb_comp.currentData()))
        cc.addWidget(self.b_comparar, 2, 0, 1, 2)
        sec.cuerpo.addWidget(self.caja_comparar)
        self._previo = {}
        self._combo_zip = None
        self.barra_sim = QtWidgets.QProgressBar(minimum=0, maximum=100, textVisible=False)
        self.barra_sim.setFixedHeight(6)
        self.barra_sim.setVisible(False)
        sec.cuerpo.addWidget(self.barra_sim)
        self.lbl_sim = QtWidgets.QLabel(objectName="nota", wordWrap=True, openExternalLinks=True)
        self.lbl_sim.setVisible(False)
        sec.cuerpo.addWidget(self.lbl_sim)

        # el reanálisis: la tabla de los pueblos, del olor. Qué se ve en el mapa (la media, el máximo o el P98) y cómo (isolíneas o degradado),
        # en la barra de encima del mapa; y solo el olor, sin los gases (usuario, 2026-11-17). Los botones de las capas, ocultos: llevan cuál
        # está encendida, al día con la barra y con el selector de capas del mapa
        self.sec_res = Tarjeta("Resultados")
        self.lbl_res = QtWidgets.QLabel(objectName="nota", wordWrap=True)
        self.sec_res.cuerpo.addWidget(self.lbl_res)
        self.botones_mag_res = {}
        for capa, nombre in (("media", "Media"), ("maximo", "Máximo"), ("norma", "P98")):
            self._boton_capa(f"plan_{capa}", nombre, chip=True, oculto=True)
        self._b_estilo = {}
        self._estilo = "isolineas"
        self.lbl_pueblos = QtWidgets.QLabel(objectName="titulo_menu", wordWrap=True)
        self.sec_res.cuerpo.addSpacing(4)
        self.sec_res.cuerpo.addWidget(self.lbl_pueblos)
        self.res_anios = BloqueResultado(self, "plan", pueblos=True)
        self.res_anios.setVisible(True)
        self.sec_res.cuerpo.addWidget(self.res_anios)
        self.sec_res.setVisible(False)

        # la comparación de dos escenarios: el olor o un gas, el estadístico en el mapa, los criterios del olor y los pueblos
        self.sec_comp = Tarjeta("Comparación")
        self.lbl_comp = QtWidgets.QLabel(objectName="nota", wordWrap=True)
        self.sec_comp.cuerpo.addWidget(self.lbl_comp)
        self.b_informe_comp = QtWidgets.QPushButton("Informe de la comparación (PDF)")
        self.b_informe_comp.setToolTip("El informe de los dos escenarios: lo común (la planta, los focos y la meteorología), la operación de los "
                                       "dos, los resultados de cada uno y la comparación. Va a la carpeta de los casos del reanálisis, en "
                                       "«comparaciones» (unos 2 minutos; la app sigue mientras).")
        self.b_informe_comp.clicked.connect(self.informeComparacion)
        self.sec_comp.cuerpo.addWidget(self.b_informe_comp)
        # el cambio de la media, el máximo o el P98, en la barra de encima del mapa; solo el olor (usuario, 2026-11-17)
        self.botones_mag_comp = {}
        for capa, nombre in (("media", "Media"), ("maximo", "Máximo"), ("norma", "P98")):
            self._boton_capa(f"comp_{capa}", nombre, chip=True, oculto=True)
        self.lbl_criterios = QtWidgets.QLabel(wordWrap=True)
        self.sec_comp.cuerpo.addSpacing(4)
        self.sec_comp.cuerpo.addWidget(self.lbl_criterios)
        self.lbl_pueblos_comp = QtWidgets.QLabel(objectName="titulo_menu", wordWrap=True)
        self.sec_comp.cuerpo.addSpacing(4)
        self.sec_comp.cuerpo.addWidget(self.lbl_pueblos_comp)
        self.tabla_comp = TablaCambio()
        self.sec_comp.cuerpo.addWidget(self.tabla_comp)
        self.sec_comp.setVisible(False)
        self._comp, self._mag_comp, self._estad_comp, self._comparando = None, None, "norma", False

        # el episodio de queja y la predicción: su resultado, con el penacho
        self.sec_periodo = Tarjeta("Resultado")
        self.cmb_magnitud = QtWidgets.QComboBox()
        self.cmb_magnitud.currentIndexChanged.connect(lambda _: self._magnitud_periodo_elegida())
        self.cmb_magnitud.setVisible(False)                 # solo el olor (usuario, 2026-11-17): siempre oculto
        self.sec_periodo.cuerpo.addWidget(self.cmb_magnitud)
        self._b_estilo_periodo = {}                         # isolíneas o degradado: en la barra de encima del mapa
        self.res_periodo = BloqueResultado(self, "dia", penacho=True, solo_pueblos=True)
        self.sec_periodo.cuerpo.addWidget(self.res_periodo)
        self.sec_periodo.setVisible(False)
        self._hay_respuestas, self._simulando, self._calculando_3d, self._archivando = False, False, False, False
        self._res = {"anios": None, "periodo": None}
        self._mag_res, self._formato, self._t0_sim, self._periodo_rea = None, None, None, None
        self.horizonteMeteo.connect(lambda _: self._actualizar_simular())
        self._actualizar_simular()
        return [sec, self.sec_res, self.sec_comp, self.sec_periodo]

    def _pulsar_simular(self):
        """El botón principal: simula lo de la opción de Meteorología o, mientras se simula, lo cancela."""
        if self._simulando:
            self.b_simular.setEnabled(False)
            self.b_simular.setText("Cancelando…")
            self.cancelarSimulacion.emit()
        elif self.horizonte_meteo() == "reanalisis":
            self.simular.emit(self.cmb_plan.currentData())
        else:
            self.simularPeriodo.emit(self.cmb_plan.currentData())

    def set_planes(self, lista, hay_respuestas):
        """Planes guardados [(nombre, ruta)] para elegir, y si ya se puede calcular."""
        from teodors.operacion import simulacion
        actual = self.cmb_plan.currentData()
        self.cmb_plan.clear()
        self.cmb_plan.addItem("Base", None)
        for nombre, ruta in lista:
            self.cmb_plan.addItem(nombre, ruta)
        self.cmb_plan.setCurrentIndex(max(self.cmb_plan.findData(actual), 0))
        self._hay_respuestas = hay_respuestas
        self._periodo_rea = simulacion.periodo_reanalisis() if hay_respuestas else None
        self._estado["planes"] = len(lista)
        # en la página Focos: el plan del calendario de emisión, que se repinta (el elegido puede haber cambiado)
        actual = self.cmb_plan_focos.currentData()
        self.cmb_plan_focos.blockSignals(True)
        self.cmb_plan_focos.clear()
        self.cmb_plan_focos.addItem("Base", None)
        for nombre, ruta in lista:
            self.cmb_plan_focos.addItem(nombre, ruta)
        self.cmb_plan_focos.setCurrentIndex(max(self.cmb_plan_focos.findData(actual), 0))
        self.cmb_plan_focos.blockSignals(False)
        self._pintar_emision()
        self._actualizar_simular()

    def _texto_periodo_rea(self):
        """«Del d/m/aaaa al d/m/aaaa · N horas»: los días del reanálisis con respuesta de los focos."""
        p = self._periodo_rea
        if p is None:
            return texto_anios(None)
        ini, fin = (dt.date.fromisoformat(p[k]) for k in ("ini", "fin"))
        return f"Del {ini.day}/{ini.month}/{ini.year} al {fin.day}/{fin.month}/{fin.year} · {_num(p['horas'])} horas"

    def _actualizar_simular(self):
        h = self.horizonte_meteo()
        ocupado = self._simulando or self._calculando_3d or self._archivando or self._comparando
        rea, per = h == "reanalisis", h in periodos.DIAS
        comparar = rea and self._modo == "comparar"
        if comparar:
            titulo, boton, listo = f"Reanálisis · {texto_anios(self._periodo_rea)}", "Simular reanálisis", False
            texto = "Dos escenarios ya simulados: cuánto sube o baja cada sitio, en %, respecto a la referencia"
        elif rea:
            titulo, boton = f"Reanálisis · {texto_anios(self._periodo_rea)}", "Simular reanálisis"
            texto = self._texto_periodo_rea() if self._hay_respuestas else "Faltan las respuestas de los focos del reanálisis"
            listo = self._hay_respuestas
        elif per:
            p = self.periodo()
            # «Simular episodio» solo necesita que el VIENTO esté listo: las respuestas (puff) las prepara al vuelo `calcular_periodo_preparando`.
            # La predicción prepara viento + respuestas de una vez (botón «Preparar»), así que sigue gateada por `listo` (respuestas).
            if p is None:
                listo = False
            elif h == "queja":
                listo = bool(periodos.fuente(p))
            else:
                listo = periodos.listo(p)
            titulo, boton = periodos.MODOS[h], {"queja": "Simular episodio", "prediccion": "Simular predicción"}[h]
            if p is None:
                texto = "Elige el día en <b>Meteo</b>" if h == "queja" else "Prepara la predicción en <b>Meteo</b>"
            else:
                texto = periodos.etiqueta(p) + ("" if listo else (" · simula o carga el viento en <b>Meteo</b>" if h == "queja" else " · falta prepararlo en <b>Meteo</b>"))
        else:
            titulo, boton, texto, listo = "Simular", "Simular", "Elige primero la meteorología en <b>Meteo</b>", False
        self.tarj_simular.titulo.setText(titulo)
        self.lbl_sim_meteo.setText(texto)
        if bool(self.b_simular.property("cancelar")) != self._simulando:      # mientras se simula, «Cancelar» no es la acción principal
            self.b_simular.setProperty("cancelar", self._simulando)
            self.b_simular.style().unpolish(self.b_simular)
            self.b_simular.style().polish(self.b_simular)
        if self._simulando:
            if self.b_simular.isEnabled():
                self.b_simular.setText("Cancelar")
        else:
            self.b_simular.setText(boton)
            self.b_simular.setEnabled(listo and not ocupado)
        self.cmb_plan.setEnabled(not ocupado)
        self.fila_archivo.setVisible((rea and not comparar) or per)   # guardar/cargar resultados también en episodio/predicción
        self.b_guardar_res.setEnabled((self._res["anios"] if rea else self._res["periodo"]) is not None and not ocupado)
        self.b_cargar_res.setEnabled(not ocupado)
        hay_rea = rea and not comparar and self._res["anios"] is not None and not self._simulando
        self.sec_res.setVisible(hay_rea)
        self.fila_modo.setVisible(rea)
        self.caja_simular.setVisible(not comparar)
        self.caja_comparar.setVisible(comparar)
        ref, otro = self.cmb_ref.currentData(), self.cmb_comp.currentData()
        self.b_comparar.setEnabled(bool(ref) and bool(otro) and "__abrir__" not in (ref, otro) and ref != otro and not ocupado)
        self.b_comparar.setToolTip("Elige dos escenarios distintos" if ref and ref == otro else "")
        for c in (self.cmb_ref, self.cmb_comp):
            c.setEnabled(not ocupado)
        self.sec_comp.setVisible(comparar and self._comp is not None and not self._comparando)
        self.b_informe_comp.setEnabled(self._comp is not None and not ocupado)
        self.sec_periodo.setVisible(per and self._res["periodo"] is not None and not self._simulando)
        self._estado["horizonte"] = h
        self._pintar_inicio()

    def periodo_simulacion(self):
        """Lo que simula el botón con el episodio o la predicción: su periodo (con el reanálisis no hay un día suelto)."""
        return self.periodo()

    def set_simulando(self, si, periodo=False):
        """Mientras se simula, el botón la cancela y los resultados se ocultan hasta que acaba."""
        self._simulando = si
        self.b_simular.setEnabled(True)
        self.barra_sim.setVisible(si)
        self.barra_sim.setValue(0)
        self.lbl_sim.setVisible(si)
        if si:
            self._t0_sim = time.monotonic()
            self.lbl_sim.setText("Empezando…")
        self._actualizar_simular()

    def fin_simulacion(self):
        self._simulando = False
        self.b_simular.setEnabled(True)
        self.barra_sim.setVisible(False)
        self._actualizar_simular()

    @staticmethod
    def _duracion(s):
        s = int(round(s))
        if s < 60:
            return f"{s} s"
        if s < 3600:
            return f"{s // 60} min {s % 60:02d} s" if s < 600 else f"{round(s / 60)} min"
        return f"{s // 3600} h {s % 3600 // 60:02d} min"

    def set_progreso_simulacion(self, pct, mensaje):
        """La barra y lo que se está haciendo, con el tiempo que lleva y, en cuanto se puede estimar, lo que queda."""
        self.barra_sim.setValue(pct)
        lleva = time.monotonic() - (self._t0_sim or time.monotonic())
        tiempo = f"{pct} % · lleva {self._duracion(lleva)}"
        if 3 <= pct < 100 and lleva > 5:
            tiempo += f" · quedan ≈ {self._duracion(lleva * (100 - pct) / pct)}"
        self.lbl_sim.setText(f"{html.escape(mensaje)}<br>{tiempo}")

    def set_fallo_simulacion(self, mensaje):
        self.lbl_sim.setVisible(True)
        self.lbl_sim.setText("Cancelado: no se ha guardado nada." if "cancelado" in mensaje.lower() else
                             f"No se pudo simular: {html.escape(mensaje)}")

    def set_archivando(self, si, texto=""):
        """Mientras se guardan o se cargan unos resultados; al acabar, `texto` dice cómo ha ido."""
        self._archivando = si
        self.lbl_sim.setVisible(bool(texto))
        self.lbl_sim.setText(texto)
        self._actualizar_simular()

    def magnitud(self):
        """La magnitud elegida en los resultados: la fila de la tabla del reanálisis o la del desplegable del periodo."""
        if self.horizonte_meteo() == "reanalisis":
            return self._mag_res
        return self.cmb_magnitud.currentData()

    def set_resultado(self, r, cifra):
        """Muestra el resultado de una simulación; `cifra` da formato a las concentraciones."""
        self._formato = cifra
        if r["periodo"] is None:
            self._res["anios"] = r
            self._mag_res = solo_olor(r)
            self._poner_botones_mag(r)
            self.res_anios.orden_inicial(r["magnitudes"][self._mag_res])
            d = r.get("datos") or {}
            cuando = dt.datetime.strptime(r["fecha"], "%Y-%m-%d %H:%M")
            texto = f"Plan <b>{html.escape(r['nombre'] or 'Base')}</b> · simulado el {cuando:%d/%m/%Y a las %H:%M}"
            if r.get("segundos"):
                texto += f" en {self._duracion(r['segundos'])}"
            if d:
                texto += f"<br>{_num(d['dias'])} días · {_num(d['horas'])} horas"
            if r.get("caso"):
                texto += f"<br>Caso guardado <b>{html.escape(r['caso']['nombre'])}</b>"
            self.lbl_res.setText(texto)
            self._poner_magnitud_res()
        else:
            self._res["periodo"] = r
            actual = self.cmb_magnitud.currentData()
            self.cmb_magnitud.blockSignals(True)
            self.cmb_magnitud.clear()
            for k in r["orden"]:
                self.cmb_magnitud.addItem(r["magnitudes"][k]["nombre"], k)
            self.cmb_magnitud.setCurrentIndex(max(self.cmb_magnitud.findData(solo_olor(r)), 0))     # solo el olor (usuario, 2026-11-17)
            self.cmb_magnitud.blockSignals(False)
            self.res_periodo.orden_por_media()
            self.res_periodo.poner(r["magnitudes"][self.cmb_magnitud.currentData()], cifra)
            self.res_periodo.setVisible(True)
            self.sec_periodo.titulo.setText(f"Resultado · {r['nombre'] or 'Base'}")
        self.lbl_sim.setVisible(False)
        self._estado["simulado"] = r["nombre"]
        self._actualizar_simular()

    def _poner_botones_mag(self, r):
        """Antes, un botón por magnitud (el olor y cada gas). Desde la v0.1.11 solo se ve el olor (usuario, 2026-11-17: «se dejarán de
        visualizar los resultados para diferentes gases, solo se visualizan los resultados de olor»): ninguno."""
        self.botones_mag_res = {}

    def _poner_magnitud_res(self):
        """La tabla de los pueblos y el botón del P98 (o de la norma) con la magnitud elegida del reanálisis."""
        m = self._res["anios"]["magnitudes"][self._mag_res]
        for c, b in self.botones_mag_res.items():
            b.setChecked(c == self._mag_res)
        self.res_anios.poner(m, self._formato)
        self.lbl_pueblos.setText(f"PUEBLOS · {m['nombre']} ({m['unidad']})")
        norma = next((c for c in m["columnas"] if c["capa"] == "norma"), None)
        self._botones_capa["plan_norma"].setVisible(norma is not None)
        if norma is not None:
            self.nombrar_capa("plan_norma", "P98" if norma["clave"] == "p98" else norma["titulo"])

    def _magnitud_res_elegida(self, clave):
        if self._res["anios"] is None:
            return
        if clave == self._mag_res:
            self.botones_mag_res[clave].setChecked(True)          # la que ya se ve: sigue marcada
            return
        self._mag_res = clave
        self._poner_magnitud_res()
        self.magnitudElegida.emit(clave)

    def _magnitud_periodo_elegida(self):
        r, clave = self._res["periodo"], self.cmb_magnitud.currentData()
        if r is None or clave not in r["magnitudes"]:
            return
        self.res_periodo.poner(r["magnitudes"][clave], self._formato)
        self.magnitudElegida.emit(clave)

    def elegir_estilo(self, clave):
        """Isolíneas o degradado: desde la barra de encima del mapa (usuario, 2026-11-17)."""
        self._elegir_estilo(clave)

    def _elegir_estilo(self, clave):
        if clave != self._estilo:
            self._estilo = clave
            for grupo in (self._b_estilo, getattr(self, "_b_estilo_periodo", {})):   # los dos juegos de botones (reanálisis y episodio) comparten estado
                for c, b in grupo.items():
                    b.setChecked(c == clave)
            self.estiloCapas.emit(clave)

    def estilo_capas(self):
        """«isolineas» o «degradado»: cómo se ven en el mapa la media, el máximo y el P98 del reanálisis."""
        return self._estilo

    def set_resultado_caducado(self):
        self.lbl_sim.setText("⚠ El plan ha cambiado: vuelve a simular")
        self.lbl_sim.setVisible(True)

    def limpiar_resultado(self, periodo=None):
        """Quita los resultados: `periodo` True, los del episodio o la predicción; False, los del reanálisis; None, todos."""
        for bloque, cual, es in ((self.res_anios, "anios", False), (self.res_periodo, "periodo", True)):
            if periodo is None or periodo == es:
                bloque._m = None
                self._res[cual] = None
        if periodo is None or not periodo:
            self.res_anios.tabla.setRowCount(0)
        self.lbl_sim.setVisible(False)
        if not any(self._res.values()):
            self._estado.pop("simulado", None)
        self._actualizar_simular()

    # ── Comparar escenarios del reanálisis (usuario, 2026-11-09) ─────────────────────────
    def _elegir_modo(self, clave):
        if clave != self._modo:
            self._modo = clave
            self.lbl_sim.setVisible(False)                    # los links (abrir carpeta / informe) eran del modo anterior
            self.lbl_sim.setText("")
            self._actualizar_simular()
            self.modoReanalisis.emit(clave)

    def modo_reanalisis(self):
        """«simular» o «comparar»."""
        return self._modo

    def set_modo_reanalisis(self, clave):
        """Pone el modo (simular/comparar) sin re-emitir: para volver atrás al cancelar un cambio."""
        self._modo = clave
        b = self._b_modo.get(clave)
        if b is not None:
            b.setChecked(True)
        self._actualizar_simular()

    def set_escenarios(self, lista):
        """Los escenarios ya simulados y los casos guardados (`comparacion.escenarios`) en los dos desplegables, y al final «Abrir otro caso
        guardado…», de otra carpeta. Sigue lo elegido; si no, la Base de referencia y otro para comparar."""
        for cmb in (self.cmb_ref, self.cmb_comp):
            actual = cmb.currentData()
            cmb.blockSignals(True)
            cmb.clear()
            for e in lista:
                cmb.addItem(e["texto"], e["carpeta"])
                cmb.setItemData(cmb.count() - 1, e["carpeta"], QtCore.Qt.ItemDataRole.ToolTipRole)
            cmb.addItem("Abrir otro caso guardado…", "__abrir__")
            k = cmb.findData(actual) if actual and actual != "__abrir__" else -1
            if k < 0:
                base = next((i for i, e in enumerate(lista) if e["nombre"] == "Base" and not e["caso"]), 0)
                k = base if cmb is self.cmb_ref else next((i for i in range(len(lista)) if i != self.cmb_ref.currentIndex()), -1)
            cmb.setCurrentIndex(k if k >= 0 and lista else -1)
            cmb.blockSignals(False)
            self._previo[id(cmb)] = cmb.currentIndex()
        self._actualizar_simular()

    def _escenario_elegido(self, cmb):
        """«Abrir otro caso guardado…»: vuelve a lo que había y pide la carpeta (`escenario_cargado` lo pone al llegar)."""
        if cmb.currentData() == "__abrir__":
            cmb.setCurrentIndex(self._previo.get(id(cmb), -1))
            self._combo_zip = cmb
            self.cargarEscenario.emit()
        else:
            self._previo[id(cmb)] = cmb.currentIndex()
        self._actualizar_simular()

    def escenario_cargado(self, carpeta):
        """Ya en los desplegables (`set_escenarios`): se elige en el que lo pidió."""
        cmb = self._combo_zip or self.cmb_comp
        k = cmb.findData(carpeta)
        if k >= 0:
            cmb.setCurrentIndex(k)
            self._previo[id(cmb)] = k
        self._combo_zip = None
        self._actualizar_simular()

    def set_comparando(self, si, texto=""):
        """Mientras se comparan dos escenarios; al acabar, `texto` dice cómo ha ido."""
        self._comparando = si
        self.barra_sim.setVisible(si)
        self.barra_sim.setValue(0)
        if si:
            self._t0_sim = time.monotonic()
            texto = texto or "Comparando…"
        self.lbl_sim.setVisible(bool(texto))
        self.lbl_sim.setText(texto)
        self._actualizar_simular()

    def set_comparacion(self, r, cifra):
        """El resultado de `comparacion.comparar`."""
        self._comp, self._formato = r, cifra
        self._mag_comp = solo_olor(r)                       # solo el olor (usuario, 2026-11-17): sin los botones de los gases
        self.botones_mag_comp = {}
        fecha = lambda f: f"{f[8:10]}/{f[5:7]}/{f[:4]}"                                # noqa: E731
        texto = (f"<b>{html.escape(r['otro']['nombre'])}</b> (simulado el {fecha(r['otro']['fecha'])}) frente a <b>{html.escape(r['ref']['nombre'])}</b>"
                 f" (el {fecha(r['ref']['fecha'])}), la referencia")
        for a in r["avisos"]:
            texto += f"<br><span style='color:$aviso'>⚠ {html.escape(a)}</span>"
        tema.texto(self.lbl_comp, texto)
        self._pintar_comparacion()
        self._actualizar_simular()

    def magnitud_comparada(self):
        return self._mag_comp

    def comparacion(self):
        return self._comp

    def _magnitud_comp_elegida(self, clave):
        if self._comp is None:
            return
        if clave == self._mag_comp:
            self.botones_mag_comp[clave].setChecked(True)
            return
        self._mag_comp = clave
        self._pintar_comparacion()
        self.magnitudComparada.emit(clave)

    def _pintar_comparacion(self):
        """Los botones, los criterios del olor y la tabla de los pueblos con la magnitud y el estadístico elegidos."""
        r = self._comp
        if r is None:
            return
        m = r["magnitudes"][self._mag_comp]
        for c, b in self.botones_mag_comp.items():
            b.setChecked(c == self._mag_comp)
        hay = {c["id"]: c for c in m["capas"]}
        for capa in ("media", "maximo", "norma"):
            self._botones_capa[f"comp_{capa}"].setVisible(f"comp_{capa}" in hay)
        if "comp_norma" in hay:
            self.nombrar_capa("comp_norma", hay["comp_norma"]["titulo"])
        capa = hay.get(f"comp_{self._estad_comp}") or next(iter(hay.values()))
        cr = r["criterios"] if self._mag_comp == "olor" else None
        self.lbl_criterios.setVisible(bool(cr))
        if cr:
            def cambio(a, b):
                return "" if a <= 0 else f" <b>({_con_signo((b - a) / a * 100)} %)</b>"
            filas = "".join(f"<tr><td>&gt; {_num(c['umbral'])} ou_E/m³</td>"
                            f"<td align='right'>{_num(c['km2'][0], 2)} → {_num(c['km2'][1], 2)} km²{cambio(*c['km2'])}</td>"
                            f"<td align='right'>{c['pueblos'][0]} → {c['pueblos'][1]}</td></tr>" for c in cr)
            tema.texto(self.lbl_criterios, "<table width='100%' cellspacing='0' cellpadding='2'>"
                                           "<tr style='color:$tenue'><td>P98 de olor</td><td align='right'>Superficie</td>"
                                           f"<td align='right'>Pueblos</td></tr>{filas}</table>")
        self.lbl_pueblos_comp.setText(f"PUEBLOS · {m['nombre']} · {capa['titulo']} ({m['unidad']})")
        self.tabla_comp.poner(m, capa["clave"], (r["ref"]["nombre"], r["otro"]["nombre"]), self._formato)

    def set_fallo_comparacion(self, mensaje):
        self.lbl_sim.setVisible(True)
        self.lbl_sim.setText(f"No se pudo comparar: {html.escape(mensaje)}")

    def limpiar_comparacion(self):
        self._comp = None
        self.tabla_comp.setRowCount(0)
        self._actualizar_simular()

    # ── Visor 3D ─────────────────────────────────────────────────────────────────────────
    def _seccion_visor(self):
        sec = Tarjeta("Penachos simulados")
        self.cmb_3d = QtWidgets.QComboBox()
        sec.cuerpo.addWidget(self.cmb_3d)
        self.cmb_3d_mag = QtWidgets.QComboBox()
        sec.cuerpo.addWidget(self.cmb_3d_mag)
        self.b_3d = QtWidgets.QPushButton("Abrir", objectName="primario")
        self.b_3d.clicked.connect(self.ver3d)
        sec.cuerpo.addWidget(self.b_3d)
        self.barra_3d = QtWidgets.QProgressBar(minimum=0, maximum=100)
        self.barra_3d.setVisible(False)
        sec.cuerpo.addWidget(self.barra_3d)
        self.lbl_3d = QtWidgets.QLabel(wordWrap=True)
        self.lbl_3d.setVisible(False)
        sec.cuerpo.addWidget(self.lbl_3d)
        self.cmb_3d.currentIndexChanged.connect(self._penacho_elegido)
        self.cmb_3d_mag.currentIndexChanged.connect(lambda _: self._pinta_b_3d())
        self._penachos = []
        self._pinta_b_3d()
        return sec

    def set_penachos(self, lista):
        """Los penachos ya simulados de las 3 modalidades (penacho_3d.lista)."""
        actual = self.cmb_3d.currentData()
        self._penachos = lista
        self.cmb_3d.blockSignals(True)
        self.cmb_3d.clear()
        for p in lista:
            self.cmb_3d.addItem(p["texto"], p["ruta"])
        self.cmb_3d.setCurrentIndex(max(self.cmb_3d.findData(actual), 0))
        self.cmb_3d.blockSignals(False)
        self._penacho_elegido()

    def _penacho_elegido(self, _=None):
        p = next((x for x in self._penachos if x["ruta"] == self.cmb_3d.currentData()), None)
        actual = self.cmb_3d_mag.currentData()
        self.cmb_3d_mag.blockSignals(True)
        self.cmb_3d_mag.clear()
        for m in (p["magnitudes"] if p else ()):
            self.cmb_3d_mag.addItem(m["nombre"], m["clave"])
        self.cmb_3d_mag.setCurrentIndex(max(self.cmb_3d_mag.findData(actual), 0))
        self.cmb_3d_mag.blockSignals(False)
        self._pinta_b_3d()

    def penacho_elegido(self):
        """(ruta del resultado, magnitud) elegidos en el visor, o None."""
        return (self.cmb_3d.currentData(), self.cmb_3d_mag.currentData()) if self.cmb_3d.currentData() else None

    def _pinta_b_3d(self):
        p = next((x for x in self._penachos if x["ruta"] == self.cmb_3d.currentData()), None)
        m = next((x for x in p["magnitudes"] if x["clave"] == self.cmb_3d_mag.currentData()), None) if p else None
        if self._calculando_3d:
            self.b_3d.setText("Cancelar")
        else:
            self.b_3d.setText("Abrir" if m and m["listo"] else "Calcular")
        self.b_3d.setEnabled(self._calculando_3d or m is not None)
        self.cmb_3d.setEnabled(not self._calculando_3d)
        self.cmb_3d_mag.setEnabled(not self._calculando_3d)

    def set_calculando_3d(self, si):
        self._calculando_3d = si
        self.barra_3d.setVisible(si)
        self.barra_3d.setValue(0)
        self.lbl_3d.setVisible(si)
        self._pinta_b_3d()
        self._actualizar_simular()

    def set_progreso_3d(self, pct, mensaje):
        self.barra_3d.setValue(pct)
        self.lbl_3d.setText(mensaje)

    def set_fallo_3d(self, mensaje):
        self.lbl_3d.setText(f"No se pudo calcular en 3D: {mensaje}")
        self.lbl_3d.setVisible(True)

    # --- Huecos de los botones de capa -------------------------------------------------------
    # Son FÁBRICAS a propósito, no `lambda si, c=id_capa: …`. Esa forma, con un argumento
    # obligatorio y otro con valor por defecto, es la de toda la vida para capturar la variable de
    # un bucle, pero NO sobrevive al compilado: en el `.exe` (Nuitka + PySide6), Qt no acierta con
    # cuántos argumentos pasarle y la llama sin ninguno, así que el hueco revienta con un
    # «TypeError: missing 1 required positional argument» y el botón no hace nada. Se vio el
    # 2026-11-18, en el `.exe`, al pulsar «Ver usos del suelo» y «Ver edificios». Comprobado con
    # pruebas compiladas aparte: falla `lambda si, c=X`, y funcionan la fábrica (la variable se
    # captura por cierre y la lambda solo declara el argumento de la señal), `lambda si` a secas y
    # las funciones normales. En Python nativo las dos formas funcionan igual.
    def _capa_nombrada(self, id_capa):
        return lambda si: self.nombrar_capa(id_capa)

    def _capa_pulsada(self, id_capa):
        return lambda si: self.verCapa.emit(id_capa, si)

    def _boton_capa(self, id_capa, nombre, chip=False, oculto=False):
        """Botón que enciende o apaga una capa del mapa. Se mantiene al día con el mapa
        (set_capa_visible): las capas de un grupo son excluyentes, así que al encender una se
        apagan las otras y sus botones. Con `chip`, solo su nombre (marcado si se ve). Con `oculto`
        (las capas de lo simulado, que elige la barra de encima del mapa; usuario, 2026-11-17), en un
        contenedor que nunca se ve: solo lleva cuál está encendida (`capa_encendida`). Sin padre, un
        setVisible(True) lo abriría como una ventana suelta."""
        b = QtWidgets.QPushButton(nombre if chip else f"Ver {nombre}", checkable=True, objectName="chip_capa" if chip else "")
        if oculto:
            if getattr(self, "_capas_ocultas", None) is None:
                self._capas_ocultas = QtWidgets.QWidget(self)
                self._capas_ocultas.hide()
            b.setParent(self._capas_ocultas)
        b.toggled.connect(self._capa_nombrada(id_capa))
        b.clicked.connect(self._capa_pulsada(id_capa))
        self._botones_capa = getattr(self, "_botones_capa", {})
        self._nombres_capa = getattr(self, "_nombres_capa", {})
        self._botones_capa[id_capa] = b
        self._nombres_capa[id_capa] = nombre
        return b

    def nombrar_capa(self, id_capa, nombre=None):
        """Pone al día el texto de un botón de capa, con su nombre si cambia (P98, o la norma de un gas con límite)."""
        self._nombres_capa[id_capa] = nombre or self._nombres_capa[id_capa]
        b = self._botones_capa[id_capa]
        if b.objectName() == "chip_capa":
            b.setText(self._nombres_capa[id_capa])
            b.setToolTip(f"{'Ocultar' if b.isChecked() else 'Ver'} en el mapa")
        else:
            b.setText(f"{'Ocultar' if b.isChecked() else 'Ver'} {self._nombres_capa[id_capa]}")

    def capa_encendida(self, ids):
        """De estas capas, la que está encendida (son excluyentes), o None."""
        return next((i for i in ids if self._botones_capa[i].isChecked()), None)

    def set_capa_visible(self, id_capa, si):
        """El mapa avisa de que una capa se ha encendido o apagado: actualiza su botón."""
        b = getattr(self, "_botones_capa", {}).get(id_capa)
        if b is not None and b.isChecked() != si:
            b.setChecked(si)                       # solo cambia el texto: no vuelve a avisar
        if si and id_capa.startswith("comp_") and id_capa[5:] != self._estad_comp:
            self._estad_comp = id_capa[5:]         # la tabla de los pueblos de la comparación, con lo que se ve en el mapa
            self._pintar_comparacion()

    def set_descargando_edificios(self, activo):
        self.b_edificios.setEnabled(not activo)
        self.barra_edificios.setVisible(activo)
        if activo:
            self.barra_edificios.setValue(0)
            self.barra_edificios.setFormat("Preparando…")

    def set_progreso_edificios(self, pct, mensaje):
        self.barra_edificios.setValue(pct)
        self.barra_edificios.setFormat(f"{pct} % · {mensaje}")

    def set_descargando(self, activo):
        self.b_terreno.setEnabled(not activo)
        self.barra_terreno.setVisible(activo)
        if activo:
            self.barra_terreno.setValue(0)
            self.barra_terreno.setFormat("Preparando…")

    def set_progreso_terreno(self, pct, mensaje):
        self.barra_terreno.setValue(pct)
        self.barra_terreno.setFormat(f"{pct} % · {mensaje}")
