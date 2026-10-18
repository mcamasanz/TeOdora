# -*- coding: utf-8 -*-
"""Lector de ficheros de control con la sintaxis publicada de CALMET (la misma de la fase 06).

Sintaxis publicada (CALMET User's Guide, 2000, págs. 4-95 y 4-96; CALPUFF Version 6 User
Instructions, 2011, pág. 2-51): solo cuenta lo que va entre delimitadores «!», con la forma
``!VARIABLE = valor[, valor...]!`` (el nombre sin distinguir mayúsculas, los blancos se ignoran,
los valores separados por comas, se admiten factores de repetición ``3*1.5`` y el valor puede
seguir en otra línea); ``!END!`` cierra un grupo o subgrupo; el texto fuera de los delimitadores
es comentario. Una variable que se repite (una por subgrupo, como las filas de una tabla) se
acumula en una lista.
"""
import re

_ENTRADA = re.compile(r"!([^!]*)!")


def leer(texto):
    """Devuelve (título, {VARIABLE: [lista de cadenas de valores, una por aparición]})."""
    lineas = texto.replace("\r", "").split("\n")
    titulo = lineas[0] if lineas else ""
    v = {}
    for m in _ENTRADA.finditer(texto):
        c = m.group(1).strip()
        if not c or c.upper() == "END" or "=" not in c:
            continue
        nombre, valor = c.split("=", 1)
        v.setdefault(nombre.strip().upper(), []).append(valor.strip())
    return titulo, v


class Control:
    """Acceso tipado a las variables leídas."""

    def __init__(self, texto):
        self.titulo, self.v = leer(texto)

    def hay(self, n):
        return n in self.v

    def cadena(self, n, defecto=None):
        return self.v[n][-1] if n in self.v else defecto

    def entero(self, n, defecto=None):
        return int(float(self.v[n][-1])) if n in self.v else defecto

    def real(self, n, defecto=None):
        return float(self.v[n][-1]) if n in self.v else defecto

    def logico(self, n, defecto=None):
        if n not in self.v:
            return defecto
        return self.v[n][-1].strip().upper()[:1] == "T"

    def lista(self, n):
        """Todas las apariciones de una variable, cada una partida por comas (con los factores de
        repetición «n*valor» desplegados)."""
        out = []
        for a in self.v.get(n, []):
            vals = []
            for x in a.replace(" ", "").split(","):
                if not x:
                    continue
                if "*" in x:
                    k, val = x.split("*", 1)
                    vals += [val] * int(k)
                else:
                    vals.append(x)
            out.append(vals)
        return out
