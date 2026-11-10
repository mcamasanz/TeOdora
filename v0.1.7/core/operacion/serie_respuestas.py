# -*- coding: utf-8 -*-
"""Las respuestas de los focos (`operacion.respuestas`) de todos los días de la serie del reanálisis, comprimidas, en la carpeta
`dispersion/` de la planta (`planta.DIR_DISPERSION`): es lo que lee `simulacion.calcular`. Unos 56 kB por foco y día de media: con 13
focos, 5 años en ~1,3 GB, frente a ~38 GB de los .npz de cada día.

    dispersion/
      indice.json        formato, serie, umbral, error, receptores (número, centro y los que tienen nombre) y, por foco, su huella
                         y sus días ({"AAAAMM": [días]})
      receptores.npz     x, y, cota y clase de cada receptor: los de todos los días
      <foco>/AAAAMM.rz   un ZIP sin comprimir; por día, «DD.m» (qué valores no son cero: un bit cada uno, lzma) y «DD.v» (esos valores)

Cada R[h, t, r] en s/m³ ((g/m³) por g/s): por debajo de UMBRAL vale cero; por encima, su logaritmo con un byte, con un error relativo
de ERROR como mucho. La escala de cada foco y día baja desde su máximo, que sale exacto: 254 pasos de logaritmo, 7,6 órdenes de
magnitud; lo que quede más abajo también va a cero (solo si el máximo pasa de ~0,4 s/m³, y aun así lo que no llega a 3·10⁻⁸ de él).
Con focos de hasta ~10⁵ ou_E/s, lo que se tira es ~0,001 ou_E/m³ por foco y hora. Con 15 días de una planta real, 13 focos y tres
planes, la media, el P98 y el máximo de cada receptor salen a un 0,5 % típico de los de las respuestas sin comprimir (3,5 % como mucho).

Añadir días (otro mes, otro año) o rehacer un foco que ha cambiado reescribe solo sus ficheros de esos meses:

    python -m teodors.operacion.serie_respuestas [--serie NOMBRE] [--origen CARPETA]

empaqueta en `dispersion/` todos los días de DATOS/respuestas/<serie>_AAAAMMDD/ (o de --origen). Un foco cuya huella ha cambiado
pierde los días que tenía: no valen.

Mientras no estén los focos de la planta, un banco de pruebas del tamaño de la serie de verdad: unas semanas simuladas (una por estación),
copiadas en todos los años (`repetir`; de prueba, y el índice lo dice).

    python -m teodors.operacion.serie_respuestas --repetir 2021-01-01 2025-12-31
"""
import argparse
import json
import lzma
import os
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

FORMATO = 1
UMBRAL = 1e-8                          # s/m³: por debajo, cero
ERROR = 0.035                          # relativo, como mucho, en lo que queda
_PASO = 2.0 * np.log1p(ERROR)          # paso del logaritmo: el error es la mitad
_RAMPA = np.exp(np.arange(-1, 255) * _PASO)    # código c (1…255) → exp((c − 1)·paso) por el valor del código 1
INDICE, RECEPTORES = "indice.json", "receptores.npz"


# ── formato de un día ──
def codificar(R):
    """R (h, t, r) → (bytes de la máscara, bytes de los valores): lo que se guarda de un foco en un día. Los valores llevan delante
    el logaritmo del código 1 (float64): el máximo del día cae justo en el código 255."""
    R = np.asarray(R, np.float32)
    techo = float(R.max()) if R.size else 0.0
    base = np.log(techo) - 254 * _PASO if techo >= UMBRAL else np.log(UMBRAL)
    m = R >= max(np.float32(UMBRAL), np.float32(np.exp(base) * (1 - 1e-6)))
    q = (1 + np.round((np.log(R[m].astype(np.float64)) - base) / _PASO)).clip(1, 255).astype(np.uint8)
    return (lzma.compress(np.packbits(m).tobytes(), preset=6),
            lzma.compress(np.float64(base).tobytes() + q.tobytes(), preset=6))


def decodificar(m, v, forma):
    """(máscara, valores, forma) → (índices planos de los no nulos en R[h, t, r], sus valores en float32): sin pasar por R entero."""
    n = int(np.prod(forma))
    idx = np.flatnonzero(np.unpackbits(np.frombuffer(lzma.decompress(m), np.uint8), count=n).view(bool))
    b = lzma.decompress(v)
    val = (np.exp(np.frombuffer(b[:8], np.float64)[0]) * _RAMPA[np.frombuffer(b, np.uint8, offset=8)]).astype(np.float32)
    if len(idx) != len(val):
        raise ValueError("respuesta dañada: la máscara y los valores no casan")
    return idx, val


