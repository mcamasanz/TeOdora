# -*- coding: utf-8 -*-
"""Traducción de AERMAP v24142 (US EPA, dominio público): programa principal (aermap.f,
PROGRAM AERMAP).

Uso (mismos argumentos que el original):
    python -m teodors.terreno.relieve                      -> lee aermap.inp, escribe aermap.out
    python -m teodors.terreno.relieve caso.inp             -> escribe caso.out
    python -m teodors.terreno.relieve caso.inp salida.out
"""
import datetime
import sys
import time

from . import control, salida
from .colina import calchc
from .dominio import chkext, domcnv, puntos_cnv, puntos_dem
from .cotas import elevacion
from .estado import AbortoFortran, Estado, NoTraducido
from .mdt_externo import chkadj, cnrcnv, initer_ned, nedchk


def _fecha():
    t = datetime.datetime.now()
    return t.strftime("%m/%d/%y"), t.strftime("%H:%M:%S")


def _nombres(argv):
    if len(argv) == 0:
        return "aermap.inp", "aermap.out"
    if len(argv) == 1:
        c = argv[0]
        i = c.rfind(".")
        base = c[:i] if i > 0 else c
        return c, base.strip() + ".out"
    if len(argv) == 2:
        return argv[0], argv[1]
    raise SystemExit("usage: 0, 1, or 2 args")


def ejecutar(inpfil="aermap.inp", outfil="aermap.out", fecha=None):
    """Ejecuta AERMAP. Devuelve el Estado (con e.out, e.tmpmsg...)."""
    e = Estado(inpfil, outfil)
    lineas = control.leer_lineas(inpfil)
    control.preset(e, lineas)
    e.asignar()
    e.rundat, e.runtim = fecha or _fecha()
    w = e.out.append
    w(f"** AERMAP - VERSION 24142".ljust(71) + e.rundat)
    w("**".ljust(71) + e.runtim)
    w("")
    control.setup(e, lineas)
    if not e.fatal:
        if e.typdat.rstrip() == "DEM":
            raise NoTraducido("DATATYPE DEM (formato USGS «Blue Book»): no traducido; use GeoTIFF (NED)")
        nedchk(e)
        w("  ")
        w(" Finished Reading Input NED Data")
        w("  ")
        if e.nederr:
            w("  ")
            w(" Error Occurred in NEDCHK")
            w("  ")
        else:
            if not e.fatal and e.nada != 0 and e.l_neednadcon:
                raise NoTraducido("El ancla (NADA) y los ficheros tienen datum distinto "
                                  "(NAD27/NAD83): haría falta NADCON, que no se traduce")
            cnrcnv(e)
            chkadj(e)
            if e.gotdomflg:
                domcnv(e)
            puntos_cnv(e, fuentes=False)
            if e.numsrc > 0:
                puntos_cnv(e, fuentes=True)
            if e.gotdomflg:
                chkext(e)
            puntos_dem(e, fuentes=False)
            if e.numsrc > 0:
                puntos_dem(e, fuentes=True)
    e.terrst()
    if not e.run or e.fatal or e.iwrn > 0:
        e.header()
        e.out += ["", "", "  *** Message Summary For AERMAP Setup ***", ""]
        e.sumtbl()
    if e.fatal:
        e.out += ["", "    **************************************",
                  "    *** SETUP Finishes UN-successfully ***",
                  "    **************************************", ""]
    else:
        e.out += ["", " ***********************************",
                  " *** SETUP Finishes Successfully ***",
                  " ***********************************", ""]
    if not e.fatal and e.run:
        initer_ned(e)
        if not e.runerr:
            if e.numsrc > 0 and e.iostat[3] > 0 and e.extract:
                for isrc in range(1, e.numsrc + 1):
                    if e.extract and not e.runerr:
                        _punto(e, isrc, fuentes=True)
                salida.srcout(e)
            for irec in range(1, e.numrec + 1):
                if e.extract and not e.runerr:
                    _punto(e, irec, fuentes=False)
                if not e.runerr:
                    calchc(e, irec)
            if e.nrgap_in > 0:
                e.gapsfound_in = True
            salida.writer(e)
    e.header()
    salida.inpsum(e)
    e.header()
    e.out += ["", " *** Message Summary For AERMAP Execution ***", ""]
    e.terrst()
    e.sumtbl()
    if e.fatal:
        e.out += ["", "    ***************************************",
                  "    *** AERMAP Finishes UN-successfully ***",
                  "    ***************************************", ""]
    else:
        e.out += ["", "    ************************************",
                  "    *** AERMAP Finishes Successfully ***",
                  "    ************************************", ""]
    with open(outfil, "w", encoding="latin-1", newline="\r\n") as f:
        for l in e.out:
            f.write(l + "\n")
    return e


