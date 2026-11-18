# -*- coding: utf-8 -*-
"""Traducción de AERMAP v24142 (US EPA, dominio público): ficheros de resultados
(aermap.f: SRCOUT, WRITER, RECOUT, WRITE_INCLUD, WRITGC, WRITGP, WRITRZ, WRITDC, WRITEV,
WRITDP) y resumen del fichero de salida (INPSUM).

WRITER vuelve a leer el fichero de control y reescribe la vía RE con las cotas y alturas de
colina calculadas: las líneas STA/XYINC/DIST... se copian tal cual, las ELEV/FLAG de la
entrada no se copian y se sustituyen por las calculadas."""
from .control import cargar, define, exkey, expath, feq, getfld, kw, leer_lineas
from .estado import VERSN, fa, fx
from .formato import stodbl, nint
from .mensajes import NADN


def ff(x, w, d):
    """Fw.d de gfortran."""
    s = f"{x:.{d}f}"
    if len(s) > w:
        if s.startswith("0.") and len(s) - 1 <= w:
            s = s[1:]
        elif s.startswith("-0.") and len(s) - 1 <= w:
            s = "-" + s[2:]
        else:
            return "*" * w
    return s.rjust(w)


def _cab_version(e):
    return [f"** AERMAP - VERSION {VERSN}".ljust(71) + fa(e.rundat, 8),
            "**".ljust(71) + fa(e.runtim, 8)]


def _cabecera(e, n, que, ancho):
    L = _cab_version(e)
    L.append("** " + e.title1.rstrip(" "))
    L.append("** " + e.title2.rstrip(" "))
    td = e.typdat[:3]
    L.append(f"** A total of {n_dem(e):{ancho}d}  {td} files were used")
    L.append(f"** A total of {n:{ancho}d}  {que} were processed")
    if e.gotdomflg:
        L.append("** " + e.domcard.rstrip(" "))
        if e.domfix:
            L.append("** DOMAINLL was adjusted for Negative West Longitude:")
            L.append("** " + e.domadj.rstrip(" "))
    else:
        L.append("** No user-specifed DOMAIN; all available data used")
    L.append("** " + e.anchcrd.rstrip(" "))
    if e.hgtcard.ljust(11)[:11] != " " * 11:
        L.append("** " + e.hgtcard.rstrip(" "))
    else:
        L.append("** Terrain heights were extracted by default")
    if td == "NED":
        nuser = sum(1 for i in range(1, e.numdem + 1) if e.l_userelevunits[i])
        if nuser > 0:
            L.append(f"** User-specified elevation units for  {nuser:5d} NED files")
    return L


def n_dem(e):
    return e.numdem


# ====================================================================================== SRCOUT
def srcout(e):
    L = _cabecera(e, e.numsrc, "sources", 6)
    if e.nsmiss > 0:
        L.append(f"** NOTE:  A total of {e.nsmiss:7d}  sources were located within data gaps")
        L.append("**        and assigned missing elevations (-9999.0)!")
    if e.nsgap2 > 0 or e.nsgap_in > 0 or e.nsmiss > 0 or e.nsfilled > 0:
        L += ["**", "** NOTE:"]
    if e.nsgap2 > 0:
        L.append(f"**   This run includes: {e.nsgap2:7d}  Source(s) located in GAPS BETWEEN "
                 "files due to NAD shifts;")
        L.append("**" + " " * 41 + "but ALL have been assigned to the closest file.")
    if e.nsgap_in > 0:
        L.append(f"**   This run includes: {e.nsgap_in:7d}  Source(s) located in GAPS INSIDE file(s);")
        L.append(f"**     with a total of: {e.nssubs:7d}  Source(s) assigned elevations based on "
                 "subsequent file(s).")
    if e.nsmiss > 0:
        L.append(f"**   This run includes: {e.nsmiss:7d}  Source(s) assigned missing elevations "
                 "(-9999.0)!")
    if e.nsfilled > 0:
        L.append(f"**   This run includes: {e.nsfilled:7d}  Source(s) located in gaps and "
                 "assigned non-missing elevations")
        L.append("**" + " " * 41 + "based on the closest nodes under the FILLGAPS option!")
    L.append("  ")
    if not e.runerr:
        L.append("SO ELEVUNIT METERS")
        for i in range(1, e.numsrc + 1):
            st = e.srctyp[i].rstrip()
            if st in ("LINE", "RLINE", "BUOYLINE"):
                vals = (e.ax1s[i], e.ay1s[i], e.ax2s[i], e.ay2s[i], e.azs[i])
            else:
                vals = (e.axs[i], e.ays[i], e.azs[i])
            L.append("SO LOCATION  " + fx(e.srcid[i], 12) + "  " + fx(e.srctyp[i], 8)
                     + "".join("  " + ff(v, 12, 2) for v in vals))
    _escribir(e.srcfil or "fort.9", L)


