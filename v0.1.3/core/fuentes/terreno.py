# -*- coding: utf-8 -*-
"""Terreno (MDT del IGN) y uso del suelo (CORINE 2018) del dominio de DESCARGA.

Se descarga UNA vez un cuadrado extenso centrado en la planta activa y después se recorta al
dominio de cálculo que haga falta. Son servicios de España: ver README.md.

Comprobado (2026-10-14):
  · el WCS del IGN sirve el MDT en EPSG:25830 para toda la península → se reproyecta al huso
    de trabajo (config.EPSG_UTM);
  · sobre el MAR devuelve 0 m (no «sin dato»; la cabecera ni trae nodata_value);
  · la respuesta es multipart: los datos acaban en la primera línea «--».

Caso en DATOS/terreno/<lat>_<lon>_<lado>km_<res>m/:
  elevacion.tif  float32 (m), usos.tif uint16 (código CLC, 0 = sin polígono),
  corine.gpkg    extracto vectorial (para no depender del CLC nacional de 3 GB),
  info.json      metadatos y estadísticas,  mapa_*.png  capas para el mapa web.
"""
import itertools
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import numpy as np

from teodors import planta as config
from teodors.comun import mercator, registro
from teodors.comun.errores import Cancelado

log = registro.get("terreno")

WCS_BASE = "https://servicios.idee.es/wcs-inspire/mdt"
WCS_CRS = "EPSG:25830"
WCS_MAXPIX = 2000                 # px por lado y petición (límite del servidor)
WCS_TIMEOUT = 180
CORINE_CAPA = "CLC18_ES"
NODATA_USO = 0

CLC_NOMBRES = {
    111: "Tejido urbano continuo", 112: "Tejido urbano discontinuo",
    121: "Zonas industriales o comerciales", 122: "Redes viarias y ferroviarias",
    123: "Zonas portuarias", 124: "Aeropuertos", 131: "Extracción minera",
    132: "Escombreras y vertederos", 133: "Zonas en construcción", 141: "Zonas verdes urbanas",
    142: "Instalaciones deportivas y recreativas", 211: "Tierras de labor en secano",
    212: "Regadío permanente", 213: "Arrozales", 221: "Viñedos", 222: "Frutales",
    223: "Olivares", 231: "Praderas", 241: "Cultivos anuales con permanentes",
    242: "Mosaico de cultivos", 243: "Agrícola con vegetación natural",
    244: "Sistemas agroforestales", 311: "Bosque de frondosas", 312: "Bosque de coníferas",
    313: "Bosque mixto", 321: "Pastizales naturales", 322: "Landas y matorrales",
    323: "Vegetación esclerófila", 324: "Matorral boscoso de transición",
    331: "Playas, dunas y arenales", 332: "Roquedo", 333: "Vegetación escasa",
    334: "Zonas quemadas", 335: "Glaciares y nieves", 411: "Humedales", 412: "Turberas",
    421: "Marismas", 422: "Salinas", 423: "Zonas intermareales", 511: "Cursos de agua",
    512: "Láminas de agua", 521: "Lagunas costeras", 522: "Estuarios", 523: "Mares y océanos",
}
# Colores oficiales de la nomenclatura CLC
CLC_COLORES = {
    111: "#e6004d", 112: "#ff0000", 121: "#b333e6", 122: "#cc0000", 123: "#e6b3b3",
    124: "#d9bfd9", 131: "#a800cf", 132: "#a84d00", 133: "#ff4dff", 141: "#ffa6ff",
    142: "#ffe6ff", 211: "#ffffa8", 212: "#ffe64d", 213: "#e68080", 221: "#d96600",
    222: "#f2a600", 223: "#e4a100", 231: "#f2f24d", 241: "#ffe6a6", 242: "#ffff00",
    243: "#ffcc4d", 244: "#f2cca5", 311: "#80ff00", 312: "#00a600", 313: "#4de600",
    321: "#cce64d", 322: "#a5fe7f", 323: "#a5e54c", 324: "#a6e600", 331: "#e6e6e6",
    332: "#cccccc", 333: "#bffeb2", 334: "#000000", 335: "#a5e5cc", 411: "#a5a6ff",
    412: "#4d4dff", 421: "#ccccfe", 422: "#e5e5fe", 423: "#a5a5e5", 511: "#00cce6",
    512: "#a5e6e6", 521: "#00fea5", 522: "#a5fee5", 523: "#e5f2fe",
}


