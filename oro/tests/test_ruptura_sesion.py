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


def test_con_spread_alto_no_se_emite_el_plan():
    """El freno importante: por encima del coste al que la ventaja medida se
    vuelve negativa, el sistema NO manda a operar, ni siquiera con buenos modales.
    """
    cfg = _cfg()
    cfg.riesgo.coste_operacion = 1.45          # el spread real del usuario hoy
    res = construir_plan(_marco("2026-03-10", MANANA), cfg, ahora=AHORA)
    assert not res.hay_plan
    assert any("coste" in m.lower() for m in res.motivos_no)


def test_con_el_rango_demasiado_estrecho_el_spread_manda_parar():
    """Rango de 0.90 $ y spread de 0.30 $: el coste sería el 33 % de lo que se
    arriesga, por encima del máximo del 30 %."""
    estrecha = {3: (2000.6, 2000.0), 4: (2000.8, 2000.2), 5: (2000.7, 2000.1),
                6: (2000.9, 2000.3), 7: (2000.85, 2000.4)}
    res = construir_plan(_marco("2026-03-10", estrecha), _cfg(), ahora=AHORA)
    assert not res.hay_plan
    assert any("spread" in m.lower() for m in res.motivos_no)


@pytest.mark.parametrize("spread", [0.10, 0.30, 0.60])
def test_el_umbral_de_coste_diario_se_puede_disparar_de_verdad(spread):
    """Una guarda que NUNCA salta es peor que no tenerla: da sensación de
    protección y no protege. Aquí hubo una: un suelo fijo de 1.00 $ de amplitud
    tapaba al umbral de coste con el spread por defecto, y el umbral no llegaba
    a dispararse nunca. Se quitó el suelo; esta prueba impide que vuelva.
    """
    cfg = _cfg()
    cfg.riesgo.coste_operacion = spread
    # Un rango justo por debajo del que el umbral tolera.
    ancho = spread / cfg.ruptura.coste_r_max * 0.9
    base = 2000.0
    apretada = {h: (base + ancho, base) for h in range(3, 8)}
    res = construir_plan(_marco("2026-03-10", apretada), cfg, ahora=AHORA)
    assert not res.hay_plan, f"con spread {spread} y rango {ancho:.2f} $ debería parar"
    assert any("spread" in m.lower() for m in res.motivos_no)


def test_el_umbral_diario_de_coste_es_una_red_no_un_filtro():
    """Apretarlo está MEDIDO que hace daño: a 0.20 R quitaba 163 operaciones y
    bajaba la t de 3.38 a 2.78, empeorando las dos mitades del histórico. Los
    días de rango estrecho son los que mejor miden, no los peores.

    Esta prueba fija el valor para que nadie lo "mejore" apretándolo sin medir.
    """
    from oro.config import ConfiguracionRuptura
    assert ConfiguracionRuptura().coste_r_max >= 0.30

    # Y con un rango normal de hoy (26 $) y un spread bueno, no puede estorbar.
    normal = {3: (4018, 4004), 4: (4022, 4010), 5: (4020, 3998),
              6: (4024, 4008), 7: (4015, 4002)}
    plan = construir_plan(_marco("2026-03-10", normal), _cfg(), ahora=AHORA).plan
    assert plan is not None and plan.coste_r < 0.02


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
