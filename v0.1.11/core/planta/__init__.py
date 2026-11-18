# -*- coding: utf-8 -*-
"""Una planta: lo que teOdors necesita saber de un emplazamiento, leído de su carpeta.

Los motores no saben nada de esto (reciben ficheros de control). Es para lo que va encima de ellos:
preparar casos, descargar datos y la aplicación. Cambiar de planta es cambiar de carpeta, sin tocar
el código.

Carpeta de una planta:
    planta.json         identidad, proyección, dominio, receptores, años del reanálisis…
    emplazamiento.json  nombre y coordenadas
    focos.json, receptores.json, normativa.json   sus focos, receptores con nombre y límites
    terreno/, edificios/  su terreno (cotas, usos del suelo, núcleos) y sus edificios: se descargan UNA vez y van con la planta
    planes/             sus planes de operación guardados: los crea quien opera la planta y no se pueden recalcular
    rutas.json          opcional: dónde están sus DATOS, los cálculos, {"datos": ruta} (absoluta, o relativa a esta carpeta)

Uso:
    from teodors import planta
    planta.activar("ruta/de/la/carpeta")
    planta.DATOS, planta.EPSG_UTM, planta.RADIO_CALCULO_KM…     # los de la planta activa
    from teodors.planta import geo                                # coordenadas en su huso

⚠️ Un proceso trabaja con UNA planta. `activar` la deja en la variable de entorno TEODORS_PLANTA para
que los procesos hijos usen la misma. Los valores se leen UNA vez al activar: las variables de
entorno de la planta (`<prefijo>_DATOS`, `_LOCAL`, `_CORINE`) hay que fijarlas antes.
"""
import json
import os
from pathlib import Path

ENV_PLANTA = "TEODORS_PLANTA"

_activa = None


# la carpeta de cada modo de simulación dentro de la de los casos (`Planta.DIR_CASOS`)
CARPETAS_CASOS = {"reanalisis": "reanalisis", "queja": "episodios", "prediccion": "prediccion"}

