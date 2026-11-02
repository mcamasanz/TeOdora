# -*- coding: utf-8 -*-
"""Prepara el ejemplo de la ventana de configuración: una hora del viento guardado y del penacho
de un plan ya simulado, la que más receptores tiene por encima de 10 ou_E/m³, para que se vea casi toda la escala de
color. Solo sirve para enseñar las escalas: no es un resultado. Va a la carpeta de `operacion.ejemplo` de planta.json, relativa a la de la planta.

    python -m teodors.operacion.ejemplo_configuracion [--plan base]

⚠️ Heredado: lee `resultados_planes/<plan>/` y `dia_viento`, de antes de las modalidades de simulación, que hoy no se escriben. Ver el README.
"""
import argparse
import json

import numpy as np

from teodors import planta as config
from teodors.operacion import penacho_mapa, simulacion as planes_calculo, viento_mapa
from teodors.planta import geo

ENCUADRE_GRADOS = 0.07                     # ≈ ±8 km: el mapa abre a un nivel más del que encuadra esto


def carpeta_ejemplo():
    """Dónde va el ejemplo: `operacion.ejemplo` de planta.json, relativo a la carpeta de la planta."""
    return config.PLANTA / config.bloque("operacion").get("ejemplo", "recursos/ejemplo")


def principal(plan):
    EJEMPLO = carpeta_ejemplo()
    carpeta = config.DATOS / "resultados_planes" / plan
    res = json.loads((carpeta / "resultado.json").read_text(encoding="utf-8"))
    C = np.load(carpeta / "olor" / "penacho.npz")["C"]
    with np.load(carpeta / "olor" / "resumen.npz") as z:
        x, y = z["x"], z["y"]
    h = int(np.argmax((C > 10).sum(axis=1)))
    emp = config.cargar_emplazamiento()
    EJEMPLO.mkdir(parents=True, exist_ok=True)
    imagenes = planes_calculo._imagenes(C[h], planes_calculo._rejillas(x, y, geo.a_utm(emp["lat"], emp["lon"])),
                                        EJEMPLO / "penacho")
    d = viento_mapa.datos_dia(res["dia_viento"], res["serie"])
    viento = dict(d, u=[d["u"][h]], v=[d["v"][h]], pos=[0], horas=[d["horas"][h]], media=[d["media"][h]],
                  maxima=[d["maxima"][h]])
    (EJEMPLO / "viento.json").write_text(json.dumps(viento), encoding="utf-8")
    g = ENCUADRE_GRADOS
    (EJEMPLO / "ejemplo.json").write_text(json.dumps(
        {"hora": d["horas"][h], "serie": res["serie"], "plan": plan, "limites": [i["limites"] for i in imagenes],
         "vmin": planes_calculo.VMIN, "decadas": penacho_mapa.DECADAS,
         "encuadre": [[emp["lat"] - g, emp["lon"] - g], [emp["lat"] + g, emp["lon"] + g]]}, indent=1), encoding="utf-8")
    print(f"Hora {d['horas'][h]} · máximo {C[h].max():.0f} · "
          + " · ".join(f"{f.name} {f.stat().st_size / 1024:.0f} kB" for f in sorted(EJEMPLO.iterdir())))


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--plan", default="base")
    principal(a.parse_args().plan)


if __name__ == "__main__":
    main()
