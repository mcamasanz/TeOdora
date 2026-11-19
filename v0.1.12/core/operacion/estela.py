# -*- coding: utf-8 -*-
"""Los edificios alrededor de un foco punto y su estela en cada dirección del viento, sin que nadie los escriba (usuario, 2026-11-08: «que no
haya que introducir el edificio para las 36 direcciones, sino que sea el propio código, con los edificios descargados, el que configure esa
información; como una especie de radar en función de donde localice yo el punto»).

- `edificios_cerca(x, y)`: los edificios de la planta (`edificios_planta`: del Catastro, del LiDAR o dibujados por el administrador) a menos de
  `RADIO_M`; sin ellos, los descargados (`fuentes.catastro`) con su altura: la del LiDAR de la
  planta (`viento_local.lidar` de planta.json: percentil 90 de lo clasificado como edificio sobre el terreno) si lo ve con `MIN_CELDAS_LIDAR`
  celdas de 1 m o más, y si no la del Catastro (plantas × 3 m, que subestima las naves). Los de menos de `ALTURA_MIN_M`, fuera.
- `calcular(x, y, altura)`: con `terreno.edificios` (la traducción del programa de perfiles de edificios, en su modo para la estela con
  cavidad), las dimensiones del edificio que afecta a la chimenea en cada una de las 36 direcciones del VECTOR DE FLUJO (10° … 360°, hacia
  donde va el viento): alto, ancho, largo y desplazamientos. Solo cuenta un edificio si la chimenea está en su zona de influencia (a menos
  de 5 L, con L lo menor de su alto y su ancho proyectado). Más la altura de buena práctica de la chimenea: la que la sacaría de todas las estelas.
- `por_viento(estela, altura)`: por dirección de PROCEDENCIA del viento (10° … 360°), si la chimenea queda dentro de la estela del edificio
  (altura < alto + 1,5 L), que arrastra el penacho al suelo.

Lo calculado va en el foco («edificios»), lo enseña el editor y lo lee el motor (`focos.geometria`): cambia la respuesta del foco.
"""
import math
import re
import tempfile
from pathlib import Path

import numpy as np

from teodors import planta as config
from teodors.comun import registro

log = registro.get("focos")

RADIO_M = 200.0              # edificios que se miran alrededor de la chimenea (la influencia llega a 5 L: ~125 m con naves de 25 m)
MIN_CELDAS_LIDAR = 25        # celdas de 1 m clasificadas como edificio para fiarse de la altura del LiDAR
ALTURA_MIN_M = 2.5           # una caseta o un muro: no hacen estela que cuente
SIMPLIFICA_M = 0.5           # tolerancia al simplificar las huellas (el programa de perfiles va vértice a vértice)
CLAVES = ("hb", "hw", "hl", "xadj", "yadj")                  # en el foco; en el motor, HEIGHT, WIDTH, LENGTH, XBADJ e YBADJ
TARJETAS = {"BUILDHGT": "hb", "BUILDWID": "hw", "BUILDLEN": "hl", "XBADJ": "xadj", "YBADJ": "yadj"}

_cache_lidar, _cache_edificios, _cache_alturas = {}, {}, {}


def _descargados():
    """Los edificios descargados de la planta (`fuentes.catastro.cargar`), leídos una vez mientras no cambie el fichero; None si no hay."""
    from teodors.fuentes import catastro
    emp = config.cargar_emplazamiento()
    f = catastro.dir_caso(emp["lat"], emp["lon"]) / "edificios.gpkg"
    if not f.is_file():
        return None
    clave = (str(f), f.stat().st_mtime)
    if clave not in _cache_edificios:
        _cache_edificios.clear()
        _cache_edificios[clave] = catastro.cargar(emp["lat"], emp["lon"])[1]
    return _cache_edificios[clave]


def _lidar():
    """{"dsm", "dsm_edif", "dtm", "x0", "y0"} del LiDAR de 1 m de la planta (`fuentes.lidar`; fila 0, el sur), o None."""
    rel = (config.bloque("viento_local") or {}).get("lidar")
    if not rel:
        return None
    ruta = (Path(config.PLANTA) / rel).resolve()
    if not ruta.is_file():
        return None
    clave = (str(ruta), ruta.stat().st_mtime)
    if clave not in _cache_lidar:
        d = np.load(ruta)
        _cache_lidar.clear()
        _cache_lidar[clave] = {k: d[k] for k in ("dsm", "dsm_edif", "dtm")} | {"x0": float(d["x0"]), "y0": float(d["y0"])}
    return _cache_lidar[clave]


