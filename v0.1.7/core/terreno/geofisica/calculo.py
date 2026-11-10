# -*- coding: utf-8 -*-
"""Geofísica de la malla para CALMET (GEO.DAT) a partir de fracciones de uso del suelo y cotas.

Implementación propia en SALA LIMPIA: escrita desde la documentación publicada y el comportamiento
observado del programa original usado solo como caja negra. Procedencia de cada regla en
``FUENTES.md del laboratorio`` (claves [Fn]).

Por celda:
  · las fracciones de las categorías de entrada (columnas del LU.DAT, asociadas POR POSICIÓN a las
    filas de la tabla de propiedades) se normalizan por su suma [F2, F5];
  · uso dominante [F3]: si el agua total (fracción bruta, sin normalizar) supera ESTRICTAMENTE
    CFRACT, la categoría de agua de mayor fracción; si no, la de tierra de mayor fracción; en
    empate, la primera columna; después se reasigna a su categoría de salida [F4];
  · z0 = exp(Σ fᵢ·ln z0ᵢ) (media logarítmica) y albedo, Bowen, flujo de calor del suelo, flujo
    antropogénico e índice de área foliar como medias aritméticas ponderadas por fᵢ [F1];
  · celda sin dato (suma ≤ 0,001): categoría IMISS con sus propiedades; suma entre 0,001 y FLUMIN:
    error fatal, sin GEO.DAT [F5].
"""
import math

import numpy as np


PROGRAMA = "GEO_PY (CIRCE)"
VERSION = "1.0"
NIVEL = "261017"
_MISS = 0.001


class ErrorGeo(Exception):
    """Error que impide escribir el GEO.DAT (el original para con un mensaje FATAL)."""


# ------------------------------------------------------------------------------- lectura
def _cabecera(lineas):
    """Cabecera «2.0» común a LU.DAT y TERR.DAT: (tipo, ncomm, comentarios, resto de líneas)."""
    tipo = lineas[0][:16].strip()
    ver = lineas[0][16:32].strip()
    if ver != "2.0":
        raise ErrorGeo("versión de %s no admitida: %r (solo 2.0)" % (tipo, ver))
    ncomm = int(lineas[1].split()[0])
    return tipo, lineas[2:2 + ncomm], lineas[2 + ncomm:]


def _malla(lineas, k):
    """PMAP, zona/hemisferio u origen, datum y la línea de la malla; devuelve (dict, índice)."""
    pmap = lineas[k][:8].strip()
    k += 1
    info = {"pmap": pmap}
    if pmap == "UTM":
        info["zona"] = lineas[k][:8]
        k += 1
    elif pmap in ("TTM", "LCC", "LAZA", "PS", "EM"):
        info["origen"] = lineas[k]
        k += 1
        if pmap in ("TTM", "LCC", "LAZA"):
            info["falso"] = lineas[k]
            k += 1
    info["datum"] = lineas[k]
    k += 1
    return info, k


def leer_lu(ruta):
    """LU.DAT de fracciones (formato 2.0): (malla, ncat, matriz [ny, nx, ncat] de fracciones)."""
    lineas = open(ruta, encoding="latin-1").read().replace("\r", "").split("\n")
    tipo, _com, resto = _cabecera(lineas)
    if resto[0].strip().upper() != "FRACTION":
        raise ErrorGeo("LU.DAT no está en formato de fracciones (FRACTION)")
    info, k = _malla(resto, 1)
    p = resto[k].split()
    nx, ny = int(p[0]), int(p[1])
    xo, yo, dx, dy = (float(v) for v in p[2:6])
    ncat = int(p[6])
    info.update(nx=nx, ny=ny, xorg=xo, yorg=yo, dgx=dx, dgy=dy, unidad=resto[k + 1])
    fr = np.zeros((ny, nx, ncat))
    # un registro por celda con columnas fijas: i, j (5 caracteres cada uno) y las ncat
    # fracciones (6 caracteres); lo que sigue en la línea no se usa
    for lin in resto[k + 2:]:
        if len(lin.strip()) == 0:
            continue
        i, j = int(lin[0:5]), int(lin[5:10])
        fr[j - 1, i - 1, :] = [float(lin[10 + 6 * c:16 + 6 * c]) for c in range(ncat)]
    return info, ncat, fr


def leer_terr(ruta):
    """TERR.DAT de cotas medias por celda (formato 2.0): (malla, matriz [ny, nx] con j=1 al sur)."""
    lineas = open(ruta, encoding="latin-1").read().replace("\r", "").split("\n")
    tipo, _com, resto = _cabecera(lineas)
    info, k = _malla(resto, 0)
    p = resto[k].split()
    nx, ny = int(p[0]), int(p[1])
    info.update(nx=nx, ny=ny, xorg=float(p[2]), yorg=float(p[3]), dgx=float(p[4]), dgy=float(p[5]),
                unidad=resto[k + 1])
    orden = resto[k + 2].split()
    vals = [float(v) for v in " ".join(resto[k + 3:]).split()][:nx * ny]
    z = np.array(vals).reshape(ny, nx)
    if orden[:2] == ["W_E", "N_S"]:
        z = z[::-1, :]
    elif orden[:2] != ["W_E", "S_N"]:
        raise ErrorGeo("orden de TERR.DAT no admitido: %r" % orden)
    return info, z


