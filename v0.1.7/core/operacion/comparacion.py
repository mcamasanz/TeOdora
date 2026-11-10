# -*- coding: utf-8 -*-
"""Comparar dos escenarios ya simulados del reanálisis (usuario, 2026-11-09: «en reanálisis hay dos modos, simular un escenario y otro que pueda
comparar dos escenarios, pero la comparación se hace desde escenarios ya simulados; la idea es comparar el porcentaje de más o de menos debido
a un escenario diferente»).

Sin volver a calcular: cada resultado guarda la media, el máximo y el P98 de cada receptor (`simulacion`, resumen.npz), y el cambio es

    cambio (%) = (comparado − referencia) / referencia × 100

receptor a receptor, en cada magnitud y estadístico. Donde los dos están por debajo del primer nivel de sus isolíneas (0,01 ou_E/m³ con el olor;
el comienzo de su escala con un gas) no se da: pasar de 0,0001 a 0,0003 es un +200 % que no dice nada. En el mapa, isolíneas del cambio con
dos colores (azul, baja; rojo, sube; entre ±10 %, sin color); de los pueblos, los dos valores y el cambio; y del olor, la superficie y los
pueblos por encima de 1, 3 y 5 ou_E/m³ de P98 en cada escenario.

Los dos tienen que ser de los mismos receptores y las mismas horas; si los focos o sus emisiones no son los mismos, se compara y se avisa.
"""
import datetime as dt
import json
import re
import shutil
from pathlib import Path

import numpy as np

from teodors import planta as config
from teodors.comun import registro
from teodors.operacion import penacho_mapa, serie_respuestas as SR, simulacion as S

log = registro.get("planes")

LIMITES = (-75.0, -50.0, -25.0, -10.0, 10.0, 25.0, 50.0, 75.0)        # % entre las franjas del cambio
# de lo que más baja a lo que más sube (azules y rojos de ColorBrewer RdBu); entre −10 y +10 %, sin color: «sin cambio apreciable»
COLORES = ("#2166ac", "#4393c3", "#92c5de", "#d1e5f0", None, "#fddbc7", "#f4a582", "#d6604d", "#b2182b")
CRITERIOS_OLOR = (1.0, 3.0, 5.0)                                         # ou_E/m³ de P98: superficie y pueblos por encima
ABIERTO = 1e9                                                            # los extremos de las franjas de los lados


def escenarios(otros=()):
    """Los escenarios del reanálisis ya simulados, para elegir: los de `resultados_planes/reanalisis`, los casos guardados (`simulacion.guardar_caso`,
    en `dir_guardados`) y los de `otros` (carpetas de «resultados» de casos de otro sitio), de la versión de ahora. [{"texto", "carpeta" (la del
    resultado.json), "nombre" (el del plan), "fecha", "caso" (el nombre del caso guardado, o None)}]: primero los simulados, la Base delante, y
    luego los casos, del más nuevo al más viejo."""
    rutas = [(r, False) for r in sorted((config.DATOS / "resultados_planes" / "reanalisis" / "5_anios").glob("*/resultado.json"))]
    rutas += [(r, True) for r in sorted(S.dir_guardados().glob("*/resultados/resultado.json"))]
    rutas += [(Path(c) / "resultado.json", True) for c in otros]
    salen, vistas = [], set()
    for ruta, es_caso in rutas:
        if ruta.parent.resolve() in vistas:
            continue
        vistas.add(ruta.parent.resolve())
        try:
            res = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if res.get("formato") != S.FORMATO_RESULTADO or res.get("periodo") is not None:
            continue
        nombre = res.get("nombre") or "Base"
        cuando = dt.datetime.strptime(res["fecha"], "%Y-%m-%d %H:%M")
        caso = ruta.parent.parent.name if es_caso and ruta.parent.name == "resultados" else (ruta.parent.name if es_caso else None)
        texto = f"{caso} · caso guardado" if caso else f"{nombre} · {cuando:%d/%m/%Y %H:%M}"
        salen.append({"texto": texto, "carpeta": str(ruta.parent), "nombre": nombre, "fecha": res["fecha"], "caso": caso})
    simulados = sorted((e for e in salen if not e["caso"]), key=lambda e: (e["nombre"] != "Base", e["nombre"].lower()))
    casos = sorted((e for e in salen if e["caso"]), key=lambda e: e["caso"], reverse=True)
    con_fecha = [e for e in casos if re.match(r"\d{4}-\d{2}-\d{2}-", e["caso"])]
    return simulados + con_fecha + [e for e in casos if e not in con_fecha]