# ====================================================================================== WRITER
def writer(e):
    """WRITER: relee el control y escribe el fichero RECEPTOR."""
    e.iline = 0
    e._rec = []
    for linea in leer_lineas(e.inpfil):
        e.iline += 1
        cargar(e, linea)
        define(e)
        getfld(e)
        if e.bline:
            continue
        if feq(e.field[1], "NO") and feq(e.field[2], "ECHO"):
            continue
        if expath(e, e.field[1]) or e.path == "**":
            continue
        if exkey(e, e.field[2]):
            e.pkeywd = e.keywrd
            continue
        e.ppath = e.path
        e.ippnum = e.ipnum
        if e.path == "RE":
            recout(e)
        e.pkeywd = e.keywrd
        if e.path == "RE" and kw(e) == "FINISHED":
            break
    if e._rec:
        _escribir(e.recfil or "fort.8", e._rec)


def _escribir(ruta, lineas):
    with open(ruta, "w", encoding="latin-1", newline="\r\n") as f:
        for l in lineas:
            f.write(l + "\n")


def recout(e, en_incluido=False):
    m = "RECOUT"
    w = e._rec.append
    k = kw(e)
    if e.runerr and k != "STARTING":
        return
    if k == "STARTING" and not en_incluido:
        e._rec += _cabecera(e, e.numrec, "receptors", 7)
        if e.nrgap2 > 0 or e.nrgap_in > 0 or e.nrmiss > 0 or e.nrfilled > 0:
            e._rec += ["**", "** NOTE:"]
        if e.nrgap2 > 0:
            w(f"**   This run includes: {e.nrgap2:7d}  Receptor(s) located in GAPS BETWEEN "
              "files due to NAD shifts;")
            w("**" + " " * 43 + "but ALL have been assigned to the closest file.")
        if e.nrgap_in > 0:
            w(f"**   This run includes: {e.nrgap_in:7d}  Receptor(s) located in GAPS INSIDE file(s);")
            w(f"**     with a total of: {e.nrsubs:7d}  Receptor(s) assigned elevations based "
              "on subsequent file(s).")
        if e.nrmiss > 0:
            w(f"**   This run includes: {e.nrmiss:7d}  Receptor(s) assigned missing elevations "
              "and hill heights (-9999.0)!")
        if e.nrfilled > 0:
            w(f"**   This run includes: {e.nrfilled:7d}  Receptor(s) located in gaps and "
              "assigned non-missing elevations")
            w("**" + " " * 43 + "based on the closest nodes under the FILLGAPS option!")
        w("  ")
        if e.runerr:
            return
        w("RE ELEVUNIT METERS")
        e.innet = 0
        e.numrec = 0
        e.numarc = 0
        e.irxr = e.iryr = e.irze = e.irhz = e.irzf = 0
        e.ista = False
    elif k == "GRIDCART":
        writgc(e)
    elif k == "GRIDPOLR":
        writgp(e)
    elif k == "DISCCART":
        writdc(e)
    elif k == "DISCPOLR":
        writdp(e)
    elif k == "ELEVUNIT":
        pass
    elif k == "EVALCART":
        writev(e)
    elif k == "INCLUDED" and not en_incluido:
        e.ilsave = e.iline
        write_includ(e)
        e.iline = e.ilsave
    elif k == "FINISHED":
        e.numrec = e.irxr
    elif not en_incluido or k not in ("STARTING", "INCLUDED"):
        e.errhdl(e.path, "WRITE_INCLUD" if en_incluido else m, "E", "110", e.keywrd)


