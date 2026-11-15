# -*- coding: utf-8 -*-
"""La meteo de los INFORMES, YA PROCESADA, con la planta (`planta.DIR_METEO_PLANTA`, junto a `entrada/`): lo que los informes sacan de la
meteo en bruto de los años del reanálisis, calculado UNA vez en el equipo que la tiene en su caché (`planta.DIR_METEO`), para que un equipo
sin ella (el del cliente) haga los informes completos. Ni un fichero meteorológico en bruto.

    python -m teodors.operacion.meteo_planta            (con TEODORS_PLANTA en la carpeta `entrada/` de la planta)

De los años del reanálisis (`reanalisis.anios` de planta.json) escribe:
  · estaciones.json           las estaciones de la zona: las de su inventario a menos del radio de la planta (`fuentes.meteocat`)
  · rosas_estaciones.json     la rosa de cada estación y la del ERA5 en las mismas horas (`metricas.viento.rosas_estaciones`)
  · tiempo_planta.json        el tiempo en la planta: la media de cada día de cada variable (con su mínimo y su máximo, la temperatura y la
                              capa de mezcla), su resumen y el calor sensible y la capa de mezcla hora a hora (`writer.datos.tiempo_planta`)
  · normales_estaciones.json  lo normal de cada fecha y hora en las estaciones: el valor de cada año y su mínimo, mediana, máximo y media; de
                              la dirección, la nube de cada año (`writer.datos.normales_estaciones`)
  · indice.json y LEEME.md    qué hay y de qué años, con su tamaño y su huella; y el mínimo, la media y el máximo de cada variable
Cada producto lleva su lista `de`: los ficheros en bruto de los que sale, relativos a la caché. Donde están todos, se calcula de ellos como
siempre; donde no, se lee el producto (`planta.meteo_procesada`).

NINGÚN fichero de la planta lleva la ruta de la carpeta de DATOS: el equipo del cliente no la conoce ni la necesita. Si alguno la llevara, no
se escribe nada. Nada se descarga: si falta algo en la caché, no se hace. Se rehace entera, en una carpeta aparte que solo sustituye a la
anterior si todo ha ido bien.
"""
import datetime as dt
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np

from teodors import __version__
from teodors import planta as config

FORMATO = 1
ESTACIONES = "estaciones.json"
PRODUCTOS = ("estaciones.json", "rosas_estaciones.json", "tiempo_planta.json", "normales_estaciones.json")


def faltan(emp=None):
    """Lo que falta en la caché para hacerla (relativo a la caché; vacío si está todo): el inventario de las estaciones, los meses del ERA5
    de la planta y su serie, las medidas de alguna estación cercana y el viento en la planta (su serie)."""
    from teodors.fuentes import era5 as E5
    from teodors.fuentes import meteocat as M
    from teodors.operacion import viento_mapa as VM
    emp = emp or config.cargar_emplazamiento()
    anios = [int(a) for a in config.REANALISIS_ANIOS]
    celda = E5.dir_era5(emp["lat"], emp["lon"])
    salen = [f"meteocat/{ESTACIONES}"] if not (M.dir_meteocat() / ESTACIONES).is_file() else []
    salen += [f"era5/{celda.name}/sfc_{a}{m:02d}.csv" for a in anios for m in range(1, 13) if not (celda / f"sfc_{a}{m:02d}.csv").is_file()]
    if not (celda / f"serie_sfc_{anios[0]}_{anios[-1]}.csv").is_file():
        salen.append(f"era5/{celda.name}/serie_sfc_{anios[0]}_{anios[-1]}.csv")
    if not salen:
        cercanas = M.cercanas(emp["lat"], emp["lon"])
        if not any((M.dir_meteocat() / e["codigo"] / f"{a}.csv").is_file() for e in cercanas for a in anios):
            salen.append("meteocat/<código>/<año>.csv (ninguna estación cercana)")
    if VM.serie_disponible() is None:
        salen.append("el viento en la planta (ninguna serie del viento 3D)")
    return salen


def viento_en_la_planta():
    """La serie del viento en la planta con la que se hace el tiempo en la planta: (serie, horas, ws, wd), todas sus horas en orden (como
    las junta `writer.datos._meteo` para el informe del reanálisis)."""
    from teodors.operacion import viento_mapa as VM
    serie = VM.serie_disponible()
    datos = VM.serie_planta(serie)
    horas, ws, wd = [], [], []
    for k in sorted(datos):
        horas += datos[k]["horas"]
        ws += datos[k]["ws"]
        wd += datos[k]["wd"]
    return serie, horas, ws, wd


