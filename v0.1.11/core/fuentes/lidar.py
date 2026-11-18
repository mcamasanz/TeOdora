# -*- coding: utf-8 -*-
"""De un LiDAR (nube de puntos .laz, con las clases de ASPRS) a rejillas de 1 m alrededor de una planta: terreno, superficie y clases.

Los .laz son datos descargados: esto se lanza con «python -I» desde otra carpeta, por su ruta, y solo lee números. Por eso no importa
nada del proyecto ni de teOdors, las librerías (laspy, numpy) salen de la carpeta que se le da, y no se lanza con -m. Quien lo use
desde una planta puede cargar este fichero por su ruta y darle la zona por defecto: `main(zona=…)`.

    python -I lidar.py <carpeta con los .laz> <carpeta de las librerías> <salida.npz> x y semilado
"""
import argparse
import sys
from pathlib import Path


def rejillas(carpeta, salida, xc, yc, r):
    """Lee los .laz de `carpeta` y guarda en `salida` las rejillas de 1 m del cuadrado de semilado `r` centrado en (xc, yc): dsm, dsm_edif,
    dtm, x0, y0 y los puntos por celda. Los puntos fuera del cuadrado no cuentan. laspy y numpy tienen que estar ya en el camino."""
    import laspy
    import numpy as np

    x0, y0, n = np.floor(xc - r), np.floor(yc - r), int(2 * r)
    dsm = np.full((n, n), -np.inf)          # lo más alto de cada celda, sin ruido
    dsm_edif = np.full((n, n), -np.inf)     # lo más alto clasificado como edificio: sin los cables que pasen por encima
    dtm = np.full((n, n), np.inf)           # lo más bajo clasificado como suelo
    cuenta = {c: np.zeros((n, n), np.int32) for c in ("total", "suelo", "edificio", "vegetacion")}
    clases, total = {}, 0
    for f in sorted(carpeta.glob("*.laz")):
        with laspy.open(f) as a:
            print(f.name, "puntos:", a.header.point_count, "CRS:", a.header.parse_crs(), flush=True)
            for t in a.chunk_iterator(4_000_000):
                x, y, z, c = np.asarray(t.x), np.asarray(t.y), np.asarray(t.z), np.asarray(t.classification)
                i, j = ((x - x0).astype(np.int64), (y - y0).astype(np.int64))
                ok = (i >= 0) & (i < n) & (j >= 0) & (j < n)
                i, j, z, c = i[ok], j[ok], z[ok], c[ok]
                for k, m in zip(*np.unique(c, return_counts=True)):
                    clases[int(k)] = clases.get(int(k), 0) + int(m)
                total += len(z)
                bueno = ~np.isin(c, (7, 18))        # sin ruido (clases 7 y 18 de ASPRS)
                np.maximum.at(dsm, (j[bueno], i[bueno]), z[bueno])
                s = c == 2
                np.minimum.at(dtm, (j[s], i[s]), z[s])
                np.add.at(cuenta["total"], (j[bueno], i[bueno]), 1)
                np.add.at(cuenta["suelo"], (j[s], i[s]), 1)
                e = c == 6
                np.maximum.at(dsm_edif, (j[e], i[e]), z[e])
                np.add.at(cuenta["edificio"], (j[e], i[e]), 1)
                g = np.isin(c, (3, 4, 5))
                np.add.at(cuenta["vegetacion"], (j[g], i[g]), 1)
    print("Puntos en la zona:", total, "· por clase:", clases, flush=True)
    print("Densidad media:", round(total / n ** 2, 1), "puntos/m²", flush=True)
    np.savez_compressed(salida, dsm=dsm, dsm_edif=dsm_edif, dtm=dtm, x0=x0, y0=y0, **cuenta)


def main(argv=None, zona=None):
    """`zona`: (x, y, semilado) si no se da en la línea de órdenes. Aquí no hay ninguna por defecto: es de cada planta."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("carpeta", type=Path)
    ap.add_argument("libs")
    ap.add_argument("salida", type=Path)
    ap.add_argument("zona", nargs="*", type=float, metavar="x y semilado")
    a = ap.parse_args(argv)
    if not a.zona and zona is None:
        ap.error("hace falta la zona: x y semilado")
    sys.path.insert(0, a.libs)
    xc, yc, r = a.zona[:3] if a.zona else zona
    rejillas(a.carpeta, a.salida, xc, yc, r)


if __name__ == "__main__":
    main()