def write_includ(e):
    m = "WRITE_INCLUD"
    e.iline = 1
    lineas = []
    if e.ifc == 3:
        if e.loce[3] - e.locb[3] <= 199:
            nombre = e.runst1[e.locb[3] - 1:e.loce[3]]
            try:
                lineas = leer_lineas(nombre)
            except OSError:
                e.errhdl(e.path, m, "E", "500", "INCFILE ")
                return
        else:
            e.errhdl(e.path, m, "E", "210", f"{200:8d}")
            return
    elif e.ifc > 4:
        e.errhdl(e.path, m, "E", "202", e.keywrd)
    else:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
    for linea in lineas:
        e.iline += 1
        e.ilreal_winc += 1
        cargar(e, linea)
        define(e)
        if e.ilreal_winc == 1:
            e.iline -= 1
        getfld(e)
        if e.bline:
            continue
        if feq(e.field[1], "NO") and feq(e.field[2], "ECHO"):
            continue
        if expath(e, e.field[1]):
            e.path = e.ppath
            continue
        elif e.path == "**":
            continue
        if exkey(e, e.field[2]):
            e.pkeywd = e.keywrd
            continue
        k = kw(e)
        if k in ("GRIDCART", "GRIDPOLR", "DISCCART", "DISCPOLR", "ELEVUNIT", "EVALCART",
                 "FINISHED"):
            recout(e, en_incluido=True)
        else:
            e.errhdl(e.path, m, "E", "110", e.keywrd)
        e.pkeywd = e.keywrd
    e.iline += 1
    e.ilreal_winc += 1


def _netid_w(e, claves, m):
    """Cabecera común de WRITGC/WRITGP -> idst o None."""
    e.netidt = fx(e.field[3], 8)
    if not e.newid and (e.netidt.rstrip() == "" or e.netidt.rstrip() in claves):
        e.netidt = e.pnetid
        e.ktype = fx(e.field[3], 5)
        return 4
    if not e.newid and e.netidt == e.pnetid:
        e.ktype = fx(e.field[4], 5)
        return 5
    if e.newid and e.netidt.rstrip() != "":
        e.newid = False
        e.ktype = fx(e.field[4], 5)
        e.innet += 1
        if e.innet > e.nnet:
            e.errhdl(e.path, m, "E", "224", f"{e.nnet:8d}")
            e.recerr = True
            return None
        e.incset = e.ixyset = e.ievset = e.ifgset = 0
        return 5
    e.errhdl(e.path, m, "E", "170", e.pnetid)
    e.recerr = True
    return None


def _eco(e):
    e._rec.append(e.runst1.rstrip(" "))


def writgc(e):
    m = "WRITGC"
    if e.ifc < 3:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        return
    idst = _netid_w(e, ("XYINC", "XPNTS", "YPNTS", "ELEV", "FLAG", "END"), m)
    if idst is None:
        return
    kt = e.ktype.rstrip()
    if kt == "STA":
        _eco(e)
        e.ista = True
        e.iend = False
        e.newid = False
        e.recerr = False
        e.icount = e.jcount = 0
        e.ize = e.izf = 0
        e.idc1 = e.irxr
        e.irxt = e.iryt = 0
    elif kt == "XYINC":
        _eco(e)
        for i in range(1, e.ifc + 1):
            if feq(e.field[i], "XYINC"):
                e.isc = i + 1
        t2, e.mitl = stodbl(e.field[e.isc + 1], 200, getattr(e, "_wgc_t2", 0.0))
        e._wgc_t2 = t2
        if e.mitl == -1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
            e.recerr = True
        t5, e.mitl = stodbl(e.field[e.isc + 4], 200, getattr(e, "_wgc_t5", 0.0))
        e._wgc_t5 = t5
        if e.mitl == -1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
            e.recerr = True
        e.irxt = nint(t2)
        e.iryt = nint(t5)
    elif kt in ("XPNTS", "YPNTS"):
        _eco(e)
        if kt == "XPNTS":
            e.irxt = e.irxt + e.ifc - idst + 1
        else:
            e.iryt = e.iryt + e.ifc - idst + 1
    elif kt in ("ELEV", "FLAG"):
        pass
    elif kt == "END":
        e.irlas = e.irxt * e.iryt
        writrz(e)
        _eco(e)
        e.iend = True
        e.ista = False
        e.newid = True
    else:
        e.errhdl(e.path, m, "E", "170", e.netidt)
        e.recerr = True
        return
    e.pnetid = e.netidt


