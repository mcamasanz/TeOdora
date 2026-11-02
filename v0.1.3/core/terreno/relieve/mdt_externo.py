# -*- coding: utf-8 -*-
"""Traducción de AERMAP v24142 (US EPA, dominio público): ficheros de terreno GeoTIFF
(«NED»): sub_nedchk.f (NEDCHK), sub_cnrcnv.f (CNRCNV), sub_chkadj.f (CHKADJ) y
sub_initer_ned.f (INITER_NED).

INITER_NED del original escribe las cotas en un fichero de acceso directo y, por cada
perfil (columna), una línea de índice con formato '(2(D24.15,1X),I6,1X,I3,F15.5)' que luego
se vuelve a LEER. Ese ida y vuelta redondea la base del perfil a 15 cifras significativas y
la cota máxima del perfil a 5 decimales; aquí se reproduce formateando y releyendo, y las
cotas se guardan en memoria (sin ficheros temporales).

Fuera de alcance (como en la traducción de AERSURFACE): los volcados de depuración
MAPDETAIL/MAPPARAMS/DOMDETAIL y TiffDebug."""
import os

import numpy as np

from .estado import NUDGE, fx
from .tiff import leer_etiquetas, leer_elevaciones
from .utm import utmgeo, utm_zona

TFLG = [(256, "ImageWidth"), (257, "ImageLength"), (258, "BitsPerSample"), (259, "Compression"),
        (273, "StripOffsets"), (274, "Orientation"), (277, "SamplesPerPixel"),
        (278, "RowsPerStrip"), (322, "TileWidth"), (323, "TileLength"), (324, "TileOffsets"),
        (339, "SampleFormat"), (33550, "ModelPixelScale"), (33922, "ModelTiePoint")]
GFLG = [(1024, "GTModelType"), (1025, "GTRasterType"), (2048, "GeographicType"),
        (2050, "GeogGeodeticDatum"), (2054, "GeogAngularUnits"), (2056, "GeogEllipsoid"),
        (3072, "ProjectedCSType"), (3076, "ProjLinearUnits"), (4099, "VerticalUnits")]


class Dem:
    """Parámetros de un fichero de terreno (los vectores (IDEM) del original)."""

    def __init__(self):
        self.ncols = self.nrows = 0
        self.bps = 0
        self.sampleformat = 1
        self.swap = False
        self.tifftype = "     "
        self.rowsperstrip = self.tilewid = self.tilelen = 0
        self.dataos = []
        self.pxlx = self.pxly = self.pxlz = 0.0
        self.tiex = self.tiey = self.tiez = 0.0
        self.dci = 1.0
        self.elunit = 0
        self.cunit = 0
        self.iplan = 0
        self.nadd = 0
        self.izo = 0
        self.izond = 0
        self.dxm = self.dym = 0.0
        self.dmcnr = [[0.0] * 5 for _ in range(3)]       # [eje 1..2][esquina 1..4]
        self.nprof = 0
        self.fln = ""
        # esquinas (CNRCNV)
        for nom in ("swe", "swn", "nwe", "nwn", "nee", "nen", "see", "sen"):
            setattr(self, nom + "_m", 0.0)
        for nom in ("swlon", "swlat", "nwlon", "nwlat", "nelon", "nelat", "selon", "selat"):
            setattr(self, nom + "_s", 0.0)
            setattr(self, nom + "_d", 0.0)
        self.sw_z = self.nw_z = self.ne_z = self.se_z = 0
        # INITER_NED
        self.elevmn = self.elevmx = 0.0
        self.numprf = 0
        self.idx_x = self.idx_y = self.idx_max = np.zeros(0)
        self.idx_n = self.idx_z = np.zeros(0, dtype=np.int64)
        self.elev = np.zeros(0)


def _i8(n):
    return f"{n:8d}"


def _q_d24(x):
    """Ida y vuelta por D24.15: 15 cifras significativas."""
    return float(f"{x:.14e}")


def _q_f155(x):
    """Ida y vuelta por F15.5."""
    return float(f"{x:.5f}")


def isphere_nadd(dem):
    """SELECT CASE (NADD) habitual de RECELV/CALCHC/DEMREC/CHKEXT."""
    n = dem.nadd
    if n == 0:
        return 4 if dem.iplan == 0 else (0 if dem.iplan == 1 else 4)
    if 2 <= n <= 4:
        return 4
    if n == 1 or 5 <= n <= 6:
        return 0
    return 4


