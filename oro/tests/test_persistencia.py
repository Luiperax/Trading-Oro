"""Pruebas del guardado a prueba de conflictos.

Reproducen el fallo REAL del 24-ago-2026: el vigilante envió un aviso de COMPRA
y, al guardar, el rebase chocó con el estado que otra ejecución acababa de
subir; se abortó y la operación se perdió en silencio. Ninguna ejecución
posterior supo que estaba abierta, así que el aviso de SALIDA no llegó nunca.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from oro.persistencia import _unir_jsonl, guardar_en_repo


def _run(*a, **kw):
    return subprocess.run(a, capture_output=True, text=True, check=True, **kw)


@pytest.fixture
def repo_con_remoto(tmp_path, monkeypatch):
    """Un repo local con un 'remoto' de verdad, para probar el push."""
    remoto = tmp_path / "remoto.git"
    _run("git", "init", "--bare", "-q", "-b", "main", str(remoto))

    clon = tmp_path / "clon"
    _run("git", "clone", "-q", str(remoto), str(clon))
    monkeypatch.chdir(clon)
    _run("git", "config", "user.email", "t@t.t")
    _run("git", "config", "user.name", "t")
    (clon / "oro_estado.json").write_text('{"abiertas": []}', encoding="utf-8")
    _run("git", "add", "-A")
    _run("git", "commit", "-qm", "init")
    _run("git", "push", "-q", "origin", "main")
    return clon, remoto


def _otra_ejecucion_sube_estado(remoto, tmp_path, contenido):
    """Simula OTRA ejecución que sube su estado antes que nosotros."""
    otro = tmp_path / "otro"
    _run("git", "clone", "-q", str(remoto), str(otro))
    _run("git", "-C", str(otro), "config", "user.email", "o@o.o")
    _run("git", "-C", str(otro), "config", "user.name", "o")
    (otro / "oro_estado.json").write_text(contenido, encoding="utf-8")
    _run("git", "-C", str(otro), "add", "-A")
    _run("git", "-C", str(otro), "commit", "-qm", "estado de otra ejecucion")
    _run("git", "-C", str(otro), "push", "-q", "origin", "main")


def test_guarda_aunque_otra_ejecucion_se_haya_adelantado(repo_con_remoto, tmp_path):
    """EL FALLO DEL 24-AGO: antes se perdía la operación; ahora debe guardarse."""
    clon, remoto = repo_con_remoto
    # Otra ejecución sube SU estado (esto provocaba el conflicto de rebase).
    _otra_ejecucion_sube_estado(remoto, tmp_path, '{"abiertas": [], "otra": true}')

    # Nosotros tenemos una operación ABIERTA recién avisada por correo.
    nuestro = {"abiertas": [{"direccion": "compra", "entrada": 4697.9}]}
    (clon / "oro_estado.json").write_text(json.dumps(nuestro), encoding="utf-8")

    assert guardar_en_repo() is True

    # El remoto debe contener NUESTRA operación abierta.
    subprocess.run(["git", "fetch", "-q", "origin", "main"], check=True)
    guardado = subprocess.run(["git", "show", "origin/main:oro_estado.json"],
                              capture_output=True, text=True, check=True).stdout
    assert json.loads(guardado)["abiertas"][0]["entrada"] == 4697.9


def test_el_registro_de_operaciones_no_pierde_lineas(repo_con_remoto, tmp_path):
    """El histórico solo crece: no debe perderse ninguna operación cerrada."""
    clon, remoto = repo_con_remoto
    otro = tmp_path / "otro2"
    _run("git", "clone", "-q", str(remoto), str(otro))
    _run("git", "-C", str(otro), "config", "user.email", "o@o.o")
    _run("git", "-C", str(otro), "config", "user.name", "o")
    (otro / "operaciones_oro.jsonl").write_text('{"id": "remota"}\n', encoding="utf-8")
    _run("git", "-C", str(otro), "add", "-A")
    _run("git", "-C", str(otro), "commit", "-qm", "op remota")
    _run("git", "-C", str(otro), "push", "-q", "origin", "main")

    (clon / "operaciones_oro.jsonl").write_text('{"id": "nuestra"}\n', encoding="utf-8")
    assert guardar_en_repo() is True

    subprocess.run(["git", "fetch", "-q", "origin", "main"], check=True)
    final = subprocess.run(["git", "show", "origin/main:operaciones_oro.jsonl"],
                           capture_output=True, text=True, check=True).stdout
    assert '"remota"' in final and '"nuestra"' in final   # ninguna se pierde


def test_sin_cambios_no_commitea(repo_con_remoto):
    assert guardar_en_repo() is False


def test_fuera_de_git_no_rompe(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert guardar_en_repo() is False


def test_unir_jsonl_deduplica_y_conserva_orden():
    assert _unir_jsonl('{"b": 2}\n', '{"a": 1}\n') == '{"a": 1}\n{"b": 2}\n'
    assert _unir_jsonl('{"a": 1}\n', '{"a": 1}\n') == '{"a": 1}\n'
    assert _unir_jsonl(None, '{"a": 1}\n') == '{"a": 1}\n'


def test_no_sube_un_estado_ilegible(repo_con_remoto, capsys):
    """Un estado corrupto NO debe machacar la copia buena del repositorio.

    El runner siempre escribe JSON válido, así que llegar aquí con algo ilegible
    significa disco corrupto o escritura a medias. Subirlo destruiría las
    operaciones abiertas de todas las máquinas.
    """
    from pathlib import Path

    from oro.persistencia import guardar_en_repo

    Path("oro_estado.json").write_text("{esto no es json", encoding="utf-8")
    assert guardar_en_repo("oro_estado.json") is False
    assert "no es JSON válido" in capsys.readouterr().out