# Núcleos con icono: casa azul, fábrica amarilla, balón naranja.
# El 121 entra porque CORINE clasifica así muchos pueblos agrícolas pequeños; a cambio también
# marca polígonos industriales. Vías, puertos y aeropuertos (122-124) no cuentan.
FAMILIAS_NUCLEO = {"residencial": (111, 112), "industrial": (121,), "deportivo": (142,)}
NUCLEO_MIN_HA = 5.0            # descarta recortes del borde (la UMM de CORINE es 25 ha)

# Grupos de usos para el resumen en porcentajes: (nombre, color, ¿pertenece el código?)
GRUPOS_USO = [
    ("Urbano residencial", "#e6004d", lambda c: c in (111, 112)),
    ("Industrial y comercial", "#b333e6", lambda c: c == 121),
    ("Otras superficies artificiales", "#cc0000", lambda c: 122 <= c <= 142),
    ("Agrícola", "#ffe64d", lambda c: 200 <= c < 300),
    ("Forestal y matorral", "#00a600", lambda c: 300 <= c < 330),
    ("Espacios abiertos (playas, roquedo…)", "#cccccc", lambda c: 330 <= c < 400),
    ("Zonas húmedas", "#a5a6ff", lambda c: 400 <= c < 500),
    ("Aguas continentales", "#00cce6", lambda c: c in (511, 512)),
    ("Mar y aguas costeras", "#9ec9f2", lambda c: c in (521, 522, 523, NODATA_USO)),
]
BANDAS_COTA = (50, 200, 500, 1000)      # m


# ── rejilla ──────────────────────────────────────────────────────────────────────────────
def rejilla(lat, lon, lado_km, res_m=None):
    """Rejilla cuadrada en config.EPSG_UTM centrada en (lat, lon), con el origen ajustado a
    múltiplos de la resolución (rejillas de distintos casos quedan alineadas).
    Devuelve (transform, (nfilas, ncols), ext=(xmin, xmax, ymin, ymax))."""
    res_m = config.RES_TERRENO_M if res_m is None else res_m
    from rasterio.transform import from_origin
    from teodors.planta import geo
    cx, cy = geo.a_utm(lat, lon)
    n = int(round(lado_km * 1000.0 / res_m))
    xmin = np.floor((cx - n * res_m / 2) / res_m) * res_m
    ymin = np.floor((cy - n * res_m / 2) / res_m) * res_m
    ext = (xmin, xmin + n * res_m, ymin, ymin + n * res_m)
    return from_origin(ext[0], ext[3], res_m, res_m), (n, n), ext


def caso_dir(lat, lon, lado_km, res_m=None):
    res_m = config.RES_TERRENO_M if res_m is None else res_m
    return config.DIR_TERRENO / f"{lat:.5f}_{lon:.5f}_{lado_km:g}km_{res_m:g}m"


# ── MDT por WCS ──────────────────────────────────────────────────────────────────────────
def _parse_asc(texto):
    """ArcGrid ASCII dentro del multipart del WCS -> (array, transform, nodata|None)."""
    from rasterio.transform import from_origin
    lineas = texto.splitlines()
    ini = next((i for i, l in enumerate(lineas) if l.split() and l.split()[0].lower() == "ncols"),
               None)
    if ini is None:
        raise ValueError("el WCS no devolvió un grid ASC (¿excepción del servidor?): «"
                         + " ".join(texto.split())[:300] + "»")
    claves = ("ncols", "nrows", "xllcorner", "yllcorner", "xllcenter", "yllcenter",
              "cellsize", "dx", "dy", "nodata_value")
    cab, i = {}, ini
    while i < len(lineas):
        p = lineas[i].split()
        if not p:
            i += 1
            continue
        if p[0].lower() in claves and len(p) >= 2:
            cab[p[0].lower()] = p[1]
            i += 1
        else:
            break
    nc, nf = int(cab["ncols"]), int(cab["nrows"])
    cs = float(cab.get("cellsize") or cab["dx"])
    if "xllcorner" in cab:
        xll, yll = float(cab["xllcorner"]), float(cab["yllcorner"])
    else:
        xll, yll = float(cab["xllcenter"]) - cs / 2, float(cab["yllcenter"]) - cs / 2
    datos = itertools.takewhile(lambda l: not l.startswith("--"), lineas[i:])
    vals = np.array(" ".join(datos).split(), dtype="float32")
    if vals.size < nf * nc:
        raise ValueError(f"grid ASC incompleto: {vals.size} valores de {nf * nc}")
    nodata = float(cab["nodata_value"]) if "nodata_value" in cab else None
    return vals[:nf * nc].reshape(nf, nc), from_origin(xll, yll + nf * cs, cs, cs), nodata


