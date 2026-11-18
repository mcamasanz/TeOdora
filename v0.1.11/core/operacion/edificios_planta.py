# -*- coding: utf-8 -*-
"""Los edificios de la planta: los que cuentan para la estela de sus chimeneas (usuario, 2026-11-08: «poder configurar los edificios vía 3
caminos, Catastro, LiDAR y dibujar/modificar desde el usuario administrador, todo en Planta y en el menú de edificios»).

Fichero: `edificios_planta.json`, en la carpeta de la planta (va con ella, como sus focos):

    {"formato": 1, "epsg": "EPSG:…", "actualizado": "aaaa-mm-dd", "edificios": [edificio, …]}
    edificio = {"id": "E01", "nombre": "…", "origen": "catastro" | "lidar" | "dibujo", "poligono": [[x, y], …], "altura_m": 12.0,
                "ref": "…"}          # «ref», la referencia del edificio descargado, si viene de uno

Los importados se llaman por su forma (`_nombrar`): «Depósito N» lo redondo (un digestor, un tanque) y «Edificio N» lo demás, del más alto al
más bajo.

Tres caminos:
- `desde_catastro`: las huellas descargadas del Catastro (`fuentes.catastro`; cada parte de una referencia, un edificio) con su altura del
  Catastro (plantas × 3 m: subestima las naves).
- `desde_lidar`: las mismas huellas con la altura que mide el LiDAR de la planta (`estela`), más lo que el LiDAR ve como edificio y el Catastro
  no tiene (manchas de lo clasificado como edificio, a más de 2,5 m sobre el suelo, de `AREA_MIN_M2` o más), con su contorno.
- a mano, solo el administrador (`gui.editor_edificios`): crear con un rectángulo, un círculo o un polígono, cambiar su forma, su nombre o su
  altura (`altura_lidar` sugiere la del LiDAR dentro del polígono) y eliminar. Un edificio tocado a mano pasa a «dibujo».

`importar` pone los de un camino automático en lugar de los automáticos que hubiera; los «dibujo» se quedan, y lo importado que pisa uno de
ellos (más del `SOLAPE` de su área), fuera.

Si la planta tiene edificios propios, la estela de las chimeneas (`estela.edificios_cerca`) usa solo esos; si no, los descargados con la altura
del LiDAR. Al cambiarlos, `recalcular_focos` rehace la estela guardada en los focos punto.
"""
import datetime as dt
import json
import math
from pathlib import Path

import numpy as np

from teodors import planta as config
from teodors.comun import registro

log = registro.get("focos")

FORMATO = 1
ORIGENES = ("catastro", "lidar", "dibujo")          # «catastro»: los edificios descargados (`fuentes.edificios` de planta.json)
AREA_MIN_M2 = 15.0           # una mancha del LiDAR más pequeña es un poste, una farola o ruido
SOLAPE = 0.3                 # lo importado que pisa más de esta fracción de su área a otro edificio no entra
SIMPLIFICA_M = 0.75          # tolerancia del contorno de las manchas del LiDAR
REDONDO = 0.9                # compacidad (4πA/P², 1 un círculo, 0,79 un cuadrado, 0,85 uno de esquinas romas) desde la que una huella es un depósito
_cache = {}


def nombre_origen(origen):
    """Cómo se llama un origen en los textos: el de los edificios descargados es el de su fuente (`fuentes.edificios` de planta.json)."""
    if origen == "catastro":
        return config.bloque("fuentes").get("edificios") or "descargados"
    return {"lidar": "LiDAR", "dibujo": "Dibujado"}.get(origen, str(origen))


def ruta():
    return Path(config.PLANTA) / "edificios_planta.json"


def vacio():
    return {"formato": FORMATO, "epsg": config.EPSG_UTM, "actualizado": dt.date.today().isoformat(), "edificios": []}


def cargar():
    """Los edificios de la planta (una copia; los leídos se guardan mientras no cambie el fichero); vacío si no hay fichero."""
    f = ruta()
    if not f.is_file():
        return vacio()
    clave = (str(f), f.stat().st_mtime)
    if _cache.get("clave") != clave:
        datos = json.loads(f.read_text(encoding="utf-8"))
        if datos.get("epsg") != config.EPSG_UTM:
            raise ValueError(f"{f.name}: coordenadas en {datos.get('epsg')}, no en {config.EPSG_UTM}")
        _cache.clear()
        _cache.update(clave=clave, datos=datos)
    return json.loads(json.dumps(_cache["datos"]))


def guardar(datos):
    """Escribe los edificios de una vez (fichero temporal y reemplazo)."""
    from teodors.operacion import focos
    datos = dict(datos, formato=FORMATO, epsg=config.EPSG_UTM, actualizado=dt.date.today().isoformat())
    focos.escribir_json(ruta(), datos)
    _cache.clear()
    return ruta()


def hay():
    """¿Tiene la planta edificios propios?"""
    return bool(cargar()["edificios"])


def nuevo_id(datos):
    usados = {e["id"] for e in datos["edificios"]}
    k = 1
    while f"E{k:02d}" in usados:
        k += 1
    return f"E{k:02d}"


