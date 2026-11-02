# -*- coding: utf-8 -*-
"""Tanda 6: la operación movida a teOdors frente al original de git, función a función.

    python comparar_movidos_tanda6.py <raíz de la planta> <commit original de la planta> <commit original del core> <carpeta core nueva>

Con ENCE_GALERA_DATOS, una copia de los datos: además comprueba lo guardado y lanza el código original, sacado de git a una carpeta temporal.

Por cada nombre del módulo, el TEXTO sin docstrings (caza comentarios y caracteres invisibles) y su AST. Cada diferencia esperada se quita de forma explícita, con su
motivo; lo demás tiene que dar igual byte a byte. Después: el diff entero de cada fichero, lo de planta.json frente a las constantes del original, los envoltorios,
lo que no puede quedar en el core y, con los datos, la firma, lo guardado y la página del visor frente al código original, sacado de git.
"""
import ast
import difflib
import hashlib
import inspect
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

PLANTA, COMMIT, COMMIT_CORE, CORE = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])
REPO_CORE = CORE.parent
RARO = {0xa0: "NBSP", 0x202f: "NNBSP", 0x2009: "fino", 0x200b: "ancho cero", 0x2011: "guion duro", 0xad: "guion blando", 0x2212: "menos"}
sys.stdout.reconfigure(encoding="utf-8")


def _git(repo, rev, rel):
    return subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{rel}"], capture_output=True, check=True).stdout.decode("utf-8").replace("\r\n", "\n")


def viejo(rel):
    return _git(PLANTA, COMMIT, rel)


def nuevo(rel):
    return (CORE / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")


def tabla(src):
    d = {}
    for n in ast.parse(src).body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            d[n.name] = n
        elif isinstance(n, ast.Assign):
            for o in n.targets:
                for x in ast.walk(o):
                    if isinstance(x, ast.Name):
                        d[x.id] = n
    return d


def _doc(n):
    return isinstance(n, (ast.FunctionDef, ast.ClassDef)) and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant) and isinstance(n.body[0].value.value, str)


def texto_sin_doc(src, nodo):
    """El texto, comentarios incluidos, sin los docstrings."""
    lineas = src.splitlines(keepends=True)
    fuera = set()
    for n in ast.walk(nodo):
        if _doc(n):
            fuera.update(range(n.body[0].lineno, n.body[0].end_lineno + 1))
    return "".join(lineas[i - 1] for i in range(nodo.lineno, nodo.end_lineno + 1) if i not in fuera)


def ast_sin_doc(nodo):
    arbol = ast.parse(ast.unparse(nodo))
    for n in ast.walk(arbol):
        if _doc(n):
            n.body = n.body[1:] or [ast.Pass()]
    return ast.dump(arbol)


GUI = "lib/galera/gui/"
NOR, FOC, PLA, PER, SIM, PMA, VMA, P3D, RES, VPE, SER, EJE = [f"operacion/{m}.py" for m in ("normativa", "focos", "planes", "periodos", "simulacion", "penacho_mapa", "viento_mapa", "penacho_3d", "respuestas", "viento_periodo", "viento3d_series", "ejemplo_configuracion")]
PARES = [(GUI + "normativa.py", NOR), (GUI + "focos.py", FOC), (GUI + "escenarios.py", PLA), (GUI + "periodos.py", PER), (GUI + "planes_calculo.py", SIM), (GUI + "penacho_mapa.py", PMA),
         (GUI + "viento_mapa.py", VMA), (GUI + "penacho_3d.py", P3D), (GUI + "tareas/respuestas_dia.py", RES), (GUI + "tareas/viento_dia_local.py", VPE), (GUI + "tareas/viento3d_series.py", SER),
         (GUI + "tareas/ejemplo_configuracion.py", EJE)]

DEF = "valor por defecto de la planta: None, y se resuelve al llamar"
MOD = "cada módulo por su nombre en teodors (ya eran envoltorios de eso)"
NOMBRE_TAREA = "las tareas se lanzan por su nombre en teodors; el envoltorio de galera sigue respondiendo al de antes"
REG = "registro.configurar de galera hacía estos dos pasos: aquí se dan los datos de la planta"
ZONA = "la zona horaria, de proyeccion.zona_horaria en planta.json, al llamar"
SERIE = "la serie, de series en planta.json, al llamar"
COM = "comentario: "                                # un motivo que empieza así no cambia el AST

