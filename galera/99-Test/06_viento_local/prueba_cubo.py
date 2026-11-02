# -*- coding: utf-8 -*-
"""Banco de pruebas: un cubo aislado de 10 m frente a lo medido en túnel de viento y a lo publicado.

Referencia (ERCOFTAC UFR 3-14, tabla 1, https://kbwiki.ercoftac.org/w/index.php?title=UFR_3-14_Evaluation):
    medido, Martinuzzi y Tropea (1993), Re = 40 000, en un canal: separación delante 1,04 H; reataque detrás 1,612 H.
    La tabla da además LES 1,65-1,72 H y RANS k-ε 2,2-2,7 H detrás.
⚠️ El canal no es la capa límite atmosférica, y con turbulencia exterior la zona se acorta: es una referencia de orden.
⚠️ La longitud detrás la impone una fórmula del modelo (Fackrell): esta comparación comprueba el código y la fórmula,
no que el modelo prediga la estela.
"""
import json
import time
from pathlib import Path

import sys

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
_planta.actual().DIR_PLANES = _planta.DATOS / "escenarios"      # los planes de las pruebas, con la copia de los datos: nunca en la carpeta de la planta
from teodors.meteo.viento_local import modelo as vl  # noqa: E402

AQUI = Path(__file__).resolve().parent
H = 10.0


def cubo(dx, dz):
    nx, ny, nz = int(120 / dx), int(80 / dx), int(60 / dz)
    x0, y0 = -40.0, -40.0
    dom = vl.Dominio(x0, y0, nx, ny, dx, nz, dz)
    X, Y = np.meshgrid(dom.xc, dom.yc)
    m = (np.abs(X) < H / 2) & (np.abs(Y) < H / 2)
    alt = np.where(m, H, 0.0)
    dom = vl.Dominio(x0, y0, nx, ny, dx, nz, dz, altura=alt)
    pol = np.array([[-H / 2, -H / 2], [H / 2, -H / 2], [H / 2, H / 2], [-H / 2, H / 2]])
    return dom, [{"poligono": pol, "h": H, "mascara": m}]


resultados = {}
for dx, dz in ((1.0, 1.0), (2.5, 1.25), (5.0, 2.5)):
    dom, ed = cubo(dx, dz)
    t0 = time.time()
    r = vl.calcula(dom, 270.0, ed, z_ref=H, z0=0.1)
    dt = time.time() - t0
    j = dom.ny // 2
    k = max(int(0.1 * H / dz), 0)                 # cerca del suelo, como las medidas de reataque
    u = r["u"][k, j]
    x = dom.xc
    # detrás: de negativo a positivo; delante: lo que frena
    tras = np.flatnonzero((x > H / 2) & (u > 0))
    xr = (x[tras[0]] - H / 2) / H if len(tras) else None
    # la velocidad sin edificio, a la misma altura, para ver cuánto frena y acelera
    u0 = vl.calcula(vl.Dominio(dom.x0, dom.y0, dom.nx, dom.ny, dx, dom.nz, dz), 270.0, z_ref=H, z0=0.1)["u"]
    delante = (x < -H / 2)
    i_frente = np.flatnonzero(delante)[-1]
    k_h = int(0.5 * H / dz)
    j_lado = np.argmin(np.abs(dom.yc - (H / 2 + 0.3 * H)))
    i_c = np.argmin(np.abs(x))
    k_t = int(1.2 * H / dz)
    resultados[f"{dx:g} m"] = {
        "celdas": int(dom.nx * dom.ny * dom.nz), "segundos": round(dt, 1), "iteraciones": r["iteraciones"],
        "divergencia_antes": r["div_antes"], "divergencia_despues": r["div_despues"],
        "reataque_detras_H": None if xr is None else round(float(xr), 2),
        "frena_delante_a_0,5H (u/u0)": round(float(r["u"][k_h, j, i_frente] / u0[k_h, j, i_frente]), 2),
        "acelera_al_lado_a_0,5H (u/u0)": round(float(r["u"][k_h, j_lado, i_c] / u0[k_h, j_lado, i_c]), 2),
        "acelera_encima_a_1,2H (u/u0)": round(float(r["u"][k_t, j, i_c] / u0[k_t, j, i_c]), 2),
        **{f"estela_centro_0,5H_x={d}H (u/u0)": round(float(np.interp(H / 2 + d * H, x, r["u"][k_h, j] / u0[k_h, j])), 2)
           for d in (1, 2, 3, 5)}}
    print(dx, json.dumps(resultados[f"{dx:g} m"], ensure_ascii=False), flush=True)
resultados["referencia"] = {"medido_detras_H": 1.612, "medido_delante_H": 1.04, "LES_detras_H": [1.652, 1.722],
                            "RANS_k_epsilon_detras_H": [2.182, 2.731],
                            "formula_modelo_detras_H": round(1.8 / (1.0 * 1.24), 2),
                            "fuente": "ERCOFTAC UFR 3-14, tabla 1 (Martinuzzi y Tropea 1993)"}
(AQUI / "resultados_cubo.json").write_text(json.dumps(resultados, indent=1, ensure_ascii=False), encoding="utf-8")
