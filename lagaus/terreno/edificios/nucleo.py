# -*- coding: utf-8 -*-
"""Traducción de BPIPPRM 04274 (US EPA, dominio público): Building Profile Input Program for PRIME.

Programa principal y subrutinas CNRLIN, DISLIN, GPC, MXBWH y WIDTH de Bpipprm.for.

Precisión: el original declara casi todo REAL (simple) y está compilado con Compaq Visual
Fortran para x87, que calcula cada expresión en registros de 80 bits y redondea a simple al
guardar en la variable. Aquí cada expresión se calcula en doble y se redondea con ``r4`` al
asignarla a una variable REAL. Las DOUBLE PRECISION (coordenadas X, Y de las esquinas, DIRT…)
se quedan en doble.

Índices 1-based como en el Fortran (la posición 0 de cada lista no se usa)."""
import datetime as _dt
import os
import math
import struct

from .formato import ErrorEjecucion, Fichero, fwrite, fx, lread

_F32 = struct.Struct("f")


def r4(x):
    """Asignación a una variable REAL (redondeo a simple)."""
    return _F32.unpack(_F32.pack(x))[0]


# literales de simple precisión que entran en comparaciones
R4_005 = r4(0.05)
R4_0001 = r4(0.001)
R4_M0001 = r4(-0.001)
R4_002 = r4(0.02)
DTR = r4(r4(3.141593) / 180.0)          # 3.141593 / 180. (constante simple)
DTR2 = DTR                               # DTR2 = 3.141593/180. (expresión simple, guardada en doble)

FORMATOS = {
    1: "(1X,A78,/)",
    2: "(/3X,'The ',A2,' flag has been set for preparing downwash',' related data'"
       "/10X,'for a model run utilizing the PRIME algorithm.'/)",
    3: "(3X,'Inputs entered in ', A10,' will be converted to ','meters using '/3X,"
       "' a conversion factor of',F10.4,'.  Output will be in meters.'/)",
    4: "(3X,'The UTMP variable is set to ',A4,'.  The input is ','assumed to be in'/4X,"
       "' UTM coordinates.  BPIP will move the UTM origin',' to the first pair of'/4X,"
       "' UTM coordinates read.','  The UTM coordinates of the new origin will '/4X,"
       "' be subtracted from all the other UTM coordinates entered to ','form '/4X,"
       "' this new local coordinate system.'/)",
    5: "(3X,'UTMP is set to ',A4,'.  The input is assumed to be in',' a local'/3x,"
       "' X-Y coordinate system as opposed to a UTM',' coordinate system.'/3x,"
       "' True North is in the positive Y',' direction.'/)",
    6: "(1X,'Number of buildings to be processed :',I4)",
    9: "(/3X,'The ',A2,' flag has been set for preparing downwash',' data for an ISCLT run.'/)",
    11: "(3X,'The new local coordinates will be displayed in parent','heses just below'/4X,"
        "' the UTM coordinates they represent.',/)",
    12: "(//1X,A8,' has',I2,' tier(s) with a base elevation of',F8.2,' ',A10)",
    13: "(47X,'(',F8.2,') meters',/)",
    14: "(' BUILDING  TIER  BLDG-TIER  TIER   NO. OF      CORNER   ','COORDINATES',/"
        "'   NAME   NUMBER   NUMBER  HEIGHT  CORNERS        X           Y'/)",
    16: "(/3X,'The ',A2,' flag has been set for preparing downwash',' related data'/10X,"
        "'for a model run **not** utilizing the PRIME algorithm.'/)",
    17: "(3X,'Plant north is set to',F7.2,' degrees with respect to',' True North.  '//)",
    18: "(4X,'The plant coordinates will appear as entered in the ','Summary output'/4x,"
        "'file and they will be adjusted to True ','North prior to processing.'/4x,"
        "'The True North oriented coordinates appear ','below between'/4X,'the square brackets.')",
    19: "(41X,'[',2F12.2,'] meters')",
    21: "(1X,A8,I5,5X,I4,4X,F6.2,I6)",
    22: "(27X,F6.2,' meters')",
    31: "(42X,2F12.2, 1X, A10)",
    32: "(42X,2F12.2, ' meters')",
    33: "(41X,'(',2F12.2,') meters')",
    41: "(/1X,'Number of stacks to be processed :',I4/)",
    42: "('                    STACK            STACK   COORDINATES'/"
        "'  STACK NAME     BASE  HEIGHT          X           Y'/)",
    43: "(2X, A8,3X, 2F8.2, 1X, A10)",
    44: "(12X,'(', 2F8.2, ') meters')",
    45: "(30X,'(', 2F12.2,') meters')",
    46: "(30X,'[', 2F12.2,'] meters')",
    47: "('  Caution: Blank spaces are not allowed in Stack names ','by ISC2 models.')",
    49: "(31X,2F12.2, 1X, A10)",
    51: "(31X, 2F12.2,' meters')",
    71: "(//' The following lists the stacks that have been identi','fied'/"
        "' as being atop the noted building-tiers.'/)",
    72: "(9X, ' STACK            BUILDING         TIER'/9X, ' NAME      NO.    NAME        NO.  NO.')",
    73: "(10X, A8, I4, 5X, A8, 2(1X, I5))",
    115: "('      Wind flow passing', I4,' degree direction.')",
    290: "(5X,'SO XBADJ    ', A8, 6F8.2)",
    291: "(5X,'SO YBADJ    ', A8, 6F8.2)",
    293: "(5X,'SO BUILDHGT ', A8, 6F8.2)",
    296: "(5X,'SO BUILDWID ', A8, 6F8.2)",
    297: "(/)",
    299: "(5X,'SO BUILDLEN ', A8, 6F8.2)",
    461: "(30X,'BPIP (Dated: 04274)')",
    462: "(1X,'DATE : ',I2,'/',I2,'/',I4)",
    463: "(1X,'TIME : ',I2,':',I2,':',I2)",
    604: "(/1X,'Drtcn: ', F6.2/)",
    1000: "(8X, A8, 4(F8.2,5X))",
    1001: "(8X, A8, F8.2, 10X, 'N/A',5X, 3(F8.2,5X))",
    1005: "(16X,'PRELIMINARY* GEP STACK HEIGHT RESULTS TABLE'/13X,'            (Output Units: meters)'//"
          "8X,'                    Stack-Building            Preliminary*'/"
          "8X,' Stack    Stack     Base Elevation    GEP**   GEP Stack'/"
          "8X,' Name     Height    Differences       EQN1    Height Value'//)",
    1007: "(/'   * Results are based on Determinants 1 & 2 on pages 1',' & 2 of the GEP'/"
          "'     Technical Support Document.  Determinan','t 3 may be investigated for'/"
          "'     additional stack height cred','it.  Final values result after'/"
          "'     Determinant 3 has been ta','ken into consideration.'/"
          "'  ** Results were derived from Equation 1 on page 6 of GEP Tech','nical'/"
          "'     Support Document.  Values have been adjusted for a','ny stack-building'/"
          "'     base elevation differences.'//"
          "'     Note:  Criteria for determining stack heights for modeling',' emission'/"
          "'     limitations for a source can be found in Table 3.1 of the'/"
          "'     GEP Technical Support Document.'/)",
    1020: "(//'                     Overall GEP Summary Table'/'                          (Units: meters)'//)",
    1022: "(' StkNo:', I3,'  Stk Name:', A8,' Stk Ht:',F7.2,' Prelim. GEP Stk.Ht:',F8.2,"
          "/11x,' GEP:  BH:',F7.2,'  PBW:',F8.2, 11X, '  *Eqn1 Ht:',F8.2)",
    1023: "('  No. of Tiers affecting Stk:', I3,'  Direction occurred:', F8.2)",
    1024: "('   Bldg-Tier nos. contributing to GEP:', 10I4)",
    1025: "(10X,'*adjusted for a Stack-Building elevation difference',' of',F8.2)",
    1026: "(5X,  'Single tier MAX:  BH:',F7.2,'  PBW:',F7.2,'  PBL:',F7.2,'  *Wake Effect Ht:', F8.2/5X,"
          "'Relative Coordinates of Projected Width Mid-point: XADJ: ',F7.2,'  YADJ: ',F7.2/5X)",
    2020: "(//'                     Summary By Direction Table'/'                          (Units:  meters)',"
          "// ' Dominate stand alone tiers:'/)",
    2022: "(' StkNo:', I3,'  Stk Name:', A8, 23X,'   Stack Ht:', F8.2)",
    2026: "(3X,'Combined tier MAX:  BH:',F7.2,'  PBW:',F7.2,'  PBL:',F7.2,'  *WE Ht:', F8.2/5X,"
          "'Relative Coordinates of Projected Width Mid-point: XADJ: ',F7.2,'  YADJ: ',F7.2/5X)",
    2027: "(11X,'      GEP:  BH:',F7.2,'  PBW:',F7.2,'   *Equation 1 Ht:', F8.2)",
    2028: "(15X,' BldNo:', I3,'  Bld Name:', A8, '  TierNo:', I3)",
    2023: "('  No. of Tiers affecting Stk:', I3)",
    2024: "('   Bldg-Tier nos. contributing to MAX:', 10I4)",
}