# ====================================================================================== NEDCHK
def nedchk(e):
    m = "NEDCHK"
    e.l_neednadcon = False
    e.dem = [None] + [Dem() for _ in range(e.numdem)]
    modeltype = geotype = geodatum = geoellipse = projcstype = geogunts = projunts = 0
    ancx = ancy = ancz = 0.0
    for idem in range(1, e.numdem + 1):
        d = e.dem[idem]
        geotypeflg = geodatumflg = geoellipseflg = projcstypeflg = False
        rastertypeflg = pixelisarea = pixelispoint = False
        tiepntflg = pxlsclflg = False
        striposflg = rowsperstripflg = tileosflg = tilelenflg = tilewidflg = False
        elvuntsflg = geoguntsflg = projuntsflg = False
        nombre = e.demfil[idem].rstrip()
        i = nombre.rfind("/")
        j = nombre.rfind("\\")
        if i >= 0:
            d.fln = nombre[i + 1:] if len(nombre) - (i + 1) <= 40 else nombre[-40:]
        elif j >= 0:
            d.fln = nombre[j + 1:] if len(nombre) - (j + 1) <= 40 else nombre[-40:]
        else:
            d.fln = nombre[:40]
        r = leer_etiquetas(e, nombre)
        if r.tiffwrn:
            e.errhdl(e.path, m, "W", "480", _i8(idem))
        if r.tifferr:
            e.errhdl(e.path, m, "E", "481", _i8(idem))
        if r.allerr:
            e.errhdl(e.path, m, "E", "482", _i8(idem))
        if r.tifferr or r.allerr:
            e.nederr = True
            break
        d.swap = r.swapbytes
        tt = {}
        for t in r.ttags:
            if not t.prob:
                tt[t.id] = t                    # gana la última aparición
        gk = {}
        for g in r.gkeys:
            if not g.prob:
                gk[g.id] = g

        def iv(t, k=0):
            return t.intval[k] if len(t.intval) > k else 0

        def dv(t, k):
            return t.dblval[k] if len(t.dblval) > k else 0.0

        for tid, tnom in TFLG:
            dumtag = _i8(tid)
            t = tt.get(tid)
            if t is None:
                if tid in (273, 278, 322, 323, 324):
                    pass
                elif tid in (259, 274, 277, 339):
                    if tid == 339:
                        d.sampleformat = 1
                    e.errhdl(e.path, m, "W", "450", dumtag)
                else:
                    e.errhdl(e.path, m, "E", "450", dumtag)
                    e.nederr = True
                continue
            if tid == 256:
                d.ncols = iv(t)
                d.nprof = d.ncols
            elif tid == 257:
                d.nrows = iv(t)
            elif tid == 258:
                v = iv(t)
                if v in (8, 16, 32, 64):
                    d.bps = v // 8
                    if v == 8:
                        e.errhdl(e.path, m, "W", "455", dumtag)
                else:
                    e.errhdl(e.path, m, "E", "455", dumtag)
                    e.nederr = True
            elif tid == 259:
                if iv(t) != 1:
                    e.errhdl(e.path, m, "E", "455", dumtag)
                    e.nederr = True
            elif tid == 273:
                striposflg = True
                d.dataos = list(t.intval)
            elif tid == 274:
                if iv(t) != 1:
                    e.errhdl(e.path, m, "E", "455", dumtag)
                    e.nederr = True
            elif tid == 277:
                if iv(t) != 1:
                    e.errhdl(e.path, m, "E", "455", dumtag)
                    e.nederr = True
            elif tid == 278:
                rowsperstripflg = True
                d.rowsperstrip = iv(t)
            elif tid == 322:
                tilewidflg = True
                d.tilewid = iv(t)
            elif tid == 323:
                tilelenflg = True
                d.tilelen = iv(t)
            elif tid == 324:
                tileosflg = True
                d.dataos = list(t.intval)
            elif tid == 339:
                if iv(t) not in (1, 2, 3):
                    e.errhdl(e.path, m, "E", "455", dumtag)
                    e.nederr = True
                else:
                    d.sampleformat = iv(t)
            elif tid == 33550:
                d.pxlx, d.pxly, d.pxlz = dv(t, 0), dv(t, 1), dv(t, 2)
                pxlsclflg = True
                d.dci = d.pxlz if d.pxlz != 0.0 else 1.0
            elif tid == 33922:
                ancx, ancy, ancz = dv(t, 0), dv(t, 1), dv(t, 2)
                d.tiex, d.tiey, d.tiez = dv(t, 3), dv(t, 4), dv(t, 5)
                tiepntflg = True
        if striposflg and rowsperstripflg:
            d.tifftype = "strip"
        elif striposflg:
            d.tifftype = "strip"
            d.rowsperstrip = d.nrows
            e.errhdl(e.path, m, "W", "450", "     278")
        elif tileosflg and tilelenflg and tilewidflg:
            d.tifftype = "tile"
        else:
            e.errhdl(e.path, m, "E", "475", "")
            e.nederr = True

        for gid, gnom in GFLG:
            dumflg = _i8(gid)
            g = gk.get(gid)
            if g is None:
                if gid not in (2048, 2050, 2054, 2056, 3072, 3076, 4099):
                    e.errhdl(e.path, m, "E", "460", dumflg)
                    e.nederr = True
                continue
            v = iv(g)
            if gid == 1024:
                if v == 1:
                    modeltype = 1
                    if idem == 1:
                        e.typdem = "UTM "
                    d.iplan = 1
                elif v == 2:
                    modeltype = 2
                    if idem == 1:
                        e.typdem = "LAT "
                    d.iplan = 0
                else:
                    if idem == 1:
                        e.typdem = "GEO " if v == 3 else "UNK "
                    d.iplan = 9
                    e.errhdl(e.path, m, "E", "465", dumflg)
                    e.nederr = True
            elif gid == 1025:
                if v == 1:
                    pixelisarea, pixelispoint, rastertypeflg = True, False, True
                elif v == 2:
                    pixelispoint, pixelisarea, rastertypeflg = True, False, True
                else:
                    pixelisarea = pixelispoint = rastertypeflg = False
                    e.errhdl(e.path, m, "E", "465", dumflg)
                    e.nederr = True
            elif gid == 2048:
                if v in (4267, 4269, 4322, 4326):
                    geotypeflg, geotype = True, v
                elif v in (4008, 4019, 4030):
                    geoellipseflg, geoellipse = True, v
                else:
                    geotypeflg, geotype = True, v
                    e.errhdl(e.path, m, "W", "465", dumflg)
            elif gid == 2050:
                if v in (6267, 6269, 6322, 6326):
                    geodatumflg, geodatum = True, v
                elif v in (6008, 6019, 6030):
                    geoellipseflg, geoellipse = True, v
                else:
                    geodatumflg, geodatum = True, v
                    e.errhdl(e.path, m, "W", "465", dumflg)
            elif gid == 2056:
                geoellipseflg, geoellipse = True, v
                if v not in (7008, 7019, 7030):
                    e.errhdl(e.path, m, "W", "465", dumflg)
            elif gid == 2054:
                if v in (9101, 9102, 9104):
                    geoguntsflg, geogunts = True, v
                else:
                    geoguntsflg = False
                    d.cunit = 9
                    e.errhdl(e.path, m, "W", "465", dumflg)
            elif gid == 3072:
                projcstypeflg, projcstype = True, v
                if not (26703 <= v <= 26722 or 26903 <= v <= 26923 or 32201 <= v <= 32260
                        or 32301 <= v <= 32360 or 32601 <= v <= 32660 or 32701 <= v <= 32760):
                    e.errhdl(e.path, m, "W", "465", dumflg)
            elif gid == 3076:
                if v in (9001, 9002):
                    projuntsflg, projunts = True, v
                else:
                    projuntsflg = False
                    d.cunit = 9
                    e.errhdl(e.path, m, "W", "465", dumflg)
            elif gid == 4099:
                if v == 9001:
                    elvuntsflg, d.elunit = True, 2
                elif v == 9002:
                    elvuntsflg, d.elunit = True, 1
                else:
                    elvuntsflg, d.elunit = False, 9
                    e.errhdl(e.path, m, "E", "465", dumflg)
                    e.nederr = True

        # ---- tipo de modelo: unidades, datum y zona
        if modeltype == 1:
            if projuntsflg:
                if d.cunit != 9:
                    d.cunit = 2 if projunts == 9001 else (1 if projunts == 9002 else d.cunit)
                else:
                    e.errhdl(e.path, m, "E", "465", _i8(3076))
                    e.nederr = True
            else:
                e.errhdl(e.path, m, "W", "478", _i8(idem))
                d.cunit = 2
            if projcstypeflg:
                p = projcstype
                if 26703 <= p <= 26722:
                    d.nadd = 1
                    e.errhdl(e.path, m, "W", "470", "NAD27")
                    d.izo = d.izond = p - 26700
                elif 26903 <= p <= 26923:
                    d.nadd = 4
                    d.izo = d.izond = p - 26900
                elif 32201 <= p <= 32260:
                    d.nadd = 2
                    e.errhdl(e.path, m, "W", "470", "WGS72")
                    d.izo = d.izond = p - 32200
                elif 32301 <= p <= 32360:
                    d.nadd = 2
                    e.errhdl(e.path, m, "W", "470", "WGS72")
                    d.izo = d.izond = -1 * (p - 32300)
                elif 32601 <= p <= 32660:
                    d.nadd = 3
                    e.errhdl(e.path, m, "W", "470", "WGS84")
                    d.izo = d.izond = p - 32600
                elif 32701 <= p <= 32760:
                    d.nadd = 3
                    e.errhdl(e.path, m, "W", "470", "WGS84")
                    d.izo = d.izond = -1 * (p - 32700)
                elif e.nada == 0:
                    # (sic) el original NO asigna la zona UTM en este caso
                    e.errhdl(e.path, m, "W", "471", _i8(idem))
                    d.nadd = 4
                else:
                    e.errhdl(e.path, m, "E", "472", _i8(idem))
                    e.nederr = True
            else:
                e.errhdl(e.path, m, "E", "460", _i8(3072))
                e.nederr = True
        elif modeltype == 2:
            if geoguntsflg:
                if d.cunit != 9:
                    d.cunit = {9101: 0, 9102: 4, 9104: 3}.get(geogunts, d.cunit)
                else:
                    e.errhdl(e.path, m, "E", "465", _i8(2054))
                    e.nederr = True
            else:
                e.errhdl(e.path, m, "W", "479", _i8(idem))
                d.cunit = 4
            if geotypeflg:
                _datum(e, m, d, idem, geotype, {4267: (1, "NAD27"), 4269: (4, None),
                                                4322: (2, "WGS72"), 4326: (3, "WGS84")})
            elif geodatumflg:
                _datum(e, m, d, idem, geodatum, {6267: (1, "NAD27"), 6269: (4, None),
                                                 6322: (2, "WGS72"), 6326: (3, "WGS84")})
            elif geoellipseflg:
                tabla = {}
                for c in (4008, 6008, 7008):
                    tabla[c] = (1, "NAD27")
                for c in (4019, 6019, 7019):
                    tabla[c] = (4, None)
                for c in (4030, 6030, 7030):
                    tabla[c] = (3, "WGS84")
                _datum(e, m, d, idem, geoellipse, tabla)
            else:
                for gid in (2048, 2050, 2056):
                    e.errhdl(e.path, m, "E", "460", _i8(gid))
                e.nederr = True

        # ---- unidades de cota
        if not elvuntsflg:
            if not e.l_userelevunits[idem]:
                d.elunit = 2
                e.errhdl(e.path, m, "W", "473", _i8(idem))
            else:
                d.elunit = e.userelevunits[idem]
                if e.userdci[idem] != d.dci:
                    e.errhdl(e.path, m, "E", "477", _i8(idem))
                    e.nederr = True
                else:
                    d.dci = e.userdci[idem]
                    e.errhdl(e.path, m, "W", "474", _i8(idem))
        elif e.l_userelevunits[idem]:
            if d.elunit != e.userelevunits[idem]:
                e.errhdl(e.path, m, "E", "476", _i8(idem))
                e.nederr = True
            if e.userdci[idem] != d.dci:
                e.errhdl(e.path, m, "E", "477", _i8(idem))
                e.nederr = True
            if d.elunit == e.userelevunits[idem] and e.userdci[idem] == d.dci:
                e.l_userelevunits[idem] = False

        # ---- esquinas, resolución y zona
        if pxlsclflg and tiepntflg and rastertypeflg:
            if pixelisarea:
                d.dmcnr[1][2] = d.tiex + (0.5 - ancx) * d.pxlx
                d.dmcnr[2][2] = d.tiey - (0.5 - ancy) * d.pxly
            elif pixelispoint:
                d.dmcnr[1][2] = d.tiex - ancx * d.pxlx
                d.dmcnr[2][2] = d.tiey + ancy * d.pxly
            if d.pxlz != 0.0:
                d.tiez = d.tiez - ancz * d.pxlz
            elif ancz != 0.0:
                d.tiez = d.tiez - ancz
            aviso483 = d.pxlz == 0.0 and ancz != 0.0
            if d.iplan == 0:
                if d.cunit == 0:
                    d.dmcnr[1][2] = d.dmcnr[1][2] * e.rtodeg * 3600.0
                    d.dmcnr[2][2] = d.dmcnr[2][2] * e.rtodeg * 3600.0
                    d.dxm = d.pxlx * e.rtodeg * 3600.0
                    d.dym = d.pxly * e.rtodeg * 3600.0
                    if aviso483:
                        e.errhdl(e.path, m, "W", "483", _i8(idem))
                    d.cunit = 3
                elif d.cunit == 3:
                    d.dxm, d.dym = d.pxlx, d.pxly
                    if aviso483:
                        e.errhdl(e.path, m, "W", "483", _i8(idem))
                elif d.cunit == 4:
                    d.dmcnr[1][2] = d.dmcnr[1][2] * 3600.0
                    d.dmcnr[2][2] = d.dmcnr[2][2] * 3600.0
                    d.dxm = d.pxlx * 3600.0
                    d.dym = d.pxly * 3600.0
                    if aviso483:
                        e.errhdl(e.path, m, "W", "483", _i8(idem))
                    d.cunit = 3
                else:
                    e.errhdl(e.path, m, "E", "466", f"{d.iplan:4d}{d.cunit:4d}")
                    e.nederr = True
                    continue
            elif d.iplan == 1:
                if d.cunit == 1:
                    d.dmcnr[1][2] = d.dmcnr[1][2] * 0.3048
                    d.dmcnr[2][2] = d.dmcnr[2][2] * 0.3048
                    d.dxm = d.pxlx * 0.3048
                    d.dym = d.pxly * 0.3048
                    if aviso483:
                        e.errhdl(e.path, m, "W", "483", _i8(idem))
                    d.cunit = 2
                elif d.cunit == 2:
                    d.dxm, d.dym = d.pxlx, d.pxly
                    if aviso483:
                        e.errhdl(e.path, m, "W", "483", _i8(idem))
                else:
                    e.errhdl(e.path, m, "E", "466", f"{d.iplan:4d}{d.cunit:4d}")
                    e.nederr = True
                    continue
            if d.iplan == 0:
                lat3600 = d.dmcnr[2][2] * 3600.0          # (sic) ya estaba en segundos
                if d.dxm > 60.0:
                    e.errhdl(e.path, m, "E", "484", _i8(idem))
                    e.nederr = True
                    continue
                elif ((d.dxm > 3.0 and lat3600 <= 50.0) or (d.dxm > 6.0 and lat3600 <= 70.0)
                      or (d.dxm > 9.0 and lat3600 > 70.0)):
                    e.errhdl(e.path, m, "W", "485", _i8(idem))
                elif d.dxm < 0.1:
                    e.errhdl(e.path, m, "W", "485", _i8(idem))
            elif d.iplan == 1:
                if d.dxm > 1000.0:
                    e.errhdl(e.path, m, "E", "484", _i8(idem))
                    e.nederr = True
                    continue
                elif d.dxm > 100.0 or d.dxm < 1.0:
                    e.errhdl(e.path, m, "W", "485", _i8(idem))
            if d.iplan != 9 and d.cunit != 9:
                c = d.dmcnr
                c[1][1] = c[1][2]
                c[2][1] = c[2][2] - (d.dym * float(d.nrows - 1))
                c[1][3] = c[1][2] + (d.dxm * float(d.ncols - 1))
                c[2][3] = c[2][2]
                c[1][4] = c[1][3]
                c[2][4] = c[2][1]
            if d.iplan == 0:
                d.izo = utm_zona((d.dmcnr[1][1] + NUDGE) / 3600.0)
                if ((d.dmcnr[2][1] + NUDGE) / 3600.0) < 0.0:
                    d.izo = -1 * d.izo
                d.izond = d.izo
            if not (1 <= abs(d.izo) <= 60):
                e.errhdl(e.path, m, "E", "486", _i8(idem))
                e.nederr = True
                continue
        if (e.nada == 1 or e.nada >= 5) and 2 <= d.nadd <= 4:
            e.l_neednadcon = True
        elif 2 <= e.nada <= 4 and (d.nadd == 1 or d.nadd >= 5):
            e.l_neednadcon = True
    e.out.append("")
    e.out.append(" Exiting NEDCHK")


