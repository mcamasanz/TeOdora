# -*- coding: utf-8 -*-
"""Compatibilidad de E/S y numérica con el Fortran de AERMET 26135 (US EPA, dominio público).

AERMET construye muchos FORMAT al vuelo (msg_form + sufijo) y lee los datos ONSITE con el FORMAT
que escribe el usuario, así que aquí hay un intérprete de FORMAT completo:

- ``fwrite(fmt, *items)``: WRITE formateado. Devuelve la lista de registros (una línea por registro).
- ``fread(fmt, registros, tipos)``: READ formateado.
- ``lread(registros, tipos)``: READ dirigido por lista (``read(...,*)``).
- ``Fichero``: fichero secuencial con registros, REWIND y escritura con CRLF (Intel en Windows).

Tipos de los elementos: ``int`` → entero, ``float`` → REAL, ``str`` → CHARACTER (ya con su
longitud declarada si importa), ``bool`` → LOGICAL.
"""
import math
import re
from decimal import Decimal, ROUND_HALF_UP

import numpy as np

F32 = np.float32

# Modo de redondeo de los empates exactos en la salida F/E/G ('even' = el de la biblioteca C).
EMPATE = "even"
# Cero negativo exacto (-0.0): Intel por defecto (-assume nominus0) lo escribe sin signo y SIGN lo
# trata como +0. Los negativos pequeños que se redondean a cero sí llevan signo ("-0.0").
MENOS_CERO = False


class ErrorEjecucion(RuntimeError):
    """Situación en la que el original aborta con un error de ejecución de Intel Fortran (una
    lectura interna sin IOSTAT que falla…) o no termina. `forrtl` es la línea que escribe el
    original en pantalla (None si no termina)."""

    def __init__(self, texto, forrtl=None):
        super().__init__(texto)
        self.forrtl = forrtl


FORRTL_EOF_LISTA = "forrtl: severe (24): end-of-file during read, unit -5, file Internal List-Directed Read"
FORRTL_CONV_FORMATO = "forrtl: severe (64): input conversion error, unit -5, file Internal Formatted Read"


def dsign(a, b):
    """SIGN/DSIGN: |a| con el signo de b (el -0.0 cuenta como positivo salvo MENOS_CERO)."""
    if b == 0 and not MENOS_CERO:
        return abs(a)
    return math.copysign(abs(a), b)


