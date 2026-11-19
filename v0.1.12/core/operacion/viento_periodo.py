# -*- coding: utf-8 -*-
"""Viento 3D de un periodo (un día, un episodio o una predicción), para el mapa y para `operacion.respuestas`.

Todo se baja de internet a la carpeta de DATOS de la planta (`planta.DATOS`; `periodos._lanzar` le pasa la suya):
  - terreno (MDT del IGN + CORINE de la copia local), si falta;
  - las estaciones de Meteocat cercanas, del día y del anterior (datos abiertos);
  - GFS 0,25° con niveles de presión (`fuentes.gfs_noaa`) de las
    ejecuciones de las 00 UTC del día, del anterior y del previo: predicción a 1 día (plazos
    1-24 h, interpolados entre plazos de 3 h), como en `casos.gfs_columnas`.
Después `meteo.viento3d` con GFS en columnas + las estaciones como observaciones
(NOOBS = 1, radios de `series` en planta.json), con 24 h de arranque y `--dias` días, y el resultado a
DATOS/viento3d/<serie>/ (cmz/AAAAMM.cmz + AAAAMM/caso.json); sin --serie, `series.gfs` de planta.json.

    python -m teodors.operacion.viento_periodo [--dia AAAA-MM-DD] [--dias 1] [--serie NOMBRE] [--prediccion]

Con --prediccion, desde que empieza `--dia`, la ejecución de las 00 UTC de ese día hasta `--dias` días (con lo que necesita el MOS,
`gfs_noaa.ejecucion(…, extra=True)`), y las estaciones: lo medido hasta ahora y, en las horas sin medida, la previsión de GFS corregida
con el MOS de cada estación (`operacion.prevision`, `mos.aplicar`; usuario, 2026-11-18: «Previsión corregida»), que se guarda con la
serie (`prevision_estaciones.csv`). Una hora sin temperatura en ninguna estación la toma del modelo (`estaciones.escribir`). Sin
modelos del MOS, las estaciones solo llevan lo medido. Lo descargado y el viento de la predicción van a la carpeta temporal, como en el
episodio, hasta que se guardan (`casos.viento3d.dir_serie`).
Planta: la de TEODORS_PLANTA.
"""
import argparse
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from teodors import planta as config
from teodors.casos import gfs_columnas as gc, viento3d as vc
from teodors.comun import registro
from teodors.fuentes import gfs_noaa as gfsn, meteocat as estaciones, terreno
from teodors.fuentes.meteocat import estaciones_dias
from teodors.meteo.viento3d import almacen
from teodors.mos import aplicar as mos
from teodors.operacion import penacho_mapa, prevision as PV
from teodors.planta import geo
from teodors.preparacion.viento3d import control, estaciones as obs, nubes, pronostico

TITULO_GFS = "GFS 0.25 -> pronostico 3D (%s)"          # %s: el nombre de la planta, ver `casos.viento3d.cabecera`
COMENTARIO_GFS = "GFS 0.25 deg pressure levels (NOAA), forecast at 1 day, one column per cell"


def _args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dia", default=None, help="aaaa-mm-dd (por defecto, ayer)")
    ap.add_argument("--dias", type=int, default=1)
    ap.add_argument("--serie", default=None)
    ap.add_argument("--prediccion", action="store_true")
    ap.add_argument("--procesos", type=int, default=0, help="descargas a la vez (0 = auto: cpu-2, tope 8)")
    return ap.parse_args()


def _fuente(lista, prevision):
    """Con qué se ha hecho el viento del periodo, para su caso.json (lo enseñan la app y el informe)."""
    if lista is None:
        return "GFS 0,25° (predicción)"
    if prevision is not None:
        return (f"GFS 0,25° (predicción) + {len(lista)} estaciones Meteocat: lo medido y, sin medida, la previsión corregida con el "
                f"MOS en {len(prevision)}")
    return f"GFS 0,25° (predicción a 1 día) + {len(lista)} estaciones Meteocat"


