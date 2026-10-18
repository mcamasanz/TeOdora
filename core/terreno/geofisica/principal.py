# -*- coding: utf-8 -*-
"""Programa principal: ``python -m odora.terreno.geofisica [fichero_de_control]``.

Lee el mismo fichero de control que el preprocesador original (grupos 0 a 4: ficheros, control,
proyección y malla, categorías de salida y tabla de propiedades por categoría de entrada) y
escribe el GEO.DAT, los GRD de control y un listado propio."""
import os
import sys
import time

import numpy as np

from . import calculo
from .control import Control

_NIMA = "02-21-2003"


class NoImplementado(Exception):
    pass


def _nombres(c):
    minus = c.logico("LCFILES", True)
    n = {}
    for var, defecto in (("LUDAT", "LU.DAT"), ("LU2DAT", "LU2.DAT"), ("TERRDAT", "TERR.DAT"),
                         ("GEODAT", "GEO.DAT"), ("RUNLST", "GEO.LST"), ("LUGRD", "QALUSE.GRD"),
                         ("TEGRD", "QATERR.GRD")):
        v = c.cadena(var, defecto)
        n[var] = v.lower() if minus else v.upper()
    return n


def _malla_control(c):
    pmap = c.cadena("PMAP", "UTM").upper()
    m = {"pmap": pmap, "nx": c.entero("NX"), "ny": c.entero("NY"), "xorg": c.real("XREFKM"),
         "yorg": c.real("YREFKM"), "dgx": c.real("DGRIDKM"), "dgy": c.real("DGRIDKM")}
    if pmap == "UTM":
        m["zona"] = ("%4d%s" % (c.entero("IUTMZN"), c.cadena("UTMHEM", "N").upper()[:1])).ljust(8)
    else:
        raise NoImplementado("proyección %s (de momento solo UTM)" % pmap)
    m["datum"] = c.cadena("DATUM", "WGS-84").upper().ljust(8) + _NIMA.ljust(12)
    return m


def _comprobar(m, otra, nombre):
    for k in ("nx", "ny"):
        if m[k] != otra[k]:
            raise calculo.ErrorGeo("%s: %s=%s no coincide con el control (%s)" % (nombre, k, otra[k], m[k]))
    for k in ("xorg", "yorg", "dgx"):
        if abs(m[k] - otra[k]) > 1e-3:
            raise calculo.ErrorGeo("%s: %s=%s no coincide con el control (%s)" % (nombre, k, otra[k], m[k]))


def ejecutar(argv=None, comentario=None):
    argv = sys.argv[1:] if argv is None else argv
    fich = argv[0] if argv else "geo.inp"
    t0 = time.time()
    c = Control(open(fich, encoding="latin-1").read())
    n = _nombres(c)
    if c.logico("LLU2", False):
        raise NoImplementado("segundo fichero de uso del suelo (LLU2)")
    if c.entero("NSPLIT", 0) > 0:
        raise NoImplementado("categorías divididas (NSPLIT)")
    m = _malla_control(c)
    tabla = calculo.Tabla(c)
    c._tabla = tabla
    log = ["%s %s (nivel %s) -- geofísica de la malla para CALMET" % (calculo.PROGRAMA, calculo.VERSION, calculo.NIVEL),
           "", "Fichero de control : " + fich, "Título             : " + c.titulo.strip(),
           "Uso del suelo      : " + n["LUDAT"]]
    lu_info, ncat, fr = calculo.leer_lu(n["LUDAT"])
    _comprobar(m, lu_info, n["LUDAT"])
    if c.logico("LTERR", True):
        te_info, z = calculo.leer_terr(n["TERRDAT"])
        _comprobar(m, te_info, n["TERRDAT"])
        log.append("Cotas              : " + n["TERRDAT"])
    else:
        z = np.zeros((m["ny"], m["nx"]))
        log.append("Cotas              : ninguna (0 m)")
    try:
        campos = calculo.calcular(c, tabla, fr)
    except calculo.ErrorGeo as err:
        log += ["", "FATAL -- " + str(err), "No se escribe el GEO.DAT"]
        _listado(n["RUNLST"], log, t0)
        return 1
    nmiss = int(campos["sin_dato"].sum())
    if not campos["imiss_valida"]:
        calculo.escribir_grd(n["LUGRD"], n["TEGRD"], m, campos, z)
        log += ["", "La categoría IMISS=%d no está entre las de entrada: solo se escriben los GRD de "
                "control (las celdas sin dato llevan %d)" % (c.entero("IMISS"), c.entero("IMISS")),
                "No se escribe el GEO.DAT"]
        _listado(n["RUNLST"], log, t0)
        return 1
    npar = int(campos["parcial"].sum())
    log += ["", "Malla %d x %d, celda %.3f km, origen (%.3f, %.3f) km" % (m["nx"], m["ny"], m["dgx"],
                                                                         m["xorg"], m["yorg"]),
            "Categorías de entrada: %d; de salida: %s" % (ncat, " ".join(str(v) for v in tabla.outcat)),
            "Celdas sin dato (suma <= 0.001), rellenas con IMISS=%d: %d" % (c.entero("IMISS", 55), nmiss)]
    calculo.escribir_grd(n["LUGRD"], n["TEGRD"], m, campos, z, vacios=bool(npar))
    if npar:
        log += ["FATAL -- %d celda(s) con cobertura entre 0.001 y FLUMIN=%.3f" % (npar, c.real("FLUMIN", 0.96)),
                "No se escribe el GEO.DAT"]
        _listado(n["RUNLST"], log, t0)
        return 1
    calculo.escribir_geo(n["GEODAT"], c, m, campos, z, comentario)
    usos, cuenta = np.unique(campos["lu"], return_counts=True)
    log += ["", "Uso dominante (categoría: celdas): " +
            ", ".join("%d: %d" % (u, k) for u, k in zip(usos, cuenta)),
            "GEO.DAT escrito: " + n["GEODAT"]]
    _listado(n["RUNLST"], log, t0)
    return 0


def _listado(ruta, log, t0):
    log += ["", "Tiempo: %.2f s" % (time.time() - t0)]
    with open(ruta, "w", encoding="utf-8", newline="\r\n") as fh:     # CRLF en cualquier sistema
        fh.write("\n".join(log) + "\n")


if __name__ == "__main__":
    sys.exit(ejecutar())
