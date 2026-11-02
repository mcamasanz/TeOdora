# -*- coding: utf-8 -*-
"""Panel izquierdo: una barra de iconos con una página por tema (rama interfaz-moderna, 2026-10-31):
Inicio, Planta y, en el orden de uso, Focos → Meteorología → Simulación. Sustituye a la lista de
secciones plegables. Bajo el mapa, el reproductor de tiempo (`Panel.reproductor`).

La planta y el dominio son FIJOS (decisión del usuario): no hay controles para moverlos."""
import datetime as dt
import html
from zoneinfo import ZoneInfo

from PySide6 import QtCore, QtGui, QtWidgets

from teodors import planta as config
from teodors.comun.formato import km as _km, num as _num
from teodors.gui import tema
from teodors.gui.widgets import FilaPaso, Plegable, Tarjeta
from teodors.operacion import periodos
from teodors.planta import geo

NOMBRE_NUCLEO = {"residencial": ("núcleo urbano", "núcleos urbanos"),
                 "industrial": ("núcleo industrial", "núcleos industriales"),
                 "deportivo": ("espacio deportivo", "espacios deportivos")}


def _pct(x):
    return "< 0,1 %" if 0 < x < 0.05 else f"{_num(x, 1)} %"


def _muestra(color, lado=12):
    """Cuadradito de color para el árbol de usos."""
    pm = QtGui.QPixmap(lado, lado)
    pm.fill(QtGui.QColor(color))
    p = QtGui.QPainter(pm)
    p.setPen(QtGui.QColor("#777"))
    p.drawRect(0, 0, lado - 1, lado - 1)
    p.end()
    return QtGui.QIcon(pm)


def _punto_familia(familia):
    """Punto del color de esa familia de núcleos."""
    return f"<span style='color:$fam_{familia}'>●</span>"


