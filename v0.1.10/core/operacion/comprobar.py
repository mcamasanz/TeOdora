# -*- coding: utf-8 -*-
"""Comprobar la herramienta (usuario, 2026-11-07: «un control de si todo lo que hace la herramienta funciona, con un botón de comprobar»).

Mini rutinas que miran, una a una, lo que usa la app instalada: el programa, la carpeta de la planta (`entrada`, `viento` y `dispersion`),
la de trabajo, los motores y los servicios de los que descarga para los episodios de queja y la predicción. No descarga nada: de cada
servicio pide lo mínimo (una fila, sus capacidades, una tesela o la cabecera de un fichero).

**Cada problema tiene un código** (`CODIGOS`), para que quien da soporte sepa qué falla con solo oírlo: categoría + dos cifras, la primera
el ELEMENTO que se prueba y la segunda QUÉ LE PASA, igual en todas las categorías (`QUE_PASA`): MET-05 = meteorología en línea, elemento 0
(la web de las estaciones), no responde. El panel enseña las categorías con sus códigos; el registro, además, el detalle y qué hacer.

    python -m teodors.operacion.comprobar [--sin-red]     # las mismas pruebas, por línea de órdenes
    python -m teodors.operacion.comprobar --codigos       # el catálogo de códigos, en Markdown
"""
import argparse
import datetime as dt
import json
import math
import shutil
import ssl
import subprocess
import sys
import time
import urllib.request

import numpy as np

from teodors import planta as config
from teodors.comun import registro
from teodors.comun.formato import km as _km, num as _num

log = registro.get("comprobar")
TIEMPO = 15                                   # s de espera por servicio
OK, AVISO, FALLO = "ok", "aviso", "fallo"
MARCA = {OK: "✓", AVISO: "⚠", FALLO: "✗"}

# Lo que ve el cliente: las categorías, en este orden
CATEGORIAS = (("INS", "Instalación"), ("ENT", "Datos de entrada"), ("VIE", "Viento"), ("DIS", "Dispersión"),
              ("MET", "Meteorología en línea"), ("RED", "Conexión"))
# La segunda cifra de un código: qué le pasa al elemento (igual en todas las categorías)
QUE_PASA = {1: "falta", 2: "está dañado o no arranca", 3: "incompleto o a medias", 5: "el servicio no responde",
            6: "el servicio responde con un error", 7: "permiso o clave rechazados", 8: "falta la clave"}
# Los elementos de cada categoría (la primera cifra)
ELEMENTOS = {"INS": {0: "el programa", 1: "la carpeta de trabajo", 2: "la carpeta local del equipo",
                     3: "la tabla de umbrales de olor (Nagata)"},
             "ENT": {0: "la configuración de la planta", 1: "el terreno", 2: "los edificios", 3: "los focos", 4: "los planes",
                     5: "la normativa y los receptores", 6: "los recursos de la interfaz"},
             "VIE": {0: "el viento 3D del reanálisis", 1: "el viento alrededor de los edificios", 2: "el motor del viento 3D"},
             "DIS": {0: "las respuestas de los focos", 1: "el motor de dispersión", 2: "el visor 3D", 3: "el informe en PDF"},
             "MET": {0: "las estaciones", 1: "el reanálisis ERA5", 2: "la predicción GFS"},
             "RED": {0: "internet", 1: "las conexiones seguras", 2: "los fondos del mapa"}}

