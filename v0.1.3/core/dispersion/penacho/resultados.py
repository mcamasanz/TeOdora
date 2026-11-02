# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): acumulación de resultados horarios
(calc2.f: SUMVAL, AVER, HIVALS, NHIGH, HSETFG, MAXVALUE, MSETFG, MAXFIL, POSTFL)."""
import struct

import numpy as np

from .estado import NoTraducido
from .formato import fwrite, fx


def sumval(e):
    """SUMVAL: suma HRVAL de la fuente ISRC al grupo IGRP en el receptor IREC."""
    isrc, igrp, irec = e.ISRC, e.IGRP, e.IREC
    if e.IGROUP[isrc, igrp] != 1:
        e.ITYP = e.NUMTYP + 1
        return
    for ityp in range(1, e.NUMTYP + 1):
        h = e.HRVAL[ityp]
        if h != 0.0:
            for iave in range(1, e.NUMAVE + 1):
                e.AVEVAL[irec, igrp, iave, ityp] = h + e.AVEVAL[irec, igrp, iave, ityp]
            if e.PERIOD or e.ANNUAL:
                e.ANNVAL[irec, igrp, ityp] = h + e.ANNVAL[irec, igrp, ityp]
            if e.ISEAHR[igrp] == 1:
                e.SHVALS[irec, igrp, e.ISEAS, e.IHOUR, ityp] = h + \
                    e.SHVALS[irec, igrp, e.ISEAS, e.IHOUR, ityp]
    e.ITYP = e.NUMTYP + 1


def sumback(e):
    """SUMBACK: suma la concentración de fondo de la hora a todos los receptores del grupo IGRP
    (si el grupo incluye BACKGROUND)."""
    igrp, nr = e.IGRP, e.NUMREC
    e.ITYP = 1
    if e.GRP_BACK[igrp]:
        bckgrd = e.BGCONC * e.EMIFAC[1] / 1.0e6
        e.BACKAVE[igrp] = e.BACKAVE[igrp] + e.BGCONC * e.EMIFAC[1] / 1.0e6
        if e.PERIOD or e.ANNUAL:
            e.BACKANN[igrp] = e.BACKANN[igrp] + e.BGCONC * e.EMIFAC[1] / 1.0e6
        if e.ISEAHR[igrp] == 1:
            e.BACKSEASHR[igrp, e.ISEAS, e.IHOUR] = e.BACKSEASHR[igrp, e.ISEAS, e.IHOUR] + \
                e.BGCONC * e.EMIFAC[1] / 1.0e6
    else:
        bckgrd = 0.0
    for iave in range(1, e.NUMAVE + 1):
        e.AVEVAL[1:nr + 1, igrp, iave, 1] = bckgrd + e.AVEVAL[1:nr + 1, igrp, iave, 1]
    e.IAVE = e.NUMAVE + 1
    if e.PERIOD or e.ANNUAL:
        e.ANNVAL[1:nr + 1, igrp, 1] = bckgrd + e.ANNVAL[1:nr + 1, igrp, 1]
    if e.ISEAHR[igrp] == 1:
        e.SHVALS[1:nr + 1, igrp, e.ISEAS, e.IHOUR, 1] = bckgrd + e.SHVALS[1:nr + 1, igrp, e.ISEAS, e.IHOUR, 1]


def aver(e):
    """AVER: promedio de un periodo de varias horas (horas válidas o el 75 %)."""
    e.PATH = "CN"
    ia = e.IAVE
    if e.KAVE[ia] != 1:
        nval = float(e.NUMHRS[ia] - e.NUMCLM[ia] - e.NUMMSG[ia])
        snum = max(nval, float(_dnint(float(e.NUMHRS[ia]) * 0.75 + 0.4)))
        if nval < 18 and e.KAVE[ia] == 24:
            e.errhdl(e.PATH, "AVER", "W", "732", fwrite("(I10)", e.FULLDATE)[0])
        elif nval < 6 and e.KAVE[ia] == 8:
            e.errhdl(e.PATH, "AVER", "W", "733", fwrite("(I10)", e.FULLDATE)[0])
        elif nval < 3 and e.KAVE[ia] == 3:
            e.errhdl(e.PATH, "AVER", "W", "734", fwrite("(I10)", e.FULLDATE)[0])
        e.AVEVAL[1:e.NUMREC + 1, 1:e.NUMGRP + 1, ia, 1] = \
            e.AVEVAL[1:e.NUMREC + 1, 1:e.NUMGRP + 1, ia, 1] / snum


def _dnint(x):
    import math
    return math.floor(x + 0.5) if x >= 0 else -math.floor(-x + 0.5)


def hivals(e):
    """HIVALS: actualiza las tablas de máximos por receptor y globales."""
    ia = e.IAVE
    if e.CALCS or e.KAVE[ia] != 1:
        if e.INHI[ia] == 1:
            for ityp in range(1, e.NUMTYP + 1):
                e.ITYP = ityp
                nhigh(e)
            e.ITYP = e.NUMTYP + 1
        if e.MAXAVE[ia] == 1:
            for ityp in range(1, e.NUMTYP + 1):
                e.ITYP = ityp
                maxvalue(e)
            e.ITYP = e.NUMTYP + 1
    e.NUMHRS[ia] = 0
    e.NUMCLM[ia] = 0
    e.NUMMSG[ia] = 0


def _bandera(e):
    ia = e.IAVE
    c, m = e.NUMCLM[ia], e.NUMMSG[ia]
    if c != 0 and m == 0:
        return "c"
    if c == 0 and m != 0:
        return "m"
    if c != 0 and m != 0:
        return "b"
    return None


def nhigh(e):
    """NHIGH: inserta AVEVAL en la lista de los NHIVAL valores más altos de cada receptor."""
    ia, it = e.IAVE, e.ITYP
    nh = e.NHIVAL
    hv, hc, hd = e.HIVALU, e.HCLMSG, e.NHIDAT
    sin_bandera = e.NUMCLM[ia] == 0 and e.NUMMSG[ia] == 0
    band = _bandera(e)
    kurdat = e.KURDAT
    nr = e.NUMREC
    for igrp in range(1, e.NUMGRP + 1):
        e.IGRP = igrp
        # prefiltro exacto: cada receptor tiene su tabla; solo entran los que superan su último valor
        cand = (np.flatnonzero(e.AVEVAL[1:nr + 1, igrp, ia, it] > hv[1:nr + 1, nh, igrp, ia, it]) + 1).tolist() \
            if nh >= 1 and nr >= 1 else []
        for irec in cand:
            a = e.AVEVAL[irec, igrp, ia, it]
            if nh > 1:
                if a > hv[irec, nh, igrp, ia, it]:
                    for j in range(nh - 1, 0, -1):
                        if a <= hv[irec, j, igrp, ia, it]:
                            hv[irec, j + 1, igrp, ia, it] = a
                            if sin_bandera:
                                hc[irec, j + 1, igrp, ia, it] = ""
                            elif band is not None:
                                hc[irec, j + 1, igrp, ia, it] = band
                            hd[irec, j + 1, igrp, ia, it] = kurdat
                            break
                        hv[irec, j + 1, igrp, ia, it] = hv[irec, j, igrp, ia, it]
                        hc[irec, j + 1, igrp, ia, it] = hc[irec, j, igrp, ia, it]
                        hd[irec, j + 1, igrp, ia, it] = hd[irec, j, igrp, ia, it]
                        if j == 1:
                            hv[irec, 1, igrp, ia, it] = a
                            if sin_bandera:
                                hc[irec, 1, igrp, ia, it] = ""
                            elif band is not None:
                                hc[irec, 1, igrp, ia, it] = band
                            hd[irec, 1, igrp, ia, it] = kurdat
            elif nh == 1:
                if a > hv[irec, 1, igrp, ia, it]:
                    hv[irec, 1, igrp, ia, it] = a
                    if sin_bandera:
                        hc[irec, 1, igrp, ia, it] = ""
                    elif band is not None:
                        hc[irec, 1, igrp, ia, it] = band
                    hd[irec, 1, igrp, ia, it] = kurdat
        e.IREC = e.NUMREC + 1
    e.IGRP = e.NUMGRP + 1


def maxvalue(e):
    """MAXVALUE: inserta AVEVAL en la tabla global de los NMXVAL valores máximos."""
    ia, it = e.IAVE, e.ITYP
    nm = e.NMXVAL
    rv, mc, md, ml = e.RMXVAL, e.MCLMSG, e.MXDATE, e.MXLOCA
    sin_bandera = e.NUMCLM[ia] == 0 and e.NUMMSG[ia] == 0
    band = _bandera(e)
    kurdat = e.KURDAT
    nr = e.NUMREC
    for igrp in range(1, e.NUMGRP + 1):
        e.IGRP = igrp
        # prefiltro exacto: el mínimo de la tabla (rv[nm]) solo puede crecer durante el recorrido,
        # así que un receptor que no lo supera ahora tampoco lo superaría en su turno
        cand = (np.flatnonzero(e.AVEVAL[1:nr + 1, igrp, ia, it] > rv[nm, igrp, ia, it]) + 1).tolist() \
            if nm >= 1 and nr >= 1 else []
        for irec in cand:
            a = e.AVEVAL[irec, igrp, ia, it]
            if nm > 1:
                if a > rv[nm, igrp, ia, it]:
                    for j in range(nm - 1, 0, -1):
                        if a <= rv[j, igrp, ia, it]:
                            rv[j + 1, igrp, ia, it] = a
                            if sin_bandera:
                                mc[j + 1, igrp, ia, it] = ""
                            elif band is not None:
                                mc[j + 1, igrp, ia, it] = band
                            md[j + 1, igrp, ia, it] = kurdat
                            ml[j + 1, igrp, ia, it] = irec
                            break
                        rv[j + 1, igrp, ia, it] = rv[j, igrp, ia, it]
                        md[j + 1, igrp, ia, it] = md[j, igrp, ia, it]
                        mc[j + 1, igrp, ia, it] = mc[j, igrp, ia, it]
                        ml[j + 1, igrp, ia, it] = ml[j, igrp, ia, it]
                        if j == 1:
                            rv[1, igrp, ia, it] = a
                            if sin_bandera:
                                mc[1, igrp, ia, it] = ""
                            elif band is not None:
                                mc[1, igrp, ia, it] = band
                            md[1, igrp, ia, it] = kurdat
                            ml[1, igrp, ia, it] = irec
            elif nm == 1:
                if a > rv[1, igrp, ia, it]:
                    rv[1, igrp, ia, it] = a
                    if sin_bandera:
                        mc[1, igrp, ia, it] = ""
                    elif band is not None:
                        mc[1, igrp, ia, it] = band
                    md[1, igrp, ia, it] = kurdat
                    ml[1, igrp, ia, it] = irec
        e.IREC = e.NUMREC + 1
    e.IGRP = e.NUMGRP + 1


def maxfil(e):
    """MAXFIL: escribe los valores que superan el umbral (MAXIFILE)."""
    ia = e.IAVE
    if e.CALCS or e.KAVE[ia] != 1:
        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            if e.MAXFLE[igrp, ia] == 1:
                u = e.IMXUNT[igrp, ia]
                lineas = []
                for irec in range(1, e.NUMREC + 1):
                    if e.AVEVAL[irec, igrp, ia, 1] >= e.THRESH[igrp, ia]:
                        lineas += fwrite(e.THRFRM, e.KAVE[ia], fx(e.GRPID[igrp], 8), e.KURDAT,
                                         e.AXR[irec], e.AYR[irec], e.AZELEV[irec],
                                         e.AZHILL[irec], e.AZFLAG[irec],
                                         e.AVEVAL[irec, igrp, ia, 1])
                if lineas:
                    e.w(u, lineas)
                if e.RSTSAV:
                    e.volcar(u)


_PST_FIX = "(3(1X,F13.5),3(1X,F8.2),2X,A6,2X,A8,2X,I8.8,2X,A8)"
_PST_EXP = "(2(1X,F13.5),1X,E13.6,3(1X,F8.2),2X,A6,2X,A8,2X,I8.8,2X,A8)"


def _partes_pst(e, nrec, ntyp):
    """Partes fijas por receptor de las líneas del POSTFILE PLOT con los formatos estándar
    (X e Y; cotas; red), guardadas mientras no cambien los receptores. None si no aplica."""
    if ntyp != 1 or e.PSTFRM not in (_PST_FIX, _PST_EXP):
        return None
    coords = (e.AXR[1:nrec + 1], e.AYR[1:nrec + 1], e.AZELEV[1:nrec + 1], e.AZHILL[1:nrec + 1],
              e.AZFLAG[1:nrec + 1])
    c = getattr(e, "_pst_partes", None)
    if c is not None and c[0] == e.PSTFRM and len(c[1][0]) == nrec and \
            all(np.array_equal(a, b) for a, b in zip(c[1], coords)):
        return c[2]
    from .formato import fmt_e, fmt_f
    # (los nX finales no se escriben si no les sigue nada: los blancos se añaden aparte)
    pre = [fwrite("(2(1X,F13.5))", x, y)[0] + " " for x, y in zip(coords[0].tolist(), coords[1].tolist())]
    mid = [fwrite("(3(1X,F8.2))", a, b, c_)[0]
           for a, b, c_ in zip(coords[2].tolist(), coords[3].tolist(), coords[4].tolist())]
    net = [fx(e.NETID[i], 8) for i in range(1, nrec + 1)]
    if e.PSTFRM == _PST_FIX:
        def fval(v):
            return fmt_f(v, 13, 5)
    else:
        def fval(v):
            return fmt_e(v, 13, 6, None)
    partes = (pre, mid, net, fval)
    e._pst_partes = (e.PSTFRM, tuple(a.copy() for a in coords), partes)
    return partes


def postfl(e):
    """POSTFL: escribe el fichero de posproceso (sin formato o PLOT) del periodo IAVE."""
    ia = e.IAVE
    nrec, ntyp = e.NUMREC, e.NUMTYP
    for igrp in range(1, e.NUMGRP + 1):
        e.IGRP = igrp
        if e.IPSTFL[igrp, ia] != 1:
            continue
        u = e.IPSUNT[igrp, ia]
        if e.IPSFRM[igrp, ia] == 0:
            datos = struct.pack("<ii", int(e.KURDAT), int(e.KAVE[ia])) + \
                fx(e.GRPID[igrp], 8).encode("latin-1")
            datos += e.AVEVAL[1:nrec + 1, igrp, ia, 1:ntyp + 1].T.astype("<f8").tobytes()
            e.U[u].reg(datos)
        else:
            chr_ave = fx(e.CHRAVE[ia], 5)
            grp = fx(e.GRPID[igrp], 8)
            partes = _partes_pst(e, nrec, ntyp)
            if partes is not None:
                # vía rápida (mismo texto): la parte fija de cada receptor ya está formateada
                pre, mid, net, fval = partes
                cola = fwrite("(2X,A6,2X,A8,2X,I8.8)", chr_ave, grp, e.KURDAT)[0] + "  "
                vals = e.AVEVAL[1:nrec + 1, igrp, ia, 1].tolist()
                lineas = [pre[k] + fval(vals[k]) + mid[k] + cola + net[k] for k in range(nrec)]
            else:
                lineas = []
                for irec in range(1, nrec + 1):
                    lineas += fwrite(e.PSTFRM, e.AXR[irec], e.AYR[irec],
                                     *[e.AVEVAL[irec, igrp, ia, it] for it in range(1, ntyp + 1)],
                                     e.AZELEV[irec], e.AZHILL[irec], e.AZFLAG[irec], chr_ave, grp,
                                     e.KURDAT, fx(e.NETID[irec], 8))
            e.w(u, lineas)
        if e.RSTSAV:
            e.volcar(u)


def toxxfl(e):
    """TOXXFL (calc2.f): llena los búferes del TOXXFILE y los escribe cuando se llenan."""
    ia = e.IAVE
    if e.ITOXFL[ia] == 1 and (e.CALCS or e.KAVE[ia] != 1):
        npair = e.NPAIR
        cutoff = e.TOXTHR[ia] * e.EMIFAC[1]
        for irec in range(1, e.NUMREC + 1):
            e.IREC = irec
            for igrp in range(1, e.NUMGRP + 1):
                e.IGRP = igrp
                if e.AVEVAL[irec, igrp, ia, 1] >= cutoff:
                    for ig in range(1, e.NUMGRP + 1):
                        e.IPAIR += 1
                        e.IDCONC[ia, e.IPAIR] = 100000 * e.ILINE + 1000 * ig + irec
                        e.TXCONC[ia, e.IPAIR] = e.AVEVAL[irec, ig, ia, 1] / e.EMIFAC[1]
                        if e.IPAIR == npair:
                            u = e.U[int(e.ITXUNT[ia])]
                            u.reg(e.IDCONC[ia, 1:npair + 1].astype("<i4").tobytes())
                            u.reg(e.TXCONC[ia, 1:npair + 1].astype("<f8").tobytes())
                            e.IPAIR = 0
                    break
        e.IREC = e.NUMREC + 1


def toxx_fin(e):
    """Fin de HRLOOP: rellena con ceros los búferes del TOXXFILE, los escribe y cierra."""
    npair = e.NPAIR
    for ia in range(1, e.NUMAVE + 1):
        e.IAVE = ia
        if e.ITOXFL[ia] == 1:
            e.IDCONC[ia, e.IPAIR + 1:npair + 1] = e.IDUM
            e.TXCONC[ia, e.IPAIR + 1:npair + 1] = 0.0
            u = int(e.ITXUNT[ia])
            e.U[u].reg(e.IDCONC[ia, 1:npair + 1].astype("<i4").tobytes())
            e.U[u].reg(e.TXCONC[ia, 1:npair + 1].astype("<f8").tobytes())
            e.cerrar(u)
    e.IAVE = e.NUMAVE + 1
