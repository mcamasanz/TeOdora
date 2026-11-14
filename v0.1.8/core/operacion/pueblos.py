# -*- coding: utf-8 -*-
"""Los pueblos de las tablas de resultados y del informe (usuario, 2026-11-10: un pueblo a 1,5 km de la planta no salía). Son los núcleos
urbanos de CORINE (`fuentes.terreno.nucleos`) y los que la planta añade a mano en planta.json, «pueblos»: los que CORINE no tiene como
núcleo, porque no cartografía lo que mide menos de 25 ha y un casco pequeño o en trozos le sale como cultivo.

Cada pueblo vale lo que el peor de sus receptores (usuario, 2026-11-10: «el peor receptor dentro de su contorno, también los de CORINE»):
los de dentro de su mancha urbana de CORINE o de su contorno de planta.json, es decir, el punto del núcleo, las viviendas del Catastro y la
malla. No hace falta volver a calcular: esos receptores ya están en la serie.

    etiquetas(etiquetas, x, y)   las del índice de los receptores, con «receptores» en cada pueblo y los de la planta añadidos
    firma()                      cambia con cómo se reparten (VERSION) o con los pueblos de la planta: lo guardado se rehace al leerlo
    de_la_planta()               los pueblos de planta.json
    centros()                    dónde va el icono de cada uno de ellos en el mapa
"""
import hashlib
import json

import numpy as np

from teodors import planta as config
from teodors.comun import registro

log = registro.get("pueblos")

VERSION = 1                     # cómo se reparten los receptores entre los pueblos: al cambiarlo, las tablas guardadas se rehacen al leerlas


def de_la_planta():
    """[{"nombre", "contorno"}] de planta.json, «pueblos» › «lista»: los pueblos añadidos a mano. «contorno»: sus anillos, cada uno
    [[lon, lat], …] en grados; un punto está dentro si lo rodea un número impar de anillos (así caben los huecos)."""
    salen = []
    for p in config.bloque("pueblos").get("lista", []):
        if p.get("nombre") and p.get("contorno"):
            salen.append({"nombre": str(p["nombre"]), "contorno": p["contorno"]})
    return salen


def firma():
    """Huella de cómo se hacen los pueblos: VERSION y los de la planta."""
    return hashlib.sha1(json.dumps([VERSION, de_la_planta()], sort_keys=True).encode()).hexdigest()[:12]