# código: (gravedad, qué pasa, qué hacer). La fuente única: de aquí salen el panel, el registro y el catálogo.
CODIGOS = {
    "INS-01": (FALLO, "Falta una librería del programa (mapa, geodatos o cálculo)", "Reinstalar el programa."),
    "INS-02": (FALLO, "La carpeta de la planta pide otra versión del programa", "Instalar la versión que pide el fichero VERSION de la planta."),
    "INS-11": (FALLO, "No se llega a la carpeta de trabajo (días descargados, cálculos y resultados)",
               "Comprobar la ruta de entrada/rutas.json o la variable de entorno de la planta, y que la unidad esté conectada."),
    "INS-13": (AVISO, "Queda poco espacio en la carpeta de trabajo (menos de 5 GB)", "Liberar espacio: un episodio o una predicción ocupan ~1 GB."),
    "INS-17": (FALLO, "No se puede escribir en la carpeta de trabajo", "Dar permiso de escritura al usuario en esa carpeta."),
    "INS-23": (AVISO, "Queda poco espacio en el disco local (menos de 2 GB)", "Liberar espacio en el disco del sistema."),
    "INS-27": (FALLO, "No se puede escribir en la carpeta local del equipo (registros y caché)", "Dar permiso de escritura o liberar el disco."),
    "INS-31": (FALLO, "Falta la tabla de umbrales de olor de Nagata: no se puede pasar la emisión de un gas a olor", "Reinstalar el programa."),
    "INS-32": (FALLO, "La tabla de umbrales de olor de Nagata está dañada", "Reinstalar el programa."),
    "INS-33": (FALLO, "La tabla de umbrales de olor de Nagata está incompleta (faltan gases, umbrales o masas molares)", "Reinstalar el programa."),
    "ENT-01": (FALLO, "Falta un fichero de configuración de la planta en entrada/", "Recuperar la carpeta entrada (reinstalar)."),
    "ENT-02": (FALLO, "Un fichero de configuración de la planta está dañado", "Recuperar la carpeta entrada (reinstalar)."),
    "ENT-11": (FALLO, "Falta el terreno (elevaciones y usos del suelo)", "Volver a descargarlo desde la página Planta, o reinstalar."),
    "ENT-12": (FALLO, "El terreno está dañado", "Volver a descargarlo desde la página Planta, o reinstalar."),
    "ENT-13": (AVISO, "El terreno tiene zonas sin cota", "Volver a descargarlo desde la página Planta."),
    "ENT-21": (FALLO, "Faltan los edificios", "Volver a descargarlos desde la página Planta, o reinstalar."),
    "ENT-22": (FALLO, "Los edificios están dañados", "Volver a descargarlos desde la página Planta, o reinstalar."),
    "ENT-31": (AVISO, "No hay focos", "Darlos de alta en la ventana de focos (modo de edición)."),
    "ENT-32": (FALLO, "El fichero de los focos está dañado o es de otra versión", "Recuperar entrada/focos.json."),
    "ENT-33": (FALLO, "Un foco está incompleto (sin posición o sin emisión)", "Completarlo en la ventana de focos (modo de edición)."),
    "ENT-42": (FALLO, "Un plan de operación guardado no se puede leer", "Abrirlo y volver a guardarlo en la ventana de planes, o borrarlo."),
    "ENT-52": (FALLO, "La normativa o los receptores con nombre están dañados", "Recuperar entrada/normativa.json o entrada/receptores.json."),
    "ENT-61": (AVISO, "Falta un recurso de la interfaz (la ortofoto del visor 3D o el icono)", "Recuperar entrada/recursos o entrada/icono."),
    "VIE-01": (FALLO, "No hay viento 3D del reanálisis", "Recuperar la carpeta viento/3d (reinstalar)."),
    "VIE-02": (FALLO, "Un mes del viento 3D está dañado", "Recuperar la carpeta viento/3d (reinstalar)."),
    "VIE-03": (FALLO, "Faltan meses del viento 3D", "Recuperar la carpeta viento/3d (reinstalar)."),
    "VIE-11": (AVISO, "Falta el viento alrededor de los edificios: el mapa enseña el viento sin ellos",
               "Recuperar viento/local/viento_local.npz (reinstalar)."),
    "VIE-12": (FALLO, "El viento alrededor de los edificios está dañado", "Recuperar viento/local/viento_local.npz (reinstalar)."),
    "VIE-22": (FALLO, "El motor del viento 3D no arranca: no se pueden preparar episodios ni predicciones", "Reinstalar el programa."),
    "DIS-01": (FALLO, "Faltan las respuestas de los focos (carpeta dispersion): el reanálisis de un plan no se puede simular",
               "Recuperar la carpeta dispersion (reinstalar) o pedir a soporte que la calcule."),
    "DIS-02": (FALLO, "Las respuestas de los focos están dañadas", "Recuperar la carpeta dispersion (reinstalar)."),
    "DIS-03": (AVISO, "Las respuestas están incompletas o son de prueba: hay focos sin ellas o que han cambiado desde que se calcularon, o son "
                      "unas semanas repetidas en todos los años",
               "Pedir a soporte que calcule las respuestas de esos focos o, si son de prueba, la serie entera."),
    "DIS-12": (FALLO, "El motor de dispersión no arranca", "Reinstalar el programa."),
    "DIS-22": (AVISO, "El visor 3D no arranca: falta su librería o una parte de ella", "Reinstalar el programa."),
    "DIS-31": (FALLO, "Falta el motor del informe en PDF (el navegador de la app o su lector de PDF)", "Reinstalar el programa."),
    "DIS-32": (FALLO, "El informe en PDF no se puede montar con el último caso guardado", "Avisar a soporte con el detalle del registro."),
    "MET-01": (AVISO, "No hay inventario de estaciones: el mapa no las enseña", "Se baja al preparar un episodio; si sigue, avisar a soporte."),
    "MET-05": (FALLO, "La web de las estaciones no responde (caída o sin conexión)", "Esperar y volver a comprobar; si sigue, avisar a soporte."),
    "MET-06": (FALLO, "La web de las estaciones responde con un error (ha cambiado)", "Avisar a soporte."),
    "MET-15": (FALLO, "El servicio del reanálisis ERA5 (Copernicus) no responde: no se pueden preparar episodios de queja",
               "Esperar y volver a comprobar; si sigue, avisar a soporte."),
    "MET-16": (FALLO, "El servicio del reanálisis ERA5 (Copernicus) responde con un error (ha cambiado)", "Avisar a soporte."),
    "MET-17": (FALLO, "Copernicus rechaza la clave, o falta aceptar la licencia de ERA5",
               "Revisar la clave y aceptar la licencia de ERA5 con su cuenta en la web de Copernicus."),
    "MET-18": (FALLO, "Falta la clave de Copernicus: no se pueden preparar episodios de queja", "Poner la clave en el fichero que dice el detalle."),
    "MET-23": (AVISO, "No está la predicción GFS de ayer ni la de anteayer", "Volver a comprobar más tarde; si sigue, avisar a soporte."),
    "MET-25": (FALLO, "El servicio de la predicción GFS (NOAA) no responde: no se pueden hacer predicciones",
               "Esperar y volver a comprobar; si sigue, avisar a soporte."),
    "RED-05": (FALLO, "No hay conexión a internet: no responde ningún servicio", "Comprobar la red del equipo."),
    "RED-17": (FALLO, "Las conexiones seguras fallan (certificados o proxy de la empresa)",
               "Revisar con informática el proxy o los certificados del equipo."),
    "RED-23": (AVISO, "Un fondo del mapa no responde", "Usar el otro fondo; si sigue, avisar a soporte."),
    "RED-25": (FALLO, "Ningún fondo del mapa responde", "Comprobar la conexión; si sigue, avisar a soporte."),
}


