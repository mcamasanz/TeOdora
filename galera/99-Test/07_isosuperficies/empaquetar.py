# -*- coding: utf-8 -*-
"""Junta la plantilla, la librería 3D, la ortofoto y las mallas en una sola página que funciona sin internet.

Lee los ficheros descargados solo como bytes o texto, y con la biblioteca estándar: se ejecuta con `python -I`.

    python -I empaquetar.py <carpeta de trabajo> <nombre> <salida.html> [resultados_mallas.json]
"""
import base64
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
trabajo, nombre, salida = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
datos = json.loads((trabajo / f"mallas_{nombre}.json").read_text(encoding="utf-8"))
tabla = sys.argv[4] if len(sys.argv) > 4 else None
if tabla:
    datos["tabla"] = json.loads(Path(tabla).read_text(encoding="utf-8"))["tabla"]
three = (trabajo / "descargas" / "three" / "three.min.js").read_text(encoding="utf-8")
orbita = (trabajo / "descargas" / "three" / "OrbitControls.js").read_text(encoding="utf-8")
for t, q in ((three, "three.min.js"), (orbita, "OrbitControls.js")):
    if "</script" in t.lower():
        raise SystemExit(f"{q} contiene un cierre de script: no se puede incrustar tal cual")
orto = base64.b64encode((trabajo / "descargas" / "ortofoto" / "ortofoto.jpg").read_bytes()).decode()
html = (AQUI / "plantilla.html").read_text(encoding="utf-8")
html = (html.replace("/*THREE*/", three).replace("/*ORBIT*/", orbita).replace("/*DATOS*/", json.dumps(datos))
        .replace("/*ORTO*/", orto))
salida.write_text(html, encoding="utf-8")
print(f"{salida}: {salida.stat().st_size / 1e6:.2f} MB")
