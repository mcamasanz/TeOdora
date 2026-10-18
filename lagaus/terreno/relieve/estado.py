# -*- coding: utf-8 -*-
"""Traducción de AERMAP v24142 (US EPA, dominio público): estado global (módulo MAIN1 y
VARINI de aermap.f) y gestión de mensajes (ERRHDL, TERRST, SUMTBL, HEADER).

El original guarda casi todo en variables globales que las subrutinas leen y modifican; la
traducción conserva ese diseño en un único objeto `Estado` para que cada efecto lateral del
Fortran (y sus peculiaridades) tenga su equivalente exacto. Los vectores son listas con el
índice 0 sin usar, para respetar la numeración 1..N del original."""
import math

from .mensajes import ERRORES

VERSN = "24142"
ISTRG = 512          # longitud de la línea del fichero de control
ILEN_FLD = 200       # longitud máxima de un campo
IFMAX = 40           # campos por línea
NUDGE = 0.03         # «nudge» en segundos de arco (≈1 m) para asignar la zona UTM

KEYWD = ['STARTING', 'FINISHED', 'TITLEONE', 'TITLETWO', 'ELEVUNIT', 'RUNORNOT',
         'DATATYPE', 'DATAFILE', 'DEBUGOPT', 'DOMAINXY', 'DOMAINLL', 'ANCHORXY',
         'LOCATION', 'TERRHGTS', 'FLAGPOLE', 'GRIDCART', 'GRIDPOLR', 'DISCCART',
         'DISCPOLR', 'EVALCART', 'RECEPTOR', 'SOURCLOC', 'DEBUGHIL', 'DEBUGREC',
         'DEBUGSRC', 'INCLUDED', 'SRCPARAM', 'NADGRIDS']


def feq(a, b):
    """Igualdad de cadenas de Fortran: se ignoran los blancos finales."""
    return a.rstrip(" ") == b.rstrip(" ")


def fx(s, n):
    """Asignación a una variable CHARACTER*n: trunca o rellena con blancos a la derecha."""
    return s[:n].ljust(n)


def fa(s, w):
    """Descriptor de salida Aw: si el texto es más largo, se trunca; si es más corto, se
    escribe ajustado a la DERECHA."""
    return s[:w] if len(s) >= w else s.rjust(w)


def vec(n, valor=0.0):
    """Vector 1..n (índice 0 sin usar)."""
    return [valor] * (n + 1)


class NoTraducido(Exception):
    """Opción del original que queda fuera del alcance de la traducción (DEM USGS, NADCON)."""


class AbortoFortran(Exception):
    """Situación en la que el ejecutable original (compilado con -fbounds-check) aborta con
    un error de ejecución de Fortran: acceso fuera de rango, registro inexistente..."""


