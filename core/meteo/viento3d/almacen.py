# -*- coding: utf-8 -*-
"""Almacén comprimido del fichero de viento 3D (salida de `meteo.viento3d`): un fichero .cmz por
periodo (un mes, p. ej.) y su reconstrucción, y lectura de UNA variable sin reconstruir nada.

El fichero de viento es Fortran secuencial sin formato: cada registro va entre dos marcadores int32
con su longitud. Los registros de campo 2D llevan
    etiqueta (8 caracteres) · fecha int32 (AAAAJJJHH) · NX·NY valores de 4 bytes.
Compresión (medida en casos reales: ≈ 9× con 125×125 celdas y 12 capas):
  · cabeceras y cualquier registro que no sea un campo 2D: tal cual (sin pérdida);
  · campos ENTEROS (estabilidad, código de precipitación, uso del suelo, estación más cercana):
    sin pérdida;
  · EL (longitud de Monin-Obukhov) y los campos con rango muy amplio: float32 sin pérdida;
  · el resto de reales: cuantizados a 16 bits con UNA escala por variable y fichero, diferencia
    entre horas consecutivas y byte-shuffle. Error máximo = paso/2 (≈ rango/130 000).
Todo con zlib (biblioteca estándar). Viene del proyecto de La Galera (2026-10-23), donde guarda 5
años de viento horario; los .cmz ya escritos se leen igual (el formato no cambia).
"""
import io
import json
import struct
import zipfile
import zlib
from collections import defaultdict
from pathlib import Path

import numpy as np

ENTEROS = {"IPGT", "IRH", "IPCODE", "ILANDU", "NEARS"}
SIN_PERDIDA = {"EL"}
NIVEL_ZLIB = 6
PASOS = 65000.0


def _registros(ruta):
    """Itera (bytes del registro) de un fichero Fortran secuencial."""
    with open(ruta, "rb") as f:
        while True:
            h = f.read(4)
            if len(h) < 4:
                return
            n = struct.unpack("<i", h)[0]
            b = f.read(n)
            f.read(4)
            yield b


def _barajar(a):
    b = np.ascontiguousarray(a).view(np.uint8).reshape(-1, a.dtype.itemsize)
    return np.ascontiguousarray(b.T).tobytes()


def _desbarajar(datos, dtype, n):
    it = np.dtype(dtype).itemsize
    b = np.frombuffer(datos, np.uint8).reshape(it, n)
    return np.ascontiguousarray(b.T).view(dtype).reshape(n)


def _nombre(etiqueta):
    """«U-LEV  3» -> «U-LEV»; las etiquetas sin número de nivel se quedan igual."""
    return etiqueta.rstrip("0123456789 ").strip() or etiqueta.strip()


# Paso mínimo de cuantización por variable (opcional, `pasos`): por debajo de esto la
# diferencia no tiene sentido físico (un anemómetro mide al 0,1 m/s) y comprime mucho mejor.
PASOS_FISICOS = {"U-LEV": 0.01, "V-LEV": 0.01, "WFACE": 0.001, "T-LEV": 0.01, "TEMPK": 0.01}


def comprimir(dat, destino, nx, ny, pasos=None, recorte=None):
    """Fichero de viento -> .cmz. Devuelve un resumen con tamaños y error máximo por variable.
    recorte = (año, mes, horas, primera_fecha AAAAJJJHH): quita AL VUELO los registros de las
    horas de arranque y corrige la cabecera, sin escribir una copia del fichero (con meses de
    2,8 GB, esa copia llegó a llenar el disco)."""
    n2d = 12 + 4 * nx * ny
    orden = []                                  # ("c", idx_cabecera) | ("f", etiqueta)
    cabeceras = []
    series = defaultdict(list)                  # etiqueta -> [bytes de valores]
    fechas = defaultdict(list)
    for b in _registros(dat):
        etq = b[:8].decode("latin-1") if len(b) >= 8 else ""
        if recorte and len(b) == 148 and struct.unpack_from("<i", b, 0)[0] > 1900:
            v = list(struct.unpack_from("<10i", b, 0))
            v[0:4] = [recorte[0], recorte[1], 1, 0]
            v[5] = recorte[2]
            b = struct.pack("<10i", *v) + b[40:]
        if (recorte and len(b) == n2d and etq.isprintable()
                and 0 < struct.unpack_from("<i", b, 8)[0] < recorte[3]):
            continue                                       # hora de arranque: fuera
        if len(b) == n2d and etq.isprintable():
            orden.append(etq)
            series[etq].append(b[12:])
            fechas[etq].append(struct.unpack("<i", b[8:12])[0])
        else:
            orden.append(len(cabeceras))
            cabeceras.append(b)

    buf = io.BytesIO()
    indice = {"nx": nx, "ny": ny, "orden": orden, "variables": {}}
    errores, crudo = {}, 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        cab = b"".join(struct.pack("<i", len(c)) + c for c in cabeceras)
        z.writestr("cabeceras.z", zlib.compress(cab, 9))
        for k, (etq, lista) in enumerate(series.items()):
            nom = _nombre(etq)
            crudo += len(lista) * (n2d + 8)
            fz = np.asarray(fechas[etq], np.int32)
            meta = {"fichero": f"v{k:03d}.z", "horas": len(lista),
                    "fechas": f"v{k:03d}.t"}
            z.writestr(meta["fechas"], zlib.compress(np.diff(fz, prepend=0).astype("<i4")
                                                     .tobytes(), 9))
            if nom in ENTEROS:
                a = np.frombuffer(b"".join(lista), "<i4")
                meta["tipo"] = "i4"
                datos = _barajar(a)
                errores[nom] = 0.0
            else:
                a = np.frombuffer(b"".join(lista), "<f4").reshape(len(lista), nx * ny)
                lo, hi = float(a.min()), float(a.max())
                esc = max((hi - lo) / PASOS, (pasos or {}).get(nom, 0.0))
                # campos estáticos (una sola hora: ELEV, Z0, XLAI…) también tal cual
                if (nom in SIN_PERDIDA or len(lista) == 1 or not np.isfinite(esc)
                        or esc == 0.0):
                    meta["tipo"] = "f4"
                    datos = _barajar(a.ravel())
                    errores[nom] = max(errores.get(nom, 0.0), 0.0)
                else:
                    q = np.round((a.astype(np.float64) - lo) / esc).astype(np.int32)
                    # primera hora centrada en int16 y, después, diferencias entre horas
                    d = np.diff(q, axis=0, prepend=np.full((1, q.shape[1]), 32500, np.int32))
                    meta.update({"tipo": "q16", "lo": lo, "esc": esc})
                    if d.min() >= -32768 and d.max() <= 32767:
                        meta["delta"] = True
                        datos = _barajar(d.astype("<i2").ravel())
                    else:
                        meta["delta"] = False
                        datos = _barajar((q - 32500).astype("<i2").ravel())
                    rec = (q.astype(np.float64) * esc + lo).astype(np.float32)
                    errores[nom] = max(errores.get(nom, 0.0), float(np.abs(rec - a).max()))
            z.writestr(meta["fichero"], zlib.compress(datos, NIVEL_ZLIB))
            indice["variables"][etq] = meta
        z.writestr("indice.json", json.dumps(indice))
    Path(destino).write_bytes(buf.getvalue())
    total = Path(dat).stat().st_size
    return {"original_mb": total / 1e6, "comprimido_mb": Path(destino).stat().st_size / 1e6,
            "ratio": total / Path(destino).stat().st_size, "errores": errores,
            "campos_mb": crudo / 1e6}


