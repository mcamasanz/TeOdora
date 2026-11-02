# -*- coding: utf-8 -*-
"""Segundo paso del MOS: corrección de la predicción de GFS en cada estación, entrenada
SOLO con el 80 % (semanas «train» de DATOS/mos/particion.csv) y medida en el 20 % («valid»).

Por estación, tres modelos: componente u, componente v y velocidad (la dirección sale de u y v;
la velocidad se predice aparte porque la media de vectores la encoge). Dos familias:
  - «lineal»: ridge sobre las entradas estandarizadas (MOS clásico);
  - «gb»: gradient boosting (HistGradientBoosting de scikit-learn; admite huecos).
El número de iteraciones del gb se elige con una parte del ENTRENAMIENTO (semanas con
semana ISO + año ≡ 1 mod 5); después se reentrena con todo el entrenamiento. La validación no
se mira hasta el final.

Métricas, con el viento a la altura del anemómetro de cada estación: error y sesgo
de dirección (horas con viento observado ≥ 1 m/s), sesgo y RMSE de velocidad, desajuste de la
rosa (16 sectores, horas ≥ 0,5 m/s: ½·Σ|f_mod − f_obs|) y diferencia de calmas; por día de
plazo, de día y de noche (sol sobre el horizonte en la estación).

    python -m teodors.mos.entrenar        (con la carpeta de la planta en TEODORS_PLANTA, después de `mos.tabla`)
Salida: DATOS/mos/ (modelos/*.joblib, prediccion_valid.parquet, metricas.csv)
"""
import argparse
import sys
import time

import numpy as np
import pandas as pd

from teodors import planta as config
from teodors.fuentes import meteocat as estaciones
from teodors.mos.tabla import DIAS, VIENTO_MIN, error_dir
from teodors.planta.geo import direccion, elevacion_solar

ENTRADAS = ["wind_u_10m", "wind_v_10m", "wind_u_100m", "wind_v_100m", "gfs_ws10", "gfs_ws100",
            "dir_s", "dir_c", "cizalla", "temperature_2m", "relative_humidity_2m",
            "total_cloud_cover_atmosphere", "downward_short_wave_radiation_flux_surface",
            "pressure_reduced_to_mean_sea_level", "hora_sin", "hora_cos", "doy_sin", "doy_cos",
            "plazo_h"]
OBJETIVOS = {"u": "obs_u", "v": "obs_v", "ws": "obs_ws"}
GB = dict(learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=40, l2_regularization=1.0,
          max_iter=800, early_stopping=False, random_state=0)
CALMA = 0.5


def preparar(t):
    t = t.copy()
    ws = np.maximum(t.gfs_ws10, 1e-3)
    t["dir_s"], t["dir_c"] = -t.wind_u_10m / ws, -t.wind_v_10m / ws        # de dónde viene
    return t


def interna(semana):
    iso = pd.DatetimeIndex(semana).isocalendar()
    return ((iso.week.astype(int) + iso.year.astype(int)) % 5 == 1).to_numpy()