def _datum(e, m, d, idem, codigo, tabla):
    if codigo in tabla:
        d.nadd, aviso = tabla[codigo]
        if aviso:
            e.errhdl(e.path, m, "W", "470", aviso)
    elif e.nada == 0:
        e.errhdl(e.path, m, "W", "471", _i8(idem))
        d.nadd = 4
    else:
        e.errhdl(e.path, m, "E", "472", _i8(idem))
        e.nederr = True


# ====================================================================================== CNRCNV
def cnrcnv(e):
    m = "CNRCNV"
    for idem in range(1, e.numdem + 1):
        d = e.dem[idem]
        n = d.nadd
        isph = 0 if (n == 1 or 5 <= n <= 6) else 4
        c = d.dmcnr
        if d.cunit == 2:
            d.swe_m, d.swn_m = c[1][1], c[2][1]
            d.nwe_m, d.nwn_m = c[1][2], c[2][2]
            d.nee_m, d.nen_m = c[1][3], c[2][3]
            d.see_m, d.sen_m = c[1][4], c[2][4]
            for p in ("sw", "nw", "ne", "se"):
                _, _, _, slon, slat = utmgeo(333, d.izo, getattr(d, p + "e_m"),
                                             getattr(d, p + "n_m"), getattr(d, p + "lon_s"),
                                             getattr(d, p + "lat_s"), isph)
                setattr(d, p + "lon_s", slon)
                setattr(d, p + "lat_s", slat)
        elif d.cunit == 3:
            d.swlon_s, d.swlat_s = c[1][1], c[2][1]
            d.nwlon_s, d.nwlat_s = c[1][2], c[2][2]
            d.nelon_s, d.nelat_s = c[1][3], c[2][3]
            d.selon_s, d.selat_s = c[1][4], c[2][4]
            d.izo = utm_zona((d.swlon_s + NUDGE) / 3600.0)
            if (d.swlat_s + NUDGE) < 0.0:
                d.izo = -1 * d.izo
            for p in ("sw", "nw", "ne", "se"):
                _, este, norte, slon, _ = utmgeo(555, d.izo, getattr(d, p + "e_m"),
                                                 getattr(d, p + "n_m"), getattr(d, p + "lon_s"),
                                                 getattr(d, p + "lat_s"), isph)
                setattr(d, p + "e_m", este)
                setattr(d, p + "n_m", norte)
                setattr(d, p + "lon_s", slon)
        for p in ("sw", "nw", "ne", "se"):
            setattr(d, p + "lat_d", getattr(d, p + "lat_s") / 3600.0)
            setattr(d, p + "lon_d", getattr(d, p + "lon_s") / 3600.0)
        d.sw_z = d.izo
        d.nw_z = utm_zona((d.nwlon_s + NUDGE) / 3600.0)
        if d.nwlat_s - NUDGE < 0.0:
            d.nw_z = -1 * d.nw_z
        d.se_z = utm_zona((d.selon_s - NUDGE) / 3600.0)
        if d.selat_s + NUDGE < 0.0:
            d.se_z = -1 * d.se_z
        d.ne_z = utm_zona((d.nelon_s - NUDGE) / 3600.0)
        if d.nelat_s - NUDGE < 0.0:
            d.ne_z = -1 * d.ne_z
        d.izond = d.izo
    dems = e.dem[1:]
    zmin_dem = min(abs(min(x.sw_z for x in dems)), abs(min(x.nw_z for x in dems)),
                   abs(min(x.se_z for x in dems)), abs(min(x.ne_z for x in dems)))
    zmax_dem = max(abs(max(x.sw_z for x in dems)), abs(max(x.nw_z for x in dems)),
                   abs(max(x.se_z for x in dems)), abs(max(x.ne_z for x in dems)))
    multi = False
    cruce = (zmin_dem == 1 and zmax_dem == 60) or (zmin_dem == 60 and zmax_dem == 1)
    if abs(zmax_dem - zmin_dem) > 1 and not cruce:
        dummy = f"{zmin_dem:3d}  {zmax_dem:3d}"
        multi = True
        if not e.gotdomflg:
            e.errhdl(e.path, m, "E", "232", dummy)
            e.errhdl(e.path, m, "E", "233", "Zones   ")
        else:
            e.errhdl(e.path, m, "W", "234", dummy)
    if not e.gotdomflg:
        za = abs(e.zaterr)
        if zmin_dem == zmax_dem and zmin_dem == za:
            return
        if zmin_dem == zmax_dem and abs(zmin_dem - za) <= 1:
            return
        if abs(zmax_dem - zmin_dem) == 1 and (za == zmin_dem or za == zmax_dem):
            return
        if cruce and za in (1, 60):
            return
        if not multi and (za < zmin_dem or za > zmax_dem):
            e.errhdl(e.path, m, "E", "242", _i8(e.zaterr))


