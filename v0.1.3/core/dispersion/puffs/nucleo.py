# -*- coding: utf-8 -*-
"""Núcleo del modelo de puffs: avance de una hora (numba).

Reglas y procedencia en FUENTES.md del laboratorio (documentación publicada + caja negra). Resumen:
  - Cada puff recorre la hora en nsam pasos de duración 3600/nsam. Puffs nuevos de una fuente: n
    puffs (n = int(u0·3600/(XMXLEN·Δx)) + 1, tope MXNEW), el k-ésimo sale de la fuente al principio
    del paso k. Puffs viejos: nsam = nint(u·3600/(XSAMLEN·Δx)) + 1 (tope MXSAM), con u el viento de
    advección al principio de la hora.
  - Viento de advección: media por espesor de los vientos de capa en [H − σz, H + σz] (uniforme:
    [0, tapa]) en la celda donde empieza el paso. Clase, ZI y L también de esa celda.
  - σ: fuente virtual con PG (rural) o McElroy-Pooler (urbano); en calma (u < WSCALM), funciones de
    Draxler con σv = SVMIN y σw = SWMIN de la clase; Heffter (σy crece 0,5 m/s) desde σy ≥ SYTDEP.
  - Tapa: clases A-D la ZI de la celda; E-F la mayor tapa vista por el puff (sin tapa si nunca la
    tuvo). Puff uniforme cuando σz ≥ 1,6·tapa (σz se congela).
  - Muestreo integrado a lo largo del tramo con σ en el receptor (posición recortada al tramo
    ampliado en ±σy; en calma, σ a mitad de paso), corte a 3σy, terreno por coeficiente de
    trayectoria (MCTADJ=3) y factor Fr para fuentes de área.
  - Fuentes puntuales con sobreelevación: mientras el puff no ha recorrido XFINAL, su altura en cada
    receptor es la de transición en la posición del receptor, a σ² se suma (Δh/3,5)² y el viento de
    transporte es el de la capa que barre al subir (NCOUNT iteraciones). Códigos de puff: 1 dentro de
    la capa de mezcla, 3 por encima (solo llega a receptores sobre la tapa; crece con la clase JSUP),
    5 con parte de la masa por encima de la tapa (QM = Q·QFRAC bajo la tapa PZREF, QU repartida
    hasta PZIMAX).
"""
import math

import numba as nb
import numpy as np

from .muestreo import N_CORTE, fr_area, g_vertical, integral_tramo, integral_tramo_p
from .edificios import dh_ss, dwsigs
from .estela_edificio import (MXNTR, T_DISTC, T_EXC, T_HT, T_LWAK, T_NCAV, T_NWAK, T_SYC, T_SYW, T_SZC,
                    T_SZW, T_XC, T_XT, T_XW, T_ZT)
from .sigmas import HEFFTER_Y, sigma_dist, sigma_tiempo, sigvw, t_virtual, x_virtual
from .sobreelevacion import dh_trans

# columnas del estado de un puff
(PX, PY, PH, PZB, PQ, PSY, PSZ, PSY0, PLC2, PUNI, PZIMAX, PHEF, PVIVO, PQFRAC, PFUENTE, PTIPO,
 PSYI, PSZI, PID, PXTOT,
 # sobreelevación (PH es la altura final; PHS la de salida tras el efecto punta)
 PHS, PFB, PFM, PUS, PBJ, PSQS, PXFB, PXFM, PDHBF, PDHMF, PDM, PDHF, PXF,
 # código del puff (1, 3, 5) y tapa de reflexión de la parte bajo la tapa
 PCOD, PZREF,
 # efecto edificio ISC: método (0, 1 Huber-Snyder, 2 Schulman-Scire), escala de las σ (hb o hw),
 # factor A de σz, término constante de σy' (0 sin aumento), clase de estabilidad y uso urbano de
 # la emisión; elevación de Schulman-Scire (1 sí), radio de dilución y longitud de la fuente lineal
 PDW, PDWESC, PDWA, PDWSYC, PDWK, PDWURB, PSS, PR0, PLY,
 # efecto edificio PRIME: 0 no, 1 penacho principal, 2 fuente de la cavidad; fila de su tabla
 PPRI, PTAB,
 # altura física de la chimenea o de emisión (ajuste de terreno de ISC, MCTADJ = 1)
 PHFIS) = range(47)
NCOL = 47
# masas por especie tras las columnas fijas: QM (bajo la tapa) en PM0 + 2·s y QU (por encima) en
# PM0 + 2·s + 1 (PQ y PQFRAC quedan como referencia de la emisión)
PM0 = NCOL
NTRAZA = 19      # columnas de la traza de depuración
SIN_TAPA = 10000.0
RAIZ_PI_2 = math.sqrt(0.5 * math.pi)
ZS_DEP = 10.0    # m, altura de referencia de la deposición seca

# índices del vector de parámetros
(C_DG, C_NX, C_NY, C_IB, C_IE, C_JB, C_JE, C_XSAMLEN, C_MXSAM, C_WSCALM, C_SYTDEP, C_XMINZI,
 C_XMAXZI, C_IURB1, C_IURB2, C_IWAT1, C_IWAT2, C_MCTADJ, C_NZ, C_CDIV1, C_CDIV2, C_NCOUNT,
 C_JSUP, C_MXNEW, C_CONK1, C_CONK2, C_MDISP, C_MTRANS, C_FAV) = range(29)
NPAR = 29


def ncol(nesp):
    """Columnas del estado de un puff con nesp especies."""
    return NCOL + 2 * nesp


@nb.njit(cache=True)
def _sy(x, k, urb, fav):
    """σy de las curvas de dispersión con el factor de tiempo de promedio (AVET/PGTIME)^0,2."""
    return fav * sigma_dist(x, k, urb, 0)


@nb.njit(cache=True)
def _xvy(sig, k, urb, fav):
    """Distancia virtual de σy con el factor de tiempo de promedio."""
    return x_virtual(sig / fav, k, urb, 0)


@nb.njit(cache=True)
def _nesp(P):
    return (P.shape[1] - NCOL) // 2


@nb.njit(cache=True)
def _mover_qu(P, i, fr):
    """Pasa la fracción fr de la masa por encima de la tapa (QU) a la de debajo (QM)."""
    for s in range(_nesp(P)):
        d = P[i, PM0 + 2 * s + 1] * fr
        P[i, PM0 + 2 * s] += d
        P[i, PM0 + 2 * s + 1] -= d


@nb.njit(cache=True)
def _repartir(P, i, fr):
    """Reparte la masa total de cada especie: fr bajo la tapa (QM) y el resto por encima (QU)."""
    for s in range(_nesp(P)):
        t = P[i, PM0 + 2 * s] + P[i, PM0 + 2 * s + 1]
        P[i, PM0 + 2 * s] = t * fr
        P[i, PM0 + 2 * s + 1] = t - t * fr


