# -*- coding: utf-8 -*-
"""Casos de viento 3D de una planta: une sus datos (terreno, ERA5, estaciones de Meteocat y carpetas de DATOS) con
`preparacion.viento3d`, que escribe las entradas y el control, y con `meteo.viento3d`, que calcula. Prepara un mes (ERA5 y, si se
dan, estaciones como observaciones), lo lanza, saca las series en la planta y las estaciones, vigila el disco y guarda los meses de
una serie en DATOS/viento3d/<serie>.
"""
import json
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

from teodors import planta as config
from teodors.comun import procesos, registro
from teodors.planta import geo
from teodors.preparacion.viento3d import control, estaciones as obs, geofisica, nubes, pronostico, salida

log = registro.get("viento3d_casos")

# Cabeceras de los ficheros de entrada (solo texto: el motor no las usa). %s: el nombre de la planta, ver `cabecera`
TITULO_GEO = "Malla geofisica de %s (CORINE + MDT del IGN)"
TITULO_ERA5 = "ERA5 -> pronostico 3D (%s)"
COMENTARIO_OBS = "Meteocat XEMA, medias horarias centradas (%s)"

# El viento 3D tiene memoria NOCTURNA (medido 2026-10-15): cada mes arranca ARRANQUE_H antes y
# esas horas se recortan al guardarlo (salida.recorte).
ARRANQUE_H = 24
CONSERVAR = ("caso.json", "puntos.csv", "resumen.json", "viento3d.inp")


def cabecera(texto):
    """Una cabecera de arriba con el nombre de la planta (`identidad.nombre_casos` de planta.json; va al fichero tal cual, en ASCII)."""
    return texto % config.bloque("identidad").get("nombre_casos", "teOdors")


def caso_dir(anio, mes):
    """Carpeta del caso EN MARCHA (config.DIR_TRABAJO, fuera de DATOS)."""
    return config.DIR_TRABAJO / "viento3d" / f"{anio}{mes:02d}"


