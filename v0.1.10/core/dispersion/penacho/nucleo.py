# -*- coding: utf-8 -*-
"""Núcleo compilado con numba del cálculo por receptor (fuentes de área).

El código numba NO se escribe a mano: se GENERA a partir de las funciones Python de referencia
(calc1, calc2, sigmas, pitarea, iblval, perfiles, resultados), con transformaciones mecánicas:

- el objeto de estado ``e`` pasa a ser un registro numpy (``st[0]``) con los escalares, de modo
  que ``e.ZI`` sigue escribiéndose igual;
- las matrices van en una tupla ``A`` y ``e.GRIDWS`` pasa a ``A[k]``;
- las comparaciones de cadenas (SRCTYP, AFTSRC, URBSRC, OUTTYP, POLLUT) pasan a códigos
  precalculados;
- los mensajes (ERRHDL) se registran como eventos y se reproducen en Python, en orden.

El resultado se guarda en ``_nucleo_gen.py`` (con la huella de las fuentes) y numba lo compila con
caché en disco. ``AERMOD_NUMBA=0`` fuerza la vía Python pura."""
import hashlib
import importlib
import inspect
import math
import operator
import os
import re
import textwrap

import numpy as np

from . import tablas as T

_FUNCIONES = [
    ("calculo_area", ["_acalc_bucle", "adisy", "adisz", "centroid", "heff", "refl_ht", "aer_achi",
               "acplume", "ardist", "vdis", "_humedo", "debout", "pdep", "pdepg"]),
    ("funciones_dispersion", ["fterm", "fyplm", "fypan", "meandr", "critds", "pdf", "skcalc", "crcalc", "alcalc",
               "becalc", "aacalc", "bbcalc", "llcalc", "decay", "vrtsbl", "vrtsbn", "vrtcbl",
               "pfract", "erfx"]),
    ("sigmas", ["sigy", "sigz", "bid", "szsfcl", "rmssig", "_rpot"]),
    ("integracion_area", ["areain", "plumef", "pside", "xwidth", "pwidth", "zbrent", "pside2", "hpsort",
                 "qatr3", "qg2"]),
    ("parametros_efectivos", ["iblval"]),
    ("perfiles", ["gintrp", "locate", "anyavg", "perfiles_hora"]),
    ("resultados", ["sumval"]),
    ("calculo_punto_volumen", ["_pcalc_bucle", "aercalc", "prmcalc", "gamcalc", "prm_pchi", "_vcalc_bucle",
                  "volcalc"]),
    ("estela_edificio", []),
    ("quimica_no2", ["_pvmrm_bucle"]),
]
# más funciones de calc1, calc2 y sigmas que usan chimeneas y volúmenes
_FUNCIONES[0][1].extend(["cplume", "prm_plume", "aer_pchi", "prmheff"])
_FUNCIONES[1][1].extend(["xydist"])
_FUNCIONES[2][1].extend(["deltah", "sblris", "cblprd", "cblprn", "cblpr3", "prmdelh", "hsprim"])

