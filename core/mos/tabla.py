# -*- coding: utf-8 -*-
"""Primer paso del MOS: tabla de entrenamiento GFS → estaciones, partición 80/20 por semanas y error de GFS SIN corregir
(la referencia que el MOS tiene que batir). El segundo es `mos.entrenar`.

Una fila por estación, ejecución de las 00 UTC y plazo (0-120 h):
  - predictores: GFS interpolado (bilineal) al punto de la estación: viento a 10 y 100 m, T y
    HR a 2 m, nubosidad, onda corta, presión; derivados (velocidad, cizalla 100-10 m) y el
    calendario de la hora de validez (hora del día y día del año en seno/coseno) y el plazo;
  - objetivo: lo medido en la estación a esa hora (media horaria centrada en la hora, con el
    control de calidad de `metricas.calidad`), a la altura de SU anemómetro.

Partición por SEMANAS de la hora de validez (lunes a domingo): dentro de cada año, una semana de
cada cinco va a validación, con un desfase distinto cada año (semana ISO + año ≡ 0 mod 5). Se
parte por la hora de VALIDEZ y no por la de la ejecución para que entrenamiento y validación no
compartan nunca horas medidas (una ejecución predice 5 días y cruzaría de una semana a otra).

    python -m teodors.mos.tabla        (con la carpeta de la planta en TEODORS_PLANTA)
Las estaciones, `estaciones.codigos` de planta.json; el último dato que cuenta, `pronostico.mos_hasta`.
Salida: DATOS/mos/ (tabla_gfs00.parquet, particion.csv, referencia_gfs.csv, resumen.json)
"""
import argparse
import json
import sys

import numpy as np
import pandas as pd

from teodors import planta as config
from teodors.fuentes import meteocat as estaciones
from teodors.planta.geo import direccion

DIAS = {f"día {d}": (24 * (d - 1) + 1, 24 * d) for d in range(1, 6)}       # plazos 1-24 h, …
VIENTO_MIN = 1.0                    # m/s: el error de dirección solo con viento observado


def gfs(desde="2021-05", hasta=None):
    import xarray as xr
    hasta = config.pide("pronostico", "mos_hasta") if hasta is None else hasta
    fs = sorted((config.DATOS / "meteo" / "gfs").glob("gfs00_*.nc"))
    fs = [f for f in fs if desde.replace("-", "") <= f.stem[-6:] <= hasta[:7].replace("-", "")]
    return xr.open_mfdataset(fs, combine="by_coords").load()


def particion(semanas):
    """semanas: lunes (DatetimeIndex). Validación si semana ISO + año ≡ 0 (mod 5)."""
    iso = semanas.isocalendar()
    val = ((iso.week.astype(int) + iso.year.astype(int)) % 5 == 0).to_numpy()
    return pd.DataFrame({"semana_inicio": semanas.date, "conjunto": np.where(val, "valid", "train")})


def error_dir(a, b):
    return np.abs((a - b + 180.0) % 360.0 - 180.0)


