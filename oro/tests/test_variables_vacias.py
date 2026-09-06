"""Una Variable de Actions sin definir llega VACÍA, no ausente.

CASO REAL (6-sep-2026). Al añadir `ORO_SMTP_PUERTO: ${{ vars.ORO_SMTP_PUERTO }}`
a los workflows —para arreglar que la configuración no llegaba a producción— la
variable pasó de AUSENTE a VACÍA, y `int(os.getenv("ORO_SMTP_PUERTO", "587"))`
reventó. El vigilante murió a los 17 segundos en cada ejecución y estuvo horas
sin mandar una sola alerta. El arreglo de un problema creó otro peor.

Ninguna prueba lo cazó porque todas corren SIN esas variables definidas, que es
justo el caso que no falla. Estas corren con TODAS puestas a cadena vacía.
"""

from __future__ import annotations

import glob
import re
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[2]
_WORKFLOWS = _RAIZ / ".github" / "workflows"


def _variables_de_los_workflows() -> set[str]:
    """Toda variable ORO_* que algún workflow pasa al proceso."""
    nombres: set[str] = set()
    for f in glob.glob(str(_WORKFLOWS / "*.yml")):
        texto = Path(f).read_text(encoding="utf-8")
        nombres |= set(re.findall(r"^\s+(ORO_[A-Z_]+)\s*:", texto, re.M))
    return nombres


@pytest.fixture()
def todas_vacias(monkeypatch):
    """Como llega el entorno cuando NINGUNA Variable está definida en el repo."""
    nombres = _variables_de_los_workflows()
    assert len(nombres) >= 15, f"solo se detectan {len(nombres)}: revisa el patrón"
    for n in nombres:
        monkeypatch.setenv(n, "")
    return nombres


def test_hay_variables_que_probar():
    assert "ORO_SMTP_PUERTO" in _variables_de_los_workflows()
    assert "ORO_COSTE_OPERACION" in _variables_de_los_workflows()


def test_la_configuracion_usa_sus_valores_por_defecto(todas_vacias):
    """No basta con no reventar: los valores tienen que ser los de siempre.
    Con `cfg.simbolo = os.getenv("ORO_SIMBOLO", ...)` el símbolo quedaba en ""
    y el proveedor pedía un instrumento sin nombre."""
    from oro.config import ConfiguracionSistema, cargar_configuracion

    cfg = cargar_configuracion()
    por_defecto = ConfiguracionSistema()
    assert cfg.simbolo == por_defecto.simbolo
    assert cfg.timeframe == por_defecto.timeframe
    assert cfg.capital == por_defecto.capital
    assert cfg.riesgo.coste_operacion == por_defecto.riesgo.coste_operacion
    assert cfg.ruptura.activa is True
    assert cfg.ruptura.r_objetivo == por_defecto.ruptura.r_objetivo
    assert cfg.ruta_operaciones == por_defecto.ruta_operaciones


def test_el_notificador_de_correo_se_construye(todas_vacias, monkeypatch):
    """Esta es LA prueba del fallo: con el puerto vacío, `int("")` reventaba y
    el proceso moría antes de mirar el mercado."""
    monkeypatch.setenv("ORO_SMTP_HOST", "smtp.example.com")
    from oro.notificaciones import NotificadorEmail

    n = NotificadorEmail()
    assert n._puerto == 587           # el valor por defecto, no una excepción


def test_se_construyen_todos_los_canales(todas_vacias, monkeypatch):
    monkeypatch.setenv("ORO_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("ORO_TELEGRAM_TOKEN", "t")
    monkeypatch.setenv("ORO_TELEGRAM_CHAT_ID", "c")
    monkeypatch.setenv("ORO_WEBHOOK_URL", "https://example.com/h")
    from oro.cli import _construir_notificador

    n = _construir_notificador()
    assert len(n._canales) == 4       # consola + email + telegram + webhook


def test_la_zona_horaria_no_se_va_a_utc_en_silencio(todas_vacias):
    """El más peligroso de los tres: no revienta. Con la zona vacía caía a UTC
    y TODAS las horas de los correos salían mal —«cierra a las 20:00» cuando en
    Madrid son las 22:00— sin que nada lo delatara."""
    from datetime import datetime, timezone

    from oro.tiempo import ZONA_POR_DEFECTO, hora_local, zona_usuario

    assert str(zona_usuario()) == ZONA_POR_DEFECTO
    # 20:00 UTC en julio son las 22:00 en Madrid.
    assert hora_local(datetime(2026, 7, 15, 20, tzinfo=timezone.utc)) == "22:00"


def test_el_panel_web_se_puede_importar(todas_vacias):
    """`int(os.getenv(...))` estaba a nivel de MÓDULO: con la variable vacía no
    se podía ni importar el panel."""
    import importlib

    import oro.web

    importlib.reload(oro.web)
    assert oro.web._intervalo == 900


@pytest.mark.parametrize("modulo", [
    "oro.alerta", "oro.cierre", "oro.latido", "oro.vigilar",
    "oro.plan_sesion", "oro.seguir_plan", "oro.cli",
])
def test_los_puntos_de_entrada_se_importan(todas_vacias, modulo):
    """Cada uno de estos es un trabajo programado. Si uno no importa, ese
    trabajo muere entero y el usuario se queda sin ese aviso."""
    import importlib

    importlib.import_module(modulo)


def test_ninguna_lectura_de_entorno_convierte_a_numero_a_pelo():
    """La causa raíz, fijada. `int(os.getenv(...))` vuelve a fallar en cuanto
    alguien añada la variable a un workflow; `oro.entorno` no."""
    culpables = []
    for f in glob.glob(str(_RAIZ / "oro" / "**" / "*.py"), recursive=True):
        ruta = f.replace("\\", "/")
        # `oro/entorno.py` documenta el patrón prohibido para explicarlo, y las
        # pruebas no son código de producción.
        if "/tests/" in ruta or ruta.endswith("/oro/entorno.py"):
            continue
        for i, linea in enumerate(Path(f).read_text(encoding="utf-8").splitlines(), 1):
            if linea.lstrip().startswith("#"):      # los comentarios no ejecutan
                continue
            if re.search(r"\b(int|float)\(\s*os\.(getenv|environ)", linea):
                culpables.append(f"{Path(f).relative_to(_RAIZ)}:{i}")
    assert not culpables, (
        "convierten una variable de entorno a número sin protegerse de la "
        f"cadena vacía: {culpables}. Usa oro.entorno.entero/decimal.")