# Funciones escritas aquí (en estilo Python de referencia) porque la original usa construcciones
# que numba no admite (setattr, listas de nombres) o ramas fuera de alcance.
_PLANTILLAS = '''
def _cero_receptor(e, aerout):
    if e.RUNTTRM:
        e.TTRMOUT[e.IREC, e.ISRC, 11] = 0.0
    if e.PVMRM or e.OLM or e.ARM2 or e.RUNTTRM or e.GRSM:
        _cero_chi(e, e.IREC, e.ISRC)
    e.HRVAL[:] = 0.0
    e.AERVAL[:] = 0.0
    aerout[:] = 0.0


def afluxes(e):
    raise NoTraducido("AIRCRAFT")


def adeltah(e, xarg):
    raise NoTraducido("AIRCRAFT")


def _acalc_rapido(e, aerout, qtksav):
    raise NoTraducido("FASTAREA")
    return False


def _aviso_411(e, irec):
    _evento(e, 411)


def pdis(e, xarg):
    sigz(e, xarg)
    sigy(e, xarg)
    e.VSIGY = 0.0
    e.VSYN = 0.0
    e.VSIGZ = 0.0
    e.VSZD1 = 0.0
    e.VSZD2 = 0.0
    e.VSZN1 = 0.0
    e.VSZN2 = 0.0
    e.VSZ3 = 0.0
    e.VSY3 = 0.0
    if e.NOBID:
        if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
            e.SYB = 0.0
            e.SZB = 0.0
        elif e.UNSTAB:
            e.SYB = 0.0
            e.SZBD = 0.0
            e.SZBN = 0.0
            e.SYB3 = 0.0
            e.SZB3 = 0.0
    else:
        bid(e)
    e.PLATSZ = 0.0
    e.PLATSY = 0.0
    e.PLATSZD1 = 0.0
    e.PLATSYD1 = 0.0
    e.PLATSZD2 = 0.0
    e.PLATSYD2 = 0.0
    e.PLATSZN1 = 0.0
    e.PLATSYN1 = 0.0
    e.PLATSZN2 = 0.0
    e.PLATSYN2 = 0.0
    e.PLATSZP = 0.0
    e.PLATSYP = 0.0
    if e.OSPLAT[e.ISRC]:
        raise NoTraducido("PLATFORM")
    rmssig(e)


def sngl(x):
    return float(np.float32(x))


def dsign(a, b):
    if b == 0:
        return abs(a)
    return math.copysign(abs(a), b)


def nint(x):
    if x >= 0:
        return int(math.floor(x + 0.5))
    return -int(math.floor(-x + 0.5))


def _evento(e, cod):
    n = e.EVN[0]
    if n < e.EVS.shape[0]:
        e.EVS[n, 0] = cod
        e.EVS[n, 1] = e.KURDAT
        e.EVS[n, 2] = e.IMONTH
        e.EVS[n, 3] = e.IDAY
        e.EVS[n, 4] = e.IHOUR
        e.EVS[n, 5] = e.ISRC
        e.EVS[n, 6] = e.IREC
    e.EVN[0] = n + 1
'''

# Campos añadidos (no están en MAIN1)
_EXTRA_ESC = {"POL_SO2": "?", "I_ALPHA": "i8"}
_EXTRA_ARR = ["AFT_Y", "URB_Y", "HBP_Y", "TIPOC", "OUTC", "EVN", "EVS"]
_EXTRA_TIPOS = {"AFT_Y": ("boolean", 1), "URB_Y": ("boolean", 1), "HBP_Y": ("boolean", 1),
                "TIPOC": ("int64", 1),
                "OUTC": ("int64", 1), "EVN": ("int64", 1), "EVS": ("int64", 2)}
_TIPOS = {"POINT": 1, "POINTCAP": 11, "POINTHOR": 12, "VOLUME": 2, "AREA": 3, "AREAPOLY": 4,
          "AREACIRC": 5, "LINE": 6, "OPENPIT": 7, "RLINE": 8, "RLINEXT": 9, "BUOYLINE": 13,
          "SWPOINT": 14}
_SALIDAS = {"CONC": 1, "DEPOS": 2, "DDEP": 3, "WDEP": 4}
_NEV = 200000
_GEN = os.path.join(os.path.dirname(__file__), "_nucleo_gen.py")
# error_model="numpy": sin la comprobación de división por cero de Python en cada operación
# (mismo resultado bit a bit cuando no hay divisiones por cero, que el original tampoco hace)
_DECO = '@njit(cache=True, error_model="numpy")'
_mod = None
_info = None


_DESACTIVADO = [False]


def desactivar():
    """Fuerza la vía Python (opciones de depuración: los volcados se escriben desde Python)."""
    _DESACTIVADO[0] = True


def activo():
    if _DESACTIVADO[0] or os.environ.get("AERMOD_NUMBA", "1") == "0":
        return False
    try:
        import numba  # noqa: F401
    except ImportError:
        return False
    return True


