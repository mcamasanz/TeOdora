# -*- coding: utf-8 -*-
"""Crea la carpeta de una planta nueva a partir de sus coordenadas.

    python -m teodors.planta.nueva <carpeta> --nombre "Mi planta" --lat 41.63 --lon 0.38 [--corine CLC2018_ES.gpkg] [--descargar]

Deja lo mínimo para abrir la aplicación: VERSION, main.py, README.md y entrada/, con planta.json (de `plantilla_planta.json`, en el huso
de esas coordenadas) y su lista de focos, vacía. Con --descargar baja además el terreno, los usos del suelo y los edificios a entrada/,
y anota las estaciones cercanas; si no, la aplicación ofrece el terreno y los edificios al abrirla. Los servicios de datos son los de
España: en otro país hay que cambiarlos en planta.json. El viento local, el ejemplo de la configuración y la ortofoto del visor 3D son
opcionales: sin ellos, solo hay viento de la zona, la vista previa va sin capas y el suelo del visor sale liso.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from teodors import __version__
from teodors.comun import geo

PLANTILLA = Path(__file__).resolve().parent / "plantilla_planta.json"

# Igual en todas las plantas: lee la versión que usa esta y la carga de su carpeta, al lado de la de la planta; compilado, despacha
# los motores que la app lanza como procesos hijos (`comun.procesos`)
MAIN = '''# -*- coding: utf-8 -*-
"""Lanza la aplicación de esta planta con la versión de teOdors que dice su fichero VERSION. Opciones: --dia AAAA-MM-DD --focos --planes

