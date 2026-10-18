# -*- coding: utf-8 -*-
"""Adaptador de datos propios a la rejilla de CALMET: CORINE Land Cover + MDT -> fracciones de uso
del suelo y cota media por celda, y de ahí LU.DAT, TERR.DAT y el fichero de control.

Decisiones propias (no vienen del programa original; ver FUENTES.md del laboratorio [A1]-[A4]):
  · las categorías de ENTRADA son las 44 clases de nivel 3 de CORINE (nomenclatura de la EEA),
    cada una asignada a una categoría CALMET de 14 clases con la misma tabla que ya usa
    digicompost (``CLC_TO_CALMET``, coherente con la de AERSURFACE de la fase 01);
  · las propiedades de superficie de cada clase son las de su categoría CALMET en la tabla 4-45
    de la guía de CALMET (z0, albedo, Bowen, flujo de calor del suelo, antropogénico, LAI);
  · fracción de una clase en una celda = píxeles de la clase / píxeles con dato del bloque; un
    bloque sin ningún píxel con dato queda sin dato (categoría IMISS);
  · cota de la celda = media de las cotas del bloque.
"""
import numpy as np

# 44 clases de CORINE (nivel 3) -> categoría CALMET (esquema de 14 clases)
CORINE_A_CALMET = {
    111: 10, 112: 10, 121: 10, 122: 10, 123: 10, 124: 10,          # urbano
    131: 70, 132: 70, 133: 70,                                     # extracción, vertido, obra
    141: 10, 142: 10,                                              # verde urbano y deportivo
    211: 20, 213: 20, 241: 20, 242: 20, 243: 20,                   # secano
    212: -20, 214: -20,                                            # regadío (y arrozal 213 aparte)
    221: 20, 222: 20, 223: 20,                                     # viñedo, frutal, olivar
    231: 30, 321: 30,                                              # pradera, pastizal
    311: 40, 312: 40, 313: 40, 244: 40,                            # bosque y agroforestal
    322: 30, 323: 30, 324: 30,                                     # matorral
    331: 70, 332: 70, 333: 70, 334: 70, 335: 90,                   # desnudo; glaciar
    411: 60, 412: 60, 421: 60, 422: 60, 423: 60,                   # humedal
    511: 51, 512: 51, 521: 55, 522: 55, 523: 55,                   # agua
}

# Tabla 4-45 de la guía de CALMET (2000): z0 (m), albedo, Bowen, flujo de calor del suelo,
# flujo antropogénico (W/m2), índice de área foliar
CALMET_PROPIEDADES = {
    10: (1.0, 0.18, 1.5, 0.25, 0.0, 0.2), 20: (0.25, 0.15, 1.0, 0.15, 0.0, 3.0),
    -20: (0.25, 0.15, 0.5, 0.15, 0.0, 3.0), 30: (0.05, 0.25, 1.0, 0.15, 0.0, 0.5),
    40: (1.0, 0.10, 1.0, 0.15, 0.0, 7.0), 51: (0.001, 0.10, 0.0, 1.0, 0.0, 0.0),
    54: (0.001, 0.10, 0.0, 1.0, 0.0, 0.0), 55: (0.001, 0.10, 0.0, 1.0, 0.0, 0.0),
    60: (1.0, 0.10, 0.5, 0.25, 0.0, 2.0), 61: (1.0, 0.10, 0.5, 0.25, 0.0, 2.0),
    62: (0.2, 0.10, 0.1, 0.25, 0.0, 1.0), 70: (0.05, 0.30, 1.0, 0.15, 0.0, 0.05),
    80: (0.20, 0.30, 0.5, 0.15, 0.0, 0.0), 90: (0.20, 0.70, 0.5, 0.15, 0.0, 0.0),
}
SALIDA = [10, 20, -20, 30, 40, 51, 54, 55, 60, 61, 62, 70, 80, 90]
CODIGOS = sorted(CORINE_A_CALMET)
AGUA = [c for c in CODIGOS if CORINE_A_CALMET[c] in (51, 54, 55)]
IMISS = 523                                   # mar (como la categoría 55 del original)


def malla_calmet(ext, forma, res_m):
    """Factor de agregación y malla gruesa (alineada con la esquina SO de la fina)."""
    ny, nx = forma
    dx = (ext[1] - ext[0]) / nx
    fac = max(1, int(round(res_m / dx)))
    return fac, ny // fac, nx // fac, fac * dx


def fracciones(uso, fac):
    """Fracción de cada clase CORINE (columnas en el orden de CODIGOS) por celda gruesa.
    La fila 0 es la del SUR, como en la rejilla fina."""
    nyc, nxc = uso.shape[0] // fac, uso.shape[1] // fac
    b = uso[:nyc * fac, :nxc * fac].reshape(nyc, fac, nxc, fac).transpose(0, 2, 1, 3).reshape(nyc, nxc, -1)
    idx = {c: k for k, c in enumerate(CODIGOS)}
    fr = np.zeros((nyc, nxc, len(CODIGOS)))
    for c, k in idx.items():
        fr[:, :, k] = (b == c).sum(axis=2)
    validos = fr.sum(axis=2)
    with np.errstate(invalid="ignore", divide="ignore"):
        fr = np.where(validos[:, :, None] > 0, fr / validos[:, :, None], 0.0)
    return fr


def cotas(z, fac):
    nyc, nxc = z.shape[0] // fac, z.shape[1] // fac
    return z[:nyc * fac, :nxc * fac].reshape(nyc, fac, nxc, fac).mean(axis=(1, 3))