# ====================================================================================== CHKADJ
def chkadj(e):
    m = "CHKADJ"
    eps = 0.001
    d1 = e.dem[1]
    if d1.iplan == 0:
        e.typdem = "LAT "
        dmlat = d1.dym
        dmutm = _utm_de_lat(dmlat, eps)
    elif d1.iplan == 1 and d1.selat_s >= 1.8e5:
        e.typdem = "LAT "
        dmutm = d1.dym
        dmlat = _lat_de_utm(dmutm, eps)
    elif d1.iplan == 1:
        e.typdem = "UTM "
        dmutm = d1.dym
        dmlat = _lat_de_utm(dmutm, eps)
    else:
        e.typdem = "LAT "
        dmlat = d1.dym
        dmutm = _utm_de_lat(dmlat, eps)
    for idem in range(1, e.numdem + 1):
        d = e.dem[idem]
        if idem > 1:
            if d.iplan == 0:
                if (d.dym - dmlat + eps) < 0.0:
                    e.errhdl(e.path, m, "W", "325", _i8(idem))
                elif d.dym > dmlat:
                    dmlat = d.dym
                    dmutm = dmlat * 30.0
            elif d.iplan == 1:
                if (d.dym - dmutm + eps) < 0.0:
                    e.errhdl(e.path, m, "W", "325", _i8(idem))
                elif d.dym > dmutm:
                    dmutm = d.dym
                    dmlat = dmutm / 30.0
        if d.nadd == 0:
            if d.iplan == 0:
                d.nadd = 2 if abs(d.nelat_d - d.selat_d - 1.0) <= 0.001 else 1
            elif d.iplan == 1:
                d.nadd = 1
    if e.numdem > 1:
        for idem in range(1, e.numdem + 1):
            a = e.dem[idem]
            adyacente = False
            for jdem in range(1, e.numdem + 1):
                if idem == jdem:
                    continue
                b = e.dem[jdem]
                numadj = 0
                for p in ("sw", "nw", "ne", "se"):
                    lat1, lon1 = getattr(a, p + "lat_s"), getattr(a, p + "lon_s")
                    for q in ("sw", "nw", "ne", "se"):
                        diflat = lat1 - getattr(b, q + "lat_s")
                        diflon = lon1 - getattr(b, q + "lon_s")
                        if diflon > 648000.0:
                            diflon = 1296000.0 - diflon
                        elif diflon < -648000.0:
                            diflon = diflon + 1296000.0
                        if abs(diflat) < 1.0e-1 and abs(diflon) < 1.0e-1:
                            numadj += 1
                if numadj == 2:
                    adyacente = True
            if not adyacente:
                e.errhdl(e.path, m, "W", "340", _i8(idem))
    e.out.append(" Exiting CHKADJ")