class Problema(Exception):
    """Para cortar una prueba con su código: `raise Problema("VIE-01", "detalle")`."""

    def __init__(self, codigo, detalle=""):
        super().__init__(f"{codigo}: {detalle}")
        self.codigo, self.detalle = codigo, detalle


def _ssl():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:                                            # pragma: no cover
        return ssl.create_default_context()


def pedir(url, cabeza=False, cuanto=4096):
    """(código HTTP, tipo de contenido, los primeros `cuanto` bytes) de una petición mínima, con el agente de la planta."""
    req = urllib.request.Request(url, method="HEAD" if cabeza else "GET", headers={"User-Agent": config.AGENTE_HTTP})
    with urllib.request.urlopen(req, timeout=TIEMPO, context=_ssl()) as r:
        return r.status, r.headers.get("Content-Type", ""), (b"" if cabeza else r.read(cuanto))


def _emp():
    return config.cargar_emplazamiento()


# ── INS · instalación ──────────────────────────────────────────────────────────────────────────────────────────────
def _programa():
    import importlib
    faltan = []
    for modulo, para in (("PySide6.QtWebEngineWidgets", "el mapa"), ("rasterio", "los geodatos"), ("pyproj", "las proyecciones"),
                         ("geopandas", "los edificios"), ("numba", "el cálculo"), ("scipy", "el cálculo")):
        try:
            importlib.import_module(modulo)
        except Exception as e:                                     # noqa: BLE001
            faltan.append(f"{modulo} ({para}): {e}")
    if faltan:
        raise Problema("INS-01", "; ".join(faltan))
    from teodors import __version__
    pide = config.PLANTA.parent / "VERSION"
    if pide.is_file():
        v = pide.read_text(encoding="utf-8").strip().lstrip("v")
        if v != __version__:
            raise Problema("INS-02", f"la planta pide la {v}; este programa es la {__version__}")
    return [], f"Versión {__version__}, con sus librerías"


def _nagata():
    """La tabla de Nagata (2003) que pasa la emisión de cada gas a olor (usuario, 2026-11-08: «que compruebe que dispone de los datos para
    transformar emisiones en tasas de olor»): que esté, que se lea y que tenga sus 223 gases con umbral y masa molar."""
    import json
    from teodors.operacion import focos as F
    if not F.RUTA_NAGATA.is_file():
        raise Problema("INS-31", str(F.RUTA_NAGATA))
    try:
        gases = json.loads(F.RUTA_NAGATA.read_text(encoding="utf-8"))["gases"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise Problema("INS-32", f"{F.RUTA_NAGATA.name}: {e}") from None
    malos = [str(g.get("clave", "?")) for g in gases
             if not (isinstance(g.get("umbral_ppm"), (int, float)) and g["umbral_ppm"] > 0
                     and isinstance(g.get("masa_molar"), (int, float)) and g["masa_molar"] > 0)]
    if len(gases) != F.N_NAGATA or malos:
        raise Problema("INS-33", f"{len(gases)} de {F.N_NAGATA} gases" + (f"; sin umbral o sin masa molar: {', '.join(malos[:5])}" if malos else ""))
    return [], f"{len(gases)} gases con su umbral de olor (Nagata, 2003)"


def _libre_gb(ruta):
    return shutil.disk_usage(ruta).free / 1e9


def _escribe(carpeta):
    prueba = carpeta / f".comprobar_{dt.datetime.now():%Y%m%d%H%M%S%f}"
    prueba.write_text("ok", encoding="utf-8")
    prueba.unlink()


def _trabajo():
    d = config.DATOS
    if not config.datos_disponibles():
        raise Problema("INS-11", str(d))
    try:
        _escribe(d)
    except OSError as e:
        raise Problema("INS-17", f"{d}: {e}") from None
    libre = _libre_gb(d)
    avisos = [("INS-13", f"{d}: {_num(libre, 1)} GB libres")] if libre < 5 else []
    return avisos, f"{d}: se lee y se escribe; {_num(libre, 0)} GB libres"


def _local():
    d = config.LOCAL
    try:
        d.mkdir(parents=True, exist_ok=True)
        _escribe(d)
    except OSError as e:
        raise Problema("INS-27", f"{d}: {e}") from None
    libre = _libre_gb(d)
    avisos = [("INS-23", f"{d}: {_num(libre, 1)} GB libres")] if libre < 2 else []
    return avisos, f"{d}: se escribe; {_num(libre, 0)} GB libres"


# ── ENT · datos de entrada ─────────────────────────────────────────────────────────────────────────────────────────
def _configuracion():
    for nombre in ("planta.json", "emplazamiento.json"):
        f = config.PLANTA / nombre
        if not f.is_file():
            raise Problema("ENT-01", str(f))
        try:
            json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError) as e:
            raise Problema("ENT-02", f"{f.name}: {e}") from None
    return [], f"{config.PLANTA}: planta.json y emplazamiento.json se leen"