def _altura_lidar(geom, lidar, solo_edificio=False):
    """La altura de una huella con el LiDAR: el percentil 90 de lo clasificado como edificio (o, si hay poco, de todo lo que hay encima del
    suelo) menos el suelo de alrededor (bajo un tejado no hay suelo: es la mediana del terreno a menos de 5 m de la huella). None si el LiDAR
    no la cubre. Con `solo_edificio`, solo lo clasificado como edificio (en `MIN_CELDAS_LIDAR` celdas o un 30 % de la huella): si no, None,
    el LiDAR no la ve como edificio."""
    from affine import Affine
    from rasterio import features
    n, m = lidar["dtm"].shape
    x0, y0 = lidar["x0"], lidar["y0"]
    x_min, y_min, x_max, y_max = geom.bounds
    if x_min < x0 or y_min < y0 or x_max > x0 + m or y_max > y0 + n:
        return None
    tr = Affine(1, 0, x0, 0, 1, y0)
    dentro = features.geometry_mask([geom], (n, m), tr, invert=True)
    cerca = features.geometry_mask([geom.buffer(5.0)], (n, m), tr, invert=True)
    suelo = lidar["dtm"][cerca]
    suelo = suelo[np.isfinite(suelo)]
    if not len(suelo):
        return None
    capas = (("dsm_edif", min(MIN_CELDAS_LIDAR, max(1, int(0.3 * dentro.sum())))),) if solo_edificio else (("dsm_edif", MIN_CELDAS_LIDAR), ("dsm", 1))
    for capa, minimo in capas:
        z = lidar[capa][dentro]
        z = z[np.isfinite(z)]
        if len(z) >= minimo:
            return max(0.0, float(np.percentile(z, 90) - np.median(suelo)))
    return None


def edificios_cerca(x, y, radio_m=RADIO_M):
    """Los edificios a menos de `radio_m` de (x, y): [{"ref", "verts": [(x, y)…], "altura_m", "fuente", "dist_m"}], del más cercano al más
    lejano. Los de la planta (`edificios_planta`, de Catastro, LiDAR o dibujados) si los tiene; si no, los descargados con la altura del LiDAR.
    Vacío si no hay ni unos ni otros."""
    from shapely.geometry import Point
    from teodors.operacion import edificios_planta
    if edificios_planta.hay():
        return edificios_planta.para_estela(x, y, radio_m)
    bld = _descargados()
    if bld is None or bld.empty:
        return []
    p = Point(x, y)
    todos = bld
    bld = bld[bld.geometry.distance(p) <= radio_m]
    lidar = _lidar()
    de = _cache_alturas.get("de")
    if de is None or de[0] is not todos or de[1] is not lidar:      # otros edificios u otro LiDAR: a empezar
        _cache_alturas.clear()
        _cache_alturas["de"] = (todos, lidar)
    salida = []
    for i, b in bld.iterrows():
        partes = getattr(b.geometry, "geoms", [b.geometry])
        for k, g in enumerate(partes):
            if g.is_empty or g.area < 4.0:
                continue
            clave = (i, k)                                           # la altura de cada huella, una vez (mover la chimenea, ~0,05 s)
            if clave not in _cache_alturas:
                h = _altura_lidar(g, lidar) if lidar is not None else None
                _cache_alturas[clave] = (h, "LiDAR") if h is not None else (float(b["altura_m"]), edificios_planta.nombre_origen("catastro"))
            h, fuente = _cache_alturas[clave]
            if h < ALTURA_MIN_M:
                continue
            ext = g.simplify(SIMPLIFICA_M, preserve_topology=True).exterior.coords[:-1]
            salida.append({"ref": str(b["ref"]) + (f"-{k + 1}" if len(partes) > 1 else ""), "verts": [(float(a), float(c)) for a, c in ext],
                           "altura_m": round(h, 1), "fuente": fuente, "dist_m": round(float(g.distance(p)), 1)})
    return sorted(salida, key=lambda e: e["dist_m"])


def _entrada(altura_m, edificios, x, y):
    """El fichero de entrada del programa de perfiles: coordenadas locales (m, respecto a la chimenea), todo a la misma cota."""
    filas = ["'teOdors: estela de una chimenea'", "'P'", "'METERS' 1.0", "'UTMN' 0.0", str(len(edificios))]
    for k, e in enumerate(edificios, 1):
        filas += [f"'E{k:03d}' 1 0.00", f"{len(e['verts'])} {e['altura_m']:.2f}"]
        filas += [f"{a - x:.2f} {c - y:.2f}" for a, c in e["verts"]]
    filas += ["1", f"'CHIM' 0.00 {altura_m:.2f} 0.00 0.00"]
    return "\n".join(filas) + "\n"


def _leer_salida(texto):
    """Las tarjetas de la chimenea (36 valores de cada una) y la altura de buena práctica de la ecuación 1."""
    estela = {c: [] for c in CLAVES}
    for linea in texto.splitlines():
        m = re.match(r"\s*SO\s+(BUILDHGT|BUILDWID|BUILDLEN|XBADJ|YBADJ)\s+CHIM\s+(.*)$", linea)
        if m:
            estela[TARJETAS[m.group(1)]] += [float(v) for v in re.findall(r"-?\d+\.\d+", m.group(2))]
        g = re.match(r"\s*CHIM\s+(-?\d+\.\d+)\s+(?:N/A|-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)", linea)
        if g:
            estela["gep_m"] = float(g.group(2))
    if any(len(estela[c]) != 36 for c in CLAVES):
        raise RuntimeError("el cálculo de los edificios no dio las 36 direcciones")
    return estela