def _altura_en_cache(codigo):
    """La altura del anemómetro de una estación según lo último que se bajó de ella (su CSV en la caché), o 10 m."""
    for f in sorted((estaciones.dir_meteocat() / codigo).glob("*.csv"), reverse=True):
        try:
            h = pd.read_csv(f, usecols=["altura_viento_m"])["altura_viento_m"].dropna()
        except (ValueError, OSError):
            continue
        if len(h):
            return float(h.iloc[-1])
    return 10.0


def prevision_estaciones(fichero_mos, est, horas):
    """{código: tabla} de la previsión en las estaciones (`prevision.en_estaciones`): la ejecución de `fichero_mos` corregida con el
    MOS de cada una. {} si no hay modelos del MOS."""
    import xarray as xr
    modelos = mos.cargar([e["codigo"] for e in est])
    if not modelos:
        print("   ⚠ sin los modelos del MOS: las estaciones solo llevan lo medido", flush=True)
        return {}
    ds = xr.open_dataset(fichero_mos).load()
    return PV.en_estaciones(ds, mos.horaria(mos.corregir(ds, est, modelos), horas), est, horas)


def preparar_caso(dia, info, alturas, caso, n=1, fichero_ciclo=None, dgfs=None, prevision=None):
    """Caso de teOdors en `caso` (24 h de arranque + `n` días) con los datos ya descargados: GFS en n_col × n_col columnas y las
    estaciones (alturas: {código: altura del anemómetro}; None: sin estaciones, y `fichero_ciclo` con la predicción larga).
    `prevision` (solo la predicción: {código: tabla de `prevision.en_estaciones`}) rellena las horas sin medida de cada estación
    (`prevision.completar`, guardado en `caso/prevision_estaciones.csv`), y la hora sin temperatura en ninguna estación la toma del
    modelo en vez de dejar el caso sin estaciones.
    Escribe geo.dat, pronostico3d.dat, nubes.dat, estaciones.dat, viento3d.inp y caso.json. Devuelve (geo, nubes por hora)."""
    emp = config.cargar_emplazamiento()
    ciclo = dia if fichero_ciclo else None
    dias = [dia + pd.Timedelta(days=k) for k in range(-2, 0 if ciclo is not None else n)]
    horas = list(pd.date_range(dia - pd.Timedelta(days=1), dia + pd.Timedelta(days=n), freq="h"))
    col, xs, ys = gc.columnas(gc.niveles(dias, [fichero_ciclo] if fichero_ciclo else (), raiz=dgfs), horas, ciclo)
    Z, U, tr = terreno.cargar(info)
    r = vc.rejilla(Z, U, tr)
    zona = geo.huso_utm(emp["lon"])
    shutil.rmtree(caso, ignore_errors=True)
    caso.mkdir(parents=True)
    g = vc.escribir_geo(caso / "geo.dat", r, zona)
    pronostico.escribir_columnas(caso / "pronostico3d.dat", col, config.pide("pronostico", "n_col"), xs, ys, horas, gc.NIVELES,
                                 (emp["lat"], emp["lon"]), config.EPSG_UTM, titulo=vc.cabecera(TITULO_GFS),
                                 comentario=COMENTARIO_GFS)
    nubes.escribir_zonas(caso / "nubes.dat", col, r, xs, ys, horas)
    sfc = col.groupby("time")[["cloud_cover", "temperature_2m", "dew_point_2m", "surface_pressure"]].mean().reset_index()
    sfc["tcc"] = sfc.cloud_cover / 100.0
    sfc["t2m"], sfc["d2m"], sfc["sp"] = sfc.temperature_2m, sfc.dew_point_2m, sfc.surface_pressure     # °C, °C, hPa
    lista, aviso, medido_hasta = None, None, None
    if alturas is not None:
        lista, medidas, completas = [], [], {}
        anios = sorted({h.year for h in horas})
        for k, e in enumerate(estaciones.cercanas(emp["lat"], emp["lon"]), 1):
            o = vc.obs_horarias(e["codigo"], anios, conv="inicio")       # Meteocat (5 años)
            if prevision is not None:
                o = completas[e["codigo"]] = PV.completar(o, prevision.get(e["codigo"]), horas)
            x, y = geo.a_utm(e["lat"], e["lon"])
            lista.append((e["codigo"], 100000 + k, x / 1000, y / 1000, alturas[e["codigo"]]))
            medidas.append((100000 + k, o))
        if prevision is not None:
            PV.guardar(completas, caso)
            vistas = [o.time[o.ws.notna() & ~o.previsto] for o in completas.values()]
            medido_hasta = max((v.max() for v in vistas if len(v)), default=None)
        # Una hora sin ninguna temperatura para el motor. Medido el 2026-11-01: los datos abiertos de Meteocat acababan el 26/10 a las 17:30
        con_t = pd.concat([o.set_index("time")["t"].reindex(horas) for _, o in medidas], axis=1).notna().any(axis=1)
        if con_t.all() or prevision is not None:          # la predicción: esa hora, del modelo (`estaciones.escribir`)
            obs.escribir(caso / "estaciones.dat", medidas, horas,
                         sfc[["time", "tcc", "t2m", "d2m", "sp"]] if prevision is not None else sfc[["time", "tcc"]],
                         comentario=vc.COMENTARIO_OBS)
        else:
            aviso = f"Estaciones hasta el {con_t.index[con_t][-1]:%d/%m %H:%M} UTC: sin ellas" if con_t.any() else "Sin datos de las estaciones"
            print(f"   ⚠ {aviso}", flush=True)
            lista = None
    radios = {} if lista is None else {"r1_km": config.pide("series", "r1_km"), "rmax_km": config.pide("series", "rmax_km")}
    control.escribir(caso / "viento3d.inp", r, horas[0], len(horas) - 1, zona, config.VIENTO3D_ZFACE,
                     estaciones=lista, isurft=1, **radios)
    caso_json = {"anio": dia.year, "mes": dia.month, "horas": 24 * n, "arranque_h": 24,
                 "ini_corrida": f"{pd.Timestamp(horas[0]):%Y-%m-%d %H:%M}",   # lo necesita respuestas.py (bug: antes faltaba en el episodio)
                 "nx": g["nx"], "ny": g["ny"], "celda_m": r["celda_m"], "ext": list(r["ext"]), "zona": zona,
                 "fuente": _fuente(lista, prevision),
                 "con_estaciones": lista is not None, "aviso": aviso,
                 "mos": len(prevision or {}) if lista is not None else 0,
                 "medido_hasta": None if medido_hasta is None else f"{pd.Timestamp(medido_hasta):%Y-%m-%d %H:%M}",
                 "dias_completos": [f"{dia + pd.Timedelta(days=k):%Y-%m-%d}" for k in range(n)]}
    (caso / "caso.json").write_text(json.dumps(caso_json, indent=1, default=float), encoding="utf-8")
    return g, sfc.set_index("time").tcc