@nb.njit(cache=True)
def viento_capa(U, V, zface, ix, iy, zb, zt):
    """Media por espesor de las componentes de capa en [zb, zt]."""
    nz = U.shape[0]
    if zt <= zb:
        zt = zb + 1e-6
    su = 0.0
    sv = 0.0
    sw = 0.0
    for k in range(nz):
        a = max(zb, zface[k])
        b = min(zt, zface[k + 1])
        if b > a:
            su += U[k, iy, ix] * (b - a)
            sv += V[k, iy, ix] * (b - a)
            sw += b - a
    if sw <= 0.0:
        # por encima del techo de la malla: la capa superior
        return U[nz - 1, iy, ix], V[nz - 1, iy, ix]
    return su / sw, sv / sw


@nb.njit(cache=True)
def divergencia(W, zface, ix, iy, zb, zt):
    """Media de dw/dz (1/s) en [zb, zt] con la divergencia de cada capa constante:
    (w de la cara superior − w de la inferior)/espesor, w = 0 en el suelo ([UG] ecs. 2-105, 2-106)."""
    nz = W.shape[0]
    if zt <= zb:
        return 0.0
    s = 0.0
    wb = 0.0
    for k in range(nz):
        wt = W[k, iy, ix]
        a = max(zb, zface[k])
        b = min(zt, zface[k + 1])
        if b > a:
            s += (wt - wb) / (zface[k + 1] - zface[k]) * (b - a)
        wb = wt
    return s / (zt - zb)


@nb.njit(cache=True)
def celda(x, y, nx, ny):
    ix = int(math.floor(x))
    iy = int(math.floor(y))
    return min(max(ix, 0), nx - 1), min(max(iy, 0), ny - 1)


@nb.njit(cache=True)
def _sig_rec_dist(sb, xb, s_ef, k, urb, eje, hef, ws):
    if hef:
        return sb + HEFFTER_Y * s_ef / ws
    return sigma_dist(max(xb + s_ef, 1e-3), k, urb, eje)


@nb.njit(cache=True)
def en_ascenso(P, i):
    """¿Está el puff en la fase de elevación de transición (aún no ha recorrido XFINAL)?"""
    return P[i, PXF] > 0.0 and P[i, PXTOT] < P[i, PXF]


@nb.njit(cache=True)
def _interp_tab(TB, k, c0, cy, n, x):
    """Interpolación lineal en la columna cy de la tabla k frente a la c0 (n puntos)."""
    for j in range(n - 2, -1, -1):
        if x >= TB[k, c0 + j]:
            x0 = TB[k, c0 + j]
            x1 = TB[k, c0 + j + 1]
            y1 = TB[k, cy + j + 1]
            return y1 - (y1 - TB[k, cy + j]) * (x1 - x) / (x1 - x0)
    return TB[k, cy]


@nb.njit(cache=True)
def _sig_mas_alla(s_fin, x_fin, x, kd, urb, eje):
    """σ más allá del final de una tabla: crecimiento con la clase del paso desde la σ del final."""
    xv = x_virtual(s_fin, kd, urb, eje)
    if xv < 0.0:
        return s_fin
    return sigma_dist(xv + (x - x_fin), kd, urb, eje)


@nb.njit(cache=True)
def sig_prime(P, i, TB, x, kd, urb):
    """σy, σz de un puff PRIME a la distancia x de su origen (chimenea o fuente de la cavidad): la
    tabla de la estela o de la cavidad mientras dura y, más allá, el crecimiento con la clase del
    paso desde la σ del final de la tabla (caja negra)."""
    k = int(P[i, PTAB])
    if P[i, PPRI] < 1.5:
        n = int(TB[k, T_NWAK])
        xf = TB[k, T_XW + n - 1]
        if x <= xf:
            return (_interp_tab(TB, k, T_XW, T_SYW, n, x), _interp_tab(TB, k, T_XW, T_SZW, n, x))
        return (_sig_mas_alla(TB[k, T_SYW + n - 1], xf, x, kd, urb, 0),
                _sig_mas_alla(TB[k, T_SZW + n - 1], xf, x, kd, urb, 1))
    n = int(TB[k, T_NCAV])
    xs = x + TB[k, T_DISTC]
    xf = TB[k, T_XC + n - 1]
    if xs <= xf:
        return (_interp_tab(TB, k, T_XC, T_SYC, n, xs), _interp_tab(TB, k, T_XC, T_SZC, n, xs))
    return (_sig_mas_alla(TB[k, T_SYC + n - 1], xf, xs, kd, urb, 0),
            _sig_mas_alla(TB[k, T_SZC + n - 1], xf, xs, kd, urb, 1))


@nb.njit(cache=True)
def en_tabla(P, i, TB):
    """¿Sigue el puff PRIME dentro de su tabla de σ (al principio del paso)?"""
    if P[i, PPRI] < 0.5:
        return False
    k = int(P[i, PTAB])
    if P[i, PPRI] < 1.5:
        if TB[k, T_LWAK] < 0.5:
            # sin estela: crecimiento normal del puff desde σ0 (caja negra)
            return False
        return P[i, PXTOT] < TB[k, T_XW + int(TB[k, T_NWAK]) - 1]
    return P[i, PXTOT] + TB[k, T_DISTC] < TB[k, T_XC + int(TB[k, T_NCAV]) - 1]


@nb.njit(cache=True)
def altura(P, i, x, TB):
    """Altura del puff (m) cuando ha recorrido x m: la de salida más la elevación de transición
    (la final más allá de XFINAL o si la elevación es inmediata); con PRIME, la trayectoria
    tabulada."""
    if P[i, PXF] <= 0.0 or x >= P[i, PXF]:
        return P[i, PH]
    if P[i, PPRI] > 0.5:
        k = int(P[i, PTAB])
        return _interp_tab(TB, k, T_XT, T_ZT, MXNTR, x)
    if P[i, PSS] > 0.5:
        # Schulman-Scire (efecto edificio): cúbica con radio de dilución y fuente lineal
        if x <= 0.0:
            return P[i, PHS]
        return P[i, PHS] + min(dh_ss(x, P[i, PFB], P[i, PFM], P[i, PUS], P[i, PBJ], P[i, PSQS],
                                     P[i, PXFB], P[i, PXFM], P[i, PR0], P[i, PLY]), P[i, PDHF])
    return P[i, PHS] + dh_trans(x, P[i, PFB], P[i, PFM], P[i, PUS], P[i, PBJ], P[i, PSQS],
                                P[i, PXFB], P[i, PXFM], P[i, PDHBF], P[i, PDHMF], P[i, PDM],
                                P[i, PDHF])


@nb.njit(cache=True)
def techo_capa(P, i, k0, zi0):
    """Techo de la capa de advección: la ZI de la celda (A-D), la tapa heredada (E-F); sin recorte
    para los puffs por encima de la capa de mezcla (código 3)."""
    if P[i, PCOD] == 3:
        return SIN_TAPA
    if k0 <= 4:
        return zi0
    return P[i, PZREF] if P[i, PCOD] == 5 else P[i, PZIMAX]