def _wcs_tramo(cobertura, bbox, intentos=4):
    x0, y0, x1, y1 = bbox
    url = (f"{WCS_BASE}?service=WCS&version=2.0.1&request=GetCoverage&coverageId={cobertura}"
           f"&format=application/asc&subset=x({x0:.2f},{x1:.2f})&subset=y({y0:.2f},{y1:.2f})")
    ultimo = None
    for k in range(intentos):           # el WCS del IDEE falla de forma transitoria
        try:
            req = urllib.request.Request(url, headers={"User-Agent": config.AGENTE_HTTP})
            with urllib.request.urlopen(req, timeout=WCS_TIMEOUT) as r:
                return _parse_asc(r.read().decode("latin-1"))
        except (ValueError, urllib.error.URLError, TimeoutError) as e:
            ultimo = e
            log.debug(f"WCS: intento {k + 1} fallido: {e!r}")
            time.sleep(2.0 * (k + 1))
    raise RuntimeError(f"El WCS del IGN no respondió tras {intentos} intentos: {ultimo!r}")


def descargar_mdt(transform, forma, res_m, progreso=None, cancelado=None):
    """MDT del IGN remuestreado (bilineal) sobre la rejilla destino en config.EPSG_UTM."""
    from rasterio.warp import Resampling, reproject, transform_bounds
    nativa = 25 if res_m >= 25 else 5
    cobertura = f"Elevacion25830_{nativa}"
    nf, nc = forma
    xmin, ymax = transform.c, transform.f
    xmax, ymin = xmin + nc * transform.a, ymax + nf * transform.e
    b = transform_bounds(config.EPSG_UTM, WCS_CRS, xmin, ymin, xmax, ymax, densify_pts=21)
    margen = 4 * nativa
    b = (b[0] - margen, b[1] - margen, b[2] + margen, b[3] + margen)
    lado_tramo = (WCS_MAXPIX - 10) * nativa
    tx = int(np.ceil((b[2] - b[0]) / lado_tramo))
    ty = int(np.ceil((b[3] - b[1]) / lado_tramo))
    log.info(f"MDT del IGN ({cobertura}) en {tx * ty} petición(es) al WCS…")
    Z = np.full(forma, np.nan, dtype="float32")
    for k, (ix, iy) in enumerate(itertools.product(range(tx), range(ty))):
        if cancelado and cancelado():
            raise Cancelado()
        bb = (b[0] + ix * lado_tramo - margen, b[1] + iy * lado_tramo - margen,
              min(b[0] + (ix + 1) * lado_tramo, b[2]) + margen,
              min(b[1] + (iy + 1) * lado_tramo, b[3]) + margen)
        src, src_tr, nodata = _wcs_tramo(cobertura, bb)
        tmp = np.full(forma, np.nan, dtype="float32")
        reproject(source=src, destination=tmp, src_transform=src_tr, src_crs=WCS_CRS,
                  dst_transform=transform, dst_crs=config.EPSG_UTM, src_nodata=nodata,
                  dst_nodata=np.nan, resampling=Resampling.bilinear)
        Z = np.where(np.isnan(Z), tmp, Z)
        if progreso:
            progreso(5 + int(60 * (k + 1) / (tx * ty)), f"MDT: tramo {k + 1} de {tx * ty}")
    Z = np.where(Z < 0, 0.0, Z).astype("float32")      # negativos espurios a 0
    huecos = int(np.isnan(Z).sum())
    if huecos:
        log.warning(f"MDT: {huecos} celdas sin dato tras unir los tramos.")
    return Z, cobertura


