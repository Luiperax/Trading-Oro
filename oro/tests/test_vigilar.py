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
def test_guardar_en_repo_sube_al_detectar_señal(tmp_path, monkeypatch):
    """Tras una señal, el estado debe subirse YA (no al cerrar la ventana).

    Es el fallo que deja entradas huérfanas: el correo sale al instante pero el
    estado tardaba hasta 50 min en subirse; si la máquina moría en ese hueco, la
    operación se perdía y su aviso de SALIDA no llegaba nunca.
    """
    import subprocess

    vig = importlib.import_module("oro.vigilar")
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], check=True)
    subprocess.run(["git", "config", "user.name", "t"], check=True)
    (tmp_path / "estado.json").write_text('{"abiertas": []}', encoding="utf-8")
    subprocess.run(["git", "add", "estado.json"], check=True)
    subprocess.run(["git", "commit", "-qm", "init"], check=True)

    # Cambio de estado (como al abrir una operación).
    (tmp_path / "estado.json").write_text('{"abiertas": [{"dir": "compra"}]}', encoding="utf-8")

    # Sin remoto el push falla, pero el COMMIT debe quedar hecho igualmente:
    # así la siguiente ejecución encuentra la operación.
    vig._guardar_en_repo("estado.json")
    log = subprocess.run(["git", "log", "--oneline"], capture_output=True, text=True).stdout
    assert "Estado XAU/USD tras señal" in log


def test_guardar_en_repo_no_falla_fuera_de_git(tmp_path, monkeypatch):
    """En uso local (sin repo) no debe romper el vigilante."""
    vig = importlib.import_module("oro.vigilar")
    monkeypatch.chdir(tmp_path)
    assert vig._guardar_en_repo("estado.json") is False