@nb.njit(cache=True)
def viento_ascenso(P, i, U, V, zface, ix, iy, sz, techo, tsamp, ncount, TB):
    """Viento de transporte de un paso con elevación de transición (caja negra): viento de la capa
    final [H − σz, H + σz]; primera estimación con el de la altura actual; después, NCOUNT veces,
    el de la capa barrida [h(x0) − σz, h(x1) + σz] con x1 = x0 + u·Δt, y si el paso cruza XFINAL la
    media xf·u_ascenso + (x1 − xf)·u_final entre x1."""
    hf = P[i, PH]
    uf, vf = viento_capa(U, V, zface, ix, iy, max(0.0, hf - sz), min(hf + sz, techo))
    xb = P[i, PXTOT]
    hb = altura(P, i, xb, TB)
    u, v = viento_capa(U, V, zface, ix, iy, max(0.0, hb - sz), min(hb + sz, techo))
    xf = P[i, PXF]
    for _ in range(ncount):
        xe = xb + math.sqrt(u * u + v * v) * tsamp
        he = altura(P, i, xe, TB)
        ug, vg = viento_capa(U, V, zface, ix, iy, max(0.0, min(hb, he) - sz),
                             min(max(hb, he) + sz, techo))
        if xe > xf:
            wg = xf / xe
            u = wg * ug + (1.0 - wg) * uf
            v = wg * vg + (1.0 - wg) * vf
        else:
            u, v = ug, vg
    return u, v