def texto_anios():
    """Los años del reanálisis de la planta, en un texto: «N años»."""
    n = len(config.REANALISIS_ANIOS)
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
    se ordena por la columna que se pulse, primero de más a menos. Las columnas son las de gui/normativa.py."""

    def __init__(self, panel, prefijo, penacho=False):
        super().__init__()
        self.prefijo = prefijo
        self._m, self._cifra = None, None
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        self.lbl = QtWidgets.QLabel(wordWrap=True)
        v.addWidget(self.lbl)
        if penacho:
            v.addWidget(panel._boton_capa("penacho", "penacho"))
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(4)
        self.botones = {}
        for capa, nombre in (("media", "media"), ("maximo", "máximo"), ("norma", "norma")):
            self.botones[capa] = panel._boton_capa(f"{prefijo}_{capa}", nombre)
            fila.addWidget(self.botones[capa])
        v.addLayout(fila)
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

    def orden_por_media(self):
        self.tabla.horizontalHeader().setSortIndicator(1, QtCore.Qt.SortOrder.DescendingOrder)

    def poner(self, m, cifra):
        from teodors.operacion import simulacion as PC
        self._m, self._cifra = m, cifra
        texto = f"Máximo: <b>{cifra(m['maximos']['maximo'])} {m['unidad']}</b>"
        if m["estimados"]:
            texto += "<br>Estimado por gases: " + html.escape("; ".join(m["estimados"]))
        if m["fuera"]:
            texto += "<br>Sin calcular: " + html.escape("; ".join(m["fuera"]))
        self.lbl.setText(texto)
        cols = m["columnas"]
        norma = next((c for c in cols if c["capa"] == "norma"), None)
        self.botones["norma"].setVisible(norma is not None)
        if norma is not None:
            self._panel.nombrar_capa(f"{self.prefijo}_norma", "P98" if norma["clave"] == "p98" else "norma")
        T = self.tabla
        T.setSortingEnabled(False)                # con el orden puesto, las filas se moverían mientras se rellenan
        T.setColumnCount(1 + len(cols))
        T.setHorizontalHeaderLabels(["Lugar"] + [c["titulo"] for c in cols])
        cab = T.horizontalHeader()
        cab.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        varios_dias = any(len(h) > 5 for h in m["horas_txt"])
        for k, c in enumerate(cols, 1):
            # el panel es estrecho: el sitio, para los nombres
            cab.setSectionResizeMode(k, QtWidgets.QHeaderView.ResizeMode.Fixed)
            T.setColumnWidth(k, {"hora": 88 if varios_dias else 62, "horas": 62}.get(c["tipo"], 58))
            cabecera = T.horizontalHeaderItem(k)
            cabecera.setToolTip(c["nombre"])
            cabecera.setData(QtCore.Qt.ItemDataRole.InitialSortOrderRole, QtCore.Qt.SortOrder.DescendingOrder)
        T.setRowCount(len(m["filas"]))
        for i, f in enumerate(m["filas"]):
            nombre = QtWidgets.QTableWidgetItem(f["nombre"])
            nombre.setToolTip(f["nombre"])
            T.setItem(i, 0, nombre)
            for k, c in enumerate(cols, 1):
                v = f[c["clave"]]
                it = CeldaValor(v, PC.texto_celda(c, v, m))
                it.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if PC.supera(c, v):
                    it.setForeground(QtGui.QBrush(QtGui.QColor(tema.c("aviso"))))
                    letra = it.font()
                    letra.setBold(True)
                    it.setFont(letra)
                T.setItem(i, k, it)
        if not 0 <= cab.sortIndicatorSection() < T.columnCount():
            self.orden_por_media()                # esa columna no existe en esta magnitud
        T.setSortingEnabled(True)                 # ordena con la columna que hubiera elegida
        T.resizeRowsToContents()                  # sin barra de desplazamiento: se ven todas las filas
        T.setFixedHeight(cab.sizeHint().height() + sum(T.rowHeight(i) for i in range(len(m["filas"]))) + 2 * T.frameWidth())


class Panel(QtWidgets.QWidget):
    # (clave, texto de la barra, icono, título de la página)
    PAGINAS = (("inicio", "Inicio", "inicio", "Inicio"), ("planta", "Planta", "planta", "La planta y su entorno"),
               ("focos", "Focos", "focos", "Focos y planes"), ("meteo", "Meteo", "meteo", "Meteorología"),
               ("simulacion", "Simular", "simulacion", "Simulación"), ("visor3d", "3D", "visor3d", "Visor 3D"))
    tituloPagina = QtCore.Signal(str)
    paginaCambiada = QtCore.Signal(str)
    verActividad = QtCore.Signal()               # abrir o cerrar el registro de actividad
    verTerminal = QtCore.Signal()                # abrir o cerrar la terminal
    verTerreno = QtCore.Signal()
    verPlanta = QtCore.Signal()
    descargarTerreno = QtCore.Signal()
    descargarEdificios = QtCore.Signal()
    horizonteMeteo = QtCore.Signal(str)          # "ninguno" | "reanalisis" | "queja" | "prediccion"
    periodoCambiado = QtCore.Signal()            # otro día o número de días del episodio o la predicción
    prepararPeriodo = QtCore.Signal()            # descargar y calcular su viento y sus respuestas (o cancelarlo)
    vientoPeriodo = QtCore.Signal()              # ver su viento en el mapa
    vientoDia = QtCore.Signal(str)               # "aaaa-mm-dd": cargar el viento de ese día
    vientoHora = QtCore.Signal(int, float)       # hora del día y fracción (animación)
    verCapa = QtCore.Signal(str, bool)           # botones «Ver …»: id de la capa, encender
    verFocos = QtCore.Signal()                   # abrir la ventana de los focos
    verPlanes = QtCore.Signal()                  # abrir la ventana de los planes de operación
    simular = QtCore.Signal(object)              # los años del reanálisis: ruta del plan (None = la Base)
    simularPeriodo = QtCore.Signal(object)       # un día, el episodio o la predicción: ruta del plan
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
        contenidos = {"inicio": [self._seccion_inicio()],
                      "planta": [terreno, self.pleg_elevacion, self.pleg_usos, self._seccion_edificios()],
                      "focos": [self._seccion_focos()],
                      "meteo": [self._seccion_meteo(), self._bloque_viento(), self._bloque_periodo()],
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
            area.verticalScrollBar().rangeChanged.connect(
                lambda _a, b, v=v: v.setContentsMargins(12, 10, 2 if b > 0 else 12, 12))
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
        riel = QtWidgets.QFrame(objectName="riel")
        riel.setFixedWidth(70)
        v = QtWidgets.QVBoxLayout(riel)
        v.setContentsMargins(6, 8, 6, 8)
        v.setSpacing(4)
        self._grupo_paginas = QtWidgets.QButtonGroup(self, exclusive=True)
        self._b_pagina = {}
        for clave, texto, ico, titulo in self.PAGINAS:
            b = QtWidgets.QToolButton(objectName="riel_b", text=texto, checkable=True)
            b.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            tema.pon_icono(b, ico, "tenue", 22, activo="acento_claro")
            b.setIconSize(QtCore.QSize(22, 22))
            b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            b.clicked.connect(lambda _=False, k=clave: self.ir_a(k))
            self._grupo_paginas.addButton(b)
            self._b_pagina[clave] = b
            v.addWidget(b)
        v.addStretch()
        for texto, ico, senal in (("Actividad", "actividad", self.verActividad),
                                  ("Terminal", "terminal", self.verTerminal)):
            b = QtWidgets.QToolButton(objectName="riel_b", text=texto)
            b.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            tema.pon_icono(b, ico, "tenue", 22)
            b.setIconSize(QtCore.QSize(22, 22))
            b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            b.clicked.connect(senal)
            v.addWidget(b)
        return riel

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
        return pasos

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
        sec = Tarjeta("Emplazamiento")
        self.lbl_nombre = QtWidgets.QLabel(wordWrap=True)
        sec.cuerpo.addWidget(self.lbl_nombre)

        form = QtWidgets.QFormLayout()
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
        sec.cuerpo.addLayout(form)

        fila = QtWidgets.QHBoxLayout()
        b_planta = QtWidgets.QPushButton("Ver planta")
        b_planta.clicked.connect(self.verPlanta)
        b_terreno = QtWidgets.QPushButton("Ver toda la zona")
        b_terreno.clicked.connect(self.verTerreno)
        fila.addWidget(b_planta)
        fila.addWidget(b_terreno)
        sec.cuerpo.addLayout(fila)
        return sec

    def set_emplazamiento(self, emp):
        lat, lon = emp["lat"], emp["lon"]
        x, y = geo.a_utm(lat, lon)
        self.lbl_nombre.setText(emp["nombre"])
        # coordenadas con punto decimal, como en cualquier SIG (se pueden copiar y pegar)
        self.lbl_lat.setText(f"{lat:.6f}°")
        self.lbl_lon.setText(f"{lon:.6f}°")
        self.lbl_utm.setText(f"{_num(x)} · {_num(y)} m")

    # ── Terreno y uso del suelo ──────────────────────────────────────────────────────────
    def _seccion_terreno(self):
        sec = Tarjeta("Terreno")
        self.lbl_terreno = QtWidgets.QLabel(wordWrap=True,
                                            textFormat=QtCore.Qt.TextFormat.RichText)
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

        self.pleg_elevacion = Plegable("Elevación")
        self.lbl_cotas = QtWidgets.QLabel(wordWrap=True, textFormat=QtCore.Qt.TextFormat.RichText)
        self.pleg_elevacion.cuerpo.addWidget(self.lbl_cotas)
        self.b_ver_elevacion = self._boton_capa("elevacion", "elevación")
        self.pleg_elevacion.cuerpo.addWidget(self.b_ver_elevacion)

        self.pleg_usos = Plegable("Usos del suelo")
        self.arbol_usos = QtWidgets.QTreeWidget()
        self.arbol_usos.setColumnCount(2)
        self.arbol_usos.setHeaderHidden(True)
        self.arbol_usos.setRootIsDecorated(True)
        self.arbol_usos.setUniformRowHeights(True)
        self.arbol_usos.header().setStretchLastSection(False)
        self.arbol_usos.header().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.arbol_usos.header().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.pleg_usos.cuerpo.addWidget(self.arbol_usos)
        self.b_ver_usos = self._boton_capa("usos", "usos del suelo")
        self.pleg_usos.cuerpo.addWidget(self.b_ver_usos)
        self.lbl_nucleos = QtWidgets.QLabel(wordWrap=True,
                                            textFormat=QtCore.Qt.TextFormat.RichText)
        self.pleg_usos.cuerpo.addWidget(self.lbl_nucleos)
        return sec

    def set_terreno(self, info, resumen=None):
        """Muestra el terreno cargado y su resumen. Si no hay, ofrece descargarlo (una vez)."""
        self.b_terreno.setVisible(info is None)
        for w in (self.pleg_elevacion, self.pleg_usos):
            w.setVisible(info is not None)
        if info is None:
            tema.texto(self.lbl_terreno,
                       "<span style='color:$aviso'>Sin descargar.</span>")
            return
        lado, e, p = info["lado_km"], info["estadisticas"], info.get("planta", {})
        tema.texto(self.lbl_terreno,
                   f"{_km(lado)} × {_km(lado)} km a {_num(info['res_m'])} m"
                   f"<br><span style='color:$tenue'>Descargado el "
                   f"{info['fecha'][:16].replace('T', ' ')}</span>")

        texto = (f"<b>Cota</b> {_num(e['z_min'])}–{_num(e['z_max'])} m (media "
                 f"{_num(e['z_media'])} m)")
        if p.get("z") is not None:
            texto += f" · en la planta {_num(p['z'])} m ({p.get('uso_nombre', '?')})"
        if resumen:
            # escape: «< 50 m» se tomaría como el inicio de una etiqueta HTML y no saldría
            filas = "".join(f"<tr><td>{html.escape(b['banda'])}</td><td align='right'>"
                            f"&nbsp;&nbsp;{_pct(b['pct'])}</td></tr>" for b in resumen["bandas"])
            texto += f"<table cellspacing='0'>{filas}</table>"
        tema.texto(self.lbl_cotas, texto)

        self.arbol_usos.clear()
        negrita = self.arbol_usos.font()
        negrita.setBold(True)
        for g in (resumen or {}).get("grupos", []):
            item = QtWidgets.QTreeWidgetItem([g["nombre"], _pct(g["pct"])])
            item.setIcon(0, _muestra(g["color"]))
            item.setFont(0, negrita)
            item.setFont(1, negrita)
            item.setTextAlignment(1, QtCore.Qt.AlignmentFlag.AlignRight)
            for c in g["clases"]:
                hijo = QtWidgets.QTreeWidgetItem([f"{c['codigo']} · {c['nombre']}"
                                                  if c["codigo"] else c["nombre"],
                                                  _pct(c["pct"])])
                hijo.setIcon(0, _muestra(c["color"], 10))
                hijo.setTextAlignment(1, QtCore.Qt.AlignmentFlag.AlignRight)
                item.addChild(hijo)
            self.arbol_usos.addTopLevelItem(item)
        # alto justo para ver todos los grupos plegados; al desplegar aparece la barra
        n = max(self.arbol_usos.topLevelItemCount(), 1)
        alto_fila = self.arbol_usos.sizeHintForRow(0) if n else 18
        self.arbol_usos.setMinimumHeight(alto_fila * n + 2 * self.arbol_usos.frameWidth() + 4)
        self.arbol_usos.setMaximumHeight(alto_fila * (n + 6))

        lineas = []
        nucleos = (resumen or {}).get("nucleos", [])
        for familia in NOMBRE_NUCLEO:
            icono = _punto_familia(familia)
            de_tipo = [n for n in nucleos if n["familia"] == familia]
            uno, varios = NOMBRE_NUCLEO[familia]
            if not de_tipo:
                lineas.append(f"{icono} Ningún {uno}")
                continue
            cerca = de_tipo[0]                    # vienen ordenados por distancia
            lineas.append(f"{icono} <b>{len(de_tipo)}</b> {varios if len(de_tipo) > 1 else uno}"
                          f" · el más cercano a {_num(cerca['dist_m'] / 1000, 1)} km al "
                          f"{cerca['rumbo']}")
        tema.texto(self.lbl_nucleos, "<br>".join(lineas))

    # ── Meteorología ─────────────────────────────────────────────────────────────────────
    HORIZONTES = (("ninguno", "Ninguno", True), ("reanalisis", "Reanálisis", True), ("queja", "Episodio de queja", True),
                  ("prediccion", "Predicción", True), ("presente", "Tiempo real  ·  pendiente", False))

    def _seccion_meteo(self):
        sec = Tarjeta("Horizonte")
        self._grupo_meteo = QtWidgets.QButtonGroup(self)
        self._radios_meteo = {}
        for clave, texto, activo in self.HORIZONTES:
            r = QtWidgets.QRadioButton(texto, enabled=activo, checked=(clave == "ninguno"), objectName="opcion")
            self._grupo_meteo.addButton(r)
            self._radios_meteo[clave] = r
            sec.cuerpo.addWidget(r)
            r.toggled.connect(lambda si, c=clave: si and self.horizonteMeteo.emit(c))
        return sec

    # ── viento en superficie (capa animada del mapa) ─────────────────────────────────────
    def _bloque_viento(self):
        caja = Tarjeta("Viento de un día")
        self.fecha_viento = QtWidgets.QDateEdit(calendarPopup=True)
        self.fecha_viento.setDisplayFormat("dd/MM/yyyy")
        tema.calendario(self.fecha_viento.calendarWidget())
        self.btn_viento = QtWidgets.QPushButton("Ver en el mapa")
        fila = QtWidgets.QHBoxLayout()
        fila.addWidget(QtWidgets.QLabel("Día (UTC):"))
        fila.addWidget(self.fecha_viento, 1)
        fila.addWidget(self.btn_viento)
        caja.cuerpo.addLayout(fila)
        self.btn_viento.clicked.connect(
            lambda: self.vientoDia.emit(self.fecha_viento.date().toString("yyyy-MM-dd")))
        caja.setVisible(False)
        self.caja_viento = caja
        return caja

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

    def mostrar_periodo(self, modo):
        """El bloque del periodo, según la modalidad; nada en las demás."""
        si = modo in periodos.DIAS
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
            return periodos.nuevo(modo, self.fecha_periodo.date().toString("yyyy-MM-dd"), self.cmb_dias.currentData() or 1)
        if modo == "prediccion":
            return periodos.nuevo(modo, periodos.inicio_prediccion(), self.cmb_dias.currentData() or 3)
        return None

    def periodo_simulacion(self):
        """Lo que simula el botón del periodo: el día elegido del reanálisis, o el episodio o la predicción."""
        if self.horizonte_meteo() == "reanalisis":
            dia = self.fecha_dia.date().toString("yyyy-MM-dd")
            serie = self._dias_reanalisis.get(dia)
            return periodos.nuevo("reanalisis", dia, 1, serie) if serie else None
        return self.periodo()

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
            self.btn_viento.setEnabled(False)
            return
        ini, fin = (QtCore.QDate(d.year, d.month, d.day) for d in rango)
        primera = not getattr(self, "_viento_rango", False)
        self.fecha_viento.setDateRange(ini, fin)
        if primera:
            d = (QtCore.QDate(dia_inicial.year, dia_inicial.month, dia_inicial.day)
                 if dia_inicial is not None else ini)
            self.fecha_viento.setDate(d)
            self._viento_rango = True
        self.btn_viento.setEnabled(True)

    def set_viento_cargando(self, si):
        self.btn_viento.setEnabled(not si)
        self.btn_viento.setText("Cargando…" if si else "Ver en el mapa")

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
        self.vientoHora.emit(h, f)

    def horas_reproductor(self):
        return getattr(self, "_horas_viento", None)

    def ocultar_reproductor(self):
        self.btn_play.setChecked(False)
        self._horas_viento = None
        self.reproductor.setVisible(False)

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
        self.caja_viento.setVisible(si)
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
        self.fecha_viento.setDate(QtCore.QDate.fromString(fecha, "yyyy-MM-dd"))

    # ── Edificios ────────────────────────────────────────────────────────────────────────
    def _seccion_edificios(self):
        r = config.RADIO_EDIFICIOS_KM
        sec = Plegable(f"Edificios cercanos ({config.pide('fuentes', 'edificios')}, {_num(config.RADIO_EDIFICIOS_FOCOS_M)} m)")
        self.pleg_edificios = sec
        self.lbl_edificios = QtWidgets.QLabel(wordWrap=True,
                                              textFormat=QtCore.Qt.TextFormat.RichText)
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
        return sec

    def set_edificios(self, info):
        from teodors.fuentes.catastro import USO_COLOR
        self.b_edificios.setVisible(info is None)
        self.b_ver_edificios.setVisible(info is not None)
        if info is None:
            tema.texto(self.lbl_edificios, "<span style='color:$aviso'>Sin descargar.</span>")
            return
        filas = "".join(
            f"<tr><td><span style='color:{USO_COLOR.get(u, '#999')}'>■</span> {html.escape(u)}"
            f"</td><td align='right'>&nbsp;&nbsp;{n}</td></tr>"
            for u, n in info["por_uso"].items())
        # solo la fecha, el número por categoría y el botón (decisión del usuario, 2026-10-24)
        tema.texto(self.lbl_edificios,
                   f"<span style='color:$tenue'>Descargados el "
                   f"{info['fecha'][:16].replace('T', ' ')}</span>"
                   f"<table cellspacing='0'>{filas}</table>")

    # ── Focos de emisión (el operario los consulta; se cambian en el modo de edición) ────────────────────
    def _seccion_focos(self):
        sec = Tarjeta("Focos de emisión")
        self.lbl_focos = QtWidgets.QLabel(wordWrap=True, textFormat=QtCore.Qt.TextFormat.RichText)
        sec.cuerpo.addWidget(self.lbl_focos)
        b = QtWidgets.QPushButton(f"Focos… ({config.pide('operacion', 'texto_modo_edicion')})" if config.MODO_EDICION else "Ver focos…")
        b.clicked.connect(self.verFocos)
        sec.cuerpo.addWidget(b)
        b = QtWidgets.QPushButton("Planes de operación…", objectName="primario")
        b.clicked.connect(self.verPlanes)
        sec.cuerpo.addWidget(b)
        return sec

    def set_focos(self, datos):
        focos = (datos or {}).get("focos", [])
        if not focos:
            tema.texto(self.lbl_focos, "<span style='color:$tenue'>Aún no hay focos.</span>")
            self._estado.update(focos=0)
            self._pintar_inicio()
            return
        self._estado.update(focos=len(focos))
        self._pintar_inicio()
        n = {m: sum(1 for f in focos if f["modelo"] == m) for m in ("superficie", "punto", "volumen")}
        partes = [f"{k} de {m}" for m, k in n.items() if k]
        tema.texto(self.lbl_focos,
                   f"<b>{len(focos)} focos</b>"
                   + f"<br>{' · '.join(partes)}"
                   + f"<br><span style='color:$tenue'>Actualizados el {datos.get('actualizado', '?')}</span>")

    # ── Simulación ───────────────────────────────────────────────────────────────────────
    def _seccion_simulacion(self):
        """Se simula aquí, no en la ventana de planes (el usuario, 2026-10-31). Lo que se puede simular depende de la opción de
        Meteorología (usuario, 2026-11-01): en reanálisis, sus años y, si se quiere, un día; en episodio y predicción, su periodo."""
        sec = Tarjeta("Simular un plan")
        sec.cuerpo.addWidget(QtWidgets.QLabel("Plan de operación:"))
        self.cmb_plan = QtWidgets.QComboBox()
        sec.cuerpo.addWidget(self.cmb_plan)
        self.lbl_sim_meteo = QtWidgets.QLabel(wordWrap=True)
        sec.cuerpo.addWidget(self.lbl_sim_meteo)
        self.barra_sim = QtWidgets.QProgressBar(minimum=0, maximum=100)
        self.barra_sim.setVisible(False)
        sec.cuerpo.addWidget(self.barra_sim)
        self.lbl_sim = QtWidgets.QLabel(wordWrap=True)
        self.lbl_sim.setVisible(False)
        sec.cuerpo.addWidget(self.lbl_sim)
        self.cmb_magnitud = QtWidgets.QComboBox()
        self.cmb_magnitud.currentIndexChanged.connect(
            lambda _: self.magnitudElegida.emit(self.cmb_magnitud.currentData() or ""))
        self.cmb_magnitud.setVisible(False)
        sec.cuerpo.addWidget(self.cmb_magnitud)

        self.sec_anios = Tarjeta(texto_anios())
        self.b_simular = QtWidgets.QPushButton(f"Simular {texto_anios()}", objectName="primario")
        self.b_simular.clicked.connect(lambda: self.simular.emit(self.cmb_plan.currentData()))
        self.sec_anios.cuerpo.addWidget(self.b_simular)
        self.res_anios = BloqueResultado(self, "plan")
        self.sec_anios.cuerpo.addWidget(self.res_anios)

        self.sec_periodo = Tarjeta("Un día")
        self.fila_dia = QtWidgets.QWidget()
        fila = QtWidgets.QHBoxLayout(self.fila_dia)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.addWidget(QtWidgets.QLabel("Día (UTC):"))
        self.fecha_dia = QtWidgets.QDateEdit(calendarPopup=True)
        self.fecha_dia.setDisplayFormat("dd/MM/yyyy")
        tema.calendario(self.fecha_dia.calendarWidget())
        fila.addWidget(self.fecha_dia, 1)
        self.sec_periodo.cuerpo.addWidget(self.fila_dia)
        self.b_simular_periodo = QtWidgets.QPushButton("Simular día", objectName="primario")
        self.b_simular_periodo.clicked.connect(lambda: self.simularPeriodo.emit(self.cmb_plan.currentData()))
        self.sec_periodo.cuerpo.addWidget(self.b_simular_periodo)
        self.res_periodo = BloqueResultado(self, "dia", penacho=True)
        self.sec_periodo.cuerpo.addWidget(self.res_periodo)
        self.fecha_dia.dateChanged.connect(lambda _: self._actualizar_simular())
        self._hay_respuestas, self._simulando, self._calculando_3d = False, False, False
        self._dias_reanalisis = {}
        self.horizonteMeteo.connect(lambda _: self._actualizar_simular())
        self._actualizar_simular()
        return [sec, self.sec_anios, self.sec_periodo]

    def set_dias_reanalisis(self, dias):
        """{día: serie} con respuestas: limitan el calendario de «Un día». ⚠️ Hoy, días sueltos; con la serie de los años del reanálisis, todos."""
        self._dias_reanalisis = dias
        if dias:
            a, b = (QtCore.QDate.fromString(d, "yyyy-MM-dd") for d in (min(dias), max(dias)))
            self.fecha_dia.setDateRange(a, b)
            self.fecha_dia.setDate(b)
        self._actualizar_simular()

    def set_planes(self, lista, hay_respuestas):
        """Planes guardados [(nombre, ruta)] para elegir, y si ya se puede calcular."""
        actual = self.cmb_plan.currentData()
        self.cmb_plan.clear()
        self.cmb_plan.addItem("Base", None)
        for nombre, ruta in lista:
            self.cmb_plan.addItem(nombre, ruta)
        self.cmb_plan.setCurrentIndex(max(self.cmb_plan.findData(actual), 0))
        self._hay_respuestas = hay_respuestas
        self._estado["planes"] = len(lista)
        self._actualizar_simular()

    def _actualizar_simular(self):
        h = self.horizonte_meteo()
        ocupado = self._simulando or self._calculando_3d
        rea, per = h == "reanalisis", h in periodos.DIAS
        self.sec_anios.setVisible(rea)
        self.sec_periodo.setVisible(rea or per)
        self.fila_dia.setVisible(rea)
        if h == "ninguno":
            texto = "Meteorología: <b>sin elegir</b>"
        elif per:
            p = self.periodo()
            hay = periodos.listo(p)
            texto = f"Meteorología: <b>{periodos.MODOS[h]} {periodos.etiqueta(p)}</b>" + ("" if hay else "<br>Falta prepararlo en Meteorología")
        elif not self._hay_respuestas:
            texto = "Faltan las respuestas de los focos"
        else:
            texto = "Meteorología: <b>Reanálisis</b>"
        self.lbl_sim_meteo.setText(texto)
        self.b_simular.setEnabled(rea and self._hay_respuestas and not ocupado)
        destino = self.periodo_simulacion() if rea or per else None
        self.b_simular_periodo.setEnabled(destino is not None and periodos.listo(destino) and not ocupado)
        titulo, boton = {"queja": ("Episodio", "Simular episodio"), "prediccion": ("Predicción", "Simular predicción")}.get(h, ("Un día", "Simular día"))
        self.sec_periodo.titulo.setText(titulo)
        self.b_simular_periodo.setText(boton)
        self._estado["horizonte"] = h
        self._pintar_inicio()

    def _bloque(self, periodo):
        return self.res_periodo if periodo else self.res_anios

    def set_simulando(self, si, periodo=False):
        """Mientras se simula, su bloque de resultados se oculta: `periodo`, el del día, el episodio o la predicción."""
        self._simulando = si
        self.barra_sim.setVisible(si)
        self.barra_sim.setValue(0)
        self.lbl_sim.setVisible(True)
        if si:
            self.lbl_sim.setText("Simulando…")
            self._bloque(periodo).setVisible(False)
        self._actualizar_simular()

    def fin_simulacion(self):
        self._simulando = False
        self.barra_sim.setVisible(False)
        self._actualizar_simular()

    def set_progreso_simulacion(self, pct, mensaje):
        self.barra_sim.setValue(pct)
        self.lbl_sim.setText(mensaje)

    def set_fallo_simulacion(self, mensaje):
        self.lbl_sim.setText(f"No se pudo simular: {mensaje}")

    def set_resultado(self, r, cifra):
        """Muestra el resultado de una simulación; `cifra` da formato a las concentraciones."""
        actual = self.cmb_magnitud.currentData()
        self.cmb_magnitud.blockSignals(True)
        self.cmb_magnitud.clear()
        for k in r["orden"]:
            self.cmb_magnitud.addItem(r["magnitudes"][k]["nombre"], k)
        self.cmb_magnitud.setCurrentIndex(max(self.cmb_magnitud.findData(actual), 0))
        self.cmb_magnitud.blockSignals(False)
        self.cmb_magnitud.setVisible(len(r["orden"]) > 1)
        bloque = self._bloque(r["periodo"])
        bloque.orden_por_media()
        bloque.poner(r["magnitudes"][self.cmb_magnitud.currentData()], cifra)
        bloque.setVisible(True)
        self.lbl_sim.setVisible(False)
        self._estado["simulado"] = r["nombre"]
        self._pintar_inicio()

    def set_resultado_caducado(self):
        self.lbl_sim.setText("⚠ El plan ha cambiado: vuelve a simular")
        self.lbl_sim.setVisible(True)

    def limpiar_resultado(self, periodo=None):
        """Quita los resultados: `periodo` True, los del día, el episodio o la predicción; False, los de los años del reanálisis; None, todos."""
        for bloque, es in ((self.res_anios, False), (self.res_periodo, True)):
            if periodo is None or periodo == es:
                bloque.setVisible(False)
                bloque._m = None
        self.lbl_sim.setVisible(False)
        if not self.res_anios.isVisibleTo(self) and not self.res_periodo.isVisibleTo(self):
            self.cmb_magnitud.setVisible(False)
            self._estado.pop("simulado", None)
        self._pintar_inicio()

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

    def _boton_capa(self, id_capa, nombre):
        """Botón que enciende o apaga una capa del mapa. Se mantiene al día con el mapa
        (set_capa_visible): las capas de un grupo son excluyentes, así que al encender una se
        apagan las otras y sus botones."""
        b = QtWidgets.QPushButton(f"Ver {nombre}", checkable=True)
        b.toggled.connect(lambda si, c=id_capa: self.nombrar_capa(c))
        b.clicked.connect(lambda si, c=id_capa: self.verCapa.emit(c, si))
        self._botones_capa = getattr(self, "_botones_capa", {})
        self._nombres_capa = getattr(self, "_nombres_capa", {})
        self._botones_capa[id_capa] = b
        self._nombres_capa[id_capa] = nombre
        return b

    def nombrar_capa(self, id_capa, nombre=None):
        """Pone al día el texto de un botón de capa, con su nombre si cambia (P98, o la norma de un gas con límite)."""
        self._nombres_capa[id_capa] = nombre or self._nombres_capa[id_capa]
        b = self._botones_capa[id_capa]
        b.setText(f"{'Ocultar' if b.isChecked() else 'Ver'} {self._nombres_capa[id_capa]}")

    def capa_encendida(self, ids):
        """De estas capas, la que está encendida (son excluyentes), o None."""
        return next((i for i in ids if self._botones_capa[i].isChecked()), None)

    def set_capa_visible(self, id_capa, si):
        """El mapa avisa de que una capa se ha encendido o apagado: actualiza su botón."""
        b = getattr(self, "_botones_capa", {}).get(id_capa)
        if b is not None and b.isChecked() != si:
            b.setChecked(si)                       # solo cambia el texto: no vuelve a avisar

    def set_descargando_edificios(self, activo):
        self.b_edificios.setEnabled(not activo)
        self.barra_edificios.setVisible(activo)
        if activo:
            self.pleg_edificios.cabecera.setChecked(True)      # el avance tiene que verse
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
