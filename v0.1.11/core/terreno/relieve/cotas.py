# -*- coding: utf-8 -*-
"""Traducción de AERMAP v24142 (US EPA, dominio público): cota de receptores y fuentes
(sub_recelv.f: RECELV, FIND4, INT2D; sub_srcelv.f: SRCELV, FIND4S; aermap.f: RECNUM).

FIND4 se traduce tal cual, rama a rama, porque decide qué cuatro nodos rodean al punto en
los bordes del fichero (y ahí mezcla segundos de arco con metros en algunas comparaciones:
se conserva). Su coste es pequeño frente a la altura de colina."""
import numpy as np

from .mdt_externo import isphere_nadd
from .utm import utmgeo


class _Indice:
    """El índice de perfiles tal como lo deja leído RECELV (vectores 1..NUMPRF)."""

    def __init__(self, d):
        n = d.numprf
        self.n = n
        self.xbase = [0.0] + [float(v) for v in d.idx_x[:n]]
        self.ybase = [0.0] + [float(v) for v in d.idx_y[:n]]
        self.nodes = [0] + [int(v) for v in d.idx_n[:n]]
        acum = [0]
        for k in range(1, n + 1):
            acum.append(acum[-1] + self.nodes[k])
        self.acum = acum           # acum[k] = suma de NODES(1..k)


def indice(d):
    if getattr(d, "_indice", None) is None:
        d._indice = _Indice(d)
    return d._indice


def elevacion(e, i, jdem, fuentes):
    """RECELV(IREC,JDEM) / SRCELV(ISRC,JDEM)."""
    m = "SRCELV" if fuentes else "RECELV"
    d = e.dem[jdem]
    if fuentes:
        lon, lat, xu, yu, iz = e.slon[i], e.slat[i], e.xsrcu[i], e.ysrcu[i], e.izons[i]
    else:
        lon, lat, xu, yu, iz = e.rlon[i], e.rlat[i], e.xrecu[i], e.yrecu[i], e.izonr[i]
    rlons, rlats = lon, lat                       # desplazamiento NAD nulo
    xrrm, yrrm = xu, yu
    if d.iplan == 1 and iz != d.izond:
        _, xrrm, yrrm, _, _ = utmgeo(555, d.izond, 0.0, 0.0, rlons, rlats, isphere_nadd(d))
    if d.iplan == 0:
        xrr, yrr = rlons, rlats
    elif d.iplan == 1:
        xrr, yrr = xrrm, yrrm
    else:
        xrr, yrr = e._elev_prev
    e._elev_prev = (xrr, yrr)
    if d.numprf <= 0:
        e.out.append(f" Direct Access File Empty, IDEM = {jdem:12d}")
        e.errhdl(e.path, m, "E", "510", f"IDR{min(100 + (jdem - 1) * 3 + 2, 99999):05d}")
        e.runerr = True
        return
    ix = indice(d)
    ierr, nx, ny1, ny2, x, y = find4(e, d, ix, i, xrr, yrr, fuentes)
    jrec = [0,
            ix.acum[nx[1] - 1] + ny1[1] if nx[1] >= 1 else ny1[1],
            ix.acum[nx[2] - 1] + ny1[2] if nx[2] >= 1 else ny1[2],
            ix.acum[nx[2] - 1] + ny2[2] if nx[2] >= 1 else ny2[2],
            ix.acum[nx[1] - 1] + ny2[1] if nx[1] >= 1 else ny2[1]]
    z = [0.0] * 5
    numz = 0
    sumz = 0.0
    jrecmsg = 0
    for ip in range(1, 5):
        jr = jrec[ip]
        if jr < 1 or jr > d.elev.size:
            from .estado import AbortoFortran
            raise AbortoFortran(f"{m}: registro {jr} fuera del fichero de acceso directo")
        z[ip] = float(d.elev[jr - 1])
        if z[ip] <= -9000.0 and jrecmsg == 0:
            jrecmsg = jr
        elif z[ip] <= -9000.0 and jrecmsg != 0:
            pass
        else:
            sumz = sumz + z[ip]
            numz += 1
    ident = e.srcid[i] if fuentes else f"{i:8d}"
    if 0 < numz < 4:
        e.errhdl(e.path, m, "W", "435" if fuentes else "415", ident)
        avez = sumz / float(numz)
        for ip in range(1, 5):
            if z[ip] <= -9000.0:
                z[ip] = avez
    elif numz == 0:
        ierr = -3
        e.errhdl(e.path, m, "W", "436" if fuentes else "416", ident)
        z = [0.0, -9999.0, -9999.0, -9999.0, -9999.0]
    zrec = int2d(z, x, y, xrr, yrr)
    tabla = e.isin if fuentes else e.irin
    filled = e.lsrc_filled if fuentes else e.lrec_filled
    destino = e.azs if fuentes else e.azelev
    jdmx = (e.jdms if fuentes else e.jdm)[i]
    if ierr == -3 and tabla[i][jdem] != 2:
        if fuentes:
            e.nsgap3 += 1
        else:
            e.nrgap3 += 1
        tabla[i][jdem] = 3
    if (not e.fillgaps and ierr == -3) or zrec == -9999.0:
        destino[i] = -9999.0
    elif e.fillgaps and ierr == -3 and zrec != -9999.0:
        filled[i][jdmx] = True
        destino[i] = zrec
    else:
        destino[i] = zrec


