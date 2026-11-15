# -*- coding: utf-8 -*-
"""Traducción de AERMAP v24142 (US EPA, dominio público): altura de colina (hill height
scale) de cada receptor: sub_calchc.f (CALCHC, DISTLL, GPNHRI, GPNARC, GPNLOA) y GETNOD.

Hc es la cota del nodo más alto que «asoma» por encima de la pendiente del 10 % trazada
desde el receptor: z_nodo - z_rec >= 0,1·distancia. En ficheros geográficos la distancia es
la geodésica de Vincenty (rutina INVERSE del NGS) sobre el elipsoide WGS84.

OPTIMIZACIÓN (mismo resultado): el original recorre uno a uno todos los nodos de los perfiles
no descartados y calcula una geodésica por nodo. Aquí, como Hc es el MÁXIMO de las cotas que
cumplen el criterio (la secuencia «si HEFF > HEFMAX» del original da ese máximo):
  1. solo se miran los nodos dentro del radio 10·(z_max - z_rec), en la ventana de perfiles y
     filas que lo contiene (si los perfiles son regulares; si no, se recorren por cota);
  2. se descartan los nodos con z <= HEFMAX o z < z_rec, que no pueden cambiar Hc;
  3. la cuerda 3D (siempre <= geodésica) descarta sin Vincenty los que no cumplirían;
  4. Vincenty se evalúa en orden de cota descendente, por lotes, y se para en el primer lote
     con algún nodo que cumple.
La descarga de perfiles por su cota máxima (DISTLL a lo largo del paralelo) se aplica tal
cual, porque puede excluir nodos que sí cumplirían. La iteración de Vincenty se vectoriza con
una máscara: cada nodo itera hasta SU convergencia (o 8 iteraciones) y conserva los valores
de su última iteración, como el bucle escalar; el orden de las operaciones de cada fórmula es
el del Fortran."""
import math

import numpy as np

from .mdt_externo import isphere_nadd
from .utm import utmgeo

A = 6378137.0
F = 1.0 / 298.257223563
ESQ = F * (2.0 - F)
TOL0, TOL1, TOL2 = 5.0e-15, 5.0e-14, 7.0e-03


# ------------------------------------------------------------------ geodésica (GPNHRI)
def _gpnarc(amax, esq, pi, p1, p2):
    """GPNARC: arco de meridiano entre dos latitudes (vectorizado en p2)."""
    tt = 5.0e-15
    s1 = abs(p1)
    s2 = np.abs(p2)
    flag = ((pi / 2.0 - tt) < s2) & (s2 < (pi / 2.0 + tt))
    if s1 > tt:
        flag = np.zeros_like(flag)
    da = p2 - p1
    e2 = esq
    e4 = e2 * e2
    e6 = e4 * e2
    e8 = e6 * e2
    ex = e8 * e2
    t1 = e2 * (003.0 / 4.0)
    t2 = e4 * (015.0 / 64.0)
    t3 = e6 * (035.0 / 512.0)
    t4 = e8 * (315.0 / 16384.0)
    t5 = ex * (693.0 / 131072.0)
    a = 1.0 + t1 + 3.0 * t2 + 10.0 * t3 + 35.0 * t4 + 126.0 * t5
    b = t1 + 4.0 * t2 + 15.0 * t3 + 56.0 * t4 + 210.0 * t5
    c = t2 + 06.0 * t3 + 28.0 * t4 + 120.0 * t5
    d = t3 + 08.0 * t4 + 045.0 * t5
    e_ = t4 + 010.0 * t5
    f_ = t5
    db = np.sin(p2 * 2.0) - math.sin(p1 * 2.0)
    dc = np.sin(p2 * 4.0) - math.sin(p1 * 4.0)
    dd = np.sin(p2 * 6.0) - math.sin(p1 * 6.0)
    de = np.sin(p2 * 8.0) - math.sin(p1 * 8.0)
    df = np.sin(p2 * 10.0) - math.sin(p1 * 10.0)
    s2_ = -db * b / 2.0 + dc * c / 4.0 - dd * d / 6.0 + de * e_ / 8.0 - df * f_ / 10.0
    s2_ = np.where(flag, 0.0, s2_)
    s1_ = da * a
    return amax * (1.0 - esq) * (s1_ + s2_)


