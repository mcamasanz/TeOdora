# -*- coding: utf-8 -*-
"""Edificios del Catastro (WFS INSPIRE Buildings) a menos de config.RADIO_EDIFICIOS_KM de la
planta. Se descarga UNA vez y después se carga del disco.

El servicio, comprobado:
  · el servicio rechaza bbox > ~0,81 km² o > 5000 elementos: teselas de 0,8 km que se
    subdividen solas si el Catastro las rechaza (se distingue «límite» de «sin datos»);
  · dos capas en paralelo: bu:Building (huella + currentUse) y bu:BuildingPart (plantas),
    unidas por punto interior;
  · certificado SSL del Catastro: hace falta certifi;
  · ⚠️ altura = plantas × 3 m: SUBESTIMA naves industriales (10-12 m con una planta) y no es
    conservador para el downwash. Las naves y digestores de la planta, con altura real.
Licencia: solo se guarda el dato TRANSFORMADO; no se redistribuye el GML original.

Caché: DATOS/edificios/<lat>_<lon>_r<radio>km/edificios.gpkg (EPSG de config) + info.json
"""
import json
import ssl
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from teodors import planta as config
from teodors.comun import registro

log = registro.get("edificios")

WFS_BU = "https://ovc.catastro.meh.es/INSPIRE/wfsBU.aspx"
WFS_CRS = "EPSG:25830"          # el probado; se reproyecta a config.EPSG_UTM
TESELA_KM = 0.8
TESELA_MIN_KM = 0.2
TIMEOUT = 120
ALTURA_PLANTA_M = 3.0

USO_COLOR = {
    "Residencial": "#4575b4", "Industrial": "#984ea3", "Comercial": "#ff7f00",
    "Oficinas": "#009e9e", "Serv. públicos": "#a65628", "Comercio/serv.": "#fdae61",
    "Agrario": "#66bd63", "Otro": "#999999",
}

try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:                                                   # noqa: BLE001
    _SSL = ssl.create_default_context()


def uso_legible(cu):
    """Código INSPIRE currentUse -> etiqueta."""
    cu = "" if cu is None else str(cu)
    if cu.startswith("1_"):
        return "Residencial"
    if cu.startswith("2_"):
        return "Agrario"
    if cu.startswith("3_"):
        return "Industrial"
    if cu == "4_1_office":
        return "Oficinas"
    if cu == "4_2_retail":
        return "Comercial"
    if cu == "4_3_publicServices":
        return "Serv. públicos"
    if cu.startswith("4"):
        return "Comercio/serv."
    return "Otro"


def dir_caso(lat, lon, radio_km=None):
    radio_km = config.RADIO_EDIFICIOS_KM if radio_km is None else radio_km
    return config.DIR_EDIFICIOS / f"{lat:.5f}_{lon:.5f}_r{radio_km:g}km"


# ── WFS ──────────────────────────────────────────────────────────────────────────────────
def _http(url):
    req = urllib.request.Request(url, headers={"User-Agent": config.AGENTE_HTTP})
    for k in range(3):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if k == 2:
                raise
            log.debug(f"Catastro: reintento {k + 1} ({e!r})")
            time.sleep(5 * (k + 1))


def _bbox(capa, bx0, by0, bx1, by1, cuenta):
    """Una capa en un bbox; si el Catastro lo rechaza por límite, lo divide en 4."""
    import geopandas as gpd
    url = (f"{WFS_BU}?service=WFS&version=2.0.0&request=GetFeature&typenames={capa}"
           f"&srsname={WFS_CRS}&bbox={bx0},{by0},{bx1},{by1},{WFS_CRS}")
    try:
        data = _http(url)
    except Exception as e:                                          # noqa: BLE001
        cuenta["fallos"] += 1
        log.warning(f"Catastro {capa}: fallo en la tesela {int(bx0)},{int(by0)}: {e!r}")
        return []
    if b"ExceptionReport" in data[:2000]:
        txt = data[:2000].decode("latin-1", "ignore").lower()
        es_limite = any(k in txt for k in ("exced", "exceed", "máx", "max", "límit", "limit",
                                           "too many", "number of features", "5000",
                                           "superad", "demasiad"))
        lado_km = max(bx1 - bx0, by1 - by0) / 1000.0
        if es_limite and lado_km > TESELA_MIN_KM:
            mx, my = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
            out = []
            for q in ((bx0, by0, mx, my), (mx, by0, bx1, my), (bx0, my, mx, by1),
                      (mx, my, bx1, by1)):
                out += _bbox(capa, *q, cuenta)
            return out
        if es_limite:
            cuenta["saturadas"] += 1
        return []
    tmp = tempfile.NamedTemporaryFile(suffix=".gml", delete=False)
    tmp.write(data)
    tmp.close()
    try:
        g = gpd.read_file(tmp.name)
    except Exception as e:                                          # noqa: BLE001
        log.debug(f"Catastro {capa}: GML ilegible en {int(bx0)},{int(by0)}: {e!r}")
        g = None
    finally:
        Path(tmp.name).unlink(missing_ok=True)
    return [g] if g is not None and len(g) else []


