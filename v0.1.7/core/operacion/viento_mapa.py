# -*- coding: utf-8 -*-
"""Viento en superficie de una serie de viento 3D (nivel 1 de `meteo.viento3d`) preparado para la capa animada del mapa (partículas, líneas o flechas).

Se lee directamente del .cmz del mes o, sin él, del paquete de viento de la planta (solo «U-LEV  1» y «V-LEV  1»), sin
reconstruir el fichero de viento (`casos.viento3d.campo_mes`). u y v van respecto a la CUADRÍCULA UTM (i = este, j = norte): la capa
del mapa los coloca con la geometría real de la rejilla en pantalla, así que no hace falta girar
por la convergencia de meridianos.

Las series son de la planta (`series` de planta.json): `era5`, `preferidas` y `titulos`.
"""
import base64
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

from teodors import planta as config
from teodors.casos import viento3d as vc
from teodors.comun import registro
from teodors.planta import geo

log = registro.get("viento_mapa")

# Forma, color, escala y cantidad: se eligen en la configuración; las añade la interfaz.


def serie_defecto():
    """La serie de los años del reanálisis (`series.era5`)."""
    return config.pide("series", "era5")


def titulos():
    """{serie: su título en la leyenda} (`series.titulos`)."""
    return config.bloque("series").get("titulos", {})


def preferidas():
    """Las series en orden de preferencia: la app usa la primera que exista (`series.preferidas`)."""
    return tuple(config.bloque("series").get("preferidas", ()))


def serie_disponible():
    """La primera serie de `preferidas` con algún mes calculado (o None)."""
    return next((s for s in preferidas() if meses(s)), None)


def dia_inicial(serie):
    """Día con el que abrir el calendario: el que marque el caso.json del último mes
    («dias_completos», p. ej. en un caso de un solo día) o el 15 del primer mes."""
    m = meses(serie)
    if not m:
        return None
    a, mm = m[-1]
    dias = (vc.info_mes(serie, a, mm) or {}).get("dias_completos")
    if dias:
        return pd.Timestamp(dias[-1])
    return pd.Timestamp(m[0][0], m[0][1], 15)


def rango_dias(serie):
    """Primer y último día con viento (o None): de los meses con .cmz y, si su caso.json lo dice, de «dias_completos»."""
    m = meses(serie)
    if not m:
        return None

    def extremos(anio, mes):
        dias = (vc.info_mes(serie, anio, mes) or {}).get("dias_completos")
        if dias:
            return pd.Timestamp(dias[0]), pd.Timestamp(dias[-1])
        return pd.Timestamp(anio, mes, 1), pd.Timestamp(anio, mes, 1) + pd.offsets.MonthEnd(0)
    return extremos(*m[0])[0], extremos(*m[-1])[1]


VMAX = 8.0                 # m/s: tope de la escala de color
BIBLIOTECA = None          # otra biblioteca en vez de la de la planta, si se pone


def biblioteca():
    """Ruta de la biblioteca del viento local de la planta (`viento_local.biblioteca`, relativa a su carpeta); None si no tiene."""
    if BIBLIOTECA is not None:
        return Path(BIBLIOTECA)
    b = config.bloque("viento_local").get("biblioteca")
    return config.PLANTA / b if b else None


def meses(serie=None):
    """[(año, mes)] con viento: .cmz en DATOS/viento3d/<serie>/cmz o, si no, en el paquete de viento de la planta
    (`casos.viento3d.meses_serie`); por defecto, la serie del reanálisis."""
    serie = serie_defecto() if serie is None else serie
    return vc.meses_serie(serie)