def calcular(x, y, altura_m, edificios=None):
    """La estela de los edificios sobre una chimenea de `altura_m` en (x, y): {"hb", "hw", "hl", "xadj", "yadj": 36 valores por dirección del
    vector de flujo, "gep_m": altura de buena práctica, "edificios": los que se miraron, sin vértices}. Sin altura o sin edificios cerca, None."""
    from teodors.terreno.edificios import nucleo
    if not altura_m or altura_m <= 0:
        return None
    edificios = edificios_cerca(x, y) if edificios is None else edificios
    if not edificios:
        return None
    with tempfile.TemporaryDirectory(prefix="estela_") as tmp:
        t = Path(tmp)
        (t / "e.inp").write_text(_entrada(float(altura_m), edificios, x, y), encoding="ascii")
        nucleo.ejecutar(t / "e.inp", t / "e.out", t / "e.sum")
        estela = _leer_salida((t / "e.out").read_text(encoding="latin-1"))
    estela = {c: [round(v, 2) for v in estela[c]] for c in CLAVES} | {"gep_m": round(estela.get("gep_m", 0.0), 2)}
    estela["edificios"] = [{k: e[k] for k in ("ref", "altura_m", "fuente", "dist_m")} for e in edificios]
    return estela


def precargar():
    """Lee ya los edificios descargados y el LiDAR, y deja listo el cálculo (la primera vez, ~1 s): el editor lo llama al abrirse, en
    segundo plano, para que marcar la chimenea responda al momento (luego, ~0,1 s por posición)."""
    try:
        from teodors.planta import geo
        emp = config.cargar_emplazamiento()
        x, y = geo.a_utm(emp["lat"], emp["lon"])
        edificios_cerca(x, y, radio_m=2 * RADIO_M)                 # y las alturas de las huellas de la planta
        # con sus edificios de verdad: con pocos, el programa de perfiles va por su vía sencilla y no carga la compilada
        calcular(x, y, 10.0, edificios_cerca(x, y) or [{"ref": "_", "verts": [(5.0, -5.0), (15.0, -5.0), (15.0, 5.0), (5.0, 5.0)],
                                                       "altura_m": 8.0, "fuente": "_", "dist_m": 5.0}])
    except Exception as e:                                           # noqa: BLE001 — solo adelanta trabajo: si falla, se hará al marcar
        log.debug(f"No se pudo precargar la estela de los edificios: {e}")


def sector_flujo(procedencia):
    """Índice (0…35) de la dirección del vector de flujo para un viento que VIENE de `procedencia` grados (10, 20 … 360)."""
    return (round(((procedencia + 180.0) % 360.0) / 10.0) - 1) % 36


def por_viento(estela, altura_m):
    """Por procedencia del viento (10° … 360°): [{"desde", "alto", "ancho", "libre_m", "dentro"}]: el edificio que afecta, la altura que
    sacaría a la chimenea de su estela (alto + 1,5 L) y si queda dentro."""
    salida = []
    for k in range(36):
        desde = 10.0 * (k + 1)
        s = sector_flujo(desde)
        hb, hw = (estela or {}).get("hb", [0.0] * 36)[s], (estela or {}).get("hw", [0.0] * 36)[s]
        libre = hb + 1.5 * min(hb, hw) if hb > 0 else 0.0
        salida.append({"desde": desde, "alto": hb, "ancho": hw, "libre_m": libre, "dentro": bool(hb > 0 and (altura_m or 0) < libre)})
    return salida


def resumen(estela, altura_m):
    """(direcciones de 36 en las que la chimenea queda en la estela, la altura que la sacaría de todas)."""
    filas = por_viento(estela, altura_m)
    return sum(f["dentro"] for f in filas), max((f["libre_m"] for f in filas), default=0.0)


def para_motor(estela):
    """Las tarjetas del efecto edificio del motor (HEIGHT, WIDTH, LENGTH, XBADJ, YBADJ), o None si ningún edificio afecta a la chimenea."""
    if not estela or not any(v > 0 for v in estela.get("hb", ())):
        return None
    return {"HEIGHT": estela["hb"], "WIDTH": estela["hw"], "LENGTH": estela["hl"], "XBADJ": estela["xadj"], "YBADJ": estela["yadj"]}


def angulo_texto(grados):
    """«N», «NNE»… de una procedencia en grados."""
    rosa = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO")
    return rosa[int(math.floor(((grados % 360.0) + 11.25) / 22.5)) % 16]