def _utm_de_lat(dmlat, eps):
    for v, r in ((1.0 / 9.0, 3.0), (1.0 / 3.0, 10.0), (1.0, 30.0), (2.0, 60.0), (3.0, 90.0)):
        if abs(dmlat - v) < eps:
            return r
    return dmlat * 30.0


def _lat_de_utm(dmutm, eps):
    for v, r in ((3.0, 1.0 / 9.0), (10.0, 1.0 / 3.0), (30.0, 1.0), (90.0, 3.0)):
        if abs(dmutm - v) < eps:
            return r
    return dmutm / 30.0


# ====================================================================================== INITER_NED
def initer_ned(e):
    m = "INITER_NED"
    zminshft = zmaxshft = 0
    xdmn = ydmn = xdmx = ydmx = 0.0
    for idem in range(1, e.numdem + 1):
        d = e.dem[idem]
        typ = e.typdem.rstrip()
        if e.gotdomflg:
            nadflg = _nadflg(e.nada, d.nadd)
            if typ == "LAT":
                xdmn = e.domll[2][1] + (e.xdmndifs * nadflg)
                ydmn = e.domll[1][1] + (e.ydmndifs * nadflg)
                xdmx = e.domll[2][3] + (e.xdmxdifs * nadflg)
                ydmx = e.domll[1][3] + (e.ydmxdifs * nadflg)
            elif typ == "UTM":
                xdmn = e.xdmin + (e.xdmndifm * nadflg)
                ydmn = e.ydmin + (e.ydmndifm * nadflg)
                xdmx = e.xdmax + (e.xdmxdifm * nadflg)
                ydmx = e.ydmax + (e.ydmxdifm * nadflg)
                if nadflg == 0.0:
                    zminshft, zmaxshft = e.zonmin, e.zonmax
                else:
                    zminshft, zmaxshft = e.zonmin_shft, e.zonmax_shft
            fuera = False
            if typ == "LAT":
                if ((d.selon_s <= xdmn and d.nelon_s <= xdmn)
                        or (d.swlon_s >= xdmx and d.nwlon_s >= xdmx)):
                    fuera = True
                elif ((d.nelat_s <= ydmn and d.nwlat_s <= ydmn)
                      or (d.selat_s >= ydmx and d.swlat_s >= ydmx)):
                    fuera = True
            elif typ == "UTM":
                if ((d.se_z < zminshft) or (d.se_z == zminshft and d.see_m <= xdmn
                                            and d.nee_m <= xdmn)
                        or (d.sw_z > zmaxshft) or (d.sw_z == zmaxshft and d.swe_m >= xdmx
                                                   and d.nwe_m >= xdmx)):
                    fuera = True
                elif ((d.nen_m <= ydmn and d.nwn_m <= ydmn)
                      or (d.sen_m >= ydmx and d.swn_m >= ydmx)):
                    fuera = True
            if fuera:
                e.errhdl(e.path, m, "W", "380", _i8(idem))
                e.l_nedskip[idem] = True
                continue
        else:
            xdmn = ydmn = xdmx = ydmx = 0.0
            zminshft = zmaxshft = 0
        try:
            z = leer_elevaciones(e.demfil[idem].rstrip(), d)
        except OSError:
            e.errhdl(e.path, m, "E", "500", f"NED#{min(idem, 9999):4d}")
            e.runerr = True
            continue
        except EOFError:
            e.errhdl(e.path, m, "E", "510", f"NED#{min(idem, 9999):4d}")
            e.runerr = True
            continue
        if d.elunit == 1 or d.dci != 1.0 or d.tiez != 0.0:
            ok = z != -9999.0
            if d.elunit == 1:
                z = np.where(ok, ((z * d.dci) + d.tiez) * 0.3048, z)
            else:
                z = np.where(ok, (z * d.dci) + d.tiez, z)
        d.elevmn = float(z.min()) if z.size else 0.0
        d.elevmx = float(z.max()) if z.size else 0.0
        if d.iplan not in (0, 1):
            e.errhdl(e.path, m, "E", "510", f"NED#{min(idem, 9999):4d}")
            e.runerr = True
            continue
        _perfiles(e, d, typ, xdmn, ydmn, xdmx, ydmx, zminshft, zmaxshft, z)