def _gpnloa(amax, flat, esq, pi, dl):
    """GPNLOA (escalar): constantes del punto antinodal."""
    dlon = abs(dl)
    cons = (pi - dlon) / (pi * flat)
    f = flat
    az = math.asin(cons)
    t1 = 1.0
    t2 = (-1.0 / 4.0) * f * (1.0 + f + f * f)
    t4 = 3.0 / 16.0 * f * f * (1.0 + (9.0 / 4.0) * f)
    t6 = (-25.0 / 128.0) * f * f * f
    it = 0
    while True:
        it += 1
        s = math.cos(az)
        c2 = s * s
        ao = t1 + t2 * c2 + t4 * c2 * c2 + t6 * c2 * c2 * c2
        cs = cons / ao
        s = math.asin(cs)
        if abs(s - az) < 5.0e-13:
            break
        az = s
        if it > 6:
            break
    az1 = s
    if dl < 0.0:
        az1 = 2.0 * pi - az1
    esqp = esq / (1.0 - esq)
    s = math.cos(az1)
    u2 = esqp * s * s
    u4 = u2 * u2
    u6 = u4 * u2
    u8 = u6 * u2
    bo = 1.0 + (1.0 / 4.0) * u2 + (-3.0 / 64.0) * u4 + (5.0 / 256.0) * u6 + (-175.0 / 16384.0) * u8
    s = math.sin(az1)
    return amax * pi * (1.0 - flat * abs(s) * ao - bo * (1.0 - flat))


def distll(p1, e1, p2, e2, pi):
    """DISTLL/GPNHRI vectorizado: p1, e1 escalares (receptor); p2, e2 vectores (radianes)."""
    p2 = np.asarray(p2, dtype=np.float64)
    e2 = np.asarray(e2, dtype=np.float64)
    if p2.ndim == 0:
        p2 = np.full(e2.shape, float(p2))
    if e2.ndim == 0:
        e2 = np.full(p2.shape, float(e2))
    n = p2.size
    s = np.zeros(n)
    twopi = 2.0 * pi
    ss = e2 - e1
    igual = np.abs(ss) < TOL1
    if igual.any():
        s[igual] = np.abs(_gpnarc(A, ESQ, pi, p1, p2[igual]))
    resto = ~igual
    dlon = e2 - e1
    pos = dlon >= 0.0
    d1 = np.where(pos & (pi <= dlon) & (dlon < twopi), dlon - twopi, dlon)
    sa = np.abs(dlon)
    dlon_adj = np.where(~pos & (pi <= sa) & (sa < twopi), dlon + twopi, d1)
    ss = np.abs(dlon_adj)
    ss = np.where(ss > pi, twopi - ss, ss)
    alimit = pi * (1.0 - F)
    anti = resto & (ss >= alimit)
    principal = resto.copy()
    if anti.any():
        for k in np.nonzero(anti)[0]:
            r1, r2 = abs(p1), abs(p2[k])
            if (r1 > TOL2 and r2 > TOL2) or (r1 < TOL1 and r2 > TOL2) or (r2 < TOL1 and r1 > TOL2):
                continue                         # «goto 60»: cálculo normal
            principal[k] = False
            if r1 > TOL1 or r2 > TOL1:
                s[k] = 0.0
            else:
                sms = _gpnloa(A, F, ESQ, pi, dlon_adj[k])
                s[k] = A * abs(dlon_adj[k]) - sms
    if principal.any():
        s[principal] = _vincenty(p1, e1, p2[principal], e2[principal])
    return s