def leer_campo(cmz, etiqueta):
    """Una sola variable de un .cmz sin reconstruir el fichero de viento (p. ej. «U-LEV  1» para
    el viento del nivel 1). Devuelve (fechas AAAAJJJHH int32, valores (horas, ny, nx) float32)."""
    with zipfile.ZipFile(cmz) as z:
        indice = json.loads(z.read("indice.json"))
        nx, ny = indice["nx"], indice["ny"]
        meta = indice["variables"][etiqueta]
        h = meta["horas"]
        fz = np.cumsum(np.frombuffer(zlib.decompress(z.read(meta["fechas"])), "<i4"))
        datos = zlib.decompress(z.read(meta["fichero"]))
    if meta["tipo"] in ("i4", "f4"):
        a = _desbarajar(datos, "<" + meta["tipo"], h * nx * ny).astype(np.float32)
    else:
        d = _desbarajar(datos, "<i2", h * nx * ny).reshape(h, nx * ny).astype(np.int32)
        q = (np.cumsum(d, axis=0) if meta["delta"] else d) + 32500
        a = (q.astype(np.float64) * meta["esc"] + meta["lo"]).astype(np.float32)
    return fz.astype(np.int32), a.reshape(h, ny, nx)


def descomprimir(cmz, destino):
    """.cmz -> fichero de viento con la misma secuencia de registros que el original."""
    with zipfile.ZipFile(cmz) as z:
        indice = json.loads(z.read("indice.json"))
        nxy = indice["nx"] * indice["ny"]
        cab_raw = zlib.decompress(z.read("cabeceras.z"))
        cabeceras, i = [], 0
        while i < len(cab_raw):
            n = struct.unpack_from("<i", cab_raw, i)[0]
            cabeceras.append(cab_raw[i + 4:i + 4 + n])
            i += 4 + n
        campos = {}
        for etq, meta in indice["variables"].items():
            h = meta["horas"]
            fz = np.cumsum(np.frombuffer(zlib.decompress(z.read(meta["fechas"])), "<i4"))
            datos = zlib.decompress(z.read(meta["fichero"]))
            if meta["tipo"] == "i4":
                a = _desbarajar(datos, "<i4", h * nxy).reshape(h, nxy)
            elif meta["tipo"] == "f4":
                a = _desbarajar(datos, "<f4", h * nxy).reshape(h, nxy)
            else:
                d = _desbarajar(datos, "<i2", h * nxy).reshape(h, nxy).astype(np.int32)
                q = (np.cumsum(d, axis=0) if meta["delta"] else d) + 32500
                a = (q.astype(np.float64) * meta["esc"] + meta["lo"]).astype("<f4")
            campos[etq] = (fz.astype("<i4"), a)
    usados = defaultdict(int)
    with open(destino, "wb") as f:
        for item in indice["orden"]:
            if isinstance(item, int):
                b = cabeceras[item]
            else:
                k = usados[item]
                usados[item] += 1
                fz, a = campos[item]
                b = item.encode("latin-1") + struct.pack("<i", int(fz[k])) + a[k].tobytes()
            n = struct.pack("<i", len(b))
            f.write(n + b + n)
    return Path(destino)