# ------------------------------------------------------------------------------- cálculo
class Tabla:
    """Propiedades por categoría de entrada (grupo 4b) y datos de las categorías de salida."""

    def __init__(self, c):
        filas = c.lista("X")
        self.ident = [int(float(f[0])) for f in filas]
        self.prop = np.array([[float(x) for x in f[1:7]] for f in filas])   # z0, alb, bowen, hcg, qf, lai
        self.salida = [int(float(f[7])) for f in filas]
        self.agua = {int(float(x)) for f in c.lista("IWAT") for x in f}
        self.outcat = [int(float(x)) for f in c.lista("OUTCAT") for x in f]


def calcular(c, tabla, fr):
    """Campos de salida a partir de las fracciones [ny, nx, ncat]. Devuelve dict de matrices."""
    ny, nx, ncat = fr.shape
    if ncat != len(tabla.ident):
        raise ErrorGeo("el LU.DAT trae %d categorías y la tabla %d" % (ncat, len(tabla.ident)))
    cfract = c.real("CFRACT", 0.5)
    flumin = c.real("FLUMIN", 0.96)
    imiss = c.entero("IMISS", 55)
    es_agua = np.array([i in tabla.agua for i in tabla.ident])
    total = fr.sum(axis=2)
    sin_dato = total <= _MISS
    parcial = (~sin_dato) & (total < flumin)
    # con una IMISS que no está entre las categorías de entrada no hay GEO.DAT, pero sí los GRD de
    # control, con el propio valor IMISS en las celdas sin dato [F5]
    kmiss = tabla.ident.index(imiss) if imiss in tabla.ident else None
    # uso dominante: el agua (fracción BRUTA, sin normalizar) debe superar CFRACT [F3]; argmax
    # devuelve la primera columna en caso de empate
    agua = fr[:, :, es_agua].sum(axis=2)
    sel = np.where((agua > cfract)[:, :, None], es_agua[None, None, :], ~es_agua[None, None, :])
    k = np.argmax(np.where(sel, fr, -1.0), axis=2)
    salida = np.array(tabla.salida)
    lu = salida[k]
    # aritmética en precisión simple, como el original [F6]: suma secuencial (por columnas) de
    # fᵢ·pᵢ, con cada producto y cada suma redondeados a simple, dividida por la suma de
    # fracciones; sumar los términos nulos no cambia nada, así que se recorren todas las columnas
    f32 = np.float32
    prop = tabla.prop.astype(f32)
    lnz0 = np.array([f32(math.log(float(p))) for p in prop[:, 0]], dtype=f32)
    fr32 = fr.astype(f32)
    tot = np.zeros((ny, nx), dtype=f32)
    for c in range(ncat):
        tot = (tot + fr32[:, :, c]).astype(f32)
    tot_div = np.where(sin_dato, f32(1), tot).astype(f32)
    campos = np.zeros((6, ny, nx))
    for p in range(6):
        col = lnz0 if p == 0 else prop[:, p]
        s = np.zeros((ny, nx), dtype=f32)
        for c in range(ncat):
            s = (s + (fr32[:, :, c] * col[c]).astype(f32)).astype(f32)
        v = (s / tot_div).astype(f32)
        campos[p] = np.exp(v.astype(np.float64)).astype(f32) if p == 0 else v
    # celdas sin dato: categoría IMISS con sus propiedades (o el propio valor si no existe) [F5]
    if kmiss is None:
        lu = np.where(sin_dato, imiss, lu)
        campos[:, sin_dato] = np.nan
    else:
        lu = np.where(sin_dato, tabla.salida[kmiss], lu)
        campos[:, sin_dato] = prop[kmiss][:, None].astype(np.float64)
    return {"imiss_valida": kmiss is not None, "lu": lu, "z0": campos[0], "albedo": campos[1], "bowen": campos[2], "hcg": campos[3],
            "qf": campos[4], "lai": campos[5], "total": total, "sin_dato": sin_dato, "parcial": parcial}


# ------------------------------------------------------------------------------- escritura
def _fila(vals, fmt, por_linea=None):
    """Valores de una fila con el formato y comas como separador; partida en líneas si se pide."""
    txt = [fmt % v for v in vals]
    if por_linea is None:
        return [",".join(txt)]
    out = []
    for k in range(0, len(txt), por_linea):
        trozo = txt[k:k + por_linea]
        fin = k + por_linea >= len(txt)
        out.append(",".join(trozo) + ("" if fin else ","))
    return out


def _f(x, w, d):
    """Fortran Fw.d (asteriscos si no cabe). Un valor que redondea a cero se escribe sin signo,
    como hace el original [F7]."""
    s = "%*.*f" % (w, d, x)
    if s.lstrip().startswith("-") and float(s) == 0.0:
        s = ("%*.*f" % (w, d, 0.0))
    if s.startswith("-0.") and len(s) > w:
        s = "-" + s[2:]
    elif s.startswith("0.") and len(s) > w:
        s = s[1:]
    return s if len(s) <= w else "*" * w