def _vincenty(p1, e1, p2, e2):
    """Bloque «60» de GPNHRI con iteración por elemento."""
    f = F
    f0 = (1.0 - f)
    b = A * f0
    epsq = ESQ / (1.0 - ESQ)
    f2 = f * f
    f3 = f * f2
    f4 = f * f3
    dlon = e2 - e1
    ab = dlon.copy()
    u1 = math.atan(f0 * math.sin(p1) / math.cos(p1))
    u2 = np.arctan(f0 * np.sin(p2) / np.cos(p2))
    su1 = math.sin(u1)
    cu1 = math.cos(u1)
    su2 = np.sin(u2)
    cu2 = np.cos(u2)
    n = p2.size
    sig = np.zeros(n)
    ssig = np.zeros(n)
    csig = np.zeros(n)
    w = np.zeros(n)
    q2 = np.zeros(n)
    q4 = np.zeros(n)
    q6 = np.zeros(n)
    r2 = np.zeros(n)
    r3 = np.zeros(n)
    act = np.arange(n)
    for kount in range(1, 9):
        if act.size == 0:
            break
        abk = ab[act]
        cu2k, su2k = cu2[act], su2[act]
        clon = np.cos(abk)
        slon = np.sin(abk)
        csigk = su1 * su2k + cu1 * cu2k * clon
        t_a = slon * cu2k
        t_b = su2k * cu1 - su1 * cu2k * clon
        ssigk = np.sqrt(t_a * t_a + t_b * t_b)
        sigk = np.arctan2(ssigk, csigk)
        sinalf = cu1 * cu2k * slon / ssigk
        wk = (1.0 - sinalf * sinalf)
        t4 = wk * wk
        t6 = wk * t4
        ao = (f - f2 * (1.0 + f + f2) * wk / 4.0 + 3.0 * f3 * (1.0 + 9.0 * f / 4.0) * t4 / 16.0
              - 25.0 * f4 * t6 / 128.0)
        a2 = (f2 * (1.0 + f + f2) * wk / 4.0 - f3 * (1.0 + 9.0 * f / 4.0) * t4 / 4.0
              + 75.0 * f4 * t6 / 256.0)
        a4 = f3 * (1.0 + 9.0 * f / 4.0) * t4 / 32.0 - 15.0 * f4 * t6 / 256.0
        a6 = 5.0 * f4 * t6 / 768.0
        qo = np.where(wk > TOL0, -2.0 * su1 * su2k / np.where(wk > TOL0, wk, 1.0), 0.0)
        q2k = csigk + qo
        q4k = 2.0 * q2k * q2k - 1.0
        q6k = q2k * (4.0 * q2k * q2k - 3.0)
        r2k = 2.0 * ssigk * csigk
        r3k = ssigk * (3.0 - 4.0 * ssigk * ssigk)
        sk = sinalf * (ao * sigk + a2 * ssigk * q2k + a4 * r2k * q4k + a6 * r3k * q6k)
        dl = dlon[act]
        xz = dl + sk
        xy = np.abs(xz - abk)
        ab[act] = dl + sk
        sig[act], ssig[act], csig[act], w[act] = sigk, ssigk, csigk, wk
        q2[act], q4[act], q6[act], r2[act], r3[act] = q2k, q4k, q6k, r2k, r3k
        act = act[~(xy < 0.5e-13)]
    z = epsq * w
    bo = 1.0 + z * (1.0 / 4.0 + z * (-3.0 / 64.0 + z * (5.0 / 256.0 - z * 175.0 / 16384.0)))
    b2 = z * (-1.0 / 4.0 + z * (1.0 / 16.0 + z * (-15.0 / 512.0 + z * 35.0 / 2048.0)))
    b4 = z * z * (-1.0 / 128.0 + z * (3.0 / 512.0 - z * 35.0 / 8192.0))
    b6 = z * z * z * (-1.0 / 1536.0 + z * 5.0 / 6144.0)
    return b * (bo * sig + b2 * ssig * q2 + b4 * r2 * q4 + b6 * r3 * q6)