class Estado:
    def __init__(self, inpfil="aermap.inp", outfil="aermap.out"):
        self.inpfil = inpfil
        self.outfil = outfil
        self.out = []            # líneas del fichero de salida principal (IOUNIT)
        self.tmpmsg = []         # fichero temporal de mensajes (registros de ERRHDL)
        self.rundat = "        "
        self.runtim = "        "
        # ---- lector del control (DEFINE/GETFLD) -------------------------------------
        self.iline = 0
        self.runst1 = ""
        self.runst = ""
        self.locb = [0] * (IFMAX + 1)
        self.loce = [0] * (IFMAX + 1)
        self.field = [""] * (IFMAX + 1)
        self.ifc = 0
        self.bline = True
        self.path = "  "
        self.ppath = "  "
        self.keywrd = "        "
        self.pkeywd = "        "
        self.ipnum = 0
        self.ippnum = 0
        self.dummy = "        "
        self.ilsave = 0
        self.ilreal_inc = 0      # ILREAL de INCLUD (SAVE, nunca se reinicia)
        self.ilreal_winc = 0     # ILREAL de WRITE_INCLUD
        self.ilreal_pre = 0      # ILREAL de PREINCLUD
        # ---- tamaños (PRESET) -------------------------------------------------------
        self.nrec = self.nsrc = self.ndem = self.narc = 1
        self.nnet = self.ixm = self.iym = 1
        # ---- VARINI -----------------------------------------------------------------
        self.pi = 4.0 * math.atan(1.0)
        self.dtorad = self.pi / 180.0
        self.rtodeg = 180.0 / self.pi
        self.idem = 0
        self.nsgap = self.nrgap = 0
        self.nsgap_in = self.nrgap_in = 0
        self.nsgap2 = self.nrgap2 = 0
        self.nsgap3 = self.nrgap3 = 0
        self.nssubs = self.nrsubs = 0
        self.nsfilled = self.nrfilled = 0
        self.nsmiss = self.nrmiss = 0
        self.fatal = False
        self.istart = False
        self.ifinis = True
        self.run = False
        self.recerr = False
        self.echo = True
        self.runerr = False
        self.hilldbg = self.recdbg = self.srcdbg = False
        self.demerr = self.nederr = False
        self.gapsfound = self.gapsfound_in = self.missfound = self.fillgaps = False
        self.nadpath = False
        self.domfix = False
        self.numrec = 0
        self.ista = self.iend = False
        self.irxr = self.iryr = self.irze = self.irzf = self.irhz = 0
        self.newid = True
        self.extract = True
        self.flgpol = False
        self.l_flgdf = False
        self.zflg = 0.0
        self.reelev = "METERS"
        self.soelev = "METERS"
        self.numsrc = 0
        self.recfil = ""
        self.srcfil = ""
        self.typdat = "    "
        self.typdem = "    "
        self.title1 = ""
        self.title2 = ""
        self.domcard = ""
        self.domadj = ""
        self.anchcrd = ""
        self.hgtcard = ""
        self.ierror = self.nfatal = self.nwarn = 0
        self.icstat = [0] * 21
        self.isstat = [0] * 21
        self.irstat = [0] * 21
        self.iostat = [0] * 21
        self.iftl = self.iwrn = self.info = 0
        self.gotdomflg = False
        self.domtyp = "   "
        self.xdmin = self.xdmax = self.ydmin = self.ydmax = 0.0
        self.zonmin = self.zonmax = 0
        self.xauser = self.yauser = self.xaterr = self.yaterr = 0.0
        self.zaterr = 0
        self.nada = 0
        self.nadgrid_path = ""
        self.l_neednadcon = False
        self.numdem = 0
        self.numarc = 0
        self.innet = 0
        self.domll = [[0.0] * 5 for _ in range(3)]
        self.xdmndifs = self.ydmndifs = self.xdmxdifs = self.ydmxdifs = 0.0
        self.xdmndifm = self.ydmndifm = self.xdmxdifm = self.ydmxdifm = 0.0
        self.zonmin_shft = self.zonmax_shft = 0
        self.dem = [None]
        # ficheros de depuración (solo nombres: los volcados de depuración no se traducen)
        self.calchc_file = "CALCHCDET.OUT"
        self.recdet_file = "RECDETAIL.OUT"
        self.recndem_file = "RECNDEM.OUT"
        self.recelv_file = "RECELV.OUT"
        self.srcdet_file = "SRCDETAIL.OUT"
        self.srcndem_file = "SRCNDEM.OUT"
        self.srcelv_file = "SRCELV.OUT"
        # variables «sueltas» de las redes de receptores (globales en el original)
        self.netidt = "        "
        self.pnetid = "        "
        self.ktype = "     "
        self.isc = 0
        self.icount = self.jcount = 0
        self.ize = self.izf = 0
        self.idc1 = 0
        self.incset = self.ixyset = self.ievset = self.ifgset = 0
        self.iorset = self.ixrset = self.idrset = self.igrset = 0
        self.xint = self.yint = self.xdelta = self.ydelta = 0.0
        self.mitl = 0
        self.dnum = 0.0
        self.fnum = 0.0
        self.irxt = self.iryt = self.irlas = 0
        self.isrc_soloca = 0        # ISRC local (SAVE) de SOLOCA
        self.zfdum = 0.0

    # ------------------------------------------------------------------ dimensiones
    def asignar(self):
        """ALLSETUP: reserva los vectores con los tamaños de PRESET."""
        nr, ns, nd = self.nrec, self.nsrc, self.ndem
        self.axr, self.ayr = vec(nr), vec(nr)
        self.azelev, self.azflag, self.azhill = vec(nr), vec(nr), vec(nr)
        self.zetmp1, self.zetmp2 = vec(nr), vec(nr)
        self.zftmp1, self.zftmp2 = vec(nr), vec(nr)
        self.netid = vec(nr, "        ")
        self.rectyp = vec(nr, "  ")
        self.recnam = vec(nr, "        ")
        self.ndxarc = vec(nr, 0)
        self.iref = vec(nr, 0)
        self.arcid = vec(self.narc, "        ")
        self.xcoord = [vec(self.ixm) for _ in range(self.nnet + 1)]
        self.ycoord = [vec(self.iym) for _ in range(self.nnet + 1)]
        self.ntid = vec(self.nnet, "        ")
        self.nttyp = vec(self.nnet, "        ")
        self.netsta, self.netend = vec(self.nnet, 0), vec(self.nnet, 0)
        self.numxpt, self.numypt = vec(self.nnet, 0), vec(self.nnet, 0)
        self.xorig, self.yorig = vec(self.nnet), vec(self.nnet)
        self.axs, self.ays, self.azs = vec(ns), vec(ns), vec(ns)
        self.ax1s, self.ay1s, self.ax2s, self.ay2s = vec(ns), vec(ns), vec(ns), vec(ns)
        self.aws = vec(ns)
        self.srcid = vec(ns, "            ")
        self.srctyp = vec(ns, "        ")
        self.demfil = vec(nd, "")
        self.l_tiffdebug = vec(nd, False)
        self.l_demcheck = vec(nd, False)
        self.l_userelevunits = vec(nd, False)
        self.chr_userelevunits = vec(nd, "           ")
        self.userelevunits = vec(nd, 0)
        self.userdci = vec(nd)
        self.l_nedskip = vec(nd, False)
        self.irin = [vec(nd, 0) for _ in range(nr + 1)]
        self.isin = [vec(nd, 0) for _ in range(ns + 1)]
        self.lrec_filled = [vec(nd, False) for _ in range(nr + 1)]
        self.lsrc_filled = [vec(nd, False) for _ in range(ns + 1)]

    @staticmethod
    def crecer(lista, i, valor=0.0):
        """Escritura fuera del tamaño reservado (el Fortran no comprueba en TERHGT/FLGHGT)."""
        while len(lista) <= i:
            lista.append(valor)

    # ------------------------------------------------------------------ mensajes
    def errhdl(self, pathwy, modnam, inertp, inercd, inpmsg):
        """ERRHDL: registra el mensaje en el fichero temporal, con los mismos límites de 999
        errores y 999 avisos del original."""
        self.ierror += 1
        if inertp == "E":
            self.fatal = True
            self.nfatal += 1
            if self.nfatal == 999:
                self.tmpmsg.append((pathwy, inertp, "999", min(self.iline, 99999999), "ERRHDL",
                                    "Number of Fatal Errors Has Reached Limit of 999", ""))
                return
            if self.nfatal > 999:
                return
        if inertp == "W":
            self.nwarn += 1
            if self.nwarn == 999:
                self.tmpmsg.append((pathwy, inertp, "888", min(self.iline, 99999999), "ERRHDL",
                                    "Number of Warnings Has Reached Limit of 999", ""))
                return
            if self.nwarn > 999:
                return
        errmg1 = None
        for cod, txt in ERRORES:
            if inercd == cod:
                errmg1 = txt
                break
        if errmg1 is None:
            errmg1 = "SYSTEM ERROR: MESSAGE NOT FOUND FOR THIS NUMBER!"
        self.tmpmsg.append((pathwy, inertp, inercd, min(self.iline, 99999999),
                            modnam.rstrip()[:6], errmg1, inpmsg.rstrip()[:12]))

    @staticmethod
    def _reg(r, sep):
        """Formato 1111/1117. Ojo: en Fortran, un texto más corto que el campo Aw se escribe
        AJUSTADO A LA DERECHA (blancos delante): por eso «     274» sale como «         274»."""
        p, t, c, l, m, e, i = r
        return f"{fa(p, 2)} {t}{fa(c, 3)}{l:8d} {fa(m, 6)}{sep}{fa(e, 50)} {fa(i, 12)}"

    def terrst(self):
        """TERRST: cuenta los mensajes por tipo."""
        self.iftl = sum(1 for r in self.tmpmsg if r[1] == "E")
        self.iwrn = sum(1 for r in self.tmpmsg if r[1] == "W")
        self.info = sum(1 for r in self.tmpmsg if r[1] == "I")

    def sumtbl(self):
        """SUMTBL: tabla resumen de mensajes del fichero de salida."""
        w = self.out.append
        w(" --------- Summary of Total Messages --------")
        w("  ")
        w(f" A Total of {self.iftl:10d} Fatal Error Message(s)")
        w(f" A Total of {self.iwrn:10d} Warning Message(s)")
        w(f" A Total of {self.info:10d} Informational Message(s)")
        w("  ")
        w("  ")
        w("    ******** FATAL ERROR MESSAGES ******** ")
        j = 0
        for r in self.tmpmsg:
            if r[1] == "E":
                j += 1
                w(" " + self._reg(r, ":"))
        if j == 0:
            w("               ***  NONE  ***         ")
            w("  ")
        w("  ")
        w("    ********   WARNING MESSAGES   ******** ")
        j = 0
        for r in self.tmpmsg:
            if r[1] == "W":
                j += 1
                w(" " + self._reg(r, ":"))
        if j == 0:
            w("               ***  NONE  ***        ")
            w("  ")

    def header(self):
        """HEADER: salto de página y cabecera del fichero de salida."""
        self.out.append(f"\f *** AERMAP - VERSION {VERSN} ***    *** {self.title1[:68]:68s} ***"
                        f"        {self.rundat:8s}")
        self.out.append(f"{'':35s}*** {self.title2[:68]:68s} ***        {self.runtim:8s}")

    def lineas_mensajes(self):
        """Lista de mensajes como los imprime SUMTBL (para comparar en la validación)."""
        return [self._reg(r, ":") for r in self.tmpmsg]