# --------------------------------------------------------------------------- transformación
_QUITAR = {"funciones_dispersion, sigmas, parametros_efectivos, integracion_area, resultados = _m()", "funciones_dispersion = _m()[0]", 'e.PATH = "MX"',
           "from .formato import fwrite",
           "global _calc1", "if _calc1 is None:", "from . import calculo_area as _c", "_calc1 = _c",
           "calculo_area = _calc1"}


def _quitar_fwrite(lineas):
    """Elimina las sentencias ``e.DUMMY = fwrite(...)`` y ``e.pantalla.w(...)`` (pueden ocupar
    varias líneas)."""
    out = []
    i = 0
    while i < len(lineas):
        l = lineas[i]
        if l.strip().startswith(("e.DUMMY = fwrite(", "e.pantalla.w(", "depura.")):
            nivel = l.count("(") - l.count(")")
            ini = i
            while nivel > 0:
                i += 1
                nivel += lineas[i].count("(") - lineas[i].count(")")
            i += 1
            if l.strip().startswith("depura."):
                # volcados de DEBUGOPT: con depuración el cálculo va por la vía Python
                out.append(lineas[ini][:len(l) - len(l.lstrip())] + 'raise NoTraducido("DEBUGOPT")')
            continue
        out.append(l)
        i += 1
    return out


def _transformar(src):
    s = textwrap.dedent(src)
    s = re.sub(r'"""[\s\S]*?"""', "", s)
    s = "\n".join(l for l in s.split("\n") if not l.strip().startswith("#"))
    con_p = any(l.strip() == "p = e.P" for l in s.split("\n"))
    lineas = [l for l in s.split("\n") if l.strip() not in _QUITAR and
              l.strip() != 'modnam = "AREAIN"' and not l.strip().endswith("= _m()") and
              not l.strip().endswith("= _m()[0]") and l.strip() != "p = e.P" and
              not l.strip().startswith(("from . import", "import "))]
    # el aviso de NUMRISE (NN > MXNW) se escribe aunque no haya depuración: evento
    lineas = [l.replace("depura.numrise_error(e, dbgunt, nn, mxnw)", "_evento(e, 4991)") for l in lineas]
    lineas = _quitar_fwrite(lineas)
    out = []
    for l in lineas:
        if "_rutina_tox(" in l:
            ind = l[:len(l) - len(l.lstrip())]
            l = ind + 'raise NoTraducido("FASTAREA")'
        out.append(l)
    s = "\n".join(out)
    # variables de los módulos PRIME (e.P.X, o p.X tras «p = e.P») -> campos P_X
    if con_p:
        s = re.sub(r"\bp\.(?=[A-Z_])", "e.P_", s)
    s = re.sub(r"\be\.P\.(?=[A-Z_])", "e.P_", s)
    s = re.sub(r"\b(calculo_area|funciones_dispersion|sigmas|integracion_area|parametros_efectivos|perfiles|resultados|arise|estela_edificio|calculo_punto_volumen|quimica_no2)"
               r"\.(?=[a-z_])", "", s)
    s = re.sub(r'e\.AFTSRC\[([^\]]+)\] == "Y"', r"e.AFT_Y[\1]", s)
    s = re.sub(r'e\.URBSRC\[([^\]]+)\] == "Y"', r"e.URB_Y[\1]", s)
    s = re.sub(r'e\.URBSRC\[([^\]]+)\] == "N"', r"(not e.URB_Y[\1])", s)
    s = re.sub(r'e\.HBPSRC\[([^\]]+)\] == "Y"', r"e.HBP_Y[\1]", s)
    s = s.replace('e.errhdl(e.PATH, "PRMDELH", "E", "499", e.SRCID[e.ISRC])', "_evento(e, 499)")
    s = s.replace('e.POLLUT == "SO2"', "e.POL_SO2")
    s = s.replace("e.SRCTYP[", "e.TIPOC[")
    s = s.replace('t[:5] == "POINT"', "(t == 1 or t == 11 or t == 12)")
    s = s.replace('t == "VOLUME"', "t == 2")
    s = re.sub(r'(e\.TIPOC\[[^\]]+\]) == "POINTCAP"', r"\1 == 11", s)
    s = re.sub(r'(e\.TIPOC\[[^\]]+\]) == "POINTHOR"', r"\1 == 12", s)
    s = s.replace('t[:4] == "AREA"', "(t >= 3 and t <= 5)")
    s = s.replace('t in ("AREA", "AREAPOLY", "AREACIRC", "LINE", "OPENPIT")', "(t >= 3 and t <= 7)")
    s = s.replace('== "RLINE")', "== 8)").replace('== "RLINEXT")', "== 9)")
    # resto de comparaciones de un tipo de fuente ya convertido a código (t = e.TIPOC[...])
    for nom, cod in sorted(_TIPOS.items(), key=lambda kv: -len(kv[0])):
        s = s.replace('t == "%s"' % nom, "t == %d" % cod).replace('t != "%s"' % nom, "t != %d" % cod)
    s = s.replace("e.OUTTYP[", "e.OUTC[")
    for k, v in _SALIDAS.items():
        s = s.replace('o == "%s"' % k, "o == %d" % v)
    s = s.replace('e.errhdl(e.PATH, "MEANDR", "I", "494", e.DUMMY)', "_evento(e, 494)")
    s = s.replace('e.errhdl(e.PATH, "MEANDR", "I", "424", e.DUMMY)', "_evento(e, 424)")
    s = s.replace('e.errhdl(e.PATH, "PFRACT", "I", "405", e.DUMMY)', "_evento(e, 405)")
    s = s.replace('e.errhdl(e.PATH, modnam, "E", "406", e.SRCID[e.ISRC])', "_evento(e, 406)")
    s = s.replace('e.errhdl(e.PATH, "TGINIT", "W", "479", _tg4pfl(e))', "_evento(e, 479)")
    s = s.replace('e.errhdl(e.PATH, "PCALC", "E", "601", "GRSM")', "_evento(e, 6011)")
    s = s.replace('e.errhdl(e.PATH, "VCALC", "E", "601", "GRSM")', "_evento(e, 6012)")
    s = s.replace('e.errhdl(e.PATH, "ACALC", "E", "601", "GRSM")', "_evento(e, 6013)")
    s = s.replace('float("nan")', "math.nan")
    s = s.replace("return None", "return 0.0")
    s = s.replace("return y, ier, None", "return y, ier, -1")
    resto = re.findall(r'(?:TIPOC\[[^\]]+\]|\bt|\bo|OUTC\[[^\]]+\]) (?:==|!=) "[^"]*"', s)
    if resto:
        raise RuntimeError("nucleo: comparación de cadena sin traducir: %r" % resto)
    return s


