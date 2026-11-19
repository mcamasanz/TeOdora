# -*- coding: utf-8 -*-
"""Traducción de AERMAP v24142 (US EPA, dominio público): dominio y asignación de puntos
(sub_domcnv.f, sub_reccnv.f, sub_srccnv.f, sub_chkext.f, sub_demrec.f, sub_demsrc.f).

Solo se traduce la rama SIN conversión NAD27<->NAD83 (NADCON): o bien NADA = 0, o bien el
datum de todos los ficheros coincide con el del ancla. La rama NADCON solo sirve en EE. UU.
y el programa principal se detiene antes de llegar aquí si hiciera falta."""
from .estado import vec
from .mdt_externo import isphere_nadd, _nadflg
from .utm import utmgeo


def _isphere_nada(e):
    """SELECT CASE (NADA) de DOMCNV/RECCNV/SRCCNV."""
    n = e.nada
    if n == 0:
        t = e.typdem.rstrip()
        return 0 if t == "UTM" else (4 if t == "LAT" else getattr(e, "_isph_prev", 4))
    if 2 <= n <= 4:
        return 4
    if n == 1 or 5 <= n <= 6:
        return 0
    return 4


def _a_geo(este, norte, zona, isph):
    """UTMGEO 333 con ARGE = ARGN = 0 al entrar -> (slon, slat)."""
    _, _, _, slon, slat = utmgeo(333, zona, este, norte, 0.0, 0.0, isph)
    return slon, slat


def _a_utm(slon, slat, zona, isph):
    """UTMGEO 555 con XARG = YARG = 0 -> (zona_salida, este, norte, slon_modificada)."""
    iz, este, norte, slon2, _ = utmgeo(555, zona, 0.0, 0.0, slon, slat, isph)
    return iz, este, norte, slon2


# ====================================================================================== DOMCNV
def domcnv(e):
    m = "DOMCNV"
    isph = _isphere_nada(e)
    dl = e.domll
    typ = e.typdem.rstrip()
    if typ == "LAT":
        if e.domtyp == "LAT":
            for y in (e.ydmin, e.ydmax):
                if abs(y) > 66.0:
                    e.errhdl(e.path, m, "W", "360", f"{y:8.2f}")
            dl[2][1] = e.xdmin * 3600.0
            dl[1][1] = e.ydmin * 3600.0
            dl[2][3] = e.xdmax * 3600.0
            dl[1][3] = e.ydmax * 3600.0
        elif e.domtyp == "UTM":
            dl[2][1], dl[1][1] = _a_geo(e.xdmin, e.ydmin, e.zonmin, isph)
            dl[2][3], dl[1][3] = _a_geo(e.xdmax, e.ydmax, e.zonmax, isph)
        dl[2][2] = dl[2][1]
        dl[1][2] = dl[1][3]
        dl[2][4] = dl[2][3]
        dl[1][4] = dl[1][1]
        e.zonmin, e.xdmin, e.ydmin, _ = _a_utm(dl[2][1], dl[1][1], 0, isph)
        e.zonmax, e.xdmax, e.ydmax, _ = _a_utm(dl[2][3], dl[1][3], 0, isph)
    elif typ == "UTM":
        if e.domtyp == "LAT":
            for y in (e.ydmin, e.ydmax):
                if abs(y) > 66.0:
                    e.errhdl(e.path, m, "W", "360", f"{y:8.2f}")
            e.zonmin, e.xdmin, e.ydmin, _ = _a_utm(e.xdmin * 3600.0, e.ydmin * 3600.0, 0, isph)
            e.zonmax, e.xdmax, e.ydmax, _ = _a_utm(e.xdmax * 3600.0, e.ydmax * 3600.0, 0, isph)
        elif e.domtyp == "UTM":
            for k, (xn, yn, zn) in ((1, ("xdmin", "ydmin", "zonmin")),
                                    (3, ("xdmax", "ydmax", "zonmax"))):
                izone = getattr(e, zn)
                arge, argn = _a_geo(getattr(e, xn), getattr(e, yn), izone, isph)
                dl[2][k], dl[1][k] = arge, argn
                iznew, xarg, yarg, arge2 = _a_utm(arge, argn, 0, isph)
                if iznew != izone:
                    dl[2][k], dl[1][k] = arge2, argn
                    setattr(e, xn, xarg)
                    setattr(e, yn, yarg)
                    setattr(e, zn, iznew)
        dl[2][1], dl[1][1] = _a_geo(e.xdmin, e.ydmin, e.zonmin, isph)
        dl[2][3], dl[1][3] = _a_geo(e.xdmax, e.ydmax, e.zonmax, isph)
        dl[2][2], dl[1][2] = _a_geo(e.xdmin, e.ydmax, e.zonmin, isph)
        dl[2][4], dl[1][4] = _a_geo(e.xdmax, e.ydmin, e.zonmax, isph)
    e.xdmndifs = e.ydmndifs = e.xdmxdifs = e.ydmxdifs = 0.0
    e.xdmndifm = e.ydmndifm = e.xdmxdifm = e.ydmxdifm = 0.0
    e.zonmin_shft = e.zonmin
    e.zonmax_shft = e.zonmax
    e.out.append(" Exiting DOMCNV")