def _terreno():
    from teodors.fuentes import terreno
    emp = _emp()
    info = terreno.ultimo_caso(emp["lat"], emp["lon"])
    if info is None:
        raise Problema("ENT-11", str(config.DIR_TERRENO))
    try:
        Z, U, _ = terreno.cargar(info)
    except Exception as e:                                         # noqa: BLE001
        raise Problema("ENT-12", f"{info['dir']}: {e}") from None
    validos = np.isfinite(Z) & (Z > -1000)
    if not validos.any():
        raise Problema("ENT-12", "el MDT no tiene ninguna cota válida")
    avisos = [] if validos.all() else [("ENT-13", f"{_num(100 * (1 - validos.mean()), 1)} % de las celdas sin cota")]
    return avisos, (f"{_km(info['lado_km'])} × {_km(info['lado_km'])} km a {_num(info['res_m'])} m · cotas de {_num(float(Z[validos].min()))} "
                    f"a {_num(float(Z[validos].max()))} m · {len(np.unique(U[U > 0]))} usos del suelo")


def _edificios():
    from teodors.fuentes import catastro
    emp = _emp()
    try:
        info, todos = catastro.cargar(emp["lat"], emp["lon"])
    except Exception as e:                                         # noqa: BLE001
        raise Problema("ENT-22", str(e)) from None
    if todos is None:
        raise Problema("ENT-21", str(config.DIR_EDIFICIOS))
    return [], f"{_num(len(todos))} a menos de {_km(config.RADIO_EDIFICIOS_KM)} km"


def _focos():
    from teodors.operacion import focos
    try:
        datos = focos.cargar()
    except (ValueError, OSError) as e:
        raise Problema("ENT-32", str(e)) from None
    lista = datos.get("focos", [])
    if not lista:
        return [("ENT-31", str(config.FOCOS_JSON))], "Sin focos"
    def situado(f):                                                # un punto (x, y) o, los de superficie, un polígono
        u = f.get("ubicacion") or {}
        return (u.get("x") is not None and u.get("y") is not None) or len(u.get("poligono") or []) >= 3

    def emite(f):                                                  # olor con su valor, o algún gas
        return (f.get("olor") or {}).get("valor") is not None or bool(f.get("gases"))
    malos = [f.get("nombre") or f.get("id") for f in lista if not situado(f) or not emite(f)]
    avisos = [("ENT-33", ", ".join(map(str, malos)))] if malos else []
    return avisos, f"{len(lista)} focos"


def _planes():
    from teodors.operacion import planes
    d = config.DIR_PLANES
    ficheros = sorted(d.glob("*.json")) if d.is_dir() else []
    malos = []
    for f in ficheros:
        try:
            planes.cargar(f)
        except (ValueError, OSError):
            malos.append(f.name)
    avisos = [("ENT-42", ", ".join(malos))] if malos else []
    return avisos, f"{len(ficheros)} planes guardados" if ficheros else "Ningún plan guardado"


def _normativa():
    from teodors.casos import receptores
    from teodors.operacion import normativa
    try:
        n = normativa.datos()
        r = receptores.con_nombre()
    except (ValueError, OSError, KeyError) as e:
        raise Problema("ENT-52", str(e)) from None
    return [], f"{len(n.get('gases', {}))} gases con límite · {len(r)} receptores con nombre"


def _recursos():
    faltan = []
    orto = config.bloque("visor3d").get("ortofoto")
    if orto and not (config.PLANTA / orto).is_file():
        faltan.append(orto)
    icono = config.bloque("identidad").get("icono")
    if icono and not (config.PLANTA / icono).is_file():
        faltan.append(icono)
    return ([("ENT-61", ", ".join(faltan))] if faltan else []), "La ortofoto del visor 3D y el icono"