def escribir_geo(ruta, c, malla, campos, z, comentario=None):
    nx, ny = malla["nx"], malla["ny"]
    tabla = c._tabla
    L = ["GEO.DAT".ljust(16) + "2.0".ljust(16) + "Header structure with coordinate parameters".ljust(64),
         "%4d" % 2,
         (comentario or "Produced by %s Version: %s  Level: %s" % (PROGRAMA, VERSION, NIVEL)).ljust(80)[:80],
         c.titulo.ljust(80)[:80],
         malla["pmap"].ljust(8)]
    pmap = malla["pmap"]
    if pmap == "UTM":
        L.append(malla["zona"])
    else:
        L.append(malla["origen"])
        if "falso" in malla:
            L.append(malla["falso"])
    L.append(malla["datum"])
    L.append("%8d%8d%12.3f%12.3f%12.3f%12.3f" % (nx, ny, malla["xorg"], malla["yorg"], malla["dgx"],
                                                 malla["dgy"]))
    L.append("KM  M   ")
    L.append(" 1          - LAND USE DATA - (1=new categories)")
    iw1, iw2 = c.entero("IWAT1", 50), c.entero("IWAT2", 55)
    L.append(" %4d%4d%4d - NLU, IWAT1, IWAT2" % (len(tabla.outcat), iw1, iw2))
    L.append(" " + "".join("%4d" % v for v in tabla.outcat))
    for j in range(ny - 1, -1, -1):
        L += _fila(campos["lu"][j], "%7d", 10)
    L.append(" 1.0000  - TERRAIN heights - HTFAC (Conversion to meters)".ljust(81))
    for j in range(ny - 1, -1, -1):
        L += _fila([_f(v, 7, 2) for v in z[j]], "%s", 100)
    for clave, txt, d in (("z0", "gridded z0 field", 4), ("albedo", "gridded albedo field", 2),
                          ("bowen", "gridded Bowen ratio field", 2),
                          ("hcg", "gridded soil heat flux parameters", 2),
                          ("qf", "gridded anthropogenic heat flux field", 2),
                          ("lai", "gridded leaf area index field", 2)):
        L.append((" 2    - " + txt).ljust(78))
        for j in range(ny - 1, -1, -1):
            L += _fila([_f(v, 7, d) for v in campos[clave][j]], "%s", 100)
    with open(ruta, "w", encoding="latin-1", newline="") as fh:
        fh.write("\r\n".join(L) + "\r\n")


def _e_fortran(x, w, d):
    """Fortran Ew.d sin factor de escala: 0.ddddE+ee."""
    if x == 0.0:
        m, e = 0.0, 0
    else:
        e = int(math.floor(math.log10(abs(x)))) + 1
        m = abs(x) / 10.0 ** e
        if round(m, d) >= 1.0:
            m /= 10.0
            e += 1
    s = "%s0.%0*dE%+03d" % ("-" if x < 0 else "", d, int(round(m * 10 ** d)), e)
    return s.rjust(w)


def escribir_grd(ruta_lu, ruta_te, malla, campos, z, vacios=False):
    """Ficheros de control en formato Surfer ASCII (DSAA): uso del suelo y cotas, de sur a norte.
    El de cotas solo si no son constantes. Con ``vacios`` (error fatal) se crean sin contenido,
    como deja el original los ficheros que ya tenía abiertos [F8]."""
    cotas = bool(z.max() > z.min())
    if vacios:
        for ruta in (ruta_lu, ruta_te):
            open(ruta, "w").close()
        return
    nx, ny = malla["nx"], malla["ny"]
    def centro(o, d, k):
        # centro de la celda k como (origen + k·d) − d/2, en precisión simple [F9]
        f = np.float32
        return float(f(f(f(o) + f(f(k) * f(d))) - f(f(d) * f(0.5))))
    x0, x1 = centro(malla["xorg"], malla["dgx"], 1), centro(malla["xorg"], malla["dgx"], nx)
    y0, y1 = centro(malla["yorg"], malla["dgy"], 1), centro(malla["yorg"], malla["dgy"], ny)
    cab = ["DSAA", "%12d%12d" % (nx, ny), "%12.4f%12.4f" % (x0, x1), "%12.4f%12.4f" % (y0, y1)]
    L = cab + ["%12d%12d" % (10, 100)]
    for j in range(ny):
        L.append("  ".join("%3d" % abs(v) for v in campos["lu"][j]))     # valor absoluto [F8]
    with open(ruta_lu, "w", encoding="latin-1", newline="") as fh:
        fh.write("\r\n".join(L) + "\r\n")
    if not cotas:
        return
    L = cab + [_e_fortran(float(z.min()), 12, 4) + _e_fortran(float(z.max()), 12, 4)]
    for j in range(ny):
        L.append(" ".join("%11.4E" % (v + 0.0) for v in z[j]))    # (+0.0: el -0.0 sin signo)
    with open(ruta_te, "w", encoding="latin-1", newline="") as fh:
        fh.write("\r\n".join(L) + "\r\n")