def entrenar_gb(X, y, es_int):
    """Iteraciones con la parte interna del entrenamiento; reentreno con todo."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    m = HistGradientBoostingRegressor(**GB).fit(X[~es_int], y[~es_int])
    err = [np.mean((p - y[es_int]) ** 2) for p in m.staged_predict(X[es_int])]
    n = int(np.argmin(err)) + 1
    return HistGradientBoostingRegressor(**(GB | {"max_iter": n})).fit(X, y), n


def rosa(ws, wd):
    ok = ws >= CALMA
    idx = (((wd[ok] + 11.25) % 360) // 22.5).astype(int)
    f = np.bincount(idx, minlength=16) / max(ok.sum(), 1)
    return f, (~ok).mean() * 100


def metricas(d, ws_m, wd_m):
    con = d.obs_ws >= VIENTO_MIN
    dd = ((wd_m[con] - d.obs_wd[con] + 180.0) % 360.0) - 180.0
    fo, co = rosa(d.obs_ws.to_numpy(), d.obs_wd.to_numpy())
    fm, cm = rosa(np.asarray(ws_m), np.asarray(wd_m))
    return {"n": len(d), "error_dir": float(np.abs(dd).mean()), "sesgo_dir": float(dd.mean()),
            "sesgo_vel": float((ws_m - d.obs_ws).mean()),
            "rmse_vel": float(np.sqrt(((ws_m - d.obs_ws) ** 2).mean())),
            "rosa": float(0.5 * np.abs(fm - fo).sum() * 100), "calmas_dif": float(cm - co)}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    argparse.ArgumentParser(description=__doc__).parse_args()
    import joblib
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    ESTACIONES = tuple(config.pide("estaciones", "codigos"))
    base = config.DATOS / "mos"
    (base / "modelos").mkdir(exist_ok=True)
    t = preparar(pd.read_parquet(base / "tabla_gfs00.parquet"))
    lunes = t.valid_time.dt.normalize() - pd.to_timedelta(t.valid_time.dt.weekday, unit="D")
    t["interna"] = interna(lunes) & (t.conjunto == "train").to_numpy()
    emp = config.cargar_emplazamiento()
    meta = {e["codigo"]: e for e in estaciones.cercanas(emp["lat"], emp["lon"])}
    preds = []
    for c in ESTACIONES:
        t0 = time.time()
        s = t[t.estacion == c]
        tr, va = s[s.conjunto == "train"], s[s.conjunto == "valid"].copy()
        X, Xv = tr[ENTRADAS].to_numpy(np.float32), va[ENTRADAS].to_numpy(np.float32)
        es_int = tr.interna.to_numpy()
        nits = {}
        for k, col in OBJETIVOS.items():
            y = tr[col].to_numpy()
            lin = make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(np.nan_to_num(X), y)
            gb, nits[k] = entrenar_gb(X, y, es_int)
            va[f"lin_{k}"] = lin.predict(np.nan_to_num(Xv))
            va[f"gb_{k}"] = gb.predict(Xv)
            joblib.dump({"lineal": lin, "gb": gb, "entradas": ENTRADAS},
                        base / "modelos" / f"{c}_{k}.joblib", compress=3)
        for fam in ("lin", "gb"):
            va[f"{fam}_ws"] = np.maximum(va[f"{fam}_ws"], 0.0)
            va[f"{fam}_wd"] = direccion(va[f"{fam}_u"], va[f"{fam}_v"])
        e = meta[c]
        va["elev_sol"] = elevacion_solar(va.valid_time, e["lat"], e["lon"])
        preds.append(va)
        print(f"{c}: {len(tr)} filas de entrenamiento, {len(va)} de validación · iteraciones gb "
              f"{nits} · {time.time() - t0:.0f} s", flush=True)
    v = pd.concat(preds, ignore_index=True)
    v.to_parquet(base / "prediccion_valid.parquet", index=False)

    filas = []
    modelos = {"GFS": ("gfs_ws10", "gfs_wd10"), "MOS lineal": ("lin_ws", "lin_wd"),
               "MOS gb": ("gb_ws", "gb_wd")}
    franjas = {"todo": slice(None), "día": v.elev_sol > 0, "noche": v.elev_sol <= 0}
    for c in ESTACIONES + ("media",):
        sc = v if c == "media" else v[v.estacion == c]
        for plazo, (a, b) in DIAS.items():
            sp = sc[(sc.plazo_h >= a) & (sc.plazo_h <= b)]
            for fr, m in franjas.items():
                d = sp if fr == "todo" else sp[m.loc[sp.index]]
                for nombre, (cws, cwd) in modelos.items():
                    if c == "media":           # media de las estaciones (no de todas las filas)
                        r = pd.DataFrame([metricas(d[d.estacion == x], d[d.estacion == x][cws],
                                                   d[d.estacion == x][cwd]) for x in ESTACIONES])
                        r = r.mean().to_dict()
                    else:
                        r = metricas(d, d[cws], d[cwd])
                    filas.append({"estacion": c, "plazo": plazo, "franja": fr, "modelo": nombre} | r)
    m = pd.DataFrame(filas)
    m.round(3).to_csv(base / "metricas.csv", index=False)

    med = m[(m.estacion == "media") & (m.franja == "todo")]
    for col, txt in (("error_dir", "error de dirección (°)"), ("sesgo_vel", "sesgo de velocidad (m/s)"),
                     ("rmse_vel", "RMSE de velocidad (m/s)"), ("rosa", "desajuste de la rosa (%)"),
                     ("calmas_dif", "calmas modelo − medidas (puntos)")):
        print(f"\nVALIDACIÓN · media de las {len(ESTACIONES)} estaciones · {txt}:")
        print(med.pivot(index="modelo", columns="plazo", values=col)
              .loc[list(modelos)].round(2).to_string())
    for fr in ("día", "noche"):
        q = m[(m.estacion == "media") & (m.franja == fr)]
        print(f"\nVALIDACIÓN · {fr} · error de dirección (°):")
        print(q.pivot(index="modelo", columns="plazo", values="error_dir").loc[list(modelos)]
              .round(1).to_string())
    q = m[(m.estacion != "media") & (m.franja == "todo") & (m.plazo == "día 1")]
    print("\nVALIDACIÓN · día 1 · por estación · error de dirección (°) / RMSE de velocidad (m/s):")
    print(q.pivot(index="estacion", columns="modelo", values="error_dir")[list(modelos)]
          .loc[list(ESTACIONES)].round(1).join(
          q.pivot(index="estacion", columns="modelo", values="rmse_vel")[list(modelos)]
          .loc[list(ESTACIONES)].round(2), rsuffix=" RMSE").to_string())
    print(f"\nsalida: {base}")


if __name__ == "__main__":
    main()
