# -*- coding: utf-8 -*-
"""Pronóstico 3D de entrada de `meteo.viento3d` (formato 2.1 que lee `entradas.leer_3d`).

  escribir_columna   una columna de un reanálisis (ERA5) repetida en una malla npx×npx que cubre el
                     dominio con margen, situada a la cota del MODELO (no a la del relieve real: las
                     alturas de los niveles de presión son sobre el nivel del mar y el motor las pasa
                     a altura sobre el suelo restando esa cota). Si un nivel queda bajo el suelo del
                     modelo (presión en superficie menor), se sustituye por el viento a 10 m y la T a
                     2 m. Lluvia en cm/h.
  escribir_columnas  una columna PROPIA de un modelo (GFS, ICON-EU…) en cada nodo de una malla
                     regular (`rejilla_puntos`), con la cota del modelo por la ecuación hipsométrica.
Viene del proyecto de La Galera (2026-10-23): mismos ficheros byte a byte que escribía allí.
Necesita pandas (tablas de entrada).
"""
import math
from pathlib import Path

import numpy as np

from odora.comun import geo

RD, G = 287.05, 9.80665


def _q_gkg(t_c, td_c, p_hpa):
    """Humedad específica (g/kg) desde la temperatura y el punto de rocío (°C) y la presión."""
    e = 6.112 * math.exp(17.67 * td_c / (td_c + 243.5))
    return 1000.0 * 0.622 * e / max(p_hpa - 0.378 * e, 1e-6)


def _pmsl(sp_hpa, t2_c, cota_m):
    """Presión reducida al nivel del mar (atmósfera estándar desde la cota del modelo)."""
    t = t2_c + 273.15
    return sp_hpa * (1.0 - 0.0065 * cota_m / (t + 0.0065 * cota_m)) ** -5.257


def _z_superficie(ps, pmsl, t2_c):
    """Cota del terreno del MODELO (m) por la ecuación hipsométrica entre la presión al nivel
    del mar y la de superficie (los archivos en puntos dan la cota del MDT, no la del modelo)."""
    tm = t2_c + 273.15 + 0.0065 * 50.0
    return max(0.0, RD * tm / G * math.log(pmsl / ps))


