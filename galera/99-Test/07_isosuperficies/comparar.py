# -*- coding: utf-8 -*-
"""Validación 1: el nivel del suelo de la corrida en altura, frente a una corrida solo en el suelo (mismos receptores) y
frente al penacho del plan Base de la app (superposición de respuestas, copiado en referencia/ el 2026-11-01).

    python comparar.py suelo [vol]
"""
import json
import sys

import comun as K
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
sal = {}
a = np.load(K.TRABAJO / (sys.argv[1] + ".npz"))
Ca, fin_a = a["C"], a["fines"]
xs, ys = a["x"], a["y"]
sal["fines"] = [str(fin_a[0]), str(fin_a[-1])]

# ── frente a la app ─────────────────────────────────────────────────────────────────────
z = np.load(K.REFERENCIA / "receptores.npz")
idx = {(round(float(x), 1), round(float(y), 1)): i for i, (x, y) in enumerate(zip(z["x"], z["y"]))}
pos = [[idx.get((float(x), float(y)), -1) for x in xs] for y in ys]
pos = np.array(pos)
falta = int((pos < 0).sum())
cotas = np.array([[K.cota(float(x), float(y)) for x in xs] for y in ys])
dif_cota = np.abs(cotas[pos >= 0] - z["cota"][pos[pos >= 0]]).max()
print(f"Nudos de la malla: {pos.size}; sin receptor igual en la app: {falta}; mayor diferencia de cota: {dif_cota:.3f} m", flush=True)
ref = np.load(K.REFERENCIA / "penacho.npz")["C"]                       # [hora del fin, receptor]
horas = [i for i, f in enumerate(fin_a) if str(f).startswith("2026-10-21")]
H = [int(str(fin_a[i])[11:13]) for i in horas]
ok = pos >= 0
A = Ca[horas, 0][:, ok]
B = ref[H][:, pos[ok]]
d = np.abs(A - B)
vmax = B.max()
sal["frente_a_la_app"] = {"nudos": int(ok.sum()), "horas": len(horas), "max_app": float(vmax), "max_prueba": float(A.max()),
                          "dif_max": float(d.max()), "dif_max_entre_maximo": float(d.max() / vmax),
                          "dif_relativa_max_con_c>0,1": float((d[B > 0.1] / B[B > 0.1]).max()),
                          "correlacion": float(np.corrcoef(A.ravel(), B.ravel())[0, 1])}
print("Frente a la app:", sal["frente_a_la_app"], flush=True)

# ── suelo de la corrida en altura frente a la corrida en el suelo ───────────────────────
if len(sys.argv) > 2:
    b = np.load(K.TRABAJO / (sys.argv[2] + ".npz"))
    if not (np.array_equal(b["x"], xs) and np.array_equal(b["y"], ys)):
        raise SystemExit("mallas distintas")
    comunes = [f for f in b["fines"] if f in set(fin_a)]
    ia = [list(fin_a).index(f) for f in comunes]
    ib = [list(b["fines"]).index(f) for f in comunes]
    k0 = list(b["alturas"]).index(0.0)
    P, Q = Ca[ia, 0], b["C"][ib, k0]
    dif = np.abs(P - Q)
    sal["frente_a_solo_suelo"] = {"periodos": len(comunes), "primero": str(comunes[0]), "ultimo": str(comunes[-1]),
                                  "valores": int(P.size), "iguales_bit_a_bit": int((P == Q).sum()),
                                  "dif_max": float(dif.max()), "max": float(P.max()),
                                  "por_periodo_dif_max": [float(x) for x in dif.max(axis=(1, 2))]}
    print("Suelo frente a solo suelo:", sal["frente_a_solo_suelo"], flush=True)
(K.AQUI / "resultados_comparar.json").write_text(json.dumps(sal, ensure_ascii=False, indent=1), encoding="utf-8")