def escribir_lu(ruta, fr, x0_km, y0_km, d_km, zona=30, hem="N", datum="WGS-84"):
    ny, nx, ncat = fr.shape
    L = ["LU.DAT".ljust(16) + "2.0".ljust(16) + "Header structure with coordinate parameters".ljust(64),
         "%4d" % 1, "Fracciones de uso del suelo CORINE por celda (GEO_PY, CIRCE)".ljust(80),
         "FRACTION", "UTM     ", ("%4d%s" % (zona, hem)).ljust(8), datum.ljust(8) + "02-21-2003  ",
         "%8d%8d%12.3f%12.3f%12.3f%12.3f%6d" % (nx, ny, x0_km, y0_km, d_km, d_km, ncat), "KM  "]
    for j in range(ny):
        for i in range(nx):
            L.append("%5d%5d" % (i + 1, j + 1) + "".join("%6.3f" % v for v in fr[j, i]))
    with open(ruta, "w", encoding="latin-1", newline="") as fh:
        fh.write("\r\n".join(L) + "\r\n")


def escribir_terr(ruta, z, x0_km, y0_km, d_km, zona=30, hem="N", datum="WGS-84"):
    ny, nx = z.shape
    L = ["TERREL.DAT".ljust(16) + "2.0".ljust(16) + "Header structure with coordinate parameters".ljust(64),
         "%4d" % 1, "Cota media por celda (GEO_PY, CIRCE)".ljust(80),
         "UTM     ", ("%4d%s" % (zona, hem)).ljust(8), datum.ljust(8) + "02-21-2003  ",
         "%8d%8d%12.3f%12.3f%12.3f%12.3f" % (nx, ny, x0_km, y0_km, d_km, d_km), "KM  M   ", "W_E N_S "]
    for j in range(ny - 1, -1, -1):
        for k in range(0, nx, 10):
            L.append("".join("%8.1f" % v for v in z[j, k:k + 10]))
    with open(ruta, "w", encoding="latin-1", newline="") as fh:
        fh.write("\r\n".join(L) + "\r\n")


def escribir_control(ruta, titulo, nx, ny, x0_km, y0_km, d_km, ludat="lu.dat", terrdat="terr.dat",
                     geodat="geo.dat", runlst="geo.lst", zona=30, hem="N", datum="WGS-84"):
    """Fichero de control con la sintaxis publicada (grupos 0 a 4)."""
    L = [titulo, "", "Grupo 0 -- ficheros",
         "! LUDAT = %s !  ! TERRDAT = %s !  ! GEODAT = %s !  ! RUNLST = %s !" % (ludat, terrdat, geodat, runlst),
         "! LCFILES = T !", "!END!", "", "Grupo 1 -- control",
         "! LTERR = T !  ! LLU2 = F !  ! IXQA = 0 !  ! IYQA = 0 !", "!END!", "",
         "Grupo 2 -- proyección y malla",
         "! PMAP = UTM !  ! IUTMZN = %d !  ! UTMHEM = %s !  ! DATUM = %s !" % (zona, hem, datum),
         "! XREFKM = %.3f !  ! YREFKM = %.3f !  ! NX = %d !  ! NY = %d !  ! DGRIDKM = %.4f !"
         % (x0_km, y0_km, nx, ny, d_km), "!END!", "",
         "Grupo 3a -- categorías de salida",
         "! NOUTCAT = %d !  ! IWAT1 = 50 !  ! IWAT2 = 55 !" % len(SALIDA), "!END!",
         "Grupo 3b"]
    for k in range(0, len(SALIDA), 10):
        L.append("! OUTCAT = %s !  !END!" % ", ".join(str(v) for v in SALIDA[k:k + 10]))
    L += ["", "Grupo 4a -- categorías de entrada (CORINE nivel 3)",
          "! NINCAT = %d !  ! NUMWAT = %d !  ! NSPLIT = 0 !" % (len(CODIGOS), len(AGUA)),
          "! CFRACT = 0.5 !  ! IMISS = %d !  ! FLUMIN = 0.96 !" % IMISS, "!END!",
          "Grupo 4b -- clase, z0, albedo, Bowen, flujo suelo, antropogénico, LAI, categoría CALMET"]
    for c in CODIGOS:
        cal = CORINE_A_CALMET[c]
        p = CALMET_PROPIEDADES[cal]
        L.append("! X = %d, %s, %s, %s, %s, %s, %s, %d !  !END!" % ((c,) + tuple(repr(v) for v in p) + (cal,)))
    L += ["Grupo 4c -- clases de agua"] + ["! IWAT = %d !  !END!" % c for c in AGUA]
    with open(ruta, "w", encoding="latin-1", newline="") as fh:
        fh.write("\r\n".join(L) + "\r\n")


def preparar(carpeta, uso, z, ext, res_m=250.0, titulo="GEO.DAT desde CORINE y MDT", zona=30, hem="N",
             datum="WGS-84"):
    """Escribe en `carpeta` lu.dat, terr.dat y geo.inp para la malla CALMET de `res_m` metros a
    partir de las rejillas finas (fila 0 al sur) de CORINE y cotas. Devuelve la malla."""
    from pathlib import Path
    carpeta = Path(carpeta)
    fac, nyc, nxc, d = malla_calmet(ext, uso.shape, res_m)
    x0, y0, dk = ext[0] / 1000.0, ext[2] / 1000.0, d / 1000.0
    escribir_lu(carpeta / "lu.dat", fracciones(uso, fac), x0, y0, dk, zona, hem, datum)
    escribir_terr(carpeta / "terr.dat", cotas(z, fac), x0, y0, dk, zona, hem, datum)
    escribir_control(carpeta / "geo.inp", titulo, nxc, nyc, x0, y0, dk, zona=zona, hem=hem, datum=datum)
    return {"nx": nxc, "ny": nyc, "x0_km": x0, "y0_km": y0, "d_km": dk, "fac": fac}
