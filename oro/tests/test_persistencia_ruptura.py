"""El estado de la ruptura tiene que subir al repositorio, o no sirve de nada.

CASO REAL (8-sep-2026). El vigilante mandó el plan a las 12:01 UTC —el correo
salió— pero `oro_plan.json` no estaba en la lista de ficheros que se guardan. El
runner se destruye al terminar, así que:

  * la ejecución siguiente no tenía memoria de haber enviado el plan y habría
    mandado el MISMO correo otra vez;
  * el seguimiento, sin plan que seguir, no habría avisado nunca de mover el
    stop ni de cerrar, ni habría registrado el resultado para aprender.

El fallo lo introduje yo al meter el plan en el bucle del vigilante: su paso de
guardado solo conocía el estado y el registro del sistema intradía.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from oro import persistencia


def _git(cwd, *args):
    return subprocess.run(("git",) + args, cwd=cwd, capture_output=True, text=True)


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """Un repositorio de verdad con su remoto, para no simular git."""
    remoto = tmp_path / "remoto.git"
    trabajo = tmp_path / "trabajo"
    _git(tmp_path, "init", "--bare", "-b", "main", str(remoto))
    _git(tmp_path, "clone", str(remoto), str(trabajo))
    for k, v in (("user.name", "prueba"), ("user.email", "p@p")):
        _git(trabajo, "config", k, v)
    (trabajo / "semilla.txt").write_text("x", encoding="utf-8")
    _git(trabajo, "add", "-A")
    _git(trabajo, "commit", "-m", "inicial")
    _git(trabajo, "push", "-u", "origin", "main")
    monkeypatch.chdir(trabajo)
    return trabajo


def test_el_plan_y_el_registro_de_rupturas_llegan_al_repositorio(repo):
    (repo / persistencia.RUTA_ESTADO).write_text('{"fecha": "2026-09-08"}', encoding="utf-8")
    (repo / persistencia.RUTA_PLAN).write_text(
        '{"ultimo_plan": "2026-09-08", "avisados": [], "plan": {"dia": "2026-09-08"}}',
        encoding="utf-8")
    (repo / persistencia.RUTA_RUPTURAS).write_text(
        '{"dia": "2026-09-08", "r_neto": 0.4}\n', encoding="utf-8")

    assert persistencia.guardar_en_repo() is True

    subido = _git(repo, "show", "origin/main:" + persistencia.RUTA_PLAN).stdout
    assert json.loads(subido)["ultimo_plan"] == "2026-09-08"
    subido = _git(repo, "show", "origin/main:" + persistencia.RUTA_RUPTURAS).stdout
    assert "2026-09-08" in subido


def test_el_registro_de_rupturas_no_pierde_lineas_de_otras_maquinas(repo):
    """Dos procesos distintos pueden cerrar operaciones el mismo día. El
    registro solo crece: las líneas de los dos tienen que sobrevivir."""
    (repo / persistencia.RUTA_RUPTURAS).write_text(
        '{"dia": "2026-09-07"}\n', encoding="utf-8")
    persistencia.guardar_en_repo()

    (repo / persistencia.RUTA_RUPTURAS).write_text(
        '{"dia": "2026-09-08"}\n', encoding="utf-8")
    persistencia.guardar_en_repo()

    subido = _git(repo, "show", "origin/main:" + persistencia.RUTA_RUPTURAS).stdout
    assert "2026-09-07" in subido and "2026-09-08" in subido


def test_un_plan_ilegible_no_machaca_el_bueno_del_repositorio(repo):
    """Misma disciplina que con el estado: subir basura perdería el plan del
    día y con él la memoria de que ya se envió."""
    (repo / persistencia.RUTA_PLAN).write_text('{"ultimo_plan": "2026-09-08"}',
                                               encoding="utf-8")
    persistencia.guardar_en_repo()

    (repo / persistencia.RUTA_PLAN).write_text("{esto no es json", encoding="utf-8")
    (repo / persistencia.RUTA_ESTADO).write_text('{"fecha": "x"}', encoding="utf-8")
    persistencia.guardar_en_repo()

    subido = _git(repo, "show", "origin/main:" + persistencia.RUTA_PLAN).stdout
    assert json.loads(subido)["ultimo_plan"] == "2026-09-08"


def test_sin_ningun_fichero_no_hay_nada_que_guardar(repo):
    assert persistencia.guardar_en_repo() is False
