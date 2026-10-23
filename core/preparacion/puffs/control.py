# -*- coding: utf-8 -*-
"""Fichero de control de `dispersion.puffs` escrito desde cero (solo asignaciones, ver
`preparacion.control`) a partir de los parámetros de partida (`parametros.PARAMETROS`).

Configuración: UNA especie sin química ni deposición (MCHEM = MWET = MDRY = 0), fuentes de ÁREA con
emisión constante y receptores discretos, sobre el viento 3D de `meteo.viento3d`. La malla
horizontal y la vertical tienen que ser las del fichero de viento (si no, el motor aborta). Los
demás parámetros (dispersión, ajuste por relieve…) son los de partida; `extra` cambia cualquiera.
Viene del proyecto de La Galera (2026-10-23); la secuencia de asignaciones es la misma que la del
escritor que usaba allí, salvo los nombres de las salidas de deposición y visibilidad.
"""
from odora.preparacion.control import Control
from odora.preparacion.puffs.parametros import PARAMETROS

NOMBRES = {"viento": "viento3d.dat", "listado": "puffs.lst", "concentraciones": "conc.dat"}


def fuente_area(nombre, vertices, altura_m, cota_m, q):
    """Fuente de área para `preparar`: vértices [(x, y)] en m (UTM del viento), altura efectiva
    de emisión y cota del terreno (m), q en g/(s·m²) POR METRO CUADRADO."""
    return {"id": nombre, "verts_utm": list(vertices), "h": altura_m, "elev": cota_m, "q": q}


def _areas(fuentes):
    """Entradas de los subgrupos 14b (altura, cota, σz0 = 0, emisión) y 14c (vértices, km)."""
    b, c = [], []
    for s in fuentes:
        b += [("SRCNAM", s["id"]),
              ("X", "%.1f, %.1f, 0.0, %.6E" % (s["h"], s["elev"], s["q"])), ("END", None)]
        xs = ", ".join("%.4f" % (x / 1000.0) for x, _ in s["verts_utm"])
        ys = ", ".join("%.4f" % (y / 1000.0) for _, y in s["verts_utm"])
        c += [("SRCNAM", s["id"]), ("XVERT", xs), ("YVERT", ys), ("END", None)]
    return b, c


def preparar(malla, zface, ini, nhoras, zona, fuentes, receptores, especie="OLOR", hem="N",
             datum="WGS-84", extra=None, nombres=None, titulo="Caso de puffs (odora)"):
    """Control (`preparacion.control.Control`) de un caso.
      malla       {"nx", "ny", "celda_m", "ext": (xmin, xmax, ymin, ymax) en m}: la del viento
      zface       caras de las capas del viento (m sobre el suelo)
      ini, nhoras primera hora (con .year, .month, .day, .hour, en UTC) y número de horas
      zona        huso UTM
      fuentes     [fuente_area(...)] o dicts {id, verts_utm, h, elev, q}
      receptores  [(x, y, cota)] en m
      especie     nombre de la única especie (p. ej. OLOR)
      extra       {NOMBRE: valor} para cualquier otro parámetro
      nombres     ficheros del caso (por defecto NOMBRES)"""
    nom = dict(NOMBRES, **(nombres or {}))
    nx, ny = malla["nx"], malla["ny"]
    c = Control(PARAMETROS, titulo)
    for e in c.entradas:                                    # la especie del caso
        if e[0] == "_ESPECIE":
            e[0] = especie.upper()
        elif e[0] == "CSPEC" and e[1] == "_ESPECIE":
            e[1] = especie.upper()
    for k, v in (("METDAT", nom["viento"]), ("PUFLST", nom["listado"]),
                 ("CONDAT", nom["concentraciones"]), ("IBYR", ini.year), ("IBMO", ini.month),
                 ("IBDY", ini.day), ("IBHR", ini.hour), ("IRLG", nhoras),
                 ("XBTZ", "0.0"),                           # UTC, como el viento 3D
                 ("NSPEC", 1), ("NSE", 1), ("MCHEM", 0), ("MWET", 0), ("MDRY", 0),
                 ("DATUM", datum), ("IUTMZN", zona), ("UTMHEM", hem), ("NX", nx), ("NY", ny),
                 ("DGRIDKM", "%.4f" % (malla["celda_m"] / 1000)),
                 ("XORIGKM", "%.3f" % (malla["ext"][0] / 1000)),
                 ("YORIGKM", "%.3f" % (malla["ext"][2] / 1000)),
                 ("NZ", len(zface) - 1), ("ZFACE", ", ".join("%g." % z for z in zface)),
                 ("IBCOMP", 1), ("JBCOMP", 1), ("IECOMP", nx), ("JECOMP", ny), ("LSAMP", "F"),
                 ("IBSAMP", 1), ("JBSAMP", 1), ("IESAMP", nx), ("JESAMP", ny), ("ICON", 1),
                 ("NPT1", 0), ("NAR1", len(fuentes)), ("NSAR1", 0), ("NREC", len(receptores))):
        c.poner(k, v)
    b, v = _areas(fuentes)
    c.insertar(c.indice("_AREAS_X"), b)
    c.insertar(c.indice("_AREAS_VERTICES"), v)
    rec = []
    for x, y, z in receptores:
        rec += [("X", "%.4f, %.4f, %.1f, 0.0" % (x / 1000.0, y / 1000.0, z)), ("END", None)]
    c.insertar(c.indice("_RECEPTORES"), rec)
    for k, val in (extra or {}).items():
        c.poner(k, val)
    return c


def escribir(ruta, *args, **kw):
    """Escribe el control de `preparar(*args, **kw)` en `ruta`. Devuelve el Control."""
    c = preparar(*args, **kw)
    c.escribir(ruta)
    return c
