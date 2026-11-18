# -*- coding: utf-8 -*-
"""Control de calidad de una estación en los años del reanálisis y rosas de los vientos observadas (total, por año, por estación
del año y de día / de noche), en PNG y CSV.

    python -m teodors.metricas.calidad [--codigo CÓDIGO]        (con la carpeta de la planta en TEODORS_PLANTA)
Por defecto, `estaciones.objetivo` de planta.json; un sensor dudoso se declara en `estaciones.ceros_sospechosos`.
Salida: DATOS/reanalisis/01_estacion_<código>/
"""
import argparse
import json
import sys

import numpy as np
import pandas as pd

from teodors import planta as config
from teodors.fuentes import meteocat as estaciones
from teodors.metricas import viento as validacion
from teodors.planta.geo import elevacion_solar

SECTORES = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O",
            "ONO", "NO", "NNO"]
ESTACIONES_ANIO = validacion.ESTACIONES_ANIO
ATASCO_H = 6            # misma dirección (o velocidad) durante ≥ 6 h seguidas con viento
SALTO_MS = 10.0         # salto de velocidad entre medias semihorarias consecutivas


def control_calidad(df, ceros_desde=None):
    """Marcas por medida semihoraria y resumen. Devuelve (df con columna 'qc', resumen).
    ceros_desde: fecha desde la que un 0 m/s exacto se marca como sospechoso del sensor."""
    d = df.sort_values("time").copy()
    res = {"medidas_30min": int(len(d))}
    dup = d.time.duplicated(keep="first")
    res["duplicadas"] = int(dup.sum())
    d = d[~dup].copy()
    qc = pd.Series("", index=d.index)
    fuera = ((d.ws < 0) | (d.ws > 60) | (d.wd < 0) | (d.wd > 360)
             | (d.t < -30) | (d.t > 50))
    qc[fuera] += "rango;"
    # atascos: la misma dirección exacta ATASCO_H horas seguidas con viento ≥ 1 m/s
    n = 2 * ATASCO_H
    for col, cond in (("wd", d.ws >= 1.0), ("ws", d.ws > 0.0)):
        igual = d[col].eq(d[col].shift())
        grupo = (~igual).cumsum()
        largo = d.groupby(grupo)[col].transform("size")
        qc[(largo >= n) & cond & d[col].notna()] += f"atasco_{col};"
    salto = d.ws.diff().abs() > SALTO_MS
    qc[salto] += "pico;"
    if ceros_desde:
        qc[(d.time >= pd.Timestamp(ceros_desde)) & (d.ws == 0)] += "cero_sensor;"
    d["qc"] = qc
    res.update({k: int(qc.str.contains(k).sum()) for k in
                ("rango", "atasco_wd", "atasco_ws", "pico", "cero_sensor")})
    return d, res


def rosa_tabla(ws, wd):
    tabla, calmas = validacion._rosa_clases(ws, wd)
    lim = validacion.CLASES_VEL
    cols = [f"{lim[k]:g}-{lim[k + 1]:g}" if k + 1 < len(lim) else f">={lim[k]:g}"
            for k in range(len(lim))]
    t = pd.DataFrame(np.array(tabla), index=SECTORES, columns=cols)
    return t, calmas


