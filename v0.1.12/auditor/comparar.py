# -*- coding: utf-8 -*-
"""Comparación de las salidas de un caso con su referencia.

Las salidas de los motores llevan la fecha y la hora de la corrida (cabeceras de página, nombres
de fichero de depuración…). Se sustituyen por un marcador antes de comparar; todo lo demás debe
coincidir byte a byte: el código de la referencia ya está validado frente al programa original,
así que cualquier otro cambio en una salida es un cambio de resultados.
"""
import re
import struct
from pathlib import Path

# Fecha y hora de la corrida, en el orden en que se sustituyen. Un dígito puede ir como blanco
# (« 9: 5: 3», « 1/ 5/2027»): así lo escriben algunos formatos de Fortran.
_H = rb"[ \d]\d:[ \d]\d:[ \d]\d"
_FECHA_HORA = (
    # capa_limite, informe: «OCTOBER 18, 2026  20:25:40 PM»
    re.compile(rb"[A-Z]+ +\d{1,2}, \d{4} +" + _H + rb"(?: [AP]M)?"),
    # capa_limite, mensajes: «20261018 20:25:40» (las fechas de los datos no llevan hora detrás)
    re.compile(rb"\d{8} +" + _H),
    # edificios: líneas « DATE : 10/18/2026» y « TIME : 21: 6:40»
    re.compile(rb"^ (?:DATE|TIME) :[^\r\n]*", re.M),
    # el resto: «10/18/26» y «20:25:40»
    re.compile(rb"[ \d]\d/[ \d]\d/\d\d(?:\d\d)?|" + _H),
)
# duración de la corrida en los listados («Tiempo: 0.03 s» de geofisica)
_DURACION = re.compile(rb"Tiempo: \d+(?:\.\d+)? s")


def ficheros(raiz):
    """Rutas relativas (con «/») de todos los ficheros bajo `raiz`."""
    raiz = Path(raiz)
    return sorted(p.relative_to(raiz).as_posix() for p in raiz.rglob("*") if p.is_file())


def normalizar(datos):
    """Contenido de un fichero sin la fecha, la hora ni la duración de la corrida."""
    for rx in _FECHA_HORA:
        datos = rx.sub(b"#", datos)
    return _DURACION.sub(b"Tiempo: # s", datos)


def _es_binario(datos):
    return b"\x00" in datos[:64]


def rel_postfile(a, b):
    """Mayor diferencia relativa entre dos POSTFILE sin formato del penacho (registros de 8 + n bytes
    con dobles). None si no tienen esa estructura."""
    peor, i = 0.0, 0
    try:
        while i + 4 <= len(a):
            n = struct.unpack("<i", a[i:i + 4])[0]
            ra, rb = a[i + 20:i + 4 + n], b[i + 20:i + 4 + n]
            for k in range(0, len(ra) - 7, 8):
                x = struct.unpack("<d", ra[k:k + 8])[0]
                y = struct.unpack("<d", rb[k:k + 8])[0]
                if x != y:
                    peor = max(peor, abs(x - y) / max(abs(x), abs(y)))
            i += 8 + n
    except struct.error:
        return None
    return peor


def diferencia(ref, obt, contraste=False):
    """Texto que describe en qué difieren dos ficheros, o "" si son iguales (salvo fecha y hora).
    Con `contraste` (al comparar con el programa original, no con la referencia), además se ignoran
    los finales de línea (CRLF/LF) y un POSTFILE binario que solo difiere en los últimos bits
    (≤ 1e-9 relativo) se da por igual."""
    a, b = Path(ref).read_bytes(), Path(obt).read_bytes()
    if contraste and not _es_binario(a):
        a, b = a.replace(b"\r\n", b"\n"), b.replace(b"\r\n", b"\n")
    if normalizar(a) == normalizar(b):
        return ""
    if contraste and _es_binario(a) and len(a) == len(b):
        rel = rel_postfile(a, b)
        if rel is not None and rel <= 1e-9:
            return ""
        return "binario distinto" + ("" if rel is None else " (rel %.1e)" % rel)
    if _es_binario(a):
        return "binario distinto"
    la, lb = normalizar(a).splitlines(), normalizar(b).splitlines()
    for k, (x, y) in enumerate(zip(la, lb), 1):
        if x != y:
            return "línea %d: «%s» en lugar de «%s»" % (k, y.decode("latin-1").strip()[:80],
                                                       x.decode("latin-1").strip()[:80])
    if len(la) == len(lb):
        return "mismo texto con otros finales de línea (CRLF/LF)"
    return "longitud distinta (%d líneas en lugar de %d)" % (len(lb), len(la))


def comparar_carpetas(ref, obt, nombres, contraste=False):
    """Lista de diferencias entre los ficheros `nombres` de dos carpetas (vacía si coinciden)."""
    dif = []
    for n in nombres:
        a, b = Path(ref) / n, Path(obt) / n
        if not b.exists():
            dif.append("%s: no se ha generado" % n)
        elif not a.exists():
            dif.append("%s: no está en la referencia" % n)
        else:
            d = diferencia(a, b, contraste)
            if d:
                dif.append("%s: %s" % (n, d))
    return dif
