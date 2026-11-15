# -*- coding: utf-8 -*-
"""Lo común de las imágenes de concentración en el mapa: la escala de color, su leyenda y el dibujo en Web Mercator.
Y el tiempo en la planta para el panel del penacho animado (el penacho de un plan sale de `operacion.simulacion`).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from teodors import planta as config

ICONOS = Path(__file__).resolve().parent / "recursos" / "iconos"
DECADAS = 4                    # órdenes de magnitud de la escala de color
GRUPO = "penacho"              # el penacho y las capas de media, máximo y P98: excluyentes
OPACIDAD = 0.85                # menos transparente (usuario, 2026-11-09; antes 0,72): el penacho y sus capas de media, máximo y P98
def _num(x):
    return f"{x:.0f}" if abs(x) >= 1000 else f"{x:.3g}".replace(".", ",")


def leyenda_html(m, titulo=None):
    """Leyenda de una capa de concentración: el degradado es el de la escala elegida (--escala-…, `comun.escalas`)."""
    a = m["vmin"]
    marcas = [a * 10 ** k for k in range(int(m.get("decadas", 3)) + 1)]     # una por década
    titulo = titulo or "Penacho"
    unidad = f" ({m['unidad']})" if m.get("unidad") else ""
    return (f"<h4>{titulo}{unidad}</h4>"
            f"<div style='height:12px;border-radius:2px;background:var(--escala-{m['escala']})'></div>"
            "<div style='display:flex;justify-content:space-between;font-size:11px'>"
            + "".join(f"<span>{_num(v)}</span>" for v in marcas) + "</div>")


def pintar(campo, x, y, paso_m, vmin, vmax, ruta, decadas=DECADAS, suavizado=4, max_px=1400, escala="turbo"):
    """PNG en Web Mercator de un campo (filas de SUR a norte, centros x, y en m del UTM y paso
    paso_m) con la escala logarítmica del penacho: de vmin a vmax en `decadas` órdenes de magnitud,
    transparente por debajo de vmin. El color es el de la escala de matplotlib `escala`; con None, grises
    y lo pone el mapa (`comun.escalas`). Devuelve los límites [[s, o], [n, e]]."""
    from matplotlib import colormaps
    from PIL import Image
    from rasterio.transform import from_origin
    from scipy.ndimage import zoom

    from teodors.fuentes import terreno
    paso = paso_m / suavizado
    trf = from_origin(x[0] - paso_m / 2, y[-1] + paso_m / 2, paso, paso)
    s = np.clip(zoom(campo, suavizado, order=1), 0, None)[::-1]        # filas de norte a sur
    f = np.clip((np.log10(np.maximum(s, vmin)) - np.log10(vmin)) / decadas, 0, 1)
    alfa = np.where(s > vmin, (60 + 195 * f).astype(np.uint8), 0)
    if escala is None:
        bandas = np.dstack([np.round(255 * f).astype(np.uint8), alfa])
    else:
        bandas = (colormaps[escala](f) * 255).astype(np.uint8)
        bandas[..., 3] = alfa
    img, limites = terreno.a_mercator(bandas, trf, max_px=max_px)
    Image.fromarray(img).save(ruta, optimize=True)
    return limites


def icono_tiempo(qsw, tcc, lluvia):
    """Clave del icono (día/noche × despejado/nubes/lluvia) y texto."""
    dn, momento = ("d", "día") if (qsw or 0) > 10 else ("n", "noche")
    if lluvia is not None and lluvia > 0.1:
        return f"{dn}_rain", f"Lluvia · {momento} · {lluvia:.1f} mm/h"
    if tcc is not None and tcc > 0.25:
        return f"{dn}_cloud", f"{'Nublado' if tcc > 0.75 else 'Parcial'} · {momento}"
    return f"{dn}_clear", f"Despejado · {momento}"


def tiempo_dia(dia, serie, dias=1):
    """Tiempo, temperatura y viento en la planta hora a hora, con sus iconos (de la serie: <serie>/AAAAMM/meteo.json);
    vacío si no está: el penacho va sin su panel."""
    ini = pd.Timestamp(dia)
    de_serie = config.DIR_VIENTO3D / serie / f"{ini:%Y%m}" / "meteo.json"
    if not de_serie.is_file():
        return {}
    m = json.loads(de_serie.read_text(encoding="utf-8"))
    m = [x for x in m if ini <= pd.Timestamp(x["hora"]) < ini + pd.Timedelta(days=dias)]
    if len(m) != 24 * dias:
        return {}
    return {"meteo": m, "wsmax": max(x["ws"] for x in m), "tmin": min(x["t"] for x in m), "tmax": max(x["t"] for x in m),
            "iconos": {f.stem: f.read_text(encoding="utf-8").strip() for f in (ICONOS / "tiempo").glob("*.svg")},
            "termometro": (ICONOS / "termometro.svg").read_text(encoding="utf-8").strip()}