# ── CORINE ───────────────────────────────────────────────────────────────────────────────
def leer_corine(transform, forma, gpkg=None):
    """Polígonos CORINE que tocan la rejilla, ya en config.EPSG_UTM (GeoDataFrame)."""
    import geopandas as gpd
    import pandas as pd
    from rasterio.warp import transform_bounds
    gpkg = gpkg or config.corine_gpkg()
    if gpkg is None:
        raise FileNotFoundError("No se encuentra CLC2018_ES.gpkg (CORINE). Indica su ruta con "
                                f"la variable de entorno {config.nombre_env('CORINE')}.")
    nf, nc = forma
    xmin, ymax = transform.c, transform.f
    xmax, ymin = xmin + nc * transform.a, ymax + nf * transform.e
    b = transform_bounds(config.EPSG_UTM, WCS_CRS, xmin, ymin, xmax, ymax, densify_pts=21)
    usos = gpd.read_file(gpkg, layer=CORINE_CAPA, bbox=(b[0] - 500, b[1] - 500,
                                                         b[2] + 500, b[3] + 500))
    usos = usos.to_crs(config.EPSG_UTM)
    # Recorte al cuadro (+500 m): hay polígonos enormes (mar, sierras) que se salen decenas
    # de km; sin recortar, el extracto pesaba 31 MB para 1132 polígonos.
    from shapely.geometry import box
    usos = gpd.clip(usos, box(xmin - 500, ymin - 500, xmax + 500, ymax + 500))
    usos["CODE_18"] = pd.to_numeric(usos["CODE_18"], errors="coerce")
    usos = usos.dropna(subset=["CODE_18"])
    usos["CODE_18"] = usos["CODE_18"].astype(int)
    return usos


def rasterizar_usos(usos, transform, forma):
    from rasterio.features import rasterize
    if usos.empty:
        return np.full(forma, NODATA_USO, dtype="uint16")
    formas = zip(usos.geometry, usos["CODE_18"])
    return rasterize(formas, out_shape=forma, transform=transform, fill=NODATA_USO,
                     dtype="uint16")


# ── estadísticas ─────────────────────────────────────────────────────────────────────────
def mascara_mar(Z, U):
    """Celdas de mar: código CLC 523, o sin polígono CORINE y a cota 0."""
    return (U == 523) | ((U == NODATA_USO) & (np.nan_to_num(Z, nan=0.0) <= 0.0))


def estadisticas(Z, U):
    mar = mascara_mar(Z, U)
    tierra = Z[~mar & np.isfinite(Z)]
    codigos, cuentas = np.unique(U[U != NODATA_USO], return_counts=True)
    total = U.size
    usos = sorted(({"codigo": int(c), "nombre": CLC_NOMBRES.get(int(c), "?"),
                    "pct": round(100.0 * n / total, 2)} for c, n in zip(codigos, cuentas)),
                  key=lambda d: -d["pct"])
    urbano = sum(d["pct"] for d in usos if d["codigo"] in (111, 112, 121))
    return {"z_min": float(tierra.min()) if tierra.size else None,
            "z_media": float(tierra.mean()) if tierra.size else None,
            "z_max": float(tierra.max()) if tierra.size else None,
            "pct_mar": round(float(100.0 * mar.sum() / total), 2),
            "pct_urbano_industrial": round(float(urbano), 2),
            "usos": usos}


def usos_por_grupo(Z, U):
    """Porcentaje del terreno de cada grupo de usos, con sus clases CLC dentro.
    Las celdas sin polígono CORINE son mar abierto (CORINE solo cubre la franja costera)."""
    codigos, cuentas = np.unique(U, return_counts=True)
    total = U.size
    grupos = []
    for nombre, color, es in GRUPOS_USO:
        clases = [{"codigo": int(c),
                   "nombre": CLC_NOMBRES.get(int(c), "Mar abierto (fuera de CORINE)"
                                             if c == NODATA_USO else "?"),
                   "color": CLC_COLORES.get(int(c), "#9ec9f2"),
                   "pct": 100.0 * n / total} for c, n in zip(codigos, cuentas) if es(int(c))]
        if clases:
            clases.sort(key=lambda d: -d["pct"])
            grupos.append({"nombre": nombre, "color": color, "clases": clases,
                           "pct": sum(d["pct"] for d in clases)})
    return grupos


def cotas_por_bandas(Z, U, cortes=BANDAS_COTA):
    """Reparto de la cota en bandas, en % de la superficie de TIERRA (sin mar)."""
    tierra = Z[~mascara_mar(Z, U) & np.isfinite(Z)]
    limites = (-np.inf, *cortes, np.inf)
    nombres = ([f"< {cortes[0]} m"] + [f"{a}–{b} m" for a, b in zip(cortes, cortes[1:])]
               + [f"> {cortes[-1]} m"])
    n, _ = np.histogram(tierra, bins=limites)
    return [{"banda": b, "pct": 100.0 * k / max(tierra.size, 1)} for b, k in zip(nombres, n)]


