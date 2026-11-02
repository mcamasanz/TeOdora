# -*- coding: utf-8 -*-
"""Prueba 10: huella de lo que la herramienta da hoy, para comprobar que llevar el código a teOdors no cambia nada.

Una huella (SHA-256) por resultado: focos, normativa, malla, terreno, viento, casos del motor, una corrida corta del motor, viento
local, simulaciones de las modalidades, tablas e imágenes. Se calcula con los datos de ENCE_GALERA_DATOS y se compara con `comparar.py`.

    python 99-Test/10_migracion/linea_base.py salida.json

No usa la GUI: para eso están las pruebas de clics. Lo que cambia de una vez a otra (fechas, segundos) se quita antes de la huella.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
_planta.actual().DIR_PLANES = _planta.DATOS / "escenarios"      # los planes de las pruebas, con la copia de los datos: nunca en la carpeta de la planta
sys.stdout.reconfigure(encoding="utf-8")
if "ENCE_GALERA_DATOS" not in os.environ:
    raise SystemExit("Hay que dar ENCE_GALERA_DATOS: una COPIA de los datos, esto reescribe resultados")
salida = Path(sys.argv[1])
os.environ.setdefault("NUMBA_CACHE_DIR", str(Path(os.environ["TEMP"]) / "ence_odora_numba"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from teodors.planta import geo  # noqa: E402
from teodors.fuentes import catastro as edificios  # noqa: E402
from teodors.fuentes import meteocat as estaciones  # noqa: E402
from teodors.fuentes import terreno  # noqa: E402
from teodors import planta as config  # noqa: E402
from teodors.operacion import planes as E  # noqa: E402
from teodors.operacion import focos as F  # noqa: E402
from teodors.operacion import normativa as N  # noqa: E402
from teodors.operacion import penacho_mapa  # noqa: E402
from teodors.operacion import periodos  # noqa: E402
from teodors.operacion import simulacion as PC  # noqa: E402
from teodors.casos import receptores as receptores_mapa  # noqa: E402
from teodors.operacion import viento_mapa  # noqa: E402
from teodors.preparacion.puffs import control_fuentes as cf  # noqa: E402
from teodors.meteo.viento_local import modelo as local  # noqa: E402
from teodors.metricas import viento as validacion  # noqa: E402

H = {}
t00 = time.time()


def _plano(x):
    """Lo mismo de forma comparable: arrays a bytes, y los números con todos sus decimales."""
    if isinstance(x, np.ndarray):
        return {"__a": str(x.dtype), "f": list(x.shape), "h": hashlib.sha256(x.tobytes()).hexdigest()}
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    if isinstance(x, pd.Timestamp):
        return str(x)
    if isinstance(x, dict):
        return {str(k): _plano(v) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
    if isinstance(x, (list, tuple)):
        return [_plano(v) for v in x]
    if isinstance(x, Path):
        return x.name
    return x


def huella(nombre, x):
    H[nombre] = hashlib.sha256(json.dumps(_plano(x), ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:24]


def fichero(nombre, ruta):
    H[nombre] = hashlib.sha256(Path(ruta).read_bytes()).hexdigest()[:24]


def paso(nombre):
    print(f"{time.time() - t00:6.0f} s  {nombre}", flush=True)


# ── coordenadas ──
paso("coordenadas")
emp = config.cargar_emplazamiento()
huella("emplazamiento", emp)
huella("config.dominio", [config.EPSG_UTM, config.RADIO_CALCULO_KM, config.VIENTO3D_CELDA_M, list(config.VIENTO3D_ZFACE), config.RADIO_EDIFICIOS_KM, config.RADIO_EDIFICIOS_FOCOS_M])
huella("geo", [geo.a_utm(emp["lat"], emp["lon"]), geo.a_geo(286763.0, 4507474.0), geo.dir_geo_a_rejilla(90.0, emp["lat"], emp["lon"])])

# ── focos, planes y normativa ──
paso("focos, planes, normativa")
cat = F.cargar()
huella("focos.datos", [[f["id"], F.olor_ouE_s(f), F.gases_g_s(f), F.huella(f), F.perfil(f), F.fraccion_eventos(f), F.pendientes(f), F.olor_medido(f), F.gas_dominante(f)] for f in cat["focos"]])
huella("focos.magnitudes", F.magnitudes(cat))
huella("normativa.columnas", {k: {l: N.columnas(k, l) for l in ("anios", "dias")} for k in ("olor", "H2S", "NH3", "NO2", "NOx", "SO2", "CO")})
sem = {"plan": "semanal", "perfiles": [[1.0] * 24, [0.25] * 24], "dias": [0, 1, 0, 1, 0, 1, 1]}
huella("planes.factores", E.factores(sem, pd.date_range("2026-03-27", "2026-03-31", freq="h")))
huella("planes.nivel", E.nivel_medio(sem))
fines = pd.date_range("2021-01-01 01:00", "2022-12-31 00:00", freq="h")
C = (np.sin(np.arange(len(fines))[:, None] / 7.0 + np.arange(5)[None, :]) ** 2 * 400).astype(np.float32)
huella("normativa.estadisticos", {k: {c["clave"]: N.estadistico(c, C, fines) for c in N.columnas(k, "anios")} for k in ("olor", "NO2", "SO2", "CO")})

# ── terreno, malla, edificios, estaciones ──
paso("terreno, malla, edificios, estaciones")
info = terreno.ultimo_caso(emp["lat"], emp["lon"])
Z, U, tr = terreno.cargar(info)
res = terreno.resumen(Z, U, tr, emp["lat"], emp["lon"])
huella("terreno.cargar", [Z, U, list(tr)[:6]])
huella("terreno.resumen", {k: v for k, v in res.items() if k != "nucleos"})
huella("terreno.nucleos", res["nucleos"])
huella("terreno.nombres", terreno.nombres_nucleos(info, res["nucleos"]))
bld = edificios.cargar(emp["lat"], emp["lon"])[1]
huella("edificios", [len(bld), bld["uso"].tolist(), bld["altura_m"].round(3).tolist(), edificios.cercanos(bld)["ref"].tolist()])
m = receptores_mapa.malla(res["nucleos"], bld)
huella("receptores.malla", m)
huella("receptores.con_nombre", receptores_mapa.con_nombre())
huella("estaciones.cercanas", estaciones.cercanas(emp["lat"], emp["lon"]))
huella("estaciones.rosas_dia", validacion.rosas_dia(emp["lat"], emp["lon"], "2026-10-21"))

# ── viento en el mapa ──
paso("viento")
huella("viento.series", [viento_mapa.serie_disponible(), viento_mapa.meses("odora_gfs_8est"), viento_mapa.rango_dias("odora_gfs_8est"), viento_mapa.dia_inicial("odora_gfs_8est")])
huella("viento.dia", viento_mapa.datos_dia("2026-10-21", "odora_gfs_8est"))
huella("viento.periodo", viento_mapa.datos_dia("2026-10-23", "queja_20261023_3d", dias=3))
huella("viento.local", viento_mapa.datos_local())
huella("penacho.tiempo", penacho_mapa.tiempo_dia("2026-10-23", "queja_20261023_3d", 3).get("meteo"))
huella("periodos", [periodos.nuevo("queja", "2026-10-23", 3), periodos.etiqueta(periodos.nuevo("queja", "2026-10-30", 3)), periodos.dias_reanalisis(),
                    periodos.fuente(periodos.nuevo("queja", "2026-10-25", 2)), periodos.inicio_prediccion(pd.Timestamp("2026-11-01 03:00"))])

# ── viento local: obstáculos y un cálculo grueso ──
paso("viento local")
L = local.lee_lidar(config.DATOS / "viento_local" / "planta_1m.npz")
eds = local.obstaculos(L)
huella("local.obstaculos", [[e["area"], e["h"], e["centro"]] for e in eds])
dom, cabe, alt = local.monta(L, eds, 10.0, 5.0, (286796.0, 4507440.0), 250.0)
c = local.calcula(dom, 255.0, cabe, n_iter=300)
huella("local.calcula", [dom.nx, dom.ny, dom.nz, c["iteraciones"], np.round(c["u"], 6), np.round(c["v"], 6), np.round(local.a_altura(dom, c["u"], 3.0), 6)])

# ── lo que se le da al motor ──
paso("control del motor")
malla_v = {"nx": 125, "ny": 125, "celda_m": 400.0, "ext": list(json.loads((config.DIR_VIENTO3D / "odora_gfs_8est" / "202610" / "caso.json").read_text(encoding="utf-8"))["ext"])}


def cota(x, y):
    f = int((tr.f - y) / -tr.e)
    k = int((x - tr.c) / tr.a)
    return float(max(Z[min(max(f, 0), Z.shape[0] - 1), min(max(k, 0), Z.shape[1] - 1)], 0.0))


salen = {"superficie": [], "punto": [], "volumen": []}
for f in cat["focos"]:
    modelo, d, q0 = F.geometria(f, cota)
    d.update(perfil={"C": [1.0] * 24}, q={"C": q0})
    salen[modelo].append(d)
huella("control.fuentes", salen)
recs = [(286763.2 + dx, 4507473.5 + dy, cota(286763.2 + dx, 4507473.5 + dy), h) for dx in (-800.0, 0.0, 800.0) for dy in (-800.0, 0.0, 800.0) for h in (0.0, 20.0)]
ctl = cf.preparar(malla_v, config.VIENTO3D_ZFACE, pd.Timestamp("2026-10-21 05:00"), 3, 31, ["C"], areas=salen["superficie"], puntos=salen["punto"], volumenes=salen["volumen"], receptores=recs,
                  nombres={"viento": "viento3d.dat", "listado": "x.lst", "concentraciones": "x.dat"}, titulo="Linea base")
huella("control.texto", ctl.entradas)

# ── una corrida corta del motor, con ese control ──
paso("una corrida del motor")
from teodors.meteo.viento3d import almacen  # noqa: E402
from teodors.preparacion.puffs import salida as lector  # noqa: E402

trabajo = Path(tempfile.mkdtemp(prefix="linea_base_"))
try:
    almacen.descomprimir(config.DIR_VIENTO3D / "odora_gfs_8est" / "cmz" / "202610.cmz", trabajo / "viento3d.dat")
    ctl.escribir(trabajo / "x.inp")
    import subprocess
    env = dict(os.environ, PYTHONPATH=str(CARGADOR), PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, "-m", "teodors", "puffs", "x.inp"], cwd=str(trabajo), check=True, env=env, stdout=subprocess.DEVNULL)
    fz, conc = lector.concentraciones(trabajo / "x.dat", especie="C")
    huella("motor.corrida", [list(map(str, fz)), np.asarray(conc)])
finally:
    shutil.rmtree(trabajo, ignore_errors=True)


# ── simulaciones ──
def sin_tiempos(res):
    r = json.loads(json.dumps(res, default=str))
    for k in ("fecha", "segundos", "segundos_serie"):
        r.pop(k, None)
    for k in ("creado", "modificado"):         # del plan: la hora a la que se creó
        r.get("esc", {}).pop(k, None)

    def limpia(x):
        if isinstance(x, dict):
            return {k: limpia(v) for k, v in x.items()}
        if isinstance(x, list):
            return [limpia(v) for v in x]
        if isinstance(x, str) and x.startswith("file:"):
            return x.split("/")[-1].split("?")[0]
        return x
    return limpia(r)


def resultado(nombre, res, raiz, imagenes):
    huella(f"{nombre}.resultado", sin_tiempos(res))
    for k in res["orden"]:
        with np.load(raiz / k / "resumen.npz") as z:
            huella(f"{nombre}.{k}.resumen", {c: z[c] for c in z.files})
        if (raiz / k / "penacho.npz").is_file():
            with np.load(raiz / k / "penacho.npz") as z:
                huella(f"{nombre}.{k}.penacho", z["C"])
    for n in imagenes:
        fichero(f"{nombre}.png.{n}", raiz / "olor" / n)


base = E.nuevo(cat, "linea base")
for s in (PC.carpeta_resultados(base).parent.parent,):
    pass
paso("simular 5 años")
r5 = PC.calcular(base, cat)
resultado("anios", r5, PC.carpeta_resultados(base), ["media_0.png", "p98_0.png", "maximo_1.png"])
paso("simular un día del reanálisis")
pd_ = periodos.nuevo("reanalisis", "2026-10-21", 1, "odora_gfs_8est")
rd = PC.calcular_periodo(base, cat, pd_)
resultado("dia", rd, PC.carpeta_resultados(base, pd_), ["media_0.png", "penacho_007_0.png", "penacho_015_1.png"])
paso("simular el episodio de 3 días")
pq = periodos.nuevo("queja", "2026-10-23", 3)
rq = PC.calcular_periodo(base, cat, pq)
resultado("queja", rq, PC.carpeta_resultados(base, pq), ["media_0.png", "penacho_041_0.png"])
huella("queja.tooltip", PC.tabla_punto(next(iter(PC.valores(rq, "olor").values())), "x", rq["magnitudes"]["olor"]))
huella("guardado", [PC.guardado(base, cat, pq) is not None, PC.firma(base, cat, pq)])
shutil.rmtree(config.DATOS / "resultados_planes" / "reanalisis" / "5_anios" / "linea_base", ignore_errors=True)

salida.parent.mkdir(parents=True, exist_ok=True)
salida.write_text(json.dumps(H, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
print(f"{len(H)} huellas en {salida} · {(time.time() - t00) / 60:.1f} min", flush=True)
