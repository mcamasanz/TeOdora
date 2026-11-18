# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): bucle horario (aermod.f, HRLOOP)."""
from . import calculo_area, emisiones, fondo, meteo_horaria, quimica_no2, resultados
from .estado import NoTraducido
from .formato import fwrite, fx


def hrloop(e):
    """HRLOOP: lee la meteorología hora a hora, calcula y acumula los promedios."""
    m = "HRLOOP"
    e.EOF = False
    if e.L_MORNINGTRANS is not None:
        e.L_MORNINGTRANS[:] = False
    e.KURDAT = 0
    e.KURPFL = 0
    e.FULLDATE = 0
    if e.RUNTTRM2:
        raise NoTraducido("TTRM2")
    if e.SCIM:
        raise NoTraducido("SCIM")
    while e.FULLDATE <= e.IEDATE and not e.EOF:
        meteo_horaria.metext(e)
        if e.RUNERR:
            break
        proc = (not e.L_LEAPYEAR and e.IPROC[e.JDAY] == 1) or \
            (e.L_LEAPYEAR and e.IPROCL[e.JDAY] == 1)
        if e.ISDATE <= e.FULLDATE <= e.IEDATE and proc and not e.EOF:
            if not e.L_SKIPMESSAGES:
                e.NTOTHRS += 1
        elif e.FULLDATE < e.IEDATE and e.IEDATE < 2147123124 and e.EOF:
            e.errhdl(e.PATH, m, "E", "580", "MET-DATA")
            break
        elif e.EOF or e.FULLDATE > e.IEDATE:
            break
        if e.HOURLY:
            _emisiones_hora(e)
        if e.RUNERR:
            break
        ilsave = e.ILINE
        if e.L_BACKGRND:
            fondo.fondo_hora(e)
            if e.RUNERR:
                break
        e.ILINE = ilsave
        if e.PVMRM or e.OLM or e.ARM2 or e.RUNTTRM or e.GRSM:
            quimica_no2.fondo_hora(e)
            if e.RUNERR:
                break
            e.ILINE = ilsave
        if (e.IHOUR == 1 or e.ILINE == 1) and not e.NOCHKD:
            e.pantalla.w(fwrite("('+','Now Processing Data For Day No. ',I4,' of ',I4)",
                                e.JDAY, e.IYR))
        elif e.NOCHKD:
            e.pantalla.w(fwrite("('+','Now Processing Data For     ',I8.8)", e.KURDAT))
        proc = (not e.L_LEAPYEAR and e.IPROC[e.JDAY] == 1) or \
            (e.L_LEAPYEAR and e.IPROCL[e.JDAY] == 1)
        if ((not e.RSTINP and e.FULLDATE >= e.ISDATE) or
                (e.RSTINP and not e.MULTYR and e.FULLDATE > e.ISDATE) or
                (e.MULTYR and e.FULLDATE >= e.ISDATE)) and e.FULLDATE <= e.IEDATE and proc \
                and not e.EOF and not e.RUNERR:
            _hora(e)
        if e.FULLDATE > e.ISDATE and not e.EOF and not e.NOCHKD and not e.L_WARNCHKD and \
                (e.PM25AVE or e.NO2AVE or e.SO2AVE or e.ANNUAL or e.MULTYR):
            chk_endyr(e)
        elif e.FULLDATE == e.ISDATE and not e.EOF and not e.NOCHKD and not e.L_WARNCHKD and \
                (e.PM25AVE or e.NO2AVE or e.SO2AVE or e.ANNUAL or e.MULTYR):
            e.NREMAIN += 1
        e.CALCS = False
        e.ENDMON = False
        e.PREC2 = e.PREC1
        e.PREC1 = e.PRATE
    if e.TXFILE:
        resultados.toxx_fin(e)
    e.pantalla.w(fwrite("('+','Now Processing Output Options               ')"))


