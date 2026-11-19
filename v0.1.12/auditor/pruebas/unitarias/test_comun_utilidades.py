# -*- coding: utf-8 -*-
"""comun · formato, errores, registro, procesos, mercator, escalas y las dos cuentas nuevas de geo
(dirección del viento y elevación del sol). La elevación se comprueba frente a la fórmula astronómica
del mediodía solar, 90° − latitud + declinación; la reproyección, frente a pyproj."""
import importlib.util
import logging
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest
from pyproj import Transformer
from rasterio.transform import from_origin

from teodors.comun import errores, escalas, formato, geo, mercator, procesos, registro

CON_MATPLOTLIB = importlib.util.find_spec("matplotlib") is not None
LAT, LON = 40.6905923, 0.4764197


# ------------------------------------------------------------------------------ formato
@pytest.mark.parametrize("x, dec, texto", [
    (4506594, 0, "4\u00a0506\u00a0594"), (45.3, 1, "45,3"), (0, 0, "0"), (-1234.5, 1, "-1\u00a0234,5"), (999, 0, "999"),
    (1000, 0, "1\u00a0000"),
])
def test_num(x, dec, texto):
    assert formato.num(x, dec) == texto


def test_num_separa_los_miles_con_espacio_duro():
    # se ve igual que un espacio normal, pero un número no se parte en dos líneas: ya se perdió una vez al reescribirlo
    assert " " not in formato.num(1234567) and "\u00a0" in formato.num(1234567)


@pytest.mark.parametrize("x, texto", [(50, "50"), (50.0, "50"), (7.5, "7,5"), (24.5, "24,5"), (1250, "1\u00a0250")])
def test_km(x, texto):
    assert formato.km(x) == texto


# ------------------------------------------------------------------------------ errores
def test_cancelado_es_una_excepcion_propia():
    assert issubclass(errores.Cancelado, Exception) and not issubclass(errores.Cancelado, RuntimeError)
    with pytest.raises(errores.Cancelado, match="parado"):
        raise errores.Cancelado("parado")


# ------------------------------------------------------------------------------ registro
@pytest.fixture
def logger_limpio():
    log = logging.getLogger(registro.NOMBRE)
    antes = list(log.handlers)
    log.handlers.clear()
    yield log
    for h in list(log.handlers):
        h.close()
        log.removeHandler(h)
    log.handlers.extend(antes)


def test_registro_escribe_con_el_nivel_en_espanol(tmp_path, logger_limpio):
    log = registro.configurar(tmp_path / "logs", "prueba")
    registro.get("modulo").warning("algo pasa")
    registro.get("modulo").debug("con detalle")
    for h in log.handlers:
        h.flush()
    ficheros = list((tmp_path / "logs").glob("prueba_*.log"))
    assert len(ficheros) == 1
    texto = ficheros[0].read_text(encoding="utf-8")
    assert "AVISO" in texto and "teodors.modulo: algo pasa" in texto and "DETALLE" in texto


def test_registro_configurar_dos_veces_no_duplica(tmp_path, logger_limpio):
    n = len(registro.configurar(tmp_path, "prueba").handlers)
    assert len(registro.configurar(tmp_path, "prueba").handlers) == n
    assert registro.get().propagate is False


def test_registro_get_cuelga_del_mismo_logger():
    assert registro.get("mapa").name == "teodors.mapa" and registro.get().name == "teodors"


# ------------------------------------------------------------------------------ procesos
def test_entorno_lleva_el_camino_de_este_proceso():
    env = procesos.entorno(MI_VARIABLE="1")
    assert env["MI_VARIABLE"] == "1" and env["PYTHONIOENCODING"] == "utf-8" and "PYTHONHOME" not in env
    partes = env["PYTHONPATH"].split(os.pathsep)
    assert [p for p in partes if p] == [os.path.abspath(p) for p in sys.path if p]


def test_entorno_quita_pythonhome_y_deja_el_entorno_como_estaba(monkeypatch):
    monkeypatch.setenv("PYTHONHOME", "x")
    assert "PYTHONHOME" not in procesos.entorno()
    assert os.environ["PYTHONHOME"] == "x"


