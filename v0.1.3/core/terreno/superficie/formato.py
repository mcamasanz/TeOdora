# -*- coding: utf-8 -*-
"""Compatibilidad numérica con el Fortran de AERSURFACE v26135 (US EPA, dominio público).

Cada función reproduce una semántica concreta del original que, si se hiciera «a la Python»,
cambiaría algún resultado en el último decimal o en un caso frontera.
"""
import math

import numpy as np

# Literales Fortran en PRECISIÓN SIMPLE dentro de expresiones de doble precisión: el
# compilador promociona el valor float32 (no el decimal exacto). Ej.: 0.10 -> 0.1000000015
F32_0_10 = float(np.float32(0.10))
F32_0_90 = float(np.float32(0.90))
F32_1E_3 = float(np.float32(1.0e-3))      # criterios de convergencia «err > 1.0e-03»


def nint(x):
    """NINT/IDNINT de Fortran: redondeo al entero más cercano, empates LEJOS del cero
    (numpy redondea los empates al par)."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def nint_arr(x):
    """NINT vectorizado (empates lejos del cero)."""
    x = np.asarray(x, dtype=np.float64)
    return np.where(x >= 0, np.floor(x + 0.5), -np.floor(-x + 0.5)).astype(np.int64)


def stodbl(s):
    """STODBL de AERSURFACE: convierte texto en número acumulando dígito a dígito
    (CNUM = CNUM*10 + d; decimales con FDEC = FDEC/10). Puede diferir en el último bit del
    redondeo correcto de float(); se replica para que las coordenadas den lo mismo.
    Devuelve None si el campo no es numérico."""
    cnum, head, fdec = 0.0, 0.0, 1.0
    dmark = nmark = pmark = emark = False
    started = False
    for ch in s:
        if ch == " ":
            if started:
                break
            continue
        started = True
        if "0" <= ch <= "9":
            d = float(ord(ch) - 48)
            if not dmark:
                cnum = cnum * 10.0 + d
            else:
                fdec = fdec / 10.0
                cnum = cnum + fdec * d
        elif dmark and not emark and ch in "ED":
            emark = True
            head = -cnum if nmark else cnum
            dmark = nmark = False
            cnum = 0.0
        elif not pmark and ch == "+":
            pmark = True
        elif not nmark and ch == "-":
            nmark = True
        elif not dmark and ch == ".":
            dmark = True
        else:
            return None
    fnum = -cnum if nmark else cnum
    if emark:
        if abs(fnum) <= 30.0:
            fnum = head * 10.0 ** fnum
        else:
            return None
    return fnum


def fmt_f(valor, w, d):
    """Descriptor Fw.d de Fortran (alineado a la derecha; asteriscos si no cabe)."""
    s = f"{valor:.{d}f}" + ("." if d == 0 else "")      # F10.0 -> «1532024.»
    if len(s) > w:
        return "*" * w
    return s.rjust(w)


def fmt_i(valor, w):
    s = f"{int(valor):{w}d}"
    return "*" * w if len(s) > w else s
