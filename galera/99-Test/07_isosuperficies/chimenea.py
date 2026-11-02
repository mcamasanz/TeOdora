# -*- coding: utf-8 -*-
"""¿Se ve en 3D la altura del penacho de una chimenea? (pregunta del usuario, 2026-11-01)

Una sola chimenea INVENTADA en la planta, de 12 m y 1 m de diámetro, con la misma emisión (100 000 ou_E/s, constante) y tres
salidas: sin impulso, con 30 m/s en frío y con 30 m/s a 200 °C. El modelo es lineal: con otra emisión, C escala igual.

    python chimenea.py [--procesos 2] → %TEMP%/ence_galera/99-Test/07_isosuperficies/chim_<caso>.npz y resultados_chimenea.json

Compara la altura del máximo a sotavento con la fórmula de Briggs, a mano, con el viento de la serie en la chimenea.
"""
import argparse
import json
import sys

import comun as K
import numpy as np
import pandas as pd

from teodors.meteo.viento3d import almacen

sys.stdout.reconfigure(encoding="utf-8")
a = argparse.ArgumentParser()
a.add_argument("--procesos", type=int, default=2)
A = a.parse_args()

Q = 100000.0                      # ou_E/s
H_CHIMENEA, DIAMETRO = 12.0, 1.0
CASOS = {"sin_impulso": (1.0, 20.0), "frio_30": (30.0, 20.0), "caliente_30": (30.0, 200.0)}   # m/s, °C
ALTURAS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 100, 120, 140, 160, 180, 200, 250, 300, 400, 500, 600, 800]
SEMILADO, PASO = 3000.0, 50.0
INI, FIN = pd.Timestamp("2026-10-20 06:00"), pd.Timestamp("2026-10-21 23:00")
NIVEL = 1.0                       # ou_E/m³
G = 9.80665

xs, ys = K.rejilla_100m(SEMILADO, PASO)
recs = [(x, y, K.cota(x, y), float(h)) for h in ALTURAS for y in ys for x in xs]
nhoras = int((FIN - INI) / pd.Timedelta(hours=1)) + 1
cota_chim = K.cota(*K.CENTRO)
print(f"{len(recs)} receptores · {nhoras} periodos · {A.procesos} procesos", flush=True)

# Viento en la chimenea, del almacén: nivel 1 (0-20 m), hora a hora, en la celda de la planta
fz, u1 = almacen.leer_campo(K.CMZ, "U-LEV  1")
_, v1 = almacen.leer_campo(K.CMZ, "V-LEV  1")
fz = np.asarray(fz, dtype=int)
i = int((K.CENTRO[0] - K.MALLA["ext"][0]) / K.MALLA["celda_m"])
j = int((K.CENTRO[1] - K.MALLA["ext"][2]) / K.MALLA["celda_m"])
fechas = pd.DatetimeIndex([pd.Timestamp(f // 100000, 1, 1) + pd.Timedelta(days=(f // 100) % 1000 - 1, hours=f % 100) for f in fz])
UV = {t: (float(u1[k, j, i]), float(v1[k, j, i])) for k, t in enumerate(fechas)}


def briggs(w, t_c, u, t_aire=291.0):
    """Sobreelevación final en atmósfera NEUTRA, a mano: la mayor de flotación y cantidad de movimiento (Briggs)."""
    ts = t_c + 273.15
    mom = 3.0 * DIAMETRO * w / u
    if ts <= t_aire:
        return mom, 0.0
    fb = G * w * (DIAMETRO / 2) ** 2 * (ts - t_aire) / ts
    flo = (21.425 * fb ** 0.75 if fb < 55 else 38.71 * fb ** 0.6) / u
    return max(mom, flo), fb


filas, resumen = {}, {}
for nombre, (w, t_c) in CASOS.items():
    salen = {"superficie": [], "volumen": [], "punto": [{"id": "CHIM", "h": H_CHIMENEA, "perfil": None, "x": K.CENTRO[0], "y": K.CENTRO[1], "cota": cota_chim,
                                                          "d": DIAMETRO, "t": t_c + 273.15, "w": w, "q": {K.ESPECIE: Q}}]}
    carpeta = K.TRABAJO / ("chim_" + nombre)
    K.limpia(carpeta)
    fines, C, med = K.correr(carpeta, INI, nhoras, salen, recs, procesos=A.procesos, nombre="c")
    K.shutil.rmtree(carpeta, ignore_errors=True)
    C = C.reshape(len(fines), len(ALTURAS), len(ys), len(xs))
    sel = np.array([f >= pd.Timestamp("2026-10-21 00:00") for f in fines])
    print(f"{nombre}: motor {med['segundos']:.0f} s", flush=True)
    np.savez_compressed(K.TRABAJO / f"chim_{nombre}.npz", C=C[sel], x=xs, y=ys, alturas=np.array(ALTURAS, float),
                        fines=np.array([f.strftime("%Y-%m-%d %H:%M") for f in fines[sel]]).astype("U16"))
    Z = np.array(ALTURAS, float)
    X, Y = np.meshgrid(xs, ys)
    D = np.hypot(X - K.CENTRO[0], Y - K.CENTRO[1])
    filas[nombre] = []
    for f, c in zip(fines[sel], C[sel]):
        u, v = UV[f]
        vel = max(np.hypot(u, v), 1.0)
        # Altura del máximo a 1,5-2,5 km, donde la sobreelevación ya es la final: en la columna con más carga
        banda = (D > 1500) & (D < 2500)
        col = (c * np.gradient(Z)[:, None, None]).sum(axis=0)
        fila = {"fin_utc": f.hour, "viento_m_s": round(float(np.hypot(u, v)), 2), "maximo_aire": round(float(c.max()), 2),
                "maximo_suelo": round(float(c[0].max()), 2)}
        if col[banda].max() > 0:
            jj, ii = np.unravel_index(np.argmax(np.where(banda, col, -1.0)), col.shape)
            perfil = c[:, jj, ii]
            fila["altura_max_a_2km_m"] = float(Z[np.argmax(perfil)])
            fila["suelo_entre_max_a_2km"] = round(float(perfil[0] / perfil.max()), 3)
        dh, fb = briggs(w, t_c, vel)
        fila["briggs_altura_m"] = round(H_CHIMENEA + dh, 1)
        arriba = c >= NIVEL
        if arriba.any():
            por_z = arriba.any(axis=(1, 2))
            fila.update(base_m=float(Z[por_z].min()), techo_m=float(Z[por_z].max()),
                        toca_suelo=bool(arriba[0].any()), alcance_m=round(float(D[arriba.any(axis=0)].max())),
                        suelo_km2=round(float(arriba[0].sum() * PASO * PASO / 1e6), 3))
        filas[nombre].append(fila)
    mx = np.array([x["maximo_suelo"] for x in filas[nombre]])
    resumen[nombre] = {"w_m_s": w, "T_C": t_c, "segundos_motor": med["segundos"], "maximo_suelo_del_dia": float(mx.max()),
                       "horas_con_superficie": sum("base_m" in x for x in filas[nombre]),
                       "horas_despegada_del_suelo": sum("base_m" in x and not x["toca_suelo"] for x in filas[nombre]),
                       "maximo_aire_del_dia": max(x["maximo_aire"] for x in filas[nombre])}
    print(resumen[nombre], flush=True)
    for x in filas[nombre][::4]:
        print("  ", x, flush=True)

(K.AQUI / "resultados_chimenea.json").write_text(json.dumps({"Q_ouE_s": Q, "resumen": resumen, "horas": filas}, ensure_ascii=False, indent=1), encoding="utf-8")
print("hecho", flush=True)
