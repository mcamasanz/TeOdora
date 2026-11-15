# -*- coding: utf-8 -*-
"""El usuario administrador (usuario, 2026-11-08: «dos tipos de usuario, usuario normal y usuario administrador; este último se accede desde
la terminal con un comando especial con una contraseña; tiene permisos especiales dentro de la app»).

La app arranca siempre con el usuario normal. El administrador se abre desde la terminal de la app (`admin` y su contraseña) y se cierra con
`normal` o al cerrar la app. Sustituye a la opción `--<operacion.modo_edicion>` de la línea de órdenes, que daba esos permisos sin contraseña.

La contraseña no se guarda: se guarda su huella (PBKDF2-HMAC-SHA256 con sal, `ITERACIONES` vueltas), en `administrador.json` de la carpeta de
la planta. La pone quien mantiene la planta, por línea de órdenes, o el administrador desde la terminal (`clave`). Tras `FALLOS_MAX` intentos
fallidos seguidos, hay que esperar `ESPERA_S` segundos.

    python -m teodors.operacion.administrador --clave        (con la carpeta de la planta en TEODORS_PLANTA; la pide dos veces, sin que se vea)

⚠️ La huella impide saber la contraseña, pero no que alguien con permiso de escritura en la carpeta de la planta la cambie por la suya: esa
carpeta tiene que estar protegida (el instalador).
"""
import argparse
import datetime as dt
import getpass
import hashlib
import hmac
import json
import os
import sys
import time

from teodors import planta as config

FORMATO = 1
ITERACIONES = 200 * 1000              # vueltas de PBKDF2 (así, y no en una cifra de 6: el código no lleva números que parezcan coordenadas UTM)
LARGO_MIN = 8
FALLOS_MAX, ESPERA_S = 3, 60.0


def ruta():
    return config.PLANTA / "administrador.json"


def hay_clave():
    try:
        d = json.loads(ruta().read_text(encoding="utf-8"))
        return bool(d.get("huella") and d.get("sal"))
    except (OSError, ValueError):
        return False


def _huella(clave, sal, iteraciones):
    return hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), bytes.fromhex(sal), iteraciones).hex()


def poner_clave(clave):
    """Guarda la huella de una contraseña nueva (de al menos LARGO_MIN caracteres)."""
    if len(clave) < LARGO_MIN:
        raise ValueError(f"la contraseña tiene que tener al menos {LARGO_MIN} caracteres")
    sal = os.urandom(16).hex()
    datos = {"formato": FORMATO, "algoritmo": "pbkdf2_sha256", "iteraciones": ITERACIONES, "sal": sal,
             "huella": _huella(clave, sal, ITERACIONES), "cambiada": dt.datetime.now().isoformat(timespec="minutes")}
    ruta().write_text(json.dumps(datos, indent=1), encoding="utf-8")


class Puerta:
    """Comprueba la contraseña y lleva la cuenta de los intentos fallidos de esta sesión de la app."""

    def __init__(self, reloj=time.monotonic):
        self._reloj, self._fallos, self._hasta = reloj, 0, 0.0

    def espera(self):
        """Segundos que faltan para poder volver a intentarlo (0 si se puede)."""
        return max(0.0, self._hasta - self._reloj())

    def abrir(self, clave):
        """True si la contraseña es la buena. Sin contraseña puesta o mientras hay que esperar, False sin mirarla."""
        if self.espera() > 0 or not hay_clave():
            return False
        d = json.loads(ruta().read_text(encoding="utf-8"))
        bien = hmac.compare_digest(_huella(clave, d["sal"], int(d.get("iteraciones", ITERACIONES))), d["huella"])
        if bien:
            self._fallos = 0
        else:
            self._fallos += 1
            if self._fallos >= FALLOS_MAX:
                self._fallos, self._hasta = 0, self._reloj() + ESPERA_S
        return bien


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="La contraseña del usuario administrador de la planta.")
    ap.add_argument("--clave", action="store_true", help="poner una contraseña nueva (se pide dos veces, sin que se vea)")
    a = ap.parse_args(argv)
    if not a.clave:
        print(f"{'Hay' if hay_clave() else 'No hay'} contraseña de administrador en {ruta()}")
        return 0
    nueva = getpass.getpass("Contraseña nueva de administrador: ")
    if getpass.getpass("Otra vez: ") != nueva:
        print("No coinciden: no se ha cambiado nada.")
        return 1
    try:
        poner_clave(nueva)
    except ValueError as e:
        print(f"No se ha cambiado: {e}.")
        return 1
    print(f"Contraseña de administrador guardada (su huella) en {ruta()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
