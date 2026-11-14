# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): resultados finales (parte final del
programa principal de aermod.f y output.f: PERAVE, HIPER, PSTANN, PLTANN, PLOTFL, OUTPUT, PRTANN,
PRTNHI, SPRTHT, PRTMAX, PRTSUM) y las tablas diarias de DAYTABLE (PRTDAY, calc2.f)."""
import math
import struct

from .estado import NoTraducido
from .formato import fwrite, fx, lw

_RANK = ["", "  1ST", "  2ND", "  3RD", "  4TH", "  5TH", "  6TH", "  7TH", "  8TH", "  9TH",
         " 10TH"]
_NCHR1 = ["", "YR1", "YR2", "YR3", "YR4", "YR5", "YR6", "YR7", "YR8", "YR9", "Y10"]


def final(e):
    """Tras HRLOOP: promedios del periodo, ficheros de gráficos y tablas del fichero de salida."""
    m = "MAIN"
    if (e.WDPLETE or e.DEPOS or e.WDEP) and e.TOTAL_PRECIP < 0.0001:
        e.errhdl(e.PATH, m, "W", "496", "WetDepos")
    if (e.PM25AVE or e.NO2AVE or e.SO2AVE or e.ANNUAL) and e.MULTYR and not e.RUNERR:
        # MULTYEAR con resultados promediados entre años: SAVEFILE antes de promediar
        from . import reinicio
        reinicio.rsdump(e)
        if e.SEASONHR and not e.RUNERR:
            if e.CONC:
                shave(e)
                if e.FILE_FORMAT != "EXP" and _maxval(e.SHVALS) > 9999.99999999:
                    e.errhdl(e.PATH, m, "W", "400", "= EXP")
    if (e.PM25AVE or e.NO2AVE or e.SO2AVE or e.ANNUAL) and not e.RUNERR:
        if e.NUMYRS > 0:
            nr, ng = e.NUMREC, e.NUMGRP
            for igrp in range(1, ng + 1):
                for irec in range(1, nr + 1):
                    if e.PM25AVE or e.NO2AVE or e.SO2AVE:
                        e.SUMHNH[irec, igrp, 1:e.NHIVAL + 1] = \
                            e.SUMHNH[irec, igrp, 1:e.NHIVAL + 1] / float(e.NUMYRS)
                    if e.ANNUAL:
                        for ityp in range(1, e.NUMTYP + 1):
                            e.ANNVAL[irec, igrp, ityp] = e.SUMANN[irec, igrp, ityp] / \
                                float(e.NUMYRS)
        else:
            if e.ANNUAL:
                e.errhdl(e.PATH, m, "E", "480", "NUMYRS=0")
                e.RUNERR = True
            elif e.NO2AVE:
                e.errhdl(e.PATH, m, "E", "480", "1hr NO2AVE")
                e.RUNERR = True
            elif e.SO2AVE:
                e.errhdl(e.PATH, m, "E", "480", "1hr SO2AVE")
                e.RUNERR = True
            elif e.PM25AVE:
                e.errhdl(e.PATH, m, "E", "480", "24hr PM25AVE")
                e.RUNERR = True
        if e.NREMAIN != 0:
            if not e.L_SKIPMESSAGES:
                e.errhdl(e.PATH, m, "W", "481", fwrite("(I8)", e.NREMAIN)[0])
    if (e.PERIOD or e.ANNUAL) and not e.RUNERR and e.NTOTHRS > 0:
        if e.CONC and e.PERIOD:
            perave(e)
        if e.FILE_FORMAT != "EXP" and _maxval(e.ANNVAL) > 9999999.99999:
            e.errhdl(e.PATH, m, "W", "400", "= EXP")
        for ityp in range(1, e.NUMTYP + 1):
            e.ITYP = ityp
            hiper(e)
        if e.ANPOST and e.PERIOD:
            pstann(e)
        if e.ANPLOT:
            pltann(e)
    if e.MULTYR and not e.RUNERR and not (e.ANNUAL or e.PM25AVE or e.NO2AVE or e.SO2AVE):
        from . import reinicio
        reinicio.rsdump(e)
    if not (e.MULTYR and (e.ANNUAL or e.PM25AVE or e.NO2AVE or e.SO2AVE)) and e.SEASONHR \
            and not e.RUNERR:
        if e.CONC:
            shave(e)
            if e.FILE_FORMAT != "EXP" and _maxval(e.SHVALS) > 9999.99999999:
                e.errhdl(e.PATH, m, "W", "400", "= EXP")
    if e.PLFILE and not e.RUNERR:
        _aviso_exp(e)
        plotfl(e)
    if not e.RUNERR:
        if not e.PLFILE:
            _aviso_exp(e)
        output(e)
    if not e.RUNERR and e.L_MAXDCONT and (e.PM25AVE or e.NO2AVE or e.SO2AVE):
        from . import contribuciones
        contribuciones.maxdcont_loop(e)


def _maxval(a):
    if a is None or a.size == 0:
        return -1.7976931348623157e308
    v = a if a.ndim == 0 else _interior(a)
    if v.size == 0:
        return -1.7976931348623157e308     # MAXVAL de una matriz vacía: -HUGE
    return float(v.max())


def _interior(a):
    return a[(slice(1, None),) * a.ndim]


def _aviso_exp(e):
    if e.FILE_FORMAT != "EXP":
        if e.PM25AVE or e.NO2AVE or e.SO2AVE:
            if _maxval(e.SUMHNH) > 9999999.99999:
                e.errhdl(e.PATH, "MAIN", "W", "400", "= EXP")
        elif _maxval(e.HIVALU) > 9999999.99999:
            e.errhdl(e.PATH, "MAIN", "W", "400", "= EXP")


# --------------------------------------------------------------------------------- PERAVE
def perave(e):
    """PERAVE: promedio del periodo."""
    snum = float(e.IANHRS - e.IANCLM - e.IANMSG)
    if e.SCIM:
        raise NoTraducido("SCIM")
    nr, ng = e.NUMREC, e.NUMGRP
    for ityp in range(1, e.NUMTYP + 1):
        e.ITYP = ityp
        if e.OUTTYP[ityp] == "CONC":
            e.ANNVAL[1:nr + 1, 1:ng + 1, 1] = e.ANNVAL[1:nr + 1, 1:ng + 1, 1] / snum
    e.ITYP = e.NUMTYP + 1


def hiper(e):
    """HIPER: los NHIANN valores más altos del periodo."""
    it = e.ITYP
    nh = e.NHIANN
    av, im = e.AMXVAL, e.IMXLOC
    for igrp in range(1, e.NUMGRP + 1):
        for irec in range(1, e.NUMREC + 1):
            a = e.ANNVAL[irec, igrp, it]
            if nh > 1:
                if a > av[nh, igrp, it]:
                    for j in range(nh - 1, 0, -1):
                        if a <= av[j, igrp, it]:
                            av[j + 1, igrp, it] = a
                            im[j + 1, igrp, it] = irec
                            break
                        av[j + 1, igrp, it] = av[j, igrp, it]
                        im[j + 1, igrp, it] = im[j, igrp, it]
                        if j == 1:
                            av[1, igrp, it] = a
                            im[1, igrp, it] = irec
            elif nh == 1:
                if a > av[1, igrp, it]:
                    av[1, igrp, it] = a
                    im[1, igrp, it] = irec
    e.IGRP = e.NUMGRP + 1
    e.IREC = e.NUMREC + 1


# ------------------------------------------------------------------------ ficheros PLOT
def _cab_comun(e, con_title2):
    out = fwrite("('* AERMOD (',A6,'): ',A68,5X,A8)", fx(e.VERSN, 6), fx(e.TITLE1, 68),
                 fx(e.RUNDAT, 8))
    mod = e.MODOPS_STRING.rstrip(" ")
    if con_title2:
        out += fwrite("('* AERMET (',A6,'): ',A68,T93,A8,/'* MODELING OPTIONS USED: ',A:)",
                      fx(e.C_METVER, 6), fx(e.TITLE2, 68), fx(e.RUNTIM, 8), mod)
    else:
        out += fwrite("('* AERMET (',A6,'):',T93,A8,/'* MODELING OPTIONS USED: ',A:)",
                      fx(e.C_METVER, 6), fx(e.RUNTIM, 8), mod)
    return out


def _hdr_ann(e, etiqueta):
    n = e.NUMTYP
    fmt = ("('*',8X,'X',13X,'Y',4X,%d(2X,3A4),4X,'ZELEV',4X,'ZHILL',4X,'ZFLAG',4X,'AVE',5X,"
           "'GRP',%s,3X,'NET ID',/,'*',%d(1X,'____________ '),1X,3(' ______  '),"
           "'______  ________  ________  ________')" % (n, etiqueta, n + 2))
    items = []
    for t in range(1, n + 1):
        items += [fx(e.CHIDEP[1, t], 4), fx(e.CHIDEP[2, t], 4), fx(e.CHIDEP[3, t], 4)]
    return fwrite(fmt, *items)


def _lineas_ann(e, igrp, perchr):
    lineas = []
    nt = e.NUMTYP
    grp = fx(e.GRPID[igrp], 8)
    num = e.IANHRS if e.PERIOD else e.NUMYRS
    fmt = e.PSTFRM.rstrip(" ")
    for irec in range(1, e.NUMREC + 1):
        lineas += fwrite(fmt, e.AXR[irec], e.AYR[irec],
                         *[e.ANNVAL[irec, igrp, it] for it in range(1, nt + 1)],
                         e.AZELEV[irec], e.AZHILL[irec], e.AZFLAG[irec], perchr, grp, num,
                         fx(e.NETID[irec], 8))
    return lineas


def pstann(e):
    """PSTANN: fichero de posproceso con los promedios del periodo."""
    if e.PERIOD:
        perchr = "PERIOD"
        etq = "6X,'NUM HRS'"
    else:
        perchr = "ANNUAL"
        etq = "5X,'YEAR NUM'"
    nr, nt = e.NUMREC, e.NUMTYP
    for igrp in range(1, e.NUMGRP + 1):
        e.IGRP = igrp
        if e.IANPST[igrp] != 1:
            continue
        u = e.IAPUNT[igrp]
        if e.IANFRM[igrp] == 0:
            n = e.IANHRS if e.PERIOD else e.NUMYRS
            datos = struct.pack("<ii", int(e.KURDAT), int(n)) + \
                fx(e.GRPID[igrp], 8).encode("latin-1")
            datos += e.ANNVAL[1:nr + 1, igrp, 1:nt + 1].T.astype("<f8").tobytes()
            e.U[u].reg(datos)
        else:
            out = _cab_comun(e, False)
            pst = fx(e.PSTFRM, 200)
            if e.PERIOD:
                out += fwrite("('*',9X,'POST/PLOT FILE OF ',A6,' VALUES FOR ','SOURCE GROUP: ',"
                              "A8,/'*',9X,'FOR A TOTAL OF ', I5,' RECEPTORS.',/'*',9X,'FORMAT: ',"
                              "A:)", perchr, fx(e.GRPID[igrp], 8), e.NUMREC, pst)
            else:
                out += fwrite("('*',9X,'POST/PLOT FILE OF ',A6,' VALUES FOR YEAR ',I3,' FOR "
                              "SOURCE GROUP: ',A8,/'*',9X,'FOR A TOTAL OF ', I5,' RECEPTORS.',"
                              "/'*',9X,'FORMAT: ',A:)", perchr, e.NUMYRS, fx(e.GRPID[igrp], 8),
                              e.NUMREC, pst)
            out += _hdr_ann(e, etq)
            out += _lineas_ann(e, igrp, perchr)
            e.w(u, out)


def pltann(e):
    """PLTANN: fichero de gráficos con los promedios del periodo."""
    if e.PERIOD:
        perchr = "PERIOD"
    else:
        perchr = "ANNUAL"
    etq = "6X,'NUM HRS'" if e.PERIOD else "6X,'NUM YRS'"
    for igrp in range(1, e.NUMGRP + 1):
        e.IGRP = igrp
        if e.IANPLT[igrp] != 1:
            continue
        out = _cab_comun(e, False)
        out += fwrite("('*',9X,'PLOT FILE OF ',A6,' VALUES AVERAGED ACROSS ',I3,' YEARS FOR "
                      "SOURCE GROUP: ',A8,/'*',9X,'FOR A TOTAL OF ', I5,' RECEPTORS.',/'*',9X,"
                      "'FORMAT: ',A:)", perchr, e.NUMYRS, fx(e.GRPID[igrp], 8), e.NUMREC,
                      fx(e.PSTFRM, 200))
        out += _hdr_ann(e, etq)
        out += _lineas_ann(e, igrp, perchr)
        e.w(e.IPPUNT[igrp], out)


def _chrval(ival):
    if ival <= 10:
        return _RANK[ival]
    if 10 < ival % 100 < 20:
        return fwrite('(I2,I1,"TH")', ival // 10, ival % 10)[0]
    if ival <= 999:
        imod = ival % 10
        if imod == 0:
            imod = 10
        return fwrite("(I2,A3)", ival // 10, _RANK[imod][2:5])[0]
    return None


def plotfl(e):
    """PLOTFL: ficheros de gráficos de los valores altos por receptor."""
    diario = e.PM25AVE or e.NO2AVE or e.SO2AVE
    n = e.NUMTYP
    ny = e.NUMYRS
    yr = ("YR1", "YR2", "YR3", "YR4", "YR5", "YR6", "YR7", "YR8", "YR9", "Y10")
    if diario:
        hdrfrm = ("('*',8X,'X',13X,'Y',4X,(2X,3A4),4X,'ZELEV',4X,'ZHILL',4X,'ZFLAG',4X,'AVE',5X,"
                  "'GRP',7X,'RANK',5X,'NET ID',1X,%s(2X,'AVER CONC ',A3,'  DATE ',A3),/,'*',"
                  "3(1X,'____________ '),1X,3(' ______  '),'______  ________  ________  ________',"
                  "%s('  _____________  ________'))"
                  % (fwrite("(I1)", ny)[0], fwrite("(I1)", ny)[0]))
        hitems = [fx(e.CHIDEP[1, 1], 4), fx(e.CHIDEP[2, 1], 4), fx(e.CHIDEP[3, 1], 4)]
        for i in range(ny):
            hitems += [yr[i], yr[i]]
    else:
        hdrfrm = ("('*',8X,'X',13X,'Y',4X,%d(2X,3A4),4X,'ZELEV',4X,'ZHILL',4X,'ZFLAG',4X,'AVE',5X,"
                  "'GRP',7X,'RANK',5X,'NET ID',3X,'DATE(%s)',/,'*',%d(1X,'____________ '),1X,"
                  "3(' ______  '),'______  ________  ________  ________  ________')"
                  % (n, fx(e.CHIDEP[3, 1], 4), n + 2))
        hitems = []
        for t in range(1, n + 1):
            hitems += [fx(e.CHIDEP[1, t], 4), fx(e.CHIDEP[2, t], 4), fx(e.CHIDEP[3, t], 4)]
    pltfrm = e.PLTFRM.rstrip(" ")
    chrval = None
    for iave in range(1, e.NUMAVE + 1):
        e.IAVE = iave
        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            for ival in range(1, e.NHIVAL + 1):
                if e.IPLTFL[ival, igrp, iave] != 1:
                    continue
                c = _chrval(ival)
                if c is not None:
                    chrval = c
                u = e.IPLUNT[ival, igrp, iave]
                out = []
                if not e.L_NOHEADER[3]:
                    out += _cab_comun(e, True)
                    if diario:
                        out += fwrite("('*',9X,'PLOT FILE OF ',A5,'-HIGHEST MAX DAILY ',A5,' VALUES "
                                      "AVERAGED OVER ',I3,' YEARS FOR SOURCE GROUP: ',A8,/'*',9X,"
                                      "'FOR A TOTAL OF ',I5,' RECEPTORS.',/'*',9X,'FORMAT: ',A:)",
                                      chrval, fx(e.CHRAVE[iave], 5), ny, fx(e.GRPID[igrp], 8),
                                      e.NUMREC, fx(e.PLTFRM, 200))
                    else:
                        out += fwrite("('*',9X,'PLOT FILE OF  HIGH ',A5,' HIGH ',A5,' VALUES FOR "
                                      "SOURCE GROUP: ',A8,/'*',9X,'FOR A TOTAL OF ',I5,' RECEPTORS.',"
                                      "/'*',9X,'FORMAT: ',A:)", chrval, fx(e.CHRAVE[iave], 5),
                                      fx(e.GRPID[igrp], 8), e.NUMREC, fx(e.PLTFRM, 200))
                    out += fwrite(hdrfrm, *hitems)
                ca = fx(e.CHRAVE[iave], 5)
                grp = fx(e.GRPID[igrp], 8)
                for irec in range(1, e.NUMREC + 1):
                    if diario:
                        anos = []
                        for j in range(1, ny + 1):
                            anos += [e.HIMXDLY_BYYR[irec, igrp, ival, j],
                                     e.NHIDATMXD_BYYR[irec, igrp, ival, j]]
                        out += fwrite(pltfrm, e.AXR[irec], e.AYR[irec], e.SUMHNH[irec, igrp, ival],
                                      e.AZELEV[irec], e.AZHILL[irec], e.AZFLAG[irec], ca, grp, chrval,
                                      fx(e.NETID[irec], 8), *anos)
                    else:
                        out += fwrite(pltfrm, e.AXR[irec], e.AYR[irec],
                                      *[e.HIVALU[irec, ival, igrp, iave, it] for it in range(1, n + 1)],
                                      e.AZELEV[irec], e.AZHILL[irec], e.AZFLAG[irec], ca, grp, chrval,
                                      fx(e.NETID[irec], 8), e.NHIDAT[irec, ival, igrp, iave, 1])
                e.w(u, out)


# --------------------------------------------------------------------------------- OUTPUT
def output(e):
    """OUTPUT: tablas de resultados en el fichero de salida."""
    e.PATH = "OU"
    nt = e.NUMTYP
    if e.PERIOD or e.ANNUAL:
        for ityp in range(1, nt + 1):
            e.ITYP = ityp
            prtann(e)
    if (e.PM25AVE and e.NUMAVE == 1) or ((e.NO2AVE or e.SO2AVE) and e.NUMAVE >= 1):
        for ityp in range(1, nt + 1):
            e.ITYP = ityp
            prtpm25(e)
        maxpm25(e)
    elif e.NHIVAL > 0:
        for ityp in range(1, nt + 1):
            e.ITYP = ityp
            prtnhi(e)
    elif e.EVENTS:
        raise NoTraducido("EVENTFIL")
    if e.NMXVAL > 0:
        for ityp in range(1, nt + 1):
            e.ITYP = ityp
            prtmax(e)
    if e.PERIOD or e.ANNUAL or e.NHIVAL > 0:
        for ityp in range(1, nt + 1):
            e.ITYP = ityp
            prtsum(e, e.IOUNIT)
            if e.SUMMFILE:
                prtsum(e, e.ISUMUNT)
    if (e.PM25AVE or e.NO2AVE or e.SO2AVE) and e.NHIVAL > 0:
        for ityp in range(1, nt + 1):
            e.ITYP = ityp
            prtpm25sum(e, e.IOUNIT)
            if e.SUMMFILE:
                prtpm25sum(e, e.ISUMUNT)
    if e.SEASONHR:
        shout(e)
    if e.RKFILE:
        for ityp in range(1, nt + 1):
            e.ITYP = ityp
            rankfl(e)
    if e.EVENTS:
        raise NoTraducido("EVENTFIL")


def _workid(e, igrp):
    """Lista de fuentes del grupo para las cabeceras (WORKID, INDGRP)."""
    if not e.PSDCREDIT:
        w = [fx(e.SRCID[i], 12) for i in range(1, e.NUMSRC + 1) if e.IGROUP[i, igrp] == 1]
    else:
        w = [fx("N/A", 12)]
    if e.GRP_BACK[igrp]:
        w.append(fx("BACKGROUND", 12))
        indexw = min(29, e.NSRC + 1)
    else:
        indexw = min(29, e.NSRC)
    if len(w) > indexw:
        w = w[:indexw]
        w[indexw - 1] = fx(" . . . ", 12)
    return w


def _chidep6(e, it):
    return [fx(e.CHIDEP[ii, it], 4) for ii in range(1, 7)]


def _poner(buf, a, b, texto):
    """WRITE(BUF(a+1:b), ...): el registro interno ocupa b-a caracteres."""
    t = texto[:b - a].ljust(b - a)
    return buf[:a] + t + buf[b:]


_B132 = " " * 132


def _malla(e, u, cab, ncpp, fmt_x_cart, fmt_x_polr, fila):
    """Tablas de las redes GRIDCART/GRIDPOLR (común a PRTANN y SPRTHT)."""
    nrpp = 40
    e.NCPP = ncpp
    e.NRPP = nrpp
    for i in range(1, e.INNET + 1):
        nx_ = int(e.NUMXPT[i])
        ny_ = int(e.NUMYPT[i])
        e.NPPX = 1 + (nx_ - 1) // ncpp
        e.NPPY = 1 + (ny_ - 1) // nrpp
        tipo = e.NTTYP[i]
        for nx in range(1, e.NPPX + 1):
            for ny in range(1, e.NPPY + 1):
                e.header(u)
                out = cab()
                out += fwrite("(/35X,'*** NETWORK ID: ',A8,' ;  NETWORK TYPE: ',A8,' ***')",
                              fx(e.NTID[i], 8), fx(tipo, 8))
                out += e._lbl()
                jfin = nx_ if nx == e.NPPX else ncpp * nx
                xs = [e.XCOORD[j, i] for j in range(1 + ncpp * (nx - 1), jfin + 1)]
                if tipo == "GRIDCART":
                    out += fmt_x_cart[0]
                    out += fwrite(fmt_x_cart[1], *xs)
                elif tipo == "GRIDPOLR":
                    out += fmt_x_polr[0]
                    out += fwrite(fmt_x_polr[1], *xs)
                out += fwrite("(66(' -')/)")
                kfin = ny_ if ny == e.NPPY else nrpp * ny
                for k in range(1 + nrpp * (ny - 1), kfin + 1):
                    if tipo == "GRIDCART":
                        indz = int(e.NETEND[i]) - k * nx_ + 1
                        ycoval = e.YCOORD[ny_ - k + 1, i]
                    elif tipo == "GRIDPOLR":
                        indz = int(e.NETSTA[i]) + (k - 1) * nx_
                        ycoval = e.YCOORD[k, i]
                    out += fila(ycoval, [indz + j - 1 for j in range(1 + ncpp * (nx - 1), jfin + 1)])
                e.w(u, out)


def prtann(e):
    """PRTANN: tablas de los promedios del periodo por receptor."""
    it = e.ITYP
    u = e.IOUNIT
    cfmt = "E13.6" if e.FILE_FORMAT == "EXP" else "F13.5"
    fmt9013 = "(2X,F10.2,1X,'|',1X,9(" + cfmt + "))"
    fmt9045 = "(6X,2(F12.2,2X)," + cfmt + ")"
    fmt9047 = "(2X,A12,': ',F12.2,2X,F10.2,2X," + cfmt + ")"
    perchr = "PERIOD" if e.PERIOD else "ANNUAL"
    lbl = fwrite("(/40X,'** ',A4,' OF ',A8,' IN ',A40,' **'/)", fx(e.CHIDEP[3, it], 4),
                 fx(e.POLLUT, 8), fx(e.PERLBL[it], 40))
    e._lbl = lambda: list(lbl)
    for igrp in range(1, e.NUMGRP + 1):
        e.IGRP = igrp
        w = _workid(e, igrp)
        e.INDGRP = len(w)

        def cab():
            if e.PERIOD:
                return fwrite("(/30X,'*** THE ',A6,' (',I6,' HRS) ',6A4,'VALUES FOR SOURCE GROUP:',"
                              "1X,A8,' ***',/34X,'INCLUDING SOURCE(S):     ',5(A12,', ',:),"
                              "/17X,8(A12,', ',:)/17X,8(A12,', ',:)/17X,8(A12,', ',:))",
                              perchr, e.IANHRS, *_chidep6(e, it), fx(e.GRPID[igrp], 8), *w)
            return fwrite("(/19X,'*** THE ',A6,1X,6A4,' VALUES AVERAGED OVER ',I3,' YEARS FOR "
                          "SOURCE GROUP:',1X,A8,' ***',/34X,'INCLUDING SOURCE(S):     ',"
                          "5(A12,', ',:),/17X,8(A12,', ',:)/17X,8(A12,', ',:)/17X,8(A12,', ',:))",
                          perchr, *_chidep6(e, it), e.NUMYRS, fx(e.GRPID[igrp], 8), *w)

        def fila(ycoval, idx):
            return fwrite(fmt9013, ycoval, *[e.ANNVAL[r, igrp, it] for r in idx])

        _malla(e, u, cab, 9,
               (fwrite("(3X,' Y-COORD  |',48X,'X-COORD (METERS)')"), "(3X,' (METERS) |',1X,9(1X,F12.2,:))"),
               (fwrite("(3X,'DIRECTION |',48X,'DISTANCE (METERS)')"), "(3X,'(DEGREES) |',1X,9(1X,F12.2,:))"),
               fila)
        c3 = fx(e.CHIDEP[3, it], 4)
        if e.IRSTAT[4] != 0 or e.IRSTAT[8] != 0:
            _discretos(e, u, "DC", cab, lbl,
                       fwrite("(6X,' X-COORD (M)   Y-COORD (M)        ',A4,22X,' X-COORD (M)   "
                              "Y-COORD (M)        ',A4,/65(' -'))", c3, c3),
                       lambda irec: fwrite(fmt9045, e.AXR[irec], e.AYR[irec],
                                           e.ANNVAL[irec, igrp, it])[0],
                       (0, 60), (60, 120))
        if e.IRSTAT[5] != 0:
            def dp(irec):
                dist, dirr = _distdir(e, irec)
                return fwrite(fmt9047, fx(e.SRCID[e.IREF[irec]], 12), dist, dirr,
                              e.ANNVAL[irec, igrp, it])[0]
            _discretos(e, u, "DP", cab, lbl,
                       fwrite("(5X,'ORIGIN',59X,'ORIGIN',/5X,' SRCID         DIST (M)   DIR (DEG)  "
                              "      ',A4,18X,' SRCID         DIST (M)   DIR (DEG)        ',A4,"
                              "/65(' -'))", c3, c3),
                       dp, (0, 65), (65, 130))


def prtday(e):
    """PRTDAY (calc2.f): tablas de los valores concurrentes del periodo IAVE que acaba en la hora en
    curso (DAYTABLE), para el tipo de salida ITYP. Siempre con formato fijo (F13.5)."""
    it, ia = e.ITYP, e.IAVE
    u = e.IOUNIT
    lbl = fwrite("(/40X,'** ',A4,' OF ',A8,' IN ',A40,' **'/)", fx(e.CHIDEP[3, it], 4),
                 fx(e.POLLUT, 8), fx(e.OUTLBL[it], 40))
    e._lbl = lambda: list(lbl)
    for igrp in range(1, e.NUMGRP + 1):
        e.IGRP = igrp
        if not e.PSDCREDIT:
            e.ISRC = e.NUMSRC + 1
        w = _workid(e, igrp)
        e.INDGRP = len(w)

        def cab():
            return fwrite("(20X,'*** CONCURRENT ',A5,1X,6A4,'VALUES',' ENDING WITH HOUR ',I2,' FOR DAY ',I3,"
                          "' OF ',I4,' ***'/24X,'FOR SOURCE GROUP:',1X,A8,/24X,'INCLUDING SOURCE(S):     ',"
                          "5(A12,', ',:),/17X,8(A12,', ',:)/17X,8(A12,', ',:)/17X,8(A12,', ',:))",
                          fx(e.CHRAVE[ia], 5), *_chidep6(e, it), e.IHOUR, e.JDAY, e.IYR,
                          fx(e.GRPID[igrp], 8), *w)

        def fila(ycoval, idx):
            return fwrite("(2X,F10.2,1X,'|',1X,9(F13.5))", ycoval, *[e.AVEVAL[r, igrp, ia, it] for r in idx])

        _malla(e, u, cab, 9,
               (fwrite("(3X,' Y-COORD  |',48X,'X-COORD (METERS)')"), "(3X,' (METERS) |',1X,9(1X,F12.2,:))"),
               (fwrite("(3X,'DIRECTION |',48X,'DISTANCE (METERS)')"), "(3X,'(DEGREES) |',1X,9(1X,F12.2,:))"),
               fila)
        c3 = fx(e.CHIDEP[3, it], 4)
        if e.IRSTAT[4] != 0 or e.IRSTAT[8] != 0:
            _discretos(e, u, "DC", cab, lbl,
                       fwrite("(6X,' X-COORD (M)   Y-COORD (M)        ',A4,22X,' X-COORD (M)   "
                              "Y-COORD (M)        ',A4,/65(' -'))", c3, c3),
                       lambda irec: fwrite("(6X,2(F12.2,2X),F13.5)", e.AXR[irec], e.AYR[irec],
                                           e.AVEVAL[irec, igrp, ia, it])[0],
                       (0, 60), (60, 120))
            e.IREC = e.NUMREC + 1
        if e.IRSTAT[5] != 0:
            def dp(irec):
                dist, dirr = _distdir(e, irec)
                return fwrite("(2X,A12,': ',F12.2,2X,F10.2,2X,F13.5)", fx(e.SRCID[e.IREF[irec]], 12), dist,
                              dirr, e.AVEVAL[irec, igrp, ia, it])[0]
            _discretos(e, u, "DP", cab, lbl,
                       fwrite("(5X,'ORIGIN',59X,'ORIGIN',/5X,' SRCID         DIST (M)   DIR (DEG)  "
                              "      ',A4,18X,' SRCID         DIST (M)   DIR (DEG)        ',A4,"
                              "/65(' -'))", c3, c3),
                       dp, (0, 65), (65, 130))
            e.IREC = e.NUMREC + 1
    e.IGRP = e.NUMGRP + 1


def _distdir(e, irec):
    xrms = e.AXR[irec] - e.AXS[e.IREF[irec]]
    yrms = e.AYR[irec] - e.AYS[e.IREF[irec]]
    dist = math.sqrt(xrms * xrms + yrms * yrms)
    dirr = math.atan2(xrms, yrms) * e.RTODEG
    if dirr <= 0.0:
        dirr = dirr + 360.0
    return dist, dirr


def _discretos(e, u, tipo, cab, lbl, cab_col, linea, r1, r2):
    """Tablas de receptores discretos en dos columnas (DC o DP), 80 por página."""
    indc = 0
    buf = _B132
    out = []
    titulo = "(/45X,'*** DISCRETE CARTESIAN RECEPTOR POINTS ***')" if tipo == "DC" else \
        "(/47X,'*** DISCRETE POLAR RECEPTOR POINTS ***')"
    for irec in range(1, e.NUMREC + 1):
        if e.RECTYP[irec] != tipo:
            continue
        indc += 1
        if (indc - 1) % 80 == 0:
            if out:
                e.w(u, out)
                out = []
            e.header(u)
            out += cab()
            out += fwrite(titulo)
            out += lbl
            out += cab_col
        if indc % 2 != 0:
            buf = _poner(buf, r1[0], r1[1], linea(irec))
        else:
            buf = _poner(buf, r2[0], r2[1], linea(irec))
            out.append(buf)
            buf = _B132
    if indc % 2 != 0:
        out.append(buf)
    if out:
        e.w(u, out)


# --------------------------------------------------------------------------------- PRTNHI
def prtnhi(e):
    """PRTNHI: tablas de los valores N-ésimos más altos y máximos por grupo (HMAX)."""
    it = e.ITYP
    for iave in range(1, e.NUMAVE + 1):
        e.IAVE = iave
        iwhp = [ival for ival in range(1, e.NVAL + 1) if e.NHIAVE[ival, iave] == 1]
        if not iwhp:
            continue
        for ival in range(1, e.NVAL + 1):
            if e.NHIAVE[ival, iave] == 1:
                sprtht(e, ival)
        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            for irec in range(1, e.NUMREC + 1):
                for k, ih in enumerate(iwhp, 1):
                    v = e.HIVALU[irec, ih, igrp, iave, it]
                    if v > e.HMAX[k, igrp, iave, it]:
                        e.HMAX[k, igrp, iave, it] = v
                        e.HMDATE[k, igrp, iave, it] = e.NHIDAT[irec, ih, igrp, iave, it]
                        e.HMCLM[k, igrp, iave, it] = e.HCLMSG[irec, ih, igrp, iave, it]
                        e.HMLOC[k, igrp, iave, it] = irec
            e.IREC = e.NUMREC + 1
            if it == 1 and igrp > 999:
                for _k in iwhp:
                    if igrp <= 9999:
                        d = fwrite("(I2.2,'hr',1X,'IG=',I4)", iave, igrp)[0]
                    else:
                        d = fwrite("(I2.2,'hr',1X,'IG>9999')", iave)[0]
                    e.errhdl(e.PATH, "PRTNHI", "W", "235", d)
            # (fichero temporal de eventos: solo lo usa EVENTFIL, fuera de alcance)


def sprtht(e, ihnum):
    """SPRTHT: tablas del IHNUM-ésimo valor más alto por receptor."""
    it = e.ITYP
    iave = e.IAVE
    u = e.IOUNIT
    cfmt = "E13.6" if e.FILE_FORMAT == "EXP" else "F13.5"
    fmt9013 = "(1X,F9.1,1X,'|',5(" + cfmt + ",A1,'(',I8.8,')',:))"
    fmt9047 = "(1X,A12,': ',F11.2,1X,F10.2,1X," + cfmt + ",A1,1X,'(',I8.8,')')"
    chrval = _chrval(ihnum)
    if chrval is None:
        chrval = e._sprtht_chrval
    e._sprtht_chrval = chrval
    lbl = fwrite("(/40X,'** ',A4,' OF ',A8,' IN ',A40,' **'/)", fx(e.CHIDEP[3, it], 4),
                 fx(e.POLLUT, 8), fx(e.OUTLBL[it], 40))
    e._lbl = lambda: list(lbl)
    hv, hc, hd = e.HIVALU, e.HCLMSG, e.NHIDAT
    for igrp in range(1, e.NUMGRP + 1):
        e.IGRP = igrp
        w = _workid(e, igrp)
        e.INDGRP = len(w)

        def cab():
            return fwrite("(/30X,'*** THE ',A5,' HIGHEST ',A5,1X,6A4,'VALUES FOR SOURCE GROUP:',"
                          "2X,A8,' ***',/34X,'INCLUDING SOURCE(S):     ',5(A12,', ',:),"
                          "/17X,8(A12,', ',:)/17X,8(A12,', ',:)/17X,8(A12,', ',:))",
                          chrval, fx(e.CHRAVE[iave], 5), *_chidep6(e, it), fx(e.GRPID[igrp], 8),
                          *w)

        def fila(ycoval, idx):
            items = []
            for r in idx:
                items += [hv[r, ihnum, igrp, iave, it], fx(hc[r, ihnum, igrp, iave, it], 1),
                          hd[r, ihnum, igrp, iave, it]]
            return fwrite(fmt9013, ycoval, *items)

        _malla(e, u, cab, 5,
               (fwrite("(1X,' Y-COORD  |',50X,'X-COORD (METERS)')"),
                "(1X,' (METERS) |',3X,F13.2,4(11X,F13.2,:))"),
               (fwrite("(1X,'DIRECTION |',50X,'DISTANCE (METERS)')"),
                "(1X,'(DEGREES) |',3X,F13.2,4(11X,F13.2,:))"),
               fila)
        c3 = fx(e.CHIDEP[3, it], 4)
        if e.IRSTAT[4] != 0 or e.IRSTAT[8] != 0:
            f45 = "(6X,2(F11.2,2X),E13.6,A1,1X,'(',I8.8,')')" if e.FILE_FORMAT == "EXP" else \
                "(6X,2(F11.2,2X),F13.5,A1,1X,'(',I8.8,')')"
            _discretos(e, u, "DC", cab, lbl,
                       fwrite("(6X,'X-COORD (M)  Y-COORD (M)        ',A4,5X,'(YYMMDDHH)',14X,"
                              "'X-COORD (M)  Y-COORD (M)        ',A4,5X,'(YYMMDDHH)',/66(' -'))",
                              c3, c3),
                       lambda irec: fwrite(f45, e.AXR[irec], e.AYR[irec],
                                           hv[irec, ihnum, igrp, iave, it],
                                           fx(hc[irec, ihnum, igrp, iave, it], 1),
                                           hd[irec, ihnum, igrp, iave, it])[0],
                       (0, 65), (65, 130))
        if e.IRSTAT[5] != 0:
            def dp(irec):
                dist, dirr = _distdir(e, irec)
                return fwrite(fmt9047, fx(e.SRCID[e.IREF[irec]], 12), dirr,
                              hv[irec, ihnum, igrp, iave, it], dist,
                              fx(hc[irec, ihnum, igrp, iave, it], 1),
                              hd[irec, ihnum, igrp, iave, it])[0]
            _discretos(e, u, "DP", cab, lbl,
                       fwrite("(4X,'ORIGIN',60X,'ORIGIN',/5X,'SRCID        DIST (M)  DIR (DEG)       ',"
                              "A4,5X,'(YYMMDDHH)',8X,'SRCID        DIST (M)  DIR (DEG)       ',A4,"
                              "5X,'(YYMMDDHH)',/65(' -'))", c3, c3),
                       dp, (0, 66), (66, 132))


# --------------------------------------------------------------------------------- PRTMAX
def prtmax(e):
    """PRTMAX: tablas de los valores máximos globales (MAXTABLE)."""
    it = e.ITYP
    u = e.IOUNIT
    cfmt = "E13.6" if e.FILE_FORMAT == "EXP" else "F13.5"
    fmt2 = ("(1X,I4,'.',1X," + cfmt + ",A1,'(',I8.8,') AT',1X,'(',F10.2,', ',F10.2,')  ',A2,5X,"
            "I4,'.',1X," + cfmt + ",A1,'(',I8.8,') AT',1X,'(',F10.2,', ',F10.2,')  ',A2)")
    fmt3 = "(1X,I4,'.',1X," + cfmt + ",A1,'(',I8.8,') AT',1X,'(',F10.2,', ',F10.2,')  ',A2)"
    c3 = fx(e.CHIDEP[3, it], 4)
    fmt1 = ("(1X,'RANK',8X,A4,4X,'(YYMMDDHH) AT',6X,'RECEPTOR (XR,YR) OF TYPE ',3X,'RANK',8X,A4,"
            "4X,'(YYMMDDHH) AT',6X,'RECEPTOR (XR,YR) OF TYPE ',/66(' -'))")
    lbl = fwrite("(/40X,'** ',A4,' OF ',A8,' IN ',A40,' **'/)", c3, fx(e.POLLUT, 8),
                 fx(e.OUTLBL[it], 40))

    def rec(k, blanco):
        if k == 0:
            return 0.0, 0.0, blanco
        return e.AXR[k], e.AYR[k], fx(e.RECTYP[k], 2)

    for iave in range(1, e.NUMAVE + 1):
        e.IAVE = iave
        if e.MAXAVE[iave] != 1:
            continue
        imx = int(e.IMXVAL[iave])
        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            w = _workid(e, igrp)
            e.INDGRP = len(w)
            cab = fwrite("(/30X,'*** THE MAXIMUM ',I4,2X,A5,1X,6A4,'VALUES FOR SOURCE GROUP:',2X,"
                         "A8,' ***'/34X,'INCLUDING SOURCE(S):     ',5(A12,', ',:),"
                         "/17X,8(A12,', ',:)/17X,8(A12,', ',:)/17X,8(A12,', ',:))",
                         imx, fx(e.CHRAVE[iave], 5), *_chidep6(e, it), fx(e.GRPID[igrp], 8), *w)
            rv, mc, md, ml = e.RMXVAL, e.MCLMSG, e.MXDATE, e.MXLOCA
            if imx >= 2:
                npg = 1 + (imx - 1) // 80
                for l in range(1, npg + 1):
                    if l == npg:
                        nrows = (imx - 80 * (l - 1)) // 2
                    else:
                        nrows = 40
                    e.header(u)
                    out = list(cab) + list(lbl) + fwrite(fmt1, c3, c3)
                    jstrt = 1 + 80 * (l - 1)
                    for j in range(jstrt, jstrt + nrows):
                        j1 = j + nrows
                        if l == npg and imx % 2 != 0:
                            j1 = j1 + 1
                        xr1, yr1, nty1 = rec(int(ml[j, igrp, iave, it]), "  ")
                        xr2, yr2, nty2 = rec(int(ml[j1, igrp, iave, it]), "  ")
                        out += fwrite(fmt2, j, rv[j, igrp, iave, it], fx(mc[j, igrp, iave, it], 1),
                                      md[j, igrp, iave, it], xr1, yr1, nty1, j1,
                                      rv[j1, igrp, iave, it], fx(mc[j1, igrp, iave, it], 1),
                                      md[j1, igrp, iave, it], xr2, yr2, nty2)
                    e.w(u, out)
                if imx % 2 != 0:
                    j = imx // 2 + 1 + 40 * (npg - 1)
                    xr1, yr1, nty1 = rec(int(ml[j, igrp, iave, it]), "  ")
                    e.w(u, fwrite(fmt3, j, rv[j, igrp, iave, it], fx(mc[j, igrp, iave, it], 1),
                                  md[j, igrp, iave, it], xr1, yr1, nty1))
            else:
                j = 1
                xr1, yr1, nty1 = rec(int(ml[j, igrp, iave, it]), "  ")
                e.header(u)
                out = list(cab) + list(lbl) + fwrite(fmt1, c3, c3)
                out += fwrite(fmt3, j, rv[j, igrp, iave, it], fx(mc[j, igrp, iave, it], 1),
                              md[j, igrp, iave, it], xr1, yr1, nty1)
                e.w(u, out)
            e.w(u, fwrite("(/1X,' *** RECEPTOR TYPES:  GC = GRIDCART',/23X,'GP = GRIDPOLR',"
                          "/23X,'DC = DISCCART',/23X,'DP = DISCPOLR')"))


# --------------------------------------------------------------------------------- PRTSUM
def prtsum(e, iount):
    """PRTSUM: resumen de resultados máximos (fichero de salida y SUMMFILE)."""
    it = e.ITYP
    cfmt = "E14.6" if e.FILE_FORMAT == "EXP" else "F14.5"
    loc = "'(',2(F11.2,', '),2(F8.2,', '),F7.2,')'"
    fmt1002 = "(A8,' HIGH ',A5,' HIGH VALUE IS'," + cfmt + ",A1,' ON ',I8.8,': AT '," + loc + \
        ",2X,A2,2X,A8)"
    fmt1003 = "(8X,' HIGH ',A5,' HIGH VALUE IS'," + cfmt + ",A1,' ON ',I8.8,': AT '," + loc + \
        ",2X,A2,2X,A8)"
    fmt1004 = "(A8,' HIGH ',A5,' HIGH VALUE IS'," + cfmt + ",A1,' ON ',I8.8,': AT '," + loc + ")"
    fmt1005 = "(8X,' HIGH ',A5,' HIGH VALUE IS'," + cfmt + ",A1,' ON ',I8.8,': AT '," + loc + ")"
    fmt1012 = "(/A8,A5,' HIGHEST VALUE IS'," + cfmt + ",' AT '," + loc + ",2X,A2,2X,A8)"
    fmt1013 = "(8X,A5,' HIGHEST VALUE IS'," + cfmt + ",' AT '," + loc + ",2X,A2,2X,A8)"
    fmt1014 = "(/A8,A5,' HIGHEST VALUE IS'," + cfmt + ",' AT '," + loc + ")"
    fmt1015 = "(8X,A5,' HIGHEST VALUE IS'," + cfmt + ",' AT '," + loc + ")"
    perchr = "PERIOD" if e.PERIOD else "ANNUAL"
    tipos = fwrite("(//' *** RECEPTOR TYPES:  GC = GRIDCART',/22X,'GP = GRIDPOLR',"
                   "/22X,'DC = DISCCART',/22X,'DP = DISCPOLR')")
    if e.PERIOD or e.ANNUAL:
        e.NGPP = max(1, int(50 / (e.NHIANN + 1)))
        out = []
        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            if (igrp - 1) % e.NGPP == 0:
                if out:
                    e.w(iount, out)
                    out = []
                e.header(iount)
                if e.PERIOD and e.MULTYR:
                    out += fwrite("(/40X,'*** THE SUMMARY OF MAXIMUM ',A6,' (',I6,' HRS) RESULTS "
                                  "***',/40X,'***    ACROSS ',I6,' YEARS WITH THE MULTYEAR OPTION"
                                  "    ***'/)", perchr, e.IANHRS, e.NUMYRS)
                elif e.PERIOD:
                    out += fwrite("(/40X,'*** THE SUMMARY OF MAXIMUM ',A6,' (',I6,' HRS) RESULTS "
                                  "***'/)", perchr, e.IANHRS)
                elif e.ANNUAL:
                    out += fwrite("(/35X,'*** THE SUMMARY OF MAXIMUM ',A6,' RESULTS ','AVERAGED "
                                  "OVER ',I3,' YEARS ***'/)", perchr, e.NUMYRS)
                out += fwrite("(/36X,'** ',A4,' OF ',A8,' IN ',A40,' **'/)",
                              fx(e.CHIDEP[3, it], 4), fx(e.POLLUT, 8), fx(e.PERLBL[it], 40))
                out += fwrite("(109X,'NETWORK',/,'GROUP ID',23X,3A4,16X,'RECEPTOR  (XR, YR, ZELEV, "
                              "ZHILL, ZFLAG)',2X,'OF TYPE',2X,'GRID-ID',/60('- '))",
                              fx(e.CHIDEP[1, it], 4), fx(e.CHIDEP[2, it], 4),
                              fx(e.CHIDEP[3, it], 4))
            for ival in range(1, e.NHIANN + 1):
                indmx = int(e.IMXLOC[ival, igrp, it])
                av = e.AMXVAL[ival, igrp, it]
                if ival == 1 and indmx != 0:
                    out += fwrite(fmt1012, fx(e.GRPID[igrp], 8), _RANK[ival], av, e.AXR[indmx],
                                  e.AYR[indmx], e.AZELEV[indmx], e.AZHILL[indmx], e.AZFLAG[indmx],
                                  fx(e.RECTYP[indmx], 2), fx(e.NETID[indmx], 8))
                elif ival == 1 and indmx == 0:
                    out += fwrite(fmt1014, fx(e.GRPID[igrp], 8), _RANK[ival], av, 0.0, 0.0, 0.0,
                                  0.0, 0.0)
                elif indmx == 0:
                    out += fwrite(fmt1015, _RANK[ival], av, 0.0, 0.0, 0.0, 0.0, 0.0)
                else:
                    out += fwrite(fmt1013, _RANK[ival], av, e.AXR[indmx], e.AYR[indmx],
                                  e.AZELEV[indmx], e.AZHILL[indmx], e.AZFLAG[indmx],
                                  fx(e.RECTYP[indmx], 2), fx(e.NETID[indmx], 8))
        out += tipos
        e.w(iount, out)
    if e.PM25AVE or e.NO2AVE or e.SO2AVE:
        return
    zh2 = 0.0
    for iave in range(1, e.NUMAVE + 1):
        e.IAVE = iave
        iwhp = [ival for ival in range(1, e.NVAL + 1) if e.NHIAVE[ival, iave] == 1]
        if not iwhp:
            continue
        ihst = len(iwhp)
        e.NGPP = max(1, int(50 / (ihst + 1)))
        out = []
        chrval = None
        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            for i in range(1, ihst + 1):
                c = _chrval(iwhp[i - 1])
                if c is not None:
                    chrval = c
                indloc = int(e.HMLOC[i, igrp, iave, it])
                hm = e.HMAX[i, igrp, iave, it]
                hcl = fx(e.HMCLM[i, igrp, iave, it], 1)
                hdt = e.HMDATE[i, igrp, iave, it]
                if i == 1:
                    if (igrp - 1) % e.NGPP == 0:
                        if out:
                            e.w(iount, out)
                            out = []
                        e.header(iount)
                        if e.MULTYR:
                            out += fwrite("(/48X,'*** THE SUMMARY OF HIGHEST ',A5,' RESULTS ***'/,"
                                          "44X,'*** ACROSS ',I6,' YEARS WITH THE MULTYEAR OPTION "
                                          "***'/)", fx(e.CHRAVE[iave], 5), e.NUMYRS)
                        else:
                            out += fwrite("(/48X,'*** THE SUMMARY OF HIGHEST ',A5,' RESULTS ***'/)",
                                          fx(e.CHRAVE[iave], 5))
                        out += fwrite("(/36X,'** ',A4,' OF ',A8,' IN ',A40,' **'/)",
                                      fx(e.CHIDEP[3, it], 4), fx(e.POLLUT, 8),
                                      fx(e.OUTLBL[it], 40))
                        out += fwrite("(54X,'DATE',68X,'NETWORK',/,'GROUP ID',26X,3A4,5X,"
                                      "'(YYMMDDHH)',13X,'RECEPTOR  (XR, YR, ZELEV, ZHILL, ZFLAG)',"
                                      "4X,'OF TYPE',2X,'GRID-ID',/66('- '))",
                                      fx(e.CHIDEP[1, it], 4), fx(e.CHIDEP[2, it], 4),
                                      fx(e.CHIDEP[3, it], 4))
                    out.append(lw(" "))
                    if indloc == 0:
                        zh2 = 0.0
                        out += fwrite(fmt1004, fx(e.GRPID[igrp], 8), chrval, hm, hcl, hdt,
                                      0.0, 0.0, 0.0, zh2, 0.0)
                    else:
                        zh2 = e.AZHILL[indloc]
                        out += fwrite(fmt1002, fx(e.GRPID[igrp], 8), chrval, hm, hcl, hdt,
                                      e.AXR[indloc], e.AYR[indloc], e.AZELEV[indloc], zh2,
                                      e.AZFLAG[indloc], fx(e.RECTYP[indloc], 2),
                                      fx(e.NETID[indloc], 8))
                else:
                    if indloc == 0:
                        out += fwrite(fmt1005, chrval, hm, hcl, hdt, 0.0, 0.0, 0.0, zh2, 0.0)
                    else:
                        zh2 = e.AZHILL[indloc]
                        out += fwrite(fmt1003, chrval, hm, hcl, hdt, e.AXR[indloc], e.AYR[indloc],
                                      e.AZELEV[indloc], zh2, e.AZFLAG[indloc],
                                      fx(e.RECTYP[indloc], 2), fx(e.NETID[indloc], 8))
        out += tipos
        e.w(iount, out)


# --------------------------------------------------------------------------------- RANKFL
def rankfl(e):
    """RANKFL: ficheros de valores máximos ordenados sin periodos repetidos (RANKFILE)."""
    it = e.ITYP
    for iave in range(1, e.NUMAVE + 1):
        e.IAVE = iave
        if e.IRNKFL[iave] != 1:
            continue
        u = e.IRKUNT[iave]
        out = []
        if not e.L_NOHEADER[5]:
            out += _cab_comun(e, False)
            out += fwrite("('*',9X,'RANK-FILE OF UP TO ',I5,' TOP ',A5,' VALUES ','FOR ',I5,"
                          "' SOURCE GROUPS',/'*',9X,'INCLUDES OVERALL MAXIMUM VALUES WITH DUPLICATE ',"
                          "'DATA PERIODS REMOVED',/'*',9X,'FORMAT: ',A:)", e.IRKVAL[iave],
                          fx(e.CHRAVE[iave], 5), e.NUMGRP, fx(e.RNKFRM, 200))
            out += fwrite("('*  RANK',2X,3A4,3X,'DATE',10X,'X',13X,'Y',8X,'ZELEV',3X,'ZHILL',3X,"
                          "'ZFLAG',5X,'GRP',/'*_______',1X,'____________',1X,'________',"
                          "2(2X,'____________'),3(2X,'______'),'  ________')",
                          fx(e.CHIDEP[1, it], 4), fx(e.CHIDEP[2, it], 4), fx(e.CHIDEP[3, it], 4))
        fmt = e.RNKFRM.rstrip(" ")
        nmx = e.NMXVAL
        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            idatsv = [0] * (nmx + 1)
            irank = 0
            for i in range(1, int(e.IRKVAL[iave]) + 1):
                md = e.MXDATE[i, igrp, iave, it]
                found = any(md == idatsv[j] for j in range(1, nmx + 1))
                if not found and irank < e.IRKVAL[iave]:
                    irank += 1
                    irec = int(e.MXLOCA[i, igrp, iave, it])
                    e.IREC = irec
                    idatsv[irank] = md
                    out += fwrite(fmt, irank, e.RMXVAL[i, igrp, iave, it], md, e.AXR[irec],
                                  e.AYR[irec], e.AZELEV[irec], e.AZHILL[irec], e.AZFLAG[irec],
                                  fx(e.GRPID[igrp], 8))
        e.w(u, out)


# --------------------------------------------------------------------------- SHAVE / SHOUT
def shave(e):
    """SHAVE: promedios por estación y hora del día (SEASONHR)."""
    nr, ng = e.NUMREC, e.NUMGRP
    for iseas in range(1, 5):
        e.ISEAS = iseas
        for ihour in range(1, 25):
            e.IHOUR = ihour
            snum = float(e.NSEAHR[iseas, ihour] - e.NSEACM[iseas, ihour])
            e.SHVALS[1:nr + 1, 1:ng + 1, iseas, ihour, 1] = \
                e.SHVALS[1:nr + 1, 1:ng + 1, iseas, ihour, 1] / snum
    e.ISEAS = 5
    e.IHOUR = 25


def shout(e):
    """SHOUT: ficheros de valores por estación y hora del día (SEASONHR)."""
    n = e.NUMTYP
    hdrfrm = ("('*',8X,'X',13X,'Y',4X,%d(2X,3A4),3X,'ZELEV',3X,'ZHILL',3X,'ZFLAG',4X,'GRP',5X,"
              "'NHRS',2X,'SEAS',2X,'HOUR',3X,'NET ID',/,'*',%d(1X,'____________ '),"
              "3(' ______ '),' ________  ____  ____  ____  ________')" % (n, n + 2))
    hitems = []
    for t in range(1, n + 1):
        hitems += [fx(e.CHIDEP[1, t], 4), fx(e.CHIDEP[2, t], 4), fx(e.CHIDEP[3, t], 4)]
    if e.FILE_FORMAT == "FIX":
        seafrm = "(2(1X,F13.5),%d(1X,F13.8),3(1X,F7.2),2X,A8,2X,3(I4,2X),A8)" % n
    else:
        seafrm = "(2(1X,F13.5),%d(1X,E13.6),3(1X,F7.2),2X,A8,2X,3(I4,2X),A8)" % n
    for igrp in range(1, e.NUMGRP + 1):
        e.IGRP = igrp
        if e.ISEAHR[igrp] != 1:
            continue
        u = e.ISHUNT[igrp]
        out = []
        grp = fx(e.GRPID[igrp], 8)
        if not e.L_NOHEADER[4]:
            out += _cab_comun(e, False)
            out += fwrite("('*',9X,'FILE OF SEASON/HOUR VALUES FOR ','SOURCE GROUP: ',A8,"
                          "/'*',9X,'FOR A TOTAL OF ', I5,' RECEPTORS.',/'*',9X,'FORMAT: ',A:)",
                          grp, e.NUMREC, fx(seafrm, 80))
            out += fwrite(hdrfrm, *hitems)
        for iseas in range(1, 5):
            for ihour in range(1, 25):
                inum = int(e.NSEAHR[iseas, ihour] - e.NSEACM[iseas, ihour])
                for irec in range(1, e.NUMREC + 1):
                    out += fwrite(seafrm, e.AXR[irec], e.AYR[irec],
                                  *[e.SHVALS[irec, igrp, iseas, ihour, it] for it in range(1, n + 1)],
                                  e.AZELEV[irec], e.AZHILL[irec], e.AZFLAG[irec], grp, inum, iseas,
                                  ihour, fx(e.NETID[irec], 8))
        e.ISEAS = 5
        e.IHOUR = 25
        e.IREC = e.NUMREC + 1
        e.w(u, out)


# ------------------------------------------------------------------------ PM25AVE / NO2AVE
def prtpm25(e):
    """PRTPM25: tablas de los N-ésimos máximos diarios promediados en los años (SUMHNH)."""
    it = e.ITYP
    u = e.IOUNIT
    cfmt = "E13.6" if e.FILE_FORMAT == "EXP" else "F13.5"
    fmt9013 = "(2X,F10.2,1X,'|',1X,9(" + cfmt + "))"
    fmt9045 = "(6X,2(F12.2,2X)," + cfmt + ")"
    fmt9047 = "(2X,A12,': ',F12.2,2X,F10.2,2X," + cfmt + ")"
    lbl = fwrite("(/40X,'** ',A4,' OF ',A8,' IN ',A40,' **'/)", fx(e.CHIDEP[3, it], 4),
                 fx(e.POLLUT, 8), fx(e.PERLBL[it], 40))
    e._lbl = lambda: list(lbl)
    sh = e.SUMHNH
    chrval = getattr(e, "_prtpm25_chrval", "     ")
    for n in range(1, e.NVAL + 1):
        if e.NHIAVE[n, 1] != 1:
            continue
        c = _chrval(n)
        if c is not None:
            chrval = c
        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            w = _workid(e, igrp)
            e.INDGRP = len(w)

            def cab(igrp=igrp, w=w, chrval=chrval):
                if e.NO2AVE or e.SO2AVE:
                    return fwrite("(/4X,'*** THE ',A5,'-HIGHEST MAX DAILY 1-HR ',6A4,' VALUES ',"
                                  "'AVERAGED OVER ',I3,' YEARS FOR SOURCE GROUP:',1X,A8,' ***',"
                                  "/34X,'INCLUDING SOURCE(S):     ',5(A12,', ',:),"
                                  "/17X,8(A12,', ',:)/17X,8(A12,', ',:)/17X,8(A12,', ',:))",
                                  chrval, *_chidep6(e, it), e.NUMYRS, fx(e.GRPID[igrp], 8), *w)
                return fwrite("(/13X,'*** THE ',A5,'-HIGHEST ',A5,1X,6A4,' VALUES ',"
                              "'AVERAGED OVER ',I3,' YEARS FOR SOURCE GROUP:',1X,A8,' ***',"
                              "/34X,'INCLUDING SOURCE(S):     ',5(A12,', ',:),"
                              "/17X,8(A12,', ',:)/17X,8(A12,', ',:)/17X,8(A12,', ',:))",
                              chrval, fx(e.CHRAVE[1], 5), *_chidep6(e, it), e.NUMYRS,
                              fx(e.GRPID[igrp], 8), *w)

            def fila(ycoval, idx, n=n, igrp=igrp):
                return fwrite(fmt9013, ycoval, *[sh[r, igrp, n] for r in idx])

            _malla(e, u, cab, 9,
                   (fwrite("(3X,' Y-COORD  |',48X,'X-COORD (METERS)')"),
                    "(3X,' (METERS) |',1X,9(1X,F12.2,:))"),
                   (fwrite("(3X,'DIRECTION |',48X,'DISTANCE (METERS)')"),
                    "(3X,'(DEGREES) |',1X,9(1X,F12.2,:))"),
                   fila)
            c3 = fx(e.CHIDEP[3, it], 4)
            if e.IRSTAT[4] != 0 or e.IRSTAT[8] != 0:
                def dc(irec, n=n, igrp=igrp):
                    return fwrite(fmt9045, e.AXR[irec], e.AYR[irec], sh[irec, igrp, n])[0]
                _discretos(e, u, "DC", cab, lbl,
                           fwrite("(6X,' X-COORD (M)   Y-COORD (M)        ',A4,22X,' X-COORD (M) "
                                  "  Y-COORD (M)        ',A4,/65(' -'))", c3, c3),
                           dc, (0, 60), (60, 120))
            if e.IRSTAT[5] != 0:
                def dp(irec, n=n, igrp=igrp):
                    dist, dirr = _distdir(e, irec)
                    return fwrite(fmt9047, fx(e.SRCID[e.IREF[irec]], 12), dist, dirr,
                                  sh[irec, igrp, n])[0]
                _discretos(e, u, "DP", cab, lbl,
                           fwrite("(5X,'ORIGIN',59X,'ORIGIN',/5X,' SRCID         DIST (M)   DIR (DEG)"
                                  "        ',A4,18X,' SRCID         DIST (M)   DIR (DEG)        ',"
                                  "A4,/65(' -'))", c3, c3),
                           dp, (0, 65), (65, 130))
    e._prtpm25_chrval = chrval


def maxpm25(e):
    """MAXPM25: tabla global de los NMXPM valores máximos de SUMHNH."""
    nm = e.NMXPM
    mv, ml = e.MXPMVAL, e.MXPMLOC
    for igrp in range(1, e.NUMGRP + 1):
        e.IGRP = igrp
        for n in range(1, e.NVAL + 1):
            if e.NHIAVE[n, 1] != 1:
                continue
            for irec in range(1, e.NUMREC + 1):
                v = e.SUMHNH[irec, igrp, n]
                if nm > 1:
                    if v > mv[nm, igrp, n]:
                        for j in range(nm - 1, 0, -1):
                            if v <= mv[j, igrp, n]:
                                mv[j + 1, igrp, n] = v
                                ml[j + 1, igrp, n] = irec
                                break
                            mv[j + 1, igrp, n] = mv[j, igrp, n]
                            ml[j + 1, igrp, n] = ml[j, igrp, n]
                            if j == 1:
                                mv[1, igrp, n] = v
                                ml[1, igrp, n] = irec
                elif nm == 1:
                    if v > mv[1, igrp, n]:
                        mv[1, igrp, n] = v
                        ml[1, igrp, n] = irec
            e.IREC = e.NUMREC + 1


def prtpm25sum(e, iount):
    """PRTPM25SUM: resumen de los máximos de SUMHNH (fichero de salida y SUMMFILE)."""
    if e.NUMAVE != 1:
        return
    it = e.ITYP
    cfmt = "E14.6" if e.FILE_FORMAT == "EXP" else "F14.5"
    loc = "'(',2(F11.2,', '),2(F8.2,', '),F7.2,')'"
    fmt1012 = "(/A8,A5,' HIGHEST VALUE IS'," + cfmt + ",' AT '," + loc + ",2X,A2,2X,A8)"
    fmt1013 = "(8X,A5,' HIGHEST VALUE IS'," + cfmt + ",' AT '," + loc + ",2X,A2,2X,A8)"
    fmt1014 = "(/A8,A5,' HIGHEST VALUE IS'," + cfmt + ",' AT '," + loc + ")"
    fmt1015 = "(8X,A5,' HIGHEST VALUE IS'," + cfmt + ",' AT '," + loc + ")"
    nm = e.NMXPM
    e.NGPP = max(1, int(50 / (nm + 1)))
    out = []
    chrval = getattr(e, "_prtpm25sum_chrval", "     ")
    for n in range(1, e.NVAL + 1):
        if e.NHIAVE[n, 1] != 1:
            continue
        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            if (igrp - 1) % e.NGPP == 0:
                if out:
                    e.w(iount, out)
                    out = []
                e.header(iount)
                c = _chrval(n)
                if c is not None:
                    chrval = c
                if e.PM25AVE:
                    out += fwrite("(/27X,'*** THE SUMMARY OF MAXIMUM ',A5,'-HIGHEST ',A5,' RESULTS "
                                  "AVERAGED OVER ',I3,' YEARS ***'/)", chrval,
                                  fx(e.CHRAVE[1], 5), e.NUMYRS)
                elif e.NO2AVE or e.SO2AVE:
                    out += fwrite("(/22X,'*** THE SUMMARY OF MAXIMUM ',A5,'-HIGHEST ','MAX DAILY ',"
                                  "A5,' RESULTS AVERAGED OVER ',I3,' YEARS ***'/)", chrval,
                                  fx(e.CHRAVE[1], 5), e.NUMYRS)
                out += fwrite("(/36X,'** ',A4,' OF ',A8,' IN ',A40,' **'/)",
                              fx(e.CHIDEP[3, it], 4), fx(e.POLLUT, 8), fx(e.OUTLBL[it], 40))
                out += fwrite("(109X,'NETWORK',/'GROUP ID',23X,3A4,16X,'RECEPTOR  (XR, YR, ZELEV, "
                              "ZHILL, ZFLAG)',2X,'OF TYPE',2X,'GRID-ID',/60('- '))",
                              fx(e.CHIDEP[1, it], 4), fx(e.CHIDEP[2, it], 4),
                              fx(e.CHIDEP[3, it], 4))
            for ival in range(1, nm + 1):
                indmx = int(e.MXPMLOC[ival, igrp, n])
                v = e.MXPMVAL[ival, igrp, n]
                rk = _RANK[ival] if ival <= 10 else "     "
                if ival == 1 and indmx != 0:
                    out += fwrite(fmt1012, fx(e.GRPID[igrp], 8), rk, v, e.AXR[indmx], e.AYR[indmx],
                                  e.AZELEV[indmx], e.AZHILL[indmx], e.AZFLAG[indmx],
                                  fx(e.RECTYP[indmx], 2), fx(e.NETID[indmx], 8))
                elif ival == 1 and indmx == 0:
                    out += fwrite(fmt1014, fx(e.GRPID[igrp], 8), rk, v, 0.0, 0.0, 0.0, 0.0, 0.0)
                elif indmx == 0:
                    out += fwrite(fmt1015, rk, v, 0.0, 0.0, 0.0, 0.0, 0.0)
                else:
                    out += fwrite(fmt1013, rk, v, e.AXR[indmx], e.AYR[indmx], e.AZELEV[indmx],
                                  e.AZHILL[indmx], e.AZFLAG[indmx], fx(e.RECTYP[indmx], 2),
                                  fx(e.NETID[indmx], 8))
    out += fwrite("(//' *** RECEPTOR TYPES:  GC = GRIDCART',/22X,'GP = GRIDPOLR',"
                  "/22X,'DC = DISCCART',/22X,'DP = DISCPOLR')")
    e.w(iount, out)
    e._prtpm25sum_chrval = chrval