@nb.njit(cache=True)
def paso(P, i, tsamp, U, V, W, zface, IPGT, ZI, EL, ILU, svmin, swmin, ppc, par, xr, yr, zr, zp,
         conc, peso, lmax, ids, traza, ntr, nsam, ipaso, rdbg, cdbg, TB, EXC, DEP, M2, dflx, wflx):
    """Avanza el puff i un paso de muestreo de tsamp s y muestrea los receptores. lmax: recorrido
    máximo del paso (m) antes de partirlo en subpasos. DEP (2·nesp + 2, ny, nx): velocidad de
    deposición seca y tasa de lavado de cada especie por celda, u* y w*; conc, dflx, wflx
    (nrec, nesp): concentración y flujos seco y húmedo acumulados."""
    dg = par[C_DG]
    nx = int(par[C_NX])
    ny = int(par[C_NY])
    ix, iy = celda(P[i, PX], P[i, PY], nx, ny)
    # celda inicial: viento de advección y techo de la capa de advección
    k0 = min(max(IPGT[iy, ix], 1), 6)
    zi0 = min(max(ZI[iy, ix], par[C_XMINZI]), par[C_XMAXZI])
    h = P[i, PH]
    sy = P[i, PSY]
    sz = P[i, PSZ]
    sz_pre = sz
    fdiv = 1.0
    uni = P[i, PUNI] > 0.5
    ascenso = en_ascenso(P, i)
    # ── viento de advección: capa del puff recortada a la ZI actual (clases A-D) o a la tapa
    #    heredada (E-F); en la elevación de transición, el de la capa que barre al subir ──
    techo = techo_capa(P, i, k0, zi0)
    if uni:
        # el puff uniforme ocupa [0, ZIMAX] y se advecta con la media de toda esa capa
        u, v = viento_capa(U, V, zface, ix, iy, 0.0, P[i, PZIMAX])
    elif ascenso:
        u, v = viento_ascenso(P, i, U, V, zface, ix, iy, sz, techo, tsamp, int(par[C_NCOUNT]), TB)
    else:
        u, v = viento_capa(U, V, zface, ix, iy, max(0.0, h - sz), min(h + sz, techo))
    ws = math.sqrt(u * u + v * v)
    calma = ws < par[C_WSCALM]
    if calma and ascenso:
        # en calma el puff alcanza de inmediato su elevación final (caja negra)
        P[i, PXF] = 0.0
        ascenso = False
    if calma:
        if abs(u) < 1e-3:
            u = 1e-3
        if abs(v) < 1e-3:
            v = 1e-3
        ws = math.sqrt(u * u + v * v)
    # subpaso: el puff no avanza más de lmax; el tiempo sobrante pasa al paso siguiente
    if ws * tsamp > lmax:
        tsamp = lmax / ws
    peso = tsamp / 3600.0 if peso > 0.0 else 0.0
    ds = ws * tsamp
    x1 = P[i, PX] * dg
    y1 = P[i, PY] * dg
    ddx = u * tsamp
    ddy = v * tsamp
    # la clase, ZI, L y el uso del suelo (curvas urbanas o rurales, mínimos de agua) se toman en la
    # celda del punto medio del paso; el viento en la inicial; la divergencia en la inicial y la final
    # (caja negra)
    ixe, iye = celda(P[i, PX] + ddx / dg, P[i, PY] + ddy / dg, nx, ny)
    ixm, iym = celda(P[i, PX] + 0.5 * ddx / dg, P[i, PY] + 0.5 * ddy / dg, nx, ny)
    k = min(max(IPGT[iym, ixm], 1), 6)
    zi = min(max(ZI[iym, ixm], par[C_XMINZI]), par[C_XMAXZI])
    estable = EL[iym, ixm] > 0.0
    lu = abs(ILU[iym, ixm])
    urb = par[C_IURB1] <= lu <= par[C_IURB2]
    agua = par[C_IWAT1] <= lu <= par[C_IWAT2]
    # ── estiramiento vertical por divergencia de w ([UG] sec. 2.2.6; caja negra: máximo entre la
    #    celda inicial y la final del paso, aplicado a σz antes de crecer) ──
    if not uni:
        zb_ = max(0.0, h - sz)
        zt_ = min(h + sz, techo)
        dmx = max(divergencia(W, zface, ix, iy, zb_, zt_), divergencia(W, zface, ixe, iye, zb_, zt_))
        if dmx > par[C_CDIV1]:
            if par[C_CDIV2] > par[C_CDIV1]:
                ftr = min(1.0, (dmx - par[C_CDIV1]) / (par[C_CDIV2] - par[C_CDIV1]))
            else:
                ftr = 1.0
            fdiv = 1.0 + tsamp * ftr * dmx
            sz = sz * fdiv
    # ── tapa de mezcla y código del puff (con la σz ya estirada; caja negra) ──
    cod = P[i, PCOD]
    if k <= 4:
        if cod == 3:
            if zi > h:
                # la capa de mezcla alcanza el centro del puff: entra la parte del sombrero de copa
                # [H − √(π/2)·σz, H + √(π/2)·σz] que queda bajo ZI
                zt = h + RAIZ_PI_2 * sz
                fr = (zi - (h - RAIZ_PI_2 * sz)) / (2.0 * RAIZ_PI_2 * sz) if sz > 0.0 else 1.0
                if fr >= 1.0:
                    cod = 1.0
                    _repartir(P, i, 1.0)
                    P[i, PZIMAX] = zi
                else:
                    cod = 5.0
                    _repartir(P, i, max(fr, 0.0))
                    P[i, PZIMAX] = zt
                    P[i, PZREF] = zi
            else:
                P[i, PZIMAX] = zi
                P[i, PZREF] = zi
            tapa = zi
        elif cod == 5:
            if zi >= P[i, PZIMAX]:
                cod = 1.0
                _mover_qu(P, i, 1.0)
                P[i, PZIMAX] = zi
                tapa = zi
            else:
                if zi > P[i, PZREF]:
                    # la capa de mezcla crece: entra la parte de QU (repartida entre la tapa y
                    # ZIMAX) que queda bajo la nueva ZI
                    _mover_qu(P, i, (zi - P[i, PZREF]) / (P[i, PZIMAX] - P[i, PZREF]))
                    P[i, PZREF] = zi
                tapa = P[i, PZREF]
        elif not uni and h > zi:
            # puff por encima de la ZI actual que estuvo debajo: conserva su tapa y su masa
            cod = 5.0
            P[i, PZREF] = P[i, PZIMAX]
            tapa = P[i, PZREF]
        elif uni:
            P[i, PZIMAX] = max(P[i, PZIMAX], zi) if P[i, PZIMAX] < SIN_TAPA else zi
            _repartir(P, i, min(1.0, zi / P[i, PZIMAX]))
            tapa = zi
        elif zi >= P[i, PZIMAX]:
            P[i, PZIMAX] = zi
            tapa = zi
        else:
            # ZI por debajo de la tapa que tenía el puff (o sin tapa, si nació en clase E-F): nueva
            # tapa H + √(π/2)·σz, sin pasar de la anterior ni bajar de ZI
            tapa = max(zi, min(P[i, PZIMAX], h + RAIZ_PI_2 * sz))
            P[i, PZIMAX] = tapa
    else:
        if cod == 3:
            # en estable el puff deja de estar «por encima»: toda la masa, sin tapa
            cod = 1.0
            _repartir(P, i, 1.0)
            P[i, PZIMAX] = SIN_TAPA
            tapa = SIN_TAPA
        elif cod == 5:
            tapa = P[i, PZREF]
        else:
            tapa = P[i, PZIMAX]
            if uni:
                _repartir(P, i, 1.0)
    P[i, PCOD] = cod
    if cod == 1:
        P[i, PZREF] = P[i, PZIMAX]
    # paso a mezcla uniforme con la σz ya estirada
    if not uni and cod != 3 and tapa < SIN_TAPA and sz >= 1.6 * tapa:
        P[i, PUNI] = 1.0
        if cod == 5:
            # código 6: QM uniforme bajo su tapa, QU sigue repartida hasta ZIMAX
            pass
        else:
            P[i, PZIMAX] = tapa
            P[i, PZREF] = tapa
            if k <= 4:
                # la masa útil es la que queda bajo la ZI actual, que hace de tapa
                _repartir(P, i, min(1.0, zi / tapa))
                tapa = zi
            else:
                _repartir(P, i, 1.0)
        uni = True
    # clase de crecimiento: JSUP para los puffs por encima de la capa de mezcla (A-D)
    kd = k
    if k <= 4 and not uni and h > zi:
        kd = int(par[C_JSUP])
    # clase para las curvas de dispersión: 7-12 selecciona las de MESOPUFF II (MDISP = 4)
    kc = kd + 6 if par[C_MDISP] == 4.0 else kd
    # tiempo de promedio de σy (AVET/PGTIME)^0,2 en las curvas PG ([UG] ec. 2-72)
    fav = par[C_FAV]
    # ── crecimiento de σ ──
    hef = P[i, PHEF] > 0.5
    sytdep = par[C_SYTDEP]
    tiempo = par[C_MDISP] == 2.0 and not calma
    # altura para σv, σw: la de salida en el primer paso de un puff con elevación de transición y la
    # final después (caja negra: SIGWV)
    zturb = h
    sv_t = 0.0
    sw_t = 0.0
    tyb = 0.0
    tzb = 0.0
    if calma:
        sv = svmin[kd - 1 + (6 if agua else 0)]
        sw = swmin[kd - 1 + (6 if agua else 0)]
        if par[C_MDISP] == 2.0:
            # MDISP = 2: en calma, la turbulencia de la micrometeorología con los mínimos (caja negra)
            sv_c, sw_c = sigvw(zturb, zi, M2[0, iym, ixm], M2[1, iym, ixm], EL[iym, ixm])
            sv = max(sv, sv_c)
            sw = max(sw, sw_c)
        tzb = t_virtual(sz, sw, 1, estable)
        if uni or tzb < 0.0:
            sz_e = sz
            sz_m = sz
        else:
            sz_e = sigma_tiempo(tzb + tsamp, sw, 1, estable)
            sz_m = sigma_tiempo(tzb + 0.5 * tsamp, sw, 1, estable)
        if hef:
            sy_e = sy + HEFFTER_Y * tsamp
            sy_m = sy + HEFFTER_Y * 0.5 * tsamp
        else:
            tyb = max(t_virtual(sy, sv, 0, estable), 0.0)
            sy_e = sigma_tiempo(tyb + tsamp, sv, 0, estable)
            sy_m = sigma_tiempo(tyb + 0.5 * tsamp, sv, 0, estable)
            if sy_e > sytdep:
                tc = t_virtual(sytdep, sv, 0, estable) - tyb
                sy_e = sytdep + HEFFTER_Y * (tsamp - tc)
                if sy_m > sytdep:
                    sy_m = sytdep + HEFFTER_Y * (0.5 * tsamp - tc)
                P[i, PHEF] = 1.0
        xyb = 0.0
        xzb = 0.0
    elif tiempo:
        # MDISP = 2: crecimiento con el tiempo, σ = σv·t·fy(t) y σw·t·fz(t) (funciones de Draxler),
        # con σv y σw de la micrometeorología a la altura del puff (mínimos SVMIN/SWMIN) y el tiempo
        # virtual del tamaño actual ([UG] ecs. 2-39, 2-40, 2-52 a 2-67; caja negra: SIGWV)
        sv_t, sw_t = sigvw(zturb, zi, M2[0, iym, ixm], M2[1, iym, ixm], EL[iym, ixm])
        sv_t = max(sv_t, svmin[kd - 1 + (6 if agua else 0)])
        sw_t = max(sw_t, swmin[kd - 1 + (6 if agua else 0)])
        tzb = t_virtual(sz, sw_t, 1, estable)
        sz_e = sz if (uni or tzb < 0.0) else sigma_tiempo(tzb + tsamp, sw_t, 1, estable)
        if hef:
            tyb = 0.0
            sy_e = sy + HEFFTER_Y * tsamp
        else:
            tyb = max(t_virtual(sy, sv_t, 0, estable), 0.0)
            sy_e = sigma_tiempo(tyb + tsamp, sv_t, 0, estable)
            if sy_e > sytdep:
                tc = t_virtual(sytdep, sv_t, 0, estable) - tyb
                sy_e = sytdep + HEFFTER_Y * (tsamp - tc)
                P[i, PHEF] = 1.0
        xyb = 0.0
        xzb = 0.0
        sy_m = 0.0
        sz_m = 0.0
    else:
        xzb = x_virtual(sz, kc, urb, 1)
        sz_e = sz if (uni or xzb < 0.0) else sigma_dist(xzb + ds, kc, urb, 1)
        if hef:
            xyb = 0.0
            sy_e = sy + HEFFTER_Y * tsamp
        else:
            xyb = _xvy(sy, kc, urb, fav)
            sy_e = _sy(xyb + ds, kc, urb, fav)
            if sy_e > sytdep:
                tc = (_xvy(sytdep, kc, urb, fav) - xyb) / ws
                sy_e = sytdep + HEFFTER_Y * (tsamp - tc)
                P[i, PHEF] = 1.0
        sy_m = 0.0
        sz_m = 0.0
    # PRIME: dentro de la tabla, la σ al final del paso es la de la tabla (o la de la curva desde
    # la distancia virtual al salir de ella) en la distancia total recorrida (caja negra)
    tab = (not calma) and en_tabla(P, i, TB)
    if tab:
        sy_e, sz_e = sig_prime(P, i, TB, P[i, PXTOT] + ds, kc, urb)
    sy0sq = P[i, PSY0]
    syb_t = math.sqrt(sy * sy + sy0sq)
    sye_t = math.sqrt(sy_e * sy_e + sy0sq)
    # ── masas por especie al principio y al final del paso: lavado (QM y QU) y deposición seca (solo
    #    QM), [UG] secs. 2.7.1 y 2.9; la masa varía linealmente a lo largo del tramo en el muestreo
    #    ([UG] ecs. 2-6 a 2-10) ──
    nesp = _nesp(P)
    qm0 = np.empty(nesp)
    qu0 = np.empty(nesp)
    qm1 = np.empty(nesp)
    qu1 = np.empty(nesp)
    vdp = np.zeros(nesp)
    fcs = np.ones(nesp)
    lam = np.zeros(nesp)
    fws = np.ones(nesp)      # fracción que deja el lavado (los flujos se calculan por procesos en orden:
    fds = np.ones(nesp)      # primero el lavado y después la deposición seca; caja negra)
    for s in range(nesp):
        qm0[s] = P[i, PM0 + 2 * s]
        qu0[s] = P[i, PM0 + 2 * s + 1]
        qm1[s] = qm0[s]
        qu1[s] = qu0[s]
    cambia = False
    if DEP.shape[0] == 2 * nesp + 2:
        # lavado: Λ de la celda donde empieza el paso (como vd; caja negra), sobre toda la masa
        # ([UG] ec. 2-267)
        for s in range(nesp):
            lam[s] = DEP[nesp + s, iy, ix]
            if lam[s] > 0.0:
                fw = math.exp(-lam[s] * tsamp)
                fws[s] = fw
                qm1[s] *= fw
                qu1[s] *= fw
                cambia = True
        # deposición seca de la masa bajo la tapa: Q(t + Δt) = Q(t)·exp(−vd'·Δt·ḡ), con ḡ la media
        # del término vertical en el suelo al principio, a mitad y al final del paso (caja negra)
        if cod != 3:
            if uni:
                geff = 1.0 / tapa
                us_ = DEP[2 * nesp, iy, ix]
                db = par[C_CONK1] * us_ * tapa
                if k <= 4:
                    db = max(db, par[C_CONK2] * DEP[2 * nesp + 1, iy, ix] * tapa)
            else:
                if calma:
                    szd = sz_m
                elif tiempo:
                    szd = sz if tzb < 0.0 else sigma_tiempo(tzb + 0.5 * tsamp, sw_t, 1, estable)
                elif xzb < 0.0:
                    szd = sz
                else:
                    szd = sigma_dist(xzb + 0.5 * ds, kc, urb, 1)
                szb_ = sz
                if tab:
                    # PRIME: σz de la tabla en los tres puntos (caja negra)
                    szb_ = sig_prime(P, i, TB, P[i, PXTOT], kc, urb)[1]
                    szd = sig_prime(P, i, TB, P[i, PXTOT] + 0.5 * ds, kc, urb)[1]
                # con la altura final del puff y la dispersión por flotación de la elevación final
                # (Δhf/3,5)² también durante la elevación de transición (caja negra)
                bdep = 0.0
                if P[i, PTIPO] == 1 and P[i, PSS] < 0.5:
                    if P[i, PPRI] < 0.5:
                        bdep = (h - P[i, PHS]) / 3.5
                    elif P[i, PPRI] < 1.5 and TB[int(P[i, PTAB]), T_LWAK] < 0.5:
                        bdep = TB[int(P[i, PTAB]), T_HT + MXNTR - 1] / 3.5
                b2 = bdep * bdep
                # altura sobre el terreno bajo el puff (coeficiente de trayectoria con la cota de la
                # celda donde empieza el paso; caja negra)
                hd = h
                if par[C_MCTADJ] == 3.0:
                    dzt = M2[2, iy, ix] - P[i, PZB]
                    hd = ppc[k - 1] * h if dzt > h else h - dzt * (1.0 - ppc[k - 1])
                lid = tapa if hd <= tapa else SIN_TAPA
                geff = (g_vertical(hd, 0.0, math.sqrt(szb_ * szb_ + b2), lid)
                        + g_vertical(hd, 0.0, math.sqrt(szd * szd + b2), lid)
                        + g_vertical(hd, 0.0, math.sqrt(sz_e * sz_e + b2), lid)) / 3.0
                db = 0.0
            for s in range(nesp):
                vd = DEP[s, iy, ix]
                if vd > 0.0 and qm0[s] > 0.0:
                    # puff uniforme: resistancia de la capa de mezcla ([UG] ecs. 2-231 a 2-234)
                    vdp[s] = vd * db / (db + vd * (tapa - ZS_DEP)) if uni else vd
                    # puff uniforme: la concentración en los receptores es la de la superficie,
                    # χs = χm·vd'/vd (caja negra; el flujo vd·χs = vd'·χm)
                    fcs[s] = vdp[s] / vd
                    fds[s] = math.exp(-vdp[s] * tsamp * geff)
                    qm1[s] *= fds[s]
                    cambia = True
    # ── muestreo: QM bajo la tapa y QU (códigos 3 y 5) solo en receptores por encima de ella ──
    if peso > 0.0:
        con_qu = cod == 5 or cod == 3
        sys_ = math.sqrt(sy0sq)
        area = P[i, PTIPO] == 3
        cpp = ppc[k - 1]
        mct = par[C_MCTADJ]
        # dispersión inducida por la flotación: (Δh/3,5)² en σy² y σz² ([UG] sec. 2.2.2)
        puntual = P[i, PTIPO] == 1
        # sin dispersión por flotación con Schulman-Scire ([UG] sec. 2.2.2) ni con PRIME (las σ de
        # sus tablas ya la incluyen)
        kt = int(P[i, PTAB]) if P[i, PPRI] > 0.5 else -1
        # PRIME sin entrada en la estela: flotación con la elevación tabulada sin el descenso de las
        # líneas de corriente; en el primer paso, la del primer punto (caja negra)
        bidpri = P[i, PPRI] > 0.5 and P[i, PPRI] < 1.5 and TB[kt, T_LWAK] < 0.5
        primero = bidpri and P[i, PXTOT] <= 0.0
        nobid = P[i, PSS] > 0.5 or (P[i, PPRI] > 0.5 and not bidpri)
        fexc = int(TB[kt, T_EXC]) if kt >= 0 else -1
        x0c = P[i, PXTOT] + (TB[kt, T_DISTC] if P[i, PPRI] > 1.5 else 0.0)
        bidf = (h - P[i, PHS]) / 3.5 if (puntual and not nobid) else 0.0
        if bidpri:
            bidf = (TB[kt, T_HT] if primero else TB[kt, T_HT + MXNTR - 1]) / 3.5
        # σy total (con la flotación de la elevación final) al principio y al final del tramo:
        # recorte de la posición del receptor a lo largo del tramo (caja negra)
        syb_c = math.sqrt(syb_t * syb_t + bidf * bidf)
        sye_c = math.sqrt(sye_t * sye_t + bidf * bidf)
        smax = max(syb_c, sye_c) * N_CORTE
        for r in range(xr.shape[0]):
            rx = xr[r] - x1
            ry = yr[r] - y1
            # descarte rápido por caja
            if rx < min(0.0, ddx) - smax or rx > max(0.0, ddx) + smax:
                continue
            if ry < min(0.0, ddy) - smax or ry > max(0.0, ddy) + smax:
                continue
            if ds > 0.0:
                s_r = (rx * ddx + ry * ddy) / ds
            else:
                s_r = 0.0
            sp = min(max(s_r, 0.0), ds)
            px = sp * ddx / ds if ds > 0.0 else 0.0
            py = sp * ddy / ds if ds > 0.0 else 0.0
            rmin = math.sqrt((rx - px) ** 2 + (ry - py) ** 2)
            s_ef = min(max(s_r, -min(syb_c, P[i, PXTOT])), ds + sye_c)
            if fexc >= 0 and x0c + s_ef < EXC[fexc, r]:
                # PRIME: receptor en la zona de la cavidad de la fuente en esta hora y punto de
                # evaluación (desde la chimenea) aún dentro de ella: lo representa CAV_CONC (caja negra)
                continue
            # altura del puff en el receptor: la de transición en la posición del receptor a lo
            # largo del tramo, también tras XFINAL para los receptores que quedan por detrás (caja
            # negra: «Trans. Rise» y «Time to receptor»)
            hr = h
            bid = bidf
            if P[i, PXF] > 0.0:
                s_ef = min(max(s_r, -min(syb_c, P[i, PXTOT])), ds + sye_c)
                hr = altura(P, i, P[i, PXTOT] + s_ef, TB)
                bid = 0.0 if nobid else (hr - P[i, PHS]) / 3.5
                if bidpri:
                    if primero:
                        bid = TB[kt, T_HT] / 3.5
                    elif P[i, PXTOT] + s_ef >= TB[kt, T_XT + MXNTR - 1]:
                        bid = TB[kt, T_HT + MXNTR - 1] / 3.5
                    else:
                        bid = _interp_tab(TB, kt, T_XT, T_HT, MXNTR, P[i, PXTOT] + s_ef) / 3.5
                if par[C_MTRANS] == 0.0:
                    # MTRANS = 0: altura final en los receptores, con la flotación de la elevación de
                    # transición en la dispersión (convención de ISC3; [UG] sec. 2.2.2; caja negra)
                    hr = h
            # σ en el receptor
            if calma:
                syr0 = sy_m
                szr = sz_m
            else:
                # recorte del tramo ampliado: ni más de σy por detrás del inicio ni más atrás que la
                # fuente (distancia total recorrida por el puff)
                s_ef = min(max(s_r, -min(syb_c, P[i, PXTOT])), ds + sye_c)
                if hef:
                    syr0 = sy + HEFFTER_Y * s_ef / ws
                elif tiempo:
                    syr0 = sigma_tiempo(max(tyb + s_ef / ws, 1e-3), sv_t, 0, estable)
                    if syr0 > sytdep and sy_e > sytdep and sy < sytdep:
                        syr0 = sytdep + HEFFTER_Y * (tyb + s_ef / ws - t_virtual(sytdep, sv_t, 0, estable))
                else:
                    syr0 = _sy(max(xyb + s_ef, 1e-3), kc, urb, fav)
                    if syr0 > sytdep and sy_e > sytdep and sy < sytdep:
                        xc = _xvy(sytdep, kc, urb, fav)
                        syr0 = sytdep + HEFFTER_Y * (xyb + s_ef - xc) / ws
                if tiempo:
                    szr = sz if (uni or tzb < 0.0) else sigma_tiempo(max(tzb + s_ef / ws, 1e-3), sw_t, 1,
                                                                   estable)
                elif uni or xzb < 0.0:
                    szr = sz
                else:
                    szr = sigma_dist(max(xzb + s_ef, 1e-3), kc, urb, 1)
                if tab:
                    # PRIME: σ de la tabla de la estela o de la cavidad
                    syr0, szr = sig_prime(P, i, TB, max(P[i, PXTOT] + s_ef, 0.0), kc, urb)
                if P[i, PDW] > 0.5:
                    # efecto edificio ISC: con el receptor a menos de 10·esc del origen, σ del
                    # edificio (o la ambiental si es mayor) en la distancia real, con la clase de
                    # estabilidad de la emisión (caja negra)
                    xdw = P[i, PXTOT] + s_ef
                    if xdw < 10.0 * P[i, PDWESC]:
                        syr0, szr = dwsigs(xdw, P[i, PDWESC], P[i, PDWA], P[i, PDWSYC],
                                           int(P[i, PDWK]), P[i, PDWURB] > 0.5)
                # la σ en el receptor no baja del tamaño inicial del puff (receptores a barlovento;
                # con efecto edificio, de SYMIN/SZMIN; con las tablas de PRIME, sin mínimo)
                if not tab:
                    syr0 = max(syr0, P[i, PSYI])
                    szr = max(szr, P[i, PSZI])
                elif syr0 <= 0.0 or szr <= 0.0:
                    continue
            syr = math.sqrt(syr0 * syr0 + sy0sq + bid * bid)
            szr = math.sqrt(szr * szr + bid * bid)
            # corte a 3σy con la σy total del receptor; más allá del final del tramo, la del final
            # (caja negra)
            syc = syr
            if not calma and s_ef > ds:
                if hef:
                    syc0 = sy + HEFFTER_Y * ds / ws
                elif tiempo:
                    syc0 = sy_e
                else:
                    syc0 = _sy(max(xyb + ds, 1e-3), kc, urb, fav)
                    if syc0 > sytdep and sy_e > sytdep and sy < sytdep:
                        syc0 = sytdep + HEFFTER_Y * (xyb + ds - _xvy(sytdep, kc, urb, fav)) / ws
                if tab:
                    syc0 = sig_prime(P, i, TB, P[i, PXTOT] + ds, kc, urb)[0]
                syc0 = max(syc0, P[i, PSYI])
                bidc = bidf
                if bidpri and not primero:
                    # PRIME sin estela: flotación de la elevación al final del tramo (caja negra)
                    xc_ = P[i, PXTOT] + ds
                    if xc_ >= TB[kt, T_XT + MXNTR - 1]:
                        bidc = TB[kt, T_HT + MXNTR - 1] / 3.5
                    else:
                        bidc = _interp_tab(TB, kt, T_XT, T_HT, MXNTR, xc_) / 3.5
                syc = math.sqrt(syc0 * syc0 + sy0sq + bidc * bidc)
            if rmin > N_CORTE * syc:
                continue
            a = ds * ds / (syr * syr)
            b = -(rx * ddx + ry * ddy) / (syr * syr)
            c = (rx * rx + ry * ry) / (syr * syr)
            i1 = integral_tramo(a, b, c)
            if i1 <= 0.0:
                continue
            # altura del puff en el receptor (coeficiente de trayectoria)
            hp = hr
            if mct == 3:
                dz = zr[r] - P[i, PZB]
                if dz > hr:
                    hp = cpp * hr
                else:
                    hp = hr - dz * (1.0 - cpp)
            elif mct == 1:
                # ajuste de ISC: el terreno por encima de la chimenea se recorta a 0,005 m por debajo de
                # su altura y el eje del puff baja la cota del receptor sobre la base ([UG] sec. 2.6.2.1)
                dz = min(zr[r] - P[i, PZB], P[i, PHFIS] - 0.005)
                hp = hr - dz
            # término vertical: QM con reflexiones bajo la tapa (nada por encima de ella); QU
            # uniforme entre la tapa y ZIMAX (código 5) o gaussiana libre (código 3) (caja negra:
            # «vcoup f1, f1up»)
            if uni:
                g = 1.0 / tapa if zp[r] <= tapa else 0.0
            elif hp <= tapa:
                g = g_vertical(hp, zp[r], szr, tapa) if zp[r] <= tapa else 0.0
            else:
                g = g_vertical(hp, zp[r], szr, SIN_TAPA)
            gu = 0.0
            if con_qu and zp[r] > tapa:
                if cod == 5:
                    gu = 1.0 / (P[i, PZIMAX] - tapa) if zp[r] <= P[i, PZIMAX] else 0.0
                else:
                    gu = math.exp(-0.5 * ((hp - zp[r]) / szr) ** 2) / (math.sqrt(2.0 * math.pi) * szr)
            suelo = zp[r] == 0.0
            if g <= 0.0 and gu <= 0.0 and not (suelo and cambia):
                continue
            fr = fr_area(rmin, syr, sys_, P[i, PLC2]) if area else 1.0
            base = peso / (2.0 * math.pi * syr * syr) * fr
            i2 = integral_tramo_p(a, b, c, i1) if cambia else 0.0
            dc = 0.0
            for s in range(nesp):
                mq = qm0[s] * i1 + (qm1[s] - qm0[s]) * i2
                mu = qu0[s] * i1 + (qu1[s] - qu0[s]) * i2
                d_ = base * (mq * g * fcs[s] + (mu * gu if con_qu else 0.0))
                conc[r, s] += d_
                if s == 0:
                    dc = d_
                if suelo:
                    # flujos solo en los receptores en el suelo (caja negra): húmedo Λ·∫C dz con la
                    # masa que varía por el lavado, toda la columna (también la masa por encima de la
                    # tapa del puff uniforme, código 6); seco vd'·C con la masa que ya ha perdido el
                    # lavado y varía por la deposición seca
                    if lam[s] > 0.0:
                        wq = (qm0[s] + qu0[s]) * (i1 + (fws[s] - 1.0) * i2)
                        wflx[r, s] += lam[s] * base * wq
                    if vdp[s] > 0.0:
                        dq = qm0[s] * fws[s] * (i1 + (fds[s] - 1.0) * i2)
                        dflx[r, s] += vdp[s] * base * dq * g
            q = qm0[0] if nesp > 0 else 0.0
            if r == rdbg:
                cdbg[int(P[i, PID])] += dc
            if ids.shape[0] > 0 and ntr[0] < traza.shape[0]:
                # traza por receptor (primera columna negativa): altura, σ, Δt y contribución
                for q_ in range(ids.shape[0]):
                    if ids[q_] == P[i, PID]:
                        f_ = ntr[0]
                        traza[f_, 0] = -P[i, PID]
                        traza[f_, 1] = nsam
                        traza[f_, 2] = ipaso
                        traza[f_, 3] = r
                        traza[f_, 4] = hp
                        traza[f_, 5] = syr
                        traza[f_, 6] = szr
                        traza[f_, 7] = s_r / ws if ws > 0.0 else 0.0
                        traza[f_, 8] = g
                        traza[f_, 9] = i1
                        traza[f_, 10] = dc
                        traza[f_, 11] = tapa
                        traza[f_, 12] = q
                        traza[f_, 13] = kd
                        ntr[0] += 1
    # ── traza de depuración ──
    if ids.shape[0] > 0 and ntr[0] < traza.shape[0]:
        for q_ in range(ids.shape[0]):
            if ids[q_] == P[i, PID]:
                f_ = ntr[0]
                traza[f_, 0] = P[i, PID]
                traza[f_, 1] = nsam
                traza[f_, 2] = ipaso
                traza[f_, 3] = P[i, PX]
                traza[f_, 4] = P[i, PY]
                traza[f_, 5] = P[i, PX] + ddx / dg
                traza[f_, 6] = P[i, PY] + ddy / dg
                traza[f_, 7] = sy
                traza[f_, 8] = sz
                traza[f_, 9] = sy0sq
                traza[f_, 10] = u
                traza[f_, 11] = v
                traza[f_, 12] = k
                traza[f_, 13] = tapa
                traza[f_, 14] = P[i, PUNI]
                traza[f_, 15] = tsamp
                traza[f_, 16] = sz_pre
                traza[f_, 17] = fdiv
                traza[f_, 18] = qm1[0] if nesp > 0 else 0.0
                ntr[0] += 1
    # ── actualizar el puff ──
    for s in range(nesp):
        P[i, PM0 + 2 * s] = qm1[s]
        P[i, PM0 + 2 * s + 1] = qu1[s]
    P[i, PXTOT] += ds
    if calma:
        # en calma, en las fuentes de área, el original incorpora la σy de mitad de paso al tamaño
        # inicial del puff (σy0² += σy_m²) y reescala la anchura de línea: Lc = √(2π)·σys; en las
        # puntuales («SIG-Y0 Squared» sigue en 0) la σy de mitad de paso pasa a ser la mínima en
        # los receptores; en todas, también la σz de mitad de paso
        P[i, PSZI] = max(P[i, PSZI], sz_m)
        if P[i, PTIPO] == 3:
            P[i, PSY0] = sy0sq + sy_m * sy_m
            P[i, PLC2] = 0.5 * math.sqrt(2.0 * math.pi) * math.sqrt(P[i, PSY0])
        else:
            P[i, PSYI] = max(P[i, PSYI], sy_m)
    P[i, PX] += ddx / dg
    P[i, PY] += ddy / dg
    if P[i, PPRI] > 0.5 and P[i, PPRI] < 1.5 and TB[int(P[i, PTAB]), T_LWAK] < 0.5:
        # PRIME sin entrada en la estela: la σ guardada no baja de SYMIN/SZMIN (caja negra)
        sy_e = max(sy_e, P[i, PSYI])
        sz_e = max(sz_e, P[i, PSZI])
    P[i, PSY] = sy_e
    P[i, PSZ] = sz_e
    if (P[i, PX] < par[C_IB] or P[i, PX] > par[C_IE] or P[i, PY] < par[C_JB] or P[i, PY] > par[C_JE]):
        P[i, PVIVO] = 0.0
    return tsamp


