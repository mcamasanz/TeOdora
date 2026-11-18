# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): programa principal (aermod.f, PROGRAM
AERMOD y FILOPN).

Mismos argumentos que el original: ninguno (aermod.inp -> aermod.out), uno (entrada; la salida
toma su nombre con .out) o dos (entrada y salida)."""
import sys

from . import control
from .estado import Estado, NoTraducido, Parada
from .formato import fwrite

__all__ = ["ejecutar"]


def _nombres(argv):
    if len(argv) == 0:
        return "aermod.inp", "aermod.out"
    if len(argv) == 1:
        c = argv[0]
        outfil = c
        for i1 in range(len(c), 0, -1):
            if c[i1 - 1] == "." and i1 != 1:
                outfil = c[:i1 - 1]
                break
        return c, outfil.strip() + ".out"
    if len(argv) == 2:
        return argv[0], argv[1]
    return None, None


def _uso(e):
    from .formato import lw
    e.pantalla.w([lw("usage: 0, 1, or 2 args"), lw(""),
                  lw("Usage: AERMOD " + e.VERSN + " takes either no or one or two parameters."),
                  lw("       Either"), lw("             AERMOD"), lw("       Or"),
                  lw("             AERMOD plumetest.inp"), lw("       Or"),
                  lw("             AERMOD plumetest.inp plumetest.out"), lw(""),
                  lw("       The first parameter  is the .INP file name,"),
                  lw("       The second parameter is the .OUT file name,")])


def filopn(e):
    """FILOPN: abre el fichero de control y el de salida."""
    try:
        e.abrir_entrada(e.INUNIT, e.INPFIL)
    except OSError:
        e.errhdl("  ", "FILOPN", "E", "500", "RUN-STRM")
        e.pantalla.w("+Error Opening Runstream Input File!  Aborting.")
        raise Parada()
    try:
        e.abrir_salida(e.IOUNIT, e.OUTFIL)
    except OSError:
        e.errhdl("  ", "FILOPN", "E", "500", "OUTPUT")
    e.pantalla.w("+Now Processing SETUP Information")


def ejecutar(argv=None):
    """Corre AERMOD con los argumentos de la línea de órdenes. Devuelve el código de salida."""
    if argv is None:
        argv = sys.argv[1:]
    e = Estado()
    e.NTOTHRS = 0
    e.NYEARS = 0
    e.FUNITIND = 1
    e.FUNITINX = 100
    e.FATAL = False
    e.RUNERR = False
    e.L_NOHEADER[:] = False
    inp, out = _nombres(argv)
    if inp is None:
        _uso(e)
        return 0
    e.INPFIL, e.OUTFIL = inp, out
    try:
        _programa(e)
    except Parada:
        pass
    finally:
        e.cerrar_todo()
    return 0


def _programa(e):
    e.TITLE1 = ""
    e.TITLE2 = ""
    e.RUNDAT, e.RUNTIM = e.datime()
    filopn(e)
    control.preset(e)
    fin_setup = not e.FATAL
    if fin_setup:
        if e.NYEARS == 0:
            e.NYEARS = 5
        if not e.EVONLY:
            e.IEVENT = 0
        control.allsetup(e)
        control.varini(e)
        control.setup(e)
        from . import depura
        depura.open_all_debugfiles(e)
        if e.LDPART or e.LDGAS:
            # velocidad de sedimentación y demás datos fijos de la deposición
            from . import entrada_fuentes
            entrada_fuentes.vdp1(e)
        control.allresult(e)
        from . import resumen_entrada
        resumen_entrada.resini(e)
        e.terrst()
        from . import estela_edificio
        estela_edificio.numpr1(e)
        estela_edificio.prime1(e)
        if not e.RUN or e.FATAL or e.IWRN > 0:
            e.w(e.IOUNIT, fwrite("(//2X,'*** Message Summary For AERMOD Model Setup ***'/)"))
            e.sumtbl(e.IOUNIT)
    if e.FATAL:
        e.pantalla.w("+Fatal Error Occurred During Setup Phase!")
        e.w(e.IOUNIT, fwrite("(/4X,'**************************************',/4X,'*** SETUP Finishes "
                             "UN-successfully ***',/4X,'**************************************'/)"))
    else:
        e.w(e.IOUNIT, fwrite("(/1X,'***********************************',/1X,'*** SETUP Finishes "
                             "Successfully ***',/1X,'***********************************'/)"))
        from . import resumen_entrada
        resumen_entrada.inpsum(e)
    if not e.FATAL and e.RUN and not e.EVONLY:
        from . import resumen_entrada, salida
        resumen_entrada.resini(e)
        if e.RSTINP:
            from . import reinicio
            reinicio.rsinit(e)
        from . import bucle_horario
        bucle_horario.hrloop(e)
        salida.final(e)
    else:
        e.MODOPS_STRING = ""
    e.terrst()
    e.header(e.IOUNIT)
    e.w(e.IOUNIT, fwrite("(/1X,'*** Message Summary : AERMOD Model Execution ***'/)"))
    e.sumtbl(e.IOUNIT)
    if e.SUMMFILE:
        e.header(e.ISUMUNT)
        e.w(e.ISUMUNT, fwrite("(/1X,'*** Message Summary : AERMOD Model Execution ***'/)"))
        e.sumtbl(e.ISUMUNT)
    _fin(e)


def _fin(e):
    if e.FATAL or e.RUNERR:
        if e.RUNERR:
            e.pantalla.w("+Fatal Error Occurred During Runtime Phase!")
        e.w(e.IOUNIT, fwrite("(/4X,'***************************************',/4X,'*** AERMOD Finishes "
                             "UN-successfully ***',/4X,'***************************************'/)"))
    else:
        if e.L_MAXDCONT_ORIGCONC_WARNING:
            t = fwrite("(/4X,'NOTE: MAXDCONT Inconsistency Warning Issued!'/)")
            e.pantalla.w(t)
            e.w(e.IOUNIT, t)
        elif e.L_EVENT_ORIGCONC_WARNING:
            t = fwrite("(/4X,'NOTE: EVENT Inconsistency Warning(s) Issued!')")
            e.pantalla.w(t)
            e.w(e.IOUNIT, t)
        e.w(e.IOUNIT, fwrite("(/4X,'************************************',/4X,'*** AERMOD Finishes "
                             "Successfully ***',/4X,'************************************'/)"))
    if e.ERRLST and e.IERWRT in e.U:
        e.msgwrt()
        e.cerrar(e.IERWRT)
