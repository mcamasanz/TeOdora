# -*- coding: utf-8 -*-
"""Registro de mensajes: un único logger «teOdors» que escribe a fichero, siempre con detalle, y al
terminal si lo hay. La interfaz añade sus propios manejadores con `get().addHandler(…)`."""
import logging
import sys
from datetime import date
from pathlib import Path

NOMBRE = "teodors"
NIVELES_ES = {"DEBUG": "DETALLE", "INFO": "INFO", "WARNING": "AVISO",
              "ERROR": "ERROR", "CRITICAL": "CRÍTICO"}


class FormatoES(logging.Formatter):
    """Formato con el nivel en español."""

    def format(self, record):
        record.nivel = NIVELES_ES.get(record.levelname, record.levelname)
        return super().format(record)


def configurar(carpeta, prefijo=NOMBRE):
    """Prepara el logger (solo la primera vez) y lo devuelve. Un fichero por día: <prefijo>_AAAAMMDD.log."""
    log = logging.getLogger(NOMBRE)
    if log.handlers:
        return log
    log.setLevel(logging.DEBUG)
    log.propagate = False

    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    fichero = logging.FileHandler(carpeta / f"{prefijo}_{date.today():%Y%m%d}.log", encoding="utf-8")
    fichero.setLevel(logging.DEBUG)
    fichero.setFormatter(FormatoES("%(asctime)s %(nivel)-7s %(name)s: %(message)s"))
    log.addHandler(fichero)

    # Terminal (si lo hay; con pythonw no existe). Útil al desarrollar.
    if sys.__stderr__ is not None:
        terminal = logging.StreamHandler(sys.__stderr__)
        terminal.setLevel(logging.INFO)
        terminal.setFormatter(FormatoES("%(asctime)s %(nivel)-7s %(message)s", "%H:%M:%S"))
        log.addHandler(terminal)
    return log


def get(modulo=None):
    return logging.getLogger(f"{NOMBRE}.{modulo}" if modulo else NOMBRE)