ESPERADOS = {
    (NOR, "RUTA"): [('RUTA = Path(__file__).resolve().parent / "planta" / "normativa.json"\n', 'RUTA = None                    # otro fichero en vez de esos dos, si se pone (para probar otra normativa)\n', "ahora la manda `ruta()`: la de la planta o la plantilla nacional; RUTA se queda para que una prueba ponga otro fichero (prueba_normativa.py)")],
    (NOR, "datos"): [("RUTA.read_text", "ruta().read_text", "ver `ruta`")],
    (FOC, "VM_25C"): [(" (docs/guias_cajon/06)", "", COM + "sin la ruta a un documento del proyecto")],
    (FOC, "cargar"): [(' (regla 3)")', '")', "el texto de un error: la regla 3 es del CLAUDE.md de una planta")],
    (FOC, "nuevo"): [("func = TIPOS[tipo]", "func = tipos()[tipo]", "con los tipos de la planta (operacion.tipos_foco_extra)")],
    (FOC, "nombre_tipo"): [("return TIPOS.get(", "return tipos().get(", "con los tipos de la planta (operacion.tipos_foco_extra)")],
    (PLA, "factores"): [("tz_convert(ZONA)", "tz_convert(zona())", ZONA)],
    (PLA, "horas_del_plan"): [("tz_convert(ZONA)", "tz_convert(zona())", ZONA)],
    (PER, "_lanzar"): [('f"galera.gui.tareas.{tarea}"', 'f"teodors.operacion.{tarea}"', "el core no puede nombrar a galera: el hijo hereda la planta por TEODORS_PLANTA"),
                       ("cwd=str(config.RAIZ)", "cwd=str(config.PLANTA)", "RAIZ es de la app; la carpeta de la planta existe siempre y el hijo no usa rutas relativas")],
    (PER, "preparar"): [('_lanzar("viento_dia_local"', '_lanzar("viento_periodo"', NOMBRE_TAREA), ('_lanzar("respuestas_dia"', '_lanzar("respuestas"', NOMBRE_TAREA)],
    (SIM, "calcular"): [('"Aún no hay respuestas de los focos (gui/tareas/respuestas_dia.py)."', '"Aún no hay respuestas de los focos (operacion.respuestas)."', "el texto de un error: la ruta era de la planta"),
                        ("pd.date_range(INICIO, FIN, freq", "pd.date_range(*horas_reanalisis(), freq", "los años, de reanalisis.anios en planta.json")],
    (SIM, "calcular_periodo"): [("tz_convert(E.ZONA)", "tz_convert(E.zona())", ZONA)],
    (SIM, "_tabla"): [('fila("Peor vivienda (< 2 km)"', 'fila(f"Peor vivienda (< {config.RADIO_EDIFICIOS_KM:g} km)"', "los 2 km eran dominio.radio_edificios_km de la planta; da el mismo texto (línea base: anios.resultado)")],
    (PMA, "pintar"): [("from galera.entradas import terreno", "from teodors.fuentes import terreno", MOD)],
    (VMA, "BIBLIOTECA"): [('BIBLIOTECA = Path(__file__).resolve().parent / "planta" / "viento_local.npz"\n', 'BIBLIOTECA = None          # otra biblioteca en vez de la de la planta, si se pone\n', "ahora la manda `biblioteca()`: viento_local.biblioteca de planta.json; BIBLIOTECA se queda para que una prueba ponga otra (prueba_dos_motores.py)")],
    (VMA, "serie_disponible"): [("for s in PREFERIDAS if", "for s in preferidas() if", SERIE)],
    (VMA, "meses"): [("def meses(serie=SERIE):\n", "def meses(serie=None):\n    serie = serie_defecto() if serie is None else serie\n", DEF)],
    (VMA, "datos_dia"): [("def datos_dia(fecha, serie=SERIE, cada=1, dias=1):\n", "def datos_dia(fecha, serie=None, cada=1, dias=1):\n    serie = serie_defecto() if serie is None else serie\n", DEF),
                         ('"titulo": TITULOS.get(serie, serie)', '"titulo": titulos().get(serie, serie)', SERIE)],
    (VMA, "datos_local"): [("    if not BIBLIOTECA.is_file():\n", "    ruta = biblioteca()\n    if ruta is None or not ruta.is_file():\n", "la ruta, de viento_local.biblioteca en planta.json; sin ella, None, como sin fichero"),
                           ("with np.load(BIBLIOTECA) as z:", "with np.load(ruta) as z:", "ver arriba")],
    (P3D, "PASO_TERRENO"): [('SEMILADO_VISTA, PASO_TERRENO = 3200.0, 50.0       # lo que cubre recursos/visor3d/ortofoto.jpg\n', 'PASO_TERRENO = 50.0\n', "el semilado, de visor3d.semilado_m en planta.json")],
    (P3D, "abrir"): [('return {"pagina": str(pagina(datos)), "horas": datos["horas_utc"]}', 'return {"datos": datos, "horas": datos["horas_utc"]}', "la página usa el tema de la app: la monta el envoltorio, con lo mismo")],
    (P3D, "_fuentes"): [("modelo, d, q0 = cf.geometria(f, cota)", "modelo, d, q0 = F.geometria(f, cota)", "geometria pasa a operacion.focos")],
    (P3D, "_terreno_vista"): [("int(SEMILADO_VISTA / PASO_TERRENO), int(SEMILADO_VISTA / PASO_TERRENO)", "int(semilado_vista() / PASO_TERRENO), int(semilado_vista() / PASO_TERRENO)", "de visor3d.semilado_m")],
    (P3D, "_rotulos"): [('''    gx, gy = a_utm.transform(*GALERA)
    rotulos = [{"t": "Planta", "x": 0.0, "y": 0.0, "z": cota(xc, yc)},
               {"t": "La Galera", "x": gx - xc, "y": gy - yc, "z": cota(gx, gy)}]
    vistos = {"Planta", "La Galera"}
''', '''    rotulos = [{"t": "Planta", "x": 0.0, "y": 0.0, "z": cota(xc, yc)}]
    for r in config.bloque("visor3d").get("rotulos", []):         # los que no salen de los receptores: {t, lon, lat}
        gx, gy = a_utm.transform(r["lon"], r["lat"])
        rotulos.append({"t": r["t"], "x": gx - xc, "y": gy - yc, "z": cota(gx, gy)})
    vistos = {r["t"] for r in rotulos}
''', "el pueblo, de visor3d.rotulos en planta.json"), ("<= SEMILADO_VISTA and", "<= semilado_vista() and", "de visor3d.semilado_m")],
    (P3D, "calcular"): [("# la misma cuenta que gui/tareas/respuestas_dia.py", "# la misma cuenta que `operacion.respuestas`", COM + "sin la ruta de la planta"),
                        ("tz_convert(E.ZONA)", "tz_convert(E.zona())", ZONA),
                        ('return {"pagina": str(pagina(datos)), "horas": horas_utc}', 'return {"datos": datos, "horas": horas_utc}', "la página la monta el envoltorio")],
    (RES, "fuente"): [("m, d, q0 = cf.geometria(foco, cota)", "m, d, q0 = F.geometria(foco, cota)", "geometria pasa a operacion.focos")],
    (RES, "main"): [('add_argument("--dia", default="2026-10-21")', 'add_argument("--dia", default=None)', "el día, de series.dia_prueba en planta.json"),
                    ('add_argument("--serie", default="odora_gfs_8est")', 'add_argument("--serie", default=None)', "la serie, de series.gfs en planta.json"),
                    ("    A = ap.parse_args()\n    registro.configurar()\n", '    A = ap.parse_args()\n    A.serie = A.serie or config.pide("series", "gfs")\n    config.asegurar_carpetas()\n    registro.configurar(config.DIR_LOGS, config.REGISTRO)\n', REG + "; la serie, de planta.json"),
                    ("dia = pd.Timestamp(A.dia)", 'dia = pd.Timestamp(A.dia or config.pide("series", "dia_prueba"))', "el día, de planta.json")],
    (VPE, "TITULO_GFS"): [("(ENCE La Galera)\"\n", '(%s)"          # %s: el nombre de la planta, ver `casos.viento3d.cabecera`\n', "el nombre de la planta, de identidad.nombre_casos: el mismo texto")],
    (VPE, "preparar_caso"): [("col, gc.N_COL, xs, ys", 'col, config.pide("pronostico", "n_col"), xs, ys', "de pronostico.n_col: gfs_columnas ya no tiene la constante"),
                             ("titulo=TITULO_GFS,", "titulo=vc.cabecera(TITULO_GFS),", "con identidad.nombre_casos"),
                             ('    control.escribir(caso / "viento3d.inp", r, horas[0], len(horas) - 1, zona, config.VIENTO3D_ZFACE,\n                     estaciones=lista, r1_km=5.0, rmax_km=30.0, isurft=1)\n',
                              '    radios = {} if lista is None else {"r1_km": config.pide("series", "r1_km"), "rmax_km": config.pide("series", "rmax_km")}\n    control.escribir(caso / "viento3d.inp", r, horas[0], len(horas) - 1, zona, config.VIENTO3D_ZFACE,\n                     estaciones=lista, isurft=1, **radios)\n', "los radios, de series en planta.json, y solo si hay estaciones (sin ellas, el control no los usa)"),
                             ('else "GFS 0,25° (predicción a 1 día) + 8 estaciones Meteocat")', 'else f"GFS 0,25° (predicción a 1 día) + {len(lista)} estaciones Meteocat")', "las 8 eran las de la planta: mismo texto con 8")],
    (VPE, "main"): [("    registro.configurar()\n", "    config.asegurar_carpetas()\n    registro.configurar(config.DIR_LOGS, config.REGISTRO)\n", REG),
                    ("A.serie or SERIE\n", 'A.serie or config.pide("series", "gfs")\n', SERIE)],
    (SER, "main"): [('default=list(config.REANALISIS_ANIOS))', 'default=None)', DEF + "; así --help responde sin planta"),
                    ("    a = ap.parse_args()\n    registro.configurar()\n",
                     '    a = ap.parse_args()\n    a.anios = list(config.REANALISIS_ANIOS) if a.anios is None else a.anios\n    ESTACIONES = list(config.pide("estaciones", "codigos"))\n    SERIES = {"teodors": config.pide("series", "era5")}\n    config.asegurar_carpetas()\n    registro.configurar(config.DIR_LOGS, config.REGISTRO)\n',
                     "las estaciones y la serie se leían al importar: ahora, al empezar; " + REG)],
    (EJE, "ENCUADRE_GRADOS"): [(" (ence.centrar)", "", COM + "sin el nombre de la función del mapa de la app")],
    (EJE, "principal"): [("def principal(plan):\n", "def principal(plan):\n    EJEMPLO = carpeta_ejemplo()\n", "la carpeta, de operacion.ejemplo en planta.json")],
}
QUITADOS = {(PLA, "ZONA"): "a proyeccion.zona_horaria de planta.json", (SIM, "INICIO"): "de reanalisis.anios: horas_reanalisis", (SIM, "FIN"): "de reanalisis.anios: horas_reanalisis",
            (VMA, "SERIE"): "a series.era5 de planta.json", (VMA, "TITULOS"): "a series.titulos de planta.json", (VMA, "PREFERIDAS"): "a series.preferidas de planta.json",
            (P3D, "RECURSOS"): "se queda en el envoltorio, para montar la página", (P3D, "SEMILADO_VISTA"): "a visor3d.semilado_m de planta.json", (P3D, "GALERA"): "a visor3d.rotulos de planta.json",
            (P3D, "pagina"): "se queda en el envoltorio: usa el tema de la app (tanda 8)", (VPE, "SERIE"): "a series.gfs de planta.json",
            (SER, "ESTACIONES"): "se leía al importar: ahora en main, de estaciones.codigos", (SER, "SERIES"): "se leía al importar: ahora en main, de series.era5",
            (EJE, "LIB"): "solo servía para EJEMPLO", (EJE, "EJEMPLO"): "a operacion.ejemplo de planta.json: carpeta_ejemplo"}
