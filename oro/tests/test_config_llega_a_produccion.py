"""Una opción que se puede configurar y NO llega al proceso es peor que no tenerla.

Se descubrió al preparar el cambio de bróker: `ORO_COSTE_OPERACION` —el número
del que depende que el sistema gane o pierda— no se pasaba en ningún workflow.
Se podía definir en el repositorio, no llegaba al proceso, y no había manera de
enterarse: el sistema seguía calculando con 0.30 $ sin decir nada. Con ella
faltaban 15 de las 19 variables de configuración.
"""

from __future__ import annotations

import glob
import re
from pathlib import Path

import pytest

# Anclado al repositorio, no al directorio desde el que se lance pytest.
_RAIZ = Path(__file__).resolve().parents[2]
_WORKFLOWS = _RAIZ / ".github" / "workflows"

# Credenciales: van por `secrets`, no por `vars`, y no todas se usan en todos los
# trabajos (el de aprendizaje no manda avisos de señal, por ejemplo).
_CREDENCIALES = {
    "ORO_SMTP_HOST", "ORO_SMTP_USUARIO", "ORO_SMTP_CLAVE", "ORO_SMTP_DESTINO",
    "ORO_TELEGRAM_TOKEN", "ORO_TELEGRAM_CHAT_ID", "ORO_WEBHOOK_URL",
}
# Opciones de ejecución local o del panel web, que no aplican a los workflows.
_SOLO_LOCAL = {"ORO_ESTADO", "ORO_INTERVALO", "ORO_PANEL_CLAVE", "ORO_BUCLE_CADA_SEG",
               "ORO_BUCLE_MINUTOS", "ORO_RUTA_MODELO", "ORO_RUTA_OPERACIONES",
               "ORO_RUTA_SENALES", "ORO_PLAN_ESTADO"}
# Parámetros que SOLO usa la ruptura de sesión (oro-plan.yml). No tienen sentido
# en los trabajos del sistema intradía, que es una estrategia distinta, así que
# exigírselos sería ruido; a cambio, se exigen en el suyo (ver más abajo).
_DE_LA_RUPTURA = {"ORO_RUPTURA_ACTIVA", "ORO_RUPTURA_R_OBJETIVO",
                  "ORO_RUPTURA_COSTE_MAX", "ORO_RUPTURA_HORAS_VALIDEZ",
                  "ORO_RUPTURA_SESGO_CUERPO_MINIMO"}
# Trabajos que ejecutan la lógica de operativa y necesitan la configuración.
_OPERATIVOS = ("oro-alertas.yml", "oro-cierre.yml", "oro-latido.yml", "oro-aprender.yml")
_TODOS = _OPERATIVOS + ("oro-plan.yml",)


def _variables_que_lee_el_codigo() -> set[str]:
    leidas: set[str] = set()
    for f in glob.glob(str(_RAIZ / "oro" / "**" / "*.py"), recursive=True):
        if "/tests/" in f.replace("\\", "/"):
            continue
        texto = Path(f).read_text(encoding="utf-8")
        leidas |= set(re.findall(r'getenv\(\s*"(ORO_[A-Z_]+)"', texto))
        leidas |= set(re.findall(r'_num\(\s*"(ORO_[A-Z_]+)"', texto))
    return leidas


def _variables_que_pasa(workflow: str) -> set[str]:
    texto = (_WORKFLOWS / workflow).read_text(encoding="utf-8")
    return set(re.findall(r"^\s+(ORO_[A-Z_]+)\s*:", texto, re.M))


def test_el_codigo_lee_las_variables_que_esperamos():
    leidas = _variables_que_lee_el_codigo()
    assert "ORO_COSTE_OPERACION" in leidas
    assert "ORO_CAPITAL" in leidas
    assert len(leidas) >= 15, f"solo se detectan {len(leidas)}: revisa el patrón"


@pytest.mark.parametrize("workflow", _OPERATIVOS)
def test_los_workflows_pasan_toda_la_configuracion(workflow):
    faltan = (_variables_que_lee_el_codigo() - _CREDENCIALES - _SOLO_LOCAL
              - _DE_LA_RUPTURA - _variables_que_pasa(workflow))
    assert not faltan, (
        f"{workflow} no pasa {sorted(faltan)}: se pueden configurar en el "
        f"repositorio y NO llegarán al proceso, sin ningún aviso")


def test_el_plan_recibe_los_parametros_de_su_estrategia():
    """La ruptura de sesión tiene sus propios ajustes y su propio trabajo. Si no
    llegan, ORO_RUPTURA_ACTIVA=0 no la apagaría y nadie se enteraría."""
    pasa = _variables_que_pasa("oro-plan.yml")
    faltan = (_DE_LA_RUPTURA | {"ORO_COSTE_OPERACION", "ORO_CAPITAL",
                                "ORO_RIESGO_POR_OPERACION"}) - pasa
    assert not faltan, f"oro-plan.yml no pasa {sorted(faltan)}"


def test_el_coste_de_operar_llega_a_todos_los_trabajos_operativos():
    # El más importante, con su propia prueba para que el fallo se lea solo.
    for w in _TODOS:
        assert "ORO_COSTE_OPERACION" in _variables_que_pasa(w), (
            f"{w} calcularía con el spread por defecto (0.30 $) hagas lo que hagas")


def test_avisa_si_el_coste_configurado_no_deja_margen():
    """El sistema debe delatar un spread que se come su propia ventaja.

    Medido sobre 4.410 operaciones de 19,6 años, la ventaja bruta es +0.0298 R
    por operación y 1R vale de media 7.4 $, así que el spread de equilibrio
    ronda los 0.15 $ (1.16 $ si solo se mira 2024-2026, con el oro mucho más
    caro). Con 1.45 $ el coste es SEIS VECES la ventaja.
    """
    import copy

    from oro.config import cargar_configuracion

    cfg = copy.deepcopy(cargar_configuracion())
    cfg.riesgo.coste_operacion = 1.45
    problemas = cfg.validar()
    assert any("spread" in p.lower() or "coste" in p.lower() for p in problemas), (
        "un spread de 1.45 $ se come seis veces la ventaja y nadie avisa")

    cfg.riesgo.coste_operacion = 0.30
    assert not any("coste_operacion" in p for p in cfg.validar())
