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

Con --prediccion, sin estaciones (NOOBS = 2) y desde que empieza `--dia`, la ejecución de las 00 UTC de ese día hasta `--dias` días.
Planta: la de TEODORS_PLANTA.
"""
import argparse
import json
import shutil
import sys
import time

import numpy as np
import pandas as pd

from teodors import planta as config
from teodors.casos import gfs_columnas as gc, viento3d as vc
from teodors.comun import registro
from teodors.fuentes import gfs_noaa as gfsn, meteocat as estaciones, terreno
from teodors.fuentes.meteocat import estaciones_dias
from teodors.meteo.viento3d import almacen
from teodors.operacion import penacho_mapa
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
    return ap.parse_args()


def preparar_caso(dia, info, alturas, caso, n=1, fichero_ciclo=None):
    """Caso de teOdors en `caso` (24 h de arranque + `n` días) con los datos ya descargados: GFS en n_col × n_col columnas y las
    estaciones (alturas: {código: altura del anemómetro}; None: sin estaciones, y `fichero_ciclo` con la predicción larga).
    Escribe geo.dat, pronostico3d.dat, nubes.dat, estaciones.dat, viento3d.inp y caso.json. Devuelve (geo, nubes por hora)."""
    emp = config.cargar_emplazamiento()
    ciclo = dia if fichero_ciclo else None
    dias = [dia + pd.Timedelta(days=k) for k in range(-2, 0 if ciclo is not None else n)]
    horas = list(pd.date_range(dia - pd.Timedelta(days=1), dia + pd.Timedelta(days=n), freq="h"))
    col, xs, ys = gc.columnas(gc.niveles(dias, [fichero_ciclo] if fichero_ciclo else ()), horas, ciclo)
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
    sfc = col.groupby("time")[["cloud_cover"]].mean().reset_index()
    sfc["tcc"] = sfc.cloud_cover / 100.0
    lista, aviso = None, None
    if alturas is not None:
        lista, medidas = [], []
        anios = sorted({h.year for h in horas})
        for k, e in enumerate(estaciones.cercanas(emp["lat"], emp["lon"]), 1):
            o = vc.obs_horarias(e["codigo"], anios, conv="inicio")       # Meteocat (5 años)
            x, y = geo.a_utm(e["lat"], e["lon"])
            lista.append((e["codigo"], 100000 + k, x / 1000, y / 1000, alturas[e["codigo"]]))
            medidas.append((100000 + k, o))
        # Una hora sin ninguna temperatura para el motor. Medido el 2026-11-01: los datos abiertos de Meteocat acababan el 26/10 a las 17:30
        con_t = pd.concat([o.set_index("time")["t"].reindex(horas) for _, o in medidas], axis=1).notna().any(axis=1)
        if con_t.all():
            obs.escribir(caso / "estaciones.dat", medidas, horas, sfc[["time", "tcc"]],
                         comentario=vc.COMENTARIO_OBS)
        else:
            aviso = f"Estaciones hasta el {con_t.index[con_t][-1]:%d/%m %H:%M} UTC: sin ellas" if con_t.any() else "Sin datos de las estaciones"
            print(f"   ⚠ {aviso}", flush=True)
            lista = None
    radios = {} if lista is None else {"r1_km": config.pide("series", "r1_km"), "rmax_km": config.pide("series", "rmax_km")}
    control.escribir(caso / "viento3d.inp", r, horas[0], len(horas) - 1, zona, config.VIENTO3D_ZFACE,
                     estaciones=lista, isurft=1, **radios)
    caso_json = {"anio": dia.year, "mes": dia.month, "horas": 24 * n, "arranque_h": 24,
                 "nx": g["nx"], "ny": g["ny"], "celda_m": r["celda_m"], "ext": list(r["ext"]), "zona": zona,
                 "fuente": ("GFS 0,25° (predicción)" if lista is None else f"GFS 0,25° (predicción a 1 día) + {len(lista)} estaciones Meteocat"),
                 "con_estaciones": lista is not None, "aviso": aviso,
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
    # 2) estaciones del día y del anterior
    alturas = None
    if not A.prediccion:
        est = estaciones.cercanas(lat, lon)
        ini, fin = dia - pd.Timedelta(days=1, hours=1), dia + pd.Timedelta(days=n, hours=1)
        print(f"2) Meteocat: {len(est)} estaciones, {ini:%d/%m %H:%M} a {fin:%d/%m %H:%M} UTC", flush=True)
        alturas = estaciones_dias(est, ini, fin)
    # 3) GFS con niveles de presión: de cada hora, la ejecución del día anterior (predicción a 1 día)
    dias = [dia + pd.Timedelta(days=k) for k in range(-2, 0 if A.prediccion else n)]
    dgfs = config.DATOS / "meteo" / "gfs_niveles"
    dgfs.mkdir(parents=True, exist_ok=True)
    for d in dias:
        f = dgfs / f"gfs00_{d:%Y%m%d}.nc"
        if not f.exists():
            gfsn.ejecucion(d, 9).to_netcdf(f)
        print(f"3) GFS {d:%Y-%m-%d} 00 UTC listo ({time.time() - t0:.0f} s)", flush=True)
    fichero_ciclo = None
    if A.prediccion:
        fichero_ciclo = dgfs / f"gfs00_{dia:%Y%m%d}_{24 * n}h.nc"
        if not fichero_ciclo.exists():
            gfsn.ejecucion(dia, 9, range(0, 24 * n + 1, 3)).to_netcdf(fichero_ciclo)
        print(f"3) GFS {dia:%Y-%m-%d} 00 UTC a {24 * n} h listo ({time.time() - t0:.0f} s)", flush=True)
    # 4) caso de teOdors: 24 h de arranque + los días
    caso = config.DIR_TRABAJO / "viento_dia_local" / serie
    g, nubes_h = preparar_caso(dia, info, alturas, caso, n, fichero_ciclo)
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
    (base / f"{dia:%Y%m}" / "meteo.json").write_text(json.dumps(meteo, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(caso, ignore_errors=True)
    print(f"5) teOdors {seg / 60:.1f} min · {res['comprimido_mb']:.0f} MB en {destino} · total "
          f"{(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