@nb.njit(cache=True)
def ws_puff(P, i, U, V, zface, ZI, IPGT, par):
    """Velocidad de advección del puff en su posición actual (sin modificar su estado)."""
    nx = int(par[C_NX])
    ny = int(par[C_NY])
    ix, iy = celda(P[i, PX], P[i, PY], nx, ny)
    h = P[i, PH]
    sz = P[i, PSZ]
    k = IPGT[iy, ix]
    zi = min(max(ZI[iy, ix], par[C_XMINZI]), par[C_XMAXZI])
    techo = techo_capa(P, i, k, zi)
    if P[i, PUNI] > 0.5:
        u, v = viento_capa(U, V, zface, ix, iy, 0.0, P[i, PZIMAX])
    else:
        u, v = viento_capa(U, V, zface, ix, iy, max(0.0, h - sz), min(h + sz, techo))
    return math.sqrt(u * u + v * v)


@nb.njit(cache=True)
def nsam_viejo(P, i, U, V, zface, ZI, IPGT, par):
    """Pasos de muestreo de un puff viejo para la hora (con el viento al principio)."""
    ws = ws_puff(P, i, U, V, zface, ZI, IPGT, par)
    x = np.float32(ws) * np.float32(3600.0) / np.float32(par[C_XSAMLEN] * par[C_DG])
    n = int(math.floor(x + 0.5)) + 1
    return min(n, int(par[C_MXSAM]))


