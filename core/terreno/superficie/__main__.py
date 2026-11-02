# -*- coding: utf-8 -*-
"""Traducción de AERSURFACE v26135 a Python. Uso (como el original, desde la carpeta del caso):

    python -m teodors.terreno.superficie control.inp
"""
import sys
import time
from pathlib import Path

from . import control, nucleo, salida


def main(argv=None):
    argv = argv or sys.argv[1:]
    inp = Path(argv[0] if argv else "aersurface.inp").resolve()
    t0 = time.perf_counter()
    c = control.leer(inp)
    if not c.run:
        print("RUNORNOT NOT: solo comprobación del fichero de control.")
        return 0
    r = nucleo.ejecutar(c)
    base = inp.parent
    if c.ou_sfc:
        salida.escribir_sfc(base / c.ou_sfc, c, r)
    salida.escribir_log(base / (inp.stem + ".log"), c, r)     # como el original: <control>.log
    if c.dbg_grid:
        for tipo, ou, ini in (("LC", c.ou_lc_grid, 0), ("Imp", c.ou_imp_grid, 127),
                              ("Can", c.ou_can_grid, 127)):
            if ou and tipo in r.rejillas:
                nombre = {"LC": getattr(c, "_lc_nombre", ""),
                          "Imp": getattr(c, "_imp_nombre", ""),
                          "Can": getattr(c, "_can_nombre", "")}[tipo]
                salida.escribir_rejilla(base / ou, r.rejillas[tipo], tipo, nombre, ini)
    for a in c.avisos + r.avisos:
        print("AVISO:", a)
    print(f"superficie terminado en {time.perf_counter() - t0:.2f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