def find4(e, d, ix, ir, xrr, yrr, fuentes):
    """FIND4 / FIND4S. Devuelve (ierr, nx, ny1, ny2, x, y) con índices 1..2 / 1..4."""
    m = "SRCELV" if fuentes else "RECELV"
    cod = "420" if fuentes else "400"
    ident = e.srcid[ir] if fuentes else f"{ir:8d}"

    def aviso():
        e.errhdl(e.path, m, "W", cod, ident)

    ierr = 0
    x = [0.0] * 5
    y = getattr(e, "_find4_y", [0.0] * 5)          # Y es global y no se reinicia
    nx = [0, 0, 0]
    ny1 = [0, 0, 0]
    ny2 = [0, 0, 0]
    yy1 = yy2 = 0.0
    xb, yb, nodes = ix.xbase, ix.ybase, ix.nodes
    dxm, dym = d.dxm, d.dym
    if d.iplan == 1:
        ibegin = max(1, int((min(xrr, d.see_m) - xb[1]) / dxm))
    else:
        ibegin = max(1, int((min(xrr, d.selon_s) - xb[1]) / dxm))
    iends = ix.n
    if ibegin > iends:
        ibegin = iends

    def top(j):
        return yb[j] + float((nodes[j] - 1) * dym)

    def dentro(j):
        return yb[j] <= (yrr + dym) and top(j) >= (yrr - dym)

    def lejos(j):
        return yb[j] > (yrr + dym) or top(j) < (yrr - dym)

    for jx in range(ibegin, iends + 1):
        xc1 = xb[jx]
        xc2 = xrr
        if xc1 > xc2 and xc1 <= xc2 + dxm:
            if dentro(jx):
                if nx[1] <= 0:
                    ierr = min(ierr, -1)
                    nx[1] = nx[2] = jx
                    x[1] = x[2] = xc1
                    break
                else:
                    nx[2] = jx
                    x[2] = xc1
                    break
            elif ((xc1 > d.see_m and xc1 <= d.nee_m and yb[jx] > (yrr + dym))
                  or (xc1 > d.nee_m and xc1 <= d.see_m and top(jx) < (yrr - dym))):
                if jx - 1 >= ibegin and lejos(jx - 1):
                    nx[1] = nx[2] = max(jx - 2, ibegin)
                    x[1] = x[2] = xc1 - 2.0 * dxm
                    if ierr > -3:
                        aviso()
                    ierr = -3
                    break
                else:
                    ierr = min(ierr, -2)
                    nx[1] = nx[2] = max(jx - 1, ibegin)
                    x[1] = x[2] = xc1 - dxm
                    break
            elif nx[1] <= 0 and jx < iends:
                if lejos(jx):
                    nx[1] = nx[2] = min(jx + 1, iends)
                    x[1] = x[2] = xc1 + dxm
                else:
                    nx[1] = nx[2] = jx
                    x[1] = x[2] = xc1
                if ierr > -3:
                    aviso()
                ierr = -3
                break
            else:
                nx[2] = jx
                x[2] = xc1
                if ierr > -3:
                    aviso()
                ierr = -3
                break
        elif xc1 > xc2 + dxm:
            if nx[1] <= 0 and jx < iends:
                if lejos(jx):
                    nx[1] = nx[2] = min(jx + 1, iends)
                    x[1] = x[2] = xc1 + dxm
                else:
                    nx[1] = nx[2] = jx
                    x[1] = x[2] = xc1
                if ierr > -3:
                    aviso()
                ierr = -3
                break
            else:
                nx[2] = jx
                x[2] = xc1
                if ierr > -3:
                    aviso()
                ierr = -3
                break
        elif xc1 == xc2:
            if dentro(jx):
                nx[1] = nx[2] = jx
                x[1] = x[2] = xc1
                break
            elif ((xc1 > d.nwe_m and xc1 <= d.swe_m and yb[jx] > (yrr + dym))
                  or (xc1 > d.swe_m and xc1 <= d.nwe_m and top(jx) < (yrr - dym))):
                if jx + 1 <= iends and lejos(jx + 1):
                    nx[1] = nx[2] = min(jx + 2, iends)
                    x[1] = x[2] = xc1 + 2.0 * dxm
                    if ierr > -3:
                        aviso()
                    ierr = -3
                    break
                else:
                    ierr = min(ierr, -2)
                    nx[1] = nx[2] = min(jx + 1, iends)
                    x[1] = x[2] = xc1 + dxm
                    break
            elif ((xc1 > d.see_m and xc1 <= d.nee_m and yb[jx] > (yrr + dym))
                  or (xc1 > d.nee_m and xc1 <= d.see_m and top(jx) < (yrr - dym))):
                if jx - 1 >= ibegin and lejos(jx - 1):
                    nx[1] = nx[2] = max(jx - 2, ibegin)
                    x[1] = x[2] = xc1 - 2.0 * dxm
                    if ierr > -3:
                        aviso()
                    ierr = -3
                    break
                else:
                    ierr = min(ierr, -2)
                    nx[1] = nx[2] = max(jx - 1, ibegin)
                    x[1] = x[2] = xc1 - dxm
                    break
            else:
                ierr = min(ierr, -1)
                nx[1] = nx[2] = jx
                x[1] = x[2] = xc1
                break
        elif xc1 < xc2:
            if dentro(jx):
                nx[1] = jx
                x[1] = xc1
                if jx == iends:
                    if xc1 + dxm < xc2:
                        if ierr > -3:
                            aviso()
                        ierr = -3
                    else:
                        ierr = -1
                    nx[2] = jx
                    x[2] = xc1
                    break
                else:
                    continue
            elif ((xc1 + dxm > xc2) and (xc1 > d.nwe_m and xc1 <= d.swe_m
                                          and yb[jx] > (yrr + dym))
                  or (xc1 + dxm > xc2) and (xc1 > d.swe_m and xc1 <= d.nwe_m
                                             and top(jx) < (yrr - dym))):
                if jx + 1 <= iends and lejos(jx + 1):
                    nx[1] = nx[2] = min(jx + 2, iends)
                    x[1] = x[2] = xc1 + 2.0 * dxm
                    if ierr > -3:
                        aviso()
                    ierr = -3
                    break
                else:
                    ierr = min(ierr, -2)
                    nx[1] = nx[2] = min(jx + 1, iends)
                    x[1] = x[2] = xc1 + dxm
                    break
            elif xc1 + dxm > xc2:
                if ierr > -3:
                    aviso()
                ierr = -3
                nx[1] = jx
                x[1] = xc1
                if jx == iends:
                    nx[2] = jx
                    x[2] = xc1
                    break
                else:
                    continue
            elif jx == iends:
                if ierr > -3:
                    aviso()
                ierr = -3
                if dentro(jx):
                    nx[1] = nx[2] = jx
                    x[1] = x[2] = xc1
                else:
                    nx[1] = nx[2] = jx - 1
                    x[1] = x[2] = xc1 - dxm
                break
            else:
                nx[1] = jx
                x[1] = xc1
                continue
    x[4] = x[1]
    x[3] = x[2]
    for ip in (1, 2):
        nxn = nx[ip]
        if nxn < 1 or nxn > ix.n:
            from .estado import AbortoFortran
            raise AbortoFortran(f"FIND4: índice de perfil {nxn} fuera de rango (-fbounds-check)")
        ibeg = max(1, int((yrr - yb[nxn]) / dym))
        iend = nodes[nxn]
        if ibeg > iend:
            ibeg = iend
        yc1 = 0.0
        for inn in range(ibeg, iend + 1):
            if inn == ibeg:
                yc1 = yb[nxn] + (inn - 1) * dym
                yc2 = yrr
            else:
                yc1 = yc1 + dym
            if yc1 > yc2:
                if ny1[ip] <= 0:
                    if yc1 - yc2 > dym:
                        if ierr > -3:
                            aviso()
                        ierr = -3
                    else:
                        ierr = -1
                    ny1[ip] = ny2[ip] = inn
                    yy1 = yy2 = yc1
                    break
                else:
                    ny2[ip] = inn
                    yy2 = yc1
                    break
            elif yc1 == yc2:
                ny2[ip] = ny1[ip] = inn
                yy1 = yy2 = yc1
                break
            elif yc1 < yc2:
                ny1[ip] = inn
                yy1 = yc1
                if inn == nodes[nxn]:
                    if yc2 - yc1 > dym:
                        if ierr > -3:
                            aviso()
                        ierr = -3
                    else:
                        ierr = -1
                    ny2[ip] = inn
                    yy2 = yc1
                    break
        if ip == 1:
            y[1] = yy1
            y[4] = yy2
        else:
            y[2] = yy1
            y[3] = yy2
    e._find4_y = list(y)
    return ierr, nx, ny1, ny2, x, list(y)


def int2d(params, x1, y1, xvalue, yvalue):
    """INT2D: interpolación bilineal entre los cuatro nodos (orden 1-2-3-4 de FIND4)."""
    xvalum = xvalue
    if xvalum > x1[2]:
        xvalum = x1[2]
    elif xvalum < x1[1]:
        xvalum = x1[1]
    yvalum = yvalue
    if yvalum > y1[3]:
        yvalum = y1[3]
    elif yvalum < y1[1]:
        yvalum = y1[1]
    if x1[2] - x1[1] <= 0.0:
        x2mx, xmx1 = 1.0, 0.0
    else:
        xblki = 1.0 / (x1[2] - x1[1])
        x2mx = (x1[2] - xvalum) * xblki
        xmx1 = (xvalum - x1[1]) * xblki
    pint1 = params[1] * x2mx + params[2] * xmx1
    pint2 = params[4] * x2mx + params[3] * xmx1
    if y1[4] - y1[1] <= 0.0:
        y2my, ymy1 = 1.0, 0.0
    else:
        yblki = 1.0 / (y1[4] - y1[1])
        y2my = (y1[4] - yvalum) * yblki
        ymy1 = (yvalum - y1[1]) * yblki
    return pint1 * y2my + pint2 * ymy1