def writgp(e):
    m = "WRITGP"
    idst = _netid_w(e, ("ORIG", "DIST", "DDIR", "ELEV", "FLAG", "GDIR", "END"), m)
    if idst is None:
        return
    kt = e.ktype.rstrip()
    if kt == "STA":
        _eco(e)
        e.ista = True
        e.iend = False
        e.newid = False
        e.recerr = False
        e.icount = e.jcount = 0
        e.ize = e.izf = 0
        e.idc1 = e.irxr
        e.irxt = e.iryt = 0
    elif kt == "ORIG":
        _eco(e)
    elif kt == "DIST":
        e.irxt = e.irxt + e.ifc - idst + 1
        _eco(e)
    elif kt == "GDIR":
        for i in range(1, e.ifc + 1):
            if feq(e.field[i], "GDIR"):
                e.isc = i + 1
        prev = getattr(e, "_wgp_t", [0.0] * 4)
        t = list(prev)
        for k in range(1, 4):
            t[k], e.mitl = stodbl(e.field[e.isc + k - 1], 200, prev[k])
            if e.mitl == -1:
                e.errhdl(e.path, m, "E", "208", e.keywrd)
        e._wgp_t = t
        e.jcount = nint(t[1])
        e.iryt = e.jcount
        _eco(e)
    elif kt == "DDIR":
        e.iryt = e.iryt + e.ifc - idst + 1
        _eco(e)
    elif kt in ("ELEV", "FLAG"):
        pass
    elif kt == "END":
        e.irlas = e.irxt * e.iryt
        writrz(e)
        _eco(e)
        e.iend = True
        e.ista = False
        e.newid = True
    else:
        e.errhdl(e.path, m, "E", "170", e.netidt)
        e.recerr = True
        return
    e.pnetid = e.netidt


def writrz(e):
    """WRITRZ: ELEV, HILL (y FLAG si hay FLAGPOLE) de la red, 6 valores por línea."""
    ifir = e.irxr + 1
    nlin = int((e.irxt - 1) / 6) + 1
    leftov = e.irxt % 6 if e.irxt >= 0 else -((-e.irxt) % 6)
    k8, n8 = fx(e.keywrd, 8), fx(e.netidt, 8)
    bloques = [("ELEV ", e.azelev), ("HILL ", e.azhill)]
    if e.flgpol:
        bloques.append(("FLAG ", e.azflag))
    for etiqueta, vec in bloques:
        ifin = 0
        for j in range(1, e.iryt + 1):
            for iln in range(1, nlin + 1):
                nitm = leftov if (iln == nlin and leftov != 0) else 6
                ibeg = ifir if (iln == 1 and j == 1) else ifin + 1
                ifin = ibeg + nitm - 1
                vals = "".join(" " + ff(vec[i] if i < len(vec) else 0.0, 8, 1)
                               for i in range(ibeg, ifin + 1))
                e._rec.append(f"   {k8} {n8} {etiqueta}{j:4d}{vals}")
    e.irxr = e.irxr + e.irlas
    e.iryr = e.irze = e.irzf = e.irhz = e.irxr