# ------------------------------------------------------------------ CALCHC
def calchc(e, irec):
    if e.azelev[irec] < -9998.999:
        e.azhill[irec] = -9999.0
        return
    pi, dtorad = e.pi, e.dtorad
    zrec = e.azelev[irec]
    jdem = e.jdm[irec]
    izonrec = e.izonr[irec]
    hefmax = -1000.0
    indx_dem = getattr(e, "_indx_dem", 0)
    for iidem in range(0, e.numdem + 1):
        hfdemx = -1000.0
        if iidem == 0:
            idem = jdem
        elif iidem == jdem:
            continue
        else:
            idem = iidem
        d = e.dem[idem]
        if d.numprf == 0:
            continue
        rlon, rlat = e.rlon[irec], e.rlat[irec]          # desplazamiento NAD nulo
        izonrec, xrs, yrs, _, _ = utmgeo(555, d.izond, 0.0, 0.0, rlon, rlat, isphere_nadd(d))
        plat1 = (rlat / 3600.0) * dtorad
        plon1 = (rlon / 3600.0) * dtorad
        if idem != jdem:
            if d.elevmx > hefmax:
                hfdemx = d.elevmx
                if d.selat_d * dtorad >= plat1:
                    plat2 = d.selat_d * dtorad
                    if d.selon_d * dtorad <= plon1:
                        plon2, indx_dem = d.selon_d * dtorad, 7
                    elif d.swlon_d * dtorad >= plon1:
                        plon2, indx_dem = d.swlon_d * dtorad, 9
                    else:
                        plon2, indx_dem = plon1, 8
                elif d.nelat_d * dtorad <= plat1:
                    plat2 = d.nelat_d * dtorad
                    if d.nelon_d * dtorad <= plon1:
                        plon2, indx_dem = d.nelon_d * dtorad, 1
                    elif d.nwlon_d * dtorad >= plon1:
                        plon2, indx_dem = d.nwlon_d * dtorad, 3
                    else:
                        plon2, indx_dem = plon1, 2
                else:
                    plat2 = plat1
                    if d.selon_d * dtorad <= plon1:
                        plon2, indx_dem = d.selon_d * dtorad, 4
                    elif d.swlon_d * dtorad >= plon1:
                        plon2, indx_dem = d.swlon_d * dtorad, 6
                    else:
                        indx_dem = 5
                        hfdemx = d.elevmx
                        if hfdemx <= hefmax:
                            continue
                        plon2 = None
                if plon2 is not None:
                    rmin = float(distll(plat1, plon1, np.array([plat2]), np.array([plon2]), pi)[0])
                    bp = rmin * 0.1
                    if bp <= (d.elevmx - zrec):
                        hfdemx = d.elevmx
                        if hfdemx <= hefmax:
                            continue
                    else:
                        continue
            else:
                continue
        if idem == jdem or hfdemx > hefmax:
            hefmax = _ficheros(e, d, irec, idem == jdem, indx_dem, plat1, plon1, xrs, yrs,
                               zrec, hefmax)
    e._indx_dem = indx_dem
    if hefmax < zrec or e.azhill[irec] < zrec:
        e.azhill[irec] = zrec


def _ficheros(e, d, irec, local, indx_dem, plat1, plon1, xrs, yrs, zrec, hefmax):
    """Bucle de perfiles y nodos de un fichero para un receptor."""
    pi, dtorad = e.pi, e.dtorad
    n = d.numprf
    xb = d.idx_x[:n]
    yb = d.idx_y[:n]
    nn = d.idx_n[:n]
    mx = d.idx_max[:n]
    dym = d.dym
    geo = d.iplan == 0
    # ---- descarte de perfiles por su cota máxima (solo se evalúa para los perfiles que
    #      interesan: los de la ventana con algún nodo candidato; el resultado es el mismo)
    def saltos(ip):
        xbs, ybs, nns, mxs = xb[ip], yb[ip], nn[ip], mx[ip]
        m = ip.size
        if local:
            if geo:
                rdist = distll(plat1, plon1, np.full(m, plat1), (xbs / 3600.0) * dtorad, pi)
                return rdist * 0.10 > (mxs - zrec)
            return np.abs(xrs - xbs) * 0.1 > (mxs - zrec)
        if geo:
            if 1 <= indx_dem <= 3:
                p2 = ((ybs + nns * dym) / 3600.0) * dtorad
            elif 7 <= indx_dem <= 9:
                p2 = (ybs / 3600.0) * dtorad
            else:
                p2 = np.full(m, plat1)
            rdist = distll(plat1, plon1, p2, (xbs / 3600.0) * dtorad, pi)
            return rdist * 0.10 > (mxs - zrec)
        if 1 <= indx_dem <= 3:
            yarg = ybs + nns * dym
        elif 7 <= indx_dem <= 9:
            yarg = ybs
        else:
            yarg = np.full(m, yrs)
        dx = xrs - xbs
        dy = yrs - yarg
        rdist = np.sqrt(dx * dx + dy * dy)
        return rdist * 0.10 > (mxs - zrec)

    # ---- Solo puede cambiar Hc un nodo con z > HEFMAX que cumpla el criterio, lo que exige
    #      z >= z_rec y distancia <= 10·(z - z_rec) <= 10·(z_max - z_rec). Se buscan pues los
    #      nodos dentro de ese radio; para ellos, una cota inferior barata de la distancia (la
    #      cuerda 3D, siempre <= geodésica) descarta los imposibles y solo los dudosos pasan
    #      por Vincenty. Hc = máximo de los que cumplen: idéntico al bucle del original.
    p = _preparar(e, d)
    if n == 0 or p.zmax < zrec or p.zmax <= hefmax:
        return hefmax
    if p.regular:
        heff = _ventana(e, d, p, saltos, plat1, plon1, xrs, yrs, zrec, hefmax)
    else:
        salta = saltos(np.arange(n))
        heff = None if salta.all() else _recorrido(e, d, p, salta, plat1, plon1, xrs, yrs,
                                                     zrec, hefmax)
    if heff is not None and heff > hefmax:
        hefmax = heff
        e.azhill[irec] = heff
    return hefmax