def _capa(capa, limites):
    import geopandas as gpd
    x0, y0, x1, y1 = limites
    t = TESELA_KM * 1000
    cuenta = {"fallos": 0, "saturadas": 0}
    partes = []
    for ix in range(int(np.ceil((x1 - x0) / t))):
        for iy in range(int(np.ceil((y1 - y0) / t))):
            bx0, by0 = x0 + ix * t, y0 + iy * t
            partes += _bbox(capa, bx0, by0, min(bx0 + t, x1), min(by0 + t, y1), cuenta)
    if cuenta["saturadas"]:
        log.warning(f"Catastro {capa}: {cuenta['saturadas']} teselas mínimas aún rechazadas "
                    "(zona muy densa): puede faltar algún edificio.")
    if cuenta["fallos"]:
        log.warning(f"Catastro {capa}: {cuenta['fallos']} teselas sin respuesta.")
    if not partes:
        return None
    g = gpd.GeoDataFrame(pd.concat(partes, ignore_index=True), crs=partes[0].crs)
    clave = next((k for k in ("localId", "gml_id") if k in g.columns), None)
    if clave:
        g = g.drop_duplicates(subset=clave)
    return g.reset_index(drop=True)


# ── descarga ─────────────────────────────────────────────────────────────────────────────
def descargar(lat, lon, radio_km=None, progreso=None):
    """Descarga los edificios a menos de `radio_km` de la planta y los guarda. Devuelve info."""
    radio_km = config.RADIO_EDIFICIOS_KM if radio_km is None else radio_km
    import geopandas as gpd
    from rasterio.warp import transform_bounds
    from shapely.geometry import Point
    from teodors.planta import geo
    t0 = time.time()
    cx, cy = geo.a_utm(lat, lon)
    r = radio_km * 1000.0
    lim = transform_bounds(config.EPSG_UTM, WFS_CRS, cx - r, cy - r, cx + r, cy + r,
                           densify_pts=21)
    if progreso:
        progreso(10, "Descargando edificios del Catastro")
    res = {}
    hilos = [threading.Thread(target=lambda c=c: res.__setitem__(c, _capa(c, lim)))
             for c in ("bu:Building", "bu:BuildingPart")]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    bld, part = res.get("bu:Building"), res.get("bu:BuildingPart")
    if bld is None or bld.empty:
        raise RuntimeError("El Catastro no devolvió edificios en la zona.")
    if progreso:
        progreso(70, f"Uniendo {len(bld)} edificios con sus plantas")

    # Plantas por edificio = máximo de sus partes (unión por punto interior)
    if part is not None and len(part):
        part = part.to_crs(bld.crs).copy()
        part["fl"] = pd.to_numeric(part.get("numberOfFloorsAboveGround"),
                                   errors="coerce").fillna(0)
        pts = part[["fl", "geometry"]].copy()
        pts["geometry"] = part.representative_point()
        j = gpd.sjoin(pts, bld[["geometry"]], predicate="within")
        bld["plantas"] = bld.index.map(j.groupby("index_right")["fl"].max()).fillna(0)
    else:
        bld["plantas"] = 0.0
    bld["plantas"] = bld["plantas"].astype(int)
    bld["altura_m"] = bld["plantas"] * ALTURA_PLANTA_M
    bld["uso"] = bld["currentUse"].map(uso_legible) if "currentUse" in bld else "Otro"
    bld["uso_inspire"] = bld.get("currentUse", "")
    bld["ref"] = bld.get("localId", bld.get("gml_id", ""))

    bld = bld.to_crs(config.EPSG_UTM)
    circulo = Point(cx, cy).buffer(r, 128)
    bld = bld[bld.intersects(circulo)].copy()
    bld["dist_m"] = bld.geometry.distance(Point(cx, cy))
    bld["area_m2"] = bld.geometry.area
    bld = bld[["ref", "uso", "uso_inspire", "plantas", "altura_m", "area_m2", "dist_m",
               "geometry"]].sort_values("dist_m").reset_index(drop=True)

    dest = dir_caso(lat, lon, radio_km)
    dest.mkdir(parents=True, exist_ok=True)
    f = dest / "edificios.gpkg"
    if f.exists():
        f.unlink()
    bld.to_file(f, layer="edificios", driver="GPKG")
    info = {"centro": {"lat": lat, "lon": lon}, "radio_km": radio_km, "epsg": config.EPSG_UTM,
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "fuente": "Dirección General del Catastro · WFS INSPIRE Buildings "
                      "(dato transformado: huella, uso y plantas)",
            "altura": f"estimada = plantas × {ALTURA_PLANTA_M:g} m (subestima naves)"}
    info.update(resumen(bld))
    (dest / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    log.info(f"Edificios: {len(bld)} a menos de {radio_km:g} km en {time.time() - t0:.0f} s · "
             + ", ".join(f"{k} {v}" for k, v in info["por_uso"].items()))
    if progreso:
        progreso(100, "Edificios listos")
    return info | {"dir": str(dest)}


def resumen(bld):
    por_uso = bld["uso"].value_counts().to_dict()
    cerca = bld.iloc[0] if len(bld) else None
    return {"n": int(len(bld)), "por_uso": {k: int(v) for k, v in por_uso.items()},
            "superficie_m2": float(bld["area_m2"].sum()),
            "altura_max_m": float(bld["altura_m"].max()) if len(bld) else 0.0,
            "mas_cercano": None if cerca is None else {
                "uso": cerca["uso"], "dist_m": float(cerca["dist_m"]),
                "plantas": int(cerca["plantas"])}}


def cercanos(bld, radio_m=None):
    """Los edificios a menos de `radio_m` de la planta (los que afectan a los focos)."""
    radio_m = config.RADIO_EDIFICIOS_FOCOS_M if radio_m is None else radio_m
    return bld[bld["dist_m"] <= radio_m].copy()


# ── carga ────────────────────────────────────────────────────────────────────────────────
def cargar(lat, lon, radio_km=None):
    """(info, GeoDataFrame) del caso guardado, o (None, None)."""
    import geopandas as gpd
    d = dir_caso(lat, lon, radio_km)
    if not (d / "info.json").is_file() or not (d / "edificios.gpkg").is_file():
        return None, None
    info = json.loads((d / "info.json").read_text(encoding="utf-8")) | {"dir": str(d)}
    return info, gpd.read_file(d / "edificios.gpkg", layer="edificios")


def geojson_mapa(bld):
    """GeoJSON (lat/lon) para el mapa: edificios coloreados por uso."""
    from shapely.geometry import mapping
    g = bld.to_crs("EPSG:4326")
    feats = []
    for _, b in g.iterrows():
        texto = (f"<b>{b['uso']}</b><br>{int(b['plantas'])} planta(s) · ≈ {b['altura_m']:.0f} m "
                 f"(estimada)<br>{b['area_m2']:.0f} m² · a {b['dist_m']:.0f} m de la planta"
                 f"<br><span style='color:var(--tenue)'>{b['ref']}</span>")
        feats.append({"type": "Feature", "geometry": mapping(b.geometry),
                      "properties": {"color": USO_COLOR.get(b["uso"], "#999999"),
                                     "texto": texto}})
    return {"type": "FeatureCollection", "features": feats}


def en_punto(bld, lat, lon):
    """Edificio que contiene el punto (fila) o None."""
    from shapely.geometry import Point
    from teodors.planta import geo
    p = Point(*geo.a_utm(lat, lon))
    hit = bld[bld.contains(p)]
    return None if hit.empty else hit.iloc[0]