def _lista(n, val=0):
    return [val] * (n + 1)


def _matriz(*dims, val=0):
    if len(dims) == 1:
        return [val] * (dims[0] + 1)
    return [_matriz(*dims[1:], val=val) for _ in range(dims[0] + 1)]


class _Lector:
    """READ(10,*) sobre los registros del fichero de entrada."""

    def __init__(self, nombre):
        self.nombre = nombre
        with open(nombre, "r", encoding="latin-1", newline=None) as fh:
            self.regs = fh.read().split("\n")
        if self.regs and self.regs[-1] == "":
            self.regs.pop()
        self.ptr = 0

    def leer(self, tipos):
        v, ios, nrec = lread(self.regs[self.ptr:], tipos)
        if ios != 0 or len(v) < len(tipos):
            # el original no lleva IOSTAT: el run-time de Fortran aborta
            raise ErrorEjecucion("lectura fallida en el fichero de entrada",
                                 "forrtl: severe (24): end-of-file during read, unit 10, file "
                                 + self.nombre if ios < 0 else
                                 "forrtl: severe (59): list-directed I/O syntax error, unit 10, file "
                                 + self.nombre)
        self.ptr += max(nrec, 1)
        return v

    def rewind(self):
        self.ptr = 0


# ------------------------------------------------------------------------------------------
# subrutinas
# ------------------------------------------------------------------------------------------
def cnrlin(x1, y1, x2, y2, xkp, ykp):
    """CNRLIN: distancia de una esquina (XKP, YKP) a un lado y si el pie de la perpendicular
    cae entre sus extremos. Devuelve (XI, YI, BET, DIST)."""
    if x1 != x2 and y1 != y2:
        sm = r4((y2 - y1) / (x2 - x1))
        xi = r4((ykp + xkp / sm - y1 + x1 * sm) / (sm + 1.0 / sm))
        yi = r4(y1 + (xi - x1) * sm)
    else:
        if y2 == y1:
            xi = xkp
            yi = y1
        else:
            xi = x1
            yi = ykp
    dist = r4(math.sqrt((yi - ykp) ** 2 + (xi - xkp) ** 2))
    a1 = r4((x1 - xi) ** 2 + (y1 - yi) ** 2 + (x2 - xi) ** 2 + (y2 - yi) ** 2)
    a2 = r4((x1 - x2) ** 2 + (y1 - y2) ** 2)
    bet = r4(a2 - a1)
    return xi, yi, bet, dist


def dislin(x1, y1, x2, y2, l5, xsp, ysp):
    """DISLIN: 1 si la chimenea está a sotavento del lado y a 5L o menos."""
    ibet = 0
    dx1 = min(x1, x2)
    dx2 = max(x1, x2)
    if xsp < dx1 or xsp > dx2:
        return ibet
    if y1 == y2:
        dist = r4(ysp - y1)
        if dist >= 0.0 and dist <= l5:
            ibet = 1
    if x1 == x2:
        if xsp == x1:
            d1 = r4(ysp - y1)
            if d1 <= l5 and d1 >= 0.0:
                ibet = 1
            d2 = r4(ysp - y2)
            if d2 <= l5 and d2 >= 0.0:
                ibet = 1
    else:
        yi = r4(y2 + (xsp - x2) * (y1 - y2) / (x1 - x2))
        dist = r4(ysp - yi)
        if dist >= 0.0 and dist <= l5:
            ibet = 1
    return ibet


class _Estado:
    pass


def width(st, ang, i, j, c):
    """WIDTH: esquinas giradas (XC, YC), extremos y anchura y longitud proyectadas (TW, BL)."""
    csa = math.cos(ang)
    sna = -math.sin(ang)
    X, Y = st.X[i][j], st.Y[i][j]
    XC, YC = st.XC[c], st.YC[c]
    for k in range(1, st.ND[i][j] + 1):
        XC[k] = r4(X[k] * csa + Y[k] * sna)
        YC[k] = r4(Y[k] * csa - X[k] * sna)
        if k == 1:
            st.YMIN[c] = YC[1]
            st.YMAX[c] = YC[1]
            st.XMIN[c] = XC[1]
            st.XMAX[c] = XC[1]
        if YC[k] <= st.YMIN[c]:
            st.YMIN[c] = YC[k]
        if YC[k] >= st.YMAX[c]:
            st.YMAX[c] = YC[k]
        if XC[k] <= st.XMIN[c]:
            st.XMIN[c] = XC[k]
        if XC[k] >= st.XMAX[c]:
            st.XMAX[c] = XC[k]
    tw = r4(st.XMAX[c] - st.XMIN[c])
    bl = r4(st.YMAX[c] - st.YMIN[c])
    return tw, bl


def _anchos(st, ang, nb, NTRS, mxtrs):
    """WIDTH de todos los niveles para una dirección. El original repite la llamada para cada
    chimenea y cada nivel focal, con el mismo resultado: se calcula una vez (deja también XC,
    YC, XMIN… de cada nivel como las dejaría la última llamada)."""
    res = {}
    for i in range(1, nb + 1):
        for j in range(1, NTRS[i] + 1):
            c = (i - 1) * mxtrs + j
            res[c] = width(st, ang, i, j, c)
    return res


def gpc(st, d, i, c, s, tw, ws, hta, ch, ig):
    """GPC: altura de chimenea GEP (ecuación 1) y estructura que la determina."""
    hwe = r4(hta + st.BELEV[i] - st.SB[s] + 1.5 * ws)
    st.GEPIN[s][c][ch][ig] = 1
    if hwe > st.GEP[s]:
        _gpc_guarda(st, d, i, c, s, tw, hta, hwe)
    if hwe == st.GEP[s]:
        if tw < st.GEPBW[s]:
            _gpc_guarda(st, d, i, c, s, tw, hta, hwe)


def _gpc_guarda(st, d, i, c, s, tw, hta, hwe):
    st.GEP[s] = hwe
    st.GEPBH[s] = hta
    st.GEPBW[s] = tw
    st.GTNUM[s] = st.TNUM2[c]
    st.MI[s][1] = i
    st.MJ[s][1] = c - (i - 1) * st.MXTRS
    st.GDIRS[s] = r4(float(d) / 4)
    for m in range(1, st.GTNUM[s] + 1):
        st.GTLIST[s][m] = st.TLIST2[c][m]


