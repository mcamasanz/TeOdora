# -*- coding: utf-8 -*-
"""Respuesta de cada foco a una emisión unidad en cada hora del día, con el viento de un día o un periodo. Es lo que necesita `operacion.simulacion`.

Por foco, una corrida de `dispersion.puffs` con 24 especies de cálculo H00…H23, cada una emitida solo en su hora, en la malla de la planta.
Las áreas emiten 1 g/s EN TOTAL: q = 1 / superficie, por m². Con --dias, un periodo de varios días (episodio, predicción). Salida en DATOS/respuestas/<serie>_<AAAAMMDD>/ o,
en esos, DATOS/respuestas/<serie>/:
  R_<foco>.npz     R[h, t, r] en (g/m³) por g/s: h = especie, t = hora del periodo por su FIN (UTC; en un día, su hora), r = receptor
  receptores.npz   x, y, cota, clase de cada receptor
  meta.json        día, serie, huella de cada foco (si cambia, hay que recalcularlo), receptores con nombre
Multiplicada por ou_E/s, la respuesta da ou_E/m³. Se salta los focos ya calculados con la misma huella.

    python -m teodors.operacion.respuestas [--dia AAAA-MM-DD] [--dias 1] [--serie NOMBRE] [--procesos 4]

Planta: la de TEODORS_PLANTA, y sus DATOS, los de `planta.DATOS` (<prefijo>_DATOS; `periodos._lanzar` le pasa los suyos). Sin --serie, `series.gfs` de planta.json; sin --dia,
`series.dia_prueba`.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from teodors import planta as config
from teodors.casos import receptores as receptores_mapa, viento3d as vc
from teodors.comun import procesos, registro
from teodors.fuentes import catastro as edificios, terreno
from teodors.operacion import focos as F
from teodors.planta import geo
from teodors.preparacion.puffs import control_fuentes as cf, salida as lector
from teodors.preparacion.viento3d import salida as salida_viento

VIENTO = "viento3d.dat"
HORAS = ["H%02d" % h for h in range(24)]
# Lo que le falta a un foco para la emisión no impide calcular su respuesta (es a emisión unidad)
SOLO_EMISION = ("emisión de olor", "horas de funcionamiento", "frecuencia y duración")


def fuente(foco, cota):
    """(modelo, [fuentes de control_fuentes]) con 1 g/s en total, emitido en cada hora por su especie. Una fuente, salvo una pila alargada
    (`focos.fuentes_motor`: una fila de volúmenes que se reparten ese 1 g/s)."""
    salen = []
    for m, d, q0 in F.fuentes_motor(foco, cota):
        d["perfil"] = {e: [1.0 if k == h else 0.0 for k in range(24)] for h, e in enumerate(HORAS)}
        d["q"] = {e: q0 for e in HORAS}
        salen.append(d)
    return m, salen


def correr(foco, cota, malla, zona, ini, recs, trabajo, salida, dia, dias):
    t0 = time.time()
    m, ds = fuente(foco, cota)
    nombre = foco["id"]
    nom = {"viento": VIENTO, "listado": nombre + ".lst", "concentraciones": nombre + ".dat"}
    cf.escribir(trabajo / (nombre + ".inp"), malla, config.VIENTO3D_ZFACE, ini, 18 + 24 * dias, zona, HORAS,
                areas=ds if m == "superficie" else [], puntos=ds if m == "punto" else [],
                volumenes=ds if m == "volumen" else [], receptores=recs, nombres=nom)
    env = procesos.entorno()
    with open(trabajo / (nombre + ".log"), "w", errors="replace") as fo:
        rc = subprocess.call(procesos.orden("teodors", "puffs", nombre + ".inp"), cwd=str(trabajo),
                             stdout=fo, stderr=subprocess.STDOUT, env=env)
    dat = trabajo / (nombre + ".dat")
    if rc != 0 or not dat.exists():
        raise RuntimeError(f"{nombre}: teOdors puffs falló (rc={rc}).\n"
                           + (trabajo / (nombre + ".log")).read_text(errors="replace")[-1200:])
    fines = pd.to_datetime(lector.concentraciones(dat, especie=HORAS[0])[0])
    i = np.where((fines >= dia) & (fines < dia + pd.Timedelta(days=dias)))[0]
    if len(i) != 24 * dias:
        raise RuntimeError(f"{nombre}: {len(i)} periodos del periodo, no {24 * dias}")
    R = np.zeros((24, len(i), len(recs)), np.float32)
    for h, e in enumerate(HORAS):
        R[h] = np.asarray(lector.concentraciones(dat, especie=e)[1])[i]
    np.savez_compressed(salida / f"R_{nombre}.npz", R=R)
    dat.unlink(missing_ok=True)
    seg = time.time() - t0
    print(f"  {nombre} ({foco.get('nombre')}, {m}): {seg:.0f} s · máx. {R.max() * 1e6:.3g} µg/m³ por g/s", flush=True)
    return nombre, seg


def etiquetas(recs, nucleos, nombres):
    """Receptores con nombre para la tabla de resultados: los de receptores.json de la planta y los núcleos."""
    indice = {(x, y): i for i, (x, y, _) in enumerate(recs)}
    out = []

    def pon(x, y, nombre, clase, **extra):
        i = indice.get((round(float(x), 1), round(float(y), 1)))
        if i is not None:
            out.append(dict(i=i, nombre=nombre, clase=clase, **extra))
    for r in receptores_mapa.con_nombre():
        pon(r["x"], r["y"], r["nombre"], "nombrado")
    for n in nucleos:
        nom = nombres.get(terreno.clave_nucleo(n)) or {}
        pon(n["x"], n["y"], nom.get("poblacion") or n.get("tipo", "núcleo"), "nucleo", familia=n.get("familia"))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dia", default=None)
    ap.add_argument("--dias", type=int, default=1)
    ap.add_argument("--serie", default=None)
    ap.add_argument("--procesos", type=int, default=4)
    A = ap.parse_args()
    A.serie = A.serie or config.pide("series", "gfs")
    config.asegurar_carpetas()
    registro.configurar(config.DIR_LOGS, config.REGISTRO)
    t0 = time.time()
    dia = pd.Timestamp(A.dia or config.pide("series", "dia_prueba"))
    emp = config.cargar_emplazamiento()
    xp, yp = geo.a_utm(emp["lat"], emp["lon"])
    propia = A.serie.startswith(("queja_", "prediccion_"))             # episodio o predicción: una serie para ese periodo
    salida = config.DATOS / "respuestas" / (A.serie if propia else f"{A.serie}_{dia:%Y%m%d}")
    salida.mkdir(parents=True, exist_ok=True)
    trabajo = config.DIR_TRABAJO / "respuestas" / f"{A.serie}_{dia:%Y%m%d}"
    shutil.rmtree(trabajo, ignore_errors=True)
    trabajo.mkdir(parents=True)
    vc.descomprimir_mes(A.serie, dia.year, dia.month, trabajo / VIENTO)          # del .cmz o del paquete de viento
    info = vc.info_mes(A.serie, dia.year, dia.month)
    malla = {k: info[k] for k in ("nx", "ny", "celda_m", "ext")}
    ini = dia - pd.Timedelta(hours=18)                                 # 06 UTC del día anterior
    empieza = pd.Timestamp(info["ini_corrida"]) + pd.Timedelta(hours=info.get("arranque_h", 0))
    # Reanálisis: cada mes se guarda RECORTADO a sus horas, así que la víspera del día 1 está en el .cmz del mes anterior y hay que anteponerla.
    # Episodio/predicción (`propia`): un ÚNICO .cmz con todo el corrido (el arranque, incluido el del mes anterior, YA está en VIENTO), así que no.
    if ini < empieza and not propia:
        antes = empieza - pd.Timedelta(hours=1)
        vc.descomprimir_mes(A.serie, antes.year, antes.month, trabajo / "anterior.dat")
        n = salida_viento.anteponer(trabajo / "anterior.dat", trabajo / VIENTO, ini, info["nx"], info["ny"])
        (trabajo / "anterior.dat").unlink()
        print(f"Día 1 del mes: {n} h de la víspera, del viento de {antes:%Y-%m}", flush=True)
    t_inf = terreno.ultimo_caso(emp["lat"], emp["lon"])
    Z, U, tr = terreno.cargar(t_inf)

    def cota(x, y):
        f = int((tr.f - y) / -tr.e)
        c = int((x - tr.c) / tr.a)
        return float(max(Z[min(max(f, 0), Z.shape[0] - 1), min(max(c, 0), Z.shape[1] - 1)], 0.0))

    res = terreno.resumen(Z, U, tr, emp["lat"], emp["lon"])
    bld = edificios.cargar(emp["lat"], emp["lon"])[1]
    m = receptores_mapa.malla(res["nucleos"], bld)
    recs = [(x, y, cota(x, y)) for x, y, _ in m]
    print(f"Malla: {receptores_mapa.resumen(m)}", flush=True)
    clases = np.array([c for _, _, c in m])
    meta_ruta = salida / "meta.json"
    antes = json.loads(meta_ruta.read_text(encoding="utf-8")) if meta_ruta.is_file() else {}
    misma_malla = antes.get("receptores") == len(recs)
    np.savez_compressed(salida / "receptores.npz", x=np.array([r[0] for r in recs]),
                        y=np.array([r[1] for r in recs]), cota=np.array([r[2] for r in recs]), clase=clases)
    catalogo = F.cargar()
    focos, listos = [], {}
    for f in catalogo["focos"]:
        falta = [x for x in F.pendientes(f) if not x.startswith(SOLO_EMISION)]
        if falta:
            print(f"  {f['id']}: sin calcular, falta {', '.join(falta)}", flush=True)
        elif misma_malla and antes.get("focos", {}).get(f["id"], {}).get("huella") == F.huella(f) \
                and (salida / f"R_{f['id']}.npz").is_file():
            listos[f["id"]] = antes["focos"][f["id"]]
        else:
            focos.append(f)
    print(f"{len(focos)} focos por calcular y {len(listos)} ya hechos · {A.procesos} procesos", flush=True)
    with ThreadPoolExecutor(A.procesos) as pool:
        hechos = list(pool.map(lambda f: correr(f, cota, malla, info["zona"], ini, recs, trabajo, salida, dia, A.dias), focos))
    seg = dict(hechos)
    por_id = {f["id"]: f for f in focos}
    nombres = terreno.nombres_nucleos(t_inf, res["nucleos"])
    meta = {"formato": 1, "dia": f"{dia:%Y-%m-%d}", "dias": A.dias, "serie": A.serie, "receptores": len(recs),
            "centro": [round(xp, 1), round(yp, 1)], "unidad": "(g/m³) por g/s",
            "focos": {**listos, **{i: {"huella": F.huella(por_id[i]), "segundos": round(s, 1)} for i, s in seg.items()}},
            "etiquetas": etiquetas(recs, res["nucleos"], nombres)}
    meta_ruta.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.rmtree(trabajo, ignore_errors=True)
    print(f"Hecho en {(time.time() - t0) / 60:.1f} min → {salida}", flush=True)


if __name__ == "__main__":
    main()