# ── VIE · viento ───────────────────────────────────────────────────────────────────────────────────────────────────
def _viento3d():
    from teodors.casos import viento3d as vc
    from teodors.operacion import viento_mapa
    serie = viento_mapa.serie_disponible()
    if serie is None:
        raise Problema("VIE-01", f"ni en {config.DIR_VIENTO_PAQUETE} ni en la carpeta de trabajo")
    meses = viento_mapa.meses(serie)
    faltan = [f"{m:02d}/{a}" for a, m in meses if vc.origen_mes(serie, a, m) is None]
    (a0, m0), (a1, m1) = meses[0], meses[-1]
    seguidos = (a1 - a0) * 12 + m1 - m0 + 1
    avisos = []
    if faltan or seguidos != len(meses):
        avisos.append(("VIE-03", ", ".join(faltan) or f"{seguidos - len(meses)} meses sin fichero entre {m0:02d}/{a0} y {m1:02d}/{a1}"))
    for a, m in sorted({meses[0], meses[-1]}):                  # el primero y el último se leen enteros, en la planta
        try:
            _, ws, _ = viento_mapa.planta_mes(serie, a, m)
        except Exception as e:                                     # noqa: BLE001
            raise Problema("VIE-02", f"{m:02d}/{a}: {e}") from None
        if not len(ws) or not np.isfinite(ws).all():
            raise Problema("VIE-02", f"{m:02d}/{a}: horas sin viento")
    return avisos, f"{len(meses)} meses, de {m0:02d}/{a0} a {m1:02d}/{a1}"


def _viento_local():
    from teodors.operacion import viento_mapa
    ruta = viento_mapa.biblioteca()
    if ruta is None:
        return [], "La planta no lleva viento alrededor de los edificios"
    if not ruta.is_file():
        return [("VIE-11", str(ruta))], "Falta"
    viento_mapa.datos_local.cache_clear()
    try:
        d = viento_mapa.datos_local()
    except Exception as e:                                         # noqa: BLE001
        raise Problema("VIE-12", f"{ruta}: {e}") from None
    return [], f"{len(d['u'])} direcciones, a {_num(d['dx'])} m"


# lo que importa cada motor para arrancar (`--motor`): lo mismo que carga al lanzarlo de verdad; «módulo:función», además, la llama
MOTORES = {"viento3d": "teodors.meteo.viento3d.principal", "puffs": "teodors.dispersion.puffs.principal",
           "visor3d": "teodors.operacion.penacho_3d:prueba"}