def nint(x):
    """NINT/IDNINT: redondeo al entero más cercano, empates LEJOS del cero."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def sngl(x):
    """SNGL / literal de precisión simple promovido a doble."""
    return float(F32(x))


def ftrunc(x):
    """INT() de un real: trunca hacia cero."""
    return int(x)


# ------------------------------------------------------------------------------------------
# Análisis del FORMAT
# ------------------------------------------------------------------------------------------
_CACHE = {}
_DATOS = {"A", "I", "F", "E", "ES", "EN", "D", "G", "L"}


def _analizar(fmt):
    """Devuelve (secuencia plana, índice de reversión)."""
    r = _CACHE.get(fmt)
    if r is not None:
        return r
    s = fmt.strip()
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
    items, _ = _lista(s, 0)
    # reversión: al último grupo entre paréntesis del nivel superior (con su repetición)
    plano = []
    rev = 0
    for it in items:
        if it[0] == "(":
            rev = len(plano)
        plano.extend(_expandir(it))
    r = (plano, rev)
    _CACHE[fmt] = r
    return r


def _expandir(it):
    if it[0] == "(":
        out = []
        for _ in range(it[1]):
            for sub in it[2]:
                out.extend(_expandir(sub))
        return out
    if it[0] == "R":
        return [it[2]] * it[1]
    return [it]


def _lista(s, i):
    items = []
    n = len(s)
    while i < n:
        c = s[i]
        if c in " ,":
            i += 1
            continue
        if c == ")":
            return items, i + 1
        if c in "'\"":
            q = c
            j = i + 1
            txt = []
            while j < n:
                if s[j] == q:
                    if j + 1 < n and s[j + 1] == q:
                        txt.append(q)
                        j += 2
                        continue
                    break
                txt.append(s[j])
                j += 1
            items.append(("S", "".join(txt)))
            i = j + 1
            continue
        if c == "/":
            items.append(("/",))
            i += 1
            continue
        if c == ":":
            items.append((":",))
            i += 1
            continue
        # contador de repetición opcional
        j = i
        while j < n and s[j].isdigit():
            j += 1
        cuenta = int(s[i:j]) if j > i else None
        i = j
        while i < n and s[i] == " ":
            i += 1
        if i < n and s[i] == "(":
            sub, i = _lista(s, i + 1)
            items.append(("(", cuenta or 1, sub))
            continue
        # nombre del descriptor
        j = i
        while j < n and s[j].isalpha():
            j += 1
        nombre = s[i:j].upper()
        i = j
        if nombre == "X":
            items.append(("X", cuenta if cuenta is not None else 1))
            continue
        if nombre == "P":
            items.append(("P", cuenta or 0))
            continue
        if nombre in ("BN", "BZ", "SP", "SS", "S"):
            items.append((nombre,))
            continue
        # anchura y decimales
        k = i
        while k < n and s[k].isdigit():
            k += 1
        w = int(s[i:k]) if k > i else None
        i = k
        d = None
        e = None
        if i < n and s[i] == ".":
            k = i + 1
            while k < n and s[k].isdigit():
                k += 1
            d = int(s[i + 1:k])
            i = k
            if i < n and s[i] in "eE" and nombre in ("E", "ES", "EN", "G", "D"):
                k = i + 1
                while k < n and s[k].isdigit():
                    k += 1
                if k > i + 1:
                    e = int(s[i + 1:k])
                    i = k
        if nombre in ("T", "TL", "TR"):
            items.append((nombre, w or 1))
            continue
        desc = (nombre, w, d, e)
        if cuenta and cuenta > 1:
            # repetición simple «4I2»: se expande en línea (no es grupo de reversión)
            items.append(("R", cuenta, desc))
        else:
            items.append(desc)
    return items, i


_plan = _analizar


# ------------------------------------------------------------------------------------------
# Conversión de salida
# ------------------------------------------------------------------------------------------
def _redondear(x, d):
    """Cadena decimal de |x| con d decimales (redondeo correcto del valor binario exacto)."""
    if EMPATE == "even":
        return "%.*f" % (d, abs(x))
    q = Decimal(abs(x)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    return format(q, "f")


def fmt_f(x, w, d):
    if x.__class__ is not float:
        if isinstance(x, bool):
            raise TypeError("F con LOGICAL")
        x = float(x)
    if x - x != 0.0 or EMPATE != "even":
        return _fmt_f_lento(x, w, d)
    if x == 0.0 and not MENOS_CERO:
        x = 0.0                                   # el -0.0 exacto se escribe sin signo
    s = "%.*f" % (d, x)
    if d == 0:
        s = s + "."
    n = len(s)
    if n <= w:
        return s if n == w else " " * (w - n) + s
    # el cero delante del punto es opcional
    if s.startswith("0."):
        s = s[1:]
    elif s.startswith("-0."):
        s = "-" + s[2:]
    if len(s) > w:
        return "*" * w
    return s.rjust(w)


def _fmt_f_lento(x, w, d):
    if math.isnan(x):
        return "NaN".rjust(w) if w >= 3 else "*" * w
    if math.isinf(x):
        s = ("-" if x < 0 else "") + ("Infinity" if w >= 8 + (x < 0) else "Inf")
        return s.rjust(w) if len(s) <= w else "*" * w
    s = _redondear(x, d)
    if d == 0:
        s = s + "."
    neg = x < 0 or (x == 0 and math.copysign(1.0, x) < 0 and MENOS_CERO)
    if neg:
        s = "-" + s
    if len(s) > w:
        if s.startswith("0."):
            s = s[1:]
        elif s.startswith("-0."):
            s = "-" + s[2:]
    if len(s) > w:
        return "*" * w
    return s.rjust(w)


def _mantisa(x, d):
    """Devuelve (dígitos, exponente k) con |x| = 0.dígitos × 10^k, d dígitos."""
    if x == 0:
        return "0" * d, 0
    if EMPATE == "even":
        t = "%.*e" % (d - 1, abs(x))
        m, ex = t.split("e")
        dig = m.replace(".", "")
        return dig, int(ex) + 1
    dx = Decimal(abs(x))
    k = dx.adjusted() + 1
    q = (dx.scaleb(-k)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    if q >= 1:
        k += 1
        q = (dx.scaleb(-k)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    dig = format(q, "f")[2:2 + d]
    return dig, k


def fmt_e(x, w, d, e=None):
    x = float(x)
    if math.isnan(x):
        return "NaN".rjust(w)
    dig, k = _mantisa(x, d)
    if e is None:
        if abs(k) <= 99:
            ex = "E%s%02d" % ("-" if k < 0 else "+", abs(k))
        elif abs(k) <= 999:
            ex = "%s%03d" % ("-" if k < 0 else "+", abs(k))
        else:
            return "*" * w
    else:
        ex = "E%s%0*d" % ("-" if k < 0 else "+", e, abs(k))
    s = "0." + dig + ex
    if x < 0:
        s = "-" + s
    if len(s) > w:
        s = s.replace("0.", ".", 1)
    if len(s) > w:
        return "*" * w
    return s.rjust(w)


def fmt_g(x, w, d, e=None):
    x = float(x)
    if math.isnan(x):
        return "NaN".rjust(w)
    n = 4 if e is None else e + 2
    if x == 0:
        return fmt_f(x, w - n, d - 1) + " " * n
    dig, k = _mantisa(x, d)
    if 0 <= k <= d:
        return fmt_f(x, w - n, d - k) + " " * n
    return fmt_e(x, w, d, e)


def fmt_i(v, w, m=None):
    if v.__class__ is not int:
        v = int(v)
    if m is None:
        s = str(v)
        if len(s) > w:
            return "*" * w
        return s.rjust(w)
    s = str(abs(v))
    if m is not None:
        if m == 0 and v == 0:
            s = ""
        s = s.rjust(m, "0")
    if v < 0:
        s = "-" + s
    if len(s) > w:
        return "*" * w
    return s.rjust(w)


def fmt_a(s, w):
    if isinstance(s, (int, np.integer)) and not isinstance(s, bool):
        # A con un INTEGER(4): Intel escribe sus bytes en memoria (little endian) como caracteres
        s = int(s).to_bytes(4, "little", signed=True).decode("latin-1")
    s = str(s)
    if w is None:
        return s
    if len(s) >= w:
        return s[:w]
    return s.rjust(w)


_RAPIDO = {}


def _compilar_rapido(fmt):
    """Plan secuencial (A, I, F, literales, X y ':') para la vía rápida de WRITE; False si el
    formato usa otros descriptores (tabuladores, '/', E, G…)."""
    plano, _ = _plan(fmt)
    segs = []
    ndatos = 0
    for dsc in plano:
        t = dsc[0]
        if t == "S":
            segs.append(dsc[1])
        elif t == "X":
            segs.append(dsc[1])
        elif t == ":":
            segs.append(None)
        elif t in ("A", "I", "F"):
            segs.append((t, dsc[1], dsc[2]))
            ndatos += 1
        else:
            _RAPIDO[fmt] = False
            return False
    r = (ndatos, segs, _plantilla(segs, ndatos))
    _RAPIDO[fmt] = r
    return r


def _plantilla(segs, ndatos):
    """Plantilla '%' equivalente al FORMAT cuando se escriben todos sus datos: (plantilla,
    anchura total, posiciones F, posiciones A) o None. Solo sirve si cada campo tiene anchura
    fija (A con anchura, I sin .0, F) y el redondeo es el de la biblioteca C."""
    if EMPATE != "even":
        return None
    partes = []
    ancho = 0
    pend = 0
    ndat = 0
    pos_f, pos_a = [], []
    for seg in segs:
        c = seg.__class__
        if c is int:
            pend += seg
            continue
        if seg is None:
            if ndat >= ndatos:
                break
            continue
        if pend:
            partes.append(" " * pend)
            ancho += pend
            pend = 0
        if c is str:
            partes.append(seg.replace("%", "%%"))
            ancho += len(seg)
            continue
        t, w, d = seg
        if w is None or w == 0:
            return None
        if t == "F":
            partes.append("%%%d.%df" % (w, d) if d else "%%%d.0f." % (w - 1))
            pos_f.append(ndat)
        elif t == "I":
            if d == 0:
                return None
            partes.append("%%%dd" % w if d is None else "%%%d.%dd" % (w, d))
        else:
            partes.append("%%%d.%ds" % (w, w))
            pos_a.append(ndat)
        ancho += w
        ndat += 1
    return "".join(partes), ancho, tuple(pos_f), tuple(pos_a)


def _con_plantilla(pl, items):
    """Registro con la plantilla '%'; None si algún valor necesita la vía general (no cabe,
    NaN/Inf, A que no es texto)."""
    plantilla, ancho, pos_f, pos_a = pl
    for i in pos_a:
        if items[i].__class__ is not str:
            return None
    try:
        if pos_f and not MENOS_CERO:
            it = list(items)
            for i in pos_f:
                it[i] = it[i] + 0.0           # el -0.0 exacto se escribe sin signo
            s = plantilla % tuple(it)
        else:
            s = plantilla % items
    except TypeError:
        return None
    if len(s) != ancho or "nan" in s or "inf" in s:
        return None
    return s


def _escribir_rapido(segs, items):
    out = []
    pend = 0
    idx = 0
    n = len(items)
    for seg in segs:
        c = seg.__class__
        if c is int:                          # nX: blancos que solo cuentan si sigue algo
            pend += seg
            continue
        if c is str:
            txt = seg
        elif seg is None:
            if idx >= n:
                break
            continue
        else:
            if idx >= n:
                break
            t, w, d = seg
            v = items[idx]
            idx += 1
            if t == "F":
                txt = fmt_f(v, w, d)
            elif t == "I":
                txt = fmt_i(v, w, d)
            elif v.__class__ is str and w is not None:
                txt = v[:w] if len(v) >= w else " " * (w - len(v)) + v
            else:
                txt = fmt_a(v, w)
        if pend:
            out.append(" " * pend)
            pend = 0
        out.append(txt)
    return "".join(out)


def fwrite(fmt, *items):
    """WRITE formateado: devuelve la lista de registros escritos."""
    r = _RAPIDO.get(fmt)
    if r is None:
        r = _compilar_rapido(fmt)
    if r and len(items) <= r[0]:
        if r[2] is not None and len(items) == r[0]:
            s = _con_plantilla(r[2], items)
            if s is not None:
                return [s]
        return [_escribir_rapido(r[1], items)]
    plano, rev = _plan(fmt)
    regs = []
    rec = []
    pos = 0
    idx = 0
    n = len(items)
    k = 0
    nplano = len(plano)

    def poner(txt):
        nonlocal pos
        if pos > len(rec):
            rec.extend(" " * (pos - len(rec)))
        fin = pos + len(txt)
        if pos == len(rec):
            rec.extend(txt)
        else:
            if fin > len(rec):
                rec.extend(" " * (fin - len(rec)))
            rec[pos:fin] = list(txt)
        pos = fin

    while True:
        if k == nplano:
            if idx >= n:
                break
            regs.append("".join(rec))
            rec = []
            pos = 0
            k = rev
            continue
        dsc = plano[k]
        t = dsc[0]
        if t in _DATOS:
            if idx >= n:
                break
            v = items[idx]
            idx += 1
            if t == "A":
                poner(fmt_a(v, dsc[1]))
            elif t == "I":
                poner(fmt_i(v, dsc[1], dsc[2]))
            elif t == "F":
                poner(fmt_f(v, dsc[1], dsc[2]))
            elif t in ("E", "ES", "D", "EN"):
                poner(fmt_e(v, dsc[1], dsc[2], dsc[3]))
            elif t == "G":
                if isinstance(v, str):
                    poner(fmt_a(v, dsc[1]))
                elif isinstance(v, (bool, np.bool_)):
                    poner(("T" if v else "F").rjust(dsc[1]))
                elif isinstance(v, (int, np.integer)):
                    poner(fmt_i(v, dsc[1]))
                else:
                    poner(fmt_g(v, dsc[1], dsc[2], dsc[3]))
            elif t == "L":
                poner(("T" if v else "F").rjust(dsc[1] or 1))
        elif t == "S":
            poner(dsc[1])
        elif t == "X":
            pos += dsc[1]
        elif t == "T":
            pos = dsc[1] - 1
        elif t == "TL":
            pos = max(0, pos - dsc[1])
        elif t == "TR":
            pos += dsc[1]
        elif t == "/":
            regs.append("".join(rec))
            rec = []
            pos = 0
        elif t == ":":
            if idx >= n:
                break
        k += 1
    regs.append("".join(rec))
    return regs


# ------------------------------------------------------------------------------------------
# Lectura formateada
# ------------------------------------------------------------------------------------------
class ErrorLectura(Exception):
    pass


_RE_ENTERO = re.compile(r"^[+-]?\d+$")
# separadores o formas especiales de la lectura dirigida por lista (y blancos que str.split
# trataría como separadores pero Fortran no)
_ESPECIAL_LISTA = re.compile(r"[,/'\"*\t\n\r\x0b\x0c\x1c-\x1f\x85\xa0]")
_RE_REAL_SIMPLE = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?\Z")
_RE_REAL = re.compile(r"^([+-]?)(\d*)(\.?)(\d*)(?:(?:[EeDdQq]([+-]?\d+))|([+-]\d+))?$")


def _a_entero(campo):
    t = campo.replace(" ", "")
    if t == "" or t in "+-":
        return 0
    if not _RE_ENTERO.match(t):
        raise ErrorLectura(campo)
    return int(t)


def _a_real(campo, d=0, lista=False):
    t = campo.replace(" ", "")
    # con punto decimal la d del descriptor no cuenta y float() de Python lee igual que Fortran,
    # salvo '_', exponentes D o sin letra y nan/inf (que van por la vía completa)
    if "." in t and "_" not in t and t[-1] not in "fFyYnN":
        try:
            return float(t)
        except ValueError:
            pass
    if t == "":
        if lista:
            raise ErrorLectura(campo)
        return 0.0
    tl = t.upper()
    if tl in ("NAN", "+NAN", "-NAN"):
        return float("nan")
    if tl in ("INF", "+INF", "INFINITY", "+INFINITY"):
        return float("inf")
    if tl in ("-INF", "-INFINITY"):
        return float("-inf")
    m = _RE_REAL.match(t)
    if not m:
        raise ErrorLectura(campo)
    sig, ent, pto, dec, ex1, ex2 = m.groups()
    if ent == "" and dec == "":
        if lista or t not in ("+", "-", "."):
            raise ErrorLectura(campo)
        return 0.0
    ex = int(ex1 if ex1 is not None else (ex2 if ex2 is not None else 0))
    if pto:
        txt = f"{sig}{ent or '0'}.{dec or '0'}e{ex}"
    else:
        dig = ent
        if d and not lista:
            if len(dig) <= d:
                dig = "0" * (d - len(dig) + 1) + dig
            txt = f"{sig}{dig[:-d]}.{dig[-d:]}e{ex}"
        else:
            txt = f"{sig}{dig}e{ex}"
    return float(txt)


_RAPIDO_L = {}


def _compilar_lectura(fmt):
    """Campos (descriptor, posición, anchura, decimales) de un FORMAT de lectura secuencial de
    un solo registro (I, F y A con anchura, nX); False si usa otros descriptores."""
    plano, _ = _plan(fmt)
    campos = []
    pos = 0
    for dsc in plano:
        t = dsc[0]
        if t == "X":
            pos += dsc[1]
        elif t in ("I", "F", "A") and dsc[1]:
            campos.append((t, pos, dsc[1], dsc[2] or 0))
            pos += dsc[1]
        else:
            campos = False
            break
    _RAPIDO_L[fmt] = campos
    return campos


def fread(fmt, registros, tipos):
    """READ formateado. `registros` es una lista de líneas (se consumen en orden con '/' o la
    reversión); `tipos` son 'i', 'f' o ('a', longitud). Devuelve (valores, iostat, nregistros)."""
    campos = _RAPIDO_L.get(fmt)
    if campos is None:
        campos = _compilar_lectura(fmt)
    if campos and len(tipos) <= len(campos):
        rec = registros if registros.__class__ is str else (registros[0] if registros else None)
        if rec is not None:
            vals = []
            try:
                for tipo, (t, pos, w, d) in zip(tipos, campos):
                    campo = rec[pos:pos + w]
                    if len(campo) < w:
                        campo = campo.ljust(w)
                    if t == "A":
                        lon = tipo[1] if tipo.__class__ is tuple else None
                        if lon is not None:
                            campo = campo[w - lon:] if w >= lon else campo.ljust(lon)
                        vals.append(campo)
                    elif tipo == "i":
                        if t != "I":
                            raise ErrorLectura(t)
                        vals.append(_a_entero(campo))
                    elif tipo == "f":
                        if t == "I":
                            raise ErrorLectura(t)
                        vals.append(_a_real(campo, d))
                    else:
                        vals.append(campo)
            except ErrorLectura:
                return vals, 1, 1
            return vals, 0, 1
    if isinstance(registros, str):
        registros = [registros]
    plano, rev = _plan(fmt)
    vals = []
    ir = 0
    if not registros:
        return vals, -1, 0
    rec = registros[0]
    pos = 0
    idx = 0
    n = len(tipos)
    k = 0
    nplano = len(plano)
    try:
        while True:
            if k == nplano:
                if idx >= n:
                    break
                ir += 1
                if ir >= len(registros):
                    return vals, -1, ir
                rec = registros[ir]
                pos = 0
                k = rev
                continue
            dsc = plano[k]
            t = dsc[0]
            if t in _DATOS:
                if idx >= n:
                    break
                tipo = tipos[idx]
                w = dsc[1]
                if t == "A":
                    lon = tipo[1] if isinstance(tipo, tuple) else None
                    if w is None:
                        w = lon if lon is not None else len(rec) - pos
                    campo = rec[pos:pos + w].ljust(w)
                    pos += w
                    if lon is not None:
                        if w >= lon:
                            campo = campo[w - lon:]
                        else:
                            campo = campo.ljust(lon)
                    vals.append(campo)
                else:
                    campo = rec[pos:pos + w].ljust(w) if w else ""
                    pos += w or 0
                    if tipo == "i":
                        if t != "I":
                            raise ErrorLectura(t)
                        vals.append(_a_entero(campo))
                    elif tipo == "f":
                        if t == "I":
                            raise ErrorLectura(t)
                        vals.append(_a_real(campo, dsc[2] or 0))
                    else:
                        vals.append(campo)
                idx += 1
            elif t == "X":
                pos += dsc[1]
            elif t == "T":
                pos = dsc[1] - 1
            elif t == "TL":
                pos = max(0, pos - dsc[1])
            elif t == "TR":
                pos += dsc[1]
            elif t == "/":
                ir += 1
                if ir >= len(registros):
                    if idx >= n:
                        break
                    return vals, -1, ir
                rec = registros[ir]
                pos = 0
            elif t == "S":
                pos += len(dsc[1])
            k += 1
    except ErrorLectura:
        return vals, 1, ir + 1
    return vals, 0, ir + 1


# ------------------------------------------------------------------------------------------
# Lectura dirigida por lista
# ------------------------------------------------------------------------------------------
def _fichas(rec):
    """Divide un registro en fichas de lectura dirigida por lista.
    Devuelve lista de ('v', texto, entrecomillado) | ('nulo',) | ('/',)."""
    out = []
    i = 0
    n = len(rec)
    previa_coma = True  # al principio del registro, una coma da un valor nulo
    hubo_valor = False
    while i < n:
        c = rec[i]
        if c in " \t":
            i += 1
            continue
        if c == ",":
            if not hubo_valor:
                out.append(("nulo",))
            hubo_valor = False
            i += 1
            continue
        if c == "/":
            out.append(("/",))
            return out
        if c in "'\"":
            q = c
            j = i + 1
            txt = []
            while j < n:
                if rec[j] == q:
                    if j + 1 < n and rec[j + 1] == q:
                        txt.append(q)
                        j += 2
                        continue
                    break
                txt.append(rec[j])
                j += 1
            out.append(("v", "".join(txt), True))
            i = j + 1
            hubo_valor = True
            continue
        j = i
        while j < n and rec[j] not in " \t,/":
            j += 1
        tok = rec[i:j]
        m = re.match(r"^(\d+)\*(.*)$", tok)
        if m:
            r = int(m.group(1))
            resto = m.group(2)
            if resto == "":
                out.extend([("nulo",)] * r)
            else:
                if resto[0] in "'\"":
                    resto = resto[1:-1] if len(resto) > 1 and resto[-1] == resto[0] else resto[1:]
                    out.extend([("v", resto, True)] * r)
                else:
                    out.extend([("v", resto, False)] * r)
        else:
            out.append(("v", tok, False))
        hubo_valor = True
        i = j
    return out


def lread(registros, tipos, previos=None):
    """READ(...,*) . `registros`: cadena (fichero interno) o lista de líneas (fichero externo:
    sigue en los registros siguientes). `tipos`: 'i', 'f', ('a', lon) o 'a'.
    Devuelve (valores, iostat, nregistros_consumidos). Los valores no asignados (fin de fichero,
    '/' o nulos) toman `previos[i]` si se da, si no None."""
    rec = registros if registros.__class__ is str else (registros[0] if registros else None)
    if rec is not None and not _ESPECIAL_LISTA.search(rec):
        toks = rec.split()
        if len(toks) >= len(tipos):
            vals = []
            for tipo, tok in zip(tipos, toks):
                if tipo == "i":
                    # int() de Python acepta además '_' entre cifras (Fortran no)
                    try:
                        if "_" in tok:
                            raise ValueError
                        vals.append(int(tok))
                    except ValueError:
                        return vals, 1, 1
                elif tipo == "f":
                    # float() de Python coincide con Fortran salvo '_', 'nan'/'inf' escritos de otra
                    # forma y exponentes D o sin letra: esos casos van por _a_real
                    try:
                        if "_" in tok or tok[-1] in "fFyYnN":
                            raise ValueError
                        vals.append(float(tok))
                    except ValueError:
                        try:
                            vals.append(_a_real(tok, lista=True))
                        except ErrorLectura:
                            return vals, 1, 1
                else:
                    lon = tipo[1] if tipo.__class__ is tuple else None
                    if lon is not None:
                        tok = tok[:lon] if len(tok) >= lon else tok + " " * (lon - len(tok))
                    vals.append(tok)
            return vals, 0, 1
    if isinstance(registros, str):
        registros = [registros]
    vals = []
    n = len(tipos)
    ir = 0
    fichas = []
    fi = 0
    if not registros:
        return vals, -1, 0
    fichas = _fichas(registros[0])
    ir = 1
    try:
        while len(vals) < n:
            if fi >= len(fichas):
                if ir >= len(registros):
                    return vals, -1, ir
                fichas = _fichas(registros[ir])
                ir += 1
                fi = 0
                continue
            f = fichas[fi]
            fi += 1
            iv = len(vals)
            if f[0] == "/":
                while len(vals) < n:
                    vals.append(previos[len(vals)] if previos else None)
                break
            if f[0] == "nulo":
                vals.append(previos[iv] if previos else None)
                continue
            tipo = tipos[iv]
            txt = f[1]
            if tipo == "i":
                if f[2]:
                    raise ErrorLectura(txt)
                if not _RE_ENTERO.match(txt):
                    raise ErrorLectura(txt)
                vals.append(int(txt))
            elif tipo == "f":
                if f[2]:
                    raise ErrorLectura(txt)
                vals.append(_a_real(txt, lista=True))
            else:
                lon = tipo[1] if isinstance(tipo, tuple) else None
                if lon is not None:
                    txt = txt[:lon].ljust(lon)
                vals.append(txt)
    except ErrorLectura:
        return vals, 1, ir
    return vals, 0, ir


# ------------------------------------------------------------------------------------------
# Ficheros secuenciales
# ------------------------------------------------------------------------------------------
class Fichero:
    """Fichero secuencial formateado. Lectura: lista de registros en memoria con puntero.
    Escritura: los registros se acumulan y se vuelcan con CRLF al cerrar (o con `volcar`)."""

    def __init__(self, nombre, modo="r", existente=True):
        self.nombre = nombre
        self.regs = []
        self.ptr = 0
        self.escrito = False
        if modo == "r" and existente:
            with open(nombre, "r", encoding="latin-1", newline=None) as fh:
                self.regs = fh.read().split("\n")
            if self.regs and self.regs[-1] == "":
                self.regs.pop()

    # lectura
    def leer(self):
        """Siguiente registro o None (fin de fichero)."""
        if self.ptr >= len(self.regs):
            return None
        r = self.regs[self.ptr]
        self.ptr += 1
        return r

    def restantes(self):
        return self.regs[self.ptr:]

    def avanzar(self, n):
        self.ptr += n

    def rewind(self):
        self.ptr = 0

    # escritura secuencial: escribir trunca el fichero tras el registro escrito
    def escribir(self, lineas):
        if isinstance(lineas, str):
            lineas = [lineas]
        if not self.escrito:
            self.regs = self.regs[:self.ptr]
            self.escrito = True
        del self.regs[self.ptr:]
        self.regs.extend(lineas)
        self.ptr = len(self.regs)

    def volcar(self):
        if self.escrito:
            with open(self.nombre, "w", encoding="latin-1", newline="") as fh:
                fh.write("".join(r + "\r\n" for r in self.regs))


def ch(s, i):
    """Carácter i (1-based) de una variable CHARACTER: blanco más allá de su contenido."""
    return s[i - 1] if 1 <= i <= len(s) else " "


def sub(s, i, j):
    """Subcadena s(i:j) de Fortran (1-based, inclusiva), con relleno de blancos."""
    if j < i:
        return ""
    t = s[i - 1:j]
    if len(t) < j - i + 1:
        t = t + " " * (j - i + 1 - len(t))
    return t


def adjustl(s):
    """ADJUSTL conservando la longitud."""
    t = s.lstrip(" ")
    return t + " " * (len(s) - len(t))


def fx(s, n):
    """Asignación a CHARACTER*n (trunca o rellena con blancos)."""
    s = str(s)
    return s[:n] if len(s) >= n else s + " " * (n - len(s))
