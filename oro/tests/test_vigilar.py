"""Pruebas del arranque del vigilante en ventana (oro.vigilar).

Cubre en concreto el fallo que reventaba en GitHub Actions: una Variable no
definida llega como cadena VACÍA (no ausente), y ``float("")`` explotaba.
"""

from __future__ import annotations

import importlib


def test_num_env_vacio_usa_defecto(monkeypatch):
    vig = importlib.import_module("oro.vigilar")
    # Variable definida pero VACÍA (como hace GitHub Actions con vars no fijadas).
    monkeypatch.setenv("ORO_BUCLE_MINUTOS", "")
    assert vig._num_env("ORO_BUCLE_MINUTOS", 50.0) == 50.0


def test_num_env_ausente_usa_defecto(monkeypatch):
    vig = importlib.import_module("oro.vigilar")
    monkeypatch.delenv("ORO_BUCLE_CADA_SEG", raising=False)
    assert vig._num_env("ORO_BUCLE_CADA_SEG", 180.0) == 180.0


def test_num_env_valor_valido_se_respeta(monkeypatch):
    vig = importlib.import_module("oro.vigilar")
    monkeypatch.setenv("ORO_BUCLE_MINUTOS", "12")
    assert vig._num_env("ORO_BUCLE_MINUTOS", 50.0) == 12.0


def test_num_env_valor_invalido_usa_defecto(monkeypatch):
    vig = importlib.import_module("oro.vigilar")
    monkeypatch.setenv("ORO_BUCLE_MINUTOS", "abc")
    assert vig._num_env("ORO_BUCLE_MINUTOS", 50.0) == 50.0


# ---------- guardado durable inmediato ----------
def test_vigilar_delega_en_la_persistencia_robusta(monkeypatch):
    """El vigilante guarda con el módulo a prueba de conflictos, no a mano.

    El guardado casero con rebase perdió una operación abierta el 24-ago-2026
    (chocó, abortó y el fallo se tragaba). Ver oro/tests/test_persistencia.py.
    """
    vig = importlib.import_module("oro.vigilar")
    llamadas = []
    monkeypatch.setattr("oro.persistencia.guardar_en_repo",
                        lambda ruta="oro_estado.json": llamadas.append(ruta) or True)
    assert vig._guardar_en_repo("estado.json") is True
    assert llamadas == ["estado.json"]


def test_guardar_fuera_de_git_no_rompe(tmp_path, monkeypatch):
    """En uso local (sin repo) no debe romper el vigilante."""
    vig = importlib.import_module("oro.vigilar")
    monkeypatch.chdir(tmp_path)
    assert vig._guardar_en_repo("estado.json") is False
