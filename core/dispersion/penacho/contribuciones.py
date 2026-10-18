# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): contribución de los grupos a los máximos
diarios (MAXDCONT): MAXDCONT_LOOP y MAXD_METEXT de aermod.f, MAXDCALC y MAXDCNT_FILE de output.f.

Tras el bucle horario, para cada grupo con MAXDCONT y cada rango pedido, se recalculan receptor a
receptor las horas (NO2/SO2: la hora del máximo diario; PM2.5: las 24 h del día) que dieron el valor
de diseño de cada año, con la meteorología, el fondo y las emisiones horarias guardadas, y se
promedian sobre los años las concentraciones de todos los grupos."""
from . import calculo_area, meteo_horaria, quimica_no2, resultados
from .estado import NoTraducido
from .formato import fwrite, fx, nint

_NCHR2 = ("  1ST", "  2ND", "  3RD", "  4TH", "  5TH", "  6TH", "  7TH", "  8TH", "  9TH", " 10TH")


def maxd_metext(e):
    """MAXD_METEXT: recupera la meteorología guardada de la hora (IHR_NDX, IYR_NDX)."""
    e.PATH = "MX"
    e.IPDATE = e.KURDAT
    e.IPYEAR = e.IYR
    e.IPHOUR = e.IHOUR
    h, y = e.IHR_NDX, e.IYR_NDX
    for a, v in meteo_horaria.MAXD_ESCALARES:
        setattr(e, v, float(getattr(e, a)[h, y]))
    e.KST = nint(float(e.AKST[h, y]))
    e.BLTA = float(e.ABLTA[h, y])
    if e.HBPLUME:
        e.ZICONVN = float(e.AZICONVN[h, y])
        e.ZIMECHN = float(e.AZIMECHN[h, y])
    if e.LDGAS or e.LDPART or e.LWPART or e.LWGAS or e.GRSM:
        e.BOWEN = float(e.ABOWEN[h, y])
        e.ALBEDO = float(e.AALBEDO[h, y])
        e.IPCODE = int(e.IAPCODE[h, y])
        e.PRATE = float(e.APRATE[h, y])
        e.RH = float(e.ARH[h, y])
        e.SFCP = float(e.ASFCP[h, y])
        e.NCLOUD = int(e.NACLOUD[h, y])
        e.QSW = float(e.AQSW[h, y])
        e.WNEW = float(e.AWNEW[h, y])
        e.F2 = float(e.AF2[h, y])
        e.ESTA = float(e.AESTA[h, y])
        e.PREC1 = float(e.APREC1[h, y])
        e.PREC2 = float(e.APREC2[h, y])
    for a, v in meteo_horaria.MAXD_ESCALARES2:
        x = getattr(e, a)[h, y]
        if v in ("CLMHR", "MSGHR", "UNSTAB", "STABLE", "URBSTAB"):
            setattr(e, v, bool(x))
        elif v == "NDX4ZI":
            setattr(e, v, int(x))
        else:
            setattr(e, v, float(x))
    mx = e.MXGLVL
    for a, v in meteo_horaria.MAXD_PERFILES:
        getattr(e, v)[1:mx + 1] = getattr(e, a)[h, 1:mx + 1, y]
    if e.NSEC > 0:
        e.GRIDRHO[1:mx + 1] = e.AGRIDRHO[h, 1:mx + 1, y]
    if e.PVMRM or e.GRSM:
        e.GRIDEPS[1:mx + 1] = e.AGRIDEPS[h, 1:mx + 1, y]
    if e.NURB > 0:
        e.GRDSWR[1:mx + 1] = e.AGRDSWR[h, 1:mx + 1, y]
        e.GRDSVR[1:mx + 1] = e.AGRDSVR[h, 1:mx + 1, y]
        e.GRDTGR[1:mx + 1] = e.AGRDTGR[h, 1:mx + 1, y]
        e.GRDPTR[1:mx + 1] = e.AGRDPTR[h, 1:mx + 1, y]
        for i in range(1, e.NURB + 1):
            e.GRDSWU[1:mx + 1, i] = e.AGRDSWU[h, 1:mx + 1, y, i]
            e.GRDSVU[1:mx + 1, i] = e.AGRDSVU[h, 1:mx + 1, y, i]
            e.GRDTGU[1:mx + 1, i] = e.AGRDTGU[h, 1:mx + 1, y, i]
            e.GRDPTU[1:mx + 1, i] = e.AGRDPTU[h, 1:mx + 1, y, i]
            e.ZIURB[i] = e.AZIURB[h, y, i]
            e.URBWSTR[i] = e.AURBWSTR[h, y, i]
            e.URBUSTR[i] = e.AURBUSTR[h, y, i]
            e.URBOBULEN[i] = e.AURBOBULEN[h, y, i]
            e.L_MORNINGTRANS[i] = e.AL_MORNINGTRANS[h, y, i]
    if not e.CLMHR and not e.MSGHR:
        meteo_horaria.set_metdata(e)


def maxdcalc(e):
    """MAXDCALC: cálculo de una hora de MAXDCONT (para el receptor guardado en la posición 1)."""
    e.EOF = False
    e.RSTSAV = False
    e.IAVE = 1
    maxd_metext(e)
    h, y = e.IHR_NDX, e.IYR_NDX
    if e.HOURLY:
        for isrc in range(1, e.NUMSRC + 1):
            e.ISRC = isrc
            if e.QFLAG[isrc] != "HOURLY":
                continue
            t = e.SRCTYP[isrc]
            if e.AFTSRC[isrc] == "Y":
                raise NoTraducido("fuentes de aeronaves")
            e.AQS[isrc] = e.AAQS[h, y, isrc]
            if t[:5] == "POINT":
                e.ATS[isrc] = e.AATS[h, y, isrc]
                e.AVS[isrc] = e.AAVS[h, y, isrc]
            elif t == "VOLUME" and e.L_HRLYSIG[isrc] and e.AFTSRC[isrc] == "N":
                e.AHS[isrc] = e.AAHS[h, y, isrc]
                e.ASYINI[isrc] = e.AASYINI[h, y, isrc]
                e.ASZINI[isrc] = e.AASZINI[h, y, isrc]
            elif t[:4] == "AREA" and e.L_HRLYSIG[isrc] and e.AFTSRC[isrc] == "N":
                e.AHS[isrc] = e.AAHS[h, y, isrc]
                e.ASZINI[isrc] = e.AASZINI[h, y, isrc]
            elif t == "LINE" and e.L_HRLYSIG[isrc]:
                e.AHS[isrc] = e.AAHS[h, y, isrc]
                e.ASZINI[isrc] = e.AASZINI[h, y, isrc]
            elif t == "BUOYLINE":
                e.AFP[isrc] = e.AAFP[h, y, isrc]
        e.ISRC = e.NUMSRC + 1
    e.BGCONC = float(e.ABGCONC[h, y]) if e.L_BACKGRND else 0.0
    if e.PVMRM or e.OLM or e.RUNTTRM or e.GRSM:
        e.O3CONC = float(e.AO3CONC[h, y])
        e.O3MISS = e.O3CONC < 0.0
    if e.GRSM:
        e.NOXBGCONC = float(e.ANOXBGCONC[h, y])
        e.NOXMISS = e.NOXBGCONC < 0.0
    if e.RUNTTRM2:
        raise NoTraducido("TTRM2")
    quimica = e.PVMRM or e.OLM or e.ARM2 or e.RUNTTRM or e.GRSM
    if e.ISDATE <= e.FULLDATE <= e.IEDATE:
        if e.CLMHR and e.CLMPRO:
            e.NUMHRS[1] += 1
            e.NUMCLM[1] += 1
        elif e.MSGHR and e.MSGPRO:
            e.NUMHRS[1] += 1
            e.NUMMSG[1] += 1
        elif e.ZI <= 0.0:
            e.NUMHRS[1] += 1
        else:
            e.CALCS = True
            e.NUMHRS[1] += 1
            calculo_area.calc(e)
        if quimica and not e.CLMHR and not e.MSGHR:
            quimica_no2.conversion(e)
        e.IAVE = 1
        if e.KAVE[1] != 1 and e.IHOUR % e.KAVE[1] == 0:
            resultados.aver(e)
            e.NUMHRS[:] = 0
            e.NUMCLM[:] = 0
            e.NUMMSG[:] = 0
        e.HRVAL[:] = 0.0
        e.AERVAL[:] = 0.0
        e.PRMVAL[:] = 0.0
        if quimica:
            quimica_no2.vaciar(e)
    e.CALCS = False
    e.ENDMON = False
    e.PREC2 = e.PREC1
    e.PREC1 = e.PRATE


def _vaciar_chi(e):
    """CHI (y las matrices de GRSM) a cero entre recálculos de MAXDCONT."""
    e.CHI[...] = 0.0
    if e.GRSM:
        e.CHI_TTRAVPLM = 0.0
        e.CHI_TTRAVPAN = 0.0
        e.CHI_TTRAVAER = 0.0
        e.CHI_TTRAVPRM = 0.0
        e.CHI_TTRAVCHM[...] = 0.0
        e.BLDFAC[...] = 0.0
        e.PRMVAL_SRC1 = 0.0


def _nombre_rango(ival):
    if ival <= 10:
        return _NCHR2[ival - 1]
    if 10 < ival % 100 < 20:
        return fwrite('(I2,I1,"TH")', ival // 10, ival % 10)[0]
    if ival <= 999:
        imod = ival % 10
        if imod == 0:
            imod = 10
        return fwrite("(I2,A3)", ival // 10, _NCHR2[imod - 1][2:5])[0]
    return ""


def maxdcnt_file(e, ig, ival):
    """MAXDCNT_FILE: escribe las contribuciones del rango IVAL del grupo IG."""
    ng = e.NUMGRP
    u = int(e.IMXDCUNT[ig])
    hdrfrm = fwrite("('(''*'',8X,''X'',13X,''Y'',4X,(2X,3A4),4X,''ZELEV'',4X,''ZHILL'',4X,''ZFLAG'',4X,"
                    "''AVE'',5X,''GRP'',7X,''RANK'',5X,''NET ID'',1X,',I4,'(2X,''CONT '',A8),/,''*'',"
                    "3(1X,''____________ ''),1X,3('' ______  ''),''______  ________  ________  ________'',',"
                    "I4,'(''  _____________''))')", ng, ng)[0]
    if e.FILE_FORMAT == "FIX":
        mxdfmt = fwrite("('(3(1X,F13.5),3(1X,F8.2),2X,A6,2X,A8,2X,A5,5X,A8,2X,',I4,'(F13.5,2X:))')",
                        min(ng, 9999))[0]
    else:
        mxdfmt = fwrite("('(2(1X,F13.5),1X,E13.6,3(1X,F8.2),2X,A6,2X,A8,2X,A5,5X,A8,','2X,',I4,"
                        "'(E13.6,2X:))')", min(ng, 9999))[0]
    chrval = _nombre_rango(ival)
    out = []
    if not e.L_NOHEADER[8]:
        out += fwrite("('* AERMOD (',A6,'): ',A68,5X,A8)", fx(e.VERSN, 6), fx(e.TITLE1, 68), fx(e.RUNDAT, 8))
        out += fwrite("('* AERMET (',A6,'):',T93,A8,/'* MODELING OPTIONS USED: ',A:)",
                      fx(e.C_METVER, 6), fx(e.RUNTIM, 8), e.MODOPS_STRING.rstrip(" "))
        cola = ("/'*',9X,'FOR A TOTAL OF ',I6,' RECEPTORS AND ',I4,' SOURCE GROUPS;  WITH ',"
                "'CONTRIBUTIONS FROM OTHER SOURCE GROUPS PAIRED IN TIME & ','SPACE',/'*',9X,'FORMAT: ',A:)")
        que = "'-HIGHEST ',A5," if e.PM25AVE else "'-HIGHEST MAX DAILY ',A5,"
        if e.PM25AVE or e.NO2AVE or e.SO2AVE:
            if e.MAXD_THRESH[ig] > 0.0:
                out += fwrite("('*',9X,'MAXDCONT FILE OF ',A5," + que + "' VALUES AVERAGED OVER ',I3,"
                              "' YEARS FOR SOURCE GROUP: ',A8,' ; ABOVE THRESH = ',F13.5," + cola,
                              chrval, fx(e.CHRAVE[1], 5), e.NUMYRS, fx(e.GRPID[ig], 8), e.MAXD_THRESH[ig],
                              e.NREC, ng, fx(mxdfmt, 100))
            else:
                out += fwrite("('*',9X,'MAXDCONT FILE OF ',A5," + que + "' VALUES AVERAGED OVER ',I3,"
                              "' YEARS FOR SOURCE GROUP: ',A8," + cola,
                              chrval, fx(e.CHRAVE[1], 5), e.NUMYRS, fx(e.GRPID[ig], 8), e.NREC, ng, fx(mxdfmt, 100))
        out += fwrite(hdrfrm, fx(e.CHIDEP[1, 1], 4), fx(e.CHIDEP[2, 1], 4), fx(e.CHIDEP[3, 1], 4),
                      *[fx(e.GRPID[i], 8) for i in range(1, ng + 1)])
    sv = e.SUMVAL_MAXD
    for irec in range(1, e.NREC + 1):
        out += fwrite(mxdfmt, e.AXR_SAV[irec], e.AYR_SAV[irec], e.SUMHNH[irec, ig, ival], e.AZELEV_SAV[irec],
                      e.AZHILL_SAV[irec], e.AZFLAG_SAV[irec], fx(e.CHRAVE[1], 5), fx(e.GRPID[ig], 8), chrval,
                      fx(e.NETID[irec], 8), *[sv[ival, i, ig, irec] for i in range(1, min(ng, 9999) + 1)])
    e.IREC = e.NREC + 1
    e.w(u, out)


def maxdcont_loop(e):
    """MAXDCONT_LOOP: recálculo receptor a receptor de las horas de los valores de diseño."""
    m = "MAXDCONT_LOOP"
    e.PATH = "CN"
    nr = e.NREC
    a = e.alloc
    for n in ("AXR_SAV", "AYR_SAV", "AZELEV_SAV", "AZFLAG_SAV", "AZHILL_SAV"):
        a(n, nr)
    a("SUMVAL_MAXD", e.NVAL, e.NGRP, e.NGRP, nr)
    from . import fuente_linea_flotante
    fuente_linea_flotante.reservar_maxd(e)
    hit = False
    e.NUMHRS[:] = 0
    e.NUMCLM[:] = 0
    e.NUMMSG[:] = 0
    e.HRVAL[:] = 0.0
    e.AERVAL[:] = 0.0
    e.AVEVAL[...] = 0.0
    e.NUMREC = 1
    if e.BACKAVE is not None:
        e.BACKAVE[:] = 0.0
    if e.CHI is not None:
        # el original redimensiona CHI a NUMREC = 1 y lo pone a cero
        _vaciar_chi(e)
    e.AXR_SAV[:] = e.AXR[:nr + 1]
    e.AYR_SAV[:] = e.AYR[:nr + 1]
    e.AZELEV_SAV[:] = e.AZELEV[:nr + 1]
    e.AZHILL_SAV[:] = e.AZHILL[:nr + 1]
    e.AZFLAG_SAV[:] = e.AZFLAG[:nr + 1]
    fuente_linea_flotante.maxd_guardar_bl(e)
    isdate_sav, iedate_sav = e.ISDATE, e.IEDATE
    e.SUMVAL_MAXD[...] = 0.0
    e.L_SKIPMESSAGES = True
    sv = e.SUMVAL_MAXD
    for jgrp in range(1, e.NUMGRP + 1):
        if e.MAXDCONT[jgrp] <= 0:
            continue
        r1, r2 = int(e.MXD_RANK[jgrp, 1]), int(e.MXD_RANK[jgrp, 2])
        for ival in range(r1, r2 + 1):
            e.pantalla.w(fwrite("('+','Now Processing MAXDCONT for Group ',A8,' and Rank No. ',I4)",
                                fx(e.GRPID[jgrp], 8), ival))
            for ir in range(1, nr + 1):
                s = e.SUMHNH[ir, jgrp, ival]
                if s <= 0.0 or s < e.MAXD_THRESH[jgrp]:
                    continue
                e.AXR[1] = e.AXR_SAV[ir]
                e.AYR[1] = e.AYR_SAV[ir]
                e.AZELEV[1] = e.AZELEV_SAV[ir]
                e.AZHILL[1] = e.AZHILL_SAV[ir]
                e.AZFLAG[1] = e.AZFLAG_SAV[ir]
                fuente_linea_flotante.maxd_receptor_bl(e, ir)
                for i in range(1, e.NUMYRS + 1):
                    nhid = int(e.NHIDATMXD_BYYR[ir, jgrp, ival, i])
                    e.IEDATE = nhid
                    icyr2 = e.IEDATE // 1000000
                    icyr = 0
                    if icyr2 <= 99:
                        # LONG_DATE
                        icyr = e.ISTRT_CENT * 100 + icyr2
                        e.IEDATE = e.ISTRT_CENT * 100000000 + nhid
                    if e.NO2AVE or e.SO2AVE:
                        e.ISDATE = e.IEDATE
                    elif e.PM25AVE:
                        e.ISDATE = e.IEDATE - 23
                    e.FULLDATE = e.ISDATE
                    while e.FULLDATE <= e.IEDATE:
                        fd = e.FULLDATE
                        imn = fd // 10000 - (fd // 1000000) * 100
                        idy = fd // 100 - (fd // 10000) * 100
                        ihr = fd - (fd // 100) * 100
                        ijdy = e.julian(icyr, imn, idy)
                        icjday = e.julian(icyr, e.ISMN, e.ISDY)
                        if ijdy == 0 or icjday == 0:
                            break
                        if e.ISJDAY == 1:
                            e.IHR_NDX = 24 * (ijdy - e.ISJDAY) + (ihr - e.ISHR) + 1
                        elif ijdy >= icjday:
                            e.IHR_NDX = 24 * (ijdy - icjday) + (ihr - e.ISHR) + 1
                        else:
                            ipjday = e.julian(icyr - 1, e.ISMN, e.ISDY)
                            if ipjday > icjday:
                                e.IHR_NDX = 24 * (ijdy - ipjday + 366) + (ihr - e.ISHR) + 1
                            else:
                                e.IHR_NDX = 24 * (ijdy - ipjday + 365) + (ihr - e.ISHR) + 1
                        e.IYR_NDX = i
                        e.IMONTH = imn
                        e.IDAY = idy
                        e.IHOUR = ihr
                        e.IYEAR = icyr2
                        e.IYR = icyr
                        e.KURDAT = icyr2 * 1000000 + imn * 10000 + idy * 100 + ihr
                        e.KURPFL = e.KURDAT
                        maxdcalc(e)
                        e.FULLDATE += 1
                    for ig in range(1, e.NUMGRP + 1):
                        sv[ival, ig, jgrp, ir] = sv[ival, ig, jgrp, ir] + e.AVEVAL[1, ig, 1, 1]
                    e.AVEVAL[...] = 0.0
                    e.NUMHRS[:] = 0
                    e.NUMCLM[:] = 0
                    e.NUMMSG[:] = 0
                    e.HRVAL[:] = 0.0
                    e.AERVAL[:] = 0.0
                    if e.CHI is not None:
                        _vaciar_chi(e)
                for ig in range(1, e.NUMGRP + 1):
                    sv[ival, ig, jgrp, ir] = sv[ival, ig, jgrp, ir] / float(e.NUMYRS)
                if s > 0.0 and abs(sv[ival, jgrp, jgrp, ir] - s) / s > 5.0e-6:
                    e.DUMMY = fwrite('("G",I3.3,"R",I2.2,"R",I4.4)', min(jgrp, 999), min(ival, 99),
                                     min(ir, 9999))[0]
                    e.errhdl(e.PATH, m, "W", "498", e.DUMMY)
                    e.L_MAXDCONT_ORIGCONC_WARNING = True
            maxdcnt_file(e, jgrp, ival)
            if e.SUMHNH[1:nr + 1, jgrp, ival].max() < e.MAXD_THRESH[jgrp]:
                e.MXD_RANK[jgrp, 2] = ival
                hit = True
                break
        if e.MAXD_THRESH[jgrp] > 0.0 and not hit:
            e.errhdl(e.PATH, m, "W", "415", fwrite("('GRP ',A8)", fx(e.GRPID[jgrp], 8))[0])
        hit = False
    e.AXR[:nr + 1] = e.AXR_SAV
    e.AYR[:nr + 1] = e.AYR_SAV
    e.AZELEV[:nr + 1] = e.AZELEV_SAV
    e.AZHILL[:nr + 1] = e.AZHILL_SAV
    e.AZFLAG[:nr + 1] = e.AZFLAG_SAV
    fuente_linea_flotante.maxd_restaurar_bl(e)
    e.NUMREC = nr
    e.ISDATE = isdate_sav
    e.IEDATE = iedate_sav
