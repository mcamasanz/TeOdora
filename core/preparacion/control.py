# -*- coding: utf-8 -*-
"""Fichero de control como lista ORDENADA de asignaciones, para escribirlo desde cero.

Los lectores de odora (`meteo.viento3d.control`, `dispersion.puffs.entrada`) solo tienen en cuenta
lo que va entre delimitadores «!» con la forma «!NOMBRE = valor!», en orden; el resto es comentario.
Así que un fichero con solo esas asignaciones es equivalente a uno lleno de comentarios. El orden sí
importa: las variables repetidas (fuentes, receptores, especies) se reparten por su posición.

Cada entrada es [nombre, valor, activa]; ["END", None, True] cierra un grupo (no lo usa ningún
lector, pero ayuda a leer el fichero) y las entradas con nombre que empieza por «_» son marcas de
posición. Solo se escriben las activas.
"""


class Control:
    def __init__(self, parametros, titulo="Caso de odora"):
        self.entradas = [list(e) for e in parametros]
        self.titulo = titulo

    def indice(self, nombre, desde=0):
        """Posición de la PRIMERA entrada con ese nombre (desde `desde`)."""
        n = nombre.upper()
        for i in range(desde, len(self.entradas)):
            if self.entradas[i][0] == n:
                return i
        raise KeyError("no hay ninguna entrada %s en el control" % nombre)

    def poner(self, nombre, valor):
        """Valor de la PRIMERA entrada con ese nombre, que queda activa."""
        e = self.entradas[self.indice(nombre)]
        e[1], e[2] = str(valor), True
        return self

    def apagar(self, nombre):
        """Desactiva la PRIMERA entrada con ese nombre (no se escribe)."""
        self.entradas[self.indice(nombre)][2] = False
        return self

    def quitar(self, condicion):
        """Quita las entradas para las que condicion(nombre, valor) es cierta."""
        self.entradas = [e for e in self.entradas if not condicion(e[0], e[1])]
        return self

    def insertar(self, posicion, nuevas):
        """Inserta [(nombre, valor)…] (o ("END", None)) activas en `posicion`."""
        self.entradas[posicion:posicion] = [[n.upper(), None if v is None else str(v), True]
                                            for n, v in nuevas]
        return self

    def asignaciones(self):
        """[(nombre, valor)] activas, en orden (sin los fines de grupo ni las marcas)."""
        return [(n, v) for n, v, a in self.entradas if a and n != "END" and not n.startswith("_")]

    def texto(self):
        lineas = [self.titulo]
        for n, v, a in self.entradas:
            if not a or n.startswith("_"):
                continue
            lineas.append("!END!" if n == "END" else "! %s = %s !" % (n, v))
        return "\n".join(lineas) + "\n"

    def escribir(self, ruta):
        with open(ruta, "w", encoding="ascii", errors="replace", newline="\n") as f:
            f.write(self.texto())
        return ruta