def mxbwh(st, d, i, s, c, tw, hta, ws, tl1, ig, bl, xbadj, ybadj):
    """MXBWH: valores de downwash (altura, anchura, longitud, XBADJ, YBADJ) de la estructura
    con mayor efecto de estela para la chimenea y la dirección."""
    if st.GEPIN[s][c][tl1][ig] != 1:
        return
    mflg = 0
    pbh = hta
    pbw = tw
    pbl = bl
    hwe = r4(hta + st.BELEV[i] - st.SB[s] + 1.5 * ws)
    if st.DE != d:
        st.DE = d
        for ss in range(1, st.MSK + 1):
            st.DHWE[ss] = 0.0
            st.DPBH[ss] = 0.0
            st.DPBW[ss] = 0.0
            st.DPBL[ss] = 0.0
            st.DPADX[ss] = 0.0
            st.DPADY[ss] = 0.0
            st.MTNUM[ss][ig] = 0
            st.DFLG[ss][d] = 0
    if hwe - st.MHWE[s][d] > R4_0001:
        st.MHWE[s][d] = hwe
        st.MXPBH[s][d] = pbh
        st.MXPBW[s][d] = pbw
        st.MXPBL[s][d] = pbl
        st.MPADX[s][d] = xbadj
        st.MPADY[s][d] = ybadj
        mflg = 1
    # con estelas iguales se queda la de menor anchura proyectada
    if abs(hwe - st.MHWE[s][d]) < R4_0001:
        if pbw < st.MXPBW[s][d]:
            st.MHWE[s][d] = hwe
            st.MXPBH[s][d] = pbh
            st.MXPBW[s][d] = pbw
            st.MXPBL[s][d] = pbl
            st.MPADX[s][d] = xbadj
            st.MPADY[s][d] = ybadj
            mflg = 1
    # si la estela supera la altura GEP, se toman los valores GEP
    if st.GEP[s] < st.MHWE[s][d]:
        st.MHWE[s][d] = st.GEP[s]
        st.MXPBW[s][d] = st.GEPBW[s]
        st.MXPBH[s][d] = st.GEPBH[s]
        st.MXPBL[s][d] = pbl
        st.MPADX[s][d] = xbadj
        st.MPADY[s][d] = ybadj
        mflg = 1
    if mflg == 1:
        st.DFLG[s][d] = 1
        st.MTNUM[s][1] = st.TNUM2[c]            # el original usa siempre la columna 1 aquí
        st.MI[s][ig] = i
        st.MJ[s][ig] = c - (i - 1) * st.MXTRS
        for m in range(1, st.MTNUM[s][ig] + 1):
            st.MTLIST[s][m][ig] = st.TLIST2[c][m]
        mflg = 0
    if st.TNUM2[c] > 1:
        if hwe > st.DHWE[s]:
            mflg = 2
        if abs(hwe - st.DHWE[s]) < R4_0001 and pbw < st.DPBW[s]:
            mflg = 2
        if mflg == 2:
            st.DFLG[s][d] = 1
            st.DHWE[s] = hwe
            st.DPBW[s] = pbw
            st.DPBH[s] = pbh
            st.DPBL[s] = pbl
            st.DPADX[s] = xbadj
            st.DPADY[s] = ybadj
            mflg = 0
            st.MTNUM[s][ig] = st.TNUM2[c]
            st.MI[s][ig] = i
            st.MJ[s][ig] = c - (i - 1) * st.MXTRS
            for m in range(1, st.MTNUM[s][ig] + 1):
                st.MTLIST[s][m][ig] = st.TLIST2[c][m]


# ------------------------------------------------------------------------------------------
# programa principal
# ------------------------------------------------------------------------------------------
def ejecutar(f_entrada, f_salida, f_resumen, ahora=None):
    """Ejecuta BPIPPRM. Devuelve las líneas de pantalla."""
    pant = []
    o12 = Fichero(f_salida, "w", existente=False)
    o14 = Fichero(f_resumen, "w", existente=False)

    def w(f, num, *items):
        f.escribir(fwrite(FORMATOS[num], *items))

    def wl(f, *textos):
        """WRITE(u,*) de cadenas: un blanco delante y las cadenas seguidas."""
        f.escribir(" " + "".join(textos))

    def scr(*textos):
        pant.append(" " + "".join(textos))

    try:
        _programa(f_entrada, o12, o14, w, wl, scr, pant, ahora)
    finally:
        o12.volcar()
        o14.volcar()
    return pant