def _subproceso(codigo, motor):
    """Arranca `motor` como proceso aparte, igual que se lanzan los motores (`procesos.orden` y `procesos.entorno`; en el ejecutable, el
    propio .exe): (segundos, salida). Si no acaba bien, `Problema(codigo)`."""
    from teodors.comun import procesos
    t = time.time()
    que = f"el motor {motor}"
    try:
        r = subprocess.run(procesos.orden("teodors.operacion.comprobar", "--motor", motor), env=procesos.entorno(), capture_output=True,
                           text=True, encoding="utf-8",
                           errors="replace", timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as e:                                         # noqa: BLE001
        raise Problema(codigo, f"{que}: {e}") from None
    if r.returncode != 0:
        raise Problema(codigo, f"{que}: código {r.returncode}: {(r.stderr or r.stdout).strip()[-300:]}")
    return time.time() - t, r.stdout


def _motor_viento():
    seg, _ = _subproceso("VIE-22", "viento3d")
    return [], f"Arranca como proceso aparte ({_num(seg, 1)} s)"


# ── DIS · dispersión ───────────────────────────────────────────────────────────────────────────────────────────────
def _respuestas():
    from teodors.operacion import focos, serie_respuestas as SR, simulacion
    carpeta = simulacion.dir_respuestas()
    if carpeta is None:
        raise Problema("DIS-01", str(config.DIR_DISPERSION))
    try:
        ind = SR.indice(carpeta)
        p = simulacion.periodo_reanalisis()
    except Exception as e:                                         # noqa: BLE001
        raise Problema("DIS-02", f"{carpeta}: {e}") from None
    if p is None:
        raise Problema("DIS-01", f"{carpeta}: sin ningún día con respuesta de todos los focos")
    try:
        lista = focos.cargar().get("focos", [])
    except (ValueError, OSError):
        lista = []
    en = {str(k): v for k, v in ind["focos"].items()}
    sin = [str(f.get("nombre", f["id"])) for f in lista if str(f["id"]) not in en]
    cambiados = [str(f.get("nombre", f["id"])) for f in lista if str(f["id"]) in en and en[str(f["id"])].get("huella") != focos.huella(f)]
    partes = ([f"sin respuestas: {', '.join(sin)}"] if sin else []) + ([f"han cambiado: {', '.join(cambiados)}"] if cambiados else []) \
        + ([f"{len(p['huecos'])} días sin respuesta entre el primero y el último"] if p.get("huecos") else []) \
        + ([f"de prueba: {len(rep['dias'])} días simulados (semanas del "
            f"{', '.join(f'{l:%d/%m/%Y}' for l in SR.semanas_repetidas(rep))}), copiados de {rep['desde']} a {rep['hasta']}"]
           if (rep := ind.get("repetida")) else [])
    ini, fin = (dt.date.fromisoformat(p[k]) for k in ("ini", "fin"))
    return ([("DIS-03", "; ".join(partes))] if partes else []), f"De {ini:%d/%m/%Y} a {fin:%d/%m/%Y}, {len(en)} focos"


def _motor_dispersion():
    seg, _ = _subproceso("DIS-12", "puffs")
    return [], f"Arranca como proceso aparte ({_num(seg, 1)} s)"


def _visor3d():
    """Que el visor 3D dibuja: una superficie de prueba con su código, en otro proceso (`penacho_3d.prueba`), para no cargar su librería en la
    app. Ver que está pyvista no basta: carga VTK al usarlo (2026-11-10: en el ejecutable faltaba VTK y daba ✓)."""
    import importlib.util
    if importlib.util.find_spec("pyvista") is None:
        raise Problema("DIS-22", "pyvista")
    seg, _ = _subproceso("DIS-22", "visor3d")
    return [], f"Dibuja una superficie de prueba como proceso aparte ({_num(seg, 1)} s)"


def _informe():
    """El informe en PDF (`teodors.writer`; usuario, 2026-11-10: «que el writer funcione también debería ser una de las comprobaciones»): que
    está su motor (el navegador de la app, que lo imprime, y su lector de PDF) y que monta, sin imágenes, las páginas del último caso guardado:
    sus datos, sus textos y su maquetado. Sin casos guardados, solo lo primero."""
    import importlib.util
    for modulo in ("PySide6.QtWebEngineCore", "PySide6.QtPdf"):
        if importlib.util.find_spec(modulo) is None:
            raise Problema("DIS-31", modulo)
    from teodors.operacion import simulacion
    casos = sorted(simulacion.dir_guardados().glob("*/resultados/resultado.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not casos:
        return [], "Su motor está (aún no hay casos guardados para montar uno)"
    caso = casos[0].parent.parent
    t = time.time()
    try:
        from teodors.writer import datos, informe
        d = datos.reunir(caso, viento=False)
        n = informe.crear(d).html().count("<section class='pag")
    except Exception as e:                                         # noqa: BLE001
        raise Problema("DIS-32", f"{caso.name}: {type(e).__name__}: {e}") from None
    if n < 8:
        raise Problema("DIS-32", f"{caso.name}: {n} páginas, y son al menos 8")
    return [], f"Monta las {n} páginas del caso «{caso.name}» ({_num(time.time() - t, 1)} s)"


# ── MET y RED · servicios ──────────────────────────────────────────────────────────────────────────────────────────
def _responde(url, que, cae, cambia, vacio=False, **kw):
    """Texto si responde con 200 (con `que` en lo que devuelve) o, con `vacio`, con 204; si no, `Problema`: `cae` si no responde,
    `cambia` si responde mal, RED-17 si falla la conexión segura."""
    t = time.time()
    servidor = url.split("/")[2]
    try:
        codigo, tipo, cuerpo = pedir(url, **kw)
    except Exception as e:                                         # noqa: BLE001 (cualquier fallo de red es un resultado)
        motivo = getattr(e, "reason", None) or e
        if isinstance(motivo, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(motivo):
            raise Problema("RED-17", f"{servidor}: {motivo}") from None
        if getattr(e, "code", None):                               # HTTPError: responde, pero con un error
            raise Problema(cambia, f"{servidor}: HTTP {e.code}") from None
        raise Problema(cae, f"{servidor}: {motivo}") from None
    if vacio and codigo == 204:
        return f"Responde ({_num(time.time() - t, 1)} s)"
    if codigo != 200 or (que and que not in cuerpo and que not in tipo.encode()):
        raise Problema(cambia, f"{servidor}: HTTP {codigo}, {tipo or 'sin tipo'}")
    return f"Responde ({_num(time.time() - t, 1)} s)"


def _estaciones():
    from teodors.fuentes import meteocat
    texto = _responde(meteocat.URL_INVENTARIO + "?$limit=1", b"[", "MET-05", "MET-06")
    emp = _emp()
    avisos = [] if meteocat.para_mapa(emp["lat"], emp["lon"]) else [("MET-01", str(meteocat.dir_meteocat()))]
    return avisos, texto


def _era5():
    from teodors.fuentes import era5
    texto = _responde(era5.CDS_URL + "/catalogue/v1/collections/reanalysis-era5-single-levels", b"{", "MET-15", "MET-16")
    if not config.CDS_CLAVE.is_file():
        raise Problema("MET-18", str(config.CDS_CLAVE))
    try:
        era5._cliente().check_authentication()                    # la clave la lee el cliente: aquí no se ve
    except Exception as e:                                         # noqa: BLE001
        raise Problema("MET-17", str(e)) from None
    return [], f"{texto} y acepta la clave"


def _gfs():
    from teodors.fuentes import gfs_noaa
    hoy = dt.datetime.now(dt.timezone.utc).date()
    for atras in (1, 2):                                           # la de ayer, o la de anteayer si aún no está
        dia = hoy - dt.timedelta(days=atras)
        try:
            return [], f"{_responde(gfs_noaa.URL.format(d=dia, p=0), None, 'MET-25', 'MET-23', cabeza=True)}: la del {dia:%d/%m}"
        except Problema as p:
            if p.codigo != "MET-23":
                raise
    return [("MET-23", "")], "Responde, sin la predicción reciente"


def tesela(url, lat, lon, z=12):
    """La URL de la tesela de un fondo (`{z}`, `{x}`, `{y}`, Web Mercator) en la que cae el punto."""
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return url.replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))


def _fondos():
    emp = _emp()
    fondos = config.bloque("fuentes").get("fondos", [])
    if not fondos:
        return [], "La planta no tiene fondos de mapa"
    malos = []
    for nombre, url, *_ in fondos:
        try:
            _responde(tesela(url, emp["lat"], emp["lon"]), b"image", "RED-25", "RED-25")
        except Problema as p:
            if p.codigo == "RED-17":
                raise
            malos.append(f"{nombre}: {p.detalle}")
    if len(malos) == len(fondos):
        raise Problema("RED-25", "; ".join(malos))
    return ([("RED-23", "; ".join(malos))] if malos else []), f"{len(fondos) - len(malos)} de {len(fondos)} responden"


def pruebas():
    """[(clave, título, categoría, función)]. La función devuelve (avisos [(código, detalle)], texto) o lanza `Problema`."""
    return [("programa", "El programa", "INS", _programa), ("trabajo", "Carpeta de trabajo", "INS", _trabajo),
            ("local", "Carpeta local del equipo", "INS", _local), ("nagata", "Umbrales de olor (Nagata)", "INS", _nagata),
            ("configuracion", "Configuración de la planta", "ENT", _configuracion), ("terreno", "Terreno", "ENT", _terreno),
            ("edificios", "Edificios", "ENT", _edificios), ("focos", "Focos", "ENT", _focos), ("planes", "Planes", "ENT", _planes),
            ("normativa", "Normativa y receptores", "ENT", _normativa), ("recursos", "Recursos de la interfaz", "ENT", _recursos),
            ("viento3d", "Viento 3D del reanálisis", "VIE", _viento3d),
            ("viento_local", "Viento alrededor de los edificios", "VIE", _viento_local),
            ("motor_viento", "Motor del viento 3D", "VIE", _motor_viento),
            ("respuestas", "Respuestas de los focos", "DIS", _respuestas),
            ("motor_dispersion", "Motor de dispersión", "DIS", _motor_dispersion), ("visor3d", "Visor 3D", "DIS", _visor3d),
            ("informe", "Informe en PDF", "DIS", _informe),
            ("estaciones", "Estaciones", "MET", _estaciones), ("era5", "Reanálisis ERA5", "MET", _era5),
            ("gfs", "Predicción GFS", "MET", _gfs), ("fondos", "Fondos del mapa", "RED", _fondos)]


def estado_de(codigos):
    """El peor estado de unos códigos: FALLO si alguno lo es, AVISO si hay alguno, OK si ninguno."""
    gravedades = {CODIGOS[c][0] for c in codigos}
    return FALLO if FALLO in gravedades else AVISO if gravedades else OK


def _registrar(r):
    if not r["codigos"]:
        log.info(f"✓ {r['titulo']}: {r['texto']}")
    for c, detalle in r["codigos"]:
        grav, que, hacer = CODIGOS[c]
        (log.error if grav == FALLO else log.warning)(f"{MARCA[grav]} {c} · {que}" + (f" ({detalle})" if detalle else "")
                                                      + f". Qué hacer: {hacer}")


def ejecutar(sin_red=False, progreso=None, cancelado=None):
    """Las pruebas, una tras otra. `progreso(hechas, total, resultado)`, antes de cada una (estado "en_curso") y al acabarla; sus códigos,
    al registro, con qué pasa y qué hacer. Si no responde ningún servicio, además RED-05 (sin internet). Devuelve {"resultados": [{clave,
    titulo, categoria, estado, texto, codigos: [(código, detalle)]}], "categorias": {cat: {"estado", "codigos"}} (las que se han
    comprobado), "ok", "aviso" y "fallo" (cuántas categorías) y "fecha"}."""
    lista = [p for p in pruebas() if not (sin_red and p[2] in ("MET", "RED"))]
    log.info(f"Comprobar la herramienta: {len(lista)} pruebas" + (" (sin los servicios en línea)" if sin_red else ""))
    salen = []
    for k, (clave, titulo, cat, f) in enumerate(lista):
        if cancelado is not None and cancelado():
            log.warning("Comprobar la herramienta: cancelado")
            break
        base = {"clave": clave, "titulo": titulo, "categoria": cat}
        if progreso:
            progreso(k, len(lista), dict(base, estado="en_curso", texto="Comprobando…", codigos=[]))
        try:
            codigos, texto = f()
        except Problema as p:
            codigos, texto = [(p.codigo, p.detalle)], CODIGOS[p.codigo][1]
        except Exception as e:                                     # noqa: BLE001 (una prueba que revienta no para las demás)
            log.warning(f"{titulo}: la prueba falló sin código: {type(e).__name__}: {e}")
            codigos, texto = [], f"No se pudo comprobar: {type(e).__name__}: {e}"
        r = dict(base, estado=estado_de([c for c, _ in codigos]), texto=texto, codigos=codigos)
        salen.append(r)
        _registrar(r)
        if progreso:
            progreso(k + 1, len(lista), r)
    en_linea = [r for r in salen if r["categoria"] in ("MET", "RED")]
    caidos = {"MET-05", "MET-15", "MET-25", "RED-25"}
    if en_linea and len(en_linea) == sum(1 for p in pruebas() if p[2] in ("MET", "RED")) \
            and all(any(c in caidos for c, _ in r["codigos"]) for r in en_linea):
        r = {"clave": "internet", "titulo": "Internet", "categoria": "RED", "estado": FALLO, "texto": CODIGOS["RED-05"][1],
             "codigos": [("RED-05", "ninguno de los servicios responde")]}
        salen.append(r)
        _registrar(r)
    categorias = {}
    for cat, _ in CATEGORIAS:
        cods = sorted({c for r in salen for c, _ in r["codigos"] if c.startswith(cat)})
        if any(r["categoria"] == cat for r in salen) or cods:
            categorias[cat] = {"estado": estado_de(cods), "codigos": cods}
    cuenta = {e: sum(1 for c in categorias.values() if c["estado"] == e) for e in (OK, AVISO, FALLO)}
    todos = sorted({c for r in salen for c, _ in r["codigos"]})
    resumen = (f"Comprobar la herramienta: {cuenta[OK]} categorías bien, {cuenta[AVISO]} con aviso y {cuenta[FALLO]} con fallo"
               + (f" · códigos {', '.join(todos)}" if todos else ""))
    (log.error if cuenta[FALLO] else log.warning if cuenta[AVISO] else log.info)(resumen)
    return {"resultados": salen, "categorias": categorias, **cuenta, "fecha": dt.datetime.now().isoformat(timespec="seconds")}


def catalogo():
    """El catálogo de códigos, en Markdown: para soporte y para el manual."""
    lineas = ["La segunda cifra de un código dice qué le pasa al elemento, igual en todas las categorías: "
              + "; ".join(f"**{k}** {v}" for k, v in QUE_PASA.items()) + ".", ""]
    for cat, nombre in CATEGORIAS:
        elementos = "; ".join(f"{k} {v}" for k, v in ELEMENTOS[cat].items())
        lineas += [f"### {cat} · {nombre}", "", f"Elementos (primera cifra): {elementos}.", "",
                   "| Código | Gravedad | Qué pasa | Qué hacer |", "|---|---|---|---|"]
        for c in sorted(k for k in CODIGOS if k.startswith(cat)):
            grav, que, hacer = CODIGOS[c]
            lineas.append(f"| **{c}** | {MARCA[grav]} {'fallo' if grav == FALLO else 'aviso'} | {que} | {hacer} |")
        lineas.append("")
    return "\n".join(lineas)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Comprueba lo que usa la app y da un código por cada problema.")
    ap.add_argument("--sin-red", action="store_true", help="sin los servicios en línea")
    ap.add_argument("--codigos", action="store_true", help="solo el catálogo de códigos, en Markdown")
    ap.add_argument("--motor", choices=sorted(MOTORES), help="solo arrancar ese motor (lo usa la propia comprobación, en otro proceso)")
    a = ap.parse_args(argv)
    if a.motor:
        import importlib
        modulo, _, funcion = MOTORES[a.motor].partition(":")
        m = importlib.import_module(modulo)
        if funcion:
            print(getattr(m, funcion)())
        return 0
    if sys.stdout is not None:                                     # en un ejecutable sin consola no hay salida
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if a.codigos:
        print(catalogo())
        return 0
    registro.configurar(config.DIR_LOGS, config.REGISTRO)
    r = ejecutar(sin_red=a.sin_red)
    for cat, nombre in CATEGORIAS:
        if cat in r["categorias"]:
            c = r["categorias"][cat]
            print(f"{MARCA[c['estado']]} {nombre}" + (f": {', '.join(c['codigos'])}" if c["codigos"] else ""))
    print(json.dumps({k: r[k] for k in (OK, AVISO, FALLO)}))
    return 1 if r[FALLO] else 0


if __name__ == "__main__":
    sys.exit(main())