def test_el_hijo_importa_este_mismo_odora(tmp_path):
    import teodors
    r = subprocess.run([sys.executable, "-c", "import teodors; print(teodors.__file__)"], cwd=str(tmp_path),
                       env=procesos.entorno(), capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert os.path.normcase(r.stdout.strip()) == os.path.normcase(teodors.__file__)


def test_en_un_ejecutable_la_app_se_lanza_a_si_misma_para_los_motores(tmp_path, monkeypatch):
    # usuario, 2026-11-07 (instalador): compilado, sys.executable es el propio .exe, que no entiende -m; se lanza con HIJO y main.py lo despacha
    assert not procesos.congelado()
    assert procesos.orden("teodors", "puffs", 3) == [sys.executable, "-m", "teodors", "puffs", "3"]
    # usuario, 2026-11-10: compilado con Nuitka, sys.executable es un python.exe que no existe; el .exe es sys.argv[0]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "TeOdora.exe")])
    assert procesos.congelado() and procesos.orden("teodors.operacion.respuestas", "--dia", "x") == \
        [str(tmp_path / "TeOdora.exe"), procesos.HIJO, "teodors.operacion.respuestas", "--dia", "x"]
    assert "PYTHONPATH" not in procesos.entorno()                               # teOdors va dentro: que no lo tape una copia en disco
    monkeypatch.delattr(sys, "frozen")
    assert procesos.despachar_hijo(["app.exe"]) is False and procesos.despachar_hijo(["app.exe", "--dia", "x"]) is False
    # el hijo: lo que haría `python -m teodors --version`, con el despacho de main.py (aquí, de un intérprete que hace de .exe)
    codigo = "import sys; from teodors.comun import procesos; procesos.despachar_hijo(); print('no debería llegar')"
    r = subprocess.run([sys.executable, "-c", codigo, procesos.HIJO, "teodors", "--version"], cwd=str(tmp_path), env=procesos.entorno(),
                       capture_output=True, text=True, encoding="utf-8")
    import teodors
    assert r.returncode == 0 and r.stdout.strip() == f"teodors {teodors.__version__}", r.stdout + r.stderr
    r = subprocess.run([sys.executable, "-c", codigo, procesos.HIJO, "teodors.operacion.comprobar", "--motor", "puffs"], cwd=str(tmp_path),
                       env=procesos.entorno(), capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "no debería llegar" not in r.stdout, r.stdout + r.stderr
    # en el núcleo, ningún motor se lanza ya a mano con -m: todos con procesos.orden
    import re
    from pathlib import Path
    nucleo = Path(teodors.__file__).parent
    a_mano = [f"{f.relative_to(nucleo)}" for f in nucleo.rglob("*.py") if f.name != "procesos.py" and re.search(r"\[sys\.executable,\s*\"-m\"", f.read_text(encoding="utf-8"))]
    assert a_mano == [], a_mano


def test_un_hijo_del_ejecutable_lanza_otro_motor_con_el_exe(tmp_path, monkeypatch):
    # v0.1.10: despachar_hijo cambia sys.argv al del módulo, y orden() usaba sys.argv[0] como .exe: un hijo congelado lanzaba el siguiente
    # motor con el NOMBRE del módulo como ejecutable (WinError 2). Así fallaban viento_periodo → viento3d y respuestas → puffs, todo el
    # episodio en el ejecutable (antes solo lo apañaba el instalador). Ahora despachar_hijo guarda el .exe y orden() lo usa
    exe = tmp_path / "TeOdora.exe"
    nombre = "hijo_que_lanza_otro_motor"
    (tmp_path / f"{nombre}.py").write_text(
        "from teodors.comun import procesos\nVISTA = []\n\n\ndef main():\n"
        "    VISTA.append(procesos.orden('teodors', 'puffs', 'caso.inp'))\n    return 0\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "argv", [str(exe), procesos.HIJO, nombre, "--dia", "x"])
    monkeypatch.setattr(procesos, "_EXE", None)
    try:
        with pytest.raises(SystemExit) as fin:
            procesos.despachar_hijo()
        hijo = sys.modules[nombre]
        assert fin.value.code == 0
        assert sys.argv == [nombre, "--dia", "x"]                                      # el hijo ve sus argumentos, como con python -m
        assert hijo.VISTA == [[os.path.abspath(str(exe)), procesos.HIJO, "teodors", "puffs", "caso.inp"]]   # y lanza con el .exe, no con su nombre
    finally:
        sys.modules.pop(nombre, None)


# ------------------------------------------------------------------------------ geo
@pytest.mark.parametrize("u, v, viene_de", [
    (0.0, -1.0, 0.0), (-1.0, 0.0, 90.0), (0.0, 1.0, 180.0), (1.0, 0.0, 270.0), (-1.0, -1.0, 45.0), (1.0, 1.0, 225.0),
])
def test_direccion_de_la_que_viene_el_viento(u, v, viene_de):
    assert float(geo.direccion(np.array(u), np.array(v))) == pytest.approx(viene_de)


def test_direccion_siempre_entre_0_y_360():
    a = np.linspace(0, 2 * np.pi, 361)
    d = geo.direccion(np.cos(a), np.sin(a))
    assert (d >= 0).all() and (d < 360).all()


@pytest.mark.parametrize("fecha, declinacion", [("2024-06-20", 23.44), ("2024-12-21", -23.44), ("2024-03-20", 0.0)])
def test_elevacion_del_sol_al_mediodia(fecha, declinacion):
    # 90° − latitud + declinación, en la hora de mayor elevación de ese día
    t = pd.Series(pd.date_range(f"{fecha} 00:00", periods=24 * 60, freq="min"))
    assert geo.elevacion_solar(t, LAT, LON).max() == pytest.approx(90.0 - LAT + declinacion, abs=0.5)


def test_de_noche_el_sol_esta_bajo_el_horizonte():
    t = pd.Series(pd.to_datetime(["2024-06-20 00:00", "2024-12-21 23:00"]))
    assert (geo.elevacion_solar(t, LAT, LON) < 0).all()


# ------------------------------------------------------------------------------ mercator
def test_mercator_cae_en_su_sitio():
    x0, y0, paso = 280000.0, 4510000.0, 100.0
    n = 100
    img = np.zeros((n, n, 2), dtype="uint8")
    img[:, :, 0] = 200
    img[:, :, 1] = 255
    out, ((sur, oeste), (norte, este)) = mercator.a_mercator(img, from_origin(x0, y0, paso, paso), "EPSG:25831")
    tr = Transformer.from_crs("EPSG:25831", "EPSG:4326", always_xy=True)
    lons, lats = tr.transform([x0, x0 + n * paso, x0, x0 + n * paso], [y0, y0, y0 - n * paso, y0 - n * paso])
    # la caja de salida envuelve las 4 esquinas de la entrada, salvo el redondeo a píxeles enteros, y casi sin holgura
    px_lon, px_lat = (este - oeste) / out.shape[1], (norte - sur) / out.shape[0]
    assert oeste <= min(lons) + px_lon and este >= max(lons) - px_lon
    assert sur <= min(lats) + px_lat and norte >= max(lats) - px_lat
    assert este - oeste < (max(lons) - min(lons)) * 1.01 and norte - sur < (max(lats) - min(lats)) * 1.01
    assert out.shape[2] == 2 and out.dtype == np.uint8
    assert set(np.unique(out[..., 0])) <= {0, 200}          # vecino más cercano: no inventa valores
    assert out[out.shape[0] // 2, out.shape[1] // 2, 1] == 255


def test_mercator_limita_el_lado_mayor():
    img = np.full((400, 400, 2), 255, dtype="uint8")
    grande, _ = mercator.a_mercator(img, from_origin(280000.0, 4510000.0, 25.0, 25.0), "EPSG:25831")
    pequena, _ = mercator.a_mercator(img, from_origin(280000.0, 4510000.0, 25.0, 25.0), "EPSG:25831", max_px=100)
    assert max(grande.shape[:2]) > 100 and max(pequena.shape[:2]) <= 100


# ------------------------------------------------------------------------------ escalas
def test_escalas_azul_rojo_sin_matplotlib_son_las_clases_de_velocidad():
    assert escalas.colores("azul_rojo", 5) == list(escalas.COLORES_VEL)


def test_escalas_tienen_nombre():
    assert all(isinstance(nombre, str) and nombre for nombre, _ in escalas.ESCALAS.values())


@pytest.mark.skipif(not CON_MATPLOTLIB, reason="sin matplotlib (extra mapas)")
@pytest.mark.parametrize("clave", sorted(escalas.ESCALAS))
def test_escala_lut_y_colores(clave):
    t = escalas.lut(clave)
    assert t.shape == (256, 3) and t.min() >= 0 and t.max() <= 1
    c = escalas.colores(clave, 7)
    assert len(c) == 7 and all(len(x) == 7 and x[0] == "#" for x in c)


@pytest.mark.skipif(not CON_MATPLOTLIB, reason="sin matplotlib (extra mapas)")
def test_escala_para_mapa_trae_256_valores_por_canal():
    m = escalas.para_mapa("viridis")
    assert m["gradiente"].startswith("linear-gradient(90deg,#")
    assert all(len(m[c].split()) == 256 for c in "rgb")


@pytest.mark.skipif(not CON_MATPLOTLIB, reason="sin matplotlib (extra mapas)")
def test_escala_viridis_empieza_y_acaba_en_sus_colores():
    # extremos publicados de viridis
    assert escalas.colores("viridis", 2) == ["#440154", "#fde725"]
