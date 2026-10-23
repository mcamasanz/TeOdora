# -*- coding: utf-8 -*-
"""Fichero de control de `meteo.viento3d` escrito desde cero (solo asignaciones, ver
`preparacion.control`) a partir de los parámetros de partida (`parametros.PARAMETROS`).

Configuración: campo inicial del pronóstico 3D (IPROG = 14, IWFCOD = 1), nubes del fichero de nubes
(ICLOUD = 2), sin sondeos, boyas ni pluviómetros, y dos modos:
  · sin estaciones (NOOBS = 2): solo el pronóstico; temperatura del pronóstico (ITPROG = 2);
  · con estaciones (NOOBS = 1): viento y temperatura de superficie de las estaciones (ITPROG = 1),
    radios R1/R2 y RMAX1/RMAX2, extrapolación en altura por semejanza (IEXTRP = −4) y sin
    interpolación aparte sobre el agua (JWAT1 = JWAT2 = 999: sin estaciones sobre el mar, las
    celdas de agua se quedaban sin sitios válidos para la temperatura y el cálculo se paraba).
Viene del proyecto de La Galera (2026-10-23); la secuencia de asignaciones es la misma que la del
escritor que usaba allí, comprobado caso a caso.
"""
from odora.preparacion.control import Control
from odora.preparacion.viento3d.parametros import PARAMETROS

NOMBRES = {"geo": "geo.dat", "estaciones": "estaciones.dat", "listado": "viento3d.lst",
           "viento": "viento3d.dat", "nubes": "nubes.dat", "pronostico": "pronostico3d.dat"}


def registro_estacion(k, nombre, ide, x_km, y_km, altura_m):
    """Valor del registro SSk de una estación de superficie (columnas fijas)."""
    return "'%-4.4s' %8d %12.3f %12.3f    0 %5.1f" % (nombre, ide, x_km, y_km, altura_m)


def preparar(malla, ini, nhoras, zona, zface, terrad_km=5.0, hem="N", datum="WGS-84",
             estaciones=None, r1_km=5.0, rmax_km=30.0, isurft=1, extra=None, nombres=None,
             titulo="Caso de viento 3D (odora)"):
    """Control (`preparacion.control.Control`) de un caso.
      malla       {"nx", "ny", "celda_m", "ext": (xmin, xmax, ymin, ymax) en m}
      ini, nhoras primera hora (con .year, .month, .day, .hour) y número de horas
      zona        huso UTM; zface: caras de las capas (m sobre el suelo)
      estaciones  [(nombre, id, x_km, y_km, altura_anemómetro_m)] o None
      isurft      estación (desde 1) cuya temperatura se usa en superficie
      extra       {NOMBRE: valor} para cualquier otro parámetro
      nombres     ficheros del caso (por defecto NOMBRES)"""
    nom = dict(NOMBRES, **(nombres or {}))
    nz = len(zface) - 1
    c = Control(PARAMETROS, titulo)
    c.poner("GEODAT", nom["geo"])
    if estaciones:
        c.poner("SRFDAT", nom["estaciones"])
    else:
        c.apagar("SRFDAT")
    c.poner("METLST", nom["listado"])
    c.poner("METDAT", nom["viento"])
    for k, v in (("NUSTA", 0), ("NOWSTA", 0), ("NM3D", 1), ("NIGF", 0)):
        c.poner(k, v)
    c.poner("M3DDAT", nom["pronostico"])
    for k, v in (("IBYR", ini.year), ("IBMO", ini.month), ("IBDY", ini.day), ("IBHR", ini.hour),
                 ("IBTZ", 0), ("IRLG", nhoras), ("DATUM", datum), ("IUTMZN", zona),
                 ("UTMHEM", hem), ("NX", malla["nx"]), ("NY", malla["ny"]),
                 ("DGRIDKM", "%.4f" % (malla["celda_m"] / 1000)),
                 ("XORIGKM", "%.3f" % (malla["ext"][0] / 1000)),
                 ("YORIGKM", "%.3f" % (malla["ext"][2] / 1000))):
        c.poner(k, v)
    # rejilla vertical: NZ y TODOS los vectores de NZ valores
    c.poner("NZ", nz)
    c.poner("ZFACE", ", ".join("%g." % z for z in zface))
    for k, v in (("IUVOUT", "0"), ("IWOUT", "0"), ("ITOUT", "0"), ("BIAS", "0"), ("NINTR2", "99"),
                 ("FEXTR2", "0.")):
        c.poner(k, ", ".join([v] * nz))
    c.poner("NSMTH", ", ".join(["2"] + ["4"] * (nz - 1)))
    c.poner("KBAR", nz)
    c.poner("TERRAD", "%g" % terrad_km)
    if estaciones:
        c.poner("NOOBS", 1)
        c.poner("NSSTA", len(estaciones))
        c.poner("IFORMS", 2)
        c.insertar(c.indice("_ESTACIONES"),
                   [("SS%d" % k, registro_estacion(k, *e)) for k, e in enumerate(estaciones, 1)])
        c.poner("ISURFT", isurft)
        for k in ("R1", "R2"):
            c.poner(k, "%g" % r1_km)
        for k in ("RMAX1", "RMAX2"):
            c.poner(k, "%g" % rmax_km)
        c.poner("IEXTRP", -4)
        c.poner("RMIN2", -1.0)
        c.poner("JWAT1", 999)
        c.poner("JWAT2", 999)
    else:
        c.poner("NOOBS", 2)
        c.poner("NSSTA", 0)
    c.poner("NPSTA", -1)
    c.poner("ICLOUD", 2)
    c.poner("CLDDAT", nom["nubes"])
    c.poner("IPROG", 14)
    c.poner("IWFCOD", 1)
    c.poner("ITPROG", 1 if estaciones else 2)
    for k, v in (extra or {}).items():
        c.poner(k, v)
    return c


def escribir(ruta, *args, **kw):
    """Escribe el control de `preparar(*args, **kw)` en `ruta`. Devuelve el Control."""
    c = preparar(*args, **kw)
    c.escribir(ruta)
    return c