def escribir_columna(ruta, pfl, sfc, ext, punto, horas, epsg, npx=3, margen=0.5,
                     titulo="ERA5 -> pronostico 3D (odora)",
                     comentario="ERA5 pressure levels, single column at model orography"):
    """Pronóstico 3D con UNA columna (reanálisis) repetida en npx×npx nodos.
      pfl     tabla (time, level hPa, height_asl_m, temp_c, wdir, wspd) de los niveles de presión
      sfc     tabla (time, sp hPa, t2m, d2m °C, tp mm/h, ssrd W/m², wdir, wspd) de superficie
      ext     (xmin, xmax, ymin, ymax) del dominio en m de `epsg`; margen: fracción añadida por lado
      punto   {"lat", "lon", "cota_modelo_m"} de la columna
    Devuelve {"horas", "niveles", "sustituciones_975"}."""
    niveles = sorted(pfl.level.unique(), reverse=True)        # 975 … 700
    nz = len(niveles)
    p = pfl.drop_duplicates(["time", "level"], keep="last").set_index(["time", "level"])
    s = sfc.drop_duplicates("time", keep="last").set_index("time").fillna(0.0)
    cota = float(punto["cota_modelo_m"])
    zona = geo.huso_utm(punto["lon"])

    sx = (ext[1] - ext[0]) * margen
    sy = (ext[3] - ext[2]) * margen
    ep = (ext[0] - sx, ext[1] + sx, ext[2] - sy, ext[3] + sy)
    la1, lo1 = geo.a_geo(ep[0], ep[2], epsg)
    la2, lo2 = geo.a_geo(ep[1], ep[3], epsg)
    lat0, lon0 = punto["lat"], punto["lon"]

    t0 = horas[0]
    L = [f"{'3D.DAT':<16}{'2.1':<16}{titulo:<64}",
         "   1",
         f"{comentario:<132}",
         "  0  0  0  0  0",
         f"UTM   {lat0:9.4f} {lon0:9.4f}   {zona}N",
         "  1  1  1  1  1  1" + "  0" * 14 + "  1",
         f"{t0.year:4d}{t0.month:02d}{t0.day:02d}{t0.hour:02d}{len(horas):5d}"
         f"{npx:4d}{npx:4d}{nz:4d}",
         f"{1:4d}{1:4d}{npx:4d}{npx:4d}{1:4d}{nz:4d}{lo1:10.4f}{lo2:10.4f}{la1:9.4f}{la2:9.4f}"]
    L += [f"{pl / 1013.25:6.3f}" for pl in niveles]
    dxc, dyc = (ep[1] - ep[0]) / npx, (ep[3] - ep[2]) / npx
    for j in range(npx):
        for i in range(npx):
            la, lo = geo.a_geo(ep[0] + (i + 0.5) * dxc, ep[2] + (j + 0.5) * dyc, epsg)
            L.append(f"{i + 1:4d}{j + 1:4d}{la:9.4f}{lo:10.4f}{int(round(cota)):5d}{20:3d}")

    sustituidos = 0
    for ts in horas:
        sr = s.loc[ts]
        sp = float(sr.sp)
        pmsl = _pmsl(sp, float(sr.t2m), cota)
        lluvia = max(float(sr.tp), 0.0) / 10.0                  # mm/h -> cm
        rads = max(float(sr.ssrd), 0.0)
        t2 = float(sr.t2m) + 273.15
        q2 = _q_gkg(float(sr.t2m), float(sr.d2m), sp)
        col = []
        for pl in niveles:
            r = p.loc[(ts, pl)]
            if pl > sp:                                         # nivel bajo el suelo del modelo
                col.append((pl, cota + 10.0, t2, float(sr.wdir), float(sr.wspd)))
                sustituidos += 1
            else:
                col.append((pl, float(r.height_asl_m), float(r.temp_c) + 273.15,
                            float(r.wdir), float(r.wspd)))
        bloque = []
        for j in range(1, npx + 1):
            for i in range(1, npx + 1):
                bloque.append(f"{ts.year:4d}{ts.month:02d}{ts.day:02d}{ts.hour:02d}"
                              f"{i:3d}{j:3d}{pmsl:7.1f}{lluvia:5.2f}{0:2d}"
                              f"{rads:8.1f}{0.0:8.1f}{t2:8.1f}{q2:8.2f}"
                              f"{float(sr.wdir):8.1f}{float(sr.wspd):8.1f}{0.0:8.1f}")
                bloque += [f"{int(pl):4d}{int(round(h)):6d}{tk:6.1f}{int(round(wd)) % 360:4d}"
                           f"{ws:5.1f}" for pl, h, tk, wd, ws in col]
        L += bloque
    Path(ruta).write_bytes(("\r\n".join(L) + "\r\n").encode("ascii"))
    return {"horas": len(horas), "niveles": nz, "sustituciones_975": sustituidos}


def rejilla_puntos(centro_xy, n, paso_m, epsg):
    """[(i, j, lat, lon)] de n×n puntos cada paso_m centrados en centro_xy (x, y en m de `epsg`;
    i, j desde 1) y (xs, ys) de sus columnas y filas."""
    xc, yc = centro_xy
    offs = (np.arange(n) - (n - 1) / 2) * paso_m
    pts = []
    for j in range(n):
        for i in range(n):
            la, lo = geo.a_geo(xc + offs[i], yc + offs[j], epsg)
            pts.append((i + 1, j + 1, la, lo))
    return pts, (xc + offs, yc + offs)