def writdc(e):
    i1, i2, i3, i4, i5 = e.irxr, e.iryr, e.irze, e.irzf, e.irhz
    s = (f"   DISCCART  {ff(e.axr[i1 + 1], 12, 2)} {ff(e.ayr[i2 + 1], 12, 2)}"
         f" {ff(e.azelev[i3 + 1], 10, 2)} {ff(e.azhill[i5 + 1], 10, 2)}")
    if e.flgpol:
        s += f" {ff(e.azflag[i4 + 1], 10, 2)}"
    e._rec.append(s)
    e.irxr, e.iryr, e.irze, e.irzf, e.irhz = i1 + 1, i2 + 1, i3 + 1, i4 + 1, i5 + 1


def writev(e):
    i1, i2, i3, i4, i5 = e.irxr, e.iryr, e.irze, e.irzf, e.irhz
    e._rec.append(f"   EVALCART  {ff(e.axr[i1 + 1], 12, 2)} {ff(e.ayr[i2 + 1], 12, 2)}"
                  f" {ff(e.azelev[i3 + 1], 10, 2)} {ff(e.azhill[i5 + 1], 10, 2)}"
                  f" {ff(e.azflag[i4 + 1], 10, 2)} {fx(e.arcid[e.ndxarc[i1 + 1]], 8)}"
                  f" {fx(e.recnam[i1 + 1], 8)}")
    e.irxr, e.iryr, e.irze, e.irzf, e.irhz = i1 + 1, i2 + 1, i3 + 1, i4 + 1, i5 + 1


def writdp(e):
    m = "WRITDP"
    i1, i2, i3, i4, i5 = e.irxr, e.iryr, e.irze, e.irzf, e.irhz
    if e.loce[3] - e.locb[3] <= 11:
        soid = fx(e.field[3], 12)
    else:
        e.errhdl(e.path, m, "E", "206", e.field[3][:12])
        e.recerr = True
        return
    rng, imit = stodbl(e.field[4], 200, getattr(e, "_wdp_range", 0.0))
    e._wdp_range = rng
    if imit == -1:
        e.errhdl(e.path, m, "E", "208", e.keywrd)
    direct, imit = stodbl(e.field[5], 200, getattr(e, "_wdp_direct", 0.0))
    e._wdp_direct = direct
    if imit == -1:
        e.errhdl(e.path, m, "E", "208", e.keywrd)
    s = (f"   DISCPOLR {soid}  {ff(rng, 12, 2)} {ff(direct, 12, 2)}"
         f" {ff(e.azelev[i3 + 1], 10, 2)} {ff(e.azhill[i5 + 1], 10, 2)}")
    if e.flgpol:
        s += f" {ff(e.azflag[i4 + 1], 10, 2)}"
    e._rec.append(s)
    e.irxr, e.iryr, e.irze, e.irzf, e.irhz = i1 + 1, i2 + 1, i3 + 1, i4 + 1, i5 + 1


