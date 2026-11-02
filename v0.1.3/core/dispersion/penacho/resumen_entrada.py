# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): resumen de las entradas (inpsum.f):
INPSUM, PRTOPT, PRTSRC, PRTREC, CHKREC, PRTMET y RESINI, para las opciones del alcance."""
import math

from .estado import NoTraducido
from .formato import fwrite, fx, lw, nint

# formatos de las tablas de fuentes RLINE/RLINEXT y BUOYLINE (PRTSRC)
_F9087 = '(1X,A12,2X,A5,2X,E11.5,4F10.1,A8,F9.2,7X,A3,3X,A7)'
_F9088 = ("(/6X,'BL GRP',3X,'AVG BLDG',3X,'AVG BLDG',3X,'AVG BLDG',3X,'AVG LINE',3X,'AVG SEPARATION',5X,'AV"
          "G BUOYANCY',/16X,'LENGTH',5X,'HEIGHT',5X,'WIDTH',6X,'WIDTH',5X,'BETWEEN LINES',7X,'PARAMETER',1X"
          ",/15X,'(METERS)',3X,'(METERS)',3X,'(METERS)',3X,'(METERS)',6X,'(METERS)',6X,'(METER**4/SEC**3)',"
          "1X/66(' -')/)")
_F9089 = '(6X,A8,3X,F8.1,3X,F8.1,3X,F8.1,3X,F8.1,6X,F8.1,10X,F8.1)'
_F9109 = ("(//40X,'*** RLINE/RLINEXT SOURCE DATA (with MOVES units)','***'//10X,'NUMBER EMISSION RATE',6X,'"
          "FIRST COORD',13X,'SECOND COORD',6X,'BASE',3X,4X,'INIT.  NO.  WIDTH  URBAN  EMIS RATE',/3X,'SOURC"
          "E',7X,'PART. GRAMS/HOUR',5X,'X',7X,'Y',7X,'Z',7X,'X',7X,'Y',7X,'Z',4X,'ELEV.',1X,'DCL',3X,'SZ   "
          " OF    PER',3X,'SOURCE',2X,'SCALAR',/4X,' ID         CATS.    ',1X,('/LINK)'),4X,('(M)     (M)  "
          "   (M)'),5X,('(M)     (M)     (M)   (M)   (M)   (M)'),2X,'LANES',2X,'LANE',9X,'VARY BY',/66(' -'"
          ')/)')
_F9110 = ("(//50X,'*** RLINE/RLINEXT SOURCE DATA ***'//15X,'NUMBER EMISSION RATE',6X,'FIRST COORD',13X,'SEC"
          "OND COORD',9X,'BASE',8X,'INIT.  WIDTH  URBAN EMIS RATE',/3X,'SOURCE',7X,'PART. ',A11,5X,'X',7X,'"
          "Y',7X,'Z',8X,'X',7X,'Y',8X,'Z',5X,'ELEV.',3X,'DCL',3X,'SZ  ',5X,3X,'SOURCE',2X,'SCALAR',/4X,' ID"
          "         CATS.    ',1X,('/METER)'),4X,('(M)     (M)     (M)'),6X,('(M)     (M)      (M)     (M) "
          "   (M)   (M)    (M)'),1X,10X,'VARY BY',/66(' -')/)")
_F9111 = ('(1X,A12,2X,A5,2X,E11.5,1X,F8.1,1X,F9.1,1X,F5.1,1X,F8.1,1X,F9.1,1X,F5.1,1X,A8,1X,F5.1,1X,F5.2,1X,'
          'F5.2,2X,A3,3X,A7)')
_F9112 = ("(//31X,'BARRIER',6X,'BARRIER',21X,'BARRIER',6X,'BARRIER',/3X,'SOURCE',8X,'BARRIER',7X,'HTWALL',7"
          "X,'DCLWALL',7X,'BARRIER',7X,'HTWALL2',5X,'DCLWALL2',/4X,'ID',12X,'ID1',9X,'(METERS)',5X,'(METERS"
          ")',8X,'ID2',9X,'(METERS)',5X,'(METERS)',/66(' -')/)")
_F9113 = '(3X,A12,2X,A12,2X,F6.2,7X,F6.2,5X,A12,5X,F6.2,7X,F6.2)'
_F8112 = ("(//50X,'*** Vegetative Barriers ***',//3X,'SOURCE',9X,'HT',6X,'WT',5X,'DCL',3X,'LAI',4X,'LAD',4X"
          ",'WAKE',7X,'HT',6X,'WT',5X,'DCL',3X,'LAI',4X,'LAD',4X,'WAKE'/5X,'ID',10X,'(M)',5X,'(M)',5X,'(M)'"
          ",9X,'(1/M)',4X,'(M)',6X,'(M)',5X,'(M)',5X,'(M)',9X,'(1/M)',4X,'(M)',/66(' -')/)")
_F8113 = ('(3X,A12,2X,F5.1,2X,F5.1,2X,F6.1,2X,F4.1,3X,F4.1,3X,F5.1,5X,F5.1,2X,F5.1,2X,F6.1,2X,F4.1,3X,F4.1,'
          '3X,F5.1/)')
_F9114 = ("(//14X,'DEPRESSED',5X,'DEPRESSED',3X,'DEPRESSED'/3X,'SOURCE',5X,'DEPTH',12X,'WTOP',7X,'WBOTTOM'/"
          "4X,'ID',7X,'(METERS)',5X,'(METERS)',5X,'(METERS)'/66(' -')/)")
_F9115 = '(1X,A12,1X,F6.2,2(8X,F6.2))'
_F9086 = ("(//50X,'*** BUOYANT LINE SOURCE DATA ***'//15X,'NUMBER EMISSION RATE',5X,'FIRST COORD',8X,'SECON"
          "D COORD',5X,'BASE    RELEASE    URBAN   EMISSION RATE',/3X,'SOURCE',7X,'PART. ',A11,')',7X,'X',7"
          "X,'Y',11X,'X',7X,'Y',6X,'ELEV.   ','HEIGHT',5X,'SOURCE',2x,'SCALAR VARY',/4X,' ID         CATS. "
          "              ',1X,('(METERS) (METERS)'),3X,('(METERS) (METERS)'),1X,('(METERS) (METERS)'),16X,'"
          "BY'/66(' -')/)")

F9099 = "(1X,' ')"


def resini(e):
    """RESINI: pone a cero las matrices de resultados."""
    for n in ("NUMHRS", "NUMCLM", "NUMMSG"):
        getattr(e, n)[:] = 0
    for n in ("HRVAL", "AVEVAL", "HIVALU", "NHIDAT", "HMAX", "HMDATE", "HMLOC", "RMXVAL", "MXDATE", "MXLOCA",
              "BACKAVE", "BACKANN", "BACKSEASHR", "BACKHR", "ANNVAL", "SUMANN", "AMXVAL", "IMXLOC", "SUMHNH",
              "MXPMVAL", "MXPMLOC", "SHVALS", "MXDVAL", "HIMXDLY", "HIMXDLY_BYYR", "IMXDHR", "NHIDATMXD",
              "NHIDATMXD_BYYR"):
        a = getattr(e, n)
        if a is not None:
            a[...] = 0
    for n in ("HCLMSG", "HMCLM", "MCLMSG"):
        a = getattr(e, n)
        if a is not None:
            a.fill("")
    e.IANHRS = e.IANCLM = e.IANMSG = 0
    e.NSKIPTOT = 0
    e.NSEAHR[...] = 0
    e.NSEACM[...] = 0


def inpsum(e):
    """INPSUM: resumen de las entradas en el fichero de salida (y en el SUMMFILE)."""
    prtopt(e, e.IOUNIT)
    if e.SUMMFILE:
        prtopt(e, e.ISUMUNT)
    for i in range(1, e.NUMO3SECTS + 1):
        if e.L_O3VALUES[i]:
            prtvals(e, i, "O3")
    for i in range(1, e.NUMNOXSECTS + 1):
        if e.L_NOX_VALS[i]:
            prtvals(e, i, "NOX")
    prtsrc(e)
    if e.L_BACKGRND:
        for i in range(1, e.NUMBGSECTS + 1):
            prtbkg(e, i)
    if not e.EVONLY:
        prtrec(e)
        chkrec(e)
    prtmet(e, e.IOUNIT)
    if e.SUMMFILE:
        prtmet(e, e.ISUMUNT)


def prtopt(e, u):
    """PRTOPT: resumen de las opciones del modelo."""
    o = []
    w = o.append
    numpf = int(e.OSPLAT[1:].sum()) if e.OSPLAT is not None else 0
    e.header(u)
    o += fwrite("(/44X,'***     MODEL SETUP OPTIONS SUMMARY       ***'/63(' -')/)")
    w(lw("** Model Options Selected:"))
    w(lw("     * Model Uses Regulatory DEFAULT Options" if e.DFAULT else "     * Model Allows User-Specified Options"))
    if e.CONC:
        w(lw("     * Model Is Setup For Calculation of ", "Average CONCentration Values."))
    if e.DEPOS:
        w(lw("     * Model Is Setup For Calculation of ", "Total DEPOSition Values."))
    if e.DDEP:
        w(lw("     * Model Is Setup For Calculation of ", "Dry DEPosition Values."))
    if e.WDEP:
        w(lw("     * Model Is Setup For Calculation of ", "Wet DEPosition Values."))
    if e.LDGAS and e.LUSERVD:
        w(lw("     * User-specified GAS DRY ", " DEPOSITION Velocity Provided."))
    elif e.LDGAS or e.LWGAS:
        w(lw("     * GAS DEPOSITION Data Provided."))
    else:
        w(lw("     * NO GAS DEPOSITION Data Provided."))
    w(lw("     * PARTICLE DEPOSITION Data Provided." if e.LDPART else "     * NO PARTICLE DEPOSITION Data Provided."))
    if e.DDPLETE:
        w(lw("     * Model Uses DRY DEPLETION. ", "DDPLETE  = ", e.DDPLETE))
        if e.ARDPLETE:
            w(lw("        with AREADPLT option    AREADPLT = ", e.ARDPLETE))
        elif e.ROMBERG:
            w(lw("        with ROMBERG option     ROMBERG  = ", e.ROMBERG))
    else:
        w(lw("     * Model Uses NO DRY DEPLETION. ", "DDPLETE  = ", e.DDPLETE))
    if e.WDPLETE:
        w(lw("     * Model Uses WET DEPLETION. ", "WETDPLT  = ", e.WDPLETE))
    else:
        w(lw("     * Model Uses NO WET DEPLETION. ", "WETDPLT  = ", e.WDPLETE))
    if not e.DFAULT and e.NOSTD:
        w(lw("     * No Stack-tip Downwash"))
    else:
        w(lw("     * Stack-tip Downwash."))
    if e.DFAULT:
        w(lw("     * Model Accounts for ELEVated ", "Terrain Effects."))
    elif e.FLATSRCS:
        w(lw("     * Allow FLAT/ELEV ", "Terrain Option by Source,"))
        o += fwrite("(8X,'with ',I6,' FLAT and ',I6,' ELEV Source(s).')", e.NUMFLAT, e.NUMSRC - e.NUMFLAT)
    elif e.FLAT:
        w(lw("     * Model Assumes Receptors on ", "FLAT Terrain."))
    elif e.ELEV:
        w(lw("     * Model Accounts for ELEVated ", "Terrain Effects."))
    w(lw("     * Use Calms Processing ", "Routine."))
    w(lw("     * Use Missing Data ", "Processing Routine."))
    if e.DFAULT:
        if e.URBAN and e.POLLUT == "SO2":
            w(lw("     * Half-life of 4 hrs for", " URBAN SO2."))
        else:
            w(lw("     * No Exponential Decay."))
    else:
        if e.URBAN and e.POLLUT == "SO2":
            if e.ICSTAT[7] == 1 or e.ICSTAT[8] == 1:
                if abs(e.DECOEF - 4.81e-5) <= 5.0e-8:
                    w(lw("     * Half-life of 4 hrs for", " URBAN SO2."))
                else:
                    w(lw("     * Non-DFAULT Half-life for ", " URBAN SO2."))
            elif e.ICSTAT[7] == 0 and e.ICSTAT[8] == 0:
                w(lw("     * Half-life of 4 hrs for", " URBAN SO2."))
        elif e.DECOEF != 0.0:
            w(lw("     * Non-DFAULT Exponential", " Decay."))
        else:
            w(lw("     * No Exponential Decay."))
    if e.POLLUT == "NO2":
        if e.PVMRM:
            w(lw("     * Plume Volume Molar Ratio Method (PVMRM)", "Used for NO2 Conversion"))
            o += fwrite("('        with an Equilibrium NO2/NOx ','Ratio of ',F6.3)", e.NO2EQUIL)
            o += fwrite("('        and with a Default In-stack ','Ratio of ',F6.3)", e.NO2STACK)
            if e.PSDCREDIT:
                w(lw("     * ALPHA Option for  ", "Calculating PSD Increment"))
                w(lw("     * Consumption with PSD ", "Credits Selected."))
        elif e.OLM:
            w(lw("     * Ozone Limiting Method (OLM) ", "Used for NO2 Conversion"))
            o += fwrite("('        with an Equilibrium NO2/NOx ','Ratio of ',F6.3,' and')", e.NO2EQUIL)
            if e.NUMOLM > 0:
                o += fwrite("('        with ',I3,' OLMGROUP(s)')", e.NUMOLM)
            else:
                o += fwrite("('        with NO OLMGROUPs')")
        elif e.RUNTTRM:
            w(lw("     * Travel Time Reaction Method", "Used for NO2 Conversion"))
            o += fwrite("('        with an Equilibrium NO2/NOx ','Ratio of ',F6.3,' and')", e.NO2EQUIL)
        elif e.ARM2:
            w(lw("     * Ambient Ratio ", "Method Ver 2 (ARM2) Used for NO2 Conversion"))
            o += fwrite("('         with a Minimum NO2/NOx ','Ratio of ',F6.3)", e.ARM2_MIN)
            o += fwrite("('         and a Maximum NO2/NOx ','Ratio of ',F6.3)", e.ARM2_MAX)
        elif e.GRSM:
            w(lw("     * GRS Chemistry ", "Method (GRSM) Used for NO2 Conversion"))
        else:
            w(lw("     * Full Conversion ", "Assumed for NO2."))
    if not e.URBAN:
        w(lw("     * Model Uses RURAL Dispersion Only."))
    else:
        o += fwrite("(1X,'     * Model Uses URBAN Dispersion Algorithm ','for the SBL for ',I5,' Source(s),'"
                    "/'        for Total of ',I4,' Urban Area(s):')", e.NURBSRC, e.NUMURB)
        if e.NUMURB > 1:
            for i in range(1, e.NUMURB + 1):
                o += fwrite("(8X,'Urban ID = ',A8,' ;  Urban Population = ',F11.1,' ;  Urban Roughness Length = ',"
                            "F6.3,' m')", fx(e.URBID[i], 8), e.URBPOP[i], e.URBZ0[i])
        else:
            o += fwrite("(3X,'Urban Population = ',F11.1,' ;  Urban Roughness Length = ',F6.3,' m')",
                        e.URBPOP[1], e.URBZ0[1])
        z0 = e.URBZ0[1:]
        if z0.max() != 1.0 or z0.min() != 1.0:
            w(lw("     * Non-DFAULT Urban ", "Roughness Length(s) Used."))
        else:
            w(lw("     * Urban Roughness Length ", "of 1.0 Meter Used."))
        if not e.L_URBANTRANSITION:
            o += fwrite("(1X,'     * Non-DFAULT option to ignore morning ','transition from nighttime urban boundary',"
                        "/'        layer (NoUrbTran) selected.')")
    if e.NUMCAP > 0 or e.NUMHOR > 0:
        w(lw("     * Option for Capped &", " Horiz Stacks Selected With:"))
        o += fwrite("(1X,I10,' Capped Stack(s); and',I10,' Horizontal Stack(s)')", e.NUMCAP, e.NUMHOR)
    if e.NOCHKD:
        w(lw("     * NOCHKD   - Suppresses checking", " of date sequence in meteorology files"))
    elif e.L_WARNCHKD:
        w(lw("     * WARNCHKD - Issues warning messages", " for records out of sequence"))
        w(lw("       in meteorology files"))
    if e.NOWARN:
        w(lw("     * NOWARN   - Suppresses writing", " of warning messages in main print file"))
    if e.FASTALL:
        w(lw("     * FASTALL  - Use effective sigma-y to", " optimize meander for "))
        w(lw(" POINT and VOLUME", " sources, and hybrid approach"))
        w(lw("to optimize AREA sources", " (formerly TOXICS option)"))
    elif e.FASTAREA:
        w(lw("     * FASTAREA - Use hybrid approach to", " optimize AREA sources;"))
        w(lw("                   also applies to LINE ", "sources (formerly TOXICS option)"))
    if e.SCIM:
        w(lw("     * SCIM  - Use Sampled", " Chronological Input Model (SCIM) option"))
    if e.SCREEN:
        w(lw("     * SCREEN   - Use screening option ", "which forces calculation of centerline values"))
    if e.HBPLUME:
        w(lw("     * HBP - Non-DFAULT option to optimize", " for Highly Buoyant Plumes from"))
        o += fwrite("(1X,I10,' Identified HBP POINT-type Source(s)')", e.NHBP)
    if e.LOW_WIND:
        w(lw("     * Use LOW_WIND ALPHA option"))
        if (e.L_USERSVMIN or e.L_USERWSMIN or e.L_USERFRANMAX or e.L_USERSWMIN or e.L_USERBIGT
                or e.L_USERFRANMIN or e.L_PBAL):
            w(lw("        with the following parameters:"))
            if e.L_USERSVMIN:
                o += fwrite('(12x,"* SVMin =   ",F8.2," m/s")', e.SVMIN)
            if e.L_USERWSMIN:
                o += fwrite('(12x,"* WSMin =   ",F8.2," m/s")', e.WSMIN)
            if e.L_USERFRANMIN:
                o += fwrite('(12x,"* FRANMin = ",F8.2)', e.FRANMIN)
            if e.L_USERSWMIN:
                o += fwrite('(12x,"* SWMin =   ",F8.2," m/s")', e.SWMIN)
            if e.L_USERBIGT:
                o += fwrite('(12x,"* BigT =    ",F8.2," hours")', e.BIGT)
            if e.L_USERFRANMAX:
                o += fwrite('(12x,"* FRANMax = ",F8.2)', e.FRANMAX)
            if e.L_PBAL:
                o += fwrite('(12x,"* PBalance")')
    if e.L_ADJUSTAR:
        w(lw("     * ADJ_U*   - Use ADJ_U* option ", "for SBL in AERMET"))
    if e.L_MMIF_DATA:
        w(lw("     * MMIFData - Use MMIF met data inputs"))
        if e.MMIF_VERSION:
            w(lw("                   ", fx(e.MMIF_VERSION, 29)))
    if e.L_COARE:
        w(lw("     * COARE - Use COARE processing in AERMET"))
    if e.L_BULKRN:
        if e.L_MMIF_DATA:
            w(lw("     * BULKRN   - Use BULKRN Delta-T and ", "SolarRad option for SBL with MMIF"))
        else:
            w(lw("     * BULKRN   - Use BULKRN Delta-T and ", "SolarRad option for SBL in AERMET"))
    if e.L_VECTORWS:
        w(lw("     * VECTORWS - User specifies ", "that input wind speeds are VECTOR means"))
    if e.L_CCVR_SUB:
        w(lw("     * CCVR_Sub - Meteorological data ", "includes CCVR substitutions"))
    if e.L_TEMP_SUB:
        w(lw("     * TEMP_Sub - Meteorological data ", "includes TEMP substitutions"))
    if e.L_RDEPRESS:
        w(lw("     * RDEPRESS - Use ALPHA option ", "for RLINEXT with depression"))
    if e.L_RBARRIER:
        w(lw("     * RBARRIER - Use ALPHA option ", "for RLINEXT with barrier"))
    if e.FLGPOL:
        w(lw("     * Model Accepts FLAGPOLE Receptor .", " Heights. "))
    else:
        w(lw("     * Model Assumes No FLAGPOLE Receptor ", "Heights. "))
    o += fwrite("(1X,'     * The User Specified a Pollutant Type of: ',A8)", fx(e.POLLUT, 8))
    p = e.POLLUT
    if p in ("PM25", "PM-2.5", "PM-25", "PM2.5") and not e.EVONLY:
        if e.PM25AVE:
            o += fwrite("(/1X,'**Note that special processing requirements apply',' for the 24-hour PM2.5 NAAQS - "
                        "check available guidance.'/,'   Model will process user-specified ranks of high 24-hour',"
                        "' values averaged across the number of years modeled, and'/,'   the multi-year average of "
                        "individual ANNUAL values,',' averaged across the number of years modeled.')")
        elif e.L_NO_PM25AVE:
            o += fwrite("(/1X,'**NOTE: Special processing requirements applicable',' for the 24-hour PM2.5 NAAQS "
                        "have been disabled!!!'/,'         High ranked 24-hour values are NOT averaged across',"
                        "' the number of years modeled, and'/,'         complete years of data are NOT required.')")
    elif p in ("NO2", "SO2") and not e.EVONLY:
        ave = e.NO2AVE if p == "NO2" else e.SO2AVE
        lno = e.L_NO_NO2AVE if p == "NO2" else e.L_NO_SO2AVE
        if ave:
            if p == "NO2":
                o += fwrite("(/1X,'**Note that special processing requirements apply',' for the 1-hour NO2 NAAQS - "
                            "check available guidance.'/,'   Model will process user-specified ranks of daily maximum',"
                            "' 1-hour values averaged across the number of years modeled.'/,'   For annual NO2 NAAQS "
                            "modeling, the multi-year maximum of',' PERIOD values can be simulated using the MULTYEAR "
                            "keyword.'/,'   Multi-year PERIOD and 1-hour values should only be done',' in a single "
                            "model run using the MULTYEAR option with a'/,'   single multi-year meteorological data "
                            "file using STARTEND',' keyword.')")
            else:
                o += fwrite("(/1X,'**Note that special processing requirements apply',' for the 1-hour SO2 NAAQS - "
                            "check available guidance.'/,'   Model will process user-specified ranks of daily maximum',"
                            "' 1-hour values averaged across the number of years modeled.')")
        elif lno:
            campo = e.NO2_FIELD4 if p == "NO2" else e.SO2_FIELD4
            o += fwrite("(/1X,'**NOTE: Special processing requirements applicable',' for the 1-hour " + p +
                        " NAAQS have been disabled!!!'/,'         User has specified ',A3,' on the POLLUTID "
                        "keyword.'/,'         High ranked 1-hour values are NOT averaged across',' the number of "
                        "years modeled, and'/,'         complete years of data are NOT required.')", fx(campo, 3))
        else:
            chraves = ""
            for i in range(1, e.NUMAVE + 1):
                if e.CHRAVE[i] != " 1-HR":
                    chraves = (chraves + "  " + fx(e.CHRAVE[i], 5))[:30].rstrip(" ")
            o += fwrite("(/1X,'**NOTE: Special processing requirements applicable',' for the 1-hour " + p +
                        " NAAQS have been disabled!!!'/,'         User has specified non-standard averaging "
                        "periods: ',A/,'         High ranked 1-hour values are NOT averaged across',' the number "
                        "of years modeled, and'/,'         complete years of data are NOT required.')",
                        fx(chraves, 30))
    o += fwrite(F9099)
    f9042 = "(1X,'**Model Calculates ',I2,' Short Term Average(s)',' of:  ',9(A5,2X,:))"
    chr_ = [fx(e.CHRAVE[i], 5) for i in range(1, e.NUMAVE + 1)]
    if e.PERIOD:
        if e.NUMAVE > 0:
            o += fwrite(f9042, e.NUMAVE, *chr_)
            o += fwrite("(1X,'    and Calculates PERIOD Averages')")
        else:
            o += fwrite("(1X,'**Model Calculates PERIOD Averages Only')")
    elif e.ANNUAL:
        if e.NUMAVE > 0:
            o += fwrite(f9042, e.NUMAVE, *chr_)
            o += fwrite("(1X,'    and Calculates ANNUAL Averages')")
        else:
            o += fwrite("(1X,'**Model Calculates ANNUAL Averages Only')")
    else:
        o += fwrite(f9042, e.NUMAVE, *chr_)
    o += fwrite(F9099)
    o += fwrite("(1X,'**This Run Includes: ',I6,' Source(s);  ',I6,' Source Group(s); and  ',I6,' Receptor(s)',//"
                "16X,'with: ',I6,' POINT(s), including'/22X,I6,' POINTCAP(s) and ',I6,' POINTHOR(s)'/16X,' and: ',"
                "I6,' VOLUME source(s)',/,16X,' and: ',I6,' AREA type source(s)'/,16X,' and: ',I6,' LINE source(s)',"
                "/,16X,' and: ',I6,' RLINE/RLINEXT source(s)'/,16X,' and: ',I6,' OPENPIT source(s)',/,16X,' and: ',"
                "I6,' BUOYANT LINE source(s) with a total of',I6,' line(s)',/,16x,' and: ',I6,' SWPOINT source(s)',/)",
                e.NUMSRC, e.NUMGRP, e.NUMREC, e.NUMPNT, e.NUMCAP, e.NUMHOR, e.NUMVOL, e.NUMAREA, e.NUMLINE,
                e.NRLINES, e.NUMPIT, e.NUMBLGRPS, e.NBLTOTAL, e.NUMSWP)
    if (e.NUMPNT > 0 or e.NUMCAP > 0 or e.NUMHOR > 0) and numpf > 0:
        o += fwrite("(1X,'**Number of Platform Point Sources:', I6)", numpf)
    if e.L_AWMADW or e.L_STRMLN_BLDG or e.L_AWMA_ENTRAIN or e.L_ORDDW:
        raise NoTraducido("opciones AWMA/ORD de downwash")
    if e.L_BACKGRND:
        _opciones_fondo(e, o)
    if e.OLM or e.PVMRM or e.GRSM:
        _opciones_quimica(e, o, "OZONE    ", e.L_O3SECTOR, e.NUMO3SECTS, e.O3SECT, e.L_O3FILE,
                          e.IO3SET, e.L_O3VAL, e.O3FLAG, "OZONE")
    if e.GRSM:
        _opciones_quimica(e, o, "NOx      ", e.L_NOXSECTOR, e.NUMNOXSECTS, e.NOXSECT, e.L_NOXFILE,
                          e.INOXSET, e.L_NOXVALUE, e.NOXFLAG, "NOX")
    o += fwrite(F9099)
    if e.RUN:
        w(lw("**Model Set To Continue RUNning After the ", "Setup Testing."))
    else:
        w(lw("**Model Will NOT Run After the ", "Setup Testing."))
    o += fwrite("(/1X,'**The AERMET Input Meteorological Data Version Date:',1X,A6)", fx(e.C_METVER, 6))
    o += fwrite(F9099)
    o += fwrite("(1X,'**Output Options Selected:')")
    salidas = ((2, "Tables of Highest Short Term Values by Receptor (RECTABLE Keyword)"),
               (3, "Tables of Overall Maximum Short Term Values (MAXTABLE Keyword)"),
               (4, "Tables of Concurrent Short Term Values by Receptor for Each Day Processed (DAYTABLE Keyword)"),
               (5, "External File(s) of Threshold Violations (MAXIFILE Keyword)"),
               (6, "External File(s) of Concurrent Values for Postprocessing (POSTFILE Keyword)"),
               (7, "External File(s) of High Values for Plotting (PLOTFILE Keyword)"),
               (8, "External File(s) of Values for Input to TOXX Model (TOXXFILE Keyword)"),
               (9, "External File(s) of Values by Season and Hour-of-Day (SEASONHR Keyword)"),
               (10, "External File(s) of Ranked Values (RANKFILE Keyword)"),
               (11, "External File(s) of Arc-maximum Values for Evaluation Purposes (EVALFILE Keyword)"),
               (12, "Separate Summary File of High Ranked Values (SUMMFILE Keyword)"),
               (14, "External File(s) of Maximum Daily 1-hr Values by Day (MAXDAILY Keyword)"),
               (15, "External File(s) of Maximum Daily 1-hr Values by Year (MXDYBYYR Keyword)"),
               (16, "External File(s) of Contributions to Maximum Daily Values Paired in Time & Space "
                    "(MAXDCONT Keyword)"))
    if e.PERIOD:
        w(" " * 10 + "Model Outputs Tables of PERIOD Averages by Receptor")
    elif e.ANNUAL:
        w(" " * 10 + "Model Outputs Tables of ANNUAL Averages by Receptor")
    for io, txt in salidas:
        if e.IOSTAT[io] > 0:
            w(" " * 10 + "Model Outputs " + txt)
    if e.FILE_FORMAT == "EXP" and (e.MXFILE or e.PPFILE or e.RKFILE or e.ANPOST or e.ANPLOT or e.SEASONHR):
        o += fwrite(F9099)
        w(" " * 10 + "NOTE: Option for EXPonential format used in formatted output result files (FILEFORM Keyword)")
    if e.CLMPRO or e.MSGPRO:
        o += fwrite(F9099)
        o += fwrite("(1X,'**NOTE:  The Following Flags May Appear Following ',A4,' Values:  c for Calm Hours',"
                    "/65X,'m for Missing Hours',/65X,'b for Both Calm and Missing Hours')", fx(e.CHIDEP[3, 1], 4))
    o += fwrite(F9099)
    o += fwrite("(1X,'**Misc. Inputs:  Base Elev. for Pot. Temp. Profile ','(m MSL) = ',F8.2,' ;  Decay Coef. = ',"
                "G12.4,' ;','  Rot. Angle = ',F7.1)", e.ZBASE, e.DECOEF, e.ROTANG)
    f9055 = ("(18X,'Emission Units = ',A40,' ;  Emission Rate Unit ','Factor = ',G13.5,/18X,'Output Units   = ',"
             "A40)")
    if e.NUMTYP == 1 or not e.CONC:
        o += fwrite(f9055, fx(e.EMILBL[1], 40), e.EMIFAC[1], fx(e.OUTLBL[1], 40))
    else:
        # varios tipos con CONC: unidades de concentración y, después, las de los depósitos
        o += fwrite("(2X,'Concentration:',2X,'Emission Units = ',A40,' ;  ','Emission Rate Unit Factor = ',"
                    "G13.5,/18X,'Output Units   = ',A40)", fx(e.EMILBL[1], 40), e.EMIFAC[1], fx(e.OUTLBL[1], 40))
        o += fwrite("(5X,'Deposition:',2X,'Emission Units = ',A40,' ;  ','Emission Rate Unit Factor = ',"
                    "G13.5,/18X,'Output Units   = ',A40)", fx(e.EMILBL[2], 40), e.EMIFAC[2], fx(e.OUTLBL[2], 40))
    if e.LUSERVD:
        o += fwrite(F9099)
        o += fwrite("(18X,'User-Specified Dry Deposition Velocity for Gases ','(m/s) = ',G13.5)", e.USERVD)
    if not e.EVONLY:
        o += fwrite(F9099)
        o += fwrite("(1X,'**Approximate Storage Requirements of Model = ',F8.1,' MB of RAM.')", e.STORE)
    o += fwrite(F9099)
    if e.INPFIL or e.OUTFIL:
        o += fwrite("(1X,'**Input Runstream File:          ',A96,/1X,'**Output Print File:             ',A96/)",
                    fx(e.INPFIL, 96), fx(e.OUTFIL, 96))
    if e.RSTINP:
        o += fwrite("(1X,'**NOTE: This Run was Restarted (" + ("MULTYEAR" if e.MULTYR else "INITFILE") +
                    " Keyword):',/1X,'**File for Initializing Arrays:  ',A96)", fx(e.INIFIL, 96))
    if (e.DEBUG or e.METEORDBG or e.AREADBG or e.PRIMEDBG or e.PVMRMDBG or e.OLMDEBUG or e.ARM2DEBUG or
            e.DEPOSDBG or e.TTRMDBG or e.GRSMDEBUG or e.PLATFMDBG or e.ARCFTDEBUG):
        dop = [""] * 13
        for i, (act, txt) in enumerate(((e.DEBUG, "DEBUG"), (e.METEORDBG, "METEOR"), (e.AREADBG, "AREADBG"),
                                        (e.PRIMEDBG, "PRIMEDBG"), (e.PVMRMDBG, "PVMRMDBG"),
                                        (e.OLMDEBUG, "OLMDEBUG")), 1):
            if act:
                dop[i] = txt
        for i, act, txt in ((8, e.ARM2DEBUG, "ARM2DEBUG"), (9, e.DEPOSDBG, "DEPOSDBG"),
                            (10, e.GRSMDEBUG, "GRSMDEBUG"), (11, e.TTRMDBG, "TTRMDEBUG"),
                            (12, e.ARCFTDEBUG, "AIRCRAFT"), (7, e.AWMADWDBG, "AWMADWDBG"),
                            (10, e.PLATFMDBG, "PLATFMDBG")):
            if act:
                dop[i] = txt
        s, nops = "", 0
        for i in range(1, 13):
            if dop[i]:
                nops += 1
                s = (fx(s, 10 * (nops - 1)) + " " + fx(dop[i], 10))[:80]
        o += fwrite("(1X,'**Debug Options Selected:',8X,A:)", s.rstrip(" "))
        o.append(lw(""))
    if e.RSTSAV:
        o += fwrite("(1X,'**File for Saving Result Arrays: ',A96)", fx(e.SAVFIL, 96))
    if e.ERRLST:
        o += fwrite("(1X,'**Detailed Error/Message File:   ',A96)", fx(e.MSGFIL, 96))
    if e.EVENTS:
        o += fwrite("(1X,'**File Created for Event Model:  ',A96)", fx(e.EVFILE, 96))
    if e.SUMMFILE:
        o += fwrite("(1X,'**File for Summary of Results:   ',A96)", fx(e.SUMFIL, 96))
    if e.MULTYR:
        o += fwrite(F9099)
        o.append(lw("**This Run is Part of a Multi-year (MULTYEAR)", " Application."))
        if e.PERIOD:
            o.append(lw("  NOTE:  The PERIOD Results Table Reflects", " Current Period Only;"))
            o.append(lw("         The Overall Maximum PERIOD", " Results Table and"))
        elif e.ANNUAL:
            o.append(lw("  NOTE:  Both ANNUAL Average Results and"))
        else:
            o.append(lw("  NOTE:"))
        o.append(lw("         Short Term Results are Cumulative", " Across All Years Processed."))
    e.w(u, o)


def _opciones_quimica(e, o, nom, sector_on, nsect, sect, lfile, iset, lval, flags, nom_h):
    """PRTOPT: resumen de los datos de ozono (OLM/PVMRM/GRSM) o de NOx (GRSM) de fondo.

    ``nom`` es la etiqueta de 9 caracteres de los títulos ('OZONE    ' o 'NOx      ') y ``nom_h``
    la de las líneas de valores horarios ('OZONE' o 'NOX')."""
    h8 = (nom_h + "         ")[:9]
    f_lleno = ("(1X,'     Missing HOURLY " + h8 + "Values ','are Filled Based on Values Varying by: ',"
               "A:)")
    f_nohor = "(1X,'         Non-HOURLY " + nom + "Values',' are Available Varying by: ',A:)"
    if sector_on:
        s = "".join(fwrite("(I4)", nint(sect[i]))[0] for i in range(1, nsect + 1))
        o += fwrite("(/1X,'**This Run Includes " + nom + "Values',' that Vary Across  ',I3,"
                    "' Downwind Sector(s): ',A:)", nsect, s.rstrip(" "))
        s = ""
        nhor = 0
        for i in range(1, nsect + 1):
            if lfile[i]:
                s = s.rstrip(" ") + fwrite("(I4)", nint(sect[i]))[0]
                nhor += 1
        if nhor > 0:
            o += fwrite("(1X,'             HOURLY " + h8 + "Values',' are Available for ',I3,"
                        "' Downwind Sector(s): ',A:)", nhor, s.rstrip(" "))
        s = ""
        nnoh = 0
        for i in range(1, nsect + 1):
            if iset[i] > 0 or lval[i]:
                s = s.rstrip(" ") + fwrite("(I4)", nint(sect[i]))[0]
                nnoh += 1
        if nnoh > 0:
            o += fwrite("(1X,'         Non-HOURLY " + nom + "Values',' are Available for ',I3,"
                        "' Downwind Sector(s): ',A:)", nnoh, s.rstrip(" "))
        fl = ""
        for i in range(1, nsect + 1):
            if (iset[i] > 0 or lval[i]) and lfile[i]:
                if iset[i] > 0:
                    fl = fl.rstrip(" ") + " " + flags[i].rstrip(" ")
                elif lval[i]:
                    fl = fl.rstrip(" ") + " " + "ANNUAL"
        if fl.rstrip(" "):
            o += fwrite(f_lleno, fl.rstrip(" "))
        fl = ""
        for i in range(1, nsect + 1):
            if iset[i] > 0 or lval[i]:
                if iset[i] > 0:
                    fl = fl.rstrip(" ") + " " + flags[i].rstrip(" ")
                elif lval[i]:
                    fl = fl.rstrip(" ") + " " + "ANNUAL"
        if fl.rstrip(" "):
            o += fwrite(f_nohor, fl.rstrip(" "))
    else:
        o += fwrite("(/1X,'**This Run Includes " + nom + "Values ','for a Single Sector')")
        if lfile[1]:
            o += fwrite("(1X,'             HOURLY " + h8 + "Values ','are Available')")
            if flags[1].rstrip(" "):
                o += fwrite(f_lleno, flags[1].rstrip(" "))
        elif flags[1].rstrip(" "):
            o += fwrite(f_nohor, flags[1].rstrip(" "))


def prtvals(e, isect, cual):
    """PRTO3VALS / PRTNOXVALS: tabla de los valores de ozono (O3VALUES) o de NOx (NOX_VALS) que
    varían en el tiempo para el sector ISECT."""
    u = e.IOUNIT
    if cual == "O3":
        b, f, un, nom, col = e.O3VARY, e.O3FLAG[isect], fx(e.OZONEUNITS, 5), "OZONE", "O3VALS"
    else:
        b, f, un, nom, col = e.NOXVARY, e.NOXFLAG[isect], fx(e.NOXUNITS, 5), "NOX", "NOXVALS"
    f9012 = "(5X,6('HOUR    " + col + "',6X))"
    f99012 = "(2X,8('HOUR   " + col + "',3X))"
    f9013 = "(1X,65('- ')/)"
    f99013 = "(1X,65('- '))"
    f9014 = "(4(5X,6(I3,3X,E10.5,4X)/))"
    f99014 = "(2(3X,8(I2,2X,E9.4,3X)/),3X,8(I2,2X,E9.4,3X))"

    def pares(fmt, base):
        items = []
        for k in range(1, 25):
            items += [k, b[k + base, isect]]
        return fwrite(fmt, *items)

    o = []
    if f == "ANNUAL":
        e.header(u)
        o += fwrite("(/40X,'* SECT',I1,' ANNUAL (NON-VARYING) " + nom + " ','CONCENTRATION (',A5,') *'/)",
                    isect, un)
        o += fwrite("(38X,4(E10.5,5X))", b[1, isect])
    elif f == "SEASON":
        e.header(u)
        o += fwrite("(/30X,'* SECT',I1,' " + nom + " CONCENTRATIONS (',A5,') ','WHICH VARY SEASONALLY *'/)",
                    isect, un)
        o += fwrite("(40X,4(A6,9X)/20X,40('- ')/)", *_SEASON)
        o += fwrite("(38X,4(E10.5,5X))", *[b[k, isect] for k in range(1, 5)])
    elif f == "MONTH":
        e.header(u)
        o += fwrite("(/42X,'* SECT',I1,' " + nom + " CONCENTRATIONS (',A5,') ','WHICH VARY MONTHLY *'/)",
                    isect, un)
        o += fwrite("(7X,'JANUARY  FEBRUARY   MARCH     APRIL      MAY       ','JUNE      JULY     AUGUST   "
                    "SEPTEMBER  OCTOBER  NOVEMBER  ','DECEMBER'/)")
        o += fwrite(f9013)
        o += fwrite("(5X,12(E9.3,1X))", *[b[k, isect] for k in range(1, 13)])
    elif f == "HROFDY":
        e.header(u)
        o += fwrite("(/29X,'* SECT',I1,' " + nom + " CONCENTRATIONS (',A5,') ','WHICH VARY FOR EACH HOUR OF "
                    "THE DAY *'/)", isect, un)
        o += fwrite(f9012)
        o += fwrite(f9013)
        o += pares(f9014, 0)
    elif f == "SEASHR":
        e.header(u)
        o += fwrite("(/23X,'* SECT',I1,' " + nom + " CONCENTRATIONS (',A5,') ',' WHICH VARY SEASONALLY AND "
                    "DIURNALLY (SEASHR) *'/)", isect, un)
        o += fwrite(f9012)
        o += fwrite(f9013)
        for i1 in range(1, 5):
            o += fwrite("(59X,'SEASON = ',A6)", _SEASON[i1 - 1])
            o += pares(f9014, (i1 - 1) * 24)
    elif f in ("HRDOW", "HRDOW7"):
        e.header(u)
        o += fwrite("(/20X,'* SECT',I1,' " + nom + " CONCENTRATIONS (',A5,') ',' WHICH VARY DIURNALLY AND BY "
                    "DAY OF WEEK (%s) *'/)" % f, isect, un)
        o += fwrite(f99012)
        o += fwrite(f99013)
        for i1, d in enumerate(_DOW if f == "HRDOW" else _DOW7, 1):
            o += fwrite("(46X,'DAY OF WEEK = ',A8)", d)
            o += pares(f99014, (i1 - 1) * 24)
    elif f in ("SHRDOW", "SHRDOW7"):
        e.header(u)
        o += fwrite("(/18X,'* SECT',I1,' " + nom + " CONCENTRATIONS (',A5,') ',' WHICH VARY SEASONALLY, "
                    "DIURNALLY AND BY DAY OF WEEK ','(%s) *'/)" % f, isect, un)
        o += fwrite(f99012)
        o += fwrite(f99013)
        for i1, d in enumerate(_DOW if f == "SHRDOW" else _DOW7, 1):
            for i2 in range(1, 5):
                o += fwrite("(46X,'SEASON = ',A6,';  DAY OF WEEK = ',A8)", _SEASON[i2 - 1], d)
                o += pares(f99014, (i2 - 1) * 24 + (i1 - 1) * 96)
    elif f in ("MHRDOW", "MHRDOW7"):
        for i1, d in enumerate(_DOW if f == "MHRDOW" else _DOW7, 1):
            e.header(u)
            o += fwrite("(/19X,'* SECT',I1,' " + nom + " CONCENTRATIONS (',A5,') ',' WHICH VARY MONTHLY, "
                        "DIURNALLY AND BY DAY OF WEEK ','(%s) *'/)" % f, isect, un)
            o += fwrite(f99012)
            o += fwrite(f99013)
            for i2 in range(1, 13):
                o += fwrite("(46X,'MONTH = ',A9,';  DAY OF WEEK = ',A8)", _MONTHS[i2 - 1], d)
                o += pares(f99014, (i2 - 1) * 24 + (i1 - 1) * 288)
            e.w(u, o)
            o = []
    elif f == "WSPEED" and cual == "NOX":
        e.header(u)
        o += fwrite("(/34X,'* SECT',I1,' NOX CONCENTRATIONS (',A5,') ',' WHICH VARY WITH WIND SPEED *'/)",
                    isect, un)
        o += fwrite("(26X,6('   WIND SPEED')/26X,6('   CATEGORY',I2))", *range(1, 7))
        o += fwrite(f99013)
        o += fwrite("(26X,6(1X,E12.5))", *[b[k, isect] for k in range(1, 7)])
    e.w(u, o)


def _opciones_fondo(e, o):
    """PRTOPT: líneas del resumen de opciones sobre los valores de fondo (BACKGRND)."""
    numback = sum(1 for i in range(1, e.NUMGRP + 1) if e.GRP_BACK[i])
    nb = e.NUMBGSECTS
    if e.L_BGSECTOR:
        cad = fwrite("(6I4)", *[nint(e.BGSECT[i]) for i in range(1, nb + 1)])[0].rstrip(" ")
        o += fwrite("(/1X,'**This Run Includes BACKGRND Values',' for ',I6,' Source Group(s) Varying Across ',"
                    "I3,' Downwind Sector(s): ',A:)", numback, nb, cad)
        hor = [i for i in range(1, nb + 1) if e.L_BGFILE[i]]
        if hor:
            cad = "".join(fwrite("(I4)", nint(e.BGSECT[i]))[0] for i in hor).rstrip(" ")
            o += fwrite("(1X,'             HOURLY BACKGRND Values',' are Available for ',I3,"
                        "' Downwind Sector(s): ',A:)", len(hor), cad)
        nohor = [i for i in range(1, nb + 1) if e.L_BGVALUES[i]]
        if nohor:
            cad = "".join(fwrite("(I4)", nint(e.BGSECT[i]))[0] for i in nohor).rstrip(" ")
            o += fwrite("(1X,'         Non-HOURLY BACKGRND Values',' are Available for ',I3,"
                        "' Downwind Sector(s): ',A:)", len(nohor), cad)
        cad = "".join(" " + e.BFLAG[i] for i in range(1, nb + 1) if e.L_BGVALUES[i] and e.L_BGFILE[i])
        if cad.strip():
            o += fwrite("(1X,'     Missing HOURLY BACKGRND Values ','are Filled Based on Values Varying by: ',A:)",
                        cad.rstrip(" "))
        cad = "".join(" " + e.BFLAG[i] for i in nohor)
        if cad.strip():
            o += fwrite("(1X,'         Non-HOURLY BACKGRND Values',' are Available Varying by: ',A:)",
                        cad.rstrip(" "))
    else:
        o += fwrite("(/1X,'**This Run Includes BACKGRND Values ','for ',I6,' Source Group(s) for a Single Sector')",
                    numback)
        if e.L_BGFILE[1]:
            o += fwrite("(1X,'             HOURLY BACKGRND Values',' are Available')")
            if e.BFLAG[1]:
                o += fwrite("(1X,'     Missing HOURLY BACKGRND Values ','are Filled Based on Values Varying by: ',"
                            "A:)", e.BFLAG[1])
        elif e.BFLAG[1]:
            o += fwrite("(1X,'         Non-HOURLY BACKGRND Values',' are Available Varying by: ',A:)", e.BFLAG[1])


def prtbkg(e, isect):
    """PRTBKG: tabla de los valores de fondo del sector ISECT."""
    u = e.IOUNIT
    b = e.BACKGRND
    un = fx(e.BACKUNITS, 5)
    f = e.BFLAG[isect]
    f9012 = "(5X,6('HOUR    BKGRND',6X))"
    f99012 = "(2X,8('HOUR   BKGRND',3X))"
    f9013 = "(1X,65('- ')/)"
    f99013 = "(1X,65('- '))"
    f9014 = "(4(5X,6(I3,3X,E10.5,4X)/))"
    f99014 = "(2(3X,8(I2,2X,E9.4,3X)/),3X,8(I2,2X,E9.4,3X))"

    def pares(fmt, base):
        items = []
        for k in range(1, 25):
            items += [k, b[k + base, isect]]
        return fwrite(fmt, *items)

    o = []
    if f == "ANNUAL":
        e.header(u)
        o += fwrite("(/31X,'* SECT',I1,' ANNUAL (NON-VARYING) BACKGROUND ','CONCENTRATION (',A5,') *'/)", isect, un)
        o += fwrite("(38X,4(E10.5,5X))", b[1, 1])
    elif f == "SEASON":
        e.header(u)
        o += fwrite("(/31X,'* SECT',I1,' BACKGROUND CONCENTRATIONS WHICH VARY ','SEASONALLY (',A5,') *'/)",
                    isect, un)
        o += fwrite("(40X,4(A6,9X)/20X,40('- ')/)", *_SEASON)
        o += fwrite("(38X,4(E10.5,5X))", *[b[k, isect] for k in range(1, 5)])
    elif f == "MONTH":
        e.header(u)
        o += fwrite("(/33X,'* SECT',I1,' BACKGROUND CONCENTRATIONS WHICH VARY ','MONTHLY (',A5,') *'/)", isect, un)
        o += fwrite("(7X,'JANUARY  FEBRUARY   MARCH     APRIL      MAY       ','JUNE      JULY     AUGUST   "
                    "SEPTEMBER  OCTOBER  NOVEMBER  ','DECEMBER'/)")
        o += fwrite(f9013)
        o += fwrite("(5X,12(E9.3,1X))", *[b[k, isect] for k in range(1, 13)])
    elif f == "HROFDY":
        e.header(u)
        o += fwrite("(/20X,'* SECT',I1,' BACKGROUND CONCENTRATIONS WHICH VARY ','FOR EACH HOUR OF THE DAY (',A5,"
                    "') *'/)", isect, un)
        o += fwrite(f9012)
        o += fwrite(f9013)
        o += pares(f9014, 0)
    elif f == "SEASHR":
        e.header(u)
        o += fwrite("(/15X,'* SECT',I1,' BACKGROUND CONCENTRATIONS WHICH VARY',' SEASONALLY AND DIURNALLY (SEASHR)"
                    " (',A5,') *'/)", isect, un)
        o += fwrite(f9012)
        o += fwrite(f9013)
        for i1 in range(1, 5):
            o += fwrite("(59X,'SEASON = ',A6)", _SEASON[i1 - 1])
            o += pares(f9014, (i1 - 1) * 24)
    elif f in ("HRDOW", "HRDOW7"):
        e.header(u)
        o += fwrite("(/11X,'* SECT',I1,' BACKGROUND CONCENTRATIONS WHICH VARY',' DIURNALLY AND BY DAY OF WEEK (%s)',"
                    "' (',A5,') *'/)" % f, isect, un)
        o += fwrite(f99012)
        o += fwrite(f99013)
        for i1, d in enumerate(_DOW if f == "HRDOW" else _DOW7, 1):
            o += fwrite("(46X,'DAY OF WEEK = ',A8)", d)
            o += pares(f99014, (i1 - 1) * 24)
    elif f in ("SHRDOW", "SHRDOW7"):
        e.header(u)
        o += fwrite("(/9X,'* SECT',I1,' BACKGROUND CONCENTRATIONS WHICH VARY',' SEASONALLY, DIURNALLY AND BY DAY OF"
                    " WEEK (%s)',' (',A5,') *'/)" % f, isect, un)
        o += fwrite(f99012)
        o += fwrite(f99013)
        for i1, d in enumerate(_DOW if f == "SHRDOW" else _DOW7, 1):
            for i2 in range(1, 5):
                o += fwrite("(46X,'SEASON = ',A6,';  DAY OF WEEK = ',A8)", _SEASON[i2 - 1], d)
                o += pares(f99014, (i2 - 1) * 24 + (i1 - 1) * 96)
    elif f in ("MHRDOW", "MHRDOW7"):
        for i1, d in enumerate(_DOW if f == "MHRDOW" else _DOW7, 1):
            e.header(u)
            o += fwrite("(/10X,'* SECT',I1,' BACKGROUND CONCENTRATIONS WHICH VARY',' MONTHLY, DIURNALLY AND BY DAY OF"
                        " WEEK (%s)',' (',A5,') *'/)" % f, isect, un)
            o += fwrite(f99012)
            o += fwrite(f99013)
            for i2 in range(1, 13):
                o += fwrite("(46X,'MONTH = ',A9,';  DAY OF WEEK = ',A8)", _MONTHS[i2 - 1], d)
                o += pares(f99014, (i2 - 1) * 24 + (i1 - 1) * 288)
            e.w(u, o)
            o = []
    e.w(u, o)


_SEASON = ("WINTER", "SPRING", "SUMMER", " FALL ")
_DOW = ("WEEKDAY ", "SATURDAY", "SUNDAY  ")
_DOW7 = ("MONDAY  ", "TUESDAY ", "WEDNESDY", "THURSDAY", "FRIDAY  ", "SATURDAY", "SUNDAY  ")
_MONTHS = ("JANUARY  ", "FEBRUARY ", "MARCH    ", "APRIL    ", "MAY      ", "JUNE     ", "JULY     ",
           "AUGUST   ", "SEPTEMBER", "OCTOBER  ", "NOVEMBER ", "DECEMBER ")


def _comunes(e, i):
    urb = "YES" if e.URBSRC[i] == "Y" else "NO"
    aft = "YES" if e.AFTSRC[i] == "Y" else "NO"
    cnpd = "METH2" if e.L_METHOD2[i] else fx(fwrite("(I4,1X)", int(e.INPD[i]))[0], 5)
    cazs = "    FLAT" if e.L_FLATSRC[i] else fwrite("(F8.1)", e.AZS[i])[0]
    cq = "HRLYSIG" if (e.QFLAG[i] == "HOURLY" and e.L_HRLYSIG[i]) else e.QFLAG[i]
    return fx(urb, 3), fx(aft, 3), cnpd, cazs, fx(cq, 7)


def _edificio(e, i):
    if e.NSEC > 0:
        for j in range(1, e.NSEC + 1):
            if e.ADSBH[j, i] != 0.0 and e.ADSBW[j, i] != 0.0 and e.ADSBL[j, i] != 0.0:
                return "YES"
    return "NO"


def prtsrc(e):
    """PRTSRC: tablas de datos de las fuentes, grupos, edificios y factores de emisión."""
    u = e.IOUNIT
    o = []
    iqun = " (GRAMS/SEC)" if (e.ISSTAT[8] == 0 and e.ISSTAT[17] == 0 and e.ISSTAT[18] == 0) else "(USER UNITS)"

    def cabecera(fmt, *items):
        e.w(u, o)
        o.clear()
        e.header(u)
        o.extend(fwrite(fmt, *items))

    indc = 0
    for i in range(1, e.NUMSRC + 1):
        if e.SRCTYP[i][:5] == "POINT":
            indc += 1
            urb, _aft, cnpd, cazs, _cq = _comunes(e, i)
            blding = _edificio(e, i)
            cap = {"POINTCAP": "CAP", "POINTHOR": "HOR"}.get(e.SRCTYP[i], " NO")
            if (indc - 1) % 40 == 0:
                cabecera("(//50X,'*** POINT SOURCE DATA ***'//15X,'NUMBER EMISSION RATE',20X,'BASE     STACK   STACK',"
                         "4X,'STACK     STACK    BLDG   URBAN  CAP/  EMIS RATE',/3X,'SOURCE',7X,'PART. ',A12,5X,'X',8X,"
                         "'Y',6X,'ELEV.    ','HEIGHT  TEMP.   EXIT VEL. DIAMETER',2X,'EXISTS SOURCE ','HOR   SCALAR',"
                         "/4X,' ID         CATS.              ',1X,2('(METERS) (METERS) '),'(DEG.K) ',' (M/SEC) ',1X,"
                         "'(METERS)',22X,'VARY BY'/65(' -')/)", iqun)
            o.extend(fwrite("(1X,A12,2X,A5,2X,E11.5,2F10.1,A8,4F9.2,4X,A3,5X,A3,2x,A3,2X,A7)", fx(e.SRCID[i], 12),
                            cnpd, e.AQS[i], e.AXS[i], e.AYS[i], cazs, e.AHS[i], e.ATS[i], e.AVS[i], e.ADS[i],
                            fx(blding, 3), urb, cap, fx(e.QFLAG[i], 7)))
    indc = 0
    for i in range(1, e.NUMSRC + 1):
        if e.SRCTYP[i] == "VOLUME":
            indc += 1
            urb, aft, cnpd, cazs, cq = _comunes(e, i)
            if (indc - 1) % 40 == 0:
                cabecera("(//50X,'*** VOLUME SOURCE DATA ***'//15X,'NUMBER EMISSION RATE',20X,'BASE    RELEASE    INIT.',"
                         "4X,'INIT.   URBAN  EMISSION RATE   AIRCRAFT',/3X,'SOURCE',7X,'PART. ',A12,5X,'X',8X,'Y',6X,"
                         "'ELEV.   ','HEIGHT      SY       SZ     SOURCE  SCALAR VARY',/4X,' ID         CATS.              ',"
                         "1X,3('(METERS) (METERS) '),13X,'BY'/61(' -')/)", iqun)
            o.extend(fwrite("(1X,A12,2X,A5,2X,E11.5,2F10.1,A8,F9.2,1X,F8.2,1X,F8.2,5X,A3,3X,A7,10X,A3)",
                            fx(e.SRCID[i], 12), cnpd, e.AQS[i], e.AXS[i], e.AYS[i], cazs, e.AHS[i], e.ASYINI[i],
                            e.ASZINI[i], urb, cq, aft))
    indc = 0
    for i in range(1, e.NUMSRC + 1):
        if e.SRCTYP[i] == "AREA":
            indc += 1
            urb, aft, cnpd, cazs, cq = _comunes(e, i)
            if (indc - 1) % 40 == 0:
                cabecera("(//50X,'*** AREA SOURCE DATA ***'//15X,'NUMBER EMISSION RATE',2X,'COORD (SW CORNER)',2X,"
                         "'BASE     RELEASE  X-DIM     Y-DIM    ORIENT.',4X,'INIT.   URBAN  ','EMISSION RATE  AIRCRAFT',"
                         "/3X,'SOURCE',7X,'PART. ',A11,7X,'X',8X,'Y',6X,'ELEV.    ','HEIGHT  OF AREA   OF AREA   OF AREA"
                         "     SZ     SOURCE ',' SCALAR VARY',/4X,' ID         CATS.   /METER**2)  ',1X,2('(METERS) "
                         "(METERS) '),2('(METERS)',2X),' (DEG.)  (METERS)',14X,'BY'/66(' -')/)", iqun)
            o.extend(fwrite("(1X,A12,2X,A5,2X,E11.5,2F10.1,A8,F9.2,3(1X,F9.2),1X,F8.2,5X,A3,3X,A7,10X,A3)",
                            fx(e.SRCID[i], 12), cnpd, e.AQS[i], e.AXS[i], e.AYS[i], cazs, e.AHS[i], e.AXINIT[i],
                            e.AYINIT[i], e.AANGLE[i], e.ASZINI[i], urb, cq, aft))
    indc = 0
    for i in range(1, e.NUMSRC + 1):
        if e.SRCTYP[i] == "AREACIRC":
            indc += 1
            urb, aft, cnpd, cazs, cq = _comunes(e, i)
            if (indc - 1) % 40 == 0:
                cabecera("(//48X,'*** AREACIRC SOURCE DATA ***'//15X,'NUMBER EMISSION RATE',4X,'CENTER OF AREA',3X,"
                         "'BASE     RELEASE  RADIUS     NUMBER     INIT.',3X,'URBAN  EMISSION RATE  AIRCRAFT',/3X,"
                         "'SOURCE',7X,'PART. ',A11,7X,'X',8X,'Y',6X,'ELEV.    ','HEIGHT   OF AREA   OF VERTS.    SZ  "
                         "   SOURCE  SCALAR VARY',/4X,' ID         CATS.   /METER**2)  ',1X,2('(METERS) (METERS) '),"
                         "21X,'(METERS)',14X,'BY'/63(' -')/)", iqun)
            o.extend(fwrite("(1X,A12,2X,A5,2X,E11.5,2F10.1,A8,F9.2,2X,F9.2,4X,I4,4X,F8.2,5X,A3,3X,A7,10X,A3)",
                            fx(e.SRCID[i], 12), cnpd, e.AQS[i], e.AXS[i], e.AYS[i], cazs, e.AHS[i], e.RADIUS[i],
                            int(e.NVERTS[i]), e.ASZINI[i], urb, cq, aft))
    indc = 0
    for i in range(1, e.NUMSRC + 1):
        if e.SRCTYP[i] == "AREAPOLY":
            indc += 1
            urb, aft, cnpd, cazs, cq = _comunes(e, i)
            if (indc - 1) % 40 == 0:
                cabecera("(//48X,'*** AREAPOLY SOURCE DATA ***'//15X,'NUMBER EMISSION RATE',3X,'LOCATION OF AREA',2X,"
                         "'BASE     RELEASE  NUMBER      INIT.',3X,'URBAN  EMISSION RATE','    AIRCRAFT',/3X,'SOURCE',"
                         "7X,'PART. ',A11,7X,'X',8X,'Y',6X,'ELEV.    ','HEIGHT  OF VERTS.     SZ     SOURCE  SCALAR "
                         "VARY',/4X,' ID         CATS.   /METER**2)  ',1X,2('(METERS) (METERS) '),11X,'(METERS)       "
                         "       BY'/63(' -')/)", iqun)
            o.extend(fwrite("(1X,A12,2X,A5,2X,E11.5,2F10.1,A8,F9.2,4X,I4,5X,F8.2,5X,A3,3X,A7,10X,A3)",
                            fx(e.SRCID[i], 12), cnpd, e.AQS[i], e.AXS[i], e.AYS[i], cazs, e.AHS[i], int(e.NVERTS[i]),
                            e.ASZINI[i], urb, cq, aft))
    indc = 0
    for i in range(1, e.NUMSRC + 1):
        if e.SRCTYP[i] == "LINE":
            indc += 1
            urb, _aft, cnpd, cazs, cq = _comunes(e, i)
            if (indc - 1) % 40 == 0:
                cabecera("(//50X,'*** LINE SOURCE DATA ***'//15X,'NUMBER EMISSION RATE',5X,'FIRST COORD',8X,"
                         "'SECOND COORD',5X,'BASE    RELEASE    WIDTH    INIT.   URBAN  EMISSION RATE',/3X,"
                         "'SOURCE',7X,'PART. ',A11,8X,'X',7X,'Y',11X,'X',7X,'Y',6X,'ELEV.   ',"
                         "'HEIGHT    OF LINE    SZ     SOURCE SCALAR VARY',/4X,' ID         CATS.   /METER**2)  ',"
                         "1X,'(METERS) (METERS) ',2X,'(METERS) (METERS) ',2('(METERS)',1X),1X,'(METERS) (METERS)',"
                         "13X,'BY'/66(' -')/)", iqun)
            o.extend(fwrite("(1X,A12,2X,A5,2X,E11.5,4F10.1,A8,F9.2,1X,F9.2,1X,F8.2,5X,A3,3X,A7)",
                            fx(e.SRCID[i], 12), cnpd, e.AQS[i], e.AXS1[i], e.AYS1[i], e.AXS2[i], e.AYS2[i], cazs,
                            e.AHS[i], e.AWIDTH[i], e.ASZINI[i], urb, cq))
    indc = 0
    for i in range(1, e.NUMSRC + 1):
        if e.SRCTYP[i] in ("RLINE", "RLINEXT"):
            indc += 1
            urb, _aft, cnpd, cazs, _cq = _comunes(e, i)
            if (indc - 1) % 40 == 0:
                if e.RL.RLMOVESCONV:
                    # (el original no escribe aquí la cabecera de página)
                    o.extend(fwrite(_F9109))
                else:
                    cabecera(_F9110, iqun)
            rl = e.RL
            o.extend(fwrite(_F9111, fx(e.SRCID[i], 12), cnpd, rl.S_QEMIS[i], rl.S_XSB[i], rl.S_YSB[i], rl.S_ZSB[i],
                            rl.S_XSE[i], rl.S_YSE[i], rl.S_ZSE[i], cazs, rl.S_DCL[i], rl.S_INIT_SIGMAZ[i],
                            rl.S_WIDTH[i], urb, fx(e.QFLAG[i], 7)))
    indc = 0
    for i in range(1, e.NUMSRC + 1):
        if e.SRCTYP[i] in ("RLINE", "RLINEXT") and e.RL.S_HTWALL[i] > 0.0:
            indc += 1
            if (indc - 1) % 40 == 0:
                o.extend(fwrite(_F9112))
            rl = e.RL
            o.extend(fwrite(_F9113, fx(e.SRCID[i], 12), fx(rl.S_BARID[i], 12), rl.S_HTWALL[i], rl.S_DCLWALL[i],
                            fx(rl.S_BARID2[i], 12), rl.S_HTWALL2[i], rl.S_DCLWALL2[i]))
    if e.VBARSET:
        indc = 0
        for i in range(1, e.NUMSRC + 1):
            if e.SRCTYP[i] in ("RLINE", "RLINEXT"):
                rl = e.RL
                if rl.VB_HT[1, i] > 0.0 or rl.VB_HT[2, i] > 0.0:
                    indc += 1
                    if (indc - 1) % 40 == 0:
                        o.extend(fwrite(_F8112))
                    o.extend(fwrite(_F8113, fx(e.SRCID[i], 12), *[getattr(rl, "VB_" + c)[k, i] for k in (1, 2)
                                                                   for c in ("HT", "WT", "DCL", "LAI", "LM", "WAKE")]))
    indc = 0
    for i in range(1, e.NUMSRC + 1):
        if e.SRCTYP[i] in ("RLINE", "RLINEXT") and e.RL.S_DEPTH[i] != 0.0:
            indc += 1
            if (indc - 1) % 40 == 0:
                o.extend(fwrite(_F9114))
            rl = e.RL
            o.extend(fwrite(_F9115, fx(e.SRCID[i], 12), rl.S_DEPTH[i], rl.S_WTOP[i], rl.S_WBOTTOM[i]))
    from . import fuente_foso
    fuente_foso.prtsrc_pit(e, o, cabecera, iqun)
    # BUOYLINE: todas las líneas se escriben con la primera fuente BUOYLINE, que es la que da URB, CNPD y
    # FLAT (como en el original); la cota sale de cada línea
    indc = 0
    for i in range(1, e.NUMSRC + 1):
        if e.SRCTYP[i] == "BUOYLINE":
            b = e.BUOY
            urb, _aft, cnpd, _cazs, _cq = _comunes(e, i)
            for nbl in range(1, b.NBLTOTAL + 1):
                indc += 1
                cazs = "    FLAT" if e.L_FLATSRC[i] else fwrite("(F8.1)", b.P_ELEV[nbl])[0]
                if (indc - 1) % 40 == 0:
                    cabecera(_F9086, iqun)
                o.extend(fwrite(_F9087, fx(b.P_SRCID[nbl], 12), cnpd, b.P_BLQS[nbl], b.P_XBEG[nbl], b.P_YBEG[nbl],
                                b.P_XEND[nbl], b.P_YEND[nbl], cazs, b.P_BLHS[nbl], urb,
                                fx(e.QFLAG[int(b.P_ISRCNUM[nbl])], 7)))
            o.extend(fwrite(_F9088))
            for k in range(1, b.NUMBLAVGINP + 1):
                o.extend(fwrite(_F9089, fx(b.BLAVGINP_GRPID[k], 8), b.BLAVGINP_LLEN[k], b.BLAVGINP_BHGT[k],
                                b.BLAVGINP_BWID[k], b.BLAVGINP_LWID[k], b.BLAVGINP_BSEP[k], b.BLAVGINP_FPRM[k]))
            break
    # grupos de fuentes
    if not e.PSDCREDIT:
        indc = 0
        for j in range(1, e.NUMGRP + 1):
            ids = [e.SRCID[k] for k in range(1, e.NUMSRC + 1) if e.IGROUP[k, j] == 1]
            if e.GRP_BACK[j]:
                ids.append("BACKGROUND")
            ingrp = len(ids)
            nl = 1 + int((ingrp - 1) / 8)
            for k in range(1, nl + 1):
                indc += 1
                if (indc - 1) % 20 == 0:
                    cabecera("(//43X,'*** SOURCE IDs DEFINING SOURCE GROUPS ***'//1X,'SRCGROUP ID',46X,'SOURCE IDs'/"
                             "1X,'-----------',46X,'----------'/)")
                if k == 1 and k == nl:
                    sel = ids[0:ingrp]
                elif k == 1:
                    sel = ids[0:8 * k]
                elif k == nl:
                    sel = ids[8 * (k - 1):ingrp]
                else:
                    sel = ids[8 * (k - 1):8 * k]
                sel = [fx(s, 12) for s in sel]
                if k == 1:
                    o.extend(fwrite("(/2X,A8,2X,8(1X,A12,','))", fx(e.GRPID[j], 8), *sel))
                else:
                    o.extend(fwrite("(/12X,8(1X,A12,','))", *sel))
    # grupos OLMGROUP y PSDGROUP
    for nj, ids_de, nombres, fcab in (
            (e.NUMOLM, e.IGRP_OLM, e.OLMID,
             "(//41X,'*** SOURCE IDs DEFINING OLM SOURCE GROUPS ***'/41X,'***        FOR COMBINING PLUMES"
             "           ***'//1X,'OLMGROUP ID',47X,'SOURCE IDs'/1X,'-----------',47X,'----------'/)"),
            (e.NUMPSD, e.IGRP_PSD, e.PSDID,
             "(/41X,'*** SOURCE IDs DEFINING PSD SOURCE GROUPS ***'/41X,'***      FOR PVMRM PSDCREDIT OPTION"
             "       ***'//1X,'PSDGROUP ID',47X,'SOURCE IDs'/)")):
        indc = 0
        for j in range(1, nj + 1):
            ids = [fx(e.SRCID[k], 12) for k in range(1, e.NUMSRC + 1) if ids_de[k, j] == 1]
            ingrp = len(ids)
            nl = 1 + int((ingrp - 1) / 8)
            for k in range(1, nl + 1):
                indc += 1
                if (indc - 1) % 20 == 0:
                    cabecera(fcab)
                if k == 1:
                    sel = ids[0:ingrp] if k == nl else ids[0:8 * k]
                    o.extend(fwrite("(/2X,A8,2X,8(1X,A12,','))", fx(nombres[j], 8), *sel))
                else:
                    sel = ids[8 * (k - 1):ingrp] if k == nl else ids[8 * (k - 1):8 * k]
                    o.extend(fwrite("(/12X,8(1X,A12,','))", *sel))
    # zonas urbanas y sus fuentes
    indc = 0
    for j in range(1, e.NUMURB + 1):
        ids = [fx(e.SRCID[k], 12) for k in range(1, e.NUMSRC + 1) if e.IURBGRP[k, j] == 1]
        ingrp = len(ids)
        nl = 1 + int((ingrp - 1) / 8)
        for k in range(1, nl + 1):
            indc += 1
            if (indc - 1) % 20 == 0:
                cabecera("(//42X,'*** SOURCE IDs DEFINED AS URBAN SOURCES ***'//2X,'URBAN ID',3X,'URBAN POP',36X,"
                         "'SOURCE IDs'/2X,'--------',3X,'---------',36X,'----------'/)")
            if k == 1:
                sel = ids[0:ingrp] if k == nl else ids[0:8 * k]
                o.extend(fwrite("(/2X,A8,3X,F9.0,2X,7(1X,A12,','))", fx(e.URBID[j], 8), e.URBPOP[j], *sel))
            else:
                sel = ids[8 * (k - 1):ingrp] if k == nl else ids[8 * (k - 1):8 * k]
                o.extend(fwrite("(/12X,8(1X,A12,','))", *sel))
    # razones NO2/NOx en chimenea
    if e.OLM or e.PVMRM or e.RUNTTRM or e.GRSM:
        indc = 0
        for i in range(1, e.NUMSRC + 1, 4):
            indc += 1
            if (indc - 1) % 40 == 0:
                cabecera("(//39X,'*** IN-STACK NO2 RATIOS FOR ***'/39X,'*** OLM/PVMRM/GRSM OPTIONS ***'//"
                         "/1X,4('SOURCE_ID',4X,'NO2_RATIO',6X)/)")
            items = []
            for j in range(i, min(i + 3, e.NUMSRC) + 1):
                items += [fx(e.SRCID[j], 12), e.ANO2_RATIO[j]]
            o.extend(fwrite("(1X,4(A12,2X,F7.3,7X))", *items))
    # datos de deposición de partículas (método 1 o 2) o de gases (el original deja en NPD el de la
    # última fuente)
    indc = 0
    cab_dep = "(/48X,'*** SOURCE PARTICULATE/GAS DATA ***'//)"
    f_fuente = "(//8X,'*** SOURCE ID = ',A12,'; SOURCE TYPE = ',A8,' ***')"
    f_lista = "4(:10X,10(:F9.5,', ')/))"
    for i in range(1, e.NUMSRC + 1):
        npd = int(e.INPD[i])
        e.NPD = npd
        if npd != 0 or e.LWGAS or (e.LDGAS and not e.LUSERVD):
            indc += 1
            if (indc - 1) % 3 == 0:
                cabecera(cab_dep)
            o.extend(fwrite(f_fuente, fx(e.SRCID[i], 12), fx(e.SRCTYP[i], 8)))
        if npd != 0 and not e.L_METHOD2[i]:
            o.extend(fwrite("(/8X,'MASS FRACTION ='/" + f_lista, *[e.APHI[j, i] for j in range(1, npd + 1)]))
        elif npd != 0:
            o.extend(fwrite("(/8X,'FINE PARTICLE MASS FRACTION ='/" + f_lista,
                            *[e.FINEMASS[i] for _j in range(1, npd + 1)]))
        if npd != 0:
            o.extend(fwrite("(/8X,'PARTICLE DIAMETER (MICRONS) ='/" + f_lista,
                            *[e.APDIAM[j, i] for j in range(1, npd + 1)]))
            o.extend(fwrite("(/8X,'PARTICLE DENSITY (G/CM**3)  ='/" + f_lista,
                            *[e.APDENS[j, i] for j in range(1, npd + 1)]))
        elif (e.LWGAS or (e.LDGAS and not e.LUSERVD)) and e.LDGAS:
            o.extend(fwrite("(/10X,'DIFF IN AIR (M**2/SEC)     =',2X,E9.2)", e.PDIFF[i]))
            o.extend(fwrite("(/10X,'DIFF IN WATER (M**2/SEC)   =',2X,E9.2)", e.PDIFFW[i]))
            o.extend(fwrite("(/10X,'LEAF LIPID RESIST (SEC/M)  =',2X,E9.2)", e.RCLI[i]))
            o.extend(fwrite("(/10X,'HENRY`S LAW COEFFICIENT    =',2X,E9.2)", e.HENRY[i]))
    # dimensiones de edificios por dirección
    indc = 0
    for i in range(1, e.NUMSRC + 1):
        if _edificio(e, i) == "YES":
            indc += 1
            if (indc - 1) % 4 == 0:
                cabecera("(/42X,'*** DIRECTION SPECIFIC BUILDING DIMENSIONS ***'/)")
            items = []
            for j in range(1, e.NSEC + 1):
                items += [j, abs(e.ADSBH[j, i]), e.ADSBW[j, i], e.ADSBL[j, i], e.ADSXADJ[j, i], e.ADSYADJ[j, i]]
            o.extend(fwrite("(/' SOURCE ID: ',A12,/,2('  IFV    BH      BW      BL     XADJ    YADJ',3X),/,"
                            "18(2(2X,I3,5(F7.1,','),2X)/))", fx(e.SRCID[i], 12), *items))
    # factores de emisión variables
    _factores(e, o, cabecera)
    e.w(u, o)


def _factores(e, o, cabecera):
    q = e.QFACT
    f9009 = "(/' SOURCE ID = ',A12,' ; SOURCE TYPE = ',A8,' :')"
    f99009 = "(' SOURCE ID = ',A12,' ; SOURCE TYPE = ',A8,' :')"
    f9014 = "(4(5X,6(I3,3X,E10.5,4X)/))"
    f99014 = "(2(3X,8(I2,2X,E9.4,3X)/),3X,8(I2,2X,E9.4,3X))"
    f9012 = "(5X,6('HOUR    SCALAR',6X))"
    f99012 = "(2X,8('HOUR   SCALAR',3X))"
    f9013 = "(1X,65('- ')/)"
    f99013 = "(1X,65('- '))"
    ns = e.NUMSRC

    def idt(i):
        return fx(e.SRCID[i], 12), fx(e.SRCTYP[i], 8)

    indc = 0
    for i in range(1, ns + 1):
        if e.QFLAG[i] == "SEASON":
            indc += 1
            if (indc - 1) % 6 == 0:
                cabecera("(/39X,'* SOURCE EMISSION RATE SCALARS WHICH VARY ','SEASONALLY *'/)")
                o.extend(fwrite("(40X,4(A6,9X)/20X,40('- ')/)", *_SEASON))
            o.extend(fwrite("(/10X,' SOURCE ID = ',A12,' ;  SOURCE TYPE = ',A8,' :')", *idt(i)))
            o.extend(fwrite("(38X,4(E10.5,5X))", *[q[k, i] for k in range(1, 5)]))
    indc = 0
    for i in range(1, ns + 1):
        if e.QFLAG[i] == "MONTH":
            indc += 1
            if (indc - 1) % 6 == 0:
                cabecera("(/41X,'* SOURCE EMISSION RATE SCALARS WHICH VARY MONTHLY *',/)")
                o.extend(fwrite("(7X,'JANUARY  FEBRUARY   MARCH     APRIL      MAY       ','JUNE      JULY     AUGUST"
                                "   SEPTEMBER  OCTOBER  NOVEMBER  ','DECEMBER'/)"))
                o.extend(fwrite(f9013))
            o.extend(fwrite(f9009, *idt(i)))
            o.extend(fwrite("(5X,12(E9.3,1X))", *[q[k, i] for k in range(1, 13)]))
    indc = 0
    for i in range(1, ns + 1):
        if e.QFLAG[i] == "HROFDY":
            indc += 1
            if (indc - 1) % 5 == 0:
                cabecera("(/28X,'* SOURCE EMISSION RATE SCALARS WHICH VARY FOR EACH',' HOUR OF THE DAY *'/)")
                o.extend(fwrite(f9012))
                o.extend(fwrite(f9013))
            o.extend(fwrite(f9009, *idt(i)))
            items = []
            for k in range(1, 25):
                items += [k, q[k, i]]
            o.extend(fwrite(f9014, *items))
    indc = 0
    for i in range(1, ns + 1):
        if e.QFLAG[i] == "WSPEED":
            indc += 1
            if (indc - 1) % 3 == 0:
                cabecera("(/25X,'* SOURCE EMISSION RATE SCALARS WHICH VARY WITH',' WIND SPEED *'/)")
                o.extend(fwrite(f9013))
            o.extend(fwrite(f9009, *idt(i)))
            o.extend(fwrite("(/26X,6('   WIND SPEED')/26X,6('   CATEGORY',I2))", *range(1, 7)))
            o.extend(fwrite("(26X,6(1X,E12.5))", *[q[k, i] for k in range(1, 7)]))
    for i in range(1, ns + 1):
        if e.QFLAG[i] == "SEASHR":
            cabecera("(/22X,'* SOURCE EMISSION RATE SCALARS WHICH VARY',' SEASONALLY AND DIURNALLY (SEASHR) *'/)")
            o.extend(fwrite(f9012))
            o.extend(fwrite(f9013))
            o.extend(fwrite(f9009, *idt(i)))
            for i1 in range(1, 5):
                ifr = (i1 - 1) * 24
                o.extend(fwrite("(59X,'SEASON = ',A6)", _SEASON[i1 - 1]))
                items = []
                for k in range(1, 25):
                    items += [k, q[k + ifr, i]]
                o.extend(fwrite(f9014, *items))
    for clave, tit, dias in (("HRDOW", "(/19X,'* SOURCE EMISSION RATE SCALARS WHICH VARY',' DIURNALLY AND BY DAY OF "
                                       "WEEK (HRDOW) *'/)", _DOW),
                             ("HRDOW7", "(/19X,'* SOURCE EMISSION RATE SCALARS WHICH VARY',' DIURNALLY AND BY DAY OF "
                                        "WEEK (HRDOW7) *'/)", _DOW7)):
        for i in range(1, ns + 1):
            if e.QFLAG[i] == clave:
                cabecera(tit)
                o.extend(fwrite(f99009, *idt(i)))
                o.extend(fwrite(f99012))
                o.extend(fwrite(f99013))
                for i1, d in enumerate(dias, 1):
                    idw = (i1 - 1) * 24
                    o.extend(fwrite("(46X,'DAY OF WEEK = ',A8)", d))
                    items = []
                    for k in range(1, 25):
                        items += [k, q[k + idw, i]]
                    o.extend(fwrite(f99014, *items))
    for clave, tit, dias in (("SHRDOW", "(/17X,'* SOURCE EMISSION RATE SCALARS WHICH VARY',' SEASONALLY, DIURNALLY AND"
                                        " BY DAY OF WEEK (SHRDOW) *'/)", _DOW),
                             ("SHRDOW7", "(/17X,'* SOURCE EMISSION RATE SCALARS WHICH VARY',' SEASONALLY, DIURNALLY "
                                         "AND BY DAY OF WEEK (SHRDOW7) *'/)", _DOW7)):
        for i in range(1, ns + 1):
            if e.QFLAG[i] == clave:
                cabecera(tit)
                o.extend(fwrite(f99009, *idt(i)))
                o.extend(fwrite(f99012))
                o.extend(fwrite(f99013))
                for i1, d in enumerate(dias, 1):
                    idw = (i1 - 1) * 96
                    for i2 in range(1, 5):
                        ifr = (i2 - 1) * 24
                        o.extend(fwrite("(46X,'SEASON = ',A6,';  DAY OF WEEK = ',A8)", _SEASON[i2 - 1], d))
                        items = []
                        for k in range(1, 25):
                            items += [k, q[k + ifr + idw, i]]
                        o.extend(fwrite(f99014, *items))
    for clave, tit, dias in (("MHRDOW", "(/18X,'* SOURCE EMISSION RATE SCALARS WHICH VARY',' MONTHLY, DIURNALLY AND BY"
                                        " DAY OF WEEK (MHRDOW) *'/)", _DOW),
                             ("MHRDOW7", "(/18X,'* SOURCE EMISSION RATE SCALARS WHICH VARY',' MONTHLY, DIURNALLY AND "
                                         "BY DAY OF WEEK (MHRDOW7) *'/)", _DOW7)):
        for i in range(1, ns + 1):
            if e.QFLAG[i] == clave:
                for i1, d in enumerate(dias, 1):
                    cabecera(tit)
                    o.extend(fwrite(f99009, *idt(i)))
                    o.extend(fwrite(f99012))
                    o.extend(fwrite(f99013))
                    idw = (i1 - 1) * 288
                    for i2 in range(1, 13):
                        ifr = (i2 - 1) * 24
                        o.extend(fwrite("(46X,'MONTH = ',A9,';  DAY OF WEEK = ',A8)", _MONTHS[i2 - 1], d))
                        items = []
                        for k in range(1, 25):
                            items += [k, q[k + ifr + idw, i]]
                        o.extend(fwrite(f99014, *items))


def _tabla_red(e, o, cabecera, i, titulo, valores):
    """Tabla de cotas, alturas de colina o de receptor de una red (9 columnas x 40 filas)."""
    ncpp, nrpp = 9, 40
    nx_, ny_ = int(e.NUMXPT[i]), int(e.NUMYPT[i])
    nppx = 1 + int((nx_ - 1) / ncpp)
    nppy = 1 + int((ny_ - 1) / nrpp)
    cart = e.NTTYP[i] == "GRIDCART"
    for nx in range(1, nppx + 1):
        for ny in range(1, nppy + 1):
            cabecera("(/34X,'*** NETWORK ID: ',A8,' ;  NETWORK TYPE: ',A8,' ***')", fx(e.NTID[i], 8),
                     fx(e.NTTYP[i], 8))
            o.extend(fwrite(titulo))
            jhi = nx_ if nx == nppx else ncpp * nx
            xs = [e.XCOORD[j, i] for j in range(1 + ncpp * (nx - 1), jhi + 1)]
            if cart:
                o.extend(fwrite("(3X,' Y-COORD  |',48X,'X-COORD (METERS)')"))
                o.extend(fwrite("(3X,' (METERS) |',1X,9(1X,F12.2,:))", *xs))
            else:
                o.extend(fwrite("(3X,'DIRECTION |',48X,'DISTANCE (METERS)')"))
                o.extend(fwrite("(3X,'(DEGREES) |',1X,9(1X,F12.2,:))", *xs))
            o.extend(fwrite("(66(' -')/)"))
            khi = ny_ if ny == nppy else nrpp * ny
            for k in range(1 + nrpp * (ny - 1), khi + 1):
                if cart:
                    indz = int(e.NETEND[i]) - k * nx_ + 1
                    ycoval = e.YCOORD[ny_ - k + 1, i]
                else:
                    indz = int(e.NETSTA[i]) + (k - 1) * nx_
                    ycoval = e.YCOORD[k, i]
                vals = [valores[indz + j - 1] for j in range(1 + ncpp * (nx - 1), jhi + 1)]
                o.extend(fwrite("(2X,F10.2,1X,'|',1X,9(1X,F12.2,:))", ycoval, *vals))


def prtrec(e):
    """PRTREC: resumen de los receptores (redes y receptores discretos)."""
    u = e.IOUNIT
    o = []

    def cabecera(fmt, *items):
        e.w(u, o)
        o.clear()
        e.header(u)
        o.extend(fwrite(fmt, *items))

    f9040 = "(100(5X,10(F10.1,',')/))"
    for i in range(1, e.INNET + 1):
        cabecera("(/40X,'*** GRIDDED RECEPTOR NETWORK SUMMARY ***')")
        o.extend(fwrite("(/34X,'*** NETWORK ID: ',A8,' ;  NETWORK TYPE: ',A8,' ***')", fx(e.NTID[i], 8),
                        fx(e.NTTYP[i], 8)))
        if e.NTTYP[i] == "GRIDCART":
            o.extend(fwrite("(/42X,'*** X-COORDINATES OF GRID ***'/52X,'(METERS)'/)"))
        else:
            o.extend(fwrite("(/42X,'*** ORIGIN FOR POLAR NETWORK ***'/,32X,'X-ORIG =',F10.2,' ;   Y-ORIG = ',F10.2,"
                            "'  (METERS)')", e.XORIG[i], e.YORIG[i]))
            o.extend(fwrite("(/42X,'*** DISTANCE RANGES OF NETWORK ***'/52X,'(METERS)'/)"))
        o.extend(fwrite(f9040, *[e.XCOORD[j, i] for j in range(1, int(e.NUMXPT[i]) + 1)]))
        if e.NTTYP[i] == "GRIDCART":
            o.extend(fwrite("(/42X,'*** Y-COORDINATES OF GRID *** ',/52X,'(METERS)'/)"))
        else:
            o.extend(fwrite("(/42X,'*** DIRECTION RADIALS OF NETWORK *** ',/52X,'(DEGREES)'/)"))
        o.extend(fwrite(f9040, *[e.YCOORD[j, i] for j in range(1, int(e.NUMYPT[i]) + 1)]))
        if e.ELEV:
            _tabla_red(e, o, cabecera, i, "(/48X,'* ELEVATION HEIGHTS IN METERS *'/)", e.AZELEV)
            _tabla_red(e, o, cabecera, i, "(/48X,'* HILL HEIGHT SCALES IN METERS *'/)", e.AZHILL)
        if e.FLGPOL:
            _tabla_red(e, o, cabecera, i, "(/44X,'* RECEPTOR FLAGPOLE HEIGHTS IN METERS *'/)", e.AZFLAG)
    blanco = " " * 132
    if e.IRSTAT[4] != 0 or e.IRSTAT[8] != 0:
        indc = 0
        buf = blanco
        for i in range(1, e.NUMREC + 1):
            if e.RECTYP[i] == "DC":
                indc += 1
                if (indc - 1) % 90 == 0:
                    cabecera("(/45X,'*** DISCRETE CARTESIAN RECEPTORS ***',/43X,'(X-COORD, Y-COORD, ZELEV, ZHILL, "
                             "ZFLAG)',/45X,'              (METERS)'/)")
                t = fwrite("(4X,' (',4(F9.1,', '),F9.1,'); ')", e.AXR[i], e.AYR[i], e.AZELEV[i], e.AZHILL[i],
                           e.AZFLAG[i])[0].ljust(65)[:65]
                if indc % 2 != 0:
                    buf = t + buf[65:]
                else:
                    buf = buf[:65] + t + buf[130:]
                    o.append(buf)
                    buf = blanco
        if indc % 2 != 0:
            o.append(buf)
    if e.IRSTAT[5] != 0:
        indc = 0
        buf = blanco
        for i in range(1, e.NUMREC + 1):
            if e.RECTYP[i] == "DP":
                indc += 1
                ir = int(e.IREF[i])
                xrms = e.AXR[i] - e.AXS[ir]
                yrms = e.AYR[i] - e.AYS[ir]
                rng = math.sqrt(xrms * xrms + yrms * yrms)
                radial = math.atan2(xrms, yrms) * e.RTODEG
                if radial <= 0.0:
                    radial = radial + 360.0
                if (indc - 1) % 90 == 0:
                    cabecera("(/43X,'      *** DISCRETE POLAR RECEPTORS ***',/43X,' ORIGIN:    (DIST, DIR, ZELEV, "
                             "ZHILL, ZFLAG)',/43X,' SRCID:    (METERS,DEG,METERS,METERS,METERS)'/)")
                t = fwrite("(1X,A12,': (',F9.1,', ',3(F7.1,', '),F7.1,'); ')", fx(e.SRCID[ir], 12), rng, radial,
                           e.AZELEV[i], e.AZHILL[i], e.AZFLAG[i])[0].ljust(65)[:65]
                if indc % 2 != 0:
                    buf = t + buf[65:]
                else:
                    buf = buf[:65] + t + buf[130:]
                    o.append(buf)
                    buf = blanco
        if indc % 2 != 0:
            o.append(buf)
    e.w(u, o)


def chkrec(e):
    """CHKREC: combinaciones fuente-receptor a menos de 1 m (o más allá de MAXDIST)."""
    u = e.IOUNIT
    o = []
    inc = 0
    xsrc = ysrc = 0.0
    xrad = getattr(e, "XRAD", 0.0)
    f9002 = ("(/22X,'* SOURCE-RECEPTOR COMBINATIONS FOR WHICH CALCULATIONS ','MAY NOT BE PERFORMED *'/24X,"
             "'LESS THAN 1.0 METER;',' WITHIN OPENPIT; OR BEYOND 80KM FOR FASTAREA/FASTALL',///30X,'SOURCE',10X,"
             "'- - RECEPTOR LOCATION - -',9X,'DISTANCE',/30X,'  ID  ',10X,'XR (METERS)   YR (METERS)',9X,"
             "'(METERS)',/28X,31('- ')/)")
    axr, ayr = e.AXR, e.AYR
    for isrc in range(1, e.NUMSRC + 1):
        t = e.SRCTYP[isrc]
        if t[:5] == "POINT":
            xrad = 0.0
            xsrc, ysrc = e.AXS[isrc], e.AYS[isrc]
        elif t == "VOLUME":
            xrad = 2.15 * e.ASYINI[isrc]
            xsrc, ysrc = e.AXS[isrc], e.AYS[isrc]
        elif t[:4] == "AREA" or t == "LINE":
            xrad = -1.0
            xsrc, ysrc = e.AXCNTR[isrc], e.AYCNTR[isrc]
        elif t == "OPENPIT":
            from . import fuente_foso
            xrad = -1.0
            xsrc, ysrc = e.AXCNTR[isrc], e.AYCNTR[isrc]
            xvm, yvm = fuente_foso.vertices_pit(e, isrc)
        for irec in range(1, e.NUMREC + 1):
            x = axr[irec] - xsrc
            y = ayr[irec] - ysrc
            dist = math.sqrt(x * x + y * y) - xrad
            if dist < 0.99 or dist > e.MAXDIST:
                inc += 1
                if (inc - 1) % 40 == 0:
                    e.w(u, o)
                    o = []
                    e.header(u)
                    o.extend(fwrite(f9002))
                o.extend(fwrite("(29X,A12,3X,F13.1,1X,F13.1,5X,F12.2)", fx(e.SRCID[isrc], 12), axr[irec], ayr[irec],
                                dist))
            elif t == "OPENPIT":
                e.XR, e.YR = axr[irec], ayr[irec]
                if fuente_foso.pnpoly(e.XR, e.YR, xvm, yvm, 4) > 0:
                    inc += 1
                    if (inc - 1) % 40 == 0:
                        e.w(u, o)
                        o = []
                        e.header(u)
                        o.extend(fwrite(f9002))
                    o.extend(fwrite(fuente_foso.F9004, fx(e.SRCID[isrc], 12), axr[irec], ayr[irec]))
        if e.NUMREC >= 1:
            e.X, e.Y = x, y
    e.XRAD = xrad
    e.ISRC = e.NUMSRC + 1
    e.IREC = e.NUMREC + 1
    e.w(u, o)


def prtmet(e, u):
    """PRTMET: días meteorológicos a procesar y categorías de viento."""
    o = []
    e.header(u)
    if e.L_LEAPYEAR:
        o += fwrite("(/44X,'*** METEOROLOGICAL DAYS SELECTED FOR PROCESSING ***'/63X,'(1=YES; 0=NO)'//"
                    "8(11X,5(10I2,2X)/))", *[int(e.IPROCL[i]) for i in range(1, 367)])
    else:
        o += fwrite("(/44X,'*** METEOROLOGICAL DAYS SELECTED FOR PROCESSING ***'/63X,'(1=YES; 0=NO)'//"
                    "8(11X,5(10I2,2X)/))", *[int(e.IPROC[i]) for i in range(1, 366)])
    if e.ISDATE != 0 or e.IEDATE != 2147123124:
        o += fwrite("(/23X,'METEOROLOGICAL DATA PROCESSED BETWEEN START DATE: ',I4,1X,3I3,/59X,'AND END DATE: ',I4,"
                    "1X,3I3)", e.ISYR, e.ISMN, e.ISDY, e.ISHR, e.IEYR, e.IEMN, e.IEDY, e.IEHR)
    o += fwrite("(/16X,'NOTE:  METEOROLOGICAL DATA ACTUALLY PROCESSED WILL',' ALSO DEPEND ON WHAT IS INCLUDED IN "
                "THE DATA FILE.'/)")
    o += fwrite("(//34X,'*** UPPER BOUND OF FIRST THROUGH FIFTH WIND SPEED',' CATEGORIES ***'/60X,'(METERS/SEC)'//"
                "46X,5(F7.2,','))", *[e.UCAT[i] for i in range(1, 6)])
    e.w(u, o)
