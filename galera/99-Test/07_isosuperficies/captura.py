# -*- coding: utf-8 -*-
"""Fotos de la página con Edge sin pantalla (WebGL por software): sin la app ni sus ajustes.

    python captura.py penacho_3d.html salida "h=07" [ancho alto]   →  salida.jpg en esta carpeta
"""
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
TMP = Path(os.environ["TEMP"]) / "ence_galera" / "99-Test" / "07_isosuperficies"
EDGE = next(p for p in (Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
                        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe") if p.is_file())
pagina, salida, parte = sys.argv[1], sys.argv[2], sys.argv[3]
ancho, alto = (sys.argv[4], sys.argv[5]) if len(sys.argv) > 5 else ("1200", "740")
png = TMP / (salida + ".png")
png.unlink(missing_ok=True)
perfil = TMP / "perfil_edge"
ruta = Path(pagina).resolve() if Path(pagina).is_absolute() else AQUI / pagina
url = ruta.as_uri() + "#" + parte
t0 = time.time()
r = subprocess.run([str(EDGE), "--headless=new", "--disable-gpu-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                    "--ignore-gpu-blocklist", f"--user-data-dir={perfil}", f"--window-size={ancho},{alto}", "--hide-scrollbars",
                    "--virtual-time-budget=12000", f"--screenshot={png}", url], capture_output=True, text=True, errors="replace", timeout=180)
if not png.is_file():
    raise SystemExit(f"sin captura (rc={r.returncode}): {r.stderr[-800:]}")
Image.open(png).convert("RGB").save(AQUI / (salida + ".jpg"), quality=78, optimize=True)
print(f"{salida}.jpg: {(AQUI / (salida + '.jpg')).stat().st_size / 1e3:.0f} kB, {time.time() - t0:.1f} s")