def nucleos(U, transform):
    """Núcleos con icono: manchas conexas (8-vecindad) de cada familia de FAMILIAS_NUCLEO.
    Devuelve [{familia, x, y, ha, codigos}] en UTM; el punto es el píxel de la mancha más
    cercano a su centroide (el centroide de una mancha en C puede caer fuera)."""
    from scipy import ndimage
    dx, dy = transform.a, -transform.e
    salida = []
    for familia, codigos in FAMILIAS_NUCLEO.items():
        mascara = np.isin(U, codigos)
        if not mascara.any():
            continue
        etiquetas, _ = ndimage.label(mascara, structure=np.ones((3, 3), dtype=int))
        for i, sl in enumerate(ndimage.find_objects(etiquetas), start=1):
            filas, cols = np.nonzero(etiquetas[sl] == i)
            ha = len(filas) * dx * dy / 1e4
            if ha < NUCLEO_MIN_HA:
                continue
            filas, cols = filas + sl[0].start, cols + sl[1].start
            j = int(np.argmin((filas - filas.mean()) ** 2 + (cols - cols.mean()) ** 2))
            salida.append({"familia": familia,
                           "x": float(transform.c + (cols[j] + 0.5) * dx),
                           "y": float(transform.f - (filas[j] + 0.5) * dy),
                           "ha": float(ha),
                           "codigos": [int(c) for c in np.unique(U[filas, cols])]})
    return salida


def resumen(Z, U, transform, lat, lon):
    """Todo lo que la interfaz enseña del terreno: grupos de usos, bandas de cota y núcleos
    (con lat/lon, distancia y rumbo desde la planta, el más cercano primero)."""
    from teodors.planta import geo
    lista = []
    for n in nucleos(U, transform):
        la, lo = geo.a_geo(n["x"], n["y"])
        d, rumbo = geo.distancia_rumbo(lat, lon, la, lo)
        lista.append(n | {"lat": la, "lon": lo, "dist_m": d, "rumbo": rumbo,
                          "tipo": " + ".join(CLC_NOMBRES.get(c, str(c)) for c in n["codigos"])})
    lista.sort(key=lambda n: n["dist_m"])
    return {"grupos": usos_por_grupo(Z, U), "bandas": cotas_por_bandas(Z, U), "nucleos": lista}


# ── Nombre de los núcleos (CORINE no los trae) ───────────────────────────────────────────
# Geocodificación inversa de CartoCiudad (IGN, CC BY 4.0) en el punto de cada núcleo: población
# y municipio. Se pide UNA vez y se guarda junto al terreno.
CARTOCIUDAD_INVERSA = "https://www.cartociudad.es/geocoder/api/geocoder/reverseGeocode"
NOMBRES_NUCLEOS = "nucleos_nombres.json"


def clave_nucleo(n):
    return f"{n['lat']:.5f},{n['lon']:.5f}"


def nombres_nucleos(info, lista, descargar=False, progreso=None):
    """{clave_nucleo: {"poblacion", "municipio"}} de la caché del terreno; con descargar=True
    pide a CartoCiudad los que falten y los guarda."""
    ruta = Path(info["dir"]) / NOMBRES_NUCLEOS
    nombres = json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else {}
    faltan = [n for n in lista if clave_nucleo(n) not in nombres]
    if not (descargar and faltan):
        return nombres
    for k, n in enumerate(faltan, 1):
        url = f"{CARTOCIUDAD_INVERSA}?lon={n['lon']:.6f}&lat={n['lat']:.6f}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": config.AGENTE_HTTP})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode("utf-8") or "{}")
        except (ValueError, urllib.error.URLError, TimeoutError, OSError) as e:
            log.warning(f"Sin nombre para el núcleo de {clave_nucleo(n)}: {e!r}")
            continue
        limpio = lambda t: (t or "").replace('"', "'").strip()      # «d"Enveja» → «d'Enveja»
        nombres[clave_nucleo(n)] = {"poblacion": limpio(d.get("poblacion") or d.get("muni")),
                                    "municipio": limpio(d.get("muni"))}
        if progreso:
            progreso(int(100 * k / len(faltan)), f"{k}/{len(faltan)} núcleos")
    ruta.write_text(json.dumps(nombres, ensure_ascii=False, indent=1), encoding="utf-8")
    return nombres


