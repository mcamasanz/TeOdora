# -*- coding: utf-8 -*-
"""Números para los textos que lee una persona: coma decimal y espacio de miles."""


def num(x, dec=0):
    """Número con coma decimal y espacio de miles (estilo SI): «4 506 594», «45,3».
    El espacio evita confundir el punto de miles con el decimal de las coordenadas, y es DURO (U+00A0)
    para que un número no se parta en dos líneas: se ve igual que uno normal, pero no lo es."""
    s = f"{x:,.{dec}f}"
    return s.replace(",", "\u00a0").replace(".", ",")


def km(x):
    """Kilómetros sin decimales inútiles: 50 -> «50», 7,5 -> «7,5»."""
    return num(x, 0 if float(x).is_integer() else 1)
