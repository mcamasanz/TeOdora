# -*- coding: utf-8 -*-
"""Las reglas que comparan versiones (R4-R7), con carpetas de versión y plantas en un repositorio de git de verdad."""
import os
import subprocess

import pytest

from auditor import reglas


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=p", "-c", "user.email=p@p", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
                   cwd=cwd, check=True, capture_output=True)


def _version(raiz, nombre):
    c = raiz / nombre
    (c / "core").mkdir(parents=True)
    (c / "cargador").mkdir()
    (c / "cargador" / "x.txt").write_text("x", encoding="utf-8")
    (c / "core" / "__init__.py").write_text('__version__ = "%s"\n' % nombre[1:], encoding="utf-8")
    (c / "pyproject.toml").write_text('version = "%s"\n' % nombre[1:], encoding="utf-8")
    (c / "dato.txt").write_text("uno\ndos\n", encoding="utf-8")
    return c


@pytest.fixture
def repo(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
    _version(tmp_path, "v0.1.3")
    c = _version(tmp_path, "v0.1.4")
    p = tmp_path / "planta_a"
    (p / "entrada").mkdir(parents=True)
    (p / "VERSION").write_text("v0.1.3\n", encoding="utf-8")
    (p / "entrada" / "planta.json").write_text("{}", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "x")
    monkeypatch.setattr(reglas, "RAIZ", c)
    return tmp_path


def test_la_version_anterior_va_por_numero_y_no_por_orden_alfabetico(repo, monkeypatch):
    assert reglas.version_anterior().name == "v0.1.3"
    _version(repo, "v0.1.9")
    grande = _version(repo, "v0.1.10")
    monkeypatch.setattr(reglas, "RAIZ", grande)
    assert reglas.version_anterior().name == "v0.1.9"
    monkeypatch.setattr(reglas, "RAIZ", repo / "v0.1.3")
    assert reglas.version_anterior() is None
    monkeypatch.setattr(reglas, "RAIZ", repo / "planta_a")
    assert reglas.version_anterior() is None


def test_cambios_entre_dos_carpetas(repo):
    nueva, vieja = repo / "v0.1.4", repo / "v0.1.3"
    assert reglas.cambios(None) == {}
    assert reglas.cambios(vieja) == {"core/__init__.py": "M", "pyproject.toml": "M"}
    (nueva / "nuevo.txt").write_text("a", encoding="utf-8")            # sin confirmar: también cuenta
    (nueva / "ignorado.pyc").write_text("a", encoding="utf-8")         # lo ignorado no
    (vieja / "borrado.txt").write_text("a", encoding="utf-8")
    (nueva / "dato.txt").write_bytes(b"uno\r\ndos\r\n")                # el final de línea no es un cambio
    assert reglas.cambios(vieja) == {"core/__init__.py": "M", "pyproject.toml": "M", "nuevo.txt": "A", "borrado.txt": "D"}
    assert reglas._en_base(vieja, "dato.txt") == "uno\ndos\n" and reglas._en_base(vieja, "no_esta.txt") == ""


def test_r4_subir_de_version_no_es_codigo_pero_lo_demas_si(repo):
    vieja = repo / "v0.1.3"
    assert reglas.r4_pruebas_nuevas(reglas.cambios(vieja)).ok            # entre las dos solo cambia el número
    f = repo / "v0.1.4" / "core" / "dispersion" / "puffs" / "principal.py"
    f.parent.mkdir(parents=True)
    f.write_text("x = 1\n", encoding="utf-8")
    r = reglas.r4_pruebas_nuevas(reglas.cambios(vieja))
    assert not r.ok and "puffs" in " ".join(r.detalle)
    p = repo / "v0.1.4" / "auditor" / "pruebas" / "test_algo.py"
    p.parent.mkdir(parents=True)
    p.write_text("def test_puffs():\n    pass\n", encoding="utf-8")
    assert reglas.r4_pruebas_nuevas(reglas.cambios(vieja)).ok


def test_r7_todo_en_orden(repo):
    r = reglas.r7_versiones()
    assert r.ok, r.detalle
    assert "planta_a" in r.detalle[0]


def test_r7_una_version_publicada_no_se_toca(repo):
    _git(repo, "tag", "v0.1.3")
    assert reglas.r7_versiones().ok
    (repo / "v0.1.3" / "dato.txt").write_text("otro\n", encoding="utf-8")
    r = reglas.r7_versiones()
    assert not r.ok and "v0.1.3 está publicada" in r.detalle[0] and "dato.txt" in r.detalle[0]
    (repo / "v0.1.3" / "dato.txt").write_text("uno\ndos\n", encoding="utf-8")
    assert reglas.r7_versiones().ok
    (repo / "v0.1.3" / "colado.txt").write_text("x", encoding="utf-8")   # un fichero nuevo tampoco
    assert not reglas.r7_versiones().ok


def test_r7_lo_que_aun_no_se_ha_publicado_si_se_toca(repo):
    (repo / "v0.1.4" / "dato.txt").write_text("otro\n", encoding="utf-8")
    assert reglas.r7_versiones().ok


def test_r7_una_etiqueta_de_antes_de_las_carpetas_no_cuenta(repo):
    # las versiones hasta la 0.1.2 están en la raíz de su etiqueta, sin carpeta
    (repo / "v0.1.3" / "dato.txt").write_text("otro\n", encoding="utf-8")
    _git(repo, "tag", "v0.0.1")
    assert reglas.r7_versiones().ok
    r = _git(repo, "rm", "-rq", "--cached", "v0.1.3")
    _git(repo, "commit", "-q", "-m", "sin carpeta")
    _git(repo, "tag", "v0.1.3")
    assert reglas.r7_versiones().ok


def test_r7_nombre_y_version_tienen_que_coincidir(repo):
    (repo / "v0.1.4" / "core" / "__init__.py").write_text('__version__ = "0.1.5"\n', encoding="utf-8")
    d = reglas.r7_versiones().detalle
    assert any("pyproject" in x for x in d) and any("la carpeta v0.1.4 contiene la versión 0.1.5" in x for x in d)


def test_r7_una_planta_tiene_que_usar_una_version_que_exista(repo):
    (repo / "planta_a" / "VERSION").write_text("v9.9.9\n", encoding="utf-8")
    r = reglas.r7_versiones()
    assert not r.ok and "planta_a usa v9.9.9" in r.detalle[0]
    (repo / "planta_a" / "VERSION").write_text("v0.1.3\n", encoding="utf-8")
    (repo / "planta_a" / "entrada" / "planta.json").unlink()
    r = reglas.r7_versiones()
    assert not r.ok and "no tiene entrada/planta.json" in r.detalle[0]


def test_las_pruebas_del_auditor_reciben_el_path_con_su_nombre_de_windows(monkeypatch):
    # KI-41 (2026-11-16): con la variable como «PATH» (así la deja os.environ), el Chromium de conda no arranca en los hijos de pytest y la
    # prueba del PDF se saltaba siempre en el auditor. Se le pasa con el nombre de Windows, «Path», y el mismo valor
    vistos = {}

    def correr(orden, **k):
        vistos.update(k["env"])
        return subprocess.CompletedProcess(orden, 0, "", "")
    monkeypatch.setattr(reglas.subprocess, "run", correr)
    reglas._pytest(["nada"])
    if os.name == "nt":
        assert "Path" in vistos and "PATH" not in vistos
    assert vistos.get("Path", vistos.get("PATH")) == os.environ["PATH"]
