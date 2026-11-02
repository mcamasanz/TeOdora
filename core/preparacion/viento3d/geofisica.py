# -*- coding: utf-8 -*-
"""Malla del viento 3D sobre un terreno fino y su fichero geofísico con `terreno.geofisica`
(fracciones de uso de CORINE y cota media por celda, y propiedades de superficie ponderadas).
Viene del proyecto de La Galera (2026-10-23)."""
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from teodors.comun import procesos


def malla(Z, U, transform, celda_m):
    """Malla de `celda_m` sobre el terreno fino (Z cotas, U códigos CORINE; transform afín de
    rasterio, filas de NORTE a sur), alineada con su esquina SUROESTE como `geofisica.corine`.
    Devuelve {"nx", "ny", "celda_m", "ext": (xmin, xmax, ymin, ymax), "Z", "U", "transform"}."""
    res = transform.a
    fac = int(round(celda_m / res))
    if abs(fac * res - celda_m) > 1e-6:
        raise ValueError("La celda del viento 3D (%g m) no es múltiplo de la del terreno" % celda_m)
    ny, nx = Z.shape[0] // fac, Z.shape[1] // fac
    x0 = transform.c
    ysur = transform.f + Z.shape[0] * transform.e               # transform.e < 0
    return {"nx": nx, "ny": ny, "celda_m": celda_m,
            "ext": (x0, x0 + nx * celda_m, ysur, ysur + ny * celda_m),
            "Z": Z, "U": U, "transform": transform}


def escribir(ruta, m, zona, mar=None, hem="N", datum="WGS-84", titulo="Malla geofísica (teOdors)"):
    """Fichero geofísico de la malla `m` (de `malla`) en `ruta`. `mar`: máscara (como Z) de las
    celdas finas de mar sin polígono de CORINE, que entran como 523 (mar); el resto de huecos
    (código 0) quedan sin dato. El motor se lanza en `<carpeta de ruta>/geofisica`.
    Devuelve {"nx", "ny", "categorias"} (categorías del viento 3D presentes)."""
    from teodors.meteo.viento3d.entradas import leer_geo
    from teodors.terreno.geofisica import corine

    ruta = Path(ruta)
    Z, U, tr = m["Z"], m["U"], m["transform"]
    uso = (np.where(mar, 523, U) if mar is not None else np.asarray(U)).astype("int32")
    z = np.maximum(np.nan_to_num(np.asarray(Z, dtype="float64"), nan=0.0), 0.0)
    ext_fina = (tr.c, tr.c + Z.shape[1] * tr.a, tr.f + Z.shape[0] * tr.e, tr.f)
    carpeta = ruta.parent / "geofisica"
    carpeta.mkdir(parents=True, exist_ok=True)
    g = corine.preparar(carpeta, np.flipud(uso), np.flipud(z), ext_fina, res_m=m["celda_m"],
                        titulo=titulo, zona=zona, hem=hem, datum=datum)  # corine: fila 0 = SUR
    if ((g["nx"], g["ny"]) != (m["nx"], m["ny"]) or abs(g["x0_km"] * 1000 - m["ext"][0]) > 0.01
            or abs(g["y0_km"] * 1000 - m["ext"][2]) > 0.01):
        raise ValueError("La malla geofísica %s no coincide con la del viento (%d×%d, %s)"
                         % (g, m["nx"], m["ny"], m["ext"]))
    rc, salida = _lanzar(carpeta)
    hecho = carpeta / "geo.dat"
    if rc or not hecho.exists():
        lst = carpeta / "geo.lst"
        raise RuntimeError("geofisica falló (rc=%s).\n%s%s" % (
            rc, salida[-800:], lst.read_text(errors="replace")[-800:] if lst.exists() else ""))
    shutil.move(str(hecho), str(ruta))
    cats = sorted(int(c) for c in np.unique(np.asarray(leer_geo(ruta)["lu"])))
    return {"nx": m["nx"], "ny": m["ny"], "categorias": cats}


def _lanzar(carpeta):
    """`python -m teodors geofisica geo.inp` en `carpeta`, en un proceso aparte: el motor busca sus
    ficheros en la carpeta actual, y cambiar la del propio proceso no vale si otros hilos preparan
    casos a la vez."""
    p = subprocess.run([sys.executable, "-m", "teodors", "geofisica", "geo.inp"], cwd=str(carpeta),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=procesos.entorno())
    return p.returncode, p.stdout + p.stderr