def describir_punto(Z, U, transform, lat, lon):
    """(cota, código CLC, nombre del uso) de un punto, o None si cae fuera del terreno."""
    z, u = en_punto(Z, U, transform, lat, lon)
    if z is None:
        return None
    if u == NODATA_USO:
        nombre = "Mar abierto (fuera de CORINE)" if z <= 0 else "Sin dato CORINE"
    else:
        nombre = CLC_NOMBRES.get(u, "?")
    return z, u, nombre


def en_punto(Z, U, transform, lat, lon):
    """(cota m, código CLC) de la celda que contiene (lat, lon)."""
    from teodors.planta import geo
    x, y = geo.a_utm(lat, lon)
    c, f = int((x - transform.c) // transform.a), int((transform.f - y) // -transform.e)
    if not (0 <= f < Z.shape[0] and 0 <= c < Z.shape[1]):
        return None, None
    return float(Z[f, c]), int(U[f, c])


# ── guardar / cargar ─────────────────────────────────────────────────────────────────────
def _escribe_tif(ruta, arr, transform, nodata, dtype):
    import rasterio
    tmp = ruta.with_suffix(".tmp.tif")
    with rasterio.open(tmp, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
                       count=1, dtype=dtype, crs=config.EPSG_UTM, transform=transform,
                       nodata=nodata, compress="deflate") as dst:
        dst.write(arr.astype(dtype), 1)
    tmp.replace(ruta)


def descargar(lat, lon, lado_km, res_m=None, progreso=None, cancelado=None):
    """Descarga y guarda el caso de terreno. Devuelve su info (dict)."""
    res_m = config.RES_TERRENO_M if res_m is None else res_m
    t0 = time.time()
    def avisa(p, m):
        if progreso:
            progreso(p, m)
        if cancelado and cancelado():
            raise Cancelado()

    transform, forma, ext = rejilla(lat, lon, lado_km, res_m)
    dest = caso_dir(lat, lon, lado_km, res_m)
    dest.mkdir(parents=True, exist_ok=True)
    log.info(f"Terreno: cuadrado de {lado_km:g} km a {res_m:g} m ({forma[1]}×{forma[0]} celdas) "
             f"centrado en la planta → {dest}")
    avisa(5, "Descargando el MDT del IGN")
    Z, cobertura = descargar_mdt(transform, forma, res_m, progreso, cancelado)

    avisa(70, "Leyendo CORINE 2018")
    gpkg = config.corine_gpkg()
    usos = leer_corine(transform, forma, gpkg)
    avisa(80, f"Rasterizando {len(usos)} polígonos CORINE")
    U = rasterizar_usos(usos, transform, forma)

    avisa(88, "Guardando")
    _escribe_tif(dest / "elevacion.tif", Z, transform, float("nan"), "float32")
    _escribe_tif(dest / "usos.tif", U, transform, NODATA_USO, "uint16")
    extracto = dest / "corine.gpkg"
    if extracto.exists():
        extracto.unlink()
    usos.to_file(extracto, layer=CORINE_CAPA, driver="GPKG")

    info = {"centro": {"lat": lat, "lon": lon}, "lado_km": lado_km, "res_m": res_m,
            "epsg": config.EPSG_UTM, "ext_utm": list(ext), "forma": list(forma),
            "mdt": {"fuente": "IGN · MDT por WCS (servicios.idee.es), CC BY 4.0 scne.es",
                    "cobertura": cobertura, "crs_origen": WCS_CRS, "remuestreo": "bilineal"},
            "corine": {"fuente": "CORINE Land Cover 2018 (Copernicus / IGN)",
                       "fichero": str(gpkg), "poligonos": int(len(usos))},
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "estadisticas": estadisticas(Z, U)}
    z_p, u_p = en_punto(Z, U, transform, lat, lon)
    info["planta"] = {"z": z_p, "uso": u_p, "uso_nombre": CLC_NOMBRES.get(u_p, "?")}
    avisa(93, "Preparando las capas del mapa")
    info["capas_mapa"] = imagenes_mapa(dest, Z, U, transform)
    (dest / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    e = info["estadisticas"]
    log.info(f"Terreno listo en {time.time() - t0:.0f} s · cota {e['z_min']:.0f}–{e['z_max']:.0f} m"
             f" (media {e['z_media']:.0f}) · mar {e['pct_mar']:.1f} % · {len(e['usos'])} usos CLC")
    avisa(100, "Terreno listo")
    return info | {"dir": str(dest)}


def casos():
    """Casos de terreno guardados: [{dir, info}], el de mayor lado primero."""
    res = []
    for d in config.DIR_TERRENO.glob("*km_*m"):
        f = d / "info.json"
        if f.is_file():
            try:
                res.append(json.loads(f.read_text(encoding="utf-8")) | {"dir": str(d)})
            except ValueError:
                log.warning(f"info.json ilegible en {d}")
    return sorted(res, key=lambda i: (i["lado_km"], i["fecha"]), reverse=True)


def ultimo_caso(lat, lon):
    """El caso guardado de mayor lado para esta planta (o None)."""
    for info in casos():
        c = info["centro"]
        if abs(c["lat"] - lat) < 1e-6 and abs(c["lon"] - lon) < 1e-6:
            return info
    return None


def cargar(info):
    """(Z, U, transform) de un caso guardado."""
    import rasterio
    d = Path(info["dir"])
    with rasterio.open(d / "elevacion.tif") as s:
        Z, tr = s.read(1), s.transform
    with rasterio.open(d / "usos.tif") as s:
        U = s.read(1)
    return Z, U, tr


# ── capas para el mapa web ───────────────────────────────────────────────────────────────
def a_mercator(rgba, transform, max_px=1600):
    """Reproyecta una imagen (en EPSG_UTM) a Web Mercator: `teodors.comun.mercator`."""
    return mercator.a_mercator(rgba, transform, config.EPSG_UTM, max_px)


def imagenes_mapa(dest, Z, U, transform):
    """Escribe mapa_elevacion.png y mapa_usos.png y devuelve sus metadatos para el mapa."""
    import matplotlib
    from matplotlib.colors import LightSource, LinearSegmentedColormap, to_rgba
    from PIL import Image
    mar = mascara_mar(Z, U)
    tierra = np.where(mar, np.nan, Z)
    zmin, zmax = float(np.nanmin(tierra)), float(np.nanmax(tierra))
    cmap = LinearSegmentedColormap.from_list(
        "terreno", matplotlib.colormaps["terrain"](np.linspace(0.27, 1.0, 256)))  # sin azules
    ls = LightSource(azdeg=315, altdeg=45)
    base = np.nan_to_num(Z, nan=zmin)
    rgb = ls.shade(base, cmap=cmap, norm=matplotlib.colors.Normalize(zmin, zmax),
                   vert_exag=1.5, dx=transform.a, dy=-transform.e, blend_mode="soft")
    rgba = (rgb * 255).astype("uint8")
    rgba[..., 3] = np.where(mar | ~np.isfinite(Z), 0, 255)
    img, limites = a_mercator(rgba, transform)
    Image.fromarray(img).save(dest / "mapa_elevacion.png", optimize=True)
    paradas = ", ".join(matplotlib.colors.to_hex(cmap(x)) for x in np.linspace(0, 1, 8))
    capas = [{"id": "elevacion", "nombre": "Elevación (MDT IGN)", "png": "mapa_elevacion.png",
              "bounds": limites, "leyenda": {"tipo": "continua", "min": zmin, "max": zmax,
                                             "unidad": "m", "gradiente": paradas}}]

    lut = np.zeros((1000, 4), dtype="uint8")
    for c, col in CLC_COLORES.items():
        lut[c] = [int(v * 255) for v in to_rgba(col)]
    rgba = lut[np.clip(U, 0, 999)]
    rgba[U == NODATA_USO, 3] = 0
    img, limites = a_mercator(rgba, transform)
    Image.fromarray(img).save(dest / "mapa_usos.png", optimize=True)
    st = estadisticas(Z, U)
    capas.append({"id": "usos", "nombre": "Uso del suelo (CORINE 2018)", "png": "mapa_usos.png",
                  "bounds": limites,
                  "leyenda": {"tipo": "clases", "clases": [
                      {"codigo": u["codigo"], "nombre": u["nombre"], "pct": u["pct"],
                       "color": CLC_COLORES.get(u["codigo"], "#cccccc")} for u in st["usos"]]}})
    return capas