# ====================================================================================== INPSUM
def inpsum(e):
    w = e.out.append
    td = e.typdat[:3]
    w("")
    w("")
    w(" " * 44 + "***     AERMAP SETUP OPTIONS SUMMARY       ***")
    w(" -" * 63)
    w("")
    w("  ")
    w(f" **This Run Includes: {e.numdem:7d}  {td} File(s)")
    w("  ")
    w(f" **This Run Includes: {e.numrec:7d}  Receptor(s); and  {e.numsrc:7d}  Source(s)")
    if e.gapsfound or e.gapsfound_in:
        w("  ")
        w(" NOTE:")
        if e.gapsfound and not e.fatal:
            w(f" **This run includes: {e.nrgap2:7d}  Receptor(s); and  {e.nsgap2:7d}  Source(s) "
              f"located in GAPS BETWEEN {td} files due to NAD shifts,")
            w(" " * 68 + f"but ALL have been assigned to the closest {td} file.")
        elif e.gapsfound and e.fatal:
            w(f" **This run includes: {e.nrgap2:7d}  Receptor(s); and  {e.nsgap2:7d}  Source(s) "
              f"located in GAPS BETWEEN {td} files due to NAD shifts,")
            w(" " * 68 + f"but some may NOT have been assigned to another {td} file.")
        if e.gapsfound_in:
            w(f" **This run includes: {e.nrgap_in:7d}  Receptor(s); and  {e.nsgap_in:7d}  "
              f"Source(s) located in GAPS INSIDE {td} file(s);")
            w(f"     with a total of: {e.nrsubs:7d}  Receptor(s); and  {e.nssubs:7d}  Source(s) "
              "assigned elevations based on subsequent file(s).")
        if e.missfound:
            w(f" **This run includes: {e.nrmiss:7d}  Receptor(s); and  {e.nsmiss:7d}  Source(s) "
              "that have been assigned missing elevations (-9999.0)!")
        if e.nrfilled > 0 or e.nsfilled > 0:
            w(f" **This run includes: {e.nrfilled:7d}  Receptor(s); and  {e.nsfilled:7d}  "
              "Source(s) located in gaps and assigned non-missing elevations ")
            w(" " * 68 + "based on the closest nodes under the FILLGAPS option!")
        if td == "DEM":
            w(" **These gaps may be due to NAD conversions or use of non-standard DEM files.")
            w("   Consider using standard DEM files with consistent NAD values or NED data to "
              "avoid gaps between or within files.")
        elif td == "NED":
            w(" **These gaps may be due to NAD conversions or use of non-standard NED files.")
            w("   Consider using standard NED files with consistent NAD values to avoid gaps "
              "between or within files.")
    w("  ")
    off = (f" **The Input Receptors and Sources Are Offset:{ff(e.xaterr - e.xauser, 12, 2)} "
           f"meters East; {ff(e.yaterr - e.yauser, 12, 2)} meters North")
    ancla = (f"      from the User-specified Anchor Point at:{ff(e.xaterr, 12, 2)} meters East; "
             f"{ff(e.yaterr, 12, 2)} meters North;  Zone {e.zaterr:3d}")
    if e.nada == 0:
        w(f" **The Input Receptors and Sources Were Assigned a NADA Value of {e.nada:2d}:  "
          "No NAD Shifts Included in Calculations")
    else:
        w(f" **The Input Receptors and Sources Were Assigned a NADA Value of {e.nada:2d}:  "
          f"{fx(NADN[e.nada], 40)}")
    w("")
    w(off)
    w(ancla)
    w("  ")
    if not e.extract:
        w(" **Terrain heights were PROVIDED by user")
    else:
        w(f" **Terrain heights were EXTRACTed from {td} data")
    w("  ")
    w(" **The Following Debug Output Files Have Been Automatically Generated:")
    w("")
    w(f"   DOMDETAIL.OUT - Details of User-specified Domain and Relation to {td} Files")
    w(f"   MAPDETAIL.OUT - Details Regarding Input {td} Files")
    w(f"   MAPPARAMS.OUT - Summary of {td} File Parameters and {td} File Adjacency")
    if e.hilldbg or e.recdbg or e.srcdbg:
        w("  ")
        w(" **The Following User-specified Debug Output Files Have Been Generated:")
        w("")
        if e.hilldbg:
            w("   Critical Hill Height Calculations:  " + e.calchc_file.rstrip(" "))
        if e.recdbg:
            w("  ")
            w("   Receptor NAD Conversion Results:    " + e.recdet_file.rstrip(" "))
            w(f"   Receptor vs {td} File Locations:     " + e.recndem_file.rstrip(" "))
            w("   Receptor Elevation Calculations:    " + e.recelv_file.rstrip(" "))
        if e.srcdbg and e.numsrc > 0:
            w("  ")
            w("   Source NAD Conversion Results:      " + e.srcdet_file.rstrip(" "))
            w(f"   Source vs {td} File Locations:       " + e.srcndem_file.rstrip(" "))
            w("   Source Elevation Calculations:      " + e.srcelv_file.rstrip(" "))
        w("  ")