def _nadflg(nada, nadd):
    if nada == 0 or nada == nadd:
        return 0.0
    if (nada == 1 or nada >= 5) and 2 <= nadd <= 4:
        return 1.0
    if 2 <= nada <= 4 and (nadd == 1 or nadd >= 5):
        return 1.0
    return 0.0


def _perfiles(e, d, typ, xdmn, ydmn, xdmx, ydmx, zminshft, zmaxshft, z):
    """Bucle de perfiles (columnas) y nodos de INITER_NED. Rellena el índice cuantizado y
    las cotas en el orden de los registros del fichero de acceso directo."""
    nrows, ncols = d.nrows, d.ncols
    geo = d.iplan == 0
    y0 = d.swlat_s if geo else d.swn_m
    x0 = d.swlon_s if geo else d.swe_m
    xbase = x0 + d.dxm * np.arange(ncols, dtype=np.float64)
    nodey = y0 + d.dym * np.arange(nrows, dtype=np.float64)
    mixto = e.gotdomflg and ((typ == "UTM" and d.iplan == 0) or (typ == "LAT" and d.iplan == 1))
    reg_x, reg_y, reg_n, reg_max, trozos = [], [], [], [], []
    numprf = 0
    if not mixto:
        if not e.gotdomflg:
            filas = np.arange(nrows)
        else:
            dentro = (nodey >= ydmn) & (nodey <= ydmx)
            mas = np.nonzero(nodey > ydmx)[0]
            lim = mas[0] if mas.size else nrows
            filas = np.nonzero(dentro[:lim])[0]
        for j in range(ncols):
            xb = xbase[j]
            if e.gotdomflg:
                if typ == "LAT" and d.iplan == 0:
                    if xb < xdmn:
                        continue
                    elif xb > xdmx:
                        break
                elif typ == "UTM" and d.iplan == 1:
                    if zminshft == zmaxshft:
                        if xb < xdmn:
                            continue
                        elif xb > xdmx:
                            break
                    elif d.izo == zminshft:
                        if xb < xdmn:
                            continue
                    elif d.izo == zmaxshft:
                        if xb > xdmx:
                            break
            col = z[filas, j]
            n = col.size
            if n:
                numprf += 1
                reg_y.append(nodey[filas[0]])
                reg_max.append(float(col.max()))
                trozos.append(col)
            else:
                reg_y.append(y0)
                reg_max.append(0.0)
            reg_x.append(xb)
            reg_n.append(n)
    else:
        isph = isphere_nadd(d)
        for j in range(ncols):
            xb = xbase[j]
            if typ == "UTM" and d.iplan == 0:
                _, xbutm, _, _, _ = utmgeo(555, 0, 0.0, 0.0, xb, y0, isph)
                if zminshft == zmaxshft:
                    if xbutm < xdmn:
                        continue
                    elif xbutm > xdmx:
                        break
                else:
                    iz, _, _, _, _ = utmgeo(555, 0, 0.0, 0.0, xb, y0, isph)
                    if iz == zminshft:
                        if xbutm < xdmn:
                            continue
                    elif iz == zmaxshft:
                        if xbutm > xdmx:
                            break
            else:
                _, _, _, xblon, _ = utmgeo(333, d.izo, xb, y0, 0.0, 0.0, isph)
                if xblon < xdmn:
                    continue
                elif xblon > xdmx:
                    break
            sel = []
            for k in range(nrows):
                ny = nodey[k]
                if typ == "UTM":
                    _, _, yv, _, _ = utmgeo(555, 0, 0.0, 0.0, xb, ny, isph)
                else:
                    _, _, _, _, yv = utmgeo(333, d.izo, xb, ny, 0.0, 0.0, isph)
                if (ydmn <= yv <= ydmx) or (ydmn <= ny <= ydmx):
                    sel.append(k)
                elif yv > ydmx or ny > ydmx:
                    break
            filas = np.array(sel, dtype=np.int64)
            col = z[filas, j]
            n = col.size
            if n:
                numprf += 1
                reg_y.append(nodey[filas[0]])
                reg_max.append(float(col.max()))
                trozos.append(col)
            else:
                reg_y.append(y0)
                reg_max.append(0.0)
            reg_x.append(xb)
            reg_n.append(n)
    d.numprf = numprf
    d.idx_x = np.array([_q_d24(v) for v in reg_x], dtype=np.float64)
    d.idx_y = np.array([_q_d24(v) for v in reg_y], dtype=np.float64)
    d.idx_n = np.array(reg_n, dtype=np.int64)
    d.idx_z = np.full(len(reg_n), d.izo, dtype=np.int64)
    d.idx_max = np.array([_q_f155(v) for v in reg_max], dtype=np.float64)
    d.elev = np.concatenate(trozos) if trozos else np.zeros(0)