NUEVOS = {(NOR, "PLANTILLA"): "la plantilla nacional", (NOR, "ruta"): "el fichero que manda: el de la planta o la plantilla", (FOC, "tipos"): "los 15 y los de la planta",
          (FOC, "geometria"): "de preparacion.puffs.control_fuentes, sin el módulo por parámetro (comprobado abajo)", (PLA, "zona"): "lee proyeccion.zona_horaria", (SIM, "horas_reanalisis"): "lee reanalisis.anios",
          (VMA, "serie_defecto"): "lee series.era5", (VMA, "titulos"): "lee series.titulos", (VMA, "preferidas"): "lee series.preferidas", (VMA, "biblioteca"): "lee viento_local.biblioteca",
          (P3D, "semilado_vista"): "lee visor3d.semilado_m", (EJE, "carpeta_ejemplo"): "lee operacion.ejemplo", (EJE, "main"): "lo que había suelto bajo __main__: el envoltorio tiene que poder llamarlo"}

mal = 0
diferencias = []
iguales = 0
for v_rel, n_rel in PARES:
    print(f"\n== {n_rel} frente a {v_rel} ==")
    s0, s1 = viejo(v_rel), nuevo(n_rel)
    t0, t1 = tabla(s0), tabla(s1)
    for nombre in t0:
        if nombre not in t1:
            if (n_rel, nombre) in QUITADOS:
                print("quitado  ", nombre, "·", QUITADOS[(n_rel, nombre)])
                diferencias.append((n_rel, nombre, "quitado: " + QUITADOS[(n_rel, nombre)]))
            else:
                print("FALTA    ", nombre)
                mal += 1
            continue
        ta, tb = texto_sin_doc(s0, t0[nombre]), texto_sin_doc(s1, t1[nombre])
        motivos = []
        for de, a_, motivo in ESPERADOS.get((n_rel, nombre), []):
            if ta.count(de) != 1:
                print("ESPERADO SIN USO", nombre, repr(de))
                mal += 1
            ta = ta.replace(de, a_)
            motivos.append(motivo)
        if ta != tb:
            print("DISTINTO ", nombre)
            print("--- esperado\n" + ta + "--- hay\n" + tb)
            mal += 1
            continue
        mismo_ast = ast_sin_doc(t0[nombre]) == ast_sin_doc(t1[nombre])
        solo_comentario = motivos and all(m.startswith(COM) for m in motivos)
        if motivos == [] and not mismo_ast:
            print("AST DISTINTO", nombre)
            mal += 1
        elif (motivos and not solo_comentario and mismo_ast) or (solo_comentario and not mismo_ast):
            print("EXPLICADO, PERO NO CUADRA CON EL AST", nombre)
            mal += 1
        elif not motivos:
            iguales += 1
            print("igual    ", nombre)
        else:
            print("explicado", nombre, "·", "; ".join(dict.fromkeys(motivos)))
            diferencias.append((n_rel, nombre, "; ".join(dict.fromkeys(motivos))))
    for nombre in t1:
        if nombre not in t0:
            if (n_rel, nombre) in NUEVOS:
                print("nuevo    ", nombre, "·", NUEVOS[(n_rel, nombre)])
                diferencias.append((n_rel, nombre, "nuevo: " + NUEVOS[(n_rel, nombre)]))
            else:
                print("SOBRA    ", nombre)
                mal += 1