def dentro(x, y, anillo):
    """¿Qué puntos (x, y) caen dentro del anillo [[x, y], …]? (par-impar, sin librerías)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    ax, ay = np.asarray(anillo, float).T
    salen = np.zeros(len(x), bool)
    for x0, y0, x1, y1 in zip(ax, ay, np.roll(ax, -1), np.roll(ay, -1)):
        if y0 == y1:
            continue
        cruza = (y0 > y) != (y1 > y)
        salen ^= cruza & (x < x0 + (y - y0) * (x1 - x0) / (y1 - y0))
    return salen


def _utm(contorno):
    from teodors.planta import geo
    return [[geo.a_utm(lat, lon) for lon, lat in anillo] for anillo in contorno]


def en_contorno(x, y, contorno_utm):
    """Los puntos dentro de un contorno (anillos en UTM)."""
    salen = np.zeros(len(x), bool)
    for anillo in contorno_utm:
        salen ^= dentro(x, y, anillo)
    return salen


def _centro(contorno_utm):
    """El centroide del anillo más grande (el casco, si el pueblo está en trozos)."""
    mejor, area_max = None, -1.0
    for anillo in contorno_utm:
        ax, ay = np.asarray(anillo, float).T
        cruz = ax * np.roll(ay, -1) - np.roll(ax, -1) * ay
        a = cruz.sum() / 2.0
        if abs(a) > area_max and a != 0:
            area_max = abs(a)
            mejor = (float(((ax + np.roll(ax, -1)) * cruz).sum() / (6 * a)), float(((ay + np.roll(ay, -1)) * cruz).sum() / (6 * a)))
    return mejor


def centros():
    """[{"nombre", "municipio", "x", "y", "lat", "lon", "ha"}] de los pueblos de la planta: el centro de su casco (el anillo más grande), para su
    icono en el mapa, y la superficie de su contorno."""
    from teodors.planta import geo
    municipios = {p.get("nombre"): p.get("municipio") for p in config.bloque("pueblos").get("lista", [])}
    salen = []
    for p in de_la_planta():
        contorno = _utm(p["contorno"])
        c = _centro(contorno)
        if c is None:
            continue
        lat, lon = geo.a_geo(*c)
        ha = sum(abs(float((np.asarray(a, float)[:, 0] * np.roll(np.asarray(a, float)[:, 1], -1)
                            - np.roll(np.asarray(a, float)[:, 0], -1) * np.asarray(a, float)[:, 1]).sum())) / 2.0 for a in contorno) / 1e4
        salen.append({"nombre": p["nombre"], "municipio": municipios.get(p["nombre"]), "x": c[0], "y": c[1], "lat": lat, "lon": lon, "ha": ha})
    return salen


def manchas(U, transform, x, y):
    """La mancha residencial de CORINE en la que cae cada receptor (como `terreno.nucleos`: 8-vecindad), o 0 si en ninguna."""
    from scipy import ndimage
    from teodors.fuentes import terreno as T
    etiq, _ = ndimage.label(np.isin(U, T.FAMILIAS_NUCLEO["residencial"]), structure=np.ones((3, 3), int))
    dx, dy = transform.a, -transform.e
    col = np.floor((np.asarray(x, float) - transform.c) / dx).astype(int)
    fil = np.floor((transform.f - np.asarray(y, float)) / dy).astype(int)
    ok = (fil >= 0) & (fil < U.shape[0]) & (col >= 0) & (col < U.shape[1])
    salen = np.zeros(len(col), int)
    salen[ok] = etiq[fil[ok], col[ok]]
    return salen


def _terreno():
    """(U, transform) del terreno de la planta, o None si no está descargado."""
    from teodors.fuentes import terreno as T
    try:
        emp = config.cargar_emplazamiento()
        info = T.ultimo_caso(emp["lat"], emp["lon"])
        if not info:
            return None
        _, U, tr = T.cargar(info)
        return U, tr
    except (OSError, ValueError, KeyError) as e:
        log.warning(f"Pueblos: sin el terreno de la planta ({e}); cada pueblo de CORINE, con el punto de su núcleo.")
        return None


def etiquetas(etiquetas, x, y, terreno=None):
    """Las etiquetas del índice de los receptores (`respuestas.etiquetas`) con los pueblos al día:
    - en cada núcleo residencial de CORINE, «receptores»: los de su mancha urbana, con el del núcleo (sin el terreno, solo el del núcleo);
    - los pueblos de la planta, cada uno en el receptor más cercano al centro de su casco (su distancia) y con «receptores», los de su
      contorno (si no tiene ninguno dentro, el de su centro, y se avisa).
    Lo de antes («receptores» y los pueblos de la planta) se rehace. `terreno`: (U, transform), o False sin él; por defecto, el de la planta."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    salen = [{k: v for k, v in e.items() if k != "receptores"} for e in etiquetas if e.get("origen") != "planta"]
    ter = _terreno() if terreno is None else terreno
    mancha = manchas(*ter, x, y) if ter else None
    for e in salen:
        if e.get("clase") == "nucleo" and e.get("familia") == "residencial":
            suyos = {int(e["i"])}
            if mancha is not None and mancha[e["i"]]:
                suyos |= set(np.flatnonzero(mancha == mancha[e["i"]]).tolist())
            e["receptores"] = sorted(suyos)
    for p in de_la_planta():
        contorno = _utm(p["contorno"])
        en = en_contorno(x, y, contorno)
        c = _centro(contorno)
        if c is None:
            log.warning(f"Pueblo «{p['nombre']}» de planta.json: su contorno no tiene área; no sale.")
            continue
        i = int(np.argmin(np.hypot(x - c[0], y - c[1])))
        if not en.any():
            log.warning(f"Pueblo «{p['nombre']}» de planta.json: ningún receptor dentro de su contorno; vale el más cercano a su centro.")
        salen.append({"i": i, "nombre": p["nombre"], "clase": "nucleo", "familia": "residencial", "origen": "planta",
                      "receptores": sorted(set(np.flatnonzero(en).tolist()) | {i})})
    return salen
