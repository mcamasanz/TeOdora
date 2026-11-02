# -*- coding: utf-8 -*-
"""Vista lateral de la chimenea: la cámara, a la altura del penacho y en perpendicular a por donde va a esa hora, con
los tres casos de chimenea.py en el mismo encuadre. Para ver si se despega del suelo.

    python chimenea_vista.py [hora UTC]
"""
import subprocess
import sys

import comun as K
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
H = sys.argv[1] if len(sys.argv) > 1 else "23"
d = np.load(K.TRABAJO / "chim_caliente_30.npz")
fines = [str(f) for f in d["fines"]]
c = d["C"][fines.index(f"2026-10-21 {H}:00")]
Z = d["alturas"]
col = (c * np.gradient(Z)[:, None, None]).sum(axis=0)
X, Y = np.meshgrid(d["x"] - K.CENTRO[0], d["y"] - K.CENTRO[1])
D = np.hypot(X, Y)
jj, ii = np.unravel_index(np.argmax(np.where((D > 1000) & (D < 1500), col, -1.0)), col.shape)
ux, uy = X[jj, ii] / D[jj, ii], Y[jj, ii] / D[jj, ii]
print(f"Hora {H}: el penacho va hacia ({ux:.2f} E, {uy:.2f} N)", flush=True)
E = 3.0                                  # exageración vertical de la vista
cota = K.cota(*K.CENTRO)
# mundo de la página: x = este, y = arriba (con la exageración), z = sur
mitad = 900.0
tx, tz = ux * mitad, -uy * mitad
for signo in (1.0, -1.0):                # a un lado o al otro: el que no quede tapado por el relieve
    px, py = -uy * signo, ux * signo
    xc, yc = K.CENTRO
    perfil = [K.cota(xc + ux * mitad + px * s, yc + uy * mitad + py * s) for s in np.arange(0, 2600, 100)]
    print(f"Lado {signo:+.0f}: cota máxima hasta la cámara {max(perfil):.0f} m", flush=True)
    if max(perfil) < cota + 90:
        break
cx, cz = tx + px * 2200.0, tz - py * 2200.0
ty, cy = (cota + 90.0) * E, (cota + 130.0) * E
parte = f"h={H}&e={E:.0f}&tx={tx:.0f}&ty={ty:.0f}&tz={tz:.0f}&cx={cx:.0f}&cy={cy:.0f}&cz={cz:.0f}"
print(parte, flush=True)
for caso in ("chimenea_caliente", "chimenea_sin_impulso"):
    subprocess.check_call([sys.executable, "captura.py", caso + ".html", f"{caso}_lado", parte], cwd=str(K.AQUI))