print("\n== geometria, de control_fuentes a focos; control_fuentes, sin ella ==")
cf0, cf1 = _git(REPO_CORE, COMMIT_CORE, "core/preparacion/puffs/control_fuentes.py"), nuevo("preparacion/puffs/control_fuentes.py")
g0 = texto_sin_doc(cf0, tabla(cf0)["geometria"])
g1 = texto_sin_doc(nuevo(FOC), tabla(nuevo(FOC))["geometria"])
g0 = g0.replace("def geometria(foco, cota, F):", "def geometria(foco, cota):").replace("F.area_m2(foco)", "area_m2(foco)").replace("F.caudal_m3_s(foco)", "caudal_m3_s(foco)")
print("geometria, igual salvo el módulo por parámetro:", g0 == g1)
mal += g0 != g1
t0, t1 = tabla(cf0), tabla(cf1)
ok = set(t0) - set(t1) == {"geometria"} and set(t1) <= set(t0) and all(texto_sin_doc(cf0, t0[n]) == texto_sin_doc(cf1, t1[n]) for n in t1)
print("control_fuentes: lo demás, igual:", ok)
mal += not ok

print("\n== Diff entero, también docstrings y lo que queda fuera de las funciones ==")
for v_rel, n_rel in PARES:
    print(f"--- {n_rel}")
    for linea in difflib.unified_diff(viejo(v_rel).splitlines(), nuevo(n_rel).splitlines(), lineterm="", n=0):
        if not linea.startswith(("---", "+++", "@@")):
            print(linea)