def poligono(e):
    from shapely.geometry import Polygon
    return Polygon(e["poligono"])


def area_m2(e):
    return float(poligono(e).area) if len(e.get("poligono") or []) >= 3 else 0.0


def resumen(datos=None):
    """{origen: cuántos} y el total, para la página Planta."""
    datos = cargar() if datos is None else datos
    cuenta = {o: 0 for o in ORIGENES}
    for e in datos["edificios"]:
        cuenta[e.get("origen", "dibujo")] = cuenta.get(e.get("origen", "dibujo"), 0) + 1
    return {"total": len(datos["edificios"]), "por_origen": cuenta}


# ── los caminos automáticos ───────────────────────────────────────────────────────────────────────────────────
def _centro():
    from teodors.planta import geo
    emp = config.cargar_emplazamiento()
    return geo.a_utm(emp["lat"], emp["lon"])


def _partes_catastro(x, y, radio_m):
    """[(ref, polígono shapely, altura del Catastro)] de las huellas descargadas a menos de `radio_m` de (x, y)."""
    from shapely.geometry import Point
    from teodors.operacion import estela
    bld = estela._descargados()
    if bld is None or bld.empty:
        return []
    p = Point(x, y)
    salida = []
    for _, b in bld[bld.geometry.distance(p) <= radio_m].iterrows():
        partes = getattr(b.geometry, "geoms", [b.geometry])
        for k, g in enumerate(partes):
            if not g.is_empty and g.area >= 4.0:
                salida.append((str(b["ref"]) + (f"-{k + 1}" if len(partes) > 1 else ""), g, float(b["altura_m"])))
    return salida


def _como_edificio(g, altura, origen, ref=None):
    ext = g.exterior.coords[:-1] if hasattr(g, "exterior") else g.coords
    e = {"nombre": "", "origen": origen, "poligono": [[round(float(a), 2), round(float(b), 2)] for a, b in ext], "altura_m": round(float(altura), 1)}
    if ref:
        e["ref"] = ref
    return e


def redondo(g):
    """¿La huella es redonda (un digestor, un tanque)?"""
    return bool(g.length) and 4 * math.pi * g.area / g.length ** 2 >= REDONDO


def _nombrar(edificios):
    """«Depósito N» lo redondo y «Edificio N» lo demás, del más alto al más bajo (como los lista el editor)."""
    cuenta = {}
    for e in sorted(edificios, key=lambda e: -e["altura_m"]):
        clase = "Depósito" if redondo(poligono(e)) else "Edificio"
        cuenta[clase] = cuenta.get(clase, 0) + 1
        e["nombre"] = f"{clase} {cuenta[clase]}"
    return edificios


def desde_catastro(x=None, y=None, radio_m=None):
    """Las huellas del Catastro alrededor de la planta con la altura del Catastro (plantas × 3 m)."""
    from teodors.operacion import estela
    x, y = (x, y) if x is not None else _centro()
    radio_m = radio_m or config.RADIO_EDIFICIOS_FOCOS_M
    return _nombrar([_como_edificio(g, h, "catastro", ref) for ref, g, h in _partes_catastro(x, y, radio_m) if h >= estela.ALTURA_MIN_M])


def manchas_lidar():
    """[(polígono shapely, altura p90)] de lo que el LiDAR de la planta ve como edificio: lo clasificado como edificio a 2,5 m o más sobre el
    suelo (bajo los tejados no hay suelo: el de la celda más cercana que lo tenga), juntado en manchas de `AREA_MIN_M2` o más. Las que se
    tocan salen juntas (unos depósitos pegados, una mancha): se corrigen a mano."""
    from affine import Affine
    from rasterio import features
    from scipy import ndimage
    from shapely.geometry import shape
    from teodors.operacion import estela
    L = estela._lidar()
    if L is None:
        return []
    if _cache.get("manchas", (None,))[0] is not L:                 # las de este LiDAR, una vez
        _cache.pop("manchas", None)
        dtm, dse = L["dtm"], L["dsm_edif"]
        hay_suelo = np.isfinite(dtm)
        if not hay_suelo.any():
            return []
        idx = ndimage.distance_transform_edt(~hay_suelo, return_distances=False, return_indices=True)
        with np.errstate(invalid="ignore"):
            alto = np.where(np.isfinite(dse), dse - dtm[tuple(idx)], 0.0)
        # el cierre tapa los huecos sin puntos dentro de un tejado sin agrandar el contorno; la apertura quita lo suelto
        m = ndimage.binary_opening(ndimage.binary_closing(alto >= estela.ALTURA_MIN_M, iterations=1), iterations=1)
        lab, _ = ndimage.label(m)
        salida = []
        for geom, val in features.shapes(lab.astype(np.int32), mask=lab > 0, transform=Affine(1, 0, L["x0"], 0, 1, L["y0"])):
            g = shape(geom).simplify(SIMPLIFICA_M, preserve_topology=True)
            h = alto[(lab == int(val)) & (alto > 0)]
            if g.area >= AREA_MIN_M2 and len(h):
                salida.append((g, float(np.percentile(h, 90))))
        _cache["manchas"] = (L, salida)
    return _cache["manchas"][1]