def entradas_gfs(g, lat, lon):
    """Entradas del MOS en un punto para todas las ejecuciones y plazos de g: GFS interpolado
    (bilineal) y derivados (velocidad, dirección, cizalla, hora del día y día del año)."""
    p = g.interp(latitude=lat, longitude=lon)
    inits = pd.DatetimeIndex(g.init_time.values)
    plazos = g.lead_time_h.values
    d = pd.DataFrame({"init_time": np.repeat(inits.values, len(plazos)),
                      "plazo_h": np.tile(plazos, len(inits))})
    d["valid_time"] = d.init_time + pd.to_timedelta(d.plazo_h, unit="h")
    for v in p.data_vars:
        d[v] = p[v].values.reshape(-1)
    d["gfs_ws10"] = np.hypot(d.wind_u_10m, d.wind_v_10m)
    d["gfs_wd10"] = direccion(d.wind_u_10m, d.wind_v_10m)
    d["gfs_ws100"] = np.hypot(d.wind_u_100m, d.wind_v_100m)
    d["cizalla"] = d.gfs_ws100 - d.gfs_ws10
    h = d.valid_time.dt.hour + d.valid_time.dt.minute / 60
    d["hora_sin"], d["hora_cos"] = np.sin(2 * np.pi * h / 24), np.cos(2 * np.pi * h / 24)
    doy = d.valid_time.dt.dayofyear
    d["doy_sin"], d["doy_cos"] = np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)
    return d


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    argparse.ArgumentParser(description=__doc__).parse_args()
    ESTACIONES = tuple(config.pide("estaciones", "codigos"))
    HASTA = config.pide("pronostico", "mos_hasta")
    salida = config.DATOS / "mos"
    salida.mkdir(parents=True, exist_ok=True)
    g = gfs()
    emp = config.cargar_emplazamiento()
    meta = {e["codigo"]: e for e in estaciones.cercanas(emp["lat"], emp["lon"])}
    filas = []
    for c in ESTACIONES:
        e = meta[c]
        d = entradas_gfs(g, e["lat"], e["lon"])
        d.insert(0, "estacion", c)
        obs = pd.read_csv(config.DATOS / "reanalisis" / f"01_estacion_{c}" / "horario_valido.csv",
                          parse_dates=["time"])
        obs = obs.rename(columns={"time": "valid_time", "ws": "obs_ws", "wd": "obs_wd",
                                  "t": "obs_t"})[["valid_time", "obs_ws", "obs_wd", "obs_t"]]
        d = d.merge(obs, on="valid_time", how="inner")
        d["anemometro_m"] = e.get("altura_viento_m") or 10.0
        filas.append(d)
        print(f"{c}: {len(d)} filas con medida", flush=True)
    t = pd.concat(filas, ignore_index=True)
    t = t[t.valid_time <= pd.Timestamp(HASTA)]
    rad = np.radians(t.obs_wd)
    t["obs_u"], t["obs_v"] = -t.obs_ws * np.sin(rad), -t.obs_ws * np.cos(rad)
    # partición por semana de la hora de validez
    lunes = (t.valid_time.dt.normalize()
             - pd.to_timedelta(t.valid_time.dt.weekday, unit="D"))
    semanas = pd.DatetimeIndex(sorted(lunes.unique()))
    part = particion(semanas)
    part.to_csv(salida / "particion.csv", index=False)
    mapa = dict(zip(pd.to_datetime(part.semana_inicio), part.conjunto))
    t["conjunto"] = lunes.map(mapa)
    flot = t.select_dtypes("float64").columns
    t[flot] = t[flot].astype("float32")
    t.to_parquet(salida / "tabla_gfs00.parquet", index=False)

    # referencia: GFS sin corregir, por estación y día de plazo, en validación y en entrenamiento
    ref = []
    for conj in ("valid", "train"):
        for c in ESTACIONES:
            s = t[(t.estacion == c) & (t.conjunto == conj)]
            for nombre, (a, b) in ({"día 0 (análisis)": (0, 0)} | DIAS).items():
                q = s[(s.plazo_h >= a) & (s.plazo_h <= b)]
                con = q.obs_ws >= VIENTO_MIN
                ref.append({"conjunto": conj, "estacion": c, "plazo": nombre, "n": len(q),
                            "error_dir": error_dir(q.gfs_wd10[con], q.obs_wd[con]).mean(),
                            "sesgo_vel": (q.gfs_ws10 - q.obs_ws).mean(),
                            "rmse_vel": np.sqrt(((q.gfs_ws10 - q.obs_ws) ** 2).mean()),
                            "calmas_obs": (q.obs_ws < 0.5).mean() * 100,
                            "calmas_gfs": (q.gfs_ws10 < 0.5).mean() * 100})
    ref = pd.DataFrame(ref)
    ref.round(3).to_csv(salida / "referencia_gfs.csv", index=False)

    val = t[t.conjunto == "valid"]
    est = pd.Series(t.valid_time.dt.month.map(lambda m: {12: "invierno", 1: "invierno", 2: "invierno",
                    3: "primavera", 4: "primavera", 5: "primavera", 6: "verano", 7: "verano",
                    8: "verano"}.get(m, "otoño")))
    res = {"filas": int(len(t)), "filas_validacion": int(len(val)),
           "fraccion_validacion": round(len(val) / len(t), 3),
           "fraccion_validacion_por_estacion_del_anio": {
               k: round(float((t.conjunto[est == k] == "valid").mean()), 3)
               for k in ("invierno", "primavera", "verano", "otoño")},
           "fraccion_validacion_por_anio": {
               int(a): round(float((t.conjunto[t.valid_time.dt.year == a] == "valid").mean()), 3)
               for a in sorted(t.valid_time.dt.year.unique())},
           "semanas": int(len(part)), "semanas_validacion": int((part.conjunto == "valid").sum()),
           "periodo": [str(t.valid_time.min()), str(t.valid_time.max())],
           "ejecuciones": int(t.init_time.nunique()), "estaciones": list(ESTACIONES)}
    (salida / "resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    tab = ref[ref.conjunto == "valid"].pivot(index="estacion", columns="plazo", values="error_dir")
    print("\nGFS sin corregir · error medio de dirección (°) en VALIDACIÓN, viento obs ≥ 1 m/s:")
    print(tab.loc[list(ESTACIONES)].round(1).to_string())
    tab = ref[ref.conjunto == "valid"].pivot(index="estacion", columns="plazo", values="sesgo_vel")
    print("\nGFS sin corregir · sesgo de velocidad (m/s, GFS a 10 m − medida a la altura del anemómetro):")
    print(tab.loc[list(ESTACIONES)].round(2).to_string())
    tab = ref[ref.conjunto == "valid"].pivot(index="estacion", columns="plazo", values="rmse_vel")
    print("\nGFS sin corregir · RMSE de velocidad (m/s):")
    print(tab.loc[list(ESTACIONES)].round(2).to_string())
    print(f"\nsalida: {salida}")


if __name__ == "__main__":
    main()