def escribir_columnas(ruta, df, n, xs, ys, horas, niveles, centro_latlon, epsg,
                      titulo="Model columns -> pronostico 3D (odora)",
                      comentario="Pressure levels, one column per cell"):
    """Pronóstico 3D con una columna PROPIA en cada nodo de la malla n×n (xs, ys de
    `rejilla_puntos`). df: filas (time, i, j) con surface_pressure, pressure_msl (hPa),
    temperature_2m, dew_point_2m (°C), precipitation (mm/h), shortwave_radiation (W/m²),
    wind_speed_10m, wind_direction_10m y, por nivel p de `niveles`, geopotential_height_{p}hPa,
    temperature_{p}hPa, wind_speed_{p}hPa y wind_direction_{p}hPa. Los niveles bajo el suelo del
    modelo se sustituyen por el viento a 10 m y la T a 2 m, ESCALONADOS 2 m (con varios niveles
    a la misma altura el espesor de capa sería 0 y el motor dividiría por cero)."""
    lat0, lon0 = centro_latlon
    zona = geo.huso_utm(lon0)
    paso = xs[1] - xs[0]
    la1, lo1 = geo.a_geo(xs[0] - paso / 2, ys[0] - paso / 2, epsg)
    la2, lo2 = geo.a_geo(xs[-1] + paso / 2, ys[-1] + paso / 2, epsg)
    d = df.set_index(["time", "i", "j"]).sort_index()
    primera = d.xs(horas[0], level="time")
    cotas = {(i, j): _z_superficie(r.surface_pressure, r.pressure_msl, r.temperature_2m)
             for (i, j), r in primera.iterrows()}
    nz = len(niveles)
    L = [f"{'3D.DAT':<16}{'2.1':<16}{titulo:<64}",
         "   1", f"{comentario:<132}",
         "  0  0  0  0  0", f"UTM   {lat0:9.4f} {lon0:9.4f}   {zona}N",
         "  1  1  1  1  1  1" + "  0" * 14 + "  1",
         f"{horas[0].year:4d}{horas[0].month:02d}{horas[0].day:02d}{horas[0].hour:02d}"
         f"{len(horas):5d}{n:4d}{n:4d}{nz:4d}",
         f"{1:4d}{1:4d}{n:4d}{n:4d}{1:4d}{nz:4d}{lo1:10.4f}{lo2:10.4f}{la1:9.4f}{la2:9.4f}"]
    L += [f"{p / 1013.25:6.3f}" for p in niveles]
    for j in range(1, n + 1):
        for i in range(1, n + 1):
            la, lo = geo.a_geo(xs[i - 1], ys[j - 1], epsg)
            L.append(f"{i:4d}{j:4d}{la:9.4f}{lo:10.4f}{int(round(cotas[(i, j)])):5d}"
                     f"{55 if cotas[(i, j)] < 1 else 20:3d}")
    sustituidos = 0
    for ts in horas:
        bloque = d.xs(ts, level="time")
        for j in range(1, n + 1):
            for i in range(1, n + 1):
                r = bloque.loc[(i, j)]
                cota = cotas[(i, j)]
                ps = float(r.surface_pressure)
                t2 = float(r.temperature_2m) + 273.15
                L.append(f"{ts.year:4d}{ts.month:02d}{ts.day:02d}{ts.hour:02d}{i:3d}{j:3d}"
                         f"{float(r.pressure_msl):7.1f}{max(float(r.precipitation), 0) / 10:5.2f}"
                         f"{0:2d}{max(float(r.shortwave_radiation), 0):8.1f}{0.0:8.1f}"
                         f"{t2:8.1f}{_q_gkg(r.temperature_2m, r.dew_point_2m, ps):8.2f}"
                         f"{float(r.wind_direction_10m):8.1f}{float(r.wind_speed_10m):8.1f}"
                         f"{0.0:8.1f}")
                bajo = 0
                for p in niveles:
                    z = float(r[f"geopotential_height_{p}hPa"])
                    if p > ps or z < cota + 10:                     # bajo el suelo del modelo
                        z, tk = cota + 10.0 + 2.0 * bajo, t2
                        wd, ws = float(r.wind_direction_10m), float(r.wind_speed_10m)
                        sustituidos += 1
                        bajo += 1
                    else:
                        tk = float(r[f"temperature_{p}hPa"]) + 273.15
                        wd, ws = float(r[f"wind_direction_{p}hPa"]), float(r[f"wind_speed_{p}hPa"])
                    L.append(f"{p:4d}{int(round(z)):6d}{tk:6.1f}{int(round(wd)) % 360:4d}"
                             f"{ws:5.1f}")
    Path(ruta).write_bytes(("\r\n".join(L) + "\r\n").encode("ascii"))
    return {"columnas": n * n, "niveles": nz, "sustituciones": sustituidos,
            "cota_modelo_min": min(cotas.values()), "cota_modelo_max": max(cotas.values())}