def figura(rosas, ruta, titulo):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from teodors.comun.escalas import COLORES_VEL
    n = len(rosas)
    cols = min(4, n)
    filas = int(np.ceil(n / cols))
    fig, ejes = plt.subplots(filas, cols, subplot_kw={"projection": "polar"},
                             figsize=(3.6 * cols, 3.7 * filas))
    ejes = np.atleast_1d(ejes).ravel()
    ang = np.radians(np.arange(16) * 22.5)
    tope = max(t.to_numpy().sum(1).max() for t, _, _ in rosas.values()) * 1.08
    for ax, (nombre, (t, calmas, horas)) in zip(ejes, rosas.items()):
        abajo = np.zeros(16)
        for c, col in enumerate(t.columns):
            ax.bar(ang, t[col].to_numpy(), width=np.radians(22.5) * 0.85, bottom=abajo,
                   color=COLORES_VEL[c], edgecolor="white", linewidth=0.4, label=col)
            abajo += t[col].to_numpy()
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_ylim(0, tope)
        ax.set_xticks(np.radians(np.arange(0, 360, 45)))
        ax.set_xticklabels(["N", "NE", "E", "SE", "S", "SO", "O", "NO"], fontsize=7)
        ax.tick_params(axis="y", labelsize=6)
        ax.set_title(f"{nombre}\n{horas} h · calmas {calmas:.1f} %".replace(".", ","),
                     fontsize=8.5)
    for ax in ejes[n:]:
        ax.set_visible(False)
    ejes[0].legend(title="m/s", fontsize=6.5, title_fontsize=7, loc="upper left",
                   bbox_to_anchor=(-0.45, 1.15))
    fig.suptitle(titulo, fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(ruta, dpi=105)
    plt.close(fig)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--codigo", default=None)
    codigo = ap.parse_args().codigo
    if codigo is None:
        codigo = config.pide("estaciones", "objetivo")
    anios = config.REANALISIS_ANIOS
    emp = config.cargar_emplazamiento()
    e = next(s for s in estaciones.cercanas(emp["lat"], emp["lon"]) if s["codigo"] == codigo)
    salida = config.DATOS / "reanalisis" / f"01_estacion_{codigo}"
    salida.mkdir(parents=True, exist_ok=True)
    df = estaciones.cargar(codigo, anios)
    h = df["altura_viento_m"].dropna()
    altura = float(h.iloc[0]) if len(h) else None

    # 1) control de calidad (sobre las medias semihorarias) y horas válidas
    d, res = control_calidad(df, config.bloque("estaciones").get("ceros_sospechosos", {}).get(codigo))
    conv, centro = validacion.convencion(d)
    buena = d[d.qc == ""].copy()
    hor = validacion.a_horario(buena, conv).dropna(subset=["ws", "wd"])
    todas = pd.date_range(f"{anios[0]}-01-01", f"{anios[-1]}-12-31 23:00", freq="h")
    hor = hor[hor.time.isin(todas)]
    cob = hor.groupby(hor.time.dt.year).size() / pd.Series(
        todas.year).value_counts().sort_index() * 100
    res.update({"estacion": codigo, "nombre": e["nombre"], "lat": e["lat"], "lon": e["lon"],
                "altitud_m": e["altitud_m"], "anemometro_m": altura,
                "dist_planta_km": round(e["dist_m"] / 1000, 2), "rumbo_desde_planta": e["rumbo"],
                "convencion_hora": conv, "centroide_radiacion_h": round(centro, 2),
                "horas_validas": int(len(hor)), "horas_periodo": int(len(todas)),
                "cobertura_pct_por_anio": {int(k): round(float(v), 1) for k, v in cob.items()},
                "cobertura_pct": round(100 * len(hor) / len(todas), 1)})
    d.to_csv(salida / "medidas_30min_qc.csv.gz", index=False)
    hor.to_csv(salida / "horario_valido.csv", index=False)

    # 2) rosas observadas
    hor["elev_sol"] = elevacion_solar(hor.time, e["lat"], e["lon"])
    grupos = {f"{anios[0]}-{anios[-1]}": hor}
    grupos |= {str(a): hor[hor.time.dt.year == a] for a in anios}
    grupos |= {n: hor[hor.time.dt.month.isin(m)] for n, m in ESTACIONES_ANIO.items()}
    grupos |= {"día": hor[hor.elev_sol > 0], "noche": hor[hor.elev_sol <= 0]}
    rosas, filas = {}, []
    for nombre, g in grupos.items():
        t, calmas = rosa_tabla(g.ws, g.wd)
        rosas[nombre] = (t, calmas, len(g))
        tt = t.reset_index().rename(columns={"index": "sector"})
        tt.insert(0, "subconjunto", nombre)
        tt["calmas_pct"] = calmas
        tt["horas"] = len(g)
        filas.append(tt)
    pd.concat(filas).round(3).to_csv(salida / "rosas_observadas.csv", index=False)
    base = f"{e['nombre']} ({codigo}) · medido a {altura:g} m · Meteocat"
    figura({k: rosas[k] for k in list(rosas)[:6]}, salida / "rosas_total_y_anios.png",
           f"{base} · total y por año")
    figura({k: rosas[k] for k in list(rosas)[6:]}, salida / "rosas_estaciones_dia_noche.png",
           f"{base} · por estación del año y de día / de noche")
    (salida / "resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    print("\nprocedencia dominante (sectores con más horas):")
    for nombre, (t, calmas, n) in rosas.items():
        s = t.to_numpy().sum(1)
        top = np.argsort(-s)[:3]
        print(f"   {nombre:12s} {n:6d} h · calmas {calmas:4.1f} % · "
              + ", ".join(f"{SECTORES[i]} {s[i]:.0f} %" for i in top))
    print(f"\nsalida: {salida}")


if __name__ == "__main__":
    main()
