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