def desde_lidar(x=None, y=None, radio_m=None):
    """Las huellas del Catastro con la altura que mide el LiDAR en lo que clasifica como edificio (las que el LiDAR cubre y no ve como edificio,
    fuera: una balsa, una era; las que no cubre, con la altura del Catastro), y lo que el LiDAR ve como edificio fuera de todas ellas, con su
    contorno."""
    from shapely.geometry import Point
    from shapely.ops import unary_union
    from teodors.operacion import estela
    x, y = (x, y) if x is not None else _centro()
    radio_m = radio_m or config.RADIO_EDIFICIOS_FOCOS_M
    L = estela._lidar()
    salida, huellas = [], []
    for ref, g, h_cat in _partes_catastro(x, y, radio_m):
        huellas.append(g)
        cubre = L is not None and estela._altura_lidar(g, L) is not None
        h = estela._altura_lidar(g, L, solo_edificio=True) if cubre else h_cat
        if h is not None and h >= estela.ALTURA_MIN_M:
            salida.append(_como_edificio(g, h, "lidar" if cubre else "catastro", ref))
    p = Point(x, y)
    todas = unary_union(huellas) if huellas else None
    for g, h in manchas_lidar():
        if g.distance(p) > radio_m or (todas is not None and g.intersection(todas).area > SOLAPE * g.area):
            continue
        salida.append(_como_edificio(g, h, "lidar"))
    return _nombrar(salida)


def altura_lidar(puntos):
    """La altura que mide el LiDAR dentro de un polígono [[x, y], …] (la que sugiere el editor), o None si no lo cubre."""
    from shapely.geometry import Polygon
    from teodors.operacion import estela
    L = estela._lidar()
    if L is None or len(puntos) < 3:
        return None
    h = estela._altura_lidar(Polygon(puntos), L)
    return None if h is None else round(h, 1)


def importar(datos, nuevos):
    """Pone `nuevos` (de un camino automático) en lugar de los automáticos que hubiera; los dibujados se quedan, y lo nuevo que pisa a uno de
    ellos, fuera. Devuelve los datos nuevos (no los guarda)."""
    datos = json.loads(json.dumps(datos))
    a_mano = [e for e in datos["edificios"] if e.get("origen") == "dibujo"]
    pisados = [poligono(e) for e in a_mano]
    datos["edificios"] = list(a_mano)
    for e in nuevos:
        g = poligono(e)
        if any(g.intersection(o).area > SOLAPE * g.area for o in pisados):
            continue
        datos["edificios"].append(dict(e, id=nuevo_id(datos)))
    return datos


# ── para la estela ────────────────────────────────────────────────────────────────────────────────────────────
def para_estela(x, y, radio_m):
    """Los edificios de la planta a menos de `radio_m` de (x, y), como los da `estela.edificios_cerca`."""
    from shapely.geometry import Point
    p = Point(x, y)
    salida = []
    for e in cargar()["edificios"]:
        if len(e.get("poligono") or []) < 3:
            continue
        g = poligono(e)
        d = float(g.distance(p))
        if d <= radio_m:
            salida.append({"ref": e["id"], "verts": [tuple(v) for v in e["poligono"]], "altura_m": float(e["altura_m"]),
                           "fuente": nombre_origen(e.get("origen", "dibujo")), "dist_m": round(d, 1)})
    return sorted(salida, key=lambda e: e["dist_m"])


def recalcular_focos():
    """Rehace con los edificios de ahora lo que de ellos guardan los focos: la estela de los puntos y, en las superficies que son la boca de
    un edificio (un tanque abierto, «superficie.sobre»), su contorno y su altura (si el edificio ya no está, se quedan como estaban, sin el
    enlace). Guarda los que cambian y devuelve sus ids."""
    from teodors.operacion import estela, focos
    datos = focos.cargar()
    edificios = {e["id"]: e for e in cargar()["edificios"]}
    cambiados = []
    for f in datos["focos"]:
        u = f.get("ubicacion") or {}
        sobre = (f.get("superficie") or {}).get("sobre")
        if f.get("modelo") == "superficie" and sobre:
            if sobre not in edificios:
                f["superficie"].pop("sobre")
                cambiados.append(f["id"])
            elif focos.poner_sobre(f, edificios[sobre]):
                cambiados.append(f["id"])
            continue
        if f.get("modelo") != "punto" or "x" not in u or "y" not in u:
            continue
        nueva = estela.calcular(u["x"], u["y"], f.get("altura_m")) if f.get("altura_m") else None
        if nueva != f.get("edificios"):
            if nueva is None:
                f.pop("edificios", None)
            else:
                f["edificios"] = nueva
            cambiados.append(f["id"])
    if cambiados:
        focos.guardar(datos)
        log.info(f"Focos puestos al día con los edificios: {len(cambiados)} ({', '.join(cambiados)}).")
    return cambiados


def borrar_cache():
    _cache.clear()