def _fuentes():
    """Fuentes transformadas: las funciones de la lista, las plantillas y, por cierre transitivo,
    los ayudantes privados de esos módulos que se llamen. Devuelve (trozos, constantes)."""
    mods = {m: importlib.import_module("." + m, __package__) for m, _ in _FUNCIONES}
    trozos = []
    hechas = set()
    for m, nombres in _FUNCIONES:
        for n in nombres:
            trozos.append(_transformar(inspect.getsource(getattr(mods[m], n))))
            hechas.add(n)
    trozos.append(_PLANTILLAS)
    hechas |= set(re.findall(r"^def ([A-Za-z_0-9]+)\(", _PLANTILLAS, flags=re.M))
    constantes = {}
    while True:
        texto = "\n".join(trozos)
        nuevas = []
        for n in sorted(set(re.findall(r"\b([a-z_][a-z0-9_]*)\(", texto))):
            if n in hechas:
                continue
            for mod in mods.values():
                f = getattr(mod, n, None)
                if inspect.isfunction(f) and f.__module__ == mod.__name__:
                    nuevas.append(_transformar(inspect.getsource(f)))
                    hechas.add(n)
                    break
        for c in sorted(set(re.findall(r"\b(_[A-Z][A-Z0-9_]*)\b", texto))):
            if c in constantes:
                continue
            for mod in mods.values():
                if hasattr(mod, c):
                    constantes[c] = getattr(mod, c)
                    break
        if not nuevas:
            break
        trozos += nuevas
    return trozos, constantes