def _emisiones_hora(e):
    """Emisiones horarias (HOUREMIS) de cada fuente para la hora en curso. ILINE queda en la línea
    del fichero de emisiones leída en último lugar (el original no lo restaura)."""
    m = "HRLOOP"
    for isrc in range(1, e.NUMSRC + 1):
        e.ISRC = isrc
        if e.QFLAG[isrc] != "HOURLY":
            continue
        u = e.HOUREMISARRAY[isrc]
        for jj in range(1, e.NSRC + 1):
            if e.HOUREMISARRAY[jj] == u:
                e.IQLINE[jj] += 1
        if e.AFTSRC[isrc] == "Y":
            raise NoTraducido("fuentes de aeronaves")
        emisiones.hrqread(e, isrc)
        if e.EOF:
            e.errhdl(e.PATH, m, "E", "580", "HOUREMIS")
            e.RUNERR = True
        elif e.FULLDATE != e.FULLHRQ:
            e.errhdl(e.PATH, m, "E", "455", fwrite("(I10.10)", e.FULLDATE)[0])
            e.RUNERR = True
        if not e.RUNERR:
            emisiones.hrqext(e, isrc)
        if not e.RSTINP and e.L_MAXDCONT and e.FULLDATE >= e.ISDATE:
            # emisiones de la hora guardadas para MAXDCONT
            h, y, t = e.IHR_NDX, e.IYR_NDX, e.SRCTYP[isrc]
            e.AAQS[h, y, isrc] = e.AQS[isrc]
            if t[:5] == "POINT":
                e.AATS[h, y, isrc] = e.ATS[isrc]
                e.AAVS[h, y, isrc] = e.AVS[isrc]
            elif t == "VOLUME" and e.L_HRLYSIG[isrc]:
                e.AAHS[h, y, isrc] = e.AHS[isrc]
                e.AASYINI[h, y, isrc] = e.ASYINI[isrc]
                e.AASZINI[h, y, isrc] = e.ASZINI[isrc]
            elif (t[:4] == "AREA" or t == "LINE") and e.L_HRLYSIG[isrc]:
                e.AAHS[h, y, isrc] = e.AHS[isrc]
                e.AASZINI[h, y, isrc] = e.ASZINI[isrc]
            elif t == "BUOYLINE":
                e.AAFP[h, y, isrc] = e.AFP[isrc]
    e.ISRC = e.NUMSRC + 1


def _hora(e):
    """Cuerpo del bucle para una hora que entra en el cálculo."""
    m = "HRLOOP"
    na = e.NUMAVE
    an = e.PERIOD or e.ANNUAL
    if e.CLMHR and e.CLMPRO:
        for ia in range(1, na + 1):
            e.NUMHRS[ia] += 1
            e.NUMCLM[ia] += 1
        if an:
            e.IANHRS += 1
            e.IANCLM += 1
        if e.SEASONHR:
            e.NSEAHR[e.ISEAS, e.IHOUR] += 1
            e.NSEACM[e.ISEAS, e.IHOUR] += 1
    elif e.MSGHR and e.MSGPRO:
        for ia in range(1, na + 1):
            e.NUMHRS[ia] += 1
            e.NUMMSG[ia] += 1
        if an:
            e.IANHRS += 1
            e.IANMSG += 1
        if e.SEASONHR:
            e.NSEAHR[e.ISEAS, e.IHOUR] += 1
            e.NSEACM[e.ISEAS, e.IHOUR] += 1
    elif e.ZI <= 0.0:
        if not e.L_SKIPMESSAGES:
            e.errhdl(e.PATH, m, "I", "470", fwrite("(I8.8)", e.KURDAT)[0])
        for ia in range(1, na + 1):
            e.NUMHRS[ia] += 1
        if an:
            e.IANHRS += 1
        if e.SEASONHR:
            e.NSEAHR[e.ISEAS, e.IHOUR] += 1
    else:
        e.CALCS = True
        for ia in range(1, na + 1):
            e.NUMHRS[ia] += 1
        if an:
            e.IANHRS += 1
        if e.SEASONHR:
            e.NSEAHR[e.ISEAS, e.IHOUR] += 1
        if e.DEBUG:
            from . import depura
            depura.hrloop(e)
        calculo_area.calc(e)
    quimica = e.PVMRM or e.OLM or e.ARM2 or e.RUNTTRM or e.GRSM
    if quimica and not e.CLMHR and not e.MSGHR:
        quimica_no2.conversion(e)
    nr, ng, nt = e.NUMREC, e.NUMGRP, e.NUMTYP
    for ia in range(1, na + 1):
        e.IAVE = ia
        if e.IHOUR % e.KAVE[ia] == 0 or (e.KAVE[ia] == 720 and e.ENDMON):
            if e.CONC:
                resultados.aver(e)
            resultados.hivals(e)
            if (e.NO2AVE or e.SO2AVE) and e.KAVE[ia] == 1:
                _mxdval(e, ia)
            if e.PM25AVE and e.IHOUR % 24 == 0 and e.KAVE[ia] == 24:
                _mxdval(e, ia)
            if e.DAYTAB and e.IDYTAB[ia] == 1:
                from . import salida
                for ityp in range(1, nt + 1):
                    e.ITYP = ityp
                    salida.prtday(e)
                e.ITYP = nt + 1
            if e.MXFILE:
                resultados.maxfil(e)
            if e.PPFILE:
                resultados.postfl(e)
            if e.TXFILE:
                resultados.toxxfl(e)
            e.AVEVAL[1:nr + 1, 1:ng + 1, ia, 1:nt + 1] = 0.0
    e.IAVE = na + 1
    if e.PM25AVE or e.NO2AVE or e.SO2AVE:
        if e.IHOUR % 24 == 0:
            mxdlyfl(e)
    if e.RSTSAV and e.IHOUR == 24:
        e.NDAYS += 1
        if e.NDAYS == e.INCRST:
            from . import reinicio
            reinicio.rsdump(e)
            e.NDAYS = 0
    e.HRVAL[:] = 0.0
    e.AERVAL[:] = 0.0
    e.PRMVAL[:] = 0.0
    if e.BACKAVE is not None:
        e.BACKAVE[:] = 0.0
    if e.BACKHR is not None:
        e.BACKHR[...] = 0.0
    if quimica:
        quimica_no2.vaciar(e)