def conservar(caso, destino):
    """Copia lo pequeño de un caso (CONSERVAR) a destino, dentro de DATOS."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    for f in CONSERVAR:
        if (Path(caso) / f).exists():
            shutil.copy2(Path(caso) / f, destino / f)
    return destino


# ── malla y fichero geofísico ────────────────────────────────────────────────────────────
def rejilla(Z, U, transform, celda_m=None):
    """Malla del viento 3D sobre el terreno fino (25 m), alineada con su esquina SUROESTE."""
    celda_m = config.VIENTO3D_CELDA_M if celda_m is None else celda_m
    return geofisica.malla(Z, U, transform, celda_m)


def escribir_geo(ruta, r, zona):
    """Fichero geofísico con teOdors; el mar sin polígono de CORINE (`fuentes.terreno.mascara_mar`) entra
    como mar. Devuelve nx, ny y las categorías presentes."""
    from teodors.fuentes import terreno
    return geofisica.escribir(ruta, r, zona, mar=terreno.mascara_mar(r["Z"], r["U"]),
                              titulo=cabecera(TITULO_GEO))


# ── observaciones de las estaciones ──────────────────────────────────────────────────────
def obs_horarias(codigo, anios, conv=None):
    """Medias horarias de una estación de Meteocat (`preparacion.viento3d.estaciones.medias_horarias`) sin las
    semihoras que marcó el control de calidad (`metricas.calidad`), si existe. `conv`
    («inicio»/«fin») evita deducirla de la radiación (con pocos días no es fiable; Meteocat es «inicio»)."""
    from teodors.fuentes import meteocat as estaciones
    from teodors.metricas import viento as validacion
    df = estaciones.cargar(codigo, anios)
    if df.empty:
        return df
    if conv is None:
        conv, _ = validacion.convencion(df)
    qc = config.DATOS / "reanalisis" / f"01_estacion_{codigo}" / "medidas_30min_qc.csv.gz"
    if qc.exists():
        q = pd.read_csv(qc, parse_dates=["time"], usecols=["time", "qc"], dtype={"qc": str})
        df = df[~df.time.isin(q.time[q.qc.fillna("").astype(str) != ""])]
    return obs.medias_horarias(df, conv)


# ── caso mensual ─────────────────────────────────────────────────────────────────────────
def preparar_mes(anio, mes, terrad_km=5.0, arranque_h=ARRANQUE_H, estaciones=None,
                 r1_km=None, rmax_km=None, caso=None, extra=None):
    """Escribe geo.dat, pronostico3d.dat, nubes.dat y viento3d.inp del mes en caso_dir(anio, mes).
    La corrida empieza `arranque_h` antes del mes si hay ERA5 de esas horas (si no, arranca en frío). Con `estaciones` (lista de
    códigos de Meteocat) escribe además estaciones.dat y el motor usa esas observaciones de superficie (NOOBS = 1), con los
    radios `r1_km` y `rmax_km` (por defecto, los de `series` de planta.json); `caso` permite otra carpeta."""
    from teodors.fuentes import era5 as meteo, terreno
    emp = config.cargar_emplazamiento()
    info = terreno.ultimo_caso(emp["lat"], emp["lon"])
    if info is None:
        raise FileNotFoundError("No hay terreno descargado")
    Z, U, tr = terreno.cargar(info)
    r = rejilla(Z, U, tr)
    zona = geo.huso_utm(emp["lon"])

    d_era = meteo.dir_era5(emp["lat"], emp["lon"])
    punto = json.loads((d_era / "punto.json").read_text(encoding="utf-8"))
    ini_mes = pd.Timestamp(anio, mes, 1)
    fin = ini_mes + pd.offsets.MonthBegin(1)
    ini = ini_mes - pd.Timedelta(hours=arranque_h)
    anios = sorted({ini.year, anio})
    sfc = meteo.cargar_sfc(emp["lat"], emp["lon"], anios=anios)
    pfl = meteo.cargar_pfl(emp["lat"], emp["lon"], anios=anios)
    disp_s, disp_p = set(sfc.time), set(pfl.time)
    if not all(h in disp_s and h in disp_p for h in pd.date_range(ini, ini_mes, freq="h")):
        ini, arranque_h = ini_mes, 0                      # sin ERA5 previo: arranque en frío
    horas = list(pd.date_range(ini, fin, freq="h"))      # +1 h de cola (incluye la de fin)
    horas = [h for h in horas if h in disp_s and h in disp_p]
    nh = int((fin - ini) / pd.Timedelta(hours=1))
    if len(horas) < nh:
        raise ValueError(f"ERA5 incompleto para {anio}-{mes:02d}: {len(horas)} de {nh} h")

    caso = Path(caso) if caso else caso_dir(anio, mes)
    caso.mkdir(parents=True, exist_ok=True)
    g = escribir_geo(caso / "geo.dat", r, zona)
    lista, usadas = None, []
    if estaciones:
        r1_km = config.pide("series", "r1_km") if r1_km is None else r1_km
        rmax_km = config.pide("series", "rmax_km") if rmax_km is None else rmax_km
        from teodors.fuentes import meteocat as est
        todas = {e["codigo"]: e for e in est.cercanas(emp["lat"], emp["lon"])}
        alt = est.para_mapa(emp["lat"], emp["lon"])
        medidas, lista = [], []
        for k, cod in enumerate(estaciones, 1):
            e = todas[cod]
            h = next((s["altura_viento_m"] for s in alt if s["codigo"] == cod), 10.0) or 10.0
            x, y = geo.a_utm(e["lat"], e["lon"])
            ide = 100000 + k
            medidas.append((ide, obs_horarias(cod, anios)))
            lista.append((cod, ide, x / 1000, y / 1000, h))
            usadas.append({"codigo": cod, "id": ide, "dist_km": e["dist_m"] / 1000,
                           "anemometro_m": h})
        obs.escribir(caso / "estaciones.dat", medidas, horas, sfc, comentario=cabecera(COMENTARIO_OBS))
    m3d = pronostico.escribir_columna(caso / "pronostico3d.dat", pfl, sfc, r["ext"], punto, horas,
                                      config.EPSG_UTM, titulo=cabecera(TITULO_ERA5))
    nubes.escribir(caso / "nubes.dat", sfc, horas, g["nx"], g["ny"])
    isurft = 1 + min(range(len(usadas)), key=lambda i: usadas[i]["dist_km"]) if usadas else 1
    control.escribir(caso / "viento3d.inp", r, ini, nh, zona, config.VIENTO3D_ZFACE,
                     terrad_km=terrad_km, estaciones=lista, r1_km=r1_km, rmax_km=rmax_km,
                     isurft=isurft, extra=extra)
    res = {"anio": anio, "mes": mes, "horas": nh - arranque_h, "arranque_h": arranque_h,
           "ini_corrida": f"{ini:%Y-%m-%d %H:%M}", "nx": g["nx"], "ny": g["ny"],
           "celda_m": r["celda_m"], "ext": list(r["ext"]), "zona": zona,
           "categorias": g["categorias"], "sustituciones_975": m3d["sustituciones_975"],
           "terrad_km": terrad_km, "estaciones": usadas,
           "r1_km": r1_km if usadas else None, "rmax_km": rmax_km if usadas else None,
           "extra": extra or {}}
    (caso / "caso.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    log.info(f"viento3d {anio}-{mes:02d}: caso preparado ({g['nx']}×{g['ny']} × "
             f"{len(config.VIENTO3D_ZFACE) - 1} niveles, {nh} h, {arranque_h} h de arranque) "
             f"en {caso}")
    return caso


def ejecutar(caso):
    """Lanza `meteo.viento3d` de teOdors en el caso (bloqueante), con este mismo teOdors (`comun.procesos.entorno`).
    Devuelve (segundos, ruta de viento3d.dat)."""
    caso = Path(caso)
    env = procesos.entorno()
    t0 = time.time()
    with open(caso / "odora_run.log", "w", errors="replace") as fo:
        rc = subprocess.run(procesos.orden("teodors", "viento3d", "viento3d.inp"),
                            cwd=str(caso), stdout=fo, stderr=subprocess.STDOUT, env=env).returncode
    seg = time.time() - t0
    dat = caso / "viento3d.dat"
    if rc != 0 or not dat.exists() or dat.stat().st_size == 0:
        raise RuntimeError(f"teOdors viento3d falló (rc={rc}).\n"
                           + (caso / "odora_run.log").read_text(errors="replace")[-1200:])
    log.info(f"teOdors viento3d OK en {seg / 60:.1f} min · {dat.stat().st_size / 1e9:.2f} GB")
    return seg, dat


def recorte_de(caso):
    """(año, mes, horas, primera fecha) para almacen.comprimir(recorte=…), o None si el caso
    no tuvo horas de arranque."""
    info = json.loads((Path(caso) / "caso.json").read_text(encoding="utf-8"))
    if not info.get("arranque_h"):
        return None
    return salida.recorte(pd.Timestamp(info["anio"], info["mes"], 1), info["horas"])


# ── lectura del fichero de viento ────────────────────────────────────────────────────────
def leer(caso, niveles=(1,), campos2d=("TEMPK",), fichero="viento3d.dat"):
    """Campos horarios del fichero de viento 3D `fichero` del caso, con la lectura selectiva de
    teOdors (`fichero_viento.leer_campos`; la malla sale de caso.json). Devuelve un dict con
      horas   DatetimeIndex (hora FINAL de cada paso, UTC; coincide con el instante de ERA5)
      x, y    centros de celda (m, config.EPSG_UTM) · elev (ny, nx) · zface · dgrid
      u, v    {nivel: (n_horas, ny, nx)} m/s respecto a la CUADRÍCULA UTM (no al norte
              geográfico: para dirección geográfica restar geo.acimut_norte_en_rejilla)
      <campo> (n_horas, ny, nx) para cada nombre de campos2d (p. ej. TEMPK, ZI, IPGT)."""
    from teodors.meteo.viento3d.fichero_viento import leer_campos
    caso = Path(caso)
    info = json.loads((caso / "caso.json").read_text(encoding="utf-8"))
    nx, ny, dg = info["nx"], info["ny"], info["celda_m"]
    cab, d = leer_campos(caso / fichero, niveles=niveles, campos2d=campos2d)
    fechas = [pd.Timestamp(int(n) // 100000, 1, 1)
              + pd.Timedelta(days=(int(n) // 100) % 1000 - 1, hours=int(n) % 100) for n in d["ndathr"]]
    x0, y0 = info["ext"][0], info["ext"][2]
    out = {"horas": pd.DatetimeIndex(fechas), "elev": cab.elev, "zface": cab.zface, "dgrid": dg,
           "x": x0 + (np.arange(nx) + 0.5) * dg, "y": y0 + (np.arange(ny) + 0.5) * dg,
           "u": d["u"], "v": d["v"]}
    for c in campos2d:
        out[c] = d[c]
    return out


en_punto = salida.en_punto


def viento_en_punto(c, lat, lon, nivel=1):
    """Serie (ws, wd geográfica) del viento 3D `c` (de `leer`) en (lat, lon): time, ws, wd."""
    x, y = geo.a_utm(lat, lon)
    ws, wd = salida.viento_en_punto(c["u"][nivel], c["v"][nivel], c["x"], c["y"], x, y,
                                    geo.acimut_norte_en_rejilla(lat, lon))
    return pd.DataFrame({"time": c["horas"], "ws": ws, "wd": wd})


def extraer_puntos(caso):
    """Serie horaria del viento 3D (nivel 1, ≈ 10 m, y TEMPK) en la planta y en cada estación de
    Meteocat -> caso/puntos.csv (pocos kB: permite validar sin guardar el fichero de viento)."""
    from teodors.fuentes import meteocat as estaciones
    c = leer(caso, niveles=(1,), campos2d=("TEMPK",))
    emp = config.cargar_emplazamiento()
    puntos = [("PLANTA", emp["lat"], emp["lon"])] + [
        (e["codigo"], e["lat"], e["lon"]) for e in estaciones.cercanas(emp["lat"], emp["lon"])]
    tablas = []
    for cod, la, lo in puntos:
        x, y = geo.a_utm(la, lo)
        d = viento_en_punto(c, la, lo, 1)
        d["t"] = en_punto(c["TEMPK"], x, y, c["x"], c["y"]) - 273.15
        d["cota_celda_m"] = float(en_punto(c["elev"], x, y, c["x"], c["y"]))
        d.insert(1, "codigo", cod)
        tablas.append(d)
    out = pd.concat(tablas, ignore_index=True).round(3)
    info = json.loads((Path(caso) / "caso.json").read_text(encoding="utf-8"))
    out = out[out.time >= pd.Timestamp(info["anio"], info["mes"], 1)]   # sin el arranque
    out.to_csv(Path(caso) / "puntos.csv", index=False)
    return out


# ── disco y series mensuales ─────────────────────────────────────────────────────────────
DISCO_MIN_GB = 4.0          # el fichero de viento de un mes ocupa 2,7 GB mientras se calcula
GB_POR_MES = 4.0            # fichero de viento de un mes con arranque (2,8 GB) + nubes (1,1 GB)


def _reservado_gb():
    """Lo que aún les falta por escribir a los ficheros de viento EN MARCHA de cualquier cadena
    (ERA5, alta resolución, experimentos): uno existe solo mientras su mes se calcula."""
    total = 0.0
    for raiz, patron in ((config.DIR_TRABAJO, "**/viento3d.dat"), (config.DIR_VIENTO3D_ESTUDIOS, "*/viento3d.dat"),
                         (config.DIR_VIENTO3D_ESTUDIOS, "icon/*/viento3d.dat"),
                         (config.DIR_VIENTO3D_ESTUDIOS, "experimentos/*/viento3d.dat")):
        for f in raiz.glob(patron):
            try:
                total += max(0.0, GB_POR_MES - f.stat().st_size / 1e9)
            except OSError:
                pass
    return total


def _esperar_disco(anio, mes, minimo_gb=DISCO_MIN_GB):
    """No arranca un mes si no cabe su fichero de viento ADEMÁS de lo que les falta a los que ya
    están en marcha (de CUALQUIER tubería): espera. El 2026-10-18 el disco llegó a 3,8 GB libres
    porque solo se miraba el sitio del mes siguiente."""
    avisado = False
    config.DIR_TRABAJO.mkdir(parents=True, exist_ok=True)
    while (shutil.disk_usage(config.DIR_TRABAJO).free / 1e9
           < minimo_gb + GB_POR_MES + _reservado_gb()):
        if not avisado:
            log.warning(f"viento3d {anio}-{mes:02d}: menos de {minimo_gb:g} GB libres en el disco; "
                        f"se espera a que acaben otros meses")
            avisado = True
        time.sleep(60)


def dir_serie(nombre):
    """Carpeta de una serie de viento 3D. El reanálisis va a DATOS (NAS); el viento del EPISODIO (series «queja_…») es
    temporal y vive en tmp (`DIR_VIENTO3D_TMP`), hasta que se guarda a `casos/episodios/<fecha>/viento`."""
    base = config.DIR_VIENTO3D_TMP if str(nombre).startswith("queja_") else config.DIR_VIENTO3D
    return base / nombre


# ── leer una serie: del .cmz de DATOS si está (exacto) y, si no, del paquete de viento de la planta ─────────────
def paquete_viento():
    """Carpeta del paquete de viento de la planta (`meteo.viento3d.paquete`, junto a `entrada/`), o None si no hay."""
    from teodors.meteo.viento3d import paquete
    d = config.DIR_VIENTO_PAQUETE
    return d if paquete.es_paquete(d) else None


def _del_paquete(nombre):
    """El paquete de la planta si lleva la serie `nombre`; si no, None."""
    from teodors.meteo.viento3d import paquete
    p = paquete_viento()
    return p if p is not None and paquete.serie(p) == nombre else None


def _cmz(nombre, anio, mes):
    f = dir_serie(nombre) / "cmz" / f"{anio}{mes:02d}.cmz"
    return f if f.is_file() else None


def origen_mes(nombre, anio, mes):
    """El fichero del que se lee un mes de la serie (`campo_mes`): su .cmz de DATOS o, sin él, su .vz del paquete; None si no hay."""
    from teodors.meteo.viento3d import paquete
    f = _cmz(nombre, anio, mes)
    if f is not None:
        return f
    p = _del_paquete(nombre)
    return Path(p) / f"{anio}{mes:02d}.vz" if p is not None and (anio, mes) in paquete.meses(p) else None


def meses_serie(nombre):
    """[(año, mes)] con viento de la serie: los .cmz de DATOS y, si la planta lleva su paquete, los de él."""
    from teodors.meteo.viento3d import paquete
    d = dir_serie(nombre) / "cmz"
    m = {(int(f.stem[:4]), int(f.stem[4:])) for f in d.glob("??????.cmz")} if d.is_dir() else set()
    p = _del_paquete(nombre)
    if p is not None:
        m |= set(paquete.meses(p))
    return sorted(m)


def info_mes(nombre, anio, mes):
    """El caso.json de un mes de la serie (dict), de DATOS o del paquete; None si no hay."""
    from teodors.meteo.viento3d import paquete
    f = dir_serie(nombre) / f"{anio}{mes:02d}" / "caso.json"
    if f.is_file():
        return json.loads(f.read_text(encoding="utf-8"))
    p = _del_paquete(nombre)
    return paquete.caso(p, anio, mes) if p is not None and (anio, mes) in paquete.meses(p) else None


def _sin_viento(nombre, anio, mes):
    return FileNotFoundError(f"No hay viento de la serie {nombre} en {anio}-{mes:02d}: ni en "
                             f"{dir_serie(nombre) / 'cmz'} ni en el paquete de la planta ({config.DIR_VIENTO_PAQUETE})")


def campo_mes(nombre, anio, mes, etiqueta):
    """Una variable de un mes, como `almacen.leer_campo`: (fechas AAAAJJJHH, valores (horas, ny, nx))."""
    from teodors.meteo.viento3d import almacen, paquete
    f = _cmz(nombre, anio, mes)
    if f is not None:
        return almacen.leer_campo(f, etiqueta)
    p = _del_paquete(nombre)
    if p is None or (anio, mes) not in paquete.meses(p):
        raise _sin_viento(nombre, anio, mes)
    return paquete.leer_campo(p, anio, mes, etiqueta)


def descomprimir_mes(nombre, anio, mes, destino):
    """El fichero de viento de un mes en `destino`, del .cmz o del paquete. Devuelve su ruta."""
    from teodors.meteo.viento3d import almacen, paquete
    f = _cmz(nombre, anio, mes)
    if f is not None:
        return almacen.descomprimir(f, destino)
    p = _del_paquete(nombre)
    if p is None or (anio, mes) not in paquete.meses(p):
        raise _sin_viento(nombre, anio, mes)
    return paquete.descomprimir(p, anio, mes, destino)


def construir_paquete(nombre=None, destino=None, ajustes=None):
    """Paquete de viento de una serie de DATOS (por defecto, la del reanálisis, `series.era5`) en la carpeta de la planta
    (`DIR_VIENTO_PAQUETE`) o en `destino`: todos sus .cmz con su caso.json. Devuelve el índice."""
    from teodors.meteo.viento3d import paquete
    nombre = nombre or config.pide("series", "era5")
    d = dir_serie(nombre)
    cmzs = {(int(f.stem[:4]), int(f.stem[4:])): f for f in sorted((d / "cmz").glob("??????.cmz"))}
    if not cmzs:
        raise FileNotFoundError(f"La serie {nombre} no tiene meses en {d / 'cmz'}")
    casos = {m: d / f"{m[0]}{m[1]:02d}" / "caso.json" for m in cmzs}
    casos = {m: f for m, f in casos.items() if f.is_file()}
    return paquete.construir(cmzs, Path(destino or config.DIR_VIENTO_PAQUETE), nombre, casos=casos, ajustes=ajustes,
                             avisa=log.info)


def anadir_paquete(nombre=None, meses=None, destino=None):
    """Añade al paquete de viento de la planta (o al de `destino`) los meses de la serie que hay en DATOS y él no tiene, o los
    de `meses` ([(año, mes)]), que se rehacen si ya estaban; con los patrones del paquete (`paquete.anadir`). Para ir
    sumando meses (otro año) sin rehacerlo. Devuelve el índice, o None si no había nada que añadir."""
    from teodors.meteo.viento3d import paquete
    nombre = nombre or config.pide("series", "era5")
    destino = Path(destino or config.DIR_VIENTO_PAQUETE)
    if not paquete.es_paquete(destino):
        raise FileNotFoundError(f"No hay paquete de viento en {destino}: hacerlo antes con construir_paquete")
    if paquete.serie(destino) != nombre:
        raise ValueError(f"El paquete de {destino} es de la serie {paquete.serie(destino)}, no de {nombre}")
    d = dir_serie(nombre)
    hay = {(int(f.stem[:4]), int(f.stem[4:])): f for f in sorted((d / "cmz").glob("??????.cmz"))}
    quiero = sorted(m for m in hay if m not in set(paquete.meses(destino))) if meses is None else sorted(meses)
    faltan = [f"{a}-{m:02d}" for a, m in quiero if (a, m) not in hay]
    if faltan:
        raise FileNotFoundError(f"La serie {nombre} no tiene en {d / 'cmz'}: {', '.join(faltan)}")
    if not quiero:
        return None
    casos = {m: d / f"{m[0]}{m[1]:02d}" / "caso.json" for m in quiero}
    return paquete.anadir({m: hay[m] for m in quiero}, destino, casos={m: f for m, f in casos.items() if f.is_file()},
                          avisa=log.info)


def mes_serie(anio, mes, motor, nombre, estaciones=None, r1_km=None, rmax_km=None):
    """Un mes de una serie de viento 3D con `motor` (solo «teOdors»): prepara el caso en
    DIR_TRABAJO (ERA5 y, si se dan, estaciones como observaciones), lo calcula, extrae las
    series en la planta y las estaciones, comprime a DATOS/viento3d/<nombre>/cmz/AAAAMM.cmz (sin
    el arranque), conserva lo pequeño en DATOS/viento3d/<nombre>/AAAAMM y borra el caso."""
    from teodors.meteo.viento3d import almacen
    r1_km = config.bloque("series").get("r1_km") if r1_km is None else r1_km
    rmax_km = config.bloque("series").get("rmax_km") if rmax_km is None else rmax_km
    base = dir_serie(nombre)
    destino = base / "cmz" / f"{anio}{mes:02d}.cmz"
    if destino.exists():
        return {"anio": anio, "mes": mes, "ya_estaba": True}
    caso = config.DIR_TRABAJO / nombre / f"{anio}{mes:02d}"
    _esperar_disco(anio, mes)
    shutil.rmtree(caso, ignore_errors=True)
    preparar_mes(anio, mes, estaciones=estaciones, r1_km=r1_km, rmax_km=rmax_km, caso=caso)
    seg, dat = ejecutar(caso)
    extraer_puntos(caso)
    info = json.loads((caso / "caso.json").read_text(encoding="utf-8"))
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp")
    r = almacen.comprimir(dat, tmp, info["nx"], info["ny"], recorte=recorte_de(caso))
    tmp.replace(destino)
    res = {"anio": anio, "mes": mes, "motor": motor, "serie": nombre, "minutos": seg / 60,
           "estaciones": list(estaciones or []), "r1_km": r1_km, "rmax_km": rmax_km,
           "dat_mb": r["original_mb"], "cmz_mb": r["comprimido_mb"], "ratio": r["ratio"],
           "error_max": {k: v for k, v in r["errores"].items() if v > 0}}
    (caso / "resumen.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    conservar(caso, base / f"{anio}{mes:02d}")
    shutil.rmtree(caso, ignore_errors=True)
    log.info(f"{nombre} {anio}-{mes:02d}: {motor} {seg / 60:.0f} min · {r['comprimido_mb']:.0f} MB")
    return res