@nb.njit(cache=True)
def hora(P, npuf, nuevos, nnew, U, V, W, zface, IPGT, ZI, EL, ILU, svmin, swmin, ppc, par,
         xr, yr, zr, zp, conc, ids, traza, ntr, rdbg, cdbg, TB, EXC, DEP, M2, dflx, wflx):
    """Avanza todos los puffs una hora. P[:npuf] son los puffs viejos; `nuevos` (nn, NCOL) los puffs
    nuevos con PSY/PSZ iniciales, y nnew[j] el número de pasos de la fuente del puff nuevo j y su
    orden de salida (paso inicial). Devuelve conc acumulada (media horaria)."""
    for i in range(npuf):
        if P[i, PVIVO] < 0.5:
            continue
        ns = nsam_viejo(P, i, U, V, zface, ZI, IPGT, par)
        _recorrer(P, i, ns, 0, ns >= int(par[C_MXSAM]), U, V, W, zface, IPGT, ZI, EL, ILU, svmin,
                  swmin, ppc, par, xr, yr, zr, zp, conc, ids, traza, ntr, rdbg, cdbg, TB, EXC, DEP, M2, dflx, wflx)
    for j in range(nuevos.shape[0]):
        _recorrer(nuevos, j, nnew[j, 0], nnew[j, 1], nnew[j, 0] >= int(par[C_MXNEW]), U, V, W,
                  zface, IPGT, ZI, EL, ILU, svmin, swmin, ppc, par, xr, yr, zr, zp, conc, ids,
                  traza, ntr, rdbg, cdbg, TB, EXC, DEP, M2, dflx, wflx)