def _fecha(f):
    """AAAAJJJHH (convención de viento3d: hora FINAL) → Timestamp UTC sin zona."""
    f = int(f)
    return (pd.Timestamp(f // 100000, 1, 1) + pd.Timedelta(days=(f // 100) % 1000 - 1)
            + pd.Timedelta(hours=f % 100))


@lru_cache(maxsize=2)
def _mes(serie, anio, mes):
    fz, u = vc.campo_mes(serie, anio, mes, "U-LEV  1")                       # del .cmz o del paquete de viento
    _, v = vc.campo_mes(serie, anio, mes, "V-LEV  1")
    info = vc.info_mes(serie, anio, mes)
    horas = pd.DatetimeIndex([_fecha(x) for x in fz])
    return horas, u, v, info


@lru_cache(maxsize=1)
def _rejilla(nx, ny, x0, y0, dg):
    xs = x0 + (np.arange(nx) + 0.5) * dg
    ys = y0 + (np.arange(ny) + 0.5) * dg
    X, Y = np.meshgrid(xs, ys)                                 # fila j = norte, columna i = este
    lon, lat = Transformer.from_crs(config.EPSG_UTM, "EPSG:4326", always_xy=True).transform(X, Y)
    return lat.ravel(), lon.ravel()


def datos_dia(fecha, serie=None, cada=1, dias=1):
    """Viento del nivel 1 desde el día `fecha`, `dias` días (00 a 23 UTC y, si existe, las 00 del día siguiente
    para interpolar la última hora) en el formato de la capa del mapa. `cada` aclara la malla
    (1 = todas las celdas). Por defecto, la serie del reanálisis. Lleva también el viento en la planta (`planta`: ws y wd)."""
    serie = serie_defecto() if serie is None else serie
    fecha = pd.Timestamp(fecha).normalize()
    horas, u, v, info = _mes(serie, fecha.year, fecha.month)
    sel = np.where((horas >= fecha) & (horas <= fecha + pd.Timedelta(hours=24 * dias)))[0]
    if not len(sel):
        raise ValueError(f"sin datos de {serie} el {fecha:%Y-%m-%d}")
    uu, vv = u[sel][:, ::cada, ::cada], v[sel][:, ::cada, ::cada]
    j, i = _celda_planta(info, u.shape[2], u.shape[1])
    ws_p, wd_p = velocidad_procedencia(u[sel, j, i], v[sel, j, i])
    ny, nx = uu.shape[1:]
    dg = info["celda_m"] * cada
    x0 = info["ext"][0] + (cada - 1) * info["celda_m"] / 2
    y0 = info["ext"][2] + (cada - 1) * info["celda_m"] / 2
    lat, lon = _rejilla(nx, ny, x0, y0, dg)
    vel = np.hypot(uu, vv)
    # la capa solo necesita tres esquinas para colocar la rejilla en pantalla, y el viento va
    # en centésimas de m/s como int16 en base64 (~2 MB por día en vez de ~16 MB en texto)
    esq = {"c00": [lat[0], lon[0]], "c10": [lat[nx - 1], lon[nx - 1]],
           "c01": [lat[(ny - 1) * nx], lon[(ny - 1) * nx]]}
    b64 = lambda a: base64.b64encode(np.round(a.ravel() * 100).astype("<i2").tobytes()).decode()
    return {"nx": int(nx), "ny": int(ny), "dg": float(dg),
            "esquinas": {k: [round(float(a), 6), round(float(b), 6)] for k, (a, b) in esq.items()},
            "u": [b64(a) for a in uu], "v": [b64(a) for a in vv], "escala": 0.01,
            "pos": list(range(len(sel))), "clip": [0, nx - 1, 0, ny - 1], "vmax": VMAX,
            "horas": [f"{h:%Y-%m-%d %H:%M}" for h in horas[sel]],
            "media": [round(float(x), 2) for x in vel.mean(axis=(1, 2))],
            "maxima": [round(float(x), 1) for x in vel.max(axis=(1, 2))],
            # en la celda de la planta, hora a hora: la franja de las horas del día en Meteorología
            "planta": {"ws": [round(float(x), 2) for x in ws_p], "wd": [round(float(x), 1) for x in wd_p]},
            "serie": serie, "titulo": titulos().get(serie, serie), "origen": [float(x0 + dg / 2), float(y0 + dg / 2)]}


@lru_cache(maxsize=1)
def datos_local():
    """La biblioteca del viento local de la planta (`meteo.viento_local.biblioteca`), para el mapa; None si no está."""
    ruta = biblioteca()
    if ruta is None or not ruta.is_file():
        return None
    with np.load(ruta) as z:
        b64 = lambda a: base64.b64encode(a.astype("<i2").tobytes()).decode()
        ny, nx, dx, x0, y0 = int(z["u"].shape[1]), int(z["u"].shape[2]), float(z["dx"]), float(z["x0"]), float(z["y0"])
        a_geo = Transformer.from_crs(config.EPSG_UTM, "EPSG:4326", always_xy=True).transform
        esq = {k: a_geo(x, y)[::-1] for k, (x, y) in {"c00": (x0, y0), "c10": (x0 + (nx - 1) * dx, y0),
                                                      "c01": (x0, y0 + (ny - 1) * dx)}.items()}
        return {"nx": nx, "ny": ny, "dx": dx, "x0": x0, "y0": y0, "esquinas": esq,
                "cx": float(z["cx"]), "cy": float(z["cy"]), "cx2": float(z["cx2"]), "cy2": float(z["cy2"]), "radio": float(z["radio"]),
                "radio_borde": float(z["radio_borde"]), "paso": float(z["paso"]), "escala": float(z["escala"]),
                "solido": int(z["solido"]), "u": [b64(a) for a in z["u"]], "v": [b64(a) for a in z["v"]]}


# ── el viento EN LA PLANTA: el resumen del reanálisis y el calendario del viento de Meteorología (usuario, 2026-11-07) ──────────
CALMA = 0.5                       # m/s, como las rosas de las estaciones (`metricas.viento.CALMA`)
RUMBOS = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO")


def rumbo(wd):
    """Procedencia en grados → uno de los 16 rumbos («N», «NNE»…)."""
    return RUMBOS[int(((float(wd) + 11.25) % 360.0) // 22.5)]


def _celda_planta(info, nx, ny):
    """(j, i) de la celda del viento en la que está la planta (la del borde más cercana si cayera fuera)."""
    emp = config.cargar_emplazamiento()
    x, y = geo.a_utm(emp["lat"], emp["lon"])
    i = int(np.clip((x - info["ext"][0]) // info["celda_m"], 0, nx - 1))
    j = int(np.clip((y - info["ext"][2]) // info["celda_m"], 0, ny - 1))
    return j, i


def velocidad_procedencia(u, v):
    """De u, v respecto a la cuadrícula UTM: velocidad y procedencia en grados desde el norte GEOGRÁFICO (la de las rosas)."""
    emp = config.cargar_emplazamiento()
    giro = geo.dir_geo_a_rejilla(0.0, emp["lat"], emp["lon"])
    u, v = np.asarray(u, float), np.asarray(v, float)
    return np.hypot(u, v), (np.degrees(np.arctan2(-u, -v)) - giro) % 360.0


def planta_mes(serie, anio, mes):
    """El viento del nivel 1 en la celda de la planta, hora a hora, de un mes de la serie: (horas, ws, wd)."""
    fz, u = vc.campo_mes(serie, anio, mes, "U-LEV  1")
    _, v = vc.campo_mes(serie, anio, mes, "V-LEV  1")
    j, i = _celda_planta(vc.info_mes(serie, anio, mes), u.shape[2], u.shape[1])
    ws, wd = velocidad_procedencia(u[:, j, i], v[:, j, i])
    return pd.DatetimeIndex([_fecha(x) for x in fz]), ws, wd


def _firma(f):
    st = f.stat()
    return [f.name, st.st_size, int(st.st_mtime)]


def serie_planta(serie=None, progreso=None):
    """El viento en la planta de todos los meses de la serie, hora a hora: {"AAAAMM": {"horas": ["aaaa-mm-dd HH", …], "ws", "wd"}}.
    En caché en LOCAL, que solo rehace los meses cuyo fichero cambie: la primera vez, cerca de un segundo por mes.
    `progreso(hechos, total)`, si se da, a cada mes leído."""
    serie = serie_defecto() if serie is None else serie
    ruta = config.LOCAL / "viento_planta" / f"{serie}.json"
    try:
        cache = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    lista, salen, nuevos = meses(serie), {}, 0
    for k, (a, m) in enumerate(lista):
        clave, firma = f"{a}{m:02d}", _firma(vc.origen_mes(serie, a, m))
        c = cache.get(clave)
        if c is None or c.get("firma") != firma:
            horas, ws, wd = planta_mes(serie, a, m)
            c = {"firma": firma, "horas": [f"{h:%Y-%m-%d %H}" for h in horas],
                 "ws": [round(float(x), 2) for x in ws], "wd": [round(float(x), 1) for x in wd]}
            nuevos += 1
        salen[clave] = c
        if progreso:
            progreso(k + 1, len(lista))
    if nuevos or set(cache) != set(salen):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(salen, separators=(",", ":")), encoding="utf-8")
        log.info(f"Viento en la planta ({serie}): {nuevos} meses leídos, {len(salen)} en la caché.")
    return {k: {kk: c[kk] for kk in ("horas", "ws", "wd")} for k, c in salen.items()}


def _dominante(ws, wd):
    """Rumbo del que más horas sopla (sin las calmas) y su % de esas horas; (None, 0) si todo es calma."""
    ok = ws >= CALMA
    if not ok.any():
        return None, 0.0
    sec = (((wd[ok] + 11.25) % 360.0) // 22.5).astype(int)
    n = np.bincount(sec, minlength=16)
    return RUMBOS[int(n.argmax())], float(n.max() / ok.sum() * 100)


def resumen_planta(datos):
    """De `serie_planta`: todo el periodo (su rosa, con las clases de velocidad de las de las estaciones, y sus cifras) y cada día
    (de 00 a 23 en la hora de la serie): {"desde", "hasta", "horas", "clases", "rosa", "calmas", "media", "maxima", "dominante",
    "dominante_pct", "dias": {"aaaa-mm-dd": {"media", "maxima", "hora_max", "wd", "rumbo", "calmas", "horas"}}}. None sin datos."""
    from teodors.metricas import viento as mv
    horas = [h for c in datos.values() for h in c["horas"]]
    if not horas:
        return None
    ws = np.array([x for c in datos.values() for x in c["ws"]], float)
    wd = np.array([x for c in datos.values() for x in c["wd"]], float)
    rosa, calmas = mv._rosa_clases(ws, wd)
    dom, pct = _dominante(ws, wd)
    dias = {}
    dia = np.array([h[:10] for h in horas])
    corte = np.flatnonzero(dia[1:] != dia[:-1]) + 1
    for a, b in zip(np.r_[0, corte], np.r_[corte, len(dia)]):
        w, d = ws[a:b], wd[a:b]
        k = int(w.argmax())
        r, _ = _dominante(w, d)
        # dirección del día: la media vectorial de las horas con viento (la de la flecha del calendario)
        ok = w >= CALMA
        ang = (float(np.degrees(np.arctan2(np.sin(np.radians(d[ok])).sum(), np.cos(np.radians(d[ok])).sum())) % 360.0)
               if ok.any() else None)
        dias[str(dia[a])] = {"media": round(float(w.mean()), 2), "maxima": round(float(w[k]), 1), "hora_max": horas[a + k][11:13],
                        "wd": None if ang is None else round(ang, 1), "rumbo": r, "calmas": int((~ok).sum()), "horas": int(b - a)}
    return {"desde": horas[0][:10], "hasta": horas[-1][:10], "horas": len(horas), "clases": list(mv.CLASES_VEL), "rosa": rosa,
            "calmas": calmas, "media": round(float(ws.mean()), 2), "maxima": round(float(ws.max()), 1), "dominante": dom,
            "dominante_pct": round(pct, 1), "dias": dias}
