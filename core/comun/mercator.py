# -*- coding: utf-8 -*-
"""Reproyectar una imagen a Web Mercator, que es como la pinta un mapa web: así cae exactamente en su
sitio al colocarla por sus esquinas."""
import numpy as np


def a_mercator(bandas, transform, epsg, max_px=1600):
    """`bandas`: imagen en `epsg` (filas, columnas y bandas: RGBA, o gris y alfa; uint8). `transform`: su
    transformación afín. Vecino más cercano, sin mezclar valores. Devuelve (bandas, [[sur, oeste],
    [norte, este]]), con el lado mayor limitado a `max_px`."""
    from pyproj import Transformer
    from rasterio.warp import Resampling, calculate_default_transform, reproject
    nf, nc = bandas.shape[:2]
    b = (transform.c, transform.f + nf * transform.e, transform.c + nc * transform.a, transform.f)
    tr, w, h = calculate_default_transform(epsg, "EPSG:3857", nc, nf, *b)
    escala = max(w, h) / max_px
    if escala > 1:
        tr, w, h = calculate_default_transform(epsg, "EPSG:3857", nc, nf, *b,
                                               dst_width=int(w / escala),
                                               dst_height=int(h / escala))
    out = np.zeros((bandas.shape[2], h, w), dtype="uint8")
    for k in range(bandas.shape[2]):
        reproject(source=np.ascontiguousarray(bandas[..., k]), destination=out[k],
                  src_transform=transform, src_crs=epsg, dst_transform=tr,
                  dst_crs="EPSG:3857", resampling=Resampling.nearest)
    t = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    oeste, norte = t.transform(tr.c, tr.f)
    este, sur = t.transform(tr.c + w * tr.a, tr.f + h * tr.e)
    return np.moveaxis(out, 0, -1), [[sur, oeste], [norte, este]]