# =============================================================================== RECCNV / SRCCNV
def puntos_cnv(e, fuentes):
    """RECCNV (fuentes=False) / SRCCNV (fuentes=True), rama sin NADCON."""
    isph = _isphere_nada(e)
    n = e.numsrc if fuentes else e.numrec
    ax = e.axs if fuentes else e.axr
    ay = e.ays if fuentes else e.ayr
    xu, yu, iz = vec(n), vec(n), vec(n, 0)
    lon, lat = vec(n), vec(n)
    for i in range(1, n + 1):
        xu[i] = ax[i] - e.xauser + e.xaterr
        yu[i] = ay[i] - e.yauser + e.yaterr
        iz[i] = e.zaterr
        arge, argn = _a_geo(xu[i], yu[i], iz[i], isph)
        lon[i], lat[i] = arge, argn
        iznew, xarg, yarg, arge2 = _a_utm(arge, argn, 0, isph)
        if iznew != iz[i]:
            lon[i], lat[i] = arge2, argn
            xu[i], yu[i] = xarg, yarg
            iz[i] = iznew
    if fuentes:
        e.xsrcu, e.ysrcu, e.izons, e.slon, e.slat = xu, yu, iz, lon, lat
        e.out.append(" Exiting SRCCNV")
    else:
        e.xrecu, e.yrecu, e.izonr, e.rlon, e.rlat = xu, yu, iz, lon, lat
        e.out.append(" Exiting RECCNV")