def densa(m, v, forma):
    """R (h, t, r) entero, en float32 (para comprobar)."""
    idx, val = decodificar(m, v, forma)
    R = np.zeros(int(np.prod(forma)), np.float32)
    R[idx] = val
    return R.reshape(forma)


# ── la carpeta ──
def indice(carpeta):
    """El índice de la carpeta; None si no hay."""
    ruta = Path(carpeta) / INDICE
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else None


def receptores(carpeta):
    with np.load(Path(carpeta) / RECEPTORES) as z:
        return {k: z[k] for k in z.files}


def forma(ind):
    return (24, 24, int(ind["receptores"]))


def dias_foco(ind, foco):
    """Los días con respuesta de un foco, en orden (Timestamp a las 00)."""
    d = ind["focos"].get(foco, {}).get("dias", {})
    return [pd.Timestamp(int(m[:4]), int(m[4:]), x) for m in sorted(d) for x in sorted(d[m])]


def dias(ind, focos=None):
    """Los días en que hay respuesta de TODOS esos focos (de todos, si no se dan), en orden."""
    focos = list(ind["focos"]) if focos is None else list(focos)
    if not focos:
        return []
    comunes = set(dias_foco(ind, focos[0]))
    for f in focos[1:]:
        comunes &= set(dias_foco(ind, f))
    return sorted(comunes)


def _ruta_mes(carpeta, foco, anio, mes):
    return Path(carpeta) / foco / f"{anio:04d}{mes:02d}.rz"


def leer_mes(carpeta, foco, anio, mes):
    """{día del mes: (máscara, valores)} de un foco en un mes; {} si no hay."""
    ruta = _ruta_mes(carpeta, foco, anio, mes)
    if not ruta.is_file():
        return {}
    with zipfile.ZipFile(ruta) as z:
        nombres = set(z.namelist())
        return {int(n[:2]): (z.read(n), z.read(n[:2] + ".v")) for n in sorted(nombres) if n.endswith(".m")}


def leer_dia(carpeta, foco, dia):
    """(índices, valores) de un foco en un día (`decodificar`)."""
    d = pd.Timestamp(dia)
    ind = indice(carpeta)
    m, v = leer_mes(carpeta, foco, d.year, d.month)[d.day]
    return decodificar(m, v, forma(ind))