def estaciones_zona(emp):
    """Las estaciones de la zona tal como las da su inventario (`fuentes.meteocat.inventario`, en su formato): a menos del radio de la planta, estén
    o no operativas (así `fuentes.meteocat.cercanas` da en el equipo del cliente las mismas que aquí)."""
    from teodors.fuentes import meteocat as M
    codigos = {e["codigo"] for e in M.cercanas(emp["lat"], emp["lon"], solo_operativas=False)}
    return [e for e in M.inventario() if e.get("codi_estacio") in codigos]


def productos(emp=None):
    """Los productos de la meteo procesada, {nombre: contenido}, calculados de la caché (nada se descarga: antes, `faltan`)."""
    from teodors.metricas import viento as V
    from teodors.writer import datos as W
    emp = emp or config.cargar_emplazamiento()
    anios = [int(a) for a in config.REANALISIS_ANIOS]
    rosas = V.rosas_estaciones(emp["lat"], emp["lon"], anios, procesada=False)
    rosas = dict(rosas, de=W._de(V.ficheros_rosas(emp["lat"], emp["lon"], anios)))
    serie, horas, ws, wd = viento_en_la_planta()
    tiempo = W.tiempo_planta(emp, horas, ws, wd)
    if tiempo is None:
        raise ValueError("sin el tiempo en la planta (el ERA5 de la caché no se ha podido leer)")
    tiempo["viento"]["serie"] = serie
    normales = W.normales_estaciones(emp)
    if normales is None:
        raise ValueError("sin lo normal de las estaciones (ninguna estación cercana con medidas)")
    return {ESTACIONES: estaciones_zona(emp), "rosas_estaciones.json": rosas, "tiempo_planta.json": tiempo,
            "normales_estaciones.json": normales}