def _mxdval(e, ia):
    for igrp in range(1, e.NUMGRP + 1):
        for irec in range(1, e.NUMREC + 1):
            if e.AVEVAL[irec, igrp, ia, 1] > e.MXDVAL[irec, igrp]:
                e.MXDVAL[irec, igrp] = e.AVEVAL[irec, igrp, ia, 1]
                e.IMXDHR[irec, igrp] = e.IHOUR
    e.IGRP = e.NUMGRP + 1
    e.IREC = e.NUMREC + 1


def chk_endyr(e):
    """CHK_ENDYR: fin de año para ANNUAL / PM25 / NO2 / SO2 / MULTYEAR."""
    from . import salida
    iyr = e.IYR
    # (A .AND. B) .OR. C, con la precedencia del original
    if ((e.IENDMN == 2 and e.IENDDY == 29 and e.IMONTH == 2) and (iyr % 4 != 0)) or \
            (iyr % 100 == 0 and iyr % 400 != 0):
        iend_day = 28
    else:
        iend_day = e.IENDDY
    if e.IMONTH == e.IENDMN and e.IDAY == iend_day and e.IHOUR == e.IENDHOUR:
        e.NUMYRS += 1
        e.IHR_NDX = 0
        if e.ANNUAL:
            salida.perave(e)
            if e.ANPOST:
                salida.pstann(e)
            e.SUMANN[...] = e.SUMANN + e.ANNVAL
            e.IANHRS = 0
            e.IANCLM = 0
            e.IANMSG = 0
            e.NSKIPTOT = 0
            if e.ANNVAL is not None:
                e.ANNVAL[...] = 0.0
            if e.AMXVAL is not None:
                e.AMXVAL[...] = 0.0
            if e.IMXLOC is not None:
                e.IMXLOC[...] = 0
        if (e.PM25AVE or e.NO2AVE or e.SO2AVE) and e.NUMAVE >= 1:
            nr, ng = e.NUMREC, e.NUMGRP
            for n in range(1, e.NVAL + 1):
                e.SUMHNH[1:nr + 1, 1:ng + 1, n] = e.SUMHNH[1:nr + 1, 1:ng + 1, n] + \
                    e.HIMXDLY[1:nr + 1, 1:ng + 1, n]
                if e.NUMYRS <= e.NYEARS:
                    e.HIMXDLY_BYYR[1:nr + 1, 1:ng + 1, n, e.NUMYRS] = \
                        e.HIMXDLY[1:nr + 1, 1:ng + 1, n]
                    e.NHIDATMXD_BYYR[1:nr + 1, 1:ng + 1, n, e.NUMYRS] = \
                        e.NHIDATMXD[1:nr + 1, 1:ng + 1, n]
                else:
                    e.errhdl(e.PATH, "CHK_ENDYR", "E", "482",
                             fwrite("('NYR=',I4)", e.NYEARS)[0])
                    e.RUNERR = True
                if e.MXDAILY_BYYR and e.NHIAVE[n, 1] == 1:
                    mxdybyyr(e, n)
            if e.HIMXDLY is not None:
                e.HIMXDLY[...] = 0.0
            if e.NHIDATMXD is not None:
                e.NHIDATMXD[...] = 0
        e.NREMAIN = 0
    else:
        e.NREMAIN += 1


