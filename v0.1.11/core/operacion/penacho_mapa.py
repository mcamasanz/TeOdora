# -*- coding: utf-8 -*-
"""Lo común de las imágenes de concentración en el mapa: la escala de color, su leyenda y el dibujo en Web Mercator.
Y el tiempo en la planta para el panel del penacho animado (el penacho de un plan sale de `operacion.simulacion`).
"""
import json
import math
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


def paso_redondo(ancho, partes=5):
    """Un paso «redondo» (1, 2, 2,5 o 5 por una potencia de 10) que parte `ancho` en unas `partes` (de 4 a 8)."""
    if not ancho > 0:
        return 1.0
    bruto = ancho / partes
    base = 10.0 ** math.floor(math.log10(bruto))
    return next((m * base for m in (1.0, 2.0, 2.5, 5.0) if bruto <= m * base * (1 + 1e-9)), 10.0 * base)


def redondo_arriba(valor):
    """El primer valor «redondo» (múltiplo de su `paso_redondo`) que no baja de `valor`: el final de un rango automático en escala normal."""
    paso = paso_redondo(valor)
    return max(paso, math.ceil(valor / paso - 1e-9) * paso)


def marcas_rango(vmin, vmax, lineal=False):
    """Las marcas de la leyenda de un rango, [(valor, sitio de 0 a 1)]: sus extremos y, dentro, las potencias de 10 (escala logarítmica) o los
    múltiplos de su paso redondo (escala normal), sin las que quedan pegadas a un extremo."""
    if lineal:
        paso = paso_redondo(vmax - vmin)
        dentro = [k * paso for k in range(math.floor(vmin / paso) + 1, math.ceil(vmax / paso))]
        sitio = lambda v: (v - vmin) / (vmax - vmin)                                   # noqa: E731
    else:
        a, b = math.log10(vmin), math.log10(vmax)
        dentro = [10.0 ** k for k in range(math.floor(a) + 1, math.ceil(b))]
        sitio = lambda v: (math.log10(v) - a) / (b - a)                                # noqa: E731
    return [(vmin, 0.0)] + [(v, sitio(v)) for v in dentro if 0.06 < sitio(v) < 0.94] + [(vmax, 1.0)]


def leyenda_rango(titulo, unidad, escala, vmin, vmax, lineal=False):
    """Leyenda del degradado con otro rango o con la escala normal (la barra del mapa, usuario, 2026-11-17): el degradado de la escala
    elegida (--escala-…) y cada marca en su sitio."""
    unidad = f" ({unidad})" if unidad else ""

    def marca(v, p):
        mover = "0" if p <= 0 else ("-100%" if p >= 1 else "-50%")
        return f"<span style='position:absolute;left:{100 * p:.1f}%;transform:translateX({mover})'>{_num(v)}</span>"
    return (f"<h4>{titulo}{unidad} · escala {'normal' if lineal else 'logarítmica'}</h4>"
            f"<div style='height:12px;border-radius:2px;background:var(--escala-{escala})'></div>"
            "<div style='position:relative;height:15px;font-size:11px'>"
            + "".join(marca(v, p) for v, p in marcas_rango(vmin, vmax, lineal)) + "</div>")


def pintar(campo, x, y, paso_m, vmin, vmax, ruta, decadas=DECADAS, suavizado=4, max_px=1400, escala="turbo", lineal=False, solo_en=None):
    """PNG en Web Mercator de un campo (filas de SUR a norte, centros x, y en m del UTM y paso
    paso_m) con la escala logarítmica del penacho: de vmin a vmax en `decadas` órdenes de magnitud,
    transparente por debajo de vmin. El color es el de la escala de matplotlib `escala`; con None, grises
    y lo pone el mapa (`comun.escalas`). Con `lineal` (la barra del mapa), la escala normal: de vmin a vmax en
    proporción al valor, transparente por debajo de vmin o, si vmin es 0, del 1 % de vmax (si no, todo el
    dominio saldría teñido). Con `solo_en` (`hueco_mercator`), transparente fuera de ese hueco. Devuelve los límites [[s, o], [n, e]]."""
    from matplotlib import colormaps
    from PIL import Image
    from rasterio.transform import from_origin
    from scipy.ndimage import zoom

    from teodors.fuentes import terreno
    paso = paso_m / suavizado
    trf = from_origin(x[0] - paso_m / 2, y[-1] + paso_m / 2, paso, paso)
    s = np.clip(zoom(campo, suavizado, order=1), 0, None)[::-1]        # filas de norte a sur
    if lineal:
        f = np.clip((s - vmin) / (vmax - vmin), 0, 1)
        alfa = np.where(s > (vmin if vmin > 0 else vmax / 100.0), (60 + 195 * f).astype(np.uint8), 0)
    else:
        f = np.clip((np.log10(np.maximum(s, vmin)) - np.log10(vmin)) / decadas, 0, 1)
        alfa = np.where(s > vmin, (60 + 195 * f).astype(np.uint8), 0)
    if escala is None:
        bandas = np.dstack([np.round(255 * f).astype(np.uint8), alfa])
    else:
        bandas = (colormaps[escala](f) * 255).astype(np.uint8)
        bandas[..., 3] = alfa
    img, limites = terreno.a_mercator(bandas, trf, max_px=max_px)
    if solo_en is not None:
        img[..., -1] = np.where(_centros_en(limites, img.shape[:2], *solo_en), img[..., -1], 0)
    Image.fromarray(img).save(ruta, optimize=True)
    return limites


def hueco_mercator(hueco, x, y, paso_m, max_px):
    """El hueco de una rejilla (bool, filas de SUR a norte, como el campo de `pintar`) tal como queda en la imagen que `pintar` hace de
    ella con `suavizado` 1 y `max_px`: (máscara en Web Mercator, sus límites). Sirve para recortar la imagen de la rejilla de dentro justo
    a él (`pintar(…, solo_en=)`): las dos imágenes, sin pisarse ni dejar hueco (usuario, 2026-11-17: una raya en cuadrado a 3 km en el
    degradado, donde se pisaban)."""
    from rasterio.transform import from_origin

    from teodors.fuentes import terreno
    trf = from_origin(x[0] - paso_m / 2, y[-1] + paso_m / 2, paso_m, paso_m)
    banda = np.where(np.asarray(hueco, bool)[::-1], 255, 0).astype(np.uint8)[..., None]
    img, limites = terreno.a_mercator(banda, trf, max_px=max_px)
    return img[..., 0] > 0, limites


def _centros_en(limites, forma, mascara, lim_mascara):
    """¿Cae el centro de cada píxel de una imagen en Web Mercator (`limites`, `forma`) donde `mascara` (otra, con `lim_mascara`) es True?"""
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)

    def caja(lim):
        (s, o), (n, e) = lim
        x0, y0 = t.transform(o, n)
        x1, y1 = t.transform(e, s)
        return x0, y0, x1, y1
    x0, y0, x1, y1 = caja(limites)
    h, w = forma
    mx0, my0, mx1, my1 = caja(lim_mascara)
    mh, mw = mascara.shape
    j = np.floor((x0 + (np.arange(w) + 0.5) * (x1 - x0) / w - mx0) / (mx1 - mx0) * mw).astype(int)
    i = np.floor((my0 - (y0 - (np.arange(h) + 0.5) * (y0 - y1) / h)) / (my0 - my1) * mh).astype(int)
    vale_i, vale_j = (i >= 0) & (i < mh), (j >= 0) & (j < mw)
    sale = np.zeros(forma, bool)
    sale[np.ix_(vale_i, vale_j)] = mascara[np.ix_(i[vale_i], j[vale_j])]
    return sale


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
