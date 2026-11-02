# -*- coding: utf-8 -*-
"""Series de viento 3D de los años del reanálisis con ERA5 + las estaciones de la planta como observaciones (NOOBS = 1, radios de `series` en planta.json), en DATOS:

    DATOS/viento3d/<series.era5>/   cmz/AAAAMM.cmz + AAAAMM/(puntos.csv, caso.json, viento3d.inp, resumen.json)

Un mes por tarea (24 h de arranque, recortadas al comprimir); los casos se calculan en
config.DIR_TRABAJO y se borran. Reanudable: un mes con su .cmz no se repite.

    python -m teodors.operacion.viento3d_series [--anios AAAA …] [--procesos 8]

Planta: la de TEODORS_PLANTA. Las estaciones, `estaciones.codigos` de planta.json; por defecto, los años de `reanalisis.anios`.
"""
import argparse
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from teodors import planta as config
from teodors.casos import viento3d as vc
from teodors.comun import registro


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--motores", nargs="*", default=["teodors"])
    ap.add_argument("--anios", nargs="*", type=int, default=None)
    ap.add_argument("--procesos", type=int, default=8)
    a = ap.parse_args()
    a.anios = list(config.REANALISIS_ANIOS) if a.anios is None else a.anios
    ESTACIONES = list(config.pide("estaciones", "codigos"))
    SERIES = {"teodors": config.pide("series", "era5")}
    config.asegurar_carpetas()
    registro.configurar(config.DIR_LOGS, config.REGISTRO)
    meses = [(y, m) for y in a.anios for m in range(1, 13)]
    # intercaladas: así las dos series avanzan a la vez
    tareas = [(mo, y, m) for (y, m) in meses for mo in a.motores
              if not (vc.dir_serie(SERIES[mo]) / "cmz" / f"{y}{m:02d}.cmz").exists()]
    print(f"{len(tareas)} meses pendientes ({', '.join(a.motores)}) · {a.procesos} a la vez · "
          f"datos en {config.DATOS}", flush=True)
    t0, hechas, fallos = time.time(), 0, []

    def una(t):
        mo, y, m = t
        return t, vc.mes_serie(y, m, mo, SERIES[mo], estaciones=ESTACIONES)

    with ThreadPoolExecutor(a.procesos) as ex:
        fut = {ex.submit(una, t): t for t in tareas}
        for f in as_completed(fut):
            mo, y, m = fut[f]
            try:
                _, r = f.result()
                hechas += 1
                resto = (time.time() - t0) / hechas * (len(tareas) - hechas - len(fallos)) / 60
                print(f"{mo} {y}-{m:02d}: {r.get('minutos', 0):.0f} min · {r.get('cmz_mb', 0):.0f} MB · "
                      f"{hechas}/{len(tareas)} · quedan ~{resto:.0f} min", flush=True)
            except Exception as e:
                fallos.append((mo, y, m))
                print(f"FALLO {mo} {y}-{m:02d}: {type(e).__name__}: {str(e)[:300]}", flush=True)
                traceback.print_exc()
    print(f"terminado en {(time.time() - t0) / 60:.0f} min · {hechas} meses · fallos {fallos}",
          flush=True)


if __name__ == "__main__":
    main()
