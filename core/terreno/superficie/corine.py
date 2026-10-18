# -*- coding: utf-8 -*-
"""Adaptador CORINE -> AERSURFACE para Europa/España (NO forma parte de la traducción: es
una decisión nuestra, documentada aquí).

AERSURFACE solo entiende las clases NLCD de EE. UU. El adaptador:
  1. traduce cada código CORINE (CLC, 3 dígitos) a la clase NLCD equivalente con la tabla
     CLC_TO_NLCD (la misma de digicompost/getAermod.py, usada en CIERZOFLOW);
  2. reproyecta (vecino más próximo) a una Albers CENTRADA en el emplazamiento, a 30 m,
     con el píxel NW anclado en múltiplos de 30 m, y escribe GeoTIFF sin comprimir;
  3. opcionalmente hace lo mismo con impermeable y arbolado en % (en Europa existen como
     Copernicus HRL Imperviousness Density y Tree Cover Density; si no se pasan, se usa
     solo el uso del suelo, como el caso «13_solo_nlcd» de la validación).
Después se ejecuta el motor validado con un fichero de control normal.

Uso (CLI):
    python -m lagaus.terreno.superficie.corine --npz elevacion_uso.npz --lat 41.61806 --lon 0.34259 \
        --salida carpeta [--freq MONTHLY] [--sectores 12] [--ap NONAP] \
        [--clima "AVERAGE NOSNOW NONARID"] [--zorad 1.0]
"""
import argparse
from pathlib import Path

import numpy as np

# CORINE (CLC 2018) -> NLCD 2001+.  Decisión de CIERZOFLOW (getAermod.CLC_TO_NLCD).
CLC_TO_NLCD = {
    111: 24, 112: 22, 121: 23, 122: 23, 123: 23, 124: 21,      # urbano / infraestructura
    131: 31, 132: 31, 133: 31,                                  # minería, vertederos, obras
    141: 21, 142: 21,                                           # verde urbano, deportivo
    211: 82, 212: 82, 213: 82, 221: 82, 222: 82, 223: 82,       # cultivos
    231: 81, 241: 82, 242: 82, 243: 82, 244: 43,                # prados, mosaicos, agroforestal
    311: 41, 312: 42, 313: 43,                                  # bosques
    321: 71, 322: 52, 323: 52, 324: 52,                         # pastizal, matorral
    331: 31, 332: 31, 333: 31, 334: 31, 335: 12,                # desnudo, roquedo, glaciar
    411: 90, 412: 90, 421: 95, 422: 31, 423: 31,                # humedales
    511: 11, 512: 11, 521: 11, 522: 11, 523: 11,                # agua
}
RES = 30.0
SEMILADO = 7000.0          # el motor necesita ±5050 m; se deja margen para el giro y el borde


def albers_local(lat, lon):
    """Albers centrada en el emplazamiento (giro de cuadrícula ~0) con datum WGS84."""
    return (f"+proj=aea +lat_1={lat - 1.0:.4f} +lat_2={lat + 1.0:.4f} +lat_0={lat:.4f} "
            f"+lon_0={lon:.4f} +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")


