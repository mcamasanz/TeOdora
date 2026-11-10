# -*- coding: utf-8 -*-
"""Crear un caso de regresión nuevo o regenerar la referencia de uno existente.

    python -m auditor --nuevo-caso penacho/mi_caso --desde carpeta_con_entradas \
                      --orden "aermod.inp" [--carpeta AERMOD] [--descripcion "…"]
    python -m auditor --regenerar penacho/mi_caso

- Un caso nuevo copia las entradas, corre el motor y guarda como referencia las salidas que
  aparecen. Antes de confiar en él, su resultado debe contrastarse con el programa original en el
  laboratorio; mientras tanto `caso.json` lo dice («original: pendiente de contrastar»).
- Regenerar una referencia es cambiar el resultado esperado: el auditor (regla R5) solo lo admite
  si `auditor/CAMBIOS_REFERENCIA.md` tiene una entrada nueva que nombra el caso y explica por qué.
- Los casos tienen que ser **rápidos**: unos segundos (límite de la regla R3).
"""
import json
import shutil
import tempfile
from pathlib import Path

from . import casos as C
from .comparar import ficheros


def _correr_y_guardar(caso):
    with tempfile.TemporaryDirectory() as d:
        trabajo = Path(d) / "trabajo"
        antes = set(ficheros(caso.ruta / "entrada"))
        segundos = C.ejecutar(caso, trabajo)
        salidas = sorted(set(ficheros(trabajo)) - antes)
        ref = caso.ruta / "referencia"
        if ref.exists():
            shutil.rmtree(ref)
        for s in salidas:
            (ref / s).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(trabajo / s, ref / s)
    return segundos, salidas


def _escribir_meta(caso, segundos):
    meta = dict(motor=caso.motor, descripcion=caso.descripcion, carpeta=caso.carpeta, ordenes=caso.ordenes,
                entorno=caso.entorno, salidas=caso.salidas, marcas=caso.marcas, original=caso.original,
                segundos=round(segundos, 1))
    (caso.ruta / "caso.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def crear(nombre, desde, ordenes, carpeta="", descripcion=""):
    motor = nombre.split("/")[0]
    ruta = C.CASOS / nombre
    if ruta.exists():
        raise SystemExit("ya existe el caso %s (usa --regenerar)" % nombre)
    shutil.copytree(desde, ruta / "entrada")
    caso = C.Caso(nombre=nombre, ruta=ruta, motor=motor, descripcion=descripcion or nombre, carpeta=carpeta,
                  ordenes=ordenes, entorno={}, salidas=[], original="pendiente de contrastar con el original")
    segundos, caso.salidas = _correr_y_guardar(caso)
    _escribir_meta(caso, segundos)
    print("caso %s creado: %.1f s, %d salidas de referencia" % (nombre, segundos, len(caso.salidas)))


def regenerar(nombre):
    caso = next((c for c in C.listar() if c.nombre == nombre), None)
    if caso is None:
        raise SystemExit("no existe el caso %s" % nombre)
    segundos, caso.salidas = _correr_y_guardar(caso)
    _escribir_meta(caso, segundos)
    print("referencia de %s regenerada (%.1f s). Justifícalo en auditor/CAMBIOS_REFERENCIA.md" % (nombre, segundos))