def _evaluar(e, d, p, z, lat, lon, xn, yn, x3, y3, z3, plat1, plon1, xrs, yrs, zrec):
    """Máxima cota que cumple el criterio entre los nodos dados (o None)."""
    if d.iplan == 0:
        xr, yr, zr = _ecef(plat1, plon1)
        dx, dy, dz = x3 - xr, y3 - yr, z3 - zr
        cuerda = np.sqrt(dx * dx + dy * dy + dz * dz)
        dudoso = (z - zrec) >= 0.1 * (cuerda - 1.0)
        if not dudoso.any():
            return None
        z, lat, lon = z[dudoso], lat[dudoso], lon[dudoso]
        # de mayor a menor cota: el primer lote con algún nodo que cumple contiene el máximo
        orden = np.argsort(-z, kind="stable")
        a, paso = 0, 64
        while a < orden.size:
            sel = orden[a:a + paso]
            a += paso
            paso = min(paso * 4, 65536)
            rd = distll(plat1, plon1, lat[sel], lon[sel], e.pi)
            zs = z[sel]
            cumple = (zs - zrec) >= rd * 0.1
            if cumple.any():
                return float(zs[cumple].max())
        return None
    else:
        dx = xrs - xn
        dy = yrs - yn
        rd = np.sqrt(dx * dx + dy * dy)
    cumple = (z - zrec) >= rd * 0.1
    return float(z[cumple].max()) if cumple.any() else None


def _ecef(lat, lon):
    s = np.sin(lat)
    nr = A / np.sqrt(1.0 - ESQ * s * s)
    c = np.cos(lat)
    return nr * c * np.cos(lon), nr * c * np.sin(lon), nr * (1.0 - ESQ) * s


def _ventana(e, d, p, saltos, plat1, plon1, xrs, yrs, zrec, hefmax):
    rmax = 10.0 * (p.zmax - zrec) + 10.0
    np_, nk = p.z2.shape
    p0, p1, k0, k1 = 0, np_, 0, nk
    if d.iplan == 0:
        dphi = 1.05 * rmax / (A * (1.0 - ESQ))
        ext = max(abs(plat1 - dphi), abs(plat1 + dphi))
        k0 = int(np.searchsorted(p.lat_row, plat1 - dphi, side="left"))
        k1 = int(np.searchsorted(p.lat_row, plat1 + dphi, side="right"))
        if ext < 1.5:
            dlam = 1.05 * rmax / (A * math.cos(ext))
            if dlam < 3.0:
                p0 = int(np.searchsorted(p.lon_prof, plon1 - dlam, side="left"))
                p1 = int(np.searchsorted(p.lon_prof, plon1 + dlam, side="right"))
    else:
        k0 = int(np.searchsorted(p.y_row, yrs - rmax, side="left"))
        k1 = int(np.searchsorted(p.y_row, yrs + rmax, side="right"))
        p0 = int(np.searchsorted(p.x_prof, xrs - rmax, side="left"))
        p1 = int(np.searchsorted(p.x_prof, xrs + rmax, side="right"))
    if p0 >= p1 or k0 >= k1:
        return None
    sub = p.z2[p0:p1, k0:k1]
    cand = (sub > hefmax) & (sub >= zrec)
    filas = np.nonzero(cand.any(axis=1))[0]
    if filas.size == 0:
        return None
    vivas = filas[~saltos(filas + p0)]
    if vivas.size == 0:
        return None
    pp, kk = np.nonzero(cand[vivas])
    pp = vivas[pp] + p0
    kk += k0
    z = p.z2[pp, kk]
    if d.iplan == 0:
        rc = p.rc_row[kk]
        return _evaluar(e, d, p, z, p.lat_row[kk], p.lon_prof[pp], None, None,
                        rc * p.cl_prof[pp], rc * p.sl_prof[pp], p.zc_row[kk],
                        plat1, plon1, xrs, yrs, zrec)
    return _evaluar(e, d, p, z, None, None, p.x_prof[pp], p.y_row[kk], None, None, None,
                    plat1, plon1, xrs, yrs, zrec)


