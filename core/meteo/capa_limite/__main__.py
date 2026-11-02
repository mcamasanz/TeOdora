# -*- coding: utf-8 -*-
"""Traducción de AERMET 26135 (US EPA, dominio público): programa principal (aermet.f90) y
CLEANUP (mod_misc.f90).

Uso:  python -m teodors.meteo.capa_limite [fichero_de_control]     (por defecto aermet.inp, como el original)
Códigos de salida: 0 terminado (con éxito o no, como el original), 2 opción fuera de alcance,
3 el original aborta en ese punto con un error de ejecución (se escribe su mismo mensaje).
"""
import sys

from . import informes, estacion_local, calculo_cl, obs_superficie, sondeos
from .comun import datetime, start_stop
from .control import readinp
from .estado import OUTPUT_UNIT, Estado
from .formato import ErrorEjecucion
from .control_cl import NoTraducido


def cleanup(E):
    m = E.m
    for i in range(m.inp_unit, m.debug_unit + 1):
        if i != m.rpt_unit:
            E.cerrar(i)


def _fin(E, mal):
    m = E.m
    txt = "AERMET FINISHED UN-SUCCESSFULLY" if mal else "AERMET FINISHED SUCCESSFULLY"
    E.w(m.rpt_unit, "(//1x,a/)", txt)
    if m.rpt_unit != OUTPUT_UNIT:
        E.w(OUTPUT_UNIT, "(//1x,a/)", txt)
    start_stop(E, 2, m.rpt_unit)
    if m.rpt_unit != OUTPUT_UNIT:
        start_stop(E, 2, OUTPUT_UNIT)


def ejecutar(inpfile=None, eco=True):
    """Ejecuta AERMET sobre `inpfile`. Devuelve el objeto Estado (pantalla en E.pantalla)."""
    E = Estado(inpfile if inpfile else "aermet.inp")
    m = E.m
    try:
        datetime(E, 1)
        start_stop(E, 1, OUTPUT_UNIT)
        if not readinp(E):
            return E
        if m.lstage[1]:
            informes.input_summ(E)
        if m.lbad1 or m.ljbkeywords[3]:
            informes.write_msg(E)
            cleanup(E)
            datetime(E, 2)
            _fin(E, m.lbad1)
        else:
            m.istage = 2 if not m.lstage[1] else 1
            if m.lpath[2]:
                m.ipath = 2
                sondeos.up_proc(E)
                if E.up.lbadup:
                    m.lbad1 = True
            if m.lpath[3] and not m.lbad1:
                m.ipath = 3
                obs_superficie.sf_proc(E)
                if m.lstage[2] and E.sf.lasos and E.sf.lsfkeywords[9]:
                    obs_superficie.read_1min(E)
                if E.sf.lbadsfc:
                    m.lbad1 = True
            if (m.lpath[4] or m.lpath[5]) and not m.lbad1:
                m.ipath = 4 if m.lpath[4] else 5
                estacion_local.os_proc(E)
                if E.os.lbados:
                    m.lbad1 = True
            if m.lpath[6] and not m.lbad1:
                m.ipath = 6
                calculo_cl.pbl_proc(E)
                if E.pb.lbadpbl:
                    m.lbad1 = True
            if not m.lstage[1]:
                informes.input_summ(E)
            if not m.lbad1:
                informes.audit_summ(E)
            if m.lpath[6] and not m.lbad1:
                if not E.pb.run_coare:
                    informes.sfchar_sum(E)
                informes.obs_sum(E)
                informes.pbl_sum(E)
            informes.write_msg(E)
            cleanup(E)
            datetime(E, 2)
            _fin(E, E.up.lbadup or E.sf.lbadsfc or E.os.lbados or E.pb.lbadpbl or E.pb.lbadout)
    finally:
        for u in list(E.units):
            E.cerrar(u)
        if eco:
            sys.stdout.write("".join(x + "\n" for x in E.pantalla))
    return E


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        ejecutar(argv[0] if argv else None)
    except NoTraducido as e:
        sys.stdout.write(" OPCION FUERA DEL ALCANCE DE LA TRADUCCION: %s\n" % e)
        return 2
    except ErrorEjecucion as e:
        sys.stdout.write((e.forrtl or " LA TRADUCCION SE DETIENE: %s" % e) + "\n")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