def mxdlyfl(e):
    """MXDLYFL: máximos diarios (PM25AVE/NO2AVE/SO2AVE): fichero MAXDAILY y tabla HIMXDLY."""
    nh = e.NHIMXDLY
    hm, nd = e.HIMXDLY, e.NHIDATMXD
    base = (e.KURDAT // 100) * 100
    for igrp in range(1, e.NUMGRP + 1):
        e.IGRP = igrp
        lineas = [] if e.IMXDLY[igrp] == 1 else None
        for irec in range(1, e.NUMREC + 1):
            e.IREC = irec
            e.ITYP = 1
            v = e.MXDVAL[irec, igrp]
            fecha = base + int(e.IMXDHR[irec, igrp])
            if lineas is not None:
                lineas += fwrite(e.MXDFRM, e.AXR[irec], e.AYR[irec], v, e.AZELEV[irec], e.AZHILL[irec],
                                 e.AZFLAG[irec], "  1-HR", fx(e.GRPID[igrp], 8), e.JDAY,
                                 int(e.IMXDHR[irec, igrp]), fecha, fx(e.NETID[irec], 8))
            if nh > 1:
                if v > hm[irec, igrp, nh]:
                    for j in range(nh - 1, 0, -1):
                        if v <= hm[irec, igrp, j]:
                            hm[irec, igrp, j + 1] = v
                            nd[irec, igrp, j + 1] = fecha
                            break
                        hm[irec, igrp, j + 1] = hm[irec, igrp, j]
                        nd[irec, igrp, j + 1] = nd[irec, igrp, j]
                        if j == 1:
                            hm[irec, igrp, 1] = v
                            nd[irec, igrp, 1] = fecha
            elif nh == 1:
                if v > hm[irec, igrp, 1]:
                    hm[irec, igrp, 1] = v
                    nd[irec, igrp, 1] = fecha
        if lineas:
            e.w(e.IMDUNT[igrp], lineas)
        if e.RSTSAV and e.IMXDLY[igrp] == 1:
            e.volcar(e.IMDUNT[igrp])
    e.MXDVAL[...] = 0.0
    e.IMXDHR[...] = 0


_RANGO = ["", "  1ST", "  2ND", "  3RD", "  4TH", "  5TH", "  6TH", "  7TH", "  8TH", "  9TH", " 10TH"]


def mxdybyyr(e, n):
    """MXDYBYYR (calc2.f): N-ésimo máximo diario del año de cada receptor al fichero MXDYBYYR."""
    if n <= 10:
        chrval = _RANGO[n]
    elif 10 < n % 100 < 20:
        chrval = fwrite('(I2,I1,"TH")', n // 10, n % 10)[0]
    elif n <= 999:
        imod = n % 10
        if imod == 0:
            imod = 10
        chrval = fwrite("(I2,A3)", n // 10, _RANGO[imod][2:5])[0]
    for igrp in range(1, e.NUMGRP + 1):
        e.IGRP = igrp
        if e.IMXDLY_BYYR[igrp] != 1:
            continue
        lineas = []
        for irec in range(1, e.NUMREC + 1):
            e.IREC = irec
            e.ITYP = 1
            icdat8 = int(e.NHIDATMXD[irec, igrp, n])
            icyr = icdat8 // 1000000
            icdat = 0
            if icyr <= 99:
                icdat = e.ISTRT_CENT * 100000000 + icdat8
                icyr = e.ISTRT_CENT * 100 + icyr
            icmn = icdat // 10000 - (icdat // 1000000) * 100
            icdy = icdat // 100 - (icdat // 10000) * 100
            icjdy = e.julian(icyr, icmn, icdy) if (icmn > 0 and icdy > 0) else 0
            lineas += fwrite(e.MXDFRM, e.AXR[irec], e.AYR[irec], e.HIMXDLY[irec, igrp, n], e.AZELEV[irec],
                             e.AZHILL[irec], e.AZFLAG[irec], chrval, fx(e.GRPID[igrp], 8), icjdy,
                             icdat8 - (icdat8 // 100) * 100, icdat8, fx(e.NETID[irec], 8))
        e.w(e.IMDUNT_BYYR[igrp], lineas)
    e.IGRP = e.NUMGRP + 1
    e.IREC = e.NUMREC + 1
