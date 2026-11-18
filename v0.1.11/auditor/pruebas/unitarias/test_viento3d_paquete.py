# -*- coding: utf-8 -*-
"""meteo.viento3d · paquete de viento (`paquete`: POD + correcciones), con la salida de referencia del caso de regresión
llano_lleida como dos meses: la misma secuencia de registros que el .cmz, lo pequeño sin pérdida y el error de cada
variable reducida acotado por la mitad de su paso."""
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from teodors.dispersion.puffs import fichero_viento as lector_puffs
from teodors.meteo.viento3d import almacen, fichero_viento, paquete

REF = (Path(__file__).resolve().parents[2] / "casos" / "viento3d" / "llano_lleida" / "referencia"
       / "calmet.dat")
MESES = ((2024, 7), (2024, 8))


@pytest.fixture(scope="module")
def construido(tmp_path_factory):
    d = tmp_path_factory.mktemp("paquete")
    cab, _ = fichero_viento.leer(REF, horas=False)
    cmz = {m: d / f"{m[0]}{m[1]:02d}.cmz" for m in MESES}
    almacen.comprimir(REF, cmz[MESES[0]], cab.nx, cab.ny)
    shutil.copy(cmz[MESES[0]], cmz[MESES[1]])
    casos = {}
    for m in MESES:
        casos[m] = d / f"caso_{m[1]}.json"
        casos[m].write_text(json.dumps({"anio": m[0], "mes": m[1], "nx": cab.nx}), encoding="utf-8")
    ajustes = {n: {"k": 4} for n in paquete.AJUSTES}             # pocos modos: que trabajen las correcciones
    ind = paquete.construir(cmz, d / "viento", "prueba", casos=casos, ajustes=ajustes, avisa=None)
    return d, cmz, ind


def _es_campo(b, nxy):
    return len(b) == 12 + 4 * nxy and b[:8].decode("latin-1").isprintable()


def test_paquete_indice_meses_y_caso(construido):
    d, _, ind = construido
    p = d / "viento"
    assert paquete.es_paquete(p) and not paquete.es_paquete(d)
    assert paquete.serie(p) == "prueba" and paquete.meses(p) == list(MESES)
    assert paquete.caso(p, 2024, 8)["mes"] == 8
    assert {"U-LEV", "V-LEV", "WFACE", "T-LEV", "EL", "USTAR", "ZI", "IRH"} <= set(ind["variables"])
    assert ind["variables"]["U-LEV"]["capas"] > 1 and ind["variables"]["EL"]["capas"] == 1
    for n, v in ind["variables"].items():
        assert v["errores"]["max"] <= v["paso"] / 2 + 1e-4 * max(1.0, v["paso"]), n
    with pytest.raises(FileNotFoundError):
        paquete.leer_campo(p, 2024, 9, "U-LEV  1")


def test_paquete_misma_secuencia_y_error_acotado(construido, tmp_path):
    d, cmz, ind = construido
    ref = almacen.descomprimir(cmz[MESES[1]], tmp_path / "ref.dat")
    rec = paquete.descomprimir(d / "viento", *MESES[1], tmp_path / "rec.dat")
    nxy = ind["nx"] * ind["ny"]
    a, b = list(almacen._registros(ref)), list(almacen._registros(rec))
    assert len(a) == len(b)
    vistos = set()
    for x, y in zip(a, b):
        assert len(x) == len(y)
        if not _es_campo(x, nxy):
            assert x == y                                         # cabeceras: tal cual
            continue
        assert x[:12] == y[:12]                                   # etiqueta y fecha
        nom = almacen._nombre(x[:8].decode("latin-1"))
        v = ind["variables"].get(nom)
        if v is None:
            assert x == y, nom                                    # lo que no se reduce: tal cual
            continue
        vistos.add(nom)
        tipo = "<i4" if v["entero"] else "<f4"
        vx, vy = np.frombuffer(x[12:], tipo).astype(float), np.frombuffer(y[12:], tipo).astype(float)
        if v["entero"]:
            assert np.abs(vx - vy).max() <= v["paso"] / 2 + 0.5, nom                  # redondeada después
        elif v["l0"]:
            ex = np.abs(np.arcsinh(vx / v["l0"]) - np.arcsinh(vy / v["l0"])).max()
            assert ex <= v["paso"] / 2 + 1e-3, nom
        else:
            assert np.abs(vx - vy).max() <= v["paso"] / 2 + 1e-4 * max(1.0, np.abs(vx).max()), nom
    assert {"U-LEV", "WFACE", "EL", "IRH"} <= vistos