def _huella(f):
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        for trozo in iter(lambda: fh.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def rutas_de_datos():
    """Cómo puede aparecer la carpeta de DATOS escrita dentro de un fichero (con «\\», con «/», escapada en JSON; también la ruta resuelta,
    que en una unidad de red puede ser la del servidor), en minúsculas."""
    formas = {str(config.DATOS)}
    try:
        formas.add(str(config.DATOS.resolve()))
    except OSError:
        pass
    salen = set()
    for f in formas:
        salen |= {f, f.replace("\\", "/"), f.replace("\\", "\\\\")}
    return {s.lower() for s in salen if len(s) > 3}


def lleva_ruta(fichero, rutas):
    """¿El fichero lleva escrita la carpeta de DATOS?"""
    texto = Path(fichero).read_bytes().decode("utf-8", errors="replace").lower()
    return any(r in texto for r in rutas)


def resumen_variables(tiempo):
    """De cada variable del tiempo en la planta, en los años del reanálisis: [(título, unidad, mínimo, media, máximo)], de sus valores de
    cada día (el mínimo y el máximo, de los de cada hora si los guarda: la temperatura y la capa de mezcla). Sin la dirección."""
    from teodors.writer.reanalisis_caso.paginas import GRAFICAS
    series = tiempo["era5"]["series"]
    salen = []
    for clave, titulo, unidad, forma, _ in GRAFICAS:
        s = series.get(clave)
        if not s or forma == "rumbos":
            continue
        v = np.asarray(s["v"], float)
        lo, hi = np.asarray(s.get("min", s["v"]), float), np.asarray(s.get("max", s["v"]), float)
        if not np.isfinite(v).any():
            continue
        salen.append((titulo, unidad or "", float(np.nanmin(lo)), float(np.nanmean(v)), float(np.nanmax(hi))))
    return salen


def _num(x, d=1):
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def _mb(ind):
    return _num(sum(f["bytes"] for f in ind["ficheros"].values()) / 1e6) + " MB"


def _leeme(ind, tiempo):
    from teodors.fuentes import era5 as E5
    from teodors.fuentes import meteocat as M
    filas = ""
    for t, u, a, m, b in resumen_variables(tiempo):
        d = 2 if max(abs(a), abs(b)) < 10 else 1 if max(abs(a), abs(b)) < 1000 else 0
        filas += f"| {t} | {u} | {_num(a, d)} | {_num(m, d)} | {_num(b, d)} |\n"
    return (
        "# Meteo de la planta, ya procesada: la que piden los informes\n\n"
        "La hace `python -m teodors.operacion.meteo_planta` con la meteo en bruto de la caché, en el equipo que la tiene. Con ella, un equipo\n"
        "sin esa meteo en bruto (el del cliente) hace los informes completos: el tiempo en la planta, las rosas de las estaciones y la meteo\n"
        "de un episodio frente a lo normal de esas fechas. **No hay ningún fichero meteorológico en bruto**: solo lo ya calculado. Es de solo\n"
        "lectura y no se edita a mano: se rehace con la misma orden.\n\n"
        f"- Años: {ind['anios'][0]}-{ind['anios'][-1]} · estaciones: {', '.join(ind['estaciones'])} · viento en la planta: {ind['serie_viento']}\n"
        f"- {len(ind['ficheros'])} ficheros, {_mb(ind)}: su tamaño y su huella, en `indice.json`\n"
        f"- Hecha el {ind['creado'].replace('T', ' a las ')} con teOdors {ind['teodors']}\n\n"
        "| Fichero | Qué hay |\n|---|---|\n"
        "| `estaciones.json` | las estaciones de la zona (de su inventario) |\n"
        "| `rosas_estaciones.json` | la rosa de los vientos de cada estación y la del ERA5 en las mismas horas |\n"
        "| `tiempo_planta.json` | la media de cada día de cada variable en la planta (la temperatura y la capa de mezcla, también su mínimo y "
        "su máximo), su resumen y, hora a hora, el calor sensible y la capa de mezcla |\n"
        "| `normales_estaciones.json` | lo normal de cada fecha y hora en las estaciones: el valor de cada año y su mínimo, su mediana, su "
        "máximo y su media; de la dirección, los valores de cada año |\n\n"
        f"## Cada variable en la planta, {ind['anios'][0]}-{ind['anios'][-1]}\n\n"
        "De sus valores de cada día; el mínimo y el máximo de la temperatura y de la capa de mezcla, de los de cada hora.\n\n"
        "| Variable | Unidad | Mínimo | Media | Máximo |\n|---|---|---|---|---|\n" + filas + "\n"
        f"Fuentes: {E5.FUENTE} y {M.FUENTE}, procesados con teOdors. Cada dato conserva las condiciones de uso de su proveedor.\n")


def construir(destino=None):
    """Escribe en `destino` (por defecto, la meteo de la planta) los productos de la meteo procesada y devuelve su índice. Si falta algo en
    la caché o algún fichero lleva la ruta de DATOS, no toca la carpeta que hubiera."""
    destino = Path(destino or config.DIR_METEO_PLANTA)
    emp = config.cargar_emplazamiento()
    falta = faltan(emp)
    if falta:
        raise FileNotFoundError("falta en la caché (descárgalo antes; la meteo de la planta no se ha tocado): " + ", ".join(falta[:8])
                                + (f" y {len(falta) - 8} más" if len(falta) > 8 else ""))
    hechos = productos(emp)
    rutas = rutas_de_datos()
    parcial = destino.with_name(destino.name + ".parcial")
    shutil.rmtree(parcial, ignore_errors=True)
    try:
        parcial.mkdir(parents=True)
        ficheros = {}
        for nombre, contenido in hechos.items():
            f = parcial / nombre
            f.write_text(json.dumps(contenido, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            ficheros[nombre] = {"bytes": f.stat().st_size, "sha256": _huella(f)}
        tiempo = hechos["tiempo_planta.json"]
        ind = {"formato": FORMATO, "teodors": __version__, "creado": dt.datetime.now().isoformat(timespec="minutes"),
               "anios": [int(a) for a in config.REANALISIS_ANIOS], "estaciones": sorted(hechos["normales_estaciones.json"]["convencion"]),
               "serie_viento": tiempo["viento"]["serie"], "ficheros": ficheros}
        (parcial / "indice.json").write_text(json.dumps(ind, ensure_ascii=False, indent=1), encoding="utf-8")
        (parcial / "LEEME.md").write_text(_leeme(ind, tiempo), encoding="utf-8")
        for f in parcial.iterdir():
            if lleva_ruta(f, rutas):
                raise ValueError(f"{f.name} lleva la ruta de la carpeta de DATOS: no se escribe nada en la planta")
    except BaseException:
        shutil.rmtree(parcial, ignore_errors=True)
        raise
    anterior = destino.with_name(destino.name + ".anterior")
    shutil.rmtree(anterior, ignore_errors=True)
    if destino.exists():
        destino.rename(anterior)
    parcial.rename(destino)
    shutil.rmtree(anterior, ignore_errors=True)
    return ind


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="python -m teodors.operacion.meteo_planta",
                                description="Escribe en la planta la meteo de los informes, ya procesada (de la caché; una vez).")
    p.add_argument("--destino", help="otra carpeta (por defecto, la meteo de la planta, junto a entrada/)")
    a = p.parse_args(argv)
    try:
        ind = construir(a.destino)
    except (FileNotFoundError, ValueError) as e:
        print(f"No se ha hecho: {e}", file=sys.stderr)
        return 1
    print(f"Meteo de la planta: {len(ind['ficheros'])} ficheros, {_mb(ind)} · años {ind['anios'][0]}-{ind['anios'][-1]} · "
          f"{len(ind['estaciones'])} estaciones · viento de {ind['serie_viento']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