# ====================================================================================== CHKEXT
def chkext(e):
    m = "CHKEXT"
    typ = e.typdem.rstrip()
    dl = e.domll

    def dentro(lat, lon, xu, yu, iz):
        if typ == "LAT":
            return dl[1][1] <= lat <= dl[1][2] and dl[2][1] <= lon <= dl[2][3]
        if typ == "UTM":
            if e.zonmin == e.zonmax:
                return e.xdmin <= xu <= e.xdmax and e.ydmin <= yu <= e.ydmax
            if iz == e.zonmin:
                return xu >= e.xdmin and e.ydmin <= yu <= e.ydmax
            if iz == e.zonmax:
                return xu <= e.xdmax and e.ydmin <= yu <= e.ydmax
            return True                       # ninguna rama: el original no avisa
        return True

    for i in range(1, e.numrec + 1):
        if not dentro(e.rlat[i], e.rlon[i], e.xrecu[i], e.yrecu[i], e.izonr[i]):
            e.errhdl(e.path, m, "E", "300", f"{i:8d}")
    for i in range(1, e.numsrc + 1):
        if not dentro(e.slat[i], e.slon[i], e.xsrcu[i], e.ysrcu[i], e.izons[i]):
            e.errhdl(e.path, m, "E", "305", e.srcid[i])
    domin = [0] * 5
    for idom in range(1, 5):
        if domin[idom] != 0:
            continue
        for idem in range(1, e.numdem + 1):
            d = e.dem[idem]
            nadflg = _nadflg(e.nada, d.nadd)
            if idom == 1:
                s1 = dl[1][idom] + (e.ydmndifs * nadflg)
                s2 = dl[2][idom] + (e.xdmndifs * nadflg)
                dx, dy = e.xdmin + (e.xdmndifm * nadflg), e.ydmin + (e.ydmndifm * nadflg)
            elif idom == 2:
                s1 = dl[1][idom] + (e.ydmxdifs * nadflg)
                s2 = dl[2][idom] + (e.xdmndifs * nadflg)
                dx, dy = e.xdmin + (e.xdmndifm * nadflg), e.ydmax + (e.ydmxdifm * nadflg)
            elif idom == 3:
                s1 = dl[1][idom] + (e.ydmxdifs * nadflg)
                s2 = dl[2][idom] + (e.xdmxdifs * nadflg)
                dx, dy = e.xdmax + (e.xdmxdifm * nadflg), e.ydmax + (e.ydmxdifm * nadflg)
            else:
                s1 = dl[1][idom] + (e.ydmndifs * nadflg)
                s2 = dl[2][idom] + (e.xdmxdifs * nadflg)
                dx, dy = e.xdmax + (e.xdmxdifm * nadflg), e.ydmin + (e.ydmndifm * nadflg)
            if typ == "UTM":
                rlat, rlon = s1, s2
                if nadflg == 0.0:
                    zmin, zmax = e.zonmin, e.zonmax
                else:
                    zmin, zmax = e.zonmin_shft, e.zonmax_shft
                if (idom in (1, 2) and zmin != d.izond) or (idom in (3, 4) and zmax != d.izond):
                    _, dx, dy, _ = _a_utm(rlon, rlat, d.izond, isphere_nadd(d))
            utm_ok = (typ == "UTM" and d.iplan == 1
                      and abs(d.nwe_m - d.swe_m) < 0.05 * d.dxm
                      and abs(d.nee_m - d.see_m) < 0.05 * d.dxm
                      and d.swe_m <= dx <= d.nee_m and d.swn_m <= dy <= d.nen_m)
            geo_ok = d.swlat_s <= s1 <= d.nelat_s and d.swlon_s <= s2 <= d.nelon_s
            if utm_ok or geo_ok:
                domin[idom] = 1
                break
            domin[idom] = 0
    for idom in range(1, 5):
        if domin[idom] == 0:
            e.errhdl(e.path, m, "E", "310", f"{idom:8d}")
    e.out.append(" Exiting CHKEXT")