def meteo_planta(caso, dia, n, nubes_h):
    """Tiempo en la planta hora a hora (viento, T, radiación, lluvia del viento 3D; nubes de GFS), para el panel del penacho."""
    emp = config.cargar_emplazamiento()
    xp, yp = geo.a_utm(emp["lat"], emp["lon"])
    c = vc.leer(caso, niveles=(1,), campos2d=("TEMPK", "QSW", "RMM"), fichero="viento3d.dat")
    vp = vc.viento_en_punto(c, emp["lat"], emp["lon"], 1).set_index("time")
    salen = []
    for k, h in enumerate(c["horas"]):
        if not dia <= h < dia + pd.Timedelta(days=n):
            continue
        q = float(vc.en_punto(c["QSW"][k], xp, yp, c["x"], c["y"]))
        ll = float(vc.en_punto(c["RMM"][k], xp, yp, c["x"], c["y"]))
        nub = float(nubes_h[h]) if h in nubes_h.index else None
        ic, txt = penacho_mapa.icono_tiempo(q, nub, ll)
        salen.append({"hora": f"{h:%Y-%m-%d %H:%M}", "ws": round(float(vp.ws[h]), 2), "wd": round(float(vp.wd[h]), 1),
                      "t": round(float(vc.en_punto(c["TEMPK"][k], xp, yp, c["x"], c["y"])) - 273.15, 1), "qsw": round(q, 1),
                      "nubes": None if nub is None else round(nub, 2), "lluvia": round(ll, 2), "icono": ic, "tiempo": txt})
    return salen


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    A = _args()
    config.asegurar_carpetas()
    registro.configurar(config.DIR_LOGS, config.REGISTRO)
    t0 = time.time()
    dia = pd.Timestamp(A.dia) if A.dia else pd.Timestamp.now().normalize() - pd.Timedelta(days=1)
    n, serie = A.dias, A.serie or config.pide("series", "gfs")
    print(f"Día {dia:%Y-%m-%d} · {n} día(s) · serie {serie} · DATOS en {config.DATOS}", flush=True)
    emp = config.cargar_emplazamiento()
    lat, lon = emp["lat"], emp["lon"]
    # 1) terreno
    info = terreno.ultimo_caso(lat, lon)
    if info is None:
        print("1) terreno: descargando MDT del IGN + CORINE (una vez)…", flush=True)
        terreno.descargar(lat, lon, config.DOMINIO_DESCARGA_KM,
                          progreso=lambda p, m="": print(f"   {p:3d} % {m}", flush=True))
        info = terreno.ultimo_caso(lat, lon)
    print(f"1) terreno listo ({time.time() - t0:.0f} s)", flush=True)
    # 2-3) Descargas en PARALELO (estaciones Meteocat + GFS por día): es el cuello de botella del viento del episodio
    #      (medido 2026-11-11: ~300 s en serie → ~37 s a 8 a la vez, ~8×). El motor y el resto no cambian.
    dias = [dia + pd.Timedelta(days=k) for k in range(-2, 0 if A.prediccion else n)]
    # El GFS del EPISODIO y de la PREDICCIÓN es temporal (se borra al cancelar): a tmp por serie. El del reanálisis, a la caché de DATOS.
    dgfs = (config.LOCAL / "meteo_episodio" / serie / "gfs_niveles") if vc.es_temporal(serie) \
        else (config.DATOS / "meteo" / "gfs_niveles")
    dgfs.mkdir(parents=True, exist_ok=True)
    tareas = [("gfs", d) for d in dias if not (dgfs / f"gfs00_{d:%Y%m%d}.nc").exists()]
    est = estaciones.cercanas(lat, lon)
    ini, fin = dia - pd.Timedelta(days=1, hours=1), dia + pd.Timedelta(days=n, hours=1)
    if A.prediccion:
        fin = min(fin, pd.Timestamp.now(tz="UTC").tz_localize(None).floor("h"))     # lo medido llega, como mucho, hasta ahora
    tareas += [("sta", e) for e in est]
    # descargas = I/O (red): el límite es el ancho de banda, no la RAM → usar tantos workers como tareas (cpu-2 de tope)
    procesos = A.procesos if A.procesos > 0 else max(1, (os.cpu_count() or 4) - 2)
    procesos = max(1, min(procesos, len(tareas) or 1))
    print(f"2-3) Descargando en paralelo ({procesos} a la vez): {len(est)} estaciones + "
          f"{sum(1 for k, _ in tareas if k == 'gfs')} días de GFS…", flush=True)

    def _bajar(t):
        k, x = t
        if k == "sta":
            try:
                return "sta", estaciones_dias([x], ini, fin)             # una estación a su CSV del año (ficheros distintos: sin choques)
            except Exception as e:                                         # noqa: BLE001
                if not A.prediccion:
                    raise
                print(f"   ⚠ {x['codigo']}: sin lo medido ({type(e).__name__}); va con la previsión", flush=True)
                return "sta", {x["codigo"]: _altura_en_cache(x["codigo"])}
        gfsn.ejecucion(x, 9).to_netcdf(dgfs / f"gfs00_{x:%Y%m%d}.nc")     # un día de GFS (ya con 9 hilos internos)
        return "gfs", x

    alturas = {}
    with ThreadPoolExecutor(procesos) as pool:
        for tipo, r in pool.map(_bajar, tareas):
            if tipo == "sta":
                alturas.update(r)
            else:
                print(f"3) GFS {r:%Y-%m-%d} 00 UTC listo ({time.time() - t0:.0f} s)", flush=True)
    fichero_ciclo = prevista = None
    if A.prediccion:
        fichero_ciclo = dgfs / f"gfs00_{dia:%Y%m%d}_{24 * n}h.nc"
        fichero_mos = dgfs / f"gfs00_{dia:%Y%m%d}_{24 * n}h_mos.nc"                   # la misma, con lo que necesita el MOS
        if not (fichero_ciclo.exists() and fichero_mos.exists()):
            ds = gfsn.ejecucion(dia, 9, range(0, 24 * n + 1, 3), extra=True)
            extras = [v for v in (*gfsn.EXTRA.values(), *gfsn.EXTRA_MEDIA.values()) if v in ds]
            ds.to_netcdf(fichero_mos)
            ds.drop_vars(extras).to_netcdf(fichero_ciclo)                             # la de siempre, sin lo del MOS
        print(f"3) GFS {dia:%Y-%m-%d} 00 UTC a {24 * n} h listo ({time.time() - t0:.0f} s)", flush=True)
        horas = pd.date_range(dia - pd.Timedelta(days=1), dia + pd.Timedelta(days=n), freq="h")
        prevista = prevision_estaciones(fichero_mos, est, horas)
        print(f"3) previsión corregida (MOS) en {len(prevista)} estaciones ({time.time() - t0:.0f} s)", flush=True)
    # 4) caso de teOdors: 24 h de arranque + los días
    caso = config.DIR_TRABAJO / "viento_dia_local" / serie
    g, nubes_h = preparar_caso(dia, info, alturas, caso, n, fichero_ciclo, dgfs=dgfs, prevision=prevista)
    print(f"4) caso preparado ({time.time() - t0:.0f} s); teOdors en marcha…", flush=True)
    seg, dat = vc.ejecutar(caso)
    meteo = meteo_planta(caso, dia, n, nubes_h)
    # 5) al almacén de la serie (sin recortar: el día de arranque también se puede ver)
    base = vc.dir_serie(serie)
    destino = base / "cmz" / f"{dia:%Y%m}.cmz"
    destino.parent.mkdir(parents=True, exist_ok=True)
    res = almacen.comprimir(dat, destino, g["nx"], g["ny"])
    (base / f"{dia:%Y%m}").mkdir(parents=True, exist_ok=True)
    shutil.copy2(caso / "caso.json", base / f"{dia:%Y%m}" / "caso.json")
    shutil.copy2(caso / "viento3d.inp", base / f"{dia:%Y%m}" / "viento3d.inp")
    if (caso / PV.FICHERO).is_file():                                                 # la predicción: la previsión en las estaciones
        shutil.copy2(caso / PV.FICHERO, base / f"{dia:%Y%m}" / PV.FICHERO)
    (base / f"{dia:%Y%m}" / "meteo.json").write_text(json.dumps(meteo, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(caso, ignore_errors=True)
    print(f"5) teOdors {seg / 60:.1f} min · {res['comprimido_mb']:.0f} MB en {destino} · total "
          f"{(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
