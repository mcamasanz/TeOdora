# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): vía OU (ouset.f).

OUCARD con RECTABLE, MAXTABLE, DAYTABLE, MAXIFILE, POSTFILE, PLOTFILE, SEASONHR, RANKFILE,
SUMMFILE, FILEFORM y NOHEADER, y el control final OUTQA. Los ficheros se abren al leer la clave,
como en el original (unidades dinámicas a partir de FUNITINX), y las cabeceras del MAXIFILE y del
POSTFILE en formato PLOT se escriben ya en esta fase."""
from .control import dbl, fsplit, i8, num
from .estado import ILEN_FLD, NoTraducido
from .formato import fc, fwrite, fx, nint, stonum

_NCHR1 = ("FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH", "EIGHTH", "NINTH", "TENTH")
_NCHR2 = ("1ST", "2ND", "3RD", "4TH", "5TH", "6TH", "7TH", "8TH", "9TH", "10TH")


def oucard(e):
    """OUCARD: claves de la vía OU."""
    m = "OUCARD"
    k = e.KEYWRD
    if k == "STARTING":
        e.IOSTAT[1] += 1
        if e.IOSTAT[1] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
    elif k == "RECTABLE":
        ouhigh(e)
        e.IOSTAT[2] += 1
    elif k == "MAXTABLE":
        oumxvl(e)
        e.IOSTAT[3] += 1
    elif k == "DAYTABLE":
        oudaly(e)
        e.IOSTAT[4] += 1
        if e.IOSTAT[4] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
    elif k == "MAXIFILE":
        oumxfl(e)
        e.IOSTAT[5] += 1
    elif k == "POSTFILE":
        oupost(e)
        e.IOSTAT[6] += 1
    elif k == "PLOTFILE":
        ouplot(e)
        e.IOSTAT[7] += 1
    elif k == "TOXXFILE":
        outoxx(e)
        e.IOSTAT[8] += 1
    elif k == "SEASONHR":
        if not e.SCIM:
            ouseas(e)
            e.IOSTAT[9] += 1
        else:
            e.errhdl(e.PATH, m, "E", "154", k)
    elif k == "RANKFILE":
        ourank(e)
        e.IOSTAT[10] += 1
    elif k == "EVALFILE":
        raise NoTraducido("OU EVALFILE")
    elif k == "SUMMFILE":
        ousumm(e)
        e.IOSTAT[12] += 1
        if e.IOSTAT[12] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
    elif k == "FILEFORM":
        fileform(e)
        e.IOSTAT[13] += 1
        if e.IOSTAT[13] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
    elif k == "MAXDCONT":
        if not (e.NO2AVE or e.SO2AVE or e.PM25AVE):
            e.errhdl(e.PATH, m, "E", "163", k)
            return
        for iave in range(1, e.NUMAVE + 1):
            e.IAVE = iave
            if e.KAVE[iave] == 1 or e.KAVE[iave] == 24:
                oumaxd_cont(e)
                e.IOSTAT[16] += 1
                break
        else:
            e.IAVE = e.NUMAVE + 1
        if e.IOSTAT[16] < 1:
            e.errhdl(e.PATH, m, "E", "163", k)
    elif k in ("MAXDAILY", "MXDYBYYR"):
        if not (e.NO2AVE or e.SO2AVE or e.PM25AVE):
            e.errhdl(e.PATH, m, "E", "162", k)
            return
        io = 14 if k == "MAXDAILY" else 15
        for iave in range(1, e.NUMAVE + 1):
            e.IAVE = iave
            if e.KAVE[iave] == 1 or e.KAVE[iave] == 24:
                oumaxdly(e, k == "MXDYBYYR")
                e.IOSTAT[io] += 1
                break
        else:
            e.IAVE = e.NUMAVE + 1
        if e.IOSTAT[io] < 1:
            e.errhdl(e.PATH, m, "E", "162", k)
    elif k == "NOHEADER":
        noheader(e)
        e.IOSTAT[18] += 1
        if e.IOSTAT[18] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
    elif k == "FINISHED":
        e.IOSTAT[50] += 1
        if e.IOSTAT[50] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        outqa(e)
    else:
        e.errhdl(e.PATH, m, "E", "110", k)


def outqa(e):
    """OUTQA: control de calidad de las opciones de salida."""
    m = "OUTQA"
    if e.IOSTAT[1] == 0:
        e.errhdl(e.PATH, m, "E", "130", "STARTING")
    outopt = any(e.IOSTAT[i] > 0 for i in range(2, 13))
    if not outopt and not e.PERIOD and not e.ANNUAL:
        e.errhdl(e.PATH, m, "E", "189", "  ")
    for iave in range(1, e.NUMAVE + 1):
        e.IAVE = iave
        idcst1 = 0
        for ival in range(1, e.NVAL + 1):
            if e.NHIAVE[ival, iave] == 1:
                idcst1 = 1
        if idcst1 == 0 and e.MAXAVE[iave] == 0 and e.IDYTAB[iave] == 0:
            keymsg = fwrite("(I3.3,A3)", int(e.KAVE[iave]), "-HR")[0]
            e.errhdl(e.PATH, m, "W", "540", keymsg)
    e.IAVE = e.NUMAVE + 1
    if e.DAYTAB and (e.RSTSAV or e.RSTINP):
        e.errhdl(e.PATH, m, "W", "190", "DAYTABLE")
    if e.TXFILE and (e.RSTSAV or e.RSTINP):
        e.errhdl(e.PATH, m, "E", "190", "TOXXFILE")
    if (e.RSTSAV or e.RSTINP) and e.EVAL is not None and any(e.EVAL[i] for i in range(1, e.NUMSRC + 1)):
        e.errhdl(e.PATH, m, "W", "190", "EVALFILE")
    if (e.PM25AVE or e.NO2AVE or e.SO2AVE) and e.EVENTS and not e.MXFILE:
        e.errhdl(e.PATH, m, "W", "191", "EVENTFIL Opt")
        e.EVENTS = False
    if e.IOSTAT[11] > 0 and e.NUMARC == 0:
        e.errhdl(e.PATH, m, "E", "256", "NUMARC=0")
    nnh = int(e.L_NOHEADER[1:9].sum())
    if 0 < nnh < 8:
        for i, (io, txt) in enumerate(((5, "MAXIFILE"), (6, "POSTFILE"), (7, "PLOTFILE"), (9, "SEASONHR"),
                                       (10, "RANKFILE"), (14, "MAXDAILY"), (15, "MXDYBYYR"),
                                       (16, "MAXDCONT")), 1):
            if e.L_NOHEADER[i] and e.IOSTAT[io] < 1:
                e.errhdl(e.PATH, m, "E", "164", txt)
    # ficheros de PLOTFILE que coinciden con otros ficheros con distinta unidad (o al revés)
    for i in range(1, e.NHIVAL + 1):
        for j in range(1, e.NUMGRP + 1):
            for k in range(1, e.NUMAVE + 1):
                pf, pu = e.PLTFIL[i, j, k], e.IPLUNT[i, j, k]
                for l in range(1, e.NUMGRP + 1):
                    for mm in range(1, e.NUMAVE + 1):
                        pares = ((e.PSTFIL[l, mm], e.IPSUNT[l, mm]), (e.THRFIL[l, mm], e.IMXUNT[l, mm]),
                                 (e.ANNPST[l], e.IAPUNT[l]), (e.ANNPLT[l], e.IPPUNT[l]))
                        for f2, u2 in pares:
                            if (pf == f2) != (pu == u2):
                                if l > 999:
                                    e.DUMMY = fwrite('("999+ ",I3)', int(e.KAVE[mm]))[0]
                                else:
                                    e.DUMMY = fwrite("(I4,1X,I3)", l, int(e.KAVE[mm]))[0]
                                e.errhdl(e.PATH, m, "E", "555", e.DUMMY)
                                break


def _periodo(e, m, campo, ilen=ILEN_FLD):
    """Periodo de promedio de un campo (o MONTH). Devuelve el índice INDAVE o None."""
    f = e.FIELD[campo]
    if f == "MONTH" and e.MONTH:
        iprdt = 720
    else:
        e.FNUM, imit = stonum(f, ilen, e.FNUM)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            return None
        iprdt = nint(e.FNUM)
    e.INDAVE = 0
    for j in range(1, e.NUMAVE + 1):
        if iprdt == e.KAVE[j]:
            e.INDAVE = j
            return j
    e.errhdl(e.PATH, m, "E", "203", "AVEPER")
    return None


def _grupo(e, m, campo):
    inpgrp = fc(e.FIELD[campo], 8)
    e.INDGRP = 0
    for j in range(1, e.NUMGRP + 1):
        if inpgrp == e.GRPID[j]:
            e.INDGRP = j
            return j
    e.errhdl(e.PATH, m, "E", "203", "GRPID")
    return None


def _nombre(e, campo):
    """Nombre de fichero (con mayúsculas y minúsculas) del campo, o None si es demasiado largo."""
    if e.LOCE[campo] - e.LOCB[campo] <= ILEN_FLD - 1:
        return fc(e.RUNST1[int(e.LOCB[campo]) - 1:int(e.LOCE[campo])], 200)
    e.DUMMY = i8(ILEN_FLD)
    e.errhdl(e.PATH, e._m, "E", "291", e.DUMMY)
    return None


def _unidad(e, m, campo, nombre, dinamica=True):
    """Unidad del fichero: la del campo opcional (con la comprobación de FUNITARRAY) o la siguiente
    dinámica (FUNITINX). Devuelve None si el campo no es numérico."""
    if campo is not None and e.IFC == campo:
        e.FNUM, imit = num(e, campo, e.FNUM)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            return None
        n = nint(e.FNUM)
        if not dinamica:
            u = e.FUNITINX
            e.FUNITINX += 1
            return u
        fa = e.FUNITARRAY
        idx = [i for i in range(1, len(fa)) if fa[i] == n]
        if idx and e.FNAMEARRAY[idx[0]] != nombre:
            e.DUMMY = fwrite("(i8)", n)[0]
            e.errhdl(e.PATH, m, "E", "565", e.DUMMY)
        return n
    u = e.FUNITINX
    e.FUNITINX += 1
    return u


def _registrar(e, unidad, nombre, tipo):
    e.FUNITARRAY[e.FUNITIND] = unidad
    e.FNAMEARRAY[e.FUNITIND] = nombre
    e.FTYPARRAY[e.FUNITIND] = tipo
    e.FUNITIND += 1


def _duplicado(e, m, nombre, unidad, otros):
    """Mismo fichero con otra unidad, o misma unidad con otro fichero -> error 550 (False).
    Devuelve True si ya está abierto (mismo fichero y unidad), None si no aparece."""
    found = None
    for f2, u2 in otros:
        if nombre == f2 and unidad == u2:
            found = True
        elif nombre == f2 and unidad != u2:
            e.errhdl(e.PATH, m, "E", "550", e.KEYWRD)
            return False
        elif nombre != f2 and unidad == u2:
            e.errhdl(e.PATH, m, "E", "550", e.KEYWRD)
            return False
    return found


def _reanudar(e, m, unidad, nombre, dummy, tipo, col, cod="592", ajustar_hora=False):
    """Re-arranque (RSTINP): abre el fichero existente y lo posiciona tras su último registro con
    fecha anterior o igual a la del INITFILE (col = columnas de la fecha; None: POSTFILE sin
    formato). El llamador no escribe la cabecera."""
    from . import reinicio
    e.DUMMY = dummy
    if not reinicio.existe(nombre):
        e.errhdl(e.PATH, m, "E", "585", e.DUMMY)
        return
    _registrar(e, unidad, nombre, tipo)
    e.DUMMY = "INITFILE"
    irs = reinicio.fecha_reinicio(e)
    if irs is None:
        e.errhdl(e.PATH, m, "E", "510", e.DUMMY)
        return
    e.DUMMY = dummy
    e.EOF = False
    if col is None:
        ok = reinicio.reanudar_bin(e, m, unidad, nombre, irs)
    else:
        ok = reinicio.reanudar_texto(e, m, unidad, nombre, col, irs, cod, ajustar_hora)
    if not ok:
        e.errhdl(e.PATH, m, "E", "510", e.DUMMY)
    e.EOF = False


def _abrir(e, m, unidad, nombre, tipo, prefijo, binario=False):
    try:
        if binario:
            e.abrir_bin(unidad, nombre)
        else:
            e.abrir_salida(unidad, nombre)
    except OSError:
        e.DUMMY = fwrite('("' + prefijo + '",I3.3)', unidad)[0]
        e.errhdl(e.PATH, m, "E", "500", e.DUMMY)
        return False
    _registrar(e, unidad, nombre, tipo)
    return True


def ouhigh(e):
    """OUHIGH: tablas de valores altos por receptor (RECTABLE)."""
    m = "OUHIGH"
    f = e.FIELD
    highst = [0] * (e.NVAL + 1)
    iloch = [0] * (e.NAVE + 1)
    found = False
    if e.IFC == 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC == 3:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > e.NVAL + 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    if f[3] == "ALLAVE":
        for i in range(1, e.NUMAVE + 1):
            e.INHI[i] = 1
            iloch[i] = 1
        found = True
    elif f[3] == "MONTH" and e.MONTH:
        for i in range(1, e.NUMAVE + 1):
            if e.KAVE[i] == 720:
                found = True
                e.INHI[i] = 1
                iloch[i] = 1
    else:
        _r, lprd, hprd = fsplit(e, e.PATH, e.KEYWRD, f[3], ILEN_FLD, "-")
        lprd, hprd = fc(lprd, 8), fc(hprd, 8)
        if hprd == lprd:
            e.FNUM, imit = stonum(hprd, 8, e.FNUM)
            e.IMIT = imit
            if imit != 1:
                e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            else:
                p1 = nint(e.FNUM)
                for i in range(1, e.NUMAVE + 1):
                    if p1 == e.KAVE[i]:
                        found = True
                        e.INHI[i] = 1
                        iloch[i] = 1
        else:
            e.FNUM, imit = stonum(lprd, 8, e.FNUM)
            if imit != 1:
                e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
                p1 = 0
            else:
                p1 = nint(e.FNUM)
            e.FNUM, imit = stonum(hprd, 8, e.FNUM)
            e.IMIT = imit
            if imit != 1:
                e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            else:
                p2 = nint(e.FNUM)
                for i in range(1, e.NUMAVE + 1):
                    if p1 <= e.KAVE[i] <= p2:
                        found = True
                        e.INHI[i] = 1
                        iloch[i] = 1
    if not found:
        e.errhdl(e.PATH, m, "E", "203", "AVEPER")
        return
    for i in range(4, e.IFC + 1):
        _r, lprd, hprd = fsplit(e, e.PATH, e.KEYWRD, f[i], ILEN_FLD, "-")
        lprd, hprd = fc(lprd, 8), fc(hprd, 8)
        isprd = ieprd = 0
        e.FNUM, imit = stonum(lprd, ILEN_FLD, e.FNUM)
        if imit == 1:
            isprd = int(e.FNUM)
        e.FNUM, imit = stonum(hprd, ILEN_FLD, e.FNUM)
        e.IMIT = imit
        if imit == 1:
            ieprd = int(e.FNUM)
        if isprd > 999 or ieprd > 999:
            e.errhdl(e.PATH, m, "E", "203", "HIVALU")
            continue
        if isprd == 0 or ieprd == 0:
            for j in range(10):
                if lprd == _NCHR1[j] or lprd == _NCHR2[j]:
                    isprd = j + 1
                if hprd == _NCHR1[j] or hprd == _NCHR2[j]:
                    ieprd = j + 1
        if isprd == 0 or ieprd == 0:
            e.errhdl(e.PATH, m, "E", "203", "HIVALU")
            continue
        if isprd > e.NVAL or ieprd > e.NVAL:
            e.DUMMY = fwrite("('NVAL=',I7)", e.NVAL)[0]
            e.errhdl(e.PATH, m, "E", "290", e.DUMMY)
            continue
        for j in range(isprd, ieprd + 1):
            highst[j] = 1
    for i in range(1, e.NUMAVE + 1):
        for j in range(1, e.NVAL + 1):
            if highst[j] == 1 and iloch[i] == 1:
                e.NHIAVE[j, i] = 1
                if j > e.NHIVAL:
                    e.NHIVAL = j


def oumxvl(e):
    """OUMXVL: tabla de máximos globales (MAXTABLE)."""
    m = "OUMXVL"
    f = e.FIELD
    if e.IFC == 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC == 3:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 4:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    if f[3] == "ALLAVE":
        for i in range(1, e.NUMAVE + 1):
            e.MAXAVE[i] = 1
    else:
        if f[3] == "MONTH" and e.MONTH:
            iprdt = 720
        else:
            e.FNUM, imit = num(e, 3, e.FNUM)
            e.IMIT = imit
            if imit != 1:
                e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
                return
            iprdt = nint(e.FNUM)
        found = False
        for j in range(1, e.NUMAVE + 1):
            if iprdt == e.KAVE[j]:
                found = True
                e.INDAVE = j
                e.MAXAVE[j] = 1
                break
        if not found:
            e.errhdl(e.PATH, m, "E", "203", "AVEPER")
            return
    e.FNUM, imit = num(e, 4, e.FNUM)
    e.IMIT = imit
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return
    e.INUM = nint(e.FNUM)
    if f[3] == "ALLAVE":
        for i in range(1, e.NUMAVE + 1):
            e.IMXVAL[i] = e.INUM
    else:
        e.IMXVAL[e.INDAVE] = e.INUM


def oudaly(e):
    """OUDALY: tablas de valores diarios (DAYTABLE)."""
    m = "OUDALY"
    f = e.FIELD
    if e.IFC == 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC > e.NUMAVE + 2:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    if f[3] == "ALLAVE":
        for i in range(1, e.NUMAVE + 1):
            e.IDYTAB[i] = 1
        e.DAYTAB = True
        return
    for i in range(3, e.IFC + 1):
        found = False
        if f[i] == "MONTH" and e.MONTH:
            iprdt = 720
        else:
            e.FNUM, imit = num(e, i, e.FNUM)
            e.IMIT = imit
            if imit != 1:
                e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
                return
            iprdt = nint(e.FNUM)
        for j in range(1, e.NUMAVE + 1):
            if iprdt == e.KAVE[j]:
                found = True
                e.IDYTAB[j] = 1
                break
        if not found:
            e.errhdl(e.PATH, m, "E", "203", "AVEPER")
            return
    e.DAYTAB = True


def _cabecera(e, unidad, t9007):
    """Dos primeras líneas comunes de las cabeceras de MAXIFILE y POSTFILE."""
    out = fwrite("('* AERMOD (',A6,'): ',A68,5X,A8)", fx(e.VERSN, 6), fx(e.TITLE1, 68), fx(e.RUNDAT, 8))
    return out


def oumxfl(e):
    """OUMXFL: fichero de valores que superan un umbral (MAXIFILE)."""
    m = "OUMXFL"
    e._m = m
    e.MXFILE = True
    if e.IFC == 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 6:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 7:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    ia = _periodo(e, m, 3)
    if ia is None:
        return
    ig = _grupo(e, m, 4)
    if ig is None:
        return
    e.MAXFLE[ig, ia] += 1
    if e.MAXFLE[ig, ia] > 1:
        e.errhdl(e.PATH, m, "E", "211", e.KEYWRD)
        return
    e.DNUM, imit = dbl(e, 5, e.DNUM)
    e.IMIT = imit
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return
    e.THRESH[ig, ia] = e.DNUM
    nom = _nombre(e, 6)
    if nom is not None:
        e.THRFIL[ig, ia] = nom
    u = _unidad(e, m, 7, e.THRFIL[ig, ia])
    if u is None:
        return
    e.IMXUNT[ig, ia] = u
    otros = [(e.THRFIL[i, j], e.IMXUNT[i, j]) for j in range(1, e.NUMAVE + 1) for i in range(1, e.NUMGRP + 1)
             if i != ig or j != ia]
    found = _duplicado(e, m, e.THRFIL[ig, ia], u, otros)
    if found is False:
        return
    if not found:
        if e.RSTINP:
            _reanudar(e, m, u, e.THRFIL[ig, ia], "MAXIFILE", "MAXIFILE", (15, 22))
            return
        if not _abrir(e, m, u, e.THRFIL[ig, ia], "MAXIFILE", "MAXFL"):
            return
    elif e.RSTINP:
        return
    if e.RUN and not e.FATAL and not e.L_NOHEADER[1]:
        out = _cabecera(e, u, None)
        out += fwrite("('* AERMET (',A6,'):',T93,A8,/'* MODELING OPTIONS USED: ',A:)", fx(e.C_METVER, 6),
                      fx(e.RUNTIM, 8), e.MODOPS_STRING)
        out += fwrite("('*',9X,'MAXI-FILE FOR ',A5,' VALUES ','>= A THRESHOLD OF ',G12.4,/'*',9X,"
                      "'FOR SOURCE GROUP: ',A8,/'*',9X,'FORMAT: ',A:)", fx(e.CHRAVE[ia], 5), e.THRESH[ig, ia],
                      fx(e.GRPID[ig], 8), e.THRFRM)
        out += fwrite("('*AVE',3X,'GRP',5X,'DATE',11X,'X',13X,'Y',8X,'ZELEV',3X,'ZHILL',3X,'ZFLAG',2X,3A4,"
                      "/'*___',2(1X,'________'),2(2X,'____________'),3(2X,'______'),'  ____________')",
                      fx(e.CHIDEP[1, 1], 4), fx(e.CHIDEP[2, 1], 4), fx(e.CHIDEP[3, 1], 4))
        e.w(u, out)


def oupost(e):
    """OUPOST: ficheros de valores concurrentes (POSTFILE)."""
    m = "OUPOST"
    e._m = m
    f = e.FIELD
    e.PPFILE = True
    if e.IFC == 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 6:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 7:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    if (f[3] == "PERIOD" and e.PERIOD) or (f[3] == "ANNUAL" and e.ANNUAL):
        perpst(e)
        return
    elif f[3] in ("PERIOD", "ANNUAL"):
        e.errhdl(e.PATH, m, "E", "203", " AVEPER ")
        return
    ia = _periodo(e, m, 3)
    if ia is None:
        return
    ig = _grupo(e, m, 4)
    if ig is None:
        return
    if f[5] == "UNFORM":
        e.IPSFRM[ig, ia] = 0
    elif f[5] == "PLOT":
        e.IPSFRM[ig, ia] = 1
    else:
        e.errhdl(e.PATH, m, "E", "203", "FORMAT")
        return
    e.IPSTFL[ig, ia] += 1
    if e.IPSTFL[ig, ia] > 1:
        e.errhdl(e.PATH, m, "E", "211", e.KEYWRD)
        return
    nom = _nombre(e, 6)
    if nom is not None:
        e.PSTFIL[ig, ia] = nom
    u = _unidad(e, m, 7, e.PSTFIL[ig, ia])
    if u is None:
        return
    e.IPSUNT[ig, ia] = u
    otros = [(e.PSTFIL[i, j], e.IPSUNT[i, j]) for j in range(1, e.NUMAVE + 1) for i in range(1, e.NUMGRP + 1)
             if i != ig or j != ia]
    found = _duplicado(e, m, e.PSTFIL[ig, ia], u, otros)
    if found is False:
        return
    f2 = _duplicado(e, m, e.PSTFIL[ig, ia], u, [(e.ANNPST[i], e.IAPUNT[i]) for i in range(1, e.NUMGRP + 1)])
    if f2 is False:
        return
    found = found or f2
    if not found:
        if e.RSTINP:
            if f[5] == "UNFORM":
                _reanudar(e, m, u, e.PSTFIL[ig, ia], "POSTFILE", "POSTFILE", None)
            else:
                i0 = 90 + 14 * (e.NUMTYP - 1)
                _reanudar(e, m, u, e.PSTFIL[ig, ia], "POSTFILE", "POSTFILE", (i0, i0 + 7), cod="593")
            return
        if f[5] == "UNFORM":
            if not _abrir(e, m, u, e.PSTFIL[ig, ia], "PSTFIL", "PSTFL", binario=True):
                return
        else:
            if not _abrir(e, m, u, e.PSTFIL[ig, ia], "POSTFILE", "PSTFL"):
                return
    elif e.RSTINP:
        return
    if e.RUN and not e.FATAL and f[5] == "PLOT" and not e.L_NOHEADER[2]:
        out = _cabecera(e, u, None)
        out += fwrite("('* AERMET (',A6,'): ',A68,T93,A8,/'* MODELING OPTIONS USED: ',A:)", fx(e.C_METVER, 6),
                      fx(e.TITLE2, 68), fx(e.RUNTIM, 8), e.MODOPS_STRING)
        out += fwrite("('*',9X,'POST/PLOT FILE OF CONCURRENT ',A5,' VALUES',' FOR SOURCE GROUP: ',A8,/'*',9X,"
                      "'FOR A TOTAL OF ',I5,' RECEPTORS.',/'*',9X,'FORMAT: ',A:)", fx(e.CHRAVE[ia], 5),
                      fx(e.GRPID[ig], 8), e.NUMREC, fx(e.PSTFRM, 200))
        out += _hdr_post(e)
        e.w(u, out)


def _hdr_post(e):
    """Las dos líneas de títulos de columnas del POSTFILE (formato HDRFRM del original)."""
    n = e.NUMTYP
    fmt = ("('*',8X,'X',13X,'Y',4X,%d(2X,3A4),4X,'ZELEV',4X,'ZHILL',4X,'ZFLAG',4X,'AVE',5X,'GRP',7X,'DATE',"
           "5X,'NET ID',/,'*',%d(1X,'____________ '),1X,3(' ______  '),'______  ________  ________  ________')"
           % (n, n + 2))
    items = []
    for t in range(1, n + 1):
        items += [fx(e.CHIDEP[1, t], 4), fx(e.CHIDEP[2, t], 4), fx(e.CHIDEP[3, t], 4)]
    return fwrite(fmt, *items)


def ouplot(e):
    """OUPLOT: ficheros de valores altos por receptor para gráficos (PLOTFILE)."""
    m = "OUPLOT"
    e._m = m
    f = e.FIELD
    e.PLFILE = True
    if e.IFC == 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 5:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 7:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    if (f[3] == "PERIOD" and e.PERIOD) or (f[3] == "ANNUAL" and e.ANNUAL):
        perplt(e)
        return
    elif f[3] in ("PERIOD", "ANNUAL"):
        e.errhdl(e.PATH, m, "E", "203", " AVEPER ")
        return
    ia = _periodo(e, m, 3)
    if ia is None:
        return
    ig = _grupo(e, m, 4)
    if ig is None:
        return
    found = False
    e.INDVAL = 0
    e.FNUM, imit = num(e, 5, e.FNUM)
    e.IMIT = imit
    if imit == 1:
        found = True
        e.INDVAL = int(e.FNUM)
    else:
        for i in range(10):
            if f[5] == _NCHR1[i] or f[5] == _NCHR2[i]:
                found = True
                e.INDVAL = i + 1
    iv = e.INDVAL
    if not found or iv > e.NHIVAL:
        e.errhdl(e.PATH, m, "E", "203", "HIVALU")
        return
    if e.NHIAVE[iv, ia] != 1:
        e.errhdl(e.PATH, m, "E", "203", "HIVALU")
        return
    e.IPLTFL[iv, ig, ia] += 1
    if e.IPLTFL[iv, ig, ia] > 1:
        e.errhdl(e.PATH, m, "E", "211", e.KEYWRD)
        return
    nom = _nombre(e, 6)
    if nom is not None:
        e.PLTFIL[iv, ig, ia] = nom
    u = _unidad(e, m, 7, e.PLTFIL[iv, ig, ia])
    if u is None:
        return
    e.IPLUNT[iv, ig, ia] = u
    otros = [(e.PLTFIL[i, j, k], e.IPLUNT[i, j, k]) for k in range(1, e.NUMAVE + 1)
             for j in range(1, e.NUMGRP + 1) for i in range(1, e.NHIVAL + 1) if i != iv or j != ig or k != ia]
    found = _duplicado(e, m, e.PLTFIL[iv, ig, ia], u, otros)
    if found is False:
        return
    f2 = _duplicado(e, m, e.PLTFIL[iv, ig, ia], u, [(e.ANNPLT[i], e.IPPUNT[i]) for i in range(1, e.NUMGRP + 1)])
    if f2 is False:
        return
    if not (found or f2):
        _abrir(e, m, u, e.PLTFIL[iv, ig, ia], "PLTFIL", "PLTFL")


def perpst(e):
    """PERPST: POSTFILE de los promedios del periodo."""
    m = "PERPST"
    e._m = m
    f = e.FIELD
    e.ANPOST = True
    if e.IFC > 7:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    ig = _grupo(e, m, 4)
    if ig is None:
        return
    e.IANPST[ig] += 1
    if e.IANPST[ig] > 1:
        e.errhdl(e.PATH, m, "E", "211", e.KEYWRD)
        return
    if f[5] == "UNFORM":
        e.IANFRM[ig] = 0
    elif f[5] == "PLOT":
        e.IANFRM[ig] = 1
    else:
        e.errhdl(e.PATH, m, "E", "203", "FORMAT")
        return
    nom = _nombre(e, 6)
    if nom is not None:
        e.ANNPST[ig] = nom
    u = _unidad(e, m, 7, e.ANNPST[ig])
    if u is None:
        return
    e.IAPUNT[ig] = u
    found = _duplicado(e, m, e.ANNPST[ig], u, [(e.ANNPST[i], e.IAPUNT[i]) for i in range(1, e.NUMGRP + 1)
                                                if i != ig])
    if found is False:
        return
    f2 = _duplicado(e, m, e.ANNPST[ig], u, [(e.PSTFIL[i, j], e.IPSUNT[i, j]) for j in range(1, e.NUMAVE + 1)
                                             for i in range(1, e.NUMGRP + 1)])
    if f2 is False:
        return
    if not (found or f2):
        _abrir(e, m, u, e.ANNPST[ig], "ANNPST", "PSTFL", binario=(f[5] == "UNFORM"))


def perplt(e):
    """PERPLT: PLOTFILE de los promedios del periodo."""
    m = "PERPLT"
    e._m = m
    e.ANPLOT = True
    if e.IFC > 6:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    ig = _grupo(e, m, 4)
    if ig is None:
        return
    e.IANPLT[ig] += 1
    if e.IANPLT[ig] > 1:
        e.errhdl(e.PATH, m, "E", "211", e.KEYWRD)
        return
    nom = _nombre(e, 5)
    if nom is not None:
        e.ANNPLT[ig] = nom
    u = _unidad(e, m, 6, e.ANNPLT[ig])
    if u is None:
        return
    e.IPPUNT[ig] = u
    found = _duplicado(e, m, e.ANNPLT[ig], u, [(e.ANNPLT[i], e.IPPUNT[i]) for i in range(1, e.NUMGRP + 1)
                                                if i != ig])
    if found is False:
        return
    f2 = _duplicado(e, m, e.ANNPLT[ig], u, [(e.PLTFIL[i, j, k], e.IPLUNT[i, j, k]) for k in range(1, e.NUMAVE + 1)
                                             for j in range(1, e.NUMGRP + 1) for i in range(1, e.NHIVAL + 1)])
    if f2 is False:
        return
    if not (found or f2):
        _abrir(e, m, u, e.ANNPLT[ig], "ANNPLT", "PLTFL")


def ouseas(e):
    """OUSEAS: fichero de promedios por estación y hora del día (SEASONHR)."""
    m = "OUSEAS"
    e._m = m
    e.SEASONHR = True
    if e.IFC == 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 4:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 5:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    ig = _grupo(e, m, 3)
    if ig is None:
        return
    e.ISEAHR[ig] += 1
    if e.ISEAHR[ig] > 1:
        e.errhdl(e.PATH, m, "E", "211", e.KEYWRD)
        return
    nom = _nombre(e, 4)
    if nom is not None:
        e.SEAHRS[ig] = nom
    u = _unidad(e, m, 5, e.SEAHRS[ig], dinamica=False)
    if u is None:
        return
    e.ISHUNT[ig] = u
    found = _duplicado(e, m, e.SEAHRS[ig], u, [(e.SEAHRS[i], e.ISHUNT[i]) for i in range(1, e.NUMGRP + 1)
                                               if i != ig])
    if found is False:
        return
    if not found:
        _abrir(e, m, u, e.SEAHRS[ig], "SEAHRS", "SEAHR")


def ourank(e):
    """OURANK: fichero de valores ordenados (RANKFILE)."""
    m = "OURANK"
    e._m = m
    e.RKFILE = True
    if e.IFC == 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 5:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 6:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    ia = _periodo(e, m, 3)
    if ia is None:
        return
    if e.IRNKFL[ia] == 0:
        e.IRNKFL[ia] += 1
    else:
        e.errhdl(e.PATH, m, "E", "203", "AVEPER")
        return
    e.FNUM, imit = num(e, 4, e.FNUM)
    e.IMIT = imit
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return
    e.INUM = nint(e.FNUM)
    e.IRKVAL[ia] = e.INUM
    nom = _nombre(e, 5)
    if nom is not None:
        e.RNKFIL[ia] = nom
    u = _unidad(e, m, 6, e.RNKFIL[ia])
    if u is None:
        return
    e.IRKUNT[ia] = u
    found = _duplicado(e, m, e.RNKFIL[ia], u, [(e.RNKFIL[i], e.IRKUNT[i]) for i in range(1, e.NUMAVE + 1)
                                               if i != ia])
    if found is False:
        return
    if not found:
        _abrir(e, m, u, e.RNKFIL[ia], "RNKFIL", "RNKFL")


def outoxx(e):
    """OUTOXX: ficheros sin formato para el modelo TOXX (TOXXFILE)."""
    import struct
    m = "OUTOXX"
    e._m = m
    e.IDUM = 0
    e.TXFILE = True
    f = e.FIELD
    if e.IFC == 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 5:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 6:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    if f[3] == "MONTH" and e.MONTH:
        iprdt = 720
    else:
        e.FNUM, imit = num(e, 3, e.FNUM)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            return
        iprdt = nint(e.FNUM)
    ia = 0
    for j in range(1, e.NUMAVE + 1):
        if iprdt == e.KAVE[j]:
            ia = j
            break
    e.INDAVE = ia
    if ia == 0:
        e.errhdl(e.PATH, m, "E", "203", "AVEPER")
        return
    if iprdt != 1:
        e.errhdl(e.PATH, m, "W", "296", fwrite("(2X,I4,2X)", iprdt)[0])
    e.ITOXFL[ia] += 1
    if e.ITOXFL[ia] > 1:
        e.errhdl(e.PATH, m, "E", "211", e.KEYWRD)
        return
    e.DNUM, imit = dbl(e, 4, e.DNUM)
    e.IMIT = imit
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return
    e.TOXTHR[ia] = e.DNUM
    nom = _nombre(e, 5)
    if nom is not None:
        e.TOXFIL[ia] = nom
    if e.IFC == 6:
        e.FNUM, imit = num(e, 6, e.FNUM)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            return
        n = nint(e.FNUM)
        if any(e.FUNITARRAY[i] == n for i in range(1, len(e.FUNITARRAY))):
            e.errhdl(e.PATH, m, "W", "565", e.KEYWRD)
        e.ITXUNT[ia] = n
    else:
        e.ITXUNT[ia] = e.FUNITINX
        e.FUNITINX += 1
    u = int(e.ITXUNT[ia])
    found = _duplicado(e, m, e.TOXFIL[ia], u, [(e.TOXFIL[i], e.ITXUNT[i]) for i in range(1, e.NUMAVE + 1)
                                                if i != ia])
    if found is False:
        return
    if not found:
        if not _abrir(e, m, u, e.TOXFIL[ia], "TOXXFILE", "TOXFL", binario=True):
            return
    if e.RUN:
        numper = e.NHOURS // iprdt
        e.U[u].reg((fx(e.TITLE1, 68) + " " * 12).encode("latin-1"))
        e.U[u].reg(struct.pack("<10i", e.ISYEAR, e.NUMGRP, e.NUMREC, numper, e.ITAB, e.NXTOX, e.NYTOX,
                               0, 0, 0))
        e.U[u].reg(struct.pack("<d9i", e.TOXTHR[ia], *([0] * 9)))


def oumaxdly(e, byyr):
    """OUMAXDLY / OUMXDLY_BYYR: ficheros de máximos diarios por día (MAXDAILY) o de los máximos
    diarios ordenados de cada año (MXDYBYYR) de un grupo de fuentes."""
    m = "OUMXDLY_BYYR" if byyr else "OUMAXDLY"
    e._m = m
    if byyr:
        e.MXDAILY_BYYR = True
        cont, unid, fich, tipo, dummy, nh_idx = ("IMXDLY_BYYR", "IMDUNT_BYYR", "MAXDLY_BYYR", "MAXDLY_BYYR",
                                                 "MXDYBYYR", 7)
    else:
        e.MXDAILY = True
        cont, unid, fich, tipo, dummy, nh_idx = "IMXDLY", "IMDUNT", "MAXDLY", "MAXDLY", "MAXDAILY", 6
    nt = e.NUMTYP
    hdrfrm = ("('*',8X,'X',13X,'Y',4X,%d(2X,3A4),4X,'ZELEV',4X,'ZHILL',4X,'ZFLAG',4X,'%s',%dX,'GRP',5X,"
              "'JDAY',3X,'HR',4X,'DATE',5X,'NET ID',/,'*',%d(1X,'____________ '),1X,3(' ______  '),"
              "'______  ________  ____  ___  ________','  ________')"
              % (nt, "RANK" if byyr else "AVE", 4 if byyr else 5, nt + 2))
    if e.IFC == 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 4:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 5:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    ig = _grupo(e, m, 3)
    if ig is None:
        return
    c, un, fi = getattr(e, cont), getattr(e, unid), getattr(e, fich)
    c[ig] += 1
    if c[ig] > 1:
        e.errhdl(e.PATH, m, "E", "211", e.KEYWRD)
        return
    nom = _nombre(e, 4)
    if nom is not None:
        fi[ig] = nom
    u = _unidad(e, m, 5, fi[ig])
    if u is None:
        return
    un[ig] = u
    found = _duplicado(e, m, fi[ig], u, [(fi[i], un[i]) for i in range(1, e.NUMGRP + 1) if i != ig])
    if found is False:
        return
    if not found:
        if e.RSTINP:
            _reanudar(e, m, u, fi[ig], dummy, tipo, (101, 108), cod="593", ajustar_hora=not byyr)
            return
        if not _abrir(e, m, u, fi[ig], tipo, "MXDLY"):
            return
    elif e.RSTINP:
        return
    if e.RUN and not e.FATAL and not e.L_NOHEADER[nh_idx]:
        out = _cabecera(e, u, None)
        out += fwrite("('* AERMET (',A6,'):',T93,A8,/'* MODELING OPTIONS USED: ',A:)", fx(e.C_METVER, 6),
                      fx(e.RUNTIM, 8), e.MODOPS_STRING)
        if byyr:
            out += fwrite("('*',9X,'MXDYBYYR FILE OF RANKED DAILY MAXIMUM 1-HR ',' VALUES BY YEAR FOR SOURCE "
                          "GROUP: ',A8,/'*',9X,'FOR A TOTAL OF ',I5,' RECEPTORS.',/'*',9X,'FORMAT: ',A:)",
                          fx(e.GRPID[ig], 8), e.NUMREC, e.MXDFRM)
        else:
            out += fwrite("('*',9X,'MAXDAILY FILE OF DAILY MAXIMUM 1-HR VALUES',' BY DAY FOR SOURCE GROUP: ',"
                          "A8,/'*',9X,'FOR A TOTAL OF ',I5,' RECEPTORS.',/'*',9X,'FORMAT: ',A:)",
                          fx(e.GRPID[ig], 8), e.NUMREC, e.MXDFRM)
        out += fwrite(hdrfrm, *[fx(e.CHIDEP[i, it], 4) for it in range(1, nt + 1) for i in (1, 2, 3)])
        e.w(u, out)


def oumaxd_cont(e):
    """OUMAXD_CONT: contribución de cada grupo a los máximos diarios (MAXDCONT) de un grupo, para
    un intervalo de rangos o hasta un umbral (THRESH)."""
    m = "OUMAXD_CONT"
    e._m = m
    e.L_MAXDCONT = True
    for activo, txt in ((e.MULTYR, "MULTYEAR"), (e.RSTSAV, "SAVEFILE"), (e.RSTINP, "INITFILE")):
        if activo:
            e.errhdl(e.PATH, m, "E", "153", txt)
            return
    if e.IFC == 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 6:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 8:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    ig = _grupo(e, m, 3)
    if ig is None:
        return
    if e.MAXDCONT[ig] == 1:
        e.errhdl(e.PATH, m, "E", "161", e.GRPID[ig])
        return
    e.MAXDCONT[ig] = 1
    e.FNUM, imit = num(e, 4, e.FNUM)
    e.IMIT = imit
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return
    e.MXD_RANK[ig, 1] = nint(e.FNUM)
    if e.MXD_RANK[ig, 1] > e.NHIVAL:
        e.errhdl(e.PATH, m, "E", "290", fwrite("('NVAL=',I7)", e.NHIVAL)[0])
        return
    if e.FIELD[5] == "THRESH":
        e.DNUM, imit = dbl(e, 6, e.DNUM)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            return
        e.MAXD_THRESH[ig] = e.DNUM
        e.MXD_RANK[ig, 2] = e.NHIVAL
        nom = _nombre(e, 7)
        if nom is not None:
            e.MAXDCONT_FILE[ig] = nom
        u = _unidad(e, m, 8, e.MAXDCONT_FILE[ig])
        if u is None:
            return
        e.IMXDCUNT[ig] = u
        nh = e.NHIVAL
        if (e.SO2AVE and nh <= 8) or (e.NO2AVE and nh <= 12) or (e.PM25AVE and nh <= 12):
            e.errhdl(e.PATH, m, "E", "273", fwrite("('Max Rank =',I2)", nh)[0])
        elif (e.SO2AVE and nh <= 24) or (e.NO2AVE and nh <= 28) or (e.PM25AVE and nh <= 28):
            e.errhdl(e.PATH, m, "W", "273", fwrite("('Max Rank =',I2)", nh)[0])
    else:
        e.FNUM, imit = num(e, 5, e.FNUM)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            return
        e.MXD_RANK[ig, 2] = nint(e.FNUM)
        r1, r2 = int(e.MXD_RANK[ig, 1]), int(e.MXD_RANK[ig, 2])
        if r2 > e.NHIVAL:
            e.errhdl(e.PATH, m, "E", "290", fwrite("('NVAL=',I7)", e.NHIVAL)[0])
            return
        elif r2 < r1:
            e.errhdl(e.PATH, m, "E", "272", fwrite("('U=',I3,2X,'L=',I3)", r1, r2)[0])
            return
        elif r2 > 366:
            e.errhdl(e.PATH, m, "W", "290", fwrite("(' NVAL=',I6)", r2)[0])
        e.MAXD_THRESH[ig] = 0.0
        nom = _nombre(e, 6)
        if nom is not None:
            e.MAXDCONT_FILE[ig] = nom
        if e.IFC == 7:
            e.FNUM, imit = num(e, 7, e.FNUM)
            e.IMIT = imit
            if imit != 1:
                e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
                return
            e.IMXDCUNT[ig] = nint(e.FNUM)
        else:
            e.IMXDCUNT[ig] = e.FUNITINX
            e.FUNITINX += 1
    found = _duplicado(e, m, e.MAXDCONT_FILE[ig], e.IMXDCUNT[ig],
                       [(e.MAXDCONT_FILE[i], e.IMXDCUNT[i]) for i in range(1, e.NUMGRP + 1) if i != ig])
    if found is False:
        return
    if not found:
        _abrir(e, m, int(e.IMXDCUNT[ig]), e.MAXDCONT_FILE[ig], "MAXDCONT_FILE", "MXDCN")


def ousumm(e):
    """OUSUMM: fichero de resumen (SUMMFILE)."""
    m = "OUSUMM"
    e.SUMMFILE = True
    if e.IFC == 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 3:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    if e.LOCE[3] - e.LOCB[3] <= ILEN_FLD - 1:
        e.SUMFIL = fc(e.RUNST1[int(e.LOCB[3]) - 1:int(e.LOCE[3])], 200)
    else:
        e.DUMMY = i8(ILEN_FLD)
        e.errhdl(e.PATH, m, "E", "291", e.DUMMY)
        return
    try:
        e.abrir_salida(e.ISUMUNT, e.SUMFIL)
    except OSError:
        e.errhdl(e.PATH, m, "E", "500", "SUMMFILE")
        return
    _registrar(e, e.ISUMUNT, e.SUMFIL, "SUMFIL")


def fileform(e):
    """FILEFORM: formato fijo o exponencial de los ficheros de resultados."""
    m = "FILEFORM"
    if e.IFC == 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 3:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    f3 = e.FIELD[3][:3]
    if f3 == "FIX":
        e.FILE_FORMAT = "FIX"
    elif f3 == "EXP" and e.DFAULT and e.POLLCRIT:
        e.FILE_FORMAT = "FIX"
        e.errhdl(e.PATH, m, "W", "595", e.POLLUT)
    elif f3 == "EXP":
        e.FILE_FORMAT = "EXP"
        if e.NUMTYP == 1:
            e.THRFRM = "(1X,I3,1X,A8,1X,I8.8,2(1X,F13.5),3(1X,F7.2),1X,E13.6)"
            e.PSTFRM = "(2(1X,F13.5),1X,E13.6,3(1X,F8.2),2X,A6,2X,A8,2X,I8.8,2X,A8)"
            if e.PM25AVE or e.NO2AVE or e.SO2AVE:
                e.PLTFRM = "(2(1X,F13.5),1X,E13.6,3(1X,F8.2),2X,A6,2X,A8,2X,A5,5X,A8,2X,10(E13.6,2X,I8.8,2X:))"
            else:
                e.PLTFRM = "(2(1X,F13.5),1X,E13.6,3(1X,F8.2),3X,A5,2X,A8,2X,A5,5X,A8,2X,I8)"
            e.RNKFRM = "(1X,I6,1X,E13.6,1X,I8.8,2(1X,F13.5),3(1X,F7.2),2X,A8)"
            e.MXDFRM = "(2(1X,F13.5),1X,E13.6,3(1X,F8.2),2X,A6,2X,A8,2X,I4,2X,I3,2X,I8.8,2X,A8)"
    else:
        e.errhdl(e.PATH, m, "E", "203", " FORMAT ")


def noheader(e):
    """NOHEADER: suprime las cabeceras de los ficheros de salida."""
    m = "NOHEADER"
    if e.IFC == 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 3:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 10:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    nombres = ("MAXIFILE", "POSTFILE", "PLOTFILE", "SEASONHR", "RANKFILE", "MAXDAILY", "MXDYBYYR", "MAXDCONT")
    for i in range(3, e.IFC + 1):
        fi = e.FIELD[i]
        if fi == "ALL":
            e.L_NOHEADER[:] = True
            break
        elif fi in nombres:
            e.L_NOHEADER[nombres.index(fi) + 1] = True
        else:
            e.errhdl(e.PATH, m, "E", "203", fi)
