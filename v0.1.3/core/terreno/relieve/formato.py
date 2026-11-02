# -*- coding: utf-8 -*-
"""Compatibilidad numérica y de formato con el Fortran de AERMAP v24142 (US EPA, dominio
público). Cada función reproduce una semántica concreta del original."""
import math

import numpy as np

F32 = np.float32


def nint(x):
    """NINT/IDNINT: redondeo al entero más cercano, empates LEJOS del cero."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def stodbl(s, length=200, previo=0.0):
    """STODBL de AERMAP (aermap.f). Lee el número dígito a dígito (CNUM = CNUM*10 + d;
    decimales con FDEC = FDEC/10), admite exponente E o D, signo y repetición «n*valor».
    Solo mira los `length` primeros caracteres del campo (SOLOCA usa 40).

    Devuelve (valor, imuti). imuti = -1 si el campo no es numérico: en ese caso el original
    NO asigna DNUM y la variable del llamador conserva `previo`. Con exponente > 30 asigna
    0 o HEAD*1e30 y también marca error."""
    s = s[:length]
    cnum, fdec, head = 0.0, 1.0, 0.0
    mend = inn = nmark = pmark = dmark = mmark = emark = False
    imuti = 1
    i = 0
    n = len(s)
    while not mend and i < n:
        ch = s[i]
        if ch != " ":
            inn = True
            if "0" <= ch <= "9":
                d = float(ord(ch) - 48)
                if not dmark:
                    cnum = cnum * 10.0 + d
                else:
                    fdec = fdec / 10.0
                    cnum = cnum + fdec * d
            else:
                if (not emark and ch == "E") or (not emark and ch == "D"):
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
                elif not mmark and ch == "*" and not nmark:
                    mmark = True
                    imuti = nint(cnum)
                    cnum = 0.0
                else:
                    return previo, -1
        elif inn and ch == " ":
            mend = True
        i += 1
    dnum = cnum
    if nmark:
        dnum = -dnum
    if emark and abs(dnum) <= 30.0:
        dnum = head * 10.0 ** dnum
    elif emark and abs(dnum) > 30.0:
        if dnum < 0.0:
            dnum = 0.0
        elif dnum > 0.0:
            dnum = head * 1.0e30
        return dnum, -1
    return dnum, imuti


def stonum(s, length=200, previo=0.0):
    """STONUM: como STODBL pero en PRECISIÓN SIMPLE (REAL) y sin exponente D.
    Devuelve (valor float32 promovido a float, imuti)."""
    s = s[:length]
    cnum, fdec, head = F32(0.0), F32(1.0), F32(0.0)
    diez = F32(10.0)
    mend = inn = nmark = pmark = dmark = mmark = emark = False
    imuti = 1
    i = 0
    n = len(s)
    while not mend and i < n:
        ch = s[i]
        if ch != " ":
            inn = True
            if "0" <= ch <= "9":
                d = F32(ord(ch) - 48)
                if not dmark:
                    cnum = F32(cnum * diez + d)
                else:
                    fdec = F32(fdec / diez)
                    cnum = F32(cnum + F32(fdec * d))
            else:
                if not emark and ch == "E":
                    emark = True
                    head = -cnum if nmark else cnum
                    dmark = nmark = False
                    cnum = F32(0.0)
                elif not pmark and ch == "+":
                    pmark = True
                elif not nmark and ch == "-":
                    nmark = True
                elif not dmark and ch == ".":
                    dmark = True
                elif not mmark and ch == "*" and not nmark:
                    mmark = True
                    imuti = nint(float(cnum))
                    cnum = F32(0.0)
                else:
                    return previo, -1
        elif inn and ch == " ":
            mend = True
        i += 1
    fnum = cnum
    if nmark:
        fnum = F32(-fnum)
    if emark and abs(fnum) <= 30.0:
        fnum = F32(head * F32(10.0) ** fnum)
    elif emark and abs(fnum) > 30.0:
        if fnum < 0.0:
            fnum = F32(0.0)
        elif fnum > 0.0:
            fnum = F32(head * F32(1.0e30))
        return float(fnum), -1
    return float(fnum), imuti
