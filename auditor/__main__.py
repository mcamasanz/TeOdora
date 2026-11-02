# -*- coding: utf-8 -*-
"""Línea de órdenes del auditor.

    python -m auditor [--base REF] [--solo-pruebas] [--limite S] [--total S]
    python -m auditor --instalar-hook          # pre-push: audita antes de subir a main
    python -m auditor --nuevo-caso MOTOR/NOMBRE --desde CARPETA --orden "args" [--orden "args"…]
                      [--carpeta SUB] [--descripcion TEXTO]
    python -m auditor --regenerar MOTOR/NOMBRE # referencia nueva (exige justificarlo en CAMBIOS_REFERENCIA.md)

Código de salida: 0 si se cumplen todas las reglas, 1 si alguna falla.
"""
import argparse
import shutil
import sys

from . import reglas


def _informe(res):
    ancho = max(len(r.regla) for r in res)
    print("\nAuditor de teOdors")
    print("=" * 60)
    for r in res:
        print("%s  %-*s  %s" % ("OK  " if r.ok else "FALLA", ancho, r.regla, r.detalle[0] if r.detalle else ""))
        for d in r.detalle[1:]:
            print("      %s %s" % (" " * ancho, d))
    ok = all(r.ok for r in res)
    print("=" * 60)
    print("APTO para entrar en la rama principal" if ok else "NO APTO: corrige lo que falla y vuelve a auditar")
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m auditor", description=__doc__.splitlines()[0])
    p.add_argument("--base", default="main", help="referencia de git con la que se compara (main)")
    p.add_argument("--solo-pruebas", action="store_true", help="solo R1-R3 (sin comparar con git)")
    p.add_argument("--limite", type=float, default=reglas.LIMITE_PRUEBA_S, help="segundos por prueba")
    p.add_argument("--total", type=float, default=reglas.LIMITE_TOTAL_S, help="segundos del conjunto")
    p.add_argument("--instalar-hook", action="store_true")
    p.add_argument("--nuevo-caso")
    p.add_argument("--desde")
    p.add_argument("--orden", action="append")
    p.add_argument("--carpeta", default="")
    p.add_argument("--descripcion", default="")
    p.add_argument("--regenerar")
    a = p.parse_args(argv)
    if a.instalar_hook:
        destino = reglas.RAIZ / ".git" / "hooks" / "pre-push"
        shutil.copy2(reglas.AUDITOR / "hooks" / "pre-push", destino)
        print("instalado:", destino)
        return 0
    if a.nuevo_caso or a.regenerar:
        from . import referencias
        if a.nuevo_caso:
            if not (a.desde and a.orden):
                p.error("--nuevo-caso necesita --desde y al menos un --orden")
            referencias.crear(a.nuevo_caso, a.desde, [o.split() for o in a.orden], a.carpeta, a.descripcion)
        else:
            referencias.regenerar(a.regenerar)
        return 0
    return _informe(reglas.auditar(a.base, a.solo_pruebas, a.limite, a.total))


if __name__ == "__main__":
    sys.exit(main())