_TDECL = {"DOUBLE": "f8", "REAL": "f8", "INTEGER": "i8", "LOGICAL": "?"}


def _clasificar(c, e):
    """('a', None) si es una matriz; ('e', tipo numpy) si es un escalar."""
    if c in _EXTRA_ARR:
        return "a", None
    if c in _EXTRA_ESC:
        return "e", _EXTRA_ESC[c]
    if c.startswith("P_"):
        d = T.DECL_PRIME.get(c[2:])
        obj, nom = (e.P if e is not None else None), c[2:]
    else:
        d = T.DECL.get(c)
        obj, nom = e, c
    if d is not None:
        if d[0] == "CHARACTER":
            raise RuntimeError("nucleo: queda un campo CHARACTER " + c)
        return ("a", None) if d[1] else ("e", _TDECL[d[0]])
    # atributo propio de la traducción (estado con SAVE preasignado): tipo según su valor
    if obj is None or not hasattr(obj, nom):
        raise RuntimeError("nucleo: campo desconocido " + c)
    v = getattr(obj, nom)
    if isinstance(v, np.ndarray):
        return "a", None
    if isinstance(v, (bool, np.bool_)):
        return "e", "?"
    if isinstance(v, (int, np.integer)):
        return "e", "i8"
    if isinstance(v, (float, np.floating)):
        return "e", "f8"
    raise RuntimeError("nucleo: tipo no admitido en " + c)


def _generar(e=None):
    trozos, constantes = _fuentes()
    texto = "\n\n".join(trozos)
    nombres = re.findall(r"^def ([A-Za-z_0-9]+)\(e\b", texto, flags=re.M)
    todos = re.findall(r"^def ([A-Za-z_0-9]+)\(", texto, flags=re.M)
    # firmas y llamadas: (e, ...) -> (e, A, ...)
    pat = r"\b(" + "|".join(sorted(set(nombres), key=len, reverse=True)) + r")\((\s*)e\s*([,)])"
    texto = re.sub(pat, r"\1(\2e, A\3", texto)
    # campos
    campos = sorted(set(re.findall(r"\be\.([A-Z_][A-Z0-9_]*)\b", texto)))
    arrays, escalares = [], []
    for c in campos:
        clase, tipo = _clasificar(c, e)
        if clase == "a":
            arrays.append(c)
        else:
            escalares.append((c, tipo))
    # las matrices van en una jitclass (se pasa por puntero; una tupla se copiaría por valor en
    # cada llamada interna)
    for a in arrays:
        texto = re.sub(r"\be\." + a + r"\b", "A." + a, texto)
    # structref (y no jitclass) porque es compatible con la caché en disco de numba
    cab = ['# -*- coding: utf-8 -*-',
           '# GENERADO por nucleo.py a partir de las funciones Python de referencia. NO EDITAR.',
           'import math', '', 'import numpy as np', 'from numba import njit',
           'from numba.core import types', 'from numba.experimental import structref', '',
           'from .estado import NoTraducido, Parada', '', '',
           '@structref.register', 'class MatricesTipo(types.StructRef):',
           '    def preprocess_fields(self, fields):',
           '        return tuple((n, types.unliteral(t)) for n, t in fields)', '', '',
           'class Matrices(structref.StructRefProxy):', '    pass', '', '',
           'structref.define_proxy(Matrices, MatricesTipo, %r)' % list(arrays), '', '',
           _DECO, 'def nuevas_matrices(%s):' % ", ".join(arrays),
           '    return Matrices(%s)' % ", ".join(arrays), '', '']
    for c, v in sorted(constantes.items()):
        if isinstance(v, (list, tuple, np.ndarray)):
            cab.append("%s = np.array(%r, dtype=np.float64)" % (c, [float(x) for x in v]))
        elif isinstance(v, float) and math.isnan(v):
            cab.append("%s = math.nan" % c)
        elif isinstance(v, float) and math.isinf(v):
            cab.append("%s = %smath.inf" % (c, "-" if v < 0 else ""))
        elif isinstance(v, (int, float)):
            cab.append("%s = %r" % (c, v))
        else:
            raise RuntimeError("nucleo: constante no admitida " + c)
    cab.append("")
    cuerpo = re.sub(r"^def ", _DECO + "\ndef ", texto, flags=re.M)
    entrada = ['', '', _DECO, 'def k_acalc_bucle(st, A, qtksav, aerout):',
               '    e = st[0]', '    _acalc_bucle(e, A, qtksav, aerout)', '',
               '', _DECO, 'def k_pcalc_bucle(st, A, aerplm, aerpan):',
               '    e = st[0]', '    _pcalc_bucle(e, A, aerplm, aerpan)', '',
               '', _DECO, 'def k_vcalc_bucle(st, A, aerplm, aerpan):',
               '    e = st[0]', '    _vcalc_bucle(e, A, aerplm, aerpan)', '',
               '', _DECO, 'def k_perfiles_hora(st, A):',
               '    e = st[0]', '    perfiles_hora(e, A)', '',
               '', _DECO, 'def k_pvmrm_bucle(st, A, srcs, maxchi, domidx):',
               '    e = st[0]', '    _pvmrm_bucle(e, A, srcs, maxchi, domidx)', '']
    entrada += ["", "", "# metadatos para reutilizar el núcleo sin regenerarlo",
                "_ARRAYS = %r" % list(arrays), "_ESCALARES = %r" % [list(x) for x in escalares], ""]
    fuente = "\n".join(cab) + cuerpo + "\n".join(entrada)
    huella = hashlib.sha256(fuente.encode("utf-8")).hexdigest()
    return fuente, huella, arrays, escalares, todos