def _escribir_mes(ruta, contenido):
    """Reescribe el fichero de un mes de un foco con {día: (máscara, valores)}: primero a uno temporal, luego lo sustituye."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as z:
        for dia in sorted(contenido):
            m, v = contenido[dia]
            z.writestr(f"{dia:02d}.m", m)
            z.writestr(f"{dia:02d}.v", v)
    os.replace(tmp, ruta)


def _origenes(origen, serie):
    """Las carpetas de un día de la serie dentro de `origen` (DATOS/respuestas): <serie>_AAAAMMDD con meta.json de 1 día."""
    salen = []
    for d in sorted(Path(origen).glob(f"{serie}_" + "[0-9]" * 8)):
        meta = d / "meta.json"
        if meta.is_file():
            m = json.loads(meta.read_text(encoding="utf-8"))
            if m.get("dias", 1) == 1 and m.get("serie") == serie:
                salen.append((d, m))
    return salen


def importar(carpeta, origenes, huellas=None, avisa=None):
    """Añade a `carpeta` las respuestas de unos días: `origenes`, [(carpeta del día, su meta.json)] como las deja
    `operacion.respuestas`. Sustituye los días que ya estaban. `huellas`, {foco: huella} de focos.json: solo entra lo calculado con
    esa huella, y un foco que en la carpeta tiene otra pierde todos sus días; sin ellas, cada foco tiene que llegar con una sola.
    Devuelve el índice."""
    avisa = avisa or (lambda *_: None)
    carpeta = Path(carpeta)
    if not origenes:
        raise ValueError("no hay días que importar")
    objetivo = {}
    for d, meta in origenes:
        for foco, f in meta["focos"].items():
            if (d / f"R_{foco}.npz").is_file():
                objetivo.setdefault(foco, set()).add(f["huella"])
    for foco, hs in list(objetivo.items()):
        if huellas is not None:
            if foco in huellas:
                objetivo[foco] = huellas[foco]
            else:
                avisa(f"{foco}: no está en focos.json: no se importa")
                del objetivo[foco]
        elif len(hs) > 1:
            raise ValueError(f"{foco}: días calculados con huellas distintas; pasar `huellas` (las de focos.json)")
        else:
            objetivo[foco] = hs.pop()
    ind = indice(carpeta)
    serie = origenes[0][1]["serie"]
    if ind is None:
        ind = {"formato": FORMATO, "serie": serie, "umbral": UMBRAL, "error": ERROR, "receptores": origenes[0][1]["receptores"],
               "centro": origenes[0][1]["centro"], "etiquetas": origenes[0][1].get("etiquetas", []), "focos": {}}
        carpeta.mkdir(parents=True, exist_ok=True)
        with np.load(origenes[0][0] / RECEPTORES) as z:
            np.savez_compressed(carpeta / RECEPTORES, **{k: z[k] for k in z.files})
    if ind["formato"] != FORMATO or ind["umbral"] != UMBRAL or ind["error"] != ERROR:
        raise ValueError(f"{carpeta}: formato, umbral o error distintos de los de esta versión: hay que rehacerla entera")
    rec = receptores(carpeta)
    for foco, h in objetivo.items():
        actual = ind["focos"].get(foco)
        if actual is not None and actual["huella"] != h:
            avisa(f"{foco}: ha cambiado (otra huella): se quitan sus {sum(len(x) for x in actual['dias'].values())} días")
            for ruta in (carpeta / foco).glob("*.rz"):
                ruta.unlink()
            actual = None
        if actual is None:
            ind["focos"][foco] = {"huella": h, "dias": {}}
    pendientes, viejos = {}, 0                                    # (foco, año, mes) → {día: ruta del R}
    for d, meta in origenes:
        if meta["serie"] != ind["serie"]:
            raise ValueError(f"{d.name}: es de la serie {meta['serie']}, y la carpeta de {ind['serie']}")
        if meta["receptores"] != ind["receptores"]:
            raise ValueError(f"{d.name}: {meta['receptores']} receptores, y la carpeta tiene {ind['receptores']}: la malla ha cambiado")
        with np.load(d / RECEPTORES) as z:
            if not (np.allclose(z["x"], rec["x"], rtol=0, atol=0.05) and np.allclose(z["y"], rec["y"], rtol=0, atol=0.05)):
                raise ValueError(f"{d.name}: otros receptores que los de la carpeta: la malla ha cambiado")
        dia = pd.Timestamp(meta["dia"])
        for foco, f in meta["focos"].items():
            if foco not in objetivo or not (d / f"R_{foco}.npz").is_file():
                continue
            if f["huella"] != objetivo[foco]:
                viejos += 1
                continue
            pendientes.setdefault((foco, dia.year, dia.month), {})[dia.day] = d / f"R_{foco}.npz"
    if viejos:
        avisa(f"{viejos} respuestas de foco y día calculadas con otra versión del foco: no se importan")
    for k, (foco, anio, mes) in enumerate(sorted(pendientes)):
        contenido = leer_mes(carpeta, foco, anio, mes)
        for dia, ruta in pendientes[(foco, anio, mes)].items():
            with np.load(ruta) as z:
                R = z["R"]
            if R.shape != forma(ind):
                raise ValueError(f"{ruta}: R de forma {R.shape}, no {forma(ind)}")
            contenido[dia] = codificar(R)
        _escribir_mes(_ruta_mes(carpeta, foco, anio, mes), contenido)
        ind["focos"][foco]["dias"][f"{anio:04d}{mes:02d}"] = sorted(contenido)
        avisa(f"{foco} {anio:04d}-{mes:02d}: {len(contenido)} días ({k + 1} de {len(pendientes)})")
    for f in ind["focos"].values():
        f["dias"] = {m: f["dias"][m] for m in sorted(f["dias"])}
    (carpeta / INDICE).write_text(json.dumps(ind, ensure_ascii=False, indent=1), encoding="utf-8")
    return ind


def repetir(carpeta, desde, hasta, avisa=None):
    """Llena los días de `desde` a `hasta` que no tengan respuesta con COPIAS de los simulados: cada día, el del mismo día de la semana más
    cercano en el calendario, del año que sea (con una semana, todos los lunes son su lunes; con una por estación, el verano se llena con la
    de verano). Es un banco de pruebas (usuario, 2026-11-09): mientras no estén los focos de la planta, unas semanas simuladas con los que hay
    y repetidas en los 5 años, para tener datos de dispersión del tamaño de los de verdad con los que buscar cómo guardarlos en menos sitio y
    leerlos y calcular rápido; por eso se copian de verdad. OJO: un método que busque parecidos ENTRE días encontrará las copias; se mide con
    los días simulados. Hacen falta los 7 días de la semana con respuesta de todos los focos. Lo que ya estaba no se toca. El índice lo dice
    («repetida»: los días simulados y el periodo), y `comprobar` lo avisa (DIS-03), para que nadie los tome por la serie de verdad; para
    añadir otra semana, se rehace la carpeta entera. Devuelve el índice."""
    avisa = avisa or (lambda *_: None)
    carpeta = Path(carpeta)
    ind = indice(carpeta)
    if ind is None:
        raise ValueError(f"{carpeta}: no hay respuestas que repetir")
    rep = ind.get("repetida")
    origen = [pd.Timestamp(d) for d in rep["dias"]] if rep else dias(ind)       # otra vez: los simulados, no las copias
    if len({d.weekday() for d in origen}) < 7:
        raise ValueError(f"{carpeta}: hacen falta los 7 días de la semana con respuesta de todos los focos; hay "
                         f"{len({d.weekday() for d in origen})}")

    fechas = pd.date_range(pd.Timestamp(desde), pd.Timestamp(hasta), freq="D")
    meses = sorted({(d.year, d.month) for d in fechas})
    for k, foco in enumerate(ind["focos"]):
        cache = {}
        for anio, mes in meses:
            contenido = leer_mes(carpeta, foco, anio, mes)
            faltan = [d for d in fechas if (d.year, d.month) == (anio, mes) and d.day not in contenido]
            if not faltan:
                continue
            for d in faltan:
                o = dia_de_origen(d, origen)
                if (o.year, o.month) not in cache:
                    cache[(o.year, o.month)] = leer_mes(carpeta, foco, o.year, o.month)
                contenido[d.day] = cache[(o.year, o.month)][o.day]
            _escribir_mes(_ruta_mes(carpeta, foco, anio, mes), contenido)
            ind["focos"][foco]["dias"][f"{anio:04d}{mes:02d}"] = sorted(contenido)
        ind["focos"][foco]["dias"] = {m: ind["focos"][foco]["dias"][m] for m in sorted(ind["focos"][foco]["dias"])}
        avisa(f"{foco}: {len(fechas)} días de {fechas[0]:%Y-%m-%d} a {fechas[-1]:%Y-%m-%d} ({k + 1} de {len(ind['focos'])})")
    ind["repetida"] = {"dias": [f"{d:%Y-%m-%d}" for d in sorted(origen)], "desde": f"{fechas[0]:%Y-%m-%d}", "hasta": f"{fechas[-1]:%Y-%m-%d}"}
    (carpeta / INDICE).write_text(json.dumps(ind, ensure_ascii=False, indent=1), encoding="utf-8")
    return ind


def dia_de_origen(d, origen):
    """En una serie repetida (`repetir`), el día simulado (de `origen`) del que se copia `d`: el del mismo día de la semana más cercano en el
    calendario (con el año dando la vuelta); a igualdad, el primero."""
    d = pd.Timestamp(d)

    def lejos(o):
        k = abs(d.day_of_year - o.day_of_year)
        return min(k, 365 - k)
    return min((o for o in origen if o.weekday() == d.weekday()), key=lambda o: (lejos(o), o))


def semanas_repetidas(rep):
    """Los lunes de las semanas simuladas de una carpeta repetida (`repetir`), en orden."""
    return sorted({pd.Timestamp(d) - pd.Timedelta(days=pd.Timestamp(d).weekday()) for d in rep["dias"]})


def main(argv=None):
    from teodors import planta as config
    from teodors.comun import registro
    from teodors.operacion import focos as F
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serie", default=None, help="por defecto, series.era5 de planta.json")
    ap.add_argument("--origen", default=None, help="por defecto, DATOS/respuestas")
    ap.add_argument("--repetir", nargs=2, metavar=("DESDE", "HASTA"),
                    help="después, llena de DESDE a HASTA (AAAA-MM-DD) con la semana que hay, de prueba (`repetir`)")
    A = ap.parse_args(argv)
    registro.configurar(config.DIR_LOGS, config.REGISTRO)
    serie = A.serie or config.pide("series", "era5")
    origenes = _origenes(Path(A.origen) if A.origen else config.DATOS / "respuestas", serie)
    print(f"{len(origenes)} días de {serie} → {config.DIR_DISPERSION}", flush=True)
    huellas = {f["id"]: F.huella(f) for f in F.cargar()["focos"]}
    if origenes or not A.repetir:
        ind = importar(config.DIR_DISPERSION, origenes, huellas=huellas, avisa=lambda t: print(" ", t, flush=True))
    if A.repetir:
        ind = repetir(config.DIR_DISPERSION, *A.repetir, avisa=lambda t: print(" ", t, flush=True))
        print(f"  DE PRUEBA: {len(ind['repetida']['dias'])} días simulados (semanas del "
              f"{', '.join(f'{l:%Y-%m-%d}' for l in semanas_repetidas(ind['repetida']))}), repetidos", flush=True)
    d = dias(ind)
    tam = sum(f.stat().st_size for f in config.DIR_DISPERSION.rglob("*") if f.is_file())
    print(f"Hecho: {len(ind['focos'])} focos · días con todos: {len(d)}" + (f", {d[0]:%Y-%m-%d} a {d[-1]:%Y-%m-%d}" if d else "")
          + f" · {tam / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