Compilado en un ejecutable (Nuitka o PyInstaller), teOdors va dentro y el .exe tiene que estar en esta carpeta, junto a entrada/, viento/,
dispersion/ y datos/. Ahí, la app también se lanza a sí misma para correr los motores: `procesos.despachar_hijo` los atiende antes que nada.
"""
import os
import sys
from pathlib import Path

CONGELADO = bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()
# la carpeta de la planta: la de este fichero o, compilado, la del .exe (__file__ apunta a otro sitio)
AQUI = Path(os.path.abspath(sys.argv[0])).parent if CONGELADO else Path(__file__).resolve().parent
VERSION = (AQUI / "VERSION").read_text(encoding="utf-8").strip()
if not CONGELADO:
    CARGADOR = AQUI.parent / VERSION / "cargador"
    if not CARGADOR.is_dir():
        sys.exit(f"{AQUI.name} pide teOdors {VERSION}, y no está en {CARGADOR.parent}.")
    sys.path.insert(0, str(CARGADOR))

from teodors.comun import procesos  # noqa: E402

procesos.despachar_hijo()             # un motor lanzado por la propia app: corre y sale, sin la interfaz ni activar la planta (la hereda)

from teodors import __version__, planta  # noqa: E402

if f"v{__version__}" != VERSION:
    sys.exit(f"{AQUI.name} pide teOdors {VERSION}, y {'este programa' if CONGELADO else f'la carpeta {CARGADOR.parent}'} es la {__version__}.")

from teodors.gui.principal import main  # noqa: E402

if __name__ == "__main__":
    planta.activar(AQUI / "entrada")
    sys.exit(main())
'''


def _json(ruta, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _caja_gfs(valor):
    """Un grado alrededor de la planta sobre la malla de GFS, de 0,25°: 5 puntos."""
    ini = round((valor - 0.5) * 4.0) / 4.0
    return [ini, ini + 1.0]


def crear(carpeta, nombre, lat, lon, organizacion="teOdors", version=None, corine=None):
    """Escribe la carpeta de la planta y la devuelve. Nunca encima de una que ya existe."""
    raiz = Path(carpeta).resolve()
    entrada = raiz / "entrada"
    if (entrada / "planta.json").exists():
        raise FileExistsError(f"Ya hay una planta en {raiz}.")
    entrada.mkdir(parents=True, exist_ok=True)
    corto = re.sub(r"[^0-9A-Za-z]+", "_", raiz.name).strip("_") or "planta"
    p = json.loads(PLANTILLA.read_text(encoding="utf-8"))
    p["identidad"].update(app_nombre=f"{nombre} · Dispersión", organizacion=organizacion, ajustes=corto, app_id=f"{organizacion}.{corto}", entidad=organizacion,
                          prefijo_env=corto.upper(), carpeta_local=corto.lower(), registro=corto.lower(), nombre_casos=nombre)
    p["proyeccion"]["epsg"] = geo.epsg_utm(lon)
    p["pronostico"]["caja_gfs"] = {"lat": _caja_gfs(lat), "lon": _caja_gfs(lon)}
    if corine:
        p["fuentes"]["corine_gpkg"] = [str(corine)]
    _json(entrada / "planta.json", p)
    _json(entrada / "emplazamiento.json", {"nombre": nombre, "lat": lat, "lon": lon})
    _json(entrada / "rutas.json", {"datos": "../datos"})
    _json(entrada / "receptores.json", {"formato": 1, "epsg": geo.epsg_utm(lon), "receptores": []})
    _json(entrada / "focos.json", {"formato": 2, "planta": nombre, "epsg": geo.epsg_utm(lon), "actualizado": "", "ejemplo": False, "focos": []})
    (raiz / "VERSION").write_text((version or f"v{__version__}") + "\n", encoding="utf-8", newline="\n")
    (raiz / "main.py").write_text(MAIN, encoding="utf-8", newline="\n")
    (raiz / "README.md").write_text(f"# {nombre}\n\n{lat} N, {lon} E. Sus datos de entrada están en `entrada/`; la versión de teOdors que usa, en `VERSION`.\n\n"
                                    "Abrir la aplicación: `python main.py`\n", encoding="utf-8", newline="\n")
    return raiz


def descargar(raiz, avisa=print):
    """Baja a entrada/ el terreno, los usos y los edificios, y anota las estaciones cercanas. Un servicio que falla no para a los demás. Devuelve los fallos."""
    from teodors import planta
    from teodors.fuentes import catastro, meteocat, terreno
    p = planta.activar(Path(raiz) / "entrada")
    p.asegurar_carpetas()
    emp = p.cargar_emplazamiento()
    fallos = []

    def paso(titulo, funcion):
        avisa(titulo)
        try:
            return funcion()
        except Exception as e:
            fallos.append(f"{titulo}: {e}")
            avisa(f"   no se ha podido: {e}")
            return None

    paso("Terreno y usos del suelo", lambda: terreno.descargar(emp["lat"], emp["lon"], p.DOMINIO_DESCARGA_KM))
    paso("Edificios", lambda: catastro.descargar(emp["lat"], emp["lon"]))
    cercanas = paso("Estaciones cercanas", lambda: meteocat.cercanas(emp["lat"], emp["lon"]))
    if cercanas:
        datos = json.loads(p._ruta.read_text(encoding="utf-8"))
        datos["estaciones"]["codigos"] = [e["codigo"] for e in cercanas]
        datos["estaciones"]["objetivo"] = cercanas[0]["codigo"]
        _json(p._ruta, datos)
        avisa(f"   {len(cercanas)}: {', '.join(datos['estaciones']['codigos'])}")
    return fallos


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("carpeta")
    a.add_argument("--nombre", required=True)
    a.add_argument("--lat", type=float, required=True)
    a.add_argument("--lon", type=float, required=True)
    a.add_argument("--organizacion", default="teOdors")
    a.add_argument("--corine", help="ruta del CORINE nacional: solo hace falta para descargar")
    a.add_argument("--descargar", action="store_true")
    A = a.parse_args(argv)
    raiz = crear(A.carpeta, A.nombre, A.lat, A.lon, A.organizacion, corine=A.corine)
    print(f"Planta creada en {raiz}")
    fallos = descargar(raiz) if A.descargar else []
    for f in fallos:
        print(f"⚠️ {f}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