def _huella_fuentes():
    """Huella de los ficheros de los que se genera el núcleo."""
    d = os.path.dirname(__file__)
    h = hashlib.sha256()
    for m in sorted({m for m, _ in _FUNCIONES} | {"nucleo", "tablas", "estado"}):
        with open(os.path.join(d, m + ".py"), "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def _cargar(e):
    global _mod, _info
    if _mod is not None:
        return
    # si las fuentes de las que se genera no han cambiado, se reutiliza _nucleo_gen.py sin
    # regenerarlo (la generación cuesta ~2 s por corrida)
    h_src = _huella_fuentes()
    fuente = None
    if os.path.exists(_GEN):
        with open(_GEN, encoding="utf-8") as f:
            l1, l2 = f.readline(), f.readline()
            if l2 == "# fuentes " + h_src + "\n":
                fuente = f.read()
    if fuente is not None:
        _mod = importlib.import_module("._nucleo_gen", __package__)
        arrays, escalares = list(_mod._ARRAYS), [tuple(x) for x in _mod._ESCALARES]
    else:
        fuente, huella, arrays, escalares, _ = _generar(e)
        with open(_GEN, "w", encoding="utf-8") as f:
            f.write("# huella " + huella + "\n# fuentes " + h_src + "\n" + fuente)
        _mod = importlib.import_module("._nucleo_gen", __package__)
    # orden del registro: primero los campos del estado y después los de PRIME (P_X)
    escalares = [x for x in escalares if not x[0].startswith("P_")] + \
        [x for x in escalares if x[0].startswith("P_")]
    dt = np.dtype([(n, t) for n, t in escalares])
    nombres = [n for n, _ in escalares]
    de_e = [n for n in nombres if not n.startswith("P_")]
    de_p = [n[2:] for n in nombres if n.startswith("P_")]
    # llamadas y campos asignados (también en asignaciones múltiples y aumentadas) de cada función
    # del núcleo: a la vuelta solo se devuelven a ``e`` los que escribe cada punto de entrada
    llamadas, asignados = {}, {}
    for b in re.split("\n" + re.escape(_DECO) + "\n", fuente):
        mdef = re.match(r"def ([A-Za-z_0-9]+)\(", b)
        if not mdef:
            continue
        esc = set()
        for lin in b.split("\n"):
            m = re.match(r"^\s*([^=]*?[^=<>!])=(?!=)", lin)
            if m:
                esc.update(re.findall(r"\be\.([A-Z_][A-Z0-9_]*)", m.group(1)))
        llamadas[mdef.group(1)] = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\(", b))
        asignados[mdef.group(1)] = esc
    vueltas = {}
    for k in [n for n in llamadas if n.startswith("k_")]:
        vistos, pila, esc = set(), [k], set()
        while pila:
            f = pila.pop()
            if f in vistos or f not in llamadas:
                continue
            vistos.add(f)
            esc |= asignados[f]
            pila.extend(llamadas[f] - vistos)
        vueltas[k] = [(i, n.startswith("P_"), n[2:] if n.startswith("P_") else n)
                      for i, n in enumerate(nombres) if n in esc]
    # matrices: derivadas (fijas), del estado y de PRIME, leídas con attrgetter
    a_e = [a for a in arrays if a not in _EXTRA_ARR and not a.startswith("P_")]
    a_p = [a[2:] for a in arrays if a.startswith("P_")]
    orden = [(0, a) if a in _EXTRA_ARR else ((2, a_p.index(a[2:])) if a.startswith("P_") else (1, a_e.index(a)))
             for a in arrays]
    _info = (arrays, nombres, dt, operator.attrgetter(*de_e), operator.attrgetter(*de_p) if de_p else None,
             vueltas, operator.attrgetter(*a_e), operator.attrgetter(*a_p) if a_p else None, orden,
             np.zeros(1, dtype=dt))


# ------------------------------------------------------------------------------ ejecución
def _derivados(e):
    d = getattr(e, "_nb_deriv", None)
    if d is None:
        n = len(e.SRCTYP)
        aft = np.zeros(n, dtype=np.bool_)
        urb = np.zeros(n, dtype=np.bool_)
        hbp = np.zeros(n, dtype=np.bool_)
        tip = np.zeros(n, dtype=np.int64)
        for i in range(1, n):
            aft[i] = e.AFTSRC[i] == "Y" if i < len(e.AFTSRC) else False
            urb[i] = e.URBSRC[i] == "Y" if i < len(e.URBSRC) else False
            hbp[i] = e.HBPSRC[i] == "Y" if e.HBPSRC is not None and i < len(e.HBPSRC) else False
            tip[i] = _TIPOS.get(e.SRCTYP[i], 10)
        outc = np.zeros(len(e.OUTTYP), dtype=np.int64)
        for i in range(1, len(e.OUTTYP)):
            outc[i] = _SALIDAS.get(e.OUTTYP[i], 0)
        d = {"AFT_Y": aft, "URB_Y": urb, "HBP_Y": hbp, "TIPOC": tip, "OUTC": outc,
             "EVN": np.zeros(1, dtype=np.int64), "EVS": np.zeros((_NEV, 7), dtype=np.int64)}
        e._nb_deriv = d
    return d


_FICTICIAS = {}


def _ficticia(nom):
    """Matriz de relleno para las no asignadas (p. ej. CHI sin química de NO2)."""
    a = _FICTICIAS.get(nom)
    if a is None:
        tipo, dims = T.DECL[nom][0], T.DECL[nom][1]
        dt = {"DOUBLE": np.float64, "REAL": np.float64, "INTEGER": np.int64,
              "LOGICAL": np.bool_}[tipo]
        a = np.zeros((1,) * len(dims), dtype=dt)
        _FICTICIAS[nom] = a
    return a


def _leer(e, n):
    return getattr(e.P, n[2:]) if n.startswith("P_") else getattr(e, n)


def _ejecutar(e, nucleo, *args):
    """Empaqueta el estado, ejecuta un bucle compilado y devuelve el estado a ``e``."""
    _cargar(e)
    arrays, escalares, dt, lect_e, lect_p, vueltas, lect_ae, lect_ap, orden, st = _info
    der = _derivados(e)
    der["EVN"][0] = 0
    e.POL_SO2 = e.POLLUT == "SO2"
    if not hasattr(e, "I_ALPHA"):
        e.I_ALPHA = 0
    va = lect_ae(e)
    vp = lect_ap(e.P) if lect_ap is not None else ()
    # el structref se reutiliza mientras las matrices sean los mismos objetos
    clave = tuple(map(id, va)) + tuple(map(id, vp))
    cache = getattr(e, "_nb_M", None)
    if cache is None or cache[0] != clave:
        A = []
        for (fuente, k), a in zip(orden, arrays):
            v = der[k] if fuente == 0 else (va[k] if fuente == 1 else vp[k])
            A.append(_ficticia(a) if v is None else v)
        cache = (clave, _mod.nuevas_matrices(*A), A)
        e._nb_M = cache
    M = cache[1]
    st[0] = lect_e(e) + lect_p(e.P) if lect_p is not None else lect_e(e)
    try:
        getattr(_mod, nucleo)(st, M, *args)
    finally:
        vals = st[0].item()
        p = e.P
        for i, es_p, n in vueltas[nucleo]:
            setattr(p if es_p else e, n, vals[i])
        _reproducir(e, der)


def acalc_bucle(e, qtksav, aerout):
    """Bucle de receptores de ACALC con el núcleo compilado."""
    _ejecutar(e, "k_acalc_bucle", float(qtksav), aerout)


def pcalc_bucle(e, aerplm, aerpan):
    """Bucle de receptores de PCALC (con PRIME) con el núcleo compilado."""
    _ejecutar(e, "k_pcalc_bucle", aerplm, aerpan)


def vcalc_bucle(e, aerplm, aerpan):
    """Bucle de receptores de VCALC con el núcleo compilado."""
    _ejecutar(e, "k_vcalc_bucle", aerplm, aerpan)


def perfiles_hora(e):
    """Perfiles meteorológicos de la hora en la malla con el núcleo compilado."""
    _ejecutar(e, "k_perfiles_hora")


def pvmrm_bucle(e, srcs, maxchi, domidx):
    """Bucle de receptores de PVMRM_CALC con el núcleo compilado."""
    _ejecutar(e, "k_pvmrm_bucle", int(srcs), maxchi, domidx)


def _reproducir(e, der):
    from .formato import fwrite
    n = min(int(der["EVN"][0]), _NEV)
    ev = der["EVS"]
    for i in range(n):
        cod, kurdat, imonth, iday, ihour, isrc, irec = (int(x) for x in ev[i])
        if cod == 405:
            e.DUMMY = fwrite("(I8.8)", kurdat)[0]
            e.errhdl(e.PATH, "PFRACT", "I", "405", e.DUMMY)
        elif cod in (494, 424):
            e.DUMMY = fwrite("(I2.2,1X,I2.2,1X,I2.2,1X,I3)", imonth, iday, ihour,
                             min(isrc, 999))[0]
            e.errhdl(e.PATH, "MEANDR", "I", str(cod), e.DUMMY)
        elif cod == 499:
            e.errhdl(e.PATH, "PRMDELH", "E", "499", e.SRCID[isrc])
        elif cod == 479:
            from .perfiles import _tg4pfl
            e.errhdl(e.PATH, "TGINIT", "W", "479", _tg4pfl(e))
        elif cod == 406:
            e.errhdl(e.PATH, "AREAIN", "E", "406", e.SRCID[isrc])
        elif cod == 411:
            if irec <= 999:
                d = fwrite("(I3.3,1X,I8.8)", irec, kurdat)[0]
            elif irec <= 9999:
                d = fwrite("(I4.4,I8.8)", irec, kurdat)[0]
            else:
                d = fwrite("('000',1X,I8.8)", kurdat)[0]
            e.errhdl(e.PATH, "PVMRM_CALC", "W", "411", d)
        elif cod == 4991:
            from . import depura
            depura.numrise_error(e, e.PRMDBUNT, e.P.MXNW + 1, e.P.MXNW)
        elif cod in (6011, 6012, 6013):
            e.errhdl(e.PATH, {6011: "PCALC", 6012: "VCALC", 6013: "ACALC"}[cod], "E", "601", "GRSM")