print("\n== Caracteres invisibles, original -> nuevo ==")
cuenta = lambda t: {RARO[ord(c)]: t.count(c) for c in set(t) if ord(c) in RARO}
for v_rel, n_rel in PARES:
    a, b = cuenta(viejo(v_rel)), cuenta(nuevo(n_rel))
    print(n_rel, a, "->", b)

print("\n== Imports de nivel superior del core ==")
estandar = set(sys.stdlib_module_names)
for _, n_rel in PARES:
    fuera = []
    for n in ast.parse(nuevo(n_rel)).body:
        if isinstance(n, ast.Import):
            fuera += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            fuera += [f"{n.module}.{a.name}" for a in n.names]
    print(n_rel, sorted(x for x in fuera if x.split(".")[0] not in estandar))
    mal += any("galera" in x or x.startswith(("PySide6", "folium", "pyvista")) for x in fuera)
for n in ast.walk(ast.parse(nuevo("preparacion/puffs/control_fuentes.py"))):
    if isinstance(n, ast.ImportFrom) and "operacion" in (n.module or ""):
        print("preparacion importa operacion")
        mal += 1

print("\n== Lo que no puede quedar en el core ==")
for _, n_rel in PARES:
    t = nuevo(n_rel)
    for patron in (r"_8est", r"ENCE", r"[Gg]alera", r"CALPUFF|CALMET|AERMOD|AERMET|AERMAP|MAKEGEO|BPIP", r"99-Test", r"gui/", r"Madrid", r"PNOA", r"CIRCE", r"2026-10-21", r"ence\."):
        k = len(re.findall(patron, t))
        if k:
            print("HAY", patron, "en", n_rel)
            mal += 1
t = nuevo("operacion/normativa_nacional.json")
print("plantilla sin rutas ni nombres de la planta:", not re.search(r"Galera|ENCE|docs/", t))
mal += bool(re.search(r"Galera|ENCE|docs/", t))

print("\n== Constantes del original frente a planta.json y a los envoltorios ==")
if os.environ.get("T6_PAQUETES"):                   # antes de fijar el clon: el core de desarrollo
    sys.path.insert(0, os.environ["T6_PAQUETES"])
    import teodors  # noqa: F401
sys.path[:0] = [str(PLANTA / "lib" / "paquetes"), str(PLANTA / "lib")]
trabajo = Path(tempfile.mkdtemp(prefix="t6_"))
os.environ["ENCE_GALERA_LOCAL"] = str(trabajo / "local")
import importlib  # noqa: E402