def _recorrido(e, d, p, salta, plat1, plon1, xrs, yrs, zrec, hefmax):
    """Caso general (perfiles de distinta longitud): nodos de mayor a menor cota; el
    primero que cumple el criterio es el máximo."""
    if hefmax >= zrec:
        nc = int(np.searchsorted(-p.zord, -hefmax, side="left"))     # z > HEFMAX
    else:
        nc = int(np.searchsorted(-p.zord, -zrec, side="right"))      # z >= z_rec
    a, paso = 0, 4096
    while a < nc:
        recs = p.orden[a:min(a + paso, nc)]
        a += paso
        paso = min(paso * 2, 262144)
        recs = recs[~salta[p.perfil[recs]]]
        if recs.size == 0:
            continue
        geo = d.iplan == 0
        heff = _evaluar(e, d, p, d.elev[recs],
                        p.lat[recs] if geo else None, p.lon[recs] if geo else None,
                        None if geo else p.x[recs], None if geo else p.y[recs],
                        p.x3[recs] if geo else None, p.y3[recs] if geo else None,
                        p.z3[recs] if geo else None, plat1, plon1, xrs, yrs, zrec)
        if heff is not None:
            return heff
    return None


class _Prep:
    pass


def _preparar(e, d):
    """Datos de los nodos que no dependen del receptor (se calculan una vez por fichero):
    coordenadas de cada registro como las genera GETNOD (YNODE ACUMULADO: YBASE + DYM +
    DYM...), su conversión a radianes y la posición 3D para la cota inferior de distancia."""
    p = getattr(d, "_prep", None)
    if p is not None:
        return p
    p = _Prep()
    n = d.numprf
    nn = d.idx_n[:n]
    xb = d.idx_x[:n]
    yb = d.idx_y[:n]
    total = int(nn.sum())
    z = d.elev[:total]
    p.zmax = float(z.max()) if total else -1.0e30
    nmax = int(nn.max()) if n else 0
    p.regular = (n > 0 and bool(np.all(nn == nn[0])) and bool(np.all(yb == yb[0]))
                 and d.dym > 0 and bool(np.all(np.diff(xb) > 0)))
    if p.regular:
        n0 = int(nn[0])
        ac = np.full(n0, d.dym)
        ac[0] = yb[0]
        ys = np.add.accumulate(ac)                 # YNODE de cualquier perfil
        p.z2 = z.reshape(n, n0)
        if d.iplan == 0:
            p.lat_row = (ys / 3600.0) * e.dtorad
            p.lon_prof = (xb / 3600.0) * e.dtorad
            s = np.sin(p.lat_row)
            nr = A / np.sqrt(1.0 - ESQ * s * s)
            p.rc_row = nr * np.cos(p.lat_row)
            p.zc_row = nr * (1.0 - ESQ) * s
            p.cl_prof = np.cos(p.lon_prof)
            p.sl_prof = np.sin(p.lon_prof)
        else:
            p.y_row = ys
            p.x_prof = xb
    else:
        ac = np.full((n, max(nmax, 1)), d.dym)
        ac[:, 0] = yb
        ys = np.add.accumulate(ac, axis=1)
        valido = np.arange(max(nmax, 1))[None, :] < nn[:, None]
        p.y = ys[valido]
        p.perfil = np.repeat(np.arange(n), nn)
        p.x = xb[p.perfil]
        if d.iplan == 0:
            p.lat = (p.y / 3600.0) * e.dtorad
            p.lon = (p.x / 3600.0) * e.dtorad
            p.x3, p.y3, p.z3 = _ecef(p.lat, p.lon)
        p.orden = np.argsort(-z, kind="stable")
        p.zord = z[p.orden]
    d._prep = p
    return p
