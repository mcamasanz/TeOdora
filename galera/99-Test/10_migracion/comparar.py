# -*- coding: utf-8 -*-
"""Compara dos líneas base (linea_base.py): dice qué huellas han cambiado, cuáles faltan y cuáles son nuevas.

    python 99-Test/10_migracion/comparar.py antes.json despues.json
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
a, b = (json.loads(open(f, encoding="utf-8").read()) for f in sys.argv[1:3])
distintas = sorted(k for k in a if k in b and a[k] != b[k])
faltan, nuevas = sorted(set(a) - set(b)), sorted(set(b) - set(a))
print(f"{len(a)} huellas antes, {len(b)} después; iguales: {sum(a[k] == b.get(k) for k in a)}")
for t, lista in (("DISTINTAS", distintas), ("FALTAN", faltan), ("NUEVAS", nuevas)):
    if lista:
        print(f"{t}: {lista}")
print("RESULTADO:", "todo igual" if not distintas and not faltan else "HAY DIFERENCIAS")
sys.exit(0 if not distintas and not faltan else 1)