pj = json.loads((PLANTA / "lib/galera/gui/planta/planta.json").read_text(encoding="utf-8"))
pj0 = json.loads(viejo("lib/galera/gui/planta/planta.json"))
lit = lambda rel, nombre: ast.literal_eval(tabla(viejo(rel))[nombre].value)
E = importlib.import_module("galera.gui.escenarios")
F = importlib.import_module("galera.gui.focos")
N = importlib.import_module("galera.gui.normativa")
P = importlib.import_module("galera.gui.periodos")
PC = importlib.import_module("galera.gui.planes_calculo")
PM = importlib.import_module("galera.gui.penacho_mapa")
VM = importlib.import_module("galera.gui.viento_mapa")
PD = importlib.import_module("galera.gui.penacho_3d")
RD = importlib.import_module("galera.gui.tareas.respuestas_dia")
VDL = importlib.import_module("galera.gui.tareas.viento_dia_local")
VS = importlib.import_module("galera.gui.tareas.viento3d_series")
EJ = importlib.import_module("galera.gui.tareas.ejemplo_configuracion")
CF = importlib.import_module("galera.gui.tareas.control_fuentes")
config = importlib.import_module("galera.gui.config")
i0, f0 = ast.literal_eval(tabla(viejo(GUI + "planes_calculo.py"))["INICIO"].value)
vm0 = GUI + "viento_mapa.py"
vd0 = GUI + "tareas/viento_dia_local.py"
comprobaciones = [
    ("ZONA, la misma", E.ZONA == lit(GUI + "escenarios.py", "ZONA")),
    ("INICIO y FIN, los mismos", (PC.INICIO, PC.FIN) == (i0, f0)),
    ("SERIE, TITULOS y PREFERIDAS, mismo valor, tipo y orden", VM.SERIE == lit(vm0, "SERIE") and VM.TITULOS == lit(vm0, "TITULOS") and list(VM.TITULOS) == list(lit(vm0, "TITULOS")) and VM.PREFERIDAS == lit(vm0, "PREFERIDAS") and isinstance(VM.PREFERIDAS, tuple)),
    ("BIBLIOTECA, el mismo fichero", VM.BIBLIOTECA.resolve() == (PLANTA / GUI / "planta" / "viento_local.npz").resolve()),
    ("RUTA de la normativa, el mismo fichero", N.RUTA.resolve() == (PLANTA / GUI / "planta" / "normativa.json").resolve()),
    ("TIPOS, los mismos 15, en su orden", F.TIPOS == lit(GUI + "focos.py", "TIPOS") and list(F.TIPOS) == list(lit(GUI + "focos.py", "TIPOS"))),
    ("SEMILADO_VISTA, el mismo", PD.SEMILADO_VISTA == 3200.0),
    ("rótulo del pueblo, los mismos bits", pj["visor3d"]["rotulos"] == [{"t": "La Galera", "lon": 0 + 27 / 60 + 48 / 3600, "lat": 40 + 40 / 60 + 54 / 3600}]),
    ("SERIE del viento de un periodo, la misma", VDL.SERIE == lit(vd0, "SERIE")),
    ("TITULO_GFS, el mismo texto", VDL.TITULO_GFS == lit(vd0, "TITULO_GFS") and VDL.TITULO_GFS.isascii()),
    ("radios de viento_dia_local: los de antes (5,0 y 30,0)", (pj["series"]["r1_km"], pj["series"]["rmax_km"]) == (5.0, 30.0)),
    ("--dia y --serie de respuestas_dia: los de antes", pj["series"]["dia_prueba"] == "2026-10-21" and pj["series"]["gfs"] == "odora_gfs_8est"),
    ("ESTACIONES y SERIES de viento3d_series: los de antes", VS.ESTACIONES == pj0["estaciones"]["codigos"] and VS.SERIES == lit(GUI + "tareas/viento3d_series.py", "SERIES")),
    ("EJEMPLO, la misma carpeta", EJ.EJEMPLO.resolve() == (PLANTA / GUI / "recursos" / "ejemplo").resolve() and EJ.EJEMPLO.is_dir()),
    ("ortofoto: el fichero de siempre", (config.PLANTA / pj["visor3d"]["ortofoto"]).resolve() == (PLANTA / GUI / "recursos" / "visor3d" / "ortofoto.jpg").resolve()),
    ("plantilla nacional: los mismos gases y percentiles que hoy tiene la planta", all(json.loads(nuevo("operacion/normativa_nacional.json"))[k] == json.loads(viejo(GUI + "planta/normativa.json"))[k] for k in ("gases", "olor", "sin_limite"))),
    ("normativa.json de la planta, sin tocar", (PLANTA / GUI / "planta" / "normativa.json").read_bytes().decode("utf-8").replace("\r\n", "\n") == viejo(GUI + "planta/normativa.json")),
    ("iconos: los mismos, en su sitio nuevo", all(PM.ICONOS.joinpath(r).read_text(encoding="utf-8").strip() == viejo(GUI + "recursos/iconos/" + r).strip() for r in ("termometro.svg", "tiempo/d_clear.svg", "tiempo/d_cloud.svg", "tiempo/d_rain.svg", "tiempo/n_clear.svg", "tiempo/n_cloud.svg", "tiempo/n_rain.svg"))),
    ("la app ya no tiene recursos/iconos", not (PLANTA / GUI / "recursos" / "iconos").exists()),
    ("geometria del envoltorio, con la firma de antes", str(inspect.signature(CF.geometria)) == "(foco, cota)"),
    ("calcular del envoltorio del 3D, con cancelado (Trabajo lo mira)", "cancelado" in inspect.signature(PD.calcular).parameters),
    ("plantilla del visor: solo cambia el crédito", (PLANTA / GUI / "recursos/visor3d/plantilla.html").read_bytes().decode("utf-8").replace("\r\n", "\n").replace("/*CREDITO*/", pj["visor3d"]["credito"]) == viejo(GUI + "recursos/visor3d/plantilla.html")),
]
# planta.json: los bloques y campos de antes, sin tocar
quita = {"proyeccion": {"zona_horaria"}, "series": {"era5", "gfs", "preferidas", "titulos", "dia_prueba", "nota"}, "operacion": {"tipos_foco_extra", "ejemplo", "nota"}}
for bloque in pj0:
    if isinstance(pj0[bloque], dict):
        a = {k: v for k, v in pj0[bloque].items() if k != "nota" or bloque != "series"}
        b = {k: v for k, v in pj[bloque].items() if k not in quita.get(bloque, ())}
        comprobaciones.append((f"planta.json, bloque {bloque}: lo de antes, igual", a == b))
comprobaciones.append(("planta.json: el único bloque nuevo es visor3d", set(pj) - set(pj0) == {"visor3d"} and set(pj["visor3d"]) == {"ortofoto", "semilado_m", "credito", "rotulos", "nota"}))
comprobaciones.append(("planta.json, nota de series: la de antes, ampliada", pj["series"]["nota"].startswith(pj0["series"]["nota"])))
for texto, ok in comprobaciones:
    print(texto, ok)
    mal += not ok

print("\n== Envoltorios: cada nombre del original sigue, también los privados y los importados ==")
PERMITIDOS = {"LIB", "GALERA", "Path"}          # LIB y GALERA: ver QUITADOS; Path: ejemplo_configuracion ya no lo importa
for v_rel, n_rel in PARES + [(GUI + "tareas/control_fuentes.py", "preparacion/puffs/control_fuentes.py")]:
    modulo = v_rel[4:-3].replace("/", ".")
    mod = importlib.import_module(modulo)
    nombres = set(tabla(viejo(v_rel))) if not v_rel.endswith("control_fuentes.py") else set(tabla(cf0))
    for n in ast.parse(viejo(v_rel)).body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            nombres |= {(a.asname or a.name).split(".")[0] for a in n.names}
    faltan = sorted(n for n in nombres if not hasattr(mod, n))
    print(modulo, len(nombres), "nombres; sin él:", faltan)
    mal += bool(set(faltan) - PERMITIDOS)
    definidos = [n.name if isinstance(n, ast.FunctionDef) else "=" for n in ast.parse(Path(PLANTA, v_rel).read_text(encoding="utf-8")).body if isinstance(n, (ast.FunctionDef, ast.Assign))]
    print("   lo que define el envoltorio:", definidos)
    mal += bool(set(definidos) - {"__getattr__", "geometria", "abrir", "calcular", "pagina", "="} or (definidos.count("=") and not v_rel.endswith("penacho_3d.py")))