@nb.njit(cache=True)
def _recorrer(P, i, ns, k0, tope, U, V, W, zface, IPGT, ZI, EL, ILU, svmin, swmin, ppc, par, xr, yr,
              zr, zp, conc, ids, traza, ntr, rdbg, cdbg, TB, EXC, DEP, M2, dflx, wflx):
    """Pasos k0..ns−1 de duración 3600/ns con subpasos (caja negra). Pasos intermedios: cada subpaso
    dura min(resto, Lmax/u) (Lmax = XSAMLEN·Δx); tras él, si el resto supera lo que duró, se da otro
    dentro del mismo paso; si no, el resto pasa al paso siguiente. Último paso: hasta agotar el
    tiempo, subpaso entero si cabe en Lmax/u, la mitad si cabe en 2·Lmax/u y Lmax/u si no.
    tope: el número de pasos llegó al máximo (MXNEW o MXSAM) y entonces no hay subpasos."""
    ts = 3600.0 / ns
    lmax = 1e30 if tope else par[C_XSAMLEN] * par[C_DG]
    resto = 0.0
    for s in range(k0, ns):
        if P[i, PVIVO] < 0.5:
            return
        resto += ts
        if s < ns - 1:
            dt = paso(P, i, resto, U, V, W, zface, IPGT, ZI, EL, ILU, svmin, swmin, ppc, par, xr,
                      yr, zr, zp, conc, 1.0, lmax, ids, traza, ntr, ns, s + 1, rdbg, cdbg, TB, EXC, DEP, M2, dflx, wflx)
            resto -= dt
            while resto > dt and P[i, PVIVO] > 0.5:
                dt = paso(P, i, resto, U, V, W, zface, IPGT, ZI, EL, ILU, svmin, swmin, ppc, par,
                          xr, yr, zr, zp, conc, 1.0, lmax, ids, traza, ntr, ns, s + 1, rdbg, cdbg, TB, EXC, DEP, M2, dflx, wflx)
                resto -= dt
        else:
            while resto > 1e-6 * ts and P[i, PVIVO] > 0.5:
                ws = ws_puff(P, i, U, V, zface, ZI, IPGT, par)
                lw = lmax / ws if ws > 0.0 else 1e30
                if resto <= lw:
                    dt = resto
                elif resto <= 2.0 * lw:
                    dt = 0.5 * resto
                else:
                    dt = lw
                dt = paso(P, i, dt, U, V, W, zface, IPGT, ZI, EL, ILU, svmin, swmin, ppc, par, xr,
                          yr, zr, zp, conc, 1.0, lmax, ids, traza, ntr, ns, ns, rdbg, cdbg, TB, EXC, DEP, M2, dflx, wflx)
                resto -= dt
