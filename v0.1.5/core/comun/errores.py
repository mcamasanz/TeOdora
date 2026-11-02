# -*- coding: utf-8 -*-
"""Excepciones comunes, sin dependencias: las usan a la vez los datos y la interfaz."""


class Cancelado(Exception):
    """El usuario ha cancelado un trabajo largo."""