print("\n== Lo que se pone en un envoltorio llega al código movido ==")
from teodors.operacion import focos as f_core, normativa as n_core, penacho_3d as p3d_core, periodos as per_core, simulacion as s_core, viento_mapa as v_core  # noqa: E402

for m, core, nombre in ((F, f_core, "guardar"), (P, per_core, "inicio_prediccion"), (PC, s_core, "_capas"), (PD, p3d_core, "_correr")):
    orig = getattr(m, nombre)
    falso = lambda *a, **k: None
    setattr(m, nombre, falso)
    ok = getattr(core, nombre) is falso and getattr(m, nombre) is falso
    setattr(m, nombre, orig)
    ok = ok and getattr(core, nombre) is orig
    print(f"{m.__name__}.{nombre}:", ok)
    mal += not ok
a = N.RUTA
otra = trabajo / "normativa_otra.json"
otra.write_text(json.dumps({"olor": {"percentil": 98}, "sin_limite": {"percentil": 98}, "gases": {"NO2": [{"valor": 100, "promedio": "hora"}]}}), encoding="utf-8")
N.RUTA = otra
ok = F.magnitud("NO2")["ref"] == 1.0 and N.RUTA == otra
N.RUTA = a
ok = ok and F.magnitud("NO2")["ref"] == 2.0
print("normativa.RUTA llega a focos.magnitud:", ok)
mal += not ok
a = VM.BIBLIOTECA
VM.datos_local.cache_clear()
VM.BIBLIOTECA = Path("no_existe.npz")
ok = VM.datos_local() is None
VM.BIBLIOTECA = a
VM.datos_local.cache_clear()
print("viento_mapa.BIBLIOTECA llega a datos_local:", ok)
mal += not ok
ok = VM._mes is v_core._mes and VM.datos_local is v_core.datos_local and n_core.RUTA.resolve() == a.parent.joinpath("normativa.json").resolve()
print("una sola copia de las cachés:", ok)
mal += not ok

print("\n== Con los datos, frente al código original sacado de git ==")
datos = os.environ.get("ENCE_GALERA_DATOS")
if not datos:
    print("sin ENCE_GALERA_DATOS: no se comprueba")