def _punto(e, i, fuentes):
    """Bucle sobre los ficheros de terreno de un receptor o fuente (programa principal):
    se queda con la primera cota no ausente, con la lógica de huecos del original."""
    m = "MAIN"
    tabla = e.isin if fuentes else e.irin
    filled = e.lsrc_filled if fuentes else e.lrec_filled
    destino = e.azs if fuentes else e.azelev
    ident = e.srcid[i] if fuentes else f"{i:8d}"
    c_subs, c_miss, c_gap2, c_gapin = (("425", "430", "422", "423") if fuentes
                                       else ("405", "410", "402", "403"))
    l_first = True
    e.gapsfound_in = False            # (sic) la bandera global se reutiliza por punto
    salida_ok = False
    idem = 0
    for idem in range(1, e.numdem + 1):
        t = tabla[i][idem]
        if t <= 0:
            continue
        elevacion(e, i, idem, fuentes)
        t = tabla[i][idem]
        if destino[i] > -9998.99:
            if l_first and t == 1:
                salida_ok = True
                break
            elif l_first and t == 2:
                salida_ok = True
                break
            elif t == 3:
                l_first = False
                if not e.gapsfound_in:
                    e.gapsfound_in = True
                    if fuentes:
                        e.nsgap_in += 1
                    else:
                        e.nrgap_in += 1
                continue
            elif not l_first and t in (1, 2):
                if fuentes:
                    e.nssubs += 1
                else:
                    e.nrsubs += 1
                e.errhdl(e.path, m, "W", c_subs, ident)
                salida_ok = True
                break
        else:
            l_first = False
            if t in (1, 3):
                if not e.gapsfound_in:
                    e.gapsfound_in = True
                    if fuentes:
                        e.nsgap_in += 1
                    else:
                        e.nrgap_in += 1
                continue
            elif t == 2:
                salida_ok = True
                break
    if e.numdem == 0:
        return
    if salida_ok:
        t = tabla[i][idem]
        if t == 1:
            if destino[i] < -9998.99:
                _ausente(e, fuentes, c_miss, ident)
        elif t in (2, 3):
            if destino[i] < -9998.99:
                _ausente(e, fuentes, c_miss, ident)
            elif filled[i][idem]:
                if fuentes:
                    e.nsfilled += 1
                else:
                    e.nrfilled += 1
                e.errhdl(e.path, m, "W", c_gap2 if t == 2 else c_gapin, ident)
    else:
        if destino[i] < -9998.99:
            _ausente(e, fuentes, c_miss, ident)
        else:
            if fuentes:
                e.nsfilled += 1
            else:
                e.nrfilled += 1
            e.errhdl(e.path, m, "W", c_gapin, ident)


def _ausente(e, fuentes, cod, ident):
    e.missfound = True
    if fuentes:
        e.nsmiss += 1
    else:
        e.nrmiss += 1
    e.errhdl(e.path, "MAIN", "W", cod, ident)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    inp, out = _nombres(argv)
    t0 = time.perf_counter()
    try:
        ejecutar(inp, out)
    except NoTraducido as ex:
        print(f"relieve: opción no traducida: {ex}", file=sys.stderr)
        return 2
    except AbortoFortran as ex:
        print(f"relieve: el original aborta aquí: {ex}", file=sys.stderr)
        return 3
    print(f"relieve terminado en {time.perf_counter() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