def leer(carpeta):
    """El resultado de una carpeta de `escenarios`, con «carpeta»."""
    res = json.loads((Path(carpeta) / "resultado.json").read_text(encoding="utf-8"))
    S.pueblos_al_dia(res, Path(carpeta), None)                  # los pueblos de ahora, cada uno con el peor de sus receptores
    res["carpeta"] = str(carpeta)
    return res


def _campos(res, k):
    with np.load(Path(res["carpeta"]) / k / "resumen.npz") as z:
        return {n: z[n] for n in z.files}


def cambio(a, b, umbral):
    """El cambio en % de `a` (la referencia) a `b`; NaN donde los dos están por debajo de `umbral`. Si la referencia casi no llega y el otro sí,
    se divide por una décima del umbral: sale un aumento muy grande, que es lo que es."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    pct = (b - a) / np.maximum(a, umbral / 10.0) * 100.0
    return np.where(np.maximum(a, b) >= umbral, pct, np.nan)


def _centro():
    carpeta = S.dir_respuestas()
    if carpeta is not None:
        return SR.indice(carpeta)["centro"]
    from teodors.planta import geo
    emp = config.cargar_emplazamiento()
    return list(geo.a_utm(emp["lat"], emp["lon"]))


def _texto_dias(d):
    ini, fin = (dt.date.fromisoformat(d[k]) for k in ("ini", "fin"))
    return f"del {ini:%d/%m/%Y} al {fin:%d/%m/%Y} ({d['horas']} h)"


def _isolineas_cambio(a, b, rejillas, ruta, umbral):
    """Las isolíneas del cambio en `ruta`: cada escenario se lleva a la rejilla como sus isolíneas (en logaritmos) y el cambio sale punto a
    punto; sin pintar donde los dos están por debajo del umbral."""
    zs = []
    for r in rejillas:
        va, fuera = S.en_rejilla(a, r, umbral / 100.0)
        vb, _ = S.en_rejilla(b, r, umbral / 100.0)
        pct = cambio(va, vb, umbral)
        zs.append(np.ma.masked_array(np.nan_to_num(pct), mask=fuera | np.isnan(pct)))
    bordes = (-ABIERTO,) + LIMITES + (ABIERTO,)
    franjas = [(bordes[i], bordes[i + 1], {"tipo": "franja", "color": c, "desde": bordes[i] if i else None,
                                           "hasta": bordes[i + 1] if i + 1 < len(COLORES) else None})
               for i, c in enumerate(COLORES) if c is not None]
    lineas = [(v, {"tipo": "linea", "nivel": v}) for v in LIMITES]
    ruta.write_text(json.dumps(S.franjas_geojson(zs, rejillas, franjas, lineas), separators=(",", ":")), encoding="utf-8")


def _num(v):
    return f"{v:+.0f}".replace("-", "−")


def leyenda(m, titulo, umbral):
    """Leyenda del cambio: un cuadro por franja (el del medio, vacío: sin cambio apreciable) y los % en sus bordes."""
    cuadros = "".join(f"<span style='flex:1;height:12px;background:{c}'></span>" if c else
                      "<span style='flex:1;height:12px;border:1px solid var(--linea);box-sizing:border-box'></span>" for c in COLORES)
    bordes = ["−100"] + [_num(v) for v in LIMITES] + [""]
    return (f"<h4>{m['nombre']} · {titulo}: cambio (%)</h4>"
            f"<div style='display:flex;gap:1px'>{cuadros}</div>"
            "<div style='display:flex;justify-content:space-between;font-size:11px'>" + "".join(f"<span>{b}</span>" for b in bordes) + "</div>"
            f"<div style='font-size:10.5px;margin-top:2px'>Azul, baja; rojo, sube. Sin color: ±10 % o los dos por debajo de "
            f"{penacho_mapa._num(umbral)} {m['unidad']}</div>")


def _pueblos(ma, mb):
    """{nombre: fila} de los pueblos de cada resultado (`simulacion._tabla`, tipo «pueblo»)."""
    return ({f["nombre"]: f for f in ma["filas"] if f.get("tipo") == "pueblo"}, {f["nombre"]: f for f in mb["filas"] if f.get("tipo") == "pueblo"})


def _superficie(campo, rejillas, umbral):
    """km² por encima de `umbral`, en las rejillas de las imágenes (la cercana con detalle y la zona sin el hueco de la cercana)."""
    total = 0.0
    for r in rejillas:
        v, fuera = S.en_rejilla(campo, r, umbral / 100.0)
        total += np.count_nonzero((v > umbral) & ~fuera) * r["paso"] ** 2
    return total / 1e6


def comparar(ref, otro, progreso=None, salida=None):
    """Compara el escenario de la carpeta `otro` con el de `ref` (carpetas de `escenarios`). Deja las isolíneas del cambio en `salida` (por
    defecto, LOCAL/comparacion, la de la app; el informe de la comparación, en la suya, para no pisarla) y
    devuelve lo que necesita la interfaz: los dos escenarios, los avisos y, de cada magnitud que tienen los dos, sus capas, los pueblos y, del
    olor, los criterios."""
    avisa = progreso or (lambda *_: None)
    if Path(ref).resolve() == Path(otro).resolve():
        raise ValueError("Es el mismo escenario: elige otro para comparar.")
    A, B = leer(ref), leer(otro)
    na, nb = A.get("nombre") or "Base", B.get("nombre") or "Base"
    da, db = A.get("datos") or {}, B.get("datos") or {}
    if any(da.get(k) != db.get(k) for k in ("ini", "fin", "horas")):
        raise ValueError(f"No se pueden comparar: «{na}» es {_texto_dias(da)} y «{nb}», {_texto_dias(db)}. Tienen que ser de las mismas horas.")
    comunes = [k for k in A["orden"] if k in B["magnitudes"]]
    if not comunes:
        raise ValueError(f"«{na}» y «{nb}» no tienen ni el olor ni ningún gas en común.")
    xa, xb = _campos(A, comunes[0]), _campos(B, comunes[0])
    if xa["x"].shape != xb["x"].shape or not (np.allclose(xa["x"], xb["x"]) and np.allclose(xa["y"], xb["y"])):
        raise ValueError(f"No se pueden comparar: «{na}» y «{nb}» no son de los mismos receptores.")
    avisos = []
    if any(A["magnitudes"][k]["emisiones"] != B["magnitudes"][k]["emisiones"] for k in comunes):
        avisos.append("Los focos o sus emisiones no son los mismos en los dos: el cambio no es solo de la operación.")
    solo = [m["nombre"] for r in (A, B) for k, m in r["magnitudes"].items() if k not in comunes]
    if solo:
        avisos.append("Solo en uno de los dos, sin comparar: " + ", ".join(solo) + ".")
    salida = Path(salida) if salida else config.LOCAL / "comparacion"
    shutil.rmtree(salida, ignore_errors=True)
    salida.mkdir(parents=True, exist_ok=True)
    rejillas = S._rejillas(xa["x"], xa["y"], _centro())
    magnitudes, criterios = {}, None
    for j, k in enumerate(comunes):
        ma, mb = A["magnitudes"][k], B["magnitudes"][k]
        avisa(5 + 90 * j // len(comunes), f"{ma['nombre']}: el cambio en cada receptor…")
        ca, cb = (xa, xb) if j == 0 else (_campos(A, k), _campos(B, k))
        umbral = S.niveles_isolineas(ma["ref"], k)[0]
        cols = [c for c in ma["columnas"] if c["capa"] and c["clave"] in cb]
        capas = []
        for col in cols:
            ruta = salida / f"{k}_{col['clave']}.json"
            _isolineas_cambio(ca[col["clave"]], cb[col["clave"]], rejillas, ruta, umbral)
            capas.append({"id": f"comp_{col['capa']}", "clave": col["clave"], "nombre": col["nombre"], "titulo": col["titulo"],
                          "ruta": str(ruta), "leyenda": leyenda(ma, col["nombre"], umbral)})
        pa, pb = _pueblos(ma, mb)
        filas = []
        for nombre, fa in pa.items():
            fb = pb.get(nombre)
            if fb is None:
                continue
            fila = {"nombre": nombre, "km": fa["km"]}
            for col in cols:
                a, b = fa[col["clave"]], fb[col["clave"]]
                pct = float(cambio(a, b, umbral))
                fila[col["clave"]] = [a, b, None if np.isnan(pct) else pct]
            filas.append(fila)
        magnitudes[k] = {"clave": k, "nombre": ma["nombre"], "unidad": ma["unidad"], "umbral": umbral, "columnas": cols, "capas": capas,
                         "pueblos": filas}
        if k == "olor" and "p98" in ca and "p98" in cb:
            criterios = [{"umbral": u, "km2": [_superficie(ca["p98"], rejillas, u), _superficie(cb["p98"], rejillas, u)],
                          "pueblos": [sum(f["p98"] > u for f in pa.values()), sum(f["p98"] > u for f in pb.values())]}
                         for u in CRITERIOS_OLOR]
    avisa(100, "Hecho")
    log.info(f"Comparados «{nb}» con «{na}» (referencia): {len(comunes)} magnitudes.")
    return {"ref": {"nombre": na, "fecha": A["fecha"], "carpeta": str(ref)}, "otro": {"nombre": nb, "fecha": B["fecha"], "carpeta": str(otro)},
            "datos": da, "orden": comunes, "magnitudes": magnitudes, "criterios": criterios, "avisos": avisos}