else:
    viejo_dir = trabajo / "viejo"
    for repo, rev, rutas, destino in ((PLANTA, COMMIT, ["lib/galera", "lib/paquetes"], viejo_dir), (REPO_CORE, COMMIT_CORE, ["core"], viejo_dir / "lib" / "teodors")):
        crudo = subprocess.run(["git", "-C", str(repo), "archive", rev, *rutas], capture_output=True, check=True).stdout
        destino.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(crudo)) as tar:
            tar.extractall(destino, filter="data")
    codigo = r'''
import json, hashlib, os, sys
from pathlib import Path
from galera.gui import config, escenarios as E, focos as F, penacho_3d as P, planes_calculo as PC
import teodors
sys.stdout.reconfigure(encoding="utf-8")
assert "viejo" in teodors.__file__ and not hasattr(F, "tipos")
salen = {"resultados": {}}
cat = F.cargar()
for ruta in sorted(config.DATOS.joinpath("resultados_planes").glob("*/*/*/resultado.json")):
    r = json.loads(ruta.read_text(encoding="utf-8"))
    salen["resultados"][ruta.relative_to(config.DATOS).as_posix()] = [PC.firma(r["esc"], cat, r["periodo"]), PC.guardado(r["esc"], cat, r["periodo"]) is not None]
CAT = {"focos": [{"id": "F01", "nombre": "Uno", "tipo": "biofiltro", "modelo": "superficie", "ubicacion": {"poligono": [[0, 0], [10, 0], [10, 10]]}, "altura_m": 2.0, "funcionamiento": {"modo": "continuo"}, "olor": {"valor": 5.0, "unidad": "ou_E/(s·m2)"}, "gases": []}]}
ESC = {"formato": 2, "nombre": "X", "mes": None, "focos": {"F01": {"plan": "diario", "perfiles": [[1.0] * 24], "dias": [0]}}}
PER = {"modo": "queja", "ini": "2023-03-10", "dias": 2, "serie": "queja_20230310_2d"}
salen["firma_prueba"] = [PC.firma(ESC, CAT), PC.firma(ESC, CAT, PER)]
datos = {"firma": "x", "titulo": "Plan «Base» · Olor", "dia": "d", "unidad": "ou_E/m³", "niveles": ["1"], "horas": [], "horas_utc": [], "escala_m": 0.25, "terreno": {}, "rotulos": [], "segundos": 1.0}
salen["pagina"] = hashlib.sha256(Path(P.pagina(datos)).read_bytes()).hexdigest()
print("@@" + json.dumps(salen))
'''
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(viejo_dir / "lib" / "paquetes"), str(viejo_dir / "lib")]), PYTHONIOENCODING="utf-8", ENCE_GALERA_LOCAL=str(trabajo / "local_viejo"))
    env.pop("TEODORS_PLANTA", None)
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(trabajo))
    if r.returncode != 0:
        print("EL ORIGINAL FALLA\n" + r.stderr[-2000:])
        mal += 1
    else:
        v = json.loads(next(l for l in r.stdout.splitlines() if l.startswith("@@"))[2:])
        print("firma con los datos de la prueba, código original:", v["firma_prueba"])
        cat = F.cargar()
        for rel, (firma_v, guardado_v) in v["resultados"].items():
            ruta = Path(datos) / rel
            res = json.loads(ruta.read_text(encoding="utf-8"))
            firma_n, guardado_n = PC.firma(res["esc"], cat, res["periodo"]), PC.guardado(res["esc"], cat, res["periodo"]) is not None
            ok = firma_n == firma_v and guardado_n == guardado_v
            print(rel, "firma igual" if firma_n == firma_v else "FIRMA DISTINTA", "· guardado:", guardado_v, "->", guardado_n, "· la del fichero coincide:", res["firma"] == firma_n)
            mal += not ok
        CAT = {"focos": [{"id": "F01", "nombre": "Uno", "tipo": "biofiltro", "modelo": "superficie", "ubicacion": {"poligono": [[0, 0], [10, 0], [10, 10]]}, "altura_m": 2.0, "funcionamiento": {"modo": "continuo"}, "olor": {"valor": 5.0, "unidad": "ou_E/(s·m2)"}, "gases": []}]}
        ESC = {"formato": 2, "nombre": "X", "mes": None, "focos": {"F01": {"plan": "diario", "perfiles": [[1.0] * 24], "dias": [0]}}}
        PER = {"modo": "queja", "ini": "2023-03-10", "dias": 2, "serie": "queja_20230310_2d"}
        ok = [PC.firma(ESC, CAT), PC.firma(ESC, CAT, PER)] == v["firma_prueba"]
        print("firma con los datos de la prueba, código nuevo: igual", ok)
        mal += not ok
        d3 = {"firma": "x", "titulo": "Plan «Base» · Olor", "dia": "d", "unidad": "ou_E/m³", "niveles": ["1"], "horas": [], "horas_utc": [], "escala_m": 0.25, "terreno": {}, "rotulos": [], "segundos": 1.0}
        h = hashlib.sha256(Path(PD.pagina(d3)).read_bytes()).hexdigest()
        print("la página del visor, byte a byte:", h == v["pagina"])
        mal += h != v["pagina"]
    # lo guardado del 3D: se abre, y lo que se guardó del terreno y los rótulos es lo que sale hoy
    import numpy as np  # noqa: E402
    from teodors.fuentes import terreno  # noqa: E402
    guardados = sorted(Path(datos).joinpath("resultados_planes").glob("*/*/*/*/penacho_3d.json"))
    print(len(guardados), "penachos 3D guardados")
    for g in guardados:
        ruta_res = g.parent.parent / "resultado.json"
        res = json.loads(ruta_res.read_text(encoding="utf-8"))
        abierto = PD.abrir(str(ruta_res), g.parent.name)
        guardado = json.loads(g.read_text(encoding="utf-8"))
        print(" ", g.relative_to(datos), "se abre:", abierto is not None and Path(abierto["pagina"]).is_file(), "· listo en la lista:", any(m["listo"] for x in PD.lista() if x["ruta"] == str(ruta_res) for m in x["magnitudes"]))
        mal += abierto is None
        carpeta_r = P.dir_respuestas(res["periodo"])
        meta = json.loads((carpeta_r / "meta.json").read_text(encoding="utf-8"))
        with np.load(carpeta_r / "receptores.npz") as z:
            xr, yr, cr = z["x"], z["y"], z["cota"]
        emp = config.cargar_emplazamiento()
        Zt, _, tr = terreno.cargar(terreno.ultimo_caso(emp["lat"], emp["lon"]))

        def cota(x, y):
            f = int((tr.f - y) / -tr.e)
            c = int((x - tr.c) / tr.a)
            return float(max(Zt[min(max(f, 0), Zt.shape[0] - 1), min(max(c, 0), Zt.shape[1] - 1)], 0.0))
        centro = tuple(meta["centro"])
        t_ok = PD._terreno_vista(centro, cota) == guardado["terreno"]
        rot = PD._rotulos(meta, xr, yr, cr, centro, cota)
        r_ok = json.loads(json.dumps(rot)) == guardado["rotulos"]
        print("    terreno igual al guardado:", t_ok, "· rótulos iguales:", r_ok)
        mal += not t_ok or not r_ok
        if not r_ok:
            print("    ", rot[:3], guardado["rotulos"][:3])

print("\n== Diferencias, para el informe ==")
for f, n, motivo in diferencias:
    print(f"{f} · {n}: {motivo}")
print(f"\n{iguales} nombres iguales en texto y AST, {len(diferencias)} con su explicación")
print("RESULTADO:", "todo igual, salvo lo que se dice" if not mal else f"{mal} distintos")
sys.exit(1 if mal else 0)
