# -*- coding: utf-8 -*-
"""Lo común de la prueba de isosuperficies: datos, focos del plan Base, control con receptores EN ALTURA y
lanzamiento del motor repartido por receptores.

Los focos y las fuentes salen de copias fijas del commit f1cfddb (focos_f1cfddb.*, control_f1cfddb.py): el
formato de los focos de la app va a cambiar y esta prueba tiene que seguir dando lo mismo. Son focos de EJEMPLO.

Los receptores de teOdors admiten altura sobre el suelo, pero `teodors.preparacion.puffs.control` la fija a 0: aquí se
reescriben esas líneas del control, sin tocar teOdors.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
LOCAL = Path(os.environ["TEMP"]) / "ence_galera"
os.environ.setdefault("ENCE_GALERA_DATOS", str(LOCAL / "datos_local"))
TRABAJO = LOCAL / "99-Test" / "07_isosuperficies"
REFERENCIA = TRABAJO / "referencia"
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR), str(AQUI)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
_planta.actual().DIR_PLANES = _planta.DATOS / "escenarios"      # los planes de las pruebas, con la copia de los datos: nunca en la carpeta de la planta

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import psutil  # noqa: E402
import rasterio  # noqa: E402

import control_f1cfddb as cf  # noqa: E402
import focos_f1cfddb as F  # noqa: E402
from teodors import planta as config  # noqa: E402
from teodors.meteo.viento3d import almacen  # noqa: E402
from teodors.preparacion.puffs import salida as lector  # noqa: E402

SERIE, DIA = "odora_gfs_8est", pd.Timestamp("2026-10-21")
DIR_SERIE = config.DIR_VIENTO3D / SERIE
CMZ = DIR_SERIE / "cmz" / "202610.cmz"
INFO = json.loads((DIR_SERIE / "202610" / "caso.json").read_text(encoding="utf-8"))
MALLA = {k: INFO[k] for k in ("nx", "ny", "celda_m", "ext")}
VIENTO = "viento3d.dat"
ESPECIE = "OLOR"
HORA_OFICIAL_UTC = 2                     # 21-oct-2026: hora oficial = UTC + 2
# El centro de las mallas es el de la app: los nudos de 100 m coinciden con receptores de sus respuestas
CENTRO = (286763.2, 4507473.5)


def terreno():
    """Cota (m) y transformación de elevacion.tif."""
    ruta = next((config.DATOS / "terreno").glob("*_50km_25m")) / "elevacion.tif"
    with rasterio.open(ruta) as s:
        return s.read(1), s.transform


_Z, _TR = terreno()


def cota(x, y):
    """Cota en un punto: la misma cuenta que gui/tareas/respuestas_dia.py."""
    f = int((_TR.f - y) / -_TR.e)
    c = int((x - _TR.c) / _TR.a)
    return float(max(_Z[min(max(f, 0), _Z.shape[0] - 1), min(max(c, 0), _Z.shape[1] - 1)], 0.0))


def focos():
    return json.loads((AQUI / "focos_f1cfddb.json").read_text(encoding="utf-8"))["focos"]


def perfil_utc(foco):
    """24 factores por hora UTC de INICIO: el del plan Base (el de la ficha, en hora oficial)."""
    p = F.perfil(foco)
    return [float(p[(h + HORA_OFICIAL_UTC) % 24]) for h in range(24)]


def fuente(foco, emision, perfil, especie=ESPECIE):
    """(modelo, fuente) de control_f1cfddb. `emision` es el total por segundo; en las áreas va POR m² (regla 1)."""
    u, m = foco["ubicacion"], foco["modelo"]
    d = {"id": foco["id"], "h": float(foco["altura_m"]), "perfil": {especie: perfil} if perfil else None}
    if m == "superficie":
        v = [tuple(p) for p in u["poligono"]]
        q = emision / F.area_m2(foco)
        d.update(verts=v, cota=cota(*np.mean(v, axis=0)))
    else:
        q = emision
        d.update(x=u["x"], y=u["y"], cota=cota(u["x"], u["y"]))
        if m == "punto":
            s = foco["salida"]
            d.update(d=s["diametro_m"], t=s["temperatura_C"] + 273.15,
                     w=s.get("velocidad_m_s") or F.caudal_m3_s(foco) / F.area_m2(foco))
        else:
            z = foco["dimensiones"]
            d.update(sy0=np.sqrt(z["largo_m"] * z["ancho_m"]) / 4.3, sz0=z["alto_m"] / 2.15)
    d["q"] = {especie: q}
    return m, d


def fuentes_plan_base():
    """Las fuentes del plan Base en ou_E/s (el motor las trata como g/s: el modelo es lineal) y las que quedan fuera."""
    salen = {"superficie": [], "punto": [], "volumen": []}
    fuera, total = [], 0.0
    for f in focos():
        q, duty = F.olor_ouE_s(f), F.fraccion_eventos(f)
        if q is None or duty is None:
            fuera.append(f["id"] + " " + f["nombre"])
            continue
        m, d = fuente(f, q * duty, perfil_utc(f))
        salen[m].append(d)
        total += q * duty
    return salen, fuera, total


def preparar_viento(carpeta):
    v = carpeta / VIENTO
    if not v.is_file():
        carpeta.mkdir(parents=True, exist_ok=True)
        almacen.descomprimir(CMZ, v)
    return v


def _control(ruta, ini, nhoras, salen, receptores, dat, lst):
    """Control con receptores (x, y, cota, altura). `receptores` en m."""
    c = cf.preparar(MALLA, config.VIENTO3D_ZFACE, ini, nhoras, INFO["zona"], [ESPECIE],
                    areas=salen["superficie"], puntos=salen["punto"], volumenes=salen["volumen"],
                    receptores=[(x, y, z) for x, y, z, _ in receptores],
                    nombres={"viento": VIENTO, "listado": lst, "concentraciones": dat},
                    titulo="Prueba de isosuperficies")
    fin = c.indice("_RECEPTORES")
    n = len(receptores)
    bloque = c.entradas[fin - 2 * n:fin]
    if any(e[0] != "X" for e in bloque[0::2]) or any(e[0] != "END" for e in bloque[1::2]):
        raise RuntimeError("los receptores no están donde se esperaba en el control")
    for e, (x, y, z, h) in zip(bloque[0::2], receptores):
        e[1] = "%.4f, %.4f, %.1f, %.3f" % (x / 1000.0, y / 1000.0, z, h)
    c.escribir(ruta)


def correr(carpeta, ini, nhoras, salen, receptores, procesos=4, nombre="caso"):
    """Lanza el motor con los receptores repartidos en `procesos` (son independientes). Devuelve fines, C (periodos ×
    receptores, en la unidad de la emisión por m³), segundos y memoria máxima por proceso (MB)."""
    preparar_viento(carpeta)
    env = dict(os.environ, PYTHONPATH=str(CARGADOR), PYTHONIOENCODING="utf-8")
    env.pop("PYTHONHOME", None)
    receptores = list(receptores)
    picos = [0] * procesos

    def uno(k):
        base = f"{nombre}_{k}"
        _control(carpeta / (base + ".inp"), ini, nhoras, salen, receptores[k::procesos], base + ".dat", base + ".lst")
        with open(carpeta / (base + ".log"), "w", errors="replace") as fo:
            p = subprocess.Popen([sys.executable, "-m", "teodors", "puffs", base + ".inp"], cwd=str(carpeta),
                                 stdout=fo, stderr=subprocess.STDOUT, env=env)
            yo = psutil.Process(p.pid)
            while p.poll() is None:
                try:
                    picos[k] = max(picos[k], yo.memory_info().peak_wset)
                except psutil.Error:
                    pass
                time.sleep(0.5)
        if p.returncode != 0 or not (carpeta / (base + ".dat")).exists():
            raise RuntimeError(f"{base}: el motor falló (rc={p.returncode}).\n"
                               + (carpeta / (base + ".log")).read_text(errors="replace")[-1500:])
        return base
    t0 = time.time()
    with ThreadPoolExecutor(procesos) as pool:
        bases = list(pool.map(uno, range(procesos)))
    seg = time.time() - t0
    fines, C = None, None
    bytes_dat = 0
    for k, base in enumerate(bases):
        dat = carpeta / (base + ".dat")
        bytes_dat += dat.stat().st_size
        fz, m = lector.concentraciones(dat, especie=ESPECIE)
        m = np.asarray(m, np.float32)
        if C is None:
            fines = pd.to_datetime(fz)
            C = np.zeros((len(fines), len(receptores)), np.float32)
        C[:, k::procesos] = m
        dat.unlink()
    return fines, C, {"segundos": round(seg, 1), "memoria_MB": [round(p / 1e6) for p in picos],
                      "fichero_conc_MB": round(bytes_dat / 1e6, 1)}


def rejilla_100m(semilado=3000.0, paso=100.0):
    """Nudos (x, y) de la malla horizontal, con el mismo origen que la de la app."""
    k = np.arange(-int(semilado / paso), int(semilado / paso) + 1) * paso
    return np.round(CENTRO[0] + k, 1), np.round(CENTRO[1] + k, 1)


def limpia(carpeta):
    shutil.rmtree(carpeta, ignore_errors=True)
    carpeta.mkdir(parents=True)