def test_paquete_leer_campo_igual_que_la_reconstruccion(construido, tmp_path):
    d, cmz, _ = construido
    rec = paquete.descomprimir(d / "viento", *MESES[0], tmp_path / "rec.dat")
    _, horas = fichero_viento.leer(rec)
    fechas, u1 = paquete.leer_campo(d / "viento", *MESES[0], "U-LEV  1")
    f_cmz, _ = almacen.leer_campo(cmz[MESES[0]], "U-LEV  1")
    assert list(fechas) == list(f_cmz) == [h.ndathr for h in horas]
    np.testing.assert_allclose(u1, np.stack([h.u[0] for h in horas]), atol=1e-5)
    _, ipgt = paquete.leer_campo(d / "viento", *MESES[0], "IPGT    ")         # copiada del .cmz
    np.testing.assert_array_equal(ipgt, almacen.leer_campo(cmz[MESES[0]], "IPGT    ")[1])


def test_paquete_anadir_un_mes_con_las_mismas_bases(construido, tmp_path):
    """Un paquete hecho con un mes; se le añade el otro con `anadir`: las bases no cambian, y el mes nuevo sale como si
    hubiera estado desde el principio, con el error acotado."""
    d, cmz, _ = construido
    p = tmp_path / "viento"
    ajustes = {n: {"k": 4} for n in paquete.AJUSTES}
    paquete.construir({MESES[0]: cmz[MESES[0]]}, p, "prueba", ajustes=ajustes, avisa=None)
    antes = {f.name: f.read_bytes() for f in (p / "bases").iterdir()}
    ind = paquete.anadir({MESES[1]: cmz[MESES[1]]}, p, casos={MESES[1]: d / "caso_8.json"}, avisa=None)
    assert paquete.meses(p) == list(MESES) and ind["meses"] == ["202407", "202408"]
    assert {f.name: f.read_bytes() for f in (p / "bases").iterdir()} == antes
    assert paquete.caso(p, *MESES[1])["mes"] == 8
    for n, v in ind["variables"].items():
        assert v["errores_meses"]["202408"]["max"] <= v["paso"] / 2 + 1e-4 * max(1.0, v["paso"]), n
    ref = almacen.descomprimir(cmz[MESES[1]], tmp_path / "ref.dat")
    rec = paquete.descomprimir(p, *MESES[1], tmp_path / "rec.dat")
    a, b = list(almacen._registros(ref)), list(almacen._registros(rec))
    assert len(a) == len(b) and all(x[:12] == y[:12] for x, y in zip(a, b))
    _, u = paquete.leer_campo(p, *MESES[1], "U-LEV  1")
    assert np.abs(u - almacen.leer_campo(cmz[MESES[1]], "U-LEV  1")[1]).max() <= paquete.AJUSTES["U-LEV"]["paso"] / 2 + 1e-4
    with pytest.raises(ValueError, match="malla"):
        otro = tmp_path / "otro"
        shutil.copytree(p, otro)
        i = json.loads((otro / "indice.json").read_text(encoding="utf-8"))
        (otro / "indice.json").write_text(json.dumps(dict(i, nx=i["nx"] + 1)), encoding="utf-8")
        paquete.anadir({MESES[1]: cmz[MESES[1]]}, otro, avisa=None)


def test_paquete_lo_lee_el_motor_de_puffs(construido, tmp_path):
    d, cmz, _ = construido
    rec = paquete.descomprimir(d / "viento", *MESES[0], tmp_path / "rec.dat")
    cab_r, horas_r = lector_puffs.leer(rec)
    cab_o, horas_o = lector_puffs.leer(almacen.descomprimir(cmz[MESES[0]], tmp_path / "ref.dat"))
    assert (cab_r.nx, cab_r.ny, cab_r.nz, len(horas_r)) == (cab_o.nx, cab_o.ny, cab_o.nz, len(horas_o))
    assert set(horas_r[0].d2) == set(horas_o[0].d2)
    np.testing.assert_array_equal(horas_r[3].d2["IPGT"], horas_o[3].d2["IPGT"])
    assert np.abs(horas_r[3].u - horas_o[3].u).max() <= paquete.AJUSTES["U-LEV"]["paso"] / 2 + 1e-4