def _programa(f_entrada, o12, o14, w, wl, scr, pant, ahora):
    st = _Estado()
    inp = _Lector(f_entrada)
    MD, ML = 36, 16
    MT = MTS = 0
    st.DE = 0
    G65 = 65.0

    # ---- primera lectura: dimensiones
    title = fx(inp.leer([("a", 78)])[0], 78)
    w(o12, 1, title)
    w(o14, 1, title)
    inp.leer([("a", 2)])
    inp.leer([("a", 10), "f"])
    inp.leer([("a", 4), "f"])
    nb = inp.leer(["i"])[0]
    MB = nb
    for _ in range(nb):
        _, ntrsv, _ = inp.leer([("a", 8), "i", "f"])
        if ntrsv >= MT:
            MT = ntrsv
        for _ in range(ntrsv):
            ndv, _ = inp.leer(["i", "f"])
            if ndv >= MTS:
                MTS = ndv
            for _ in range(ndv):
                inp.leer(["f", "f"])
    MBT = MB * MT
    MXTRS = MT
    st.MXTRS = MXTRS
    ns = inp.leer(["i"])[0]
    MSK = ns
    st.MSK = MSK
    for _ in range(ns):
        inp.leer([("a", 8), "f", "f", "f", "f"])
    inp.rewind()

    # ---- matrices
    st.X = _matriz(MB, MT, MTS, val=0.0)
    st.Y = _matriz(MB, MT, MTS, val=0.0)
    st.ND = _matriz(MB, MT, val=0)
    st.XC = _matriz(MBT, MTS, val=0.0)
    st.YC = _matriz(MBT, MTS, val=0.0)
    st.DFLG = _matriz(MSK, MD, val=0)
    st.DHWE, st.DPBH, st.DPBL, st.DPBW = (_lista(MSK, 0.0) for _ in range(4))
    st.BELEV = _lista(MB, 0.0)
    st.GEP, st.GEPBH, st.GEPBW = (_lista(MSK, 0.0) for _ in range(3))
    st.GEPIN = _matriz(MSK, MBT, MBT, 2, val=0)
    st.MHWE, st.MXPBH, st.MXPBL, st.MXPBW = (_matriz(MSK, MD, val=0.0) for _ in range(4))
    st.XMAX, st.XMIN, st.YMAX, st.YMIN = (_lista(MBT, 0.0) for _ in range(4))
    st.MI = _matriz(MSK, 2, val=0)
    st.MJ = _matriz(MSK, 2, val=0)
    st.TNUM2 = _lista(MBT, 0)
    st.TLIST2 = _matriz(MBT, MBT, val=0)
    st.GTNUM = _lista(MSK, 0)
    st.GTLIST = _matriz(MSK, MBT, val=0)
    st.GDIRS = _lista(MSK, 0.0)
    st.MTNUM = _matriz(MSK, 2, val=0)
    st.MTLIST = _matriz(MSK, MBT, 2, val=0)
    BTN = _lista(MB, " " * 8)
    NTRS = _lista(MB, 0)
    W = _lista(MBT, 0.0)
    HT = _lista(MBT, 0.0)
    TH = _matriz(MB, MT, val=0.0)
    STKN = _lista(MSK, " " * 8)
    st.SB = SB = _lista(MSK, 0.0)
    SH = _lista(MSK, 0.0)
    XS = _lista(MSK, 0.0)
    YS = _lista(MSK, 0.0)
    DIRT = _lista(MTS, 0.0)
    DISTMN = _matriz(MBT, MBT, val=0.0)
    LFLAT = _matriz(MSK, MBT, val=0)
    TNUM = _lista(MBT, 0)
    TLIST = _matriz(MBT, MBT, val=0)
    MH, MW, MBL, MADX, MADY = (_matriz(MSK, ML, val=0.0) for _ in range(5))
    st.DPADX, st.DPADY = _lista(MSK, 0.0), _lista(MSK, 0.0)
    st.MPADX, st.MPADY = _matriz(MSK, MD, val=0.0), _matriz(MSK, MD, val=0.0)
    X, Y, ND, XC, YC = st.X, st.Y, st.ND, st.XC, st.YC
    XMAX, XMIN, YMAX, YMIN = st.XMAX, st.XMIN, st.YMAX, st.YMIN
    BELEV, GEPIN, TNUM2, TLIST2 = st.BELEV, st.GEPIN, st.TNUM2, st.TLIST2

    # ---- segunda lectura: datos
    scr(" ")
    scr("READING INPUT DATA FROM FILE.")
    scr(" ")
    title = fx(inp.leer([("a", 78)])[0], 78)
    t = ahora or _dt.datetime.now()
    iyr, imon, iday, ihr, imin, isec = t.year, t.month, t.day, t.hour, t.minute, t.second
    w(o12, 461)
    w(o12, 462, imon, iday, iyr)
    w(o12, 463, ihr, imin, isec)
    w(o12, 1, title)
    w(o14, 461)
    w(o14, 462, imon, iday, iyr)
    w(o14, 463, ihr, imin, isec)
    w(o14, 1, title)
    for f in (o12, o14):
        wl(f, "============================")
        wl(f, "BPIP PROCESSING INFORMATION:")
        wl(f, "============================")

    swtn = fx(inp.leer([("a", 2)])[0], 2)
    swt = 3
    c0 = swtn[0:1]
    if c0 in ("p", "P"):
        swt = 0
    if c0 in ("n", "N", "s", "S"):
        swt = 2
    if c0 in ("l", "L"):
        swt = 1
    if swt == 0:
        w(o12, 2, swtn)
        w(o14, 2, swtn)
    if swt == 1:
        w(o12, 9, swtn)
        w(o14, 9, swtn)
    if swt == 2:
        w(o12, 16, swtn)
        w(o14, 16, swtn)
    if swt == 3:
        scr("**ERR: The SWTN variable, ", swtn, " is", " incorrectly entered.")
        scr("         Please use P, NP, or L as input.")
        return

    unts, conv = inp.leer([("a", 10), "f"])
    unts = fx(unts, 10)
    conv = r4(conv)
    w(o12, 3, unts, conv)
    w(o14, 3, unts, conv)
    cnvflg = 1 if abs(conv - 1.00) < R4_005 else 0

    utmp, pnorth = inp.leer([("a", 4), "f"])
    utmp = fx(utmp, 4)
    pnorth = r4(pnorth)
    utm = 2
    if utmp[3:4] in ("n", "N"):
        utm = 0
    if utmp[3:4] in ("y", "Y"):
        utm = 1
    if utm == 1:
        w(o12, 4, utmp)
        w(o14, 4, utmp)
        w(o14, 11)
    else:
        w(o12, 5, utmp)
        w(o14, 5, utmp)
    if utm == 2:
        scr("The UTMP variable, ", utmp, " is incorrectly ", "entered.")
        return

    if pnorth == 360.0 or pnorth == 0.0:
        pn = 0
        w(o12, 17, pnorth)
        w(o14, 17, pnorth)
    else:
        pn = 1
        w(o12, 17, pnorth)
        w(o12, 297)
        w(o14, 17, pnorth)
        w(o14, 18)
        w(o14, 297)
    adj = r4(360.0 - pnorth)
    csa = sna = 0.0
    if pn == 1:
        adj = r4(adj * DTR)
        csa = r4(math.cos(adj))
        sna = r4(-math.sin(adj))

    w(o14, 297)
    wl(o14, "==============")
    wl(o14, "INPUT SUMMARY:")
    wl(o14, "==============")
    w(o14, 297)

    nb = inp.leer(["i"])[0]
    if nb > MB:
        scr("WARNING :")
        scr("THE NUMBER OF BUILDINGS ENTERED EXCEEDS THE ", "PARAMETER, MB")
        return
    w(o14, 6, nb)
    ueast = unorth = 0.0                     # sin UTM no se asignan (estáticas a cero en CVF)
    for i in range(1, nb + 1):
        btn, ntrs, belev = inp.leer([("a", 8), "i", "f"])
        BTN[i] = fx(btn, 8)
        NTRS[i] = ntrs
        BELEV[i] = r4(belev)
        if NTRS[i] > MT:
            scr("WARNING :")
            scr("THE NUMBER OF TIERS/BUILDING EXCEEDS THE ", "PARAMETER, MT")
            return
        w(o14, 12, BTN[i], NTRS[i], BELEV[i], unts)
        if cnvflg == 0:
            BELEV[i] = r4(BELEV[i] * conv)
            w(o14, 13, BELEV[i])
        w(o14, 14)
        for j in range(1, NTRS[i] + 1):
            nd, th = inp.leer(["i", "f"])
            ND[i][j] = nd
            TH[i][j] = r4(th)
            if ND[i][j] > MTS:
                scr("WARNING :")
                scr("THE NUMBER OF TIERS/BUILDING EXCEEDS THE ", "PARAMETER, MTS")
                return
            c = (i - 1) * MXTRS + j
            w(o14, 21, BTN[i], j, c, TH[i][j], ND[i][j])
            if cnvflg == 0:
                TH[i][j] = r4(TH[i][j] * conv)
                w(o14, 22, TH[i][j])
            for k in range(1, ND[i][j] + 1):
                aa, bb = inp.leer(["f", "f"])
                if cnvflg == 1 or utm == 1:
                    w(o14, 32, aa, bb)
                if cnvflg == 0 and utm == 0:
                    w(o14, 31, aa, bb, unts)
                    aa = aa * conv
                    bb = bb * conv
                    w(o14, 32, aa, bb)
                if utm == 1:
                    if i == 1 and j == 1 and k == 1:
                        ueast = aa
                        unorth = bb
                        au = bu = 0.0
                    else:
                        au = r4(aa - ueast)
                        bu = r4(bb - unorth)
                    w(o14, 33, au, bu)
                    X[i][j][k] = au
                    Y[i][j][k] = bu
                else:
                    X[i][j][k] = aa
                    Y[i][j][k] = bb
                if pn == 1:
                    ap = r4(X[i][j][k] * csa + Y[i][j][k] * sna)
                    bp = r4(Y[i][j][k] * csa - X[i][j][k] * sna)
                    X[i][j][k] = ap
                    Y[i][j][k] = bp
                    w(o14, 19, X[i][j][k], Y[i][j][k])

    ns = inp.leer(["i"])[0]
    if ns > MSK:
        scr("WARNING :")
        scr("THE NUMBER OF STACKS ENTERED EXCEEDS THE ", "PARAMETER, MKS")
        return
    w(o14, 41, ns)
    w(o14, 42)
    for s in range(1, ns + 1):
        stkn, sb, sh, aa, bb = inp.leer([("a", 8), "f", "f", "f", "f"])
        STKN[s] = fx(stkn, 8)
        SB[s] = r4(sb)
        SH[s] = r4(sh)
        w(o14, 43, STKN[s], SB[s], SH[s], unts)
        SB[s] = r4(SB[s] * conv)
        SH[s] = r4(SH[s] * conv)
        if cnvflg == 0:
            w(o14, 44, SB[s], SH[s])
        if cnvflg == 1 or utm == 1:
            w(o14, 51, aa, bb)
        if cnvflg == 0 and utm == 0:
            w(o14, 49, aa, bb, unts)
            aa = aa * conv
            bb = bb * conv
            w(o14, 45, aa, bb)
        au = r4(aa - ueast)
        bu = r4(bb - unorth)
        if utm == 1:
            w(o14, 45, au, bu)
        XS[s] = au
        YS[s] = bu
        if pn == 1:
            a = XS[s] * csa + YS[s] * sna
            b = YS[s] * csa - XS[s] * sna
            XS[s] = r4(a)
            YS[s] = r4(b)
            w(o14, 46, XS[s], YS[s])
        # blancos dentro del nombre de la chimenea
        snm = STKN[s]
        icf = isf = 0
        for ch_ in snm[:8]:
            if icf == 0:
                if ch_ != " ":
                    icf = 1
                    continue
            else:
                if isf == 0:
                    if ch_ == " ":
                        isf = 1
                        continue
                else:
                    if ch_ != " ":
                        w(o14, 47)
                        break

    # ---- chimeneas sobre el tejado de un nivel (posiblemente a más de 5L del borde)
    l5sqat = 0
    for ls in range(1, ns + 1):
        for lb in range(1, nb + 1):
            for lt in range(1, NTRS[lb] + 1):
                c = (lb - 1) * MXTRS + lt
                dirtt = 0.0
                salta = False
                for ld in range(1, ND[lb][lt] + 1):
                    if YS[ls] == Y[lb][lt][ld]:
                        if XS[ls] > X[lb][lt][ld]:
                            DIRT[ld] = 270.0
                        if XS[ls] < X[lb][lt][ld]:
                            DIRT[ld] = 90.0
                        if XS[ls] == X[lb][lt][ld]:
                            GEPIN[ls][c][c][1] = 1
                            LFLAT[ls][c] = 1
                            dirtt = 360.0
                            salta = True
                            break
                    else:
                        xcomp = X[lb][lt][ld] - XS[ls]
                        ycomp = Y[lb][lt][ld] - YS[ls]
                        DIRT[ld] = math.atan(xcomp / ycomp) / DTR2
                        if ycomp > 0.0:
                            DIRT[ld] = 360.0 + DIRT[ld]
                        if ycomp <= 0.0:
                            DIRT[ld] = 180.0 + DIRT[ld]
                        if DIRT[ld] > 360.0:
                            DIRT[ld] = DIRT[ld] - 360.0
                if not salta:
                    for ld in range(1, ND[lb][lt] + 1):
                        ld1 = ld
                        ld2 = ld + 1
                        if ld2 > ND[lb][lt]:
                            ld2 = 1
                        aa = DIRT[ld2] - DIRT[ld1]
                        if aa <= -180.0:
                            aa = 360.0 + aa
                        if aa > 180.0:
                            aa = aa - 360.0
                        dirtt = dirtt + aa
                if abs(360.0 - abs(dirtt)) < R4_002:
                    l5sqat += 1
                    if l5sqat == 1:
                        w(o14, 71)
                        w(o14, 72)
                    GEPIN[ls][c][c][1] = 1
                    LFLAT[ls][c] = 1
                    w(o14, 73, STKN[ls], ls, BTN[lb], lb, lt)
    if l5sqat == 0:
        wl(o14, " ")
        wl(o14, "   No stacks have been detected as being atop", " any structures.")

    scr(" ")
    scr("END OF READING INPUT DATA FROM FILE.")
    scr(" ")
    scr(" ")
    scr("CALCULATING GEP VALUES.")
    scr(" ")

    if swt == 0 or swt == 2:
        ddeg = 10.0
        ndir = MD
    else:
        ddeg = 11.25
        ndir = ML * 2
    nd16 = ML

    # ---- distancia mínima entre niveles de edificios distintos
    for i in range(1, nb):
        for ii in range(i + 1, nb + 1):
            for j in range(1, NTRS[i] + 1):
                for jj in range(1, NTRS[ii] + 1):
                    c1 = (i - 1) * MXTRS + j
                    c2 = (ii - 1) * MXTRS + jj
                    DISTMN[c1][c2] = 1000000.0
                    for k in range(1, ND[i][j] + 1):
                        x11 = r4(X[i][j][k])
                        y11 = r4(Y[i][j][k])
                        k1 = k + 1
                        if k1 > ND[i][j]:
                            k1 = 1
                        x12 = r4(X[i][j][k1])
                        y12 = r4(Y[i][j][k1])
                        for kk in range(1, ND[ii][jj] + 1):
                            x21 = r4(X[ii][jj][kk])
                            y21 = r4(Y[ii][jj][kk])
                            k2 = kk + 1
                            if k2 > ND[ii][jj]:
                                k2 = 1
                            x22 = r4(X[ii][jj][k2])
                            y22 = r4(Y[ii][jj][k2])
                            dist = r4(math.sqrt((x11 - x21) ** 2 + (y11 - y21) ** 2))
                            if dist < DISTMN[c1][c2]:
                                DISTMN[c1][c2] = dist
                            _, _, bet, dist = cnrlin(x21, y21, x22, y22, x11, y11)
                            if bet > R4_M0001:
                                if dist < DISTMN[c1][c2]:
                                    DISTMN[c1][c2] = dist
                            _, _, bet, dist = cnrlin(x11, y11, x12, y12, x21, y21)
                            if bet > R4_M0001:
                                if dist < DISTMN[c1][c2]:
                                    DISTMN[c1][c2] = dist
                    DISTMN[c2][c1] = DISTMN[c1][c2]

    # ---- GEP: niveles aislados, cada cuarto de grado
    if _usar_numba(nb, NTRS, ND, ns):
        _gep_numba(st, nb, ns, NTRS, TH, XS, YS, LFLAT, DISTMN, W, HT, scr, pant)
    else:
        scr("  Calculating single tier GEP values.")
        for d in range(1, 1441):
            ang = r4(d * DTR / 4)
            csa = r4(math.cos(ang))
            sna = r4(-math.sin(ang))
            for i in range(1, nb + 1):
                for j in range(1, NTRS[i] + 1):
                    c = (i - 1) * MXTRS + j
                    TNUM2[c] = 0
                    tw, bl = width(st, ang, i, j, c)
                    W[c] = tw
                    ws = tw
                    hta = TH[i][j]
                    if hta < tw:
                        ws = hta
                    l5 = r4(ws * 5)
                    cxmn = XMIN[c]
                    cxmx = XMAX[c]
                    cymx = r4(YMAX[c] + l5)
                    cymn = YMIN[c]
                    for s in range(1, ns + 1):
                        xpstk = r4(XS[s] * csa + YS[s] * sna)
                        ypstk = r4(YS[s] * csa - XS[s] * sna)
                        if cxmn <= xpstk <= cxmx and ypstk >= cymn:
                            for k in range(1, ND[i][j] + 1):
                                x1, y1 = XC[c][k], YC[c][k]
                                l_ = k + 1
                                if l_ > ND[i][j]:
                                    l_ = 1
                                x2, y2 = XC[c][l_], YC[c][l_]
                                ibet = dislin(x1, y1, x2, y2, l5, xpstk, ypstk)
                                if LFLAT[s][c] == 1:
                                    ibet = 1
                                if ibet == 1:
                                    TNUM2[c] = 1
                                    TLIST2[c][1] = c
                                    gpc(st, d, i, c, s, tw, ws, hta, c, 1)

        # ---- GEP: grupos de niveles combinables, cada cuarto de grado
        scr("  Looking for and calculating", " any group of tiers GEP values")
        scr("    for a wind flow starting at 0.25 degrees.")
        for d in range(1, 1441):
            ang = r4(d * DTR / 4)
            if math.fmod(r4(d / 4.0), 10.0) == 0.0:
                pant.extend(fwrite(FORMATOS[115], d // 4))
            csa = r4(math.cos(ang))
            sna = r4(-math.sin(ang))
            anchos = _anchos(st, ang, nb, NTRS, MXTRS)   # WIDTH no depende del nivel focal ni de la chimenea
            for i in range(1, nb + 1):
                for j in range(1, NTRS[i] + 1):
                    c1 = (i - 1) * MXTRS + j
                    tw, bl = anchos[c1]
                    W[c1] = tw
                    HT[c1] = TH[i][j]
                    TNUM[c1] = 1
                    TLIST[c1][1] = c1
                    for ii in range(1, nb + 1):
                        if i != ii:
                            for jj in range(1, NTRS[ii] + 1):
                                c2 = (ii - 1) * MXTRS + jj
                                tw, bl = anchos[c2]
                                W[c2] = tw
                                HT[c2] = TH[ii][jj]
                                r = min(W[c1], HT[c1])
                                if DISTMN[c1][c2] < r:
                                    TNUM[c1] += 1
                                    TLIST[c1][TNUM[c1]] = c2
                                else:
                                    r = min(W[c2], HT[c2])
                                    if DISTMN[c1][c2] < r:
                                        TNUM[c1] += 1
                                        TLIST[c1][TNUM[c1]] = c2
            for i in range(1, nb + 1):
                for j in range(1, NTRS[i] + 1):
                    c1 = (i - 1) * MXTRS + j
                    if TNUM[c1] <= 1:
                        continue
                    tn1 = TNUM[c1]
                    htc = HT[TLIST[c1][1]]
                    for t1 in range(1, tn1 + 1):
                        tl1 = TLIST[c1][t1]
                        hta = HT[TLIST[c1][t1]]
                        if not (hta < htc or c1 == tl1):
                            continue
                        TNUM2[c1] = 1
                        TLIST2[c1][1] = c1
                        xmn, ymn, xmx, ymx = XMIN[c1], YMIN[c1], XMAX[c1], YMAX[c1]
                        for t2 in range(1, tn1 + 1):
                            tl2 = TLIST[c1][t2]
                            if c1 != tl2 and HT[tl2] >= hta:
                                ltn1 = min(hta, W[c1])
                                ltn2 = min(hta, W[tl2])
                                ltn = max(ltn1, ltn2)
                                if DISTMN[c1][tl2] < ltn:
                                    TNUM2[c1] += 1
                                    TLIST2[c1][TNUM2[c1]] = tl2
                                    if XMIN[tl2] < xmn:
                                        xmn = XMIN[tl2]
                                    if XMAX[tl2] > xmx:
                                        xmx = XMAX[tl2]
                                    if YMIN[tl2] < ymn:
                                        ymn = YMIN[tl2]
                                    if YMAX[tl2] > ymx:
                                        ymx = YMAX[tl2]
                        tw = r4(xmx - xmn)
                        bl = r4(ymx - ymn)
                        ws = tw
                        if hta < tw:
                            ws = hta
                        l5 = r4(ws * 5)
                        cxmn, cxmx = xmn, xmx
                        cymx = r4(ymx + l5)
                        cymn = ymn
                        if TNUM2[c1] > 1:
                            for s in range(1, ns + 1):
                                xpstk = r4(XS[s] * csa + YS[s] * sna)
                                ypstk = r4(YS[s] * csa - XS[s] * sna)
                                if cxmn <= xpstk <= cxmx and ypstk >= cymn:
                                    _gep_grupo(st, d, i, j, c1, s, tw, ws, l5, hta, tl1, xpstk, ypstk, LFLAT)

    # ---- resultados GEP
    w(o12, 1, title)
    w(o12, 297)
    w(o12, 1005)
    w(o14, 1020)
    for s in range(1, ns + 1):
        if st.GTNUM[s] == 0:
            pv = G65
            w(o14, 1022, s, STKN[s], SH[s], pv, st.GEPBH[s], st.GEPBW[s], st.GEP[s])
            wl(o14, "     No tiers affect this stack.")
            w(o12, 1001, STKN[s], SH[s], st.GEP[s], pv)
        else:
            dif = r4(SB[s] - BELEV[st.MI[s][1]])
            pv = max(G65, st.GEP[s])
            w(o14, 1022, s, STKN[s], SH[s], pv, st.GEPBH[s], st.GEPBW[s], st.GEP[s])
            w(o14, 1025, dif)
            w(o14, 1023, st.GTNUM[s], st.GDIRS[s])
            w(o14, 1024, *[st.GTLIST[s][m] for m in range(1, st.GTNUM[s] + 1)])
            w(o12, 1000, STKN[s], SH[s], dif, st.GEP[s], pv)
        w(o14, 297)
    w(o12, 1007)
    w(o12, 297)
    w(o12, 297)

    # ---- downwash: niveles aislados
    scr(" ")
    scr("CALCULATING BUILDING DOWNWASH INPUT VALUES.")
    scr(" ")
    scr("  Calculating single tier downwash values.")
    w(o14, 2020)
    for d in range(1, ndir + 1):
        ang = r4(d * ddeg)
        w(o14, 604, ang)
        ang = r4(ang * DTR)
        csa = r4(math.cos(ang))
        sna = r4(-math.sin(ang))
        anchos = _anchos(st, ang, nb, NTRS, MXTRS)   # WIDTH no depende del nivel focal ni de la chimenea
        for s in range(1, ns + 1):
            xpstk = r4(XS[s] * csa + YS[s] * sna)
            ypstk = r4(YS[s] * csa - XS[s] * sna)
            for i in range(1, nb + 1):
                for j in range(1, NTRS[i] + 1):
                    c = (i - 1) * MXTRS + j
                    ch = c
                    TNUM2[c] = 1
                    hta = TH[i][j]
                    tw, bl = anchos[c]
                    ws = tw
                    if TH[i][j] < tw:
                        ws = TH[i][j]
                    l2 = r4(ws * 2)
                    l5 = r4(ws * 5)
                    cxmn = r4(XMIN[c] - ws / 2)
                    cxmx = r4(XMAX[c] + ws / 2)
                    cymx = r4(YMAX[c] + l5)
                    cymn = r4(YMIN[c] - l2)
                    if cxmn <= xpstk <= cxmx and ypstk >= cymn:
                        TLIST2[c][1] = c
                        ybadj = r4(xpstk - (XMIN[c] + tw * 0.5))
                        xbadj = r4(YMIN[c] - ypstk)
                        mxbwh(st, d, i, s, c, tw, hta, ws, ch, 1, bl, xbadj, ybadj)
        for s in range(1, ns + 1):
            w(o14, 2022, s, STKN[s], SH[s])
            w(o14, 2027, st.GEPBH[s], st.GEPBW[s], st.GEP[s])
            if st.MHWE[s][d] == 0.0:
                wl(o14, "    No single tier affects this stack for ", "this direction.")
            else:
                w(o14, 1026, st.MXPBH[s][d], st.MXPBW[s][d], st.MXPBL[s][d], st.MHWE[s][d],
                  st.MPADX[s][d], st.MPADY[s][d])
                dif = r4(SB[s] - BELEV[st.MI[s][1]])
                w(o14, 1025, dif)
                w(o14, 2028, st.MI[s][1], BTN[st.MI[s][1]], st.MJ[s][1])
    for iss in range(1, ns + 1):
        for d in range(1, ndir + 1):
            st.DFLG[iss][d] = 0

    # ---- downwash: grupos de niveles
    w(o14, 297)
    if nb == 1:
        wl(o14, "Dominant combined buildings:  None")
    else:
        scr("  Calculating group of tiers downwash values.")
        wl(o14, "Dominant combined buildings:")
    for d in range(1, ndir + 1):
        ang = r4(d * ddeg)
        if nb > 1:
            w(o14, 604, ang)
        ang = r4(ang * DTR)
        csa = r4(math.cos(ang))
        sna = r4(-math.sin(ang))
        anchos = _anchos(st, ang, nb, NTRS, MXTRS)   # WIDTH no depende del nivel focal ni de la chimenea
        for i in range(1, nb + 1):
            for j in range(1, NTRS[i] + 1):
                c1 = (i - 1) * MXTRS + j
                tw, bl = anchos[c1]
                W[c1] = tw
                TNUM[c1] = 1
                TLIST[c1][1] = c1
                for ii in range(1, nb + 1):
                    if i != ii:
                        for jj in range(1, NTRS[ii] + 1):
                            c2 = (ii - 1) * MXTRS + jj
                            tw, bl = anchos[c2]
                            W[c2] = tw
                            r = min(W[c1], HT[c1])
                            if DISTMN[c1][c2] < r:
                                TNUM[c1] += 1
                                TLIST[c1][TNUM[c1]] = c2
                            else:
                                r = min(W[c2], HT[c2])
                                if DISTMN[c1][c2] < r:
                                    TNUM[c1] += 1
                                    TLIST[c1][TNUM[c1]] = c2
        for i in range(1, nb + 1):
            for j in range(1, NTRS[i] + 1):
                c = (i - 1) * MXTRS + j
                if TNUM[c] <= 1:
                    continue
                tn1 = TNUM[c]
                htc = HT[TLIST[c][1]]
                for t1 in range(1, tn1 + 1):
                    tl1 = TLIST[c][t1]
                    hta = HT[TLIST[c][t1]]
                    ch = tl1
                    if not (hta <= htc or c == tl1):
                        continue
                    TNUM2[c] = 1
                    TLIST2[c][1] = c
                    xmn, ymn, xmx, ymx = XMIN[c], YMIN[c], XMAX[c], YMAX[c]
                    for t2 in range(1, tn1 + 1):
                        tl2 = TLIST[c][t2]
                        if c != tl2 and HT[tl2] >= hta:
                            ltn1 = min(hta, W[c])
                            ltn2 = min(hta, W[tl2])
                            ltn = max(ltn1, ltn2)
                            if DISTMN[c][tl2] < ltn:
                                TNUM2[c] += 1
                                TLIST2[c][TNUM2[c]] = tl2
                                if XMIN[tl2] < xmn:
                                    xmn = XMIN[tl2]
                                if XMAX[tl2] > xmx:
                                    xmx = XMAX[tl2]
                                if YMIN[tl2] < ymn:
                                    ymn = YMIN[tl2]
                                if YMAX[tl2] > ymx:
                                    ymx = YMAX[tl2]
                    tw = r4(xmx - xmn)
                    bl = r4(ymx - ymn)
                    ws = tw
                    if hta < tw:
                        ws = hta
                    l5 = r4(ws * 5)
                    l2 = r4(ws * 2)
                    cxmn = r4(xmn - ws / 2)
                    cxmx = r4(xmx + ws / 2)
                    cymx = r4(ymx + l5)
                    cymn = r4(ymn - l2)
                    if TNUM2[c] > 1:
                        for s in range(1, ns + 1):
                            xpstk = r4(XS[s] * csa + YS[s] * sna)
                            ypstk = r4(YS[s] * csa - XS[s] * sna)
                            if cxmn <= xpstk <= cxmx and ypstk >= cymn:
                                ybadj = r4(xpstk - (xmn + tw * 0.5))
                                xbadj = r4(ymn - ypstk)
                                mxbwh(st, d, i, s, c, tw, hta, ws, ch, 2, bl, xbadj, ybadj)
        if nb > 1:
            for s in range(1, ns + 1):
                w(o14, 2022, s, STKN[s], SH[s])
                w(o14, 2027, st.GEPBH[s], st.GEPBW[s], st.GEP[s])
                if st.MTNUM[s][2] < 2:
                    wl(o14, "     No combined tiers affect this stack ", "for this direction.")
                else:
                    if st.DFLG[s][d] == 1:
                        w(o14, 2026, st.DPBH[s], st.DPBW[s], st.DPBL[s], st.DHWE[s], st.DPADX[s], st.DPADY[s])
                        dif = r4(SB[s] - BELEV[st.MI[s][2]])
                        w(o14, 1025, dif)
                        w(o14, 2023, st.MTNUM[s][2])
                        w(o14, 2024, *[st.MTLIST[s][m][2] for m in range(1, st.MTNUM[s][2] + 1)])
                    else:
                        wl(o14, "     No combined tiers affect this stack ", "for this direction")

    # ---- salida para el modelo
    if swt == 0 or swt == 2:
        w(o12, 461)
        w(o12, 462, imon, iday, iyr)
        w(o12, 463, ihr, imin, isec)
        w(o12, 297)
        w(o12, 1, title)
        wl(o12, " BPIP output is in meters")
        for s in range(1, ns + 1):
            w(o12, 297)
            bloques = [(293, st.MXPBH), (296, st.MXPBW)]
            if swt == 0:
                bloques += [(299, st.MXPBL), (290, st.MPADX), (291, st.MPADY)]
            for num, M in bloques:
                for i in range(1, 7):
                    j = (i - 1) * 6 + 1
                    k = i * 6
                    w(o12, num, STKN[s], *[M[s][d] for d in range(j, k + 1)])
    if swt == 1:
        for s in range(1, ns + 1):
            l_ = 1
            for d in range(2, ndir + 1, 2):
                l_ += 1
                i = d - 1
                j = d + 1
                if l_ > ML:
                    l_ -= ML
                if j > ndir:
                    j -= ndir
                if st.MHWE[s][d] > 0.0:
                    iz = d
                else:
                    iz = i if st.MHWE[s][i] > st.MHWE[s][j] else j
                MH[s][l_] = st.MXPBH[s][iz]
                MW[s][l_] = st.MXPBW[s][iz]
                MBL[s][l_] = st.MXPBL[s][iz]
                MADX[s][l_] = st.MPADX[s][iz]
                MADY[s][l_] = st.MPADY[s][iz]
        w(o12, 461)
        w(o12, 462, imon, iday, iyr)
        w(o12, 463, ihr, imin, isec)
        w(o12, 297)
        for s in range(1, ns + 1):
            w(o12, 297)
            for num, M in ((293, MH), (296, MW)):
                for i in range(1, 3):
                    j = (i - 1) * 6 + 1
                    k = i * 6
                    w(o12, num, STKN[s], *[M[s][d] for d in range(j, k + 1)])
                w(o12, num, STKN[s], *[M[s][d] for d in range(k + 1, ML + 1)])
    scr(" ")
    scr("END OF BPIP RUN.")
    scr(" ")
    _ = nd16


UMBRAL_NUMBA = 1500     # niveles² · esquinas · (chimeneas + 1): por debajo, cargar numba no compensa


def _usar_numba(nb, NTRS, ND, ns):
    modo = os.environ.get("BPIP_NUMBA", "")
    if modo == "0":
        return False
    nt = sum(NTRS[1:nb + 1])
    nc = max((ND[i][j] for i in range(1, nb + 1) for j in range(1, NTRS[i] + 1)), default=0)
    if modo != "1" and nt * nt * nc * (ns + 1) < UMBRAL_NUMBA:
        return False
    from . import gep_rapido
    return gep_rapido.HAY_NUMBA


def _gep_numba(st, nb, ns, NTRS, TH, XS, YS, LFLAT, DISTMN, W, HT, scr, pant):
    """Los dos bucles GEP de 1.440 direcciones con gep_rapido (numba): mismo resultado que la
    versión escalar de _programa."""
    import numpy as np

    from . import gep_rapido as g
    MB, MT, MTS = len(st.X) - 1, len(st.X[0]) - 1, len(st.X[0][0]) - 1
    MBT, MSK = len(st.XC) - 1, st.MSK
    f8 = lambda a: np.array(a, dtype=np.float64)
    i8 = lambda a: np.array(a, dtype=np.int64)
    X, Y, ND = f8(st.X), f8(st.Y), i8(st.ND)
    ntrs, th, belev, sb = i8(NTRS), f8(TH), f8(st.BELEV), f8(st.SB)
    xs, ys, lflat, distmn = f8(XS), f8(YS), i8(LFLAT), f8(DISTMN)
    csa32 = np.zeros(1441)
    sna32 = np.zeros(1441)
    csaw = np.zeros(1441)
    snaw = np.zeros(1441)
    for d in range(1, 1441):
        ang = r4(d * DTR / 4)
        csa32[d] = r4(math.cos(ang))
        sna32[d] = r4(-math.sin(ang))
        csaw[d] = math.cos(ang)
        snaw[d] = -math.sin(ang)
    XC = np.zeros((MBT + 1, MTS + 1))
    YC = np.zeros((MBT + 1, MTS + 1))
    XMAX, XMIN, YMAX, YMIN = (np.zeros(MBT + 1) for _ in range(4))
    w, ht = f8(W), f8(HT)
    TNUM = np.zeros(MBT + 1, dtype=np.int64)
    TNUM2 = np.zeros(MBT + 1, dtype=np.int64)
    TLIST = np.zeros((MBT + 1, MBT + 1), dtype=np.int64)
    TLIST2 = np.zeros((MBT + 1, MBT + 1), dtype=np.int64)
    GEPIN = np.array(st.GEPIN, dtype=np.int8)
    G = np.zeros((MSK + 1, 4))
    GI = np.zeros((MSK + 1, 3 + MBT), dtype=np.int64)
    scr("  Calculating single tier GEP values.")
    g.gep_niveles(X, Y, ND, ntrs, th, belev, sb, xs, ys, lflat, st.MXTRS, nb, ns,
                  csa32, sna32, csaw, snaw, XC, YC, XMAX, XMIN, YMAX, YMIN, w, TNUM2, TLIST2, GEPIN, G, GI)
    scr("  Looking for and calculating", " any group of tiers GEP values")
    scr("    for a wind flow starting at 0.25 degrees.")
    g.gep_grupos(X, Y, ND, ntrs, th, belev, sb, xs, ys, lflat, distmn, st.MXTRS, nb, ns,
                 csa32, sna32, csaw, snaw, XC, YC, XMAX, XMIN, YMAX, YMIN, w, ht, TNUM, TLIST,
                 TNUM2, TLIST2, GEPIN, G, GI)
    for d in range(40, 1441, 40):
        pant.extend(fwrite(FORMATOS[115], d // 4))
    # resultados de vuelta al estado del programa
    for s in range(1, MSK + 1):
        st.GEP[s], st.GEPBH[s], st.GEPBW[s], st.GDIRS[s] = (float(v) for v in G[s])
        st.GTNUM[s] = int(GI[s, 0])
        st.MI[s][1] = int(GI[s, 1])
        st.MJ[s][1] = int(GI[s, 2])
        for m in range(1, MBT + 1):
            st.GTLIST[s][m] = int(GI[s, 2 + m])
    st.GEPIN = GEPIN.tolist()
    for c in range(1, MBT + 1):
        W[c] = float(w[c])
        HT[c] = float(ht[c])
    _ = (MB, MT)


def _gep_grupo(st, d, i, j, c1, s, tw, ws, l5, hta, tl1, xpstk, ypstk, LFLAT):
    """Etiquetas 131-136 del original: ¿la chimenea está a 5L o menos de un lado del nivel
    focal, de otro nivel del grupo o de la estructura que rellena el hueco entre ambos?"""
    XC, YC, ND = st.XC, st.YC, st.ND
    for k in range(1, ND[i][j] + 1):
        l_ = k + 1
        if l_ > ND[i][j]:
            l_ = 1
        ibet = dislin(XC[c1][k], YC[c1][k], XC[c1][l_], YC[c1][l_], l5, xpstk, ypstk)
        if LFLAT[s][c1] == 1:
            ibet = 1
        if ibet == 1:
            gpc(st, d, i, c1, s, tw, ws, hta, tl1, 2)
            return
    ibet = 0
    for m in range(2, st.TNUM2[c1] + 1):
        c2 = st.TLIST2[c1][m]
        ii = int((c2 - 1) / st.MXTRS) + 1
        jj = c2 - (ii - 1) * st.MXTRS
        for k in range(1, ND[ii][jj] + 1):
            l_ = k + 1
            if l_ > ND[ii][jj]:
                l_ = 1
            ibet = dislin(XC[c2][k], YC[c2][k], XC[c2][l_], YC[c2][l_], l5, xpstk, ypstk)
            if LFLAT[s][c2] == 1:
                ibet = 1
            if ibet == 1:
                gpc(st, d, i, c1, s, tw, ws, hta, tl1, 2)
                return
        for k in range(1, ND[i][j] + 1):
            x11, y11 = XC[c1][k], YC[c1][k]
            k1 = k + 1
            if k1 > ND[i][j]:
                k1 = 1
            x12, y12 = XC[c1][k1], YC[c1][k1]
            for l_ in range(1, ND[ii][jj] + 1):
                x21, y21 = XC[c2][l_], YC[c2][l_]
                k2 = l_ + 1
                if k2 > ND[ii][jj]:
                    k2 = 1
                x22, y22 = XC[c2][k2], YC[c2][k2]
                dist = r4(math.sqrt((x11 - x21) ** 2 + (y11 - y21) ** 2))
                if dist <= ws:
                    ibet = dislin(x11, y11, x21, y21, l5, xpstk, ypstk)
                    if dist <= l5 and ibet == 1:
                        gpc(st, d, i, c1, s, tw, ws, hta, tl1, 2)
                        return
                xi, yi, bet, dist = cnrlin(x11, y11, x12, y12, x21, y21)
                if dist <= ws and bet > R4_M0001:
                    ibet = dislin(x21, y21, xi, yi, l5, xpstk, ypstk)
                    if dist <= l5 and ibet == 1:
                        gpc(st, d, i, c1, s, tw, ws, hta, tl1, 2)
                        return
                xi, yi, bet, dist = cnrlin(x21, y21, x22, y22, x11, y11)
                if dist <= ws and bet > R4_M0001:
                    ibet = dislin(x11, y11, xi, yi, l5, xpstk, ypstk)
                    if dist <= l5 and ibet == 1:
                        gpc(st, d, i, c1, s, tw, ws, hta, tl1, 2)
                        return