# =============================================================================== DEMREC / DEMSRC
def puntos_dem(e, fuentes):
    """DEMREC (fuentes=False) / DEMSRC (fuentes=True): fichero de terreno de cada punto."""
    eps = 0.001
    if fuentes:
        m, n = "DEMSRC", e.numsrc
        lon, lat, xu, yu, iz = e.slon, e.slat, e.xsrcu, e.ysrcu, e.izons
        tabla = e.isin
        ident = lambda i: e.srcid[i]
        c_mult, c_res, c_gap, c_gap2 = "333", "327", "335", "336"
        txt = ("Sources!", "sources", "SOURCE", "Gap", "sources")
    else:
        m, n = "DEMREC", e.numrec
        lon, lat, xu, yu, iz = e.rlon, e.rlat, e.xrecu, e.yrecu, e.izonr
        tabla = e.irin
        ident = lambda i: f"{i:8d}"
        c_mult, c_res, c_gap, c_gap2 = "332", "326", "330", "331"
    jdm = vec(n, 0)
    nrecd = vec(n, 0)
    td = e.typdat[:3]

    def en_fichero(d, x, y, slon, slat):
        return ((d.iplan == 1 and abs(d.nwe_m - d.swe_m) < 0.05 * d.dxm
                 and abs(d.nee_m - d.see_m) < 0.05 * d.dxm
                 and d.swe_m <= x <= d.nee_m and d.swn_m <= y <= d.nen_m)
                or (d.swlon_s <= slon <= d.nelon_s and d.swlat_s <= slat <= d.nelat_s))

    for i in range(1, n + 1):
        for idem in range(1, e.numdem + 1):
            d = e.dem[idem]
            rlon, rlat = lon[i], lat[i]            # desplazamiento NAD nulo
            x, y = xu[i], yu[i]
            if iz[i] != d.izond:
                _, x, y, _ = _a_utm(rlon, rlat, d.izond, isphere_nadd(d))
            if en_fichero(d, x, y, rlon, rlat):
                if jdm[i] == 0:
                    jdm[i] = idem
                    nrecd[i] = 1
                    tabla[i][idem] = 1
                else:
                    nrecd[i] += 1
                    tabla[i][idem] = 1
                    a = e.dem[jdm[i]]
                    if _peor_resolucion(a, d, eps):
                        e.errhdl(e.path, m, "E", c_res, ident(i))
        if nrecd[i] > 1:
            e.errhdl(e.path, m, "W", c_mult, ident(i))
    ngap = 0
    for i in range(1, n + 1):
        if jdm[i] == 0:
            ngap += 1
            e.errhdl(e.path, m, "W", c_gap, ident(i))
    if fuentes:
        e.nsgap = ngap
    else:
        e.nrgap = ngap
    if ngap:
        quien = "Sources!" if fuentes else "Receptors!"
        e.out += ["", "******", f'{m}:  Reprocessing {td}s for {ngap:7d}  "Gap" {quien}',
                  "******", ""]
        for i in range(1, n + 1):
            if jdm[i] != 0:
                continue
            for idem in range(1, e.numdem + 1):
                d = e.dem[idem]
                if iz[i] != d.izond:
                    _, x, y, _ = _a_utm(lon[i], lat[i], d.izond, isphere_nadd(d))
                else:
                    x, y = xu[i], yu[i]
                if en_fichero(d, x, y, lon[i], lat[i]):
                    if fuentes:
                        e.nsgap2 += 1
                    else:
                        e.nrgap2 += 1
                    e.gapsfound = True
                    for jdem in range(1, e.numdem + 1):
                        dj = e.dem[jdem]
                        x2, y2 = xu[i], yu[i]
                        if iz[i] != dj.izond:
                            _, x2, y2, _ = _a_utm(lon[i], lat[i], dj.izond, isphere_nadd(dj))
                        if en_fichero(dj, x2, y2, lon[i], lat[i]):
                            jdm[i] = jdem
                            tabla[i][jdem] = 2
                if jdm[i] > 0:
                    break
        n2 = e.nsgap2 if fuentes else e.nrgap2
        q = "sources" if fuentes else "receptors"
        e.out += ["", "******", f'{m}:  A total of {n2:7d} "Gap" {q} were',
                  f"         assigned to {td} files on the 2nd Pass.",
                  "         Depending on the size of the gap, these",
                  f"         {q} may be assigned missing elevations",
                  '         unless the "FILLGAPS" option on the DATATYPE',
                  "         keyword is specified.",
                  "         These gaps are due to NAD conversion issues,",
                  "         which should be resolved with the use of ",
                  "         standard NED elevation data.", "******", ""]
        for i in range(1, n + 1):
            if jdm[i] == 0:
                e.runerr = True
                e.errhdl(e.path, m, "E", c_gap2, ident(i))
                quien = "SOURCE" if fuentes else "RECEPTOR"
                e.out.append(f" *** {quien} NOT ASSIGNED TO FILE - SECOND PASS:")
                etiqueta = "SRC#: " if fuentes else "REC#: "
                e.out.append(f"{etiqueta}{i:5d}  UTM(E/N/Z):{xu[i]:20.3f}{yu[i]:20.3f}{iz[i]:4d}")
                e.out.append(f"{'':16s}Lat/Lon:{lat[i] / 3600.0:20.7f}{lon[i] / 3600.0:20.7f}"
                             f"  NAD: {e.nada:2d}")
    if fuentes:
        e.jdms = jdm
    else:
        e.jdm = jdm
    e.out.append(f" Exiting {m}")


def _peor_resolucion(a, d, eps):
    """Condiciones del error 326/327: el punto se asignó antes a un fichero de PEOR
    resolución que otro que también lo contiene."""
    if a.iplan == 0 and d.iplan == 0:
        return a.dym > d.dym + eps
    if a.iplan == 1 and d.iplan == 1:
        return a.dym > d.dym + eps
    if a.iplan == 0:
        for v, r in ((1.0 / 9.0, 3.0), (1.0 / 3.0, 10.0), (1.0, 30.0), (2.0, 60.0), (3.0, 90.0)):
            if abs(a.dym - v) < eps:
                return r > d.dym + eps
        return False
    if a.iplan == 1:
        for v, r in ((3.0, 1.0 / 9.0), (10.0, 1.0 / 3.0), (30.0, 1.0), (90.0, 3.0)):
            if abs(a.dym - v) < eps:
                return r > d.dym + eps
        return False
    return False