class Planta:
    """Los datos de una planta, con nombres en mayúsculas para las constantes."""

    def __init__(self, carpeta):
        self.PLANTA = Path(carpeta).resolve()
        self._ruta = self.PLANTA / "planta.json"
        if not self._ruta.is_file():
            raise FileNotFoundError(f"No hay ninguna planta en {self.PLANTA}: falta planta.json.")
        self._json = json.loads(self._ruta.read_text(encoding="utf-8"))

        self.APP_NOMBRE = self.pide("identidad", "app_nombre")
        self.ORGANIZACION = self.pide("identidad", "organizacion")
        self.PREFIJO_ENV = self.pide("identidad", "prefijo_env")
        self.REGISTRO = self.pide("identidad", "registro")
        self.AGENTE_HTTP = self.bloque("identidad").get("agente_http", "teOdors")    # cómo se presenta a los servicios de datos

        self.EMPLAZAMIENTO_JSON = self.PLANTA / "emplazamiento.json"
        self.FOCOS_JSON = self.PLANTA / "focos.json"
        self.RECEPTORES_JSON = self.PLANTA / "receptores.json"
        self.NORMATIVA_JSON = self.PLANTA / "normativa.json"      # opcional: si no está, manda la plantilla de `operacion.normativa`

        # Modo de edición: se pueden añadir focos y cambiar lo que obliga a recalcularlos
        self.CLAVE_EDICION = self.bloque("operacion").get("modo_edicion", "edicion")
        # Siempre empieza en False: lo abre el usuario administrador, con su contraseña, desde la terminal de la app
        # (`operacion.administrador`; usuario, 2026-11-08). Ni la línea de órdenes ni el entorno lo abren.
        self.MODO_EDICION = False

        # UNA sola constante del huso en todo el proyecto: dos husos en un dominio desvían el penacho
        self.EPSG_UTM = self.pide("proyeccion", "epsg")
        self.CRS_GEO = self.pide("proyeccion", "crs_geo")

        # El dominio es un cuadrado centrado en la planta. `lado_km` es el LADO del terreno descargado;
        # el cálculo se expresa como DISTANCIA AL CENTRO (mitad del lado, menos el margen de terreno)
        self.DOMINIO_DESCARGA_KM = float(self.pide("dominio", "lado_km"))
        self.MARGEN_TERRENO_M = float(self.pide("dominio", "margen_m"))
        self.RES_TERRENO_M = float(self.pide("dominio", "res_terreno_m"))
        self.RADIO_EDIFICIOS_KM = float(self.pide("dominio", "radio_edificios_km"))
        self.RADIO_EDIFICIOS_FOCOS_M = float(self.pide("dominio", "radio_edificios_focos_m"))
        self.VIENTO3D_CELDA_M = float(self.pide("dominio", "celda_viento_m"))
        self.VIENTO3D_ZFACE = tuple(self.pide("dominio", "zface"))
        self.RECEPTORES_POR_KM2 = self.pide("receptores", "por_km2")
        self.RADIO_CALCULO_KM = self.radio_calculo_max(self.DOMINIO_DESCARGA_KM)

        # Años COMPLETOS: el P98 exige años enteros
        self.REANALISIS_ANIOS = tuple(self.pide("reanalisis", "anios"))

        # DATOS puede ser una unidad de red; LOCAL, lo regenerable y los cálculos en marcha, no
        self.DATOS = self._ruta_datos()
        temporal = Path(os.environ.get("TEMP", Path.home())) / self.pide("identidad", "carpeta_local")
        self.LOCAL = Path(self._env("LOCAL") or temporal)
        self.DIR_WEB = self.LOCAL / "web"
        self.DIR_WEB_ASSETS = self.LOCAL / "web_assets"
        self.DIR_LOGS = self.LOCAL / "logs"
        self.DIR_TRABAJO = self.LOCAL / "trabajo"
        self.DIR_TERRENO = self.PLANTA / "terreno"       # con la planta: sin ellos no hay nada que enseñar, y no dependen de la unidad de DATOS
        self.DIR_EDIFICIOS = self.PLANTA / "edificios"
        self.DIR_PLANES = self.PLANTA / "planes"
        self.DIR_METEO = self.DATOS / "meteo"            # la caché de la meteo: AQUÍ se descarga siempre (ERA5, estaciones, GFS…)
        # La meteo de los INFORMES, YA PROCESADA, con la planta (junto a `entrada/`, o en <prefijo>_METEO): de los años del reanálisis, las
        # rosas de las estaciones, el tiempo en la planta (la media de cada día de cada variable, con su mínimo y su máximo) y lo normal de
        # cada fecha y hora (mínimo, mediana y máximo), que calcula `operacion.meteo_planta` desde la caché. Ni un fichero meteorológico en
        # bruto. Es de SOLO LECTURA (nada descarga en ella) y se usa cuando faltan los datos en bruto de los que salió (`meteo_procesada`):
        # así un equipo sin la unidad de DATOS (el del cliente) hace los informes completos.
        self.DIR_METEO_PLANTA = Path(self._env("METEO") or self.PLANTA.parent / "meteo")
        self.DIR_VIENTO3D = self.DATOS / "viento3d"
        # El viento 3D del EPISODIO es temporal: se calcula en tmp (LOCAL) y solo pasa a `casos/episodios/<fecha>/viento` si se guarda.
        self.DIR_VIENTO3D_TMP = self.LOCAL / "viento3d"
        # Viento de la planta, junto a `entrada/` (o en <prefijo>_VIENTO): `3d/`, el paquete de la serie de varios años
        # (`meteo.viento3d.paquete`, ~1 GB, para leerla sin DATOS), y `local/`, la biblioteca del viento local (su ruta, en planta.json)
        self.DIR_VIENTO = Path(self._env("VIENTO") or self.PLANTA.parent / "viento")
        self.DIR_VIENTO_PAQUETE = self.DIR_VIENTO / "3d"
        # Las respuestas de los focos de toda la serie, comprimidas (`operacion.serie_respuestas`): lo que lee el reanálisis
        self.DIR_DISPERSION = Path(self._env("DISPERSION") or self.PLANTA.parent / "dispersion")
        # Los casos guardados (usuario, 2026-11-10: «una carpeta… que sean casos, con 3 carpetas: reanálisis, episodios y predicción»), junto a `entrada/` (o en <prefijo>_CASOS): cada caso, su carpeta, con «resultados» y, a su lado, su informe
        self.DIR_CASOS = Path(self._env("CASOS") or self.PLANTA.parent / "casos")
        self.DIR_VIENTO3D_ESTUDIOS = self.DATOS / "viento3d_estudios"
        # Claves de API: NUNCA en el código ni en la carpeta de la planta. Cada usuario pone las suyas aquí
        self.DIR_CLAVES = Path(os.environ.get("APPDATA", Path.home())) / self.ORGANIZACION / "claves"
        self.CDS_CLAVE = self.DIR_CLAVES / "cds-api-key.txt"

    def __repr__(self):
        return f"Planta({str(self.PLANTA)!r})"

    def pide(self, bloque, clave):
        """Un campo de planta.json que hace falta: sin él, el error dice cuál."""
        try:
            return self._json[bloque][clave]
        except KeyError:
            raise ValueError(f"{self._ruta}: falta {bloque}.{clave}") from None

    def _env(self, nombre):
        return os.environ.get(self.nombre_env(nombre))

    def _ruta_datos(self):
        """La variable <prefijo>_DATOS, si no rutas.json y, si no, datos/ dentro de la carpeta de la planta."""
        v = self._env("DATOS")
        if v:
            return Path(v)
        rutas = self.PLANTA / "rutas.json"
        if rutas.is_file():
            r = json.loads(rutas.read_text(encoding="utf-8")).get("datos")
            if r:
                r = Path(r)
                return r if r.is_absolute() else (self.PLANTA / r).resolve()      # sin tocar una ruta absoluta: la unidad puede no estar
        return self.PLANTA / "datos"

    def nombre_env(self, nombre):
        """Nombre de la variable de entorno de esta planta: nombre_env("DATOS") -> «<prefijo>_DATOS»."""
        return f"{self.PREFIJO_ENV}_{nombre}"

    def bloque(self, nombre):
        """Un bloque de planta.json, o {} si la planta no lo tiene."""
        return self._json.get(nombre, {})

    def datos_disponibles(self):
        """¿Se llega a la carpeta de DATOS? (en una unidad de red puede no estar conectada)."""
        try:
            return self.DATOS.is_dir()
        except OSError:
            return False

    def meteo_procesada(self, nombre):
        """Un producto de la meteo procesada de la planta (`DIR_METEO_PLANTA/<nombre>`, JSON), o None si no está, no se puede leer o en este
        equipo están TODOS los ficheros en bruto de los que salió (su lista `de`, relativa a `DIR_METEO`): entonces se calcula de ellos, como
        siempre. Los pocos días que se bajan para un episodio no bastan para dejarlo."""
        try:
            d = json.loads((self.DIR_METEO_PLANTA / nombre).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        de = d.get("de") if isinstance(d, dict) else None
        if de and all((self.DIR_METEO / p).is_file() for p in de):
            return None
        return d

    def asegurar_carpetas(self):
        """Crea las carpetas locales siempre y las de DATOS solo si se llega a ellos."""
        for d in (self.DIR_WEB, self.DIR_WEB_ASSETS, self.DIR_LOGS, self.DIR_TERRENO, self.DIR_PLANES):
            d.mkdir(parents=True, exist_ok=True)
        try:
            for d in (self.DATOS, self.DIR_METEO):
                d.mkdir(parents=True, exist_ok=True)
        except OSError:                         # unidad de red sin conectar: la aplicación avisa
            pass
        try:
            for sub in CARPETAS_CASOS.values():
                (self.DIR_CASOS / sub).mkdir(parents=True, exist_ok=True)
        except OSError:                         # sin permiso donde está la planta: se dirá al guardar
            pass

    def corine_gpkg(self):
        """Ruta del CORINE nacional: la variable <prefijo>_CORINE, DATOS/insumos o las copias que liste
        fuentes.corine_gpkg de planta.json (admiten variables de entorno). None si no hay ninguna.
        Solo hace falta para descargar: el terreno de la planta guarda su propio extracto."""
        candidatos = [self._env("CORINE"), self.DATOS / "insumos" / "CLC2018_ES.gpkg"]
        candidatos += [os.path.expandvars(c) for c in self.bloque("fuentes").get("corine_gpkg", [])]
        for c in candidatos:
            if c and Path(c).is_file():
                return Path(c)
        return None

    def radio_calculo_max(self, lado_terreno_km):
        """Distancia al centro máxima del cálculo dentro de un terreno de ese LADO, dejando el margen
        de terreno: 50 km de lado y 500 m de margen -> 25 − 0,5 = 24,5 km."""
        return lado_terreno_km / 2.0 - self.MARGEN_TERRENO_M / 1000.0

    def cargar_emplazamiento(self):
        with open(self.EMPLAZAMIENTO_JSON, encoding="utf-8") as f:
            return json.load(f)


def activar(carpeta):
    """Fija la planta de este proceso y de sus hijos. Devuelve la Planta."""
    global _activa
    _activa = Planta(carpeta)
    os.environ[ENV_PLANTA] = str(_activa.PLANTA)
    return _activa


def desactivar():
    """Deja el proceso sin planta (para las pruebas)."""
    global _activa
    _activa = None
    os.environ.pop(ENV_PLANTA, None)


def actual():
    """La planta activa. En un proceso hijo se activa sola con la de su padre (TEODORS_PLANTA)."""
    if _activa is None:
        heredada = os.environ.get(ENV_PLANTA)
        if not heredada:
            raise RuntimeError("Ninguna planta activa: llama antes a teodors.planta.activar(carpeta).")
        return activar(heredada)
    return _activa


def __getattr__(nombre):
    """planta.DATOS, planta.corine_gpkg()…: los de la planta activa. Se resuelve al usarlos, nunca al
    importar: por eso un valor por defecto de una función no puede ser planta.ALGO (ponlo a None)."""
    if nombre.isupper() or (not nombre.startswith("_") and callable(getattr(Planta, nombre, None))):
        return getattr(actual(), nombre)
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")