def a_geotiff(clc, transform, crs, lat, lon, carpeta, prefijo="sitio", imp=None, can=None,
              codigos_usuario=None):
    """clc: array de códigos CORINE en `crs`/`transform`. imp/can: arrays opcionales en %
    (0-100) en la MISMA rejilla. Escribe <prefijo>_lc.tif (y _imp/_can) y devuelve sus rutas."""
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject
    from pyproj import Transformer
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    dst_crs = albers_local(lat, lon)
    cx, cy = Transformer.from_crs("EPSG:4326", dst_crs, always_xy=True).transform(lon, lat)
    n = int(2 * SEMILADO / RES)
    x0 = np.floor((cx - SEMILADO) / RES) * RES
    y0 = np.ceil((cy + SEMILADO) / RES) * RES
    dst_tr = from_origin(x0, y0, RES, RES)

    def warp(a, fill):
        out = np.full((n, n), fill, np.int32)
        reproject(np.asarray(a, np.int32), out, src_transform=transform, src_crs=crs,
                  dst_transform=dst_tr, dst_crs=dst_crs, resampling=Resampling.nearest,
                  src_nodata=fill, dst_nodata=fill)
        return out
    c2 = warp(clc, 0)
    lut = np.zeros(1000, np.uint8)
    for k, v in CLC_TO_NLCD.items():
        lut[k] = v
    # clases CORINE con código propio (ver «clases de usuario» en nucleo.py)
    for k, v in (codigos_usuario or {}).items():
        lut[k] = v
    nlcd = lut[np.clip(c2, 0, 999)]
    if (nlcd == 0).any():
        raise ValueError("Hay celdas sin dato o con códigos CORINE sin equivalencia dentro del "
                         f"cuadro de ±{SEMILADO / 1000:g} km: AERSURFACE abortaría (CheckLC). "
                         "Amplía el terreno de origen.")
    prof = dict(driver="GTiff", width=n, height=n, count=1, dtype="uint8", crs=dst_crs,
                transform=dst_tr, compress=None, tiled=False)
    rutas = {}
    for clave, a in (("lc", nlcd), ("imp", None if imp is None else warp(imp, 127)),
                     ("can", None if can is None else warp(can, 127))):
        if a is None:
            continue
        p = carpeta / f"{prefijo}_{clave}.tif"
        with rasterio.open(p, "w", **prof) as d:
            d.write(np.asarray(a, np.uint8), 1)
            d.update_tags(AREA_OR_POINT="Area")
        rutas[clave] = p
    return rutas


def desde_npz(npz, lat, lon, carpeta, **kw):
    """Desde el elevacion_uso.npz de digicompost (USE = CORINE, ext en EPSG:25830)."""
    from rasterio.transform import from_origin
    d = np.load(npz)
    use, ext = d["USE"], d["ext"]
    ny, nx = use.shape
    tr = from_origin(ext[0], ext[3], (ext[1] - ext[0]) / nx, (ext[3] - ext[2]) / ny)
    return a_geotiff(use, tr, "EPSG:25830", lat, lon, carpeta, **kw)


def control(rutas, lat, lon, freq="MONTHLY", sectores=12, ap="NONAP",
            clima="AVERAGE NOSNOW NONARID", zorad=1.0, titulo="AERSURFACE con CORINE",
            sfc="sitio_sfc.txt", anio=2018):
    L = ["CO STARTING", f"   TITLEONE  {titulo}", "   OPTIONS   PRIMARY ZORAD",
         f"   CENTERLL  {lat:.6f}   {lon:.6f}   NAD83",
         f'   DATAFILE  NLCD{anio}  "{rutas["lc"].name}"']
    if "can" in rutas:
        L.append(f'   DATAFILE  CNPY{anio}  "{rutas["can"].name}"')
    if "imp" in rutas:
        L.append(f'   DATAFILE  MPRV{anio}  "{rutas["imp"].name}"')
    L += [f"   ZORADIUS  {zorad}", f"   CLIMATE   {clima}",
          f"   FREQ_SECT   {freq} {sectores} {ap}", "   RUNORNOT  RUN", "CO FINISHED", "",
          "OU STARTING", f'   SFCCHAR    "{sfc}"', "OU FINISHED"]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap_ = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap_.add_argument("--npz", required=True)
    ap_.add_argument("--lat", type=float, required=True)
    ap_.add_argument("--lon", type=float, required=True)
    ap_.add_argument("--salida", required=True)
    ap_.add_argument("--freq", default="MONTHLY")
    ap_.add_argument("--sectores", type=int, default=12)
    ap_.add_argument("--ap", default="NONAP")
    ap_.add_argument("--clima", default="AVERAGE NOSNOW NONARID")
    ap_.add_argument("--zorad", type=float, default=1.0)
    a = ap_.parse_args(argv)
    rutas = desde_npz(a.npz, a.lat, a.lon, a.salida)
    inp = Path(a.salida) / "sitio.inp"
    inp.write_text(control(rutas, a.lat, a.lon, a.freq, a.sectores, a.ap, a.clima, a.zorad),
                   encoding="latin-1")
    from .__main__ import main as motor
    return motor([str(inp)])


if __name__ == "__main__":
    raise SystemExit(main())
