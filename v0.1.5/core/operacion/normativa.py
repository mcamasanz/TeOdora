# -*- coding: utf-8 -*-
"""Qué se enseña de cada magnitud y con qué límite se compara. Los valores están en un fichero que se puede cambiar sin tocar el código: el
normativa.json de la planta y, si no lo tiene, la plantilla nacional de aquí al lado (normativa_nacional.json, RD 102/2011). ⚠️ PRELIMINAR: se cambiará cuando se
conozcan los gases y las emisiones de cada planta.

Las columnas dependen de cuánto dura el periodo simulado:
  «anios» (el reanálisis)   media, máximo y, según su criterio, cada estadístico del límite o el percentil. La norma cuenta por
                            año civil: se da el del PEOR año (la 19.ª hora más alta de un año es lo que se compara con un límite
                            que admite 18 superaciones).
  «dias» (día, episodio, predicción)   media, máximo y hora del máximo; lo anual no se puede evaluar: del límite horario, las
                            horas por encima, y del diario y el de 8 h, su valor más alto. Sin percentil: el P98 de 24-72 valores
                            es casi la hora más alta.

⚠️ Es lo que aporta la planta, sin el fondo de la zona: no sirve para declarar que se cumple.
"""
import json
from pathlib import Path

import numpy as np

from teodors import planta as config

PLANTILLA = Path(__file__).resolve().parent / "normativa_nacional.json"
RUTA = None                    # otro fichero en vez de esos dos, si se pone (para probar otra normativa)


def ruta():
    """El fichero que manda: el normativa.json de la planta y, si no lo tiene, la plantilla nacional."""
    if RUTA is not None:
        return Path(RUTA)
    return config.NORMATIVA_JSON if config.NORMATIVA_JSON.is_file() else PLANTILLA


def datos():
    return json.loads(ruta().read_text(encoding="utf-8"))


def criterios(clave):
    """Límites de un gas, en el orden del fichero; [] si no tiene (también el olor)."""
    return [] if clave == "olor" else datos()["gases"].get(clave, [])


def _num(v):
    return f"{v:g}".replace(".", ",")


def _ordinal(k):
    return f"{k}.ª"


def _columna(clave, titulo, nombre, tipo="conc", limite=None, capa=None, **extra):
    return dict(clave=clave, titulo=titulo, nombre=nombre, tipo=tipo, limite=limite, capa=capa, **extra)


def columnas(clave, largo):
    """Las columnas de la tabla de una magnitud, sin el nombre del lugar. `capa`: la que también se ve en el mapa (la tercera, «norma»)."""
    salen = [_columna("media", "Media", "Media", capa="media"), _columna("maximo", "Máx.", "Máximo", capa="maximo")]
    cr = criterios(clave)
    d = datos()
    if largo == "dias":
        salen.append(_columna("hora_max", "Hora máx.", "Hora oficial del máximo", tipo="hora"))
    elif not cr:
        p = (d["olor"] if clave == "olor" else d["sin_limite"])["percentil"]
        salen.append(_columna("p98" if p == 98 else f"p{_num(p)}", "P" + _num(p), "Percentil " + _num(p), capa="norma", percentil=float(p)))
    con_capa = any(c["capa"] == "norma" for c in salen)
    for c in cr:
        v, N = float(c["valor"]), int(c.get("superaciones_anio", 0))
        p = c["promedio"]
        if largo == "dias":
            if p == "hora":
                salen.append(_columna("horas_sobre", f"H > {_num(v)}", f"Horas por encima de {_num(v)}", tipo="horas", limite=v))
                continue
            if p == "anio":
                continue
            N = 0
        titulo = {"hora": "1 h", "dia": "24 h", "8h": "8 h", "anio": "Año"}[p]
        nombre = {"hora": f"{_ordinal(N + 1)} hora más alta" + (" del peor año" if largo == "anios" else ""),
                  "dia": (f"{_ordinal(N + 1)} media diaria más alta del peor año" if largo == "anios" else "Media diaria más alta"),
                  "8h": "Máxima media móvil de 8 h", "anio": "Media del peor año"}[p] + f" (límite {_num(v)})"
        salen.append(_columna(f"norma_{p}", titulo, nombre, limite=v, capa=None if con_capa else "norma", promedio=p, n=N))
        con_capa = True
    return salen


def _kesimo(a, k):
    """k-ésimo valor más alto por columna; 0 si no hay tantos."""
    return np.partition(a, -k, axis=0)[-k] if a.shape[0] >= k else np.zeros(a.shape[1], a.dtype)


def _por_anio(a, anios):
    """Trozos de a (t, r) de cada año civil."""
    for y in np.unique(anios):
        yield a[anios == y]


def _medias_diarias(a, dias_t):
    """Media de cada día (filas de a seguidas en el tiempo) y su año."""
    inicio = np.flatnonzero(np.r_[True, dias_t[1:] != dias_t[:-1]])
    largos = np.diff(np.r_[inicio, len(dias_t)])
    return np.add.reduceat(a, inicio, axis=0, dtype=np.float64) / largos[:, None], inicio


def _peor_anio(a, anios, k):
    return np.max([_kesimo(t, k) for t in _por_anio(a, anios)], axis=0)


def estadistico(col, C, fines):
    """El valor de una columna en cada receptor, de C (t, r) en horas seguidas o no, con `fines` el fin de cada hora (UTC).
    El «día» es el día UTC: la diferencia con el civil no cambia la comparación mientras esto sea preliminar."""
    clave = col["clave"]
    if clave == "media":
        return C.mean(0, dtype=np.float64)                 # en float32 pierde 2·10⁻⁴ (medido)
    if clave == "maximo":
        return C.max(0).astype(np.float64)
    if clave == "hora_max":
        return np.where(C.max(0) > 0, np.argmax(C, axis=0), -1).astype(np.float64)
    if clave == "horas_sobre":
        return (C > col["limite"]).sum(0).astype(np.float64)
    salen = np.zeros(C.shape[1])
    a = np.flatnonzero(C.any(axis=0))                      # solo donde llega algo: mucho más rápido
    if not len(a):
        return salen
    B = C[:, a]
    if "percentil" in col:
        salen[a] = np.percentile(B.T, col["percentil"], axis=1)   # por columnas: 4 veces más rápido (medido)
        return salen
    anios = np.asarray(fines.year)
    p, k = col["promedio"], col.get("n", 0) + 1
    if p == "hora":
        salen[a] = _peor_anio(B, anios, k)
    elif p == "dia":
        d, ini = _medias_diarias(B, np.asarray(fines.normalize().asi8))
        salen[a] = _peor_anio(d, anios[ini], k)
    elif p == "8h":
        if len(B) >= 8:
            acu = np.cumsum(B, axis=0, dtype=np.float64)
            m = (acu[7:] - np.r_[np.zeros((1, B.shape[1])), acu[:-8]]) / 8.0
            salen[a] = m.max(axis=0)
    elif p == "anio":
        salen[a] = np.max([t.mean(0, dtype=np.float64) for t in _por_anio(B, anios)], axis=0)
    else:
        raise ValueError(f"promedio desconocido en normativa.json: {p}")
    return salen
