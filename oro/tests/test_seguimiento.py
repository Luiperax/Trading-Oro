"""El seguimiento de la operación: qué pasa después de mandar el plan.

Todas las velas se construyen a mano con horas de Nueva York explícitas, para
que las pruebas no dependan de la fecha real ni del cambio de horario.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from oro.config import ConfiguracionSistema
from oro.dominio import Direccion
from oro.notificaciones.base import Evento
from oro.seguimiento import EstadoPlan, registro_de, seguir
from oro.sesiones import construir_plan
from oro.tests.test_ruptura_sesion import ASIA_SUBE, LONDRES, _marco

NY = ZoneInfo("America/New_York")
DIA = "2026-07-15"


def _a_las(hora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 7, 15, hora, minuto, tzinfo=NY).astimezone(timezone.utc)


def _plan(**ruptura):
    cfg = ConfiguracionSistema()
    cfg.riesgo.coste_operacion = 0.30
    for k, v in ruptura.items():
        setattr(cfg.ruptura, k, v)
    velas = {**ASIA_SUBE, **LONDRES}
    return construir_plan(_marco(DIA, velas), cfg, ahora=_a_las(8)).plan, cfg


def _con_sesion(sesion: dict):
    """Marco con la mañana de siempre (rango 3998-4024) más las velas de NY."""
    return _marco(DIA, {**ASIA_SUBE, **LONDRES, **sesion})


# El rango de LONDRES es 3998.00 - 4024.00, así que 1R = 26.00 $.
# Compra en 4024 con stop en 3998; venta en 3998 con stop en 4024.


def test_si_no_se_sale_del_rango_sigue_esperando():
    plan, _ = _plan()
    df = _con_sesion({8: (4020, 4005), 9: (4022, 4010)})
    s = seguir(plan, df, ahora=_a_las(9, 30))
    assert s.estado is EstadoPlan.ESPERANDO
    assert s.avisos == []


def test_al_caducar_la_ventana_avisa_de_cancelar():
    plan, _ = _plan()
    df = _con_sesion({8: (4020, 4005), 9: (4022, 4010), 10: (4023, 4012)})
    s = seguir(plan, df, ahora=_a_las(10, 30))
    assert s.estado is EstadoPlan.CADUCADO
    assert len(s.avisos) == 1
    assert "CANCELA" in s.avisos[0].titulo
    assert s.avisos[0].tipo is Evento.CIERRE


def test_una_ruptura_al_alza_abre_la_compra():
    plan, _ = _plan()
    df = _con_sesion({8: (4030, 4015), 9: (4035, 4025)})
    s = seguir(plan, df, ahora=_a_las(9, 30))
    assert s.estado is EstadoPlan.ABIERTA
    assert s.direccion is Direccion.COMPRA
    assert s.entrada == pytest.approx(4024.0)
    assert s.stop_actual == pytest.approx(3998.0)


def test_una_ruptura_a_la_baja_abre_la_venta():
    plan, _ = _plan()
    df = _con_sesion({8: (4010, 3990), 9: (3995, 3980)})
    s = seguir(plan, df, ahora=_a_las(9, 30))
    assert s.direccion is Direccion.VENTA
    assert s.entrada == pytest.approx(3998.0)
    assert s.stop_actual == pytest.approx(4024.0)


def test_si_rompe_por_los_dos_lados_no_se_inventa_una_direccion():
    """Dentro de una vela de una hora no se sabe qué borde se tocó primero.
    Registrar una dirección adivinada envenenaría el aprendizaje con datos
    falsos, y un dato falso es peor que un dato que falta."""
    plan, _ = _plan()
    df = _con_sesion({8: (4030, 3990)})
    s = seguir(plan, df, ahora=_a_las(9))
    assert s.estado is EstadoPlan.AMBIGUA
    assert s.direccion is None
    assert s.avisos == []


def test_al_llegar_a_1r_avisa_de_mover_el_stop():
    plan, _ = _plan()
    # Rompe arriba en la vela de las 8 y en la de las 9 alcanza 4050 (= +1R).
    df = _con_sesion({8: (4030, 4015), 9: (4051, 4028), 10: (4045, 4035)})
    s = seguir(plan, df, ahora=_a_las(11))
    assert s.estado is EstadoPlan.ABIERTA
    assert s.stop_actual == pytest.approx(4024.0)      # movido a la entrada
    avisos = [a for a in s.avisos if a.tipo is Evento.MOVER_STOP]
    assert len(avisos) == 1
    assert "4024.00" in avisos[0].cuerpo


def test_el_aviso_de_break_even_no_se_repite():
    plan, _ = _plan()
    df = _con_sesion({8: (4030, 4015), 9: (4051, 4028), 10: (4045, 4035)})
    s = seguir(plan, df, ahora=_a_las(11), avisados={f"{plan.dia}:break-even"})
    assert [a for a in s.avisos if a.tipo is Evento.MOVER_STOP] == []


def test_el_stop_cierra_la_operacion_en_menos_1r():
    plan, _ = _plan()
    df = _con_sesion({8: (4030, 4015), 9: (4028, 3995)})
    s = seguir(plan, df, ahora=_a_las(11))
    assert s.estado is EstadoPlan.CERRADA
    assert s.motivo_cierre == "stop"
    assert s.r == pytest.approx(-1.0)


def test_tras_mover_el_stop_a_la_entrada_ya_no_se_pierde():
    plan, _ = _plan()
    # Llega a +1R (4050) y luego se da la vuelta hasta perder el rango entero.
    df = _con_sesion({8: (4030, 4015), 9: (4051, 4040), 10: (4045, 3990)})
    s = seguir(plan, df, ahora=_a_las(11))
    assert s.estado is EstadoPlan.CERRADA
    assert s.motivo_cierre == "break-even"
    assert s.r == pytest.approx(0.0)


def test_el_objetivo_cierra_la_operacion_a_los_r_configurados():
    plan, cfg = _plan()
    objetivo = plan.compra.objetivo                   # 4024 + 6*26 = 4180
    df = _con_sesion({8: (4030, 4015), 9: (objetivo + 5, 4028)})
    s = seguir(plan, df, ahora=_a_las(11))
    assert s.motivo_cierre == "objetivo"
    assert s.r == pytest.approx(cfg.ruptura.r_objetivo)


def test_dentro_de_una_vela_el_stop_va_antes_que_el_objetivo():
    """No se puede saber el orden real, así que se supone lo peor. Suponer lo
    favorable inflaría el registro de aprendizaje operación a operación."""
    plan, _ = _plan()
    df = _con_sesion({8: (4030, 4015), 9: (plan.compra.objetivo + 5, 3990)})
    s = seguir(plan, df, ahora=_a_las(11))
    assert s.motivo_cierre == "stop"
    assert s.r == pytest.approx(-1.0)


def test_al_final_de_la_sesion_avisa_de_cerrar_a_mano():
    plan, _ = _plan()
    df = _con_sesion({8: (4030, 4015), 9: (4040, 4028), 15: (4045, 4035)})
    s = seguir(plan, df, ahora=_a_las(16, 5))
    cierres = [a for a in s.avisos if a.tipo is Evento.CIERRE]
    assert len(cierres) == 1
    assert "CIERRA" in cierres[0].titulo


def test_la_ficha_guarda_el_resultado_neto_y_las_condiciones():
    """El registro va NETO de costes: en bruto haría creer que la estrategia
    gana mientras el spread se la come, que es el error de todo el proyecto."""
    plan, _ = _plan()
    df = _con_sesion({8: (4030, 4015), 9: (4028, 3995)})
    s = seguir(plan, df, ahora=_a_las(11))
    r = registro_de(plan, s, coste=0.60)
    assert r["r_bruto"] == pytest.approx(-1.0)
    assert r["r_neto"] == pytest.approx(-1.0 - 0.60 / 26.0, abs=1e-3)
    assert r["direccion"] == "compra"
    assert r["favorita"] == "compra"           # Asia subió
    assert r["acompaña_al_sesgo"] is True
    assert r["ganada"] is False
    assert r["amplitud"] == pytest.approx(26.0)


def test_la_ficha_de_un_dia_sin_operacion_no_finge_un_resultado():
    plan, _ = _plan()
    df = _con_sesion({8: (4020, 4005), 9: (4022, 4010), 10: (4023, 4012)})
    s = seguir(plan, df, ahora=_a_las(10, 30))
    r = registro_de(plan, s, coste=0.60)
    assert r["estado"] == "caducado"
    assert r["direccion"] is None
    assert r["ganada"] is None                 # ni ganada ni perdida: no la hubo


# ---- El punto de entrada completo: plan enviado -> seguimiento -> registro ----

class _Espia:
    def __init__(self, entrega: bool = True) -> None:
        self.entrega = entrega
        self.planes: list = []
        self.avisos: list = []

    def notificar_plan(self, plan) -> bool:
        self.planes.append(plan)
        return self.entrega

    def enviar(self, titulo, cuerpo, evento=None, html=None) -> bool:
        self.avisos.append((titulo, evento))
        return self.entrega


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    from oro import plan_sesion, seguir_plan

    monkeypatch.setenv("ORO_PLAN_ESTADO", str(tmp_path / "plan.json"))
    monkeypatch.setenv("ORO_RUTA_RUPTURAS", str(tmp_path / "rupturas.jsonl"))
    monkeypatch.setenv("ORO_COSTE_OPERACION", "0.30")
    espia = _Espia()
    monkeypatch.setattr(plan_sesion, "_construir_notificador", lambda: espia)
    monkeypatch.setattr(seguir_plan, "_construir_notificador", lambda: espia)
    return espia, tmp_path, monkeypatch


def _servir(monkeypatch, df):
    from oro import plan_sesion, seguir_plan
    prov = type("P", (), {"historico": lambda s, n: df})()
    monkeypatch.setattr(plan_sesion, "_proveedor", lambda sintetico: prov)
    monkeypatch.setattr(seguir_plan, "_proveedor", lambda sintetico: prov)


def test_de_punta_a_punta_plan_aviso_y_ficha(entorno):
    """El día completo: se manda el plan, salta la compra, llega a 1R y avisa,
    salta el stop en la entrada y queda registrado."""
    from oro import plan_sesion, seguir_plan

    espia, tmp, monkeypatch = entorno
    _servir(monkeypatch, _marco(DIA, {**ASIA_SUBE, **LONDRES}))
    assert plan_sesion.ejecutar(ahora=_a_las(8)) == 0
    assert len(espia.planes) == 1

    # La tarde: rompe arriba, llega a +1R y se da la vuelta hasta la entrada.
    _servir(monkeypatch, _con_sesion({8: (4030, 4015), 9: (4051, 4040),
                                      10: (4045, 3990)}))
    assert seguir_plan.ejecutar(ahora=_a_las(11)) == 0
    assert any(e is Evento.MOVER_STOP for _, e in espia.avisos)

    import json
    fichas = [json.loads(l) for l in (tmp / "rupturas.jsonl").read_text().splitlines()]
    assert len(fichas) == 1
    assert fichas[0]["motivo_cierre"] == "break-even"
    assert fichas[0]["r_bruto"] == 0.0


def test_no_registra_dos_veces_la_misma_operacion(entorno):
    from oro import plan_sesion, seguir_plan

    espia, tmp, monkeypatch = entorno
    _servir(monkeypatch, _marco(DIA, {**ASIA_SUBE, **LONDRES}))
    plan_sesion.ejecutar(ahora=_a_las(8))
    _servir(monkeypatch, _con_sesion({8: (4030, 4015), 9: (4028, 3995)}))
    seguir_plan.ejecutar(ahora=_a_las(11))
    seguir_plan.ejecutar(ahora=_a_las(12))
    seguir_plan.ejecutar(ahora=_a_las(13))
    lineas = (tmp / "rupturas.jsonl").read_text().strip().splitlines()
    assert len(lineas) == 1


def test_si_el_aviso_no_llega_se_reintenta(entorno):
    """Igual que con las señales: un aviso que no se pudo entregar no se da por
    enviado, o el usuario se queda sin saber que tiene que mover el stop."""
    from oro import plan_sesion, seguir_plan

    espia, tmp, monkeypatch = entorno
    _servir(monkeypatch, _marco(DIA, {**ASIA_SUBE, **LONDRES}))
    plan_sesion.ejecutar(ahora=_a_las(8))
    df = _con_sesion({8: (4030, 4015), 9: (4051, 4040), 10: (4048, 4040)})
    _servir(monkeypatch, df)
    espia.entrega = False
    seguir_plan.ejecutar(ahora=_a_las(11))
    espia.entrega = True
    espia.avisos.clear()
    seguir_plan.ejecutar(ahora=_a_las(11, 30))
    assert any(e is Evento.MOVER_STOP for _, e in espia.avisos)


def test_sin_plan_guardado_no_hace_nada(entorno):
    from oro import seguir_plan

    espia, tmp, monkeypatch = entorno
    _servir(monkeypatch, _marco(DIA, {**ASIA_SUBE, **LONDRES}))
    assert seguir_plan.ejecutar(ahora=_a_las(11)) == 0
    assert espia.avisos == []
    assert not (tmp / "rupturas.jsonl").exists()


# ---- Los cuatro fallos que encontró la revisión, fijados aquí ----

def test_sin_velas_no_se_da_el_dia_por_caducado():
    """Si el proveedor falla y no llegan velas, no se sabe NADA. Dar el día por
    caducado grabaría un «no hubo operación» que quizá es falso, y ese registro
    alimenta luego el aprendizaje."""
    plan, _ = _plan()
    solo_manana = _marco(DIA, {**ASIA_SUBE, **LONDRES})     # sin velas de sesión
    s = seguir(plan, solo_manana, ahora=_a_las(11))
    assert s.estado is EstadoPlan.ESPERANDO


def test_el_cierre_al_final_de_la_sesion_registra_su_resultado():
    """Sin esto, TODA operación cerrada a mano se guardaba con 0.00R, y el
    aprendizaje se quedaba solo con las que tocan stop u objetivo: las peores y
    las mejores, nunca las del medio, que son la mayoría."""
    plan, _ = _plan()
    df = _con_sesion({8: (4030, 4015), 9: (4040, 4028), 15: (4060, 4045)})
    s = seguir(plan, df, ahora=_a_las(16, 5))
    assert s.estado is EstadoPlan.CERRADA
    assert s.motivo_cierre == "cierre de sesión"
    assert s.salida is not None
    assert s.r != 0.0
    r = registro_de(plan, s, coste=0.60)
    assert r["r_bruto"] == pytest.approx(s.r, abs=1e-3)
    # Y cuenta en el marcador: con la operación marcada como abierta, `ganada`
    # salía nulo y el resultado no entraba en ninguna estadística.
    assert r["ganada"] is True


@pytest.mark.parametrize("sesion,estado", [
    ({8: (4020, 4005), 9: (4022, 4010), 10: (4023, 4012)}, "caducado"),
    ({8: (4030, 3990)}, "ambigua"),
])
def test_un_dia_sin_operacion_no_cuenta_como_perdida(sesion, estado):
    """El resultado de un día sin operación es NINGUNO, no cero y desde luego no
    menos el coste. Con -coste/R, los días de no operar restaban del marcador."""
    plan, _ = _plan()
    s = seguir(plan, _con_sesion(sesion), ahora=_a_las(11))
    assert s.estado.value == estado
    r = registro_de(plan, s, coste=0.60)
    assert r["r_bruto"] is None
    assert r["r_neto"] is None


def test_no_se_sigue_un_plan_de_otro_dia(entorno):
    """Un plan que nunca llegó a registrarse se seguiría reproduciendo cada 15
    minutos para siempre, mandando avisos de una operación de la semana pasada."""
    from oro import plan_sesion, seguir_plan

    espia, tmp, monkeypatch = entorno
    _servir(monkeypatch, _marco(DIA, {**ASIA_SUBE, **LONDRES}))
    plan_sesion.ejecutar(ahora=_a_las(8))
    _servir(monkeypatch, _con_sesion({8: (4030, 4015), 9: (4051, 4040)}))

    otro_dia = datetime(2026, 7, 22, 11, 0, tzinfo=NY).astimezone(timezone.utc)
    assert seguir_plan.ejecutar(ahora=otro_dia) == 0
    assert espia.avisos == []
    assert not (tmp / "rupturas.jsonl").exists()
