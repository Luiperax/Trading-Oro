"""El punto de entrada del plan: cuándo se lanza, cuándo NO, y qué pasa si el
correo falla. Es el trabajo que corre solo cada día en GitHub Actions, así que
lo importante es que no mande dos veces ni dé por avisado lo que no llegó."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from oro import plan_sesion
from oro.tests.test_ruptura_sesion import MANANA, _marco

NY = ZoneInfo("America/New_York")


class _Espia:
    """Notificador de mentira: apunta lo que se envía y puede fallar a propósito."""

    def __init__(self, entrega: bool = True) -> None:
        self.entrega = entrega
        self.planes: list = []

    def notificar_plan(self, plan) -> bool:
        self.planes.append(plan)
        return self.entrega


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    """Aísla el estado en un directorio temporal y sirve un marco fijo."""
    monkeypatch.setenv("ORO_PLAN_ESTADO", str(tmp_path / "plan.json"))
    monkeypatch.setenv("ORO_COSTE_OPERACION", "0.30")
    df = _marco("2026-03-10", MANANA)
    monkeypatch.setattr(plan_sesion, "_proveedor",
                        lambda sintetico: type("P", (), {"historico": lambda s, n: df})())
    espia = _Espia()
    monkeypatch.setattr(plan_sesion, "_construir_notificador", lambda: espia)
    return espia


def _a_las(hora: int) -> datetime:
    return datetime(2026, 3, 10, hora, 0, tzinfo=NY).astimezone(timezone.utc)


def test_a_las_ocho_de_nueva_york_manda_el_plan(entorno):
    assert plan_sesion.ejecutar(ahora=_a_las(8)) == 0
    assert len(entorno.planes) == 1
    assert entorno.planes[0].compra.entrada == pytest.approx(2020.0)


@pytest.mark.parametrize("hora", [3, 7, 10, 14, 20])
def test_fuera_de_su_hora_no_hace_nada(entorno, hora):
    assert plan_sesion.ejecutar(ahora=_a_las(hora)) == 0
    assert entorno.planes == []


def test_no_manda_el_mismo_plan_dos_veces(entorno):
    """GitHub encola la tarea varias veces y hay dos horarios programados (uno
    por cada mitad del año). Sin esto llegarían dos o tres correos iguales."""
    plan_sesion.ejecutar(ahora=_a_las(8))
    plan_sesion.ejecutar(ahora=_a_las(8))
    assert len(entorno.planes) == 1


def test_si_el_correo_falla_no_se_da_por_enviado(entorno, monkeypatch):
    """Marcar el día como enviado sin que el correo llegue dejaría al usuario sin
    plan hasta el día siguiente, sin que nada lo indicase."""
    entorno.entrega = False
    assert plan_sesion.ejecutar(ahora=_a_las(8)) == 1
    entorno.entrega = True
    assert plan_sesion.ejecutar(ahora=_a_las(8)) == 0
    assert len(entorno.planes) == 2       # se reintentó y esta vez sí llegó


def test_el_coste_de_operar_no_impide_mandar_el_plan(entorno, monkeypatch):
    """El plan se manda pase lo que pase con el coste. Antes había una puerta
    que lo bloqueaba; se quitó a petición del usuario, que decide él."""
    monkeypatch.setenv("ORO_COSTE_OPERACION", "5.00")
    assert plan_sesion.ejecutar(ahora=_a_las(8)) == 0
    assert len(entorno.planes) == 1


def test_forzar_salta_la_hora_y_el_duplicado(entorno):
    plan_sesion.ejecutar(ahora=_a_las(8))
    assert plan_sesion.ejecutar(forzar=True, ahora=_a_las(14)) == 0
    assert len(entorno.planes) == 2


def test_a_partir_de_las_18_de_nueva_york_el_dia_ya_es_el_siguiente(entorno):
    """El oro abre la sesión del día siguiente a las 18:00 de Nueva York. Forzar
    a esa hora busca el rango de MAÑANA, que aún no existe: no hay plan, y eso
    está bien. Vale la pena fijarlo: es justo el tipo de detalle que se rompe."""
    assert plan_sesion.ejecutar(forzar=True, ahora=_a_las(20)) == 0
    assert entorno.planes == []


def test_un_estado_ilegible_no_deja_el_sistema_mudo(entorno, tmp_path):
    (tmp_path / "plan.json").write_text("{esto no es json", encoding="utf-8")
    assert plan_sesion.ejecutar(ahora=_a_las(8)) == 0
    assert len(entorno.planes) == 1


def test_un_retraso_de_github_no_pierde_el_plan_del_dia(entorno):
    """Las colas gratuitas de GitHub retrasan las tareas con frecuencia. Perder
    el plan por 40 minutos de cola sería absurdo: se admite toda la ventana de
    disparo, y de las órdenes tardías protege `construir_plan`, no la hora."""
    assert plan_sesion.ejecutar(ahora=_a_las(9)) == 0
    assert len(entorno.planes) == 1


def test_las_tareas_programadas_cubren_las_dos_mitades_del_ano():
    """Las horas de GitHub van en UTC y la estrategia razona en hora de Nueva
    York. Con el cambio de horario esa correspondencia se mueve, así que se
    programan tres arranques: en cada mitad del año, uno envía y otro reintenta.

    Se comprueba aquí porque es justo el fallo que no se ve: el plan dejaría de
    llegar medio año y los registros dirían "no es la hora" sin más.
    """
    import re
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    texto = (raiz / ".github" / "workflows" / "oro-plan.yml").read_text(encoding="utf-8")
    horas = [int(h) for h in re.findall(r'cron:\s*"0 (\d+) \* \* 1-5"', texto)]
    assert horas, "no se han encontrado tareas programadas en oro-plan.yml"

    from oro.config import cargar_configuracion
    c = cargar_configuracion().ruptura
    for etiqueta, dia in (("verano", "2026-07-15"), ("invierno", "2026-01-14")):
        actuan = 0
        for h in horas:
            t = datetime.fromisoformat(f"{dia}T{h:02d}:00").replace(tzinfo=timezone.utc)
            if c.sesion_desde_et <= t.astimezone(NY).hour < c.sesion_desde_et + c.horas_validez:
                actuan += 1
        assert actuan >= 2, (
            f"en {etiqueta} solo {actuan} arranque(s) caen en la ventana: sin un "
            f"segundo intento, un fallo de SMTP deja el día sin plan")
