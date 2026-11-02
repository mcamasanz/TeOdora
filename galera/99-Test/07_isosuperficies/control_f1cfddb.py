# -*- coding: utf-8 -*-
"""Control de teOdors puffs con VARIAS especies y fuentes de ÁREA, PUNTO y VOLUMEN, con un perfil de 24 h
por fuente y especie (IVARY = 1). Amplía `teodors.preparacion.puffs.control` (v0.1.2: una especie, solo
áreas, emisión constante) sin tocar teOdors; viene de 99-Test/01_superposicion y pasará a teOdors.

Fuentes (coordenadas en m del UTM del viento; emisiones por especie):
  área     {"id", "verts": [(x, y)…], "h": altura de emisión (m), "cota": m,
            "q": {especie: g/(s·m²) POR m²}, "perfil": {especie: 24 factores} o None}
  punto    {"id", "x", "y", "h": altura (m), "cota": m, "d": diámetro (m), "w": velocidad de salida
            (m/s), "t": temperatura de salida (K), "q": {especie: g/s}, "perfil": …}
  volumen  {"id", "x", "y", "h": altura efectiva (m), "cota": m, "sy0", "sz0": σ iniciales (m),
            "q": {especie: g/s}, "perfil": …}
Las unidades son las del motor (g). Como el modelo es lineal, sin química ni deposición, sirven emisiones
unidad que luego se multiplican por lo que emite el foco, también en ou_E/s.
"""
import galera  # noqa: F401  (pone lib/paquetes en el camino: «import teodors» es siempre el clon fijo)
from teodors.preparacion.puffs import control as base

TEMPORAL = "_TMP_"              # nombre provisional de la especie que luego se reparte


def _num(v):
    return "%.6E" % v


def _repartir_especies(c, especies):
    """Copia cada fila de especie de las tablas de partida (grupos 3a, 5, 7 y 10) y su CSPEC para
    cada especie de la lista, en orden."""
    i = 0
    while i < len(c.entradas):
        n, v, _ = c.entradas[i]
        if n == "CSPEC" and v == TEMPORAL:
            if c.entradas[i + 1][0] != "END":
                raise ValueError("se esperaba !END! tras CSPEC")
            bloque = []
            for e in especies:
                bloque += [["CSPEC", e, True], ["END", None, True]]
            c.entradas[i:i + 2] = bloque
            i += len(bloque)
        elif n == TEMPORAL:
            bloque = [[e, v, True] for e in especies]
            c.entradas[i:i + 1] = bloque
            i += len(bloque)
        else:
            i += 1


def _variacion(f, especies):
    """Entradas de un subgrupo 13d, 14d o 16c: IVARY = 1 y 24 factores por especie."""
    out = [("SRCNAM", f["id"]), ("IVARY", 1)]
    for e in especies:
        fac = f["perfil"].get(e, [1.0] * 24)
        if len(fac) != 24:
            raise ValueError("perfil de %s/%s sin 24 factores" % (f["id"], e))
        out.append((e, ", ".join("%.6g" % x for x in fac)))
    return out + [("END", None)]


def preparar(malla, zface, ini, nhoras, zona, especies, areas=(), puntos=(), volumenes=(), receptores=(),
             nombres=None, titulo="Respuestas de los focos (teOdors puffs)"):
    especies = [e.upper() for e in especies]
    c = base.preparar(malla, zface, ini, nhoras, zona, [], receptores, especie=TEMPORAL,
                      nombres=nombres, titulo=titulo)
    _repartir_especies(c, especies)
    var_p = [p for p in puntos if p.get("perfil")]
    var_a = [a for a in areas if a.get("perfil")]
    var_v = [v for v in volumenes if v.get("perfil")]
    for k, v in (("NSPEC", len(especies)), ("NSE", len(especies)), ("NPT1", len(puntos)),
                 ("NSPT1", len(var_p)), ("NAR1", len(areas)), ("NSAR1", len(var_a)),
                 ("NVL1", len(volumenes)), ("NSVL1", len(var_v))):
        c.poner(k, v)

    def emisiones(f):
        return ", ".join(_num(f["q"].get(e, 0.0)) for e in especies)
    # 13b (y 13d): justo antes del grupo 14, que empieza en NAR1
    b13 = []
    for p in puntos:
        b13 += [("SRCNAM", p["id"]),
                ("X", "%.4f, %.4f, %.1f, %.1f, %.3f, %.3f, %.2f, 0.0, %s" % (
                    p["x"] / 1000.0, p["y"] / 1000.0, p["h"], p["cota"], p["d"], p["w"], p["t"], emisiones(p))),
                ("END", None)]
    for p in var_p:
        b13 += _variacion(p, especies)
    c.insertar(c.indice("NAR1"), b13)
    # 14b, 14c y 14d
    b14, c14, d14 = [], [], []
    for a in areas:
        b14 += [("SRCNAM", a["id"]), ("X", "%.1f, %.1f, 0.0, %s" % (a["h"], a["cota"], emisiones(a))),
                ("END", None)]
        xs = ", ".join("%.4f" % (x / 1000.0) for x, _ in a["verts"])
        ys = ", ".join("%.4f" % (y / 1000.0) for _, y in a["verts"])
        c14 += [("SRCNAM", a["id"]), ("XVERT", xs), ("YVERT", ys), ("END", None)]
    for a in var_a:
        d14 += _variacion(a, especies)
    c.insertar(c.indice("_AREAS_X"), b14)
    c.insertar(c.indice("_AREAS_VERTICES"), c14)
    c.insertar(c.indice("NLN2"), d14)
    # 16b y 16c: justo antes del grupo 17, que empieza en NREC
    b16 = []
    for v in volumenes:
        b16 += [("SRCNAM", v["id"]),
                ("X", "%.4f, %.4f, %.1f, %.1f, %.3f, %.3f, %s" % (
                    v["x"] / 1000.0, v["y"] / 1000.0, v["h"], v["cota"], v["sy0"], v["sz0"], emisiones(v))),
                ("END", None)]
    for v in var_v:
        b16 += _variacion(v, especies)
    c.insertar(c.indice("NREC"), b16)
    return c


def escribir(ruta, *args, **kw):
    c = preparar(*args, **kw)
    c.escribir(ruta)
    return c
