"""Pruebas de la ruptura del rango de sesión (oro/sesiones.py).

Se construyen marcos de velas a mano, con horas de Nueva York explícitas, para
que las pruebas no dependan ni de la fecha real ni del cambio de horario.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from oro.config import ConfiguracionSistema, cargar_configuracion
from oro.dominio import Direccion
from oro.sesiones import (
    construir_plan,
    direccion_disparada,
    rango_previo,
)

NY = ZoneInfo("America/New_York")


def _marco(dia: str, precios: dict[int, tuple[float, float]]) -> pd.DataFrame:
    """Velas horarias de un día, dadas como {hora_de_Nueva_York: (alto, bajo)}."""
    filas, indice = [], []
    for hora, (alto, bajo) in sorted(precios.items()):
        momento = datetime.fromisoformat(f"{dia}T{hora:02d}:00").replace(tzinfo=NY)
        indice.append(momento.astimezone(timezone.utc))
        medio = (alto + bajo) / 2
        filas.append({"open": medio, "high": alto, "low": bajo,
                      "close": medio, "volume": 1000.0})
    return pd.DataFrame(filas, index=pd.DatetimeIndex(indice))


def _cfg(**ruptura) -> ConfiguracionSistema:
    cfg = ConfiguracionSistema()
    cfg.riesgo.coste_operacion = 0.30
    for k, v in ruptura.items():
        setattr(cfg.ruptura, k, v)
    return cfg


# Una mañana de Londres con rango 2000-2020 y un mediodía cualquiera.
MANANA = {3: (2010, 2000), 4: (2015, 2005), 5: (2012, 2002),
          6: (2020, 2008), 7: (2018, 2006)}
AHORA = datetime(2026, 3, 10, 8, 0, tzinfo=NY).astimezone(timezone.utc)


def test_el_rango_es_el_maximo_y_el_minimo_de_la_manana():
    r = rango_previo(_marco("2026-03-10", MANANA), _cfg(), AHORA.astimezone(NY).date())
    assert r is not None
    assert r.alto == pytest.approx(2020.0)
    assert r.bajo == pytest.approx(2000.0)
    assert r.amplitud == pytest.approx(20.0)
    assert r.velas == 5


def test_no_se_usan_velas_de_fuera_de_la_ventana():
    """Una vela de las 9:00 con un máximo enorme NO puede ensanchar el rango:
    a las 8:00, cuando se calcula el plan, esa vela aún no ha ocurrido."""
    velas = dict(MANANA)
    velas[2] = (2500, 1500)        # sesión asiática, fuera de la ventana
    velas[9] = (2600, 1400)        # ya en Nueva York, fuera de la ventana
    r = rango_previo(_marco("2026-03-10", velas), _cfg(), AHORA.astimezone(NY).date())
    assert r.alto == pytest.approx(2020.0)
    assert r.bajo == pytest.approx(2000.0)


def test_sin_velas_suficientes_no_hay_rango():
    """Con media mañana sin datos el rango saldría más estrecho de lo real y las
    órdenes quedarían pegadas al precio: es preferible no operar ese día."""
    r = rango_previo(_marco("2026-03-10", {3: (2010, 2000), 4: (2015, 2005)}),
                     _cfg(), AHORA.astimezone(NY).date())
    assert r is None


def test_el_plan_pone_las_ordenes_en_los_bordes_y_los_stops_cruzados():
    plan = construir_plan(_marco("2026-03-10", MANANA), _cfg(), ahora=AHORA).plan
    assert plan is not None
    # La compra dispara arriba con el stop abajo; la venta, al revés.
    assert plan.compra.entrada == pytest.approx(2020.0)
    assert plan.compra.stop == pytest.approx(2000.0)
    assert plan.venta.entrada == pytest.approx(2000.0)
    assert plan.venta.stop == pytest.approx(2020.0)
    # Las dos arriesgan lo mismo: el rango entero.
    assert plan.compra.riesgo == pytest.approx(plan.venta.riesgo)
    assert plan.compra.riesgo == pytest.approx(20.0)


def test_el_objetivo_esta_a_los_r_configurados_a_cada_lado():
    plan = construir_plan(_marco("2026-03-10", MANANA), _cfg(r_objetivo=3.0),
                          ahora=AHORA).plan
    assert plan.compra.objetivo == pytest.approx(2020.0 + 3 * 20.0)
    assert plan.venta.objetivo == pytest.approx(2000.0 - 3 * 20.0)
    assert plan.r_objetivo == pytest.approx(3.0)


def test_las_horas_limite_son_del_reloj_de_nueva_york():
    """El disparo caduca 2 horas después de abrir NY y el cierre va a las 16:00
    de Nueva York, sea cual sea el desfase con UTC ese día."""
    plan = construir_plan(_marco("2026-03-10", MANANA), _cfg(), ahora=AHORA).plan
    assert plan.valido_hasta.astimezone(NY).hour == 10
    assert plan.cierre_forzoso.astimezone(NY).hour == 16
    assert plan.valido_hasta < plan.cierre_forzoso


def test_las_horas_limite_aguantan_el_cambio_de_horario():
    """Mismo plan en enero (EST, UTC-5) y en julio (EDT, UTC-4): las horas de
    Nueva York no se mueven aunque el desfase con UTC cambie una hora.

    Con las horas fijadas en UTC —que es el error fácil— esto se desajustaría
    dos veces al año sin que nadie lo notase hasta ver el correo a deshora.
    """
    for dia in ("2026-01-14", "2026-07-15"):
        ahora = datetime.fromisoformat(f"{dia}T08:00").replace(tzinfo=NY)
        plan = construir_plan(_marco(dia, MANANA), _cfg(),
                              ahora=ahora.astimezone(timezone.utc)).plan
        assert plan is not None, dia
        assert plan.valido_hasta.astimezone(NY).hour == 10, dia
        assert plan.cierre_forzoso.astimezone(NY).hour == 16, dia


def test_desactivada_no_emite_nada():
    res = construir_plan(_marco("2026-03-10", MANANA), _cfg(activa=False), ahora=AHORA)
    assert not res.hay_plan
    assert any("desactivada" in m.lower() for m in res.motivos_no)


@pytest.mark.parametrize("alto,bajo,esperado", [
    (2025.0, 2015.0, Direccion.COMPRA),      # rompe arriba
    (2005.0, 1995.0, Direccion.VENTA),       # rompe abajo
    (2010.0, 2005.0, None),                  # se queda dentro
    (2025.0, 1995.0, None),                  # toca los dos: no se puede saber cuál fue antes
])
def test_que_orden_habria_saltado(alto, bajo, esperado):
    plan = construir_plan(_marco("2026-03-10", MANANA), _cfg(), ahora=AHORA).plan
    assert direccion_disparada(plan, alto, bajo) is esperado


def test_la_configuracion_por_defecto_es_coherente():
    problemas = [p for p in cargar_configuracion().validar() if p.startswith("ruptura")]
    assert problemas == []


@pytest.mark.parametrize("campos,fragmento", [
    ({"rango_desde_et": 8, "rango_hasta_et": 3}, "menor que"),
    ({"sesion_desde_et": 5}, "antes de que termine"),
    ({"horas_validez": 20}, "después"),
    ({"velas_minimas": 99}, "mayor que las horas"),
    ({"r_objetivo": 0.0}, "positivo"),
])
def test_la_validacion_caza_las_ventanas_imposibles(campos, fragmento):
    cfg = _cfg(**campos)
    assert any(fragmento in p for p in cfg.validar()), cfg.validar()


def test_si_el_rango_ya_se_rompio_no_se_manda_el_plan():
    """Si la tarea llega tarde (GitHub retrasa las colas gratuitas) y el precio
    ya ha salido del rango, las órdenes se ejecutarían al instante y muy lejos
    del borde: exactamente lo contrario de lo que la estrategia busca."""
    velas = dict(MANANA)
    velas[8] = (2035, 2018)              # la primera hora de NY ya rompe por arriba
    tarde = datetime(2026, 3, 10, 9, 0, tzinfo=NY).astimezone(timezone.utc)
    res = construir_plan(_marco("2026-03-10", velas), _cfg(), ahora=tarde)
    assert not res.hay_plan
    assert any("ya se ha roto" in m for m in res.motivos_no)


def test_una_vela_de_ny_dentro_del_rango_no_impide_el_plan():
    """La comprobación anterior no puede pasarse de celosa: mientras el precio
    siga dentro del rango, el plan sigue siendo válido."""
    velas = dict(MANANA)
    velas[8] = (2018, 2005)              # se mueve, pero sin salir de 2000-2020
    tarde = datetime(2026, 3, 10, 9, 0, tzinfo=NY).astimezone(timezone.utc)
    plan = construir_plan(_marco("2026-03-10", velas), _cfg(), ahora=tarde).plan
    assert plan is not None
    assert plan.compra.entrada == pytest.approx(2020.0)


# La sesión asiática va de 0:00 a 3:00 de Nueva York, antes del rango de Londres.
ASIA_SUBE  = {0: (4005, 3995), 1: (4008, 3998), 2: (4012, 4004)}
ASIA_BAJA  = {0: (4012, 4004), 1: (4008, 3998), 2: (4005, 3995)}
ASIA_PLANA = {0: (4012, 3995), 1: (4010, 3998), 2: (4008, 4000)}
LONDRES    = {3: (4018, 4004), 4: (4022, 4010), 5: (4020, 3998),
              6: (4024, 4008), 7: (4015, 4002)}
JULIO = datetime(2026, 7, 15, 8, 0, tzinfo=NY).astimezone(timezone.utc)


def _plan_con(asia: dict, **ruptura):
    velas = {**asia, **LONDRES}
    return construir_plan(_marco("2026-07-15", velas), _cfg(**ruptura), ahora=JULIO).plan


def test_si_asia_sube_la_favorita_es_la_compra():
    plan = _plan_con(ASIA_SUBE)
    assert plan.favorita is Direccion.COMPRA
    assert plan.es_favorita(plan.compra)
    assert not plan.es_favorita(plan.venta)


def test_si_asia_baja_la_favorita_es_la_venta():
    plan = _plan_con(ASIA_BAJA)
    assert plan.favorita is Direccion.VENTA
    assert plan.es_favorita(plan.venta)
    assert not plan.es_favorita(plan.compra)


def test_si_asia_se_queda_plana_no_hay_favorita():
    """Medido: los 885 días de cuerpo pequeño dan -0.0162 R/op y sus dos lados
    se comportan igual (-0.029 al alza, -0.004 a la baja). Señalar una favorita
    ahí sería inventarse una ventaja que no está en los datos."""
    plan = _plan_con(ASIA_PLANA)
    assert plan.favorita is None
    assert not plan.es_favorita(plan.compra)
    assert not plan.es_favorita(plan.venta)


def test_el_sesgo_no_mira_las_velas_del_rango_de_londres():
    """Si la ventana del sesgo se solapara con la del rango, estaría midiendo
    dos veces lo mismo. Con Asia plana y Londres claramente alcista, la favorita
    tiene que seguir siendo ninguna."""
    plan = _plan_con(ASIA_PLANA)
    assert plan.favorita is None
    # Y la validación tiene que cazar el solape si alguien mueve las horas.
    cfg = _cfg(sesgo_hasta_et=5)
    assert any("solapar" in p for p in cfg.validar()), cfg.validar()


def test_sin_velas_asiaticas_no_se_inventa_una_favorita():
    """Yahoo a veces devuelve el histórico recortado. Sin datos de Asia el
    correo no puede afirmar nada, y el plan sigue siendo válido igualmente."""
    plan = construir_plan(_marco("2026-07-15", LONDRES), _cfg(), ahora=JULIO).plan
    assert plan is not None
    assert plan.favorita is None
    assert plan.sesgo.rango == 0.0


def test_el_umbral_del_cuerpo_se_puede_ajustar():
    # ASIA_SUBE tiene cuerpo 8.00 sobre rango 17.00 = 0.47 de fuerza.
    assert _plan_con(ASIA_SUBE, sesgo_cuerpo_minimo=0.45).favorita is Direccion.COMPRA
    assert _plan_con(ASIA_SUBE, sesgo_cuerpo_minimo=0.50).favorita is None


def test_el_coste_de_operar_no_bloquea_el_plan():
    """El plan se emite pase lo que pase con el coste: el sistema informa y el
    usuario decide. El coste se sigue calculando porque el registro de
    aprendizaje guarda resultados netos, pero no gobierna nada."""
    cfg = _cfg()
    cfg.riesgo.coste_operacion = 5.00
    res = construir_plan(_marco("2026-03-10", MANANA), cfg, ahora=AHORA)
    assert res.hay_plan
    assert res.motivos_no == []
