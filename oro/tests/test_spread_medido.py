"""El coste de operar está medido, no supuesto.

POR QUÉ IMPORTA MÁS QUE CUALQUIER OTRA COSA
-------------------------------------------
El coste es la restricción que decide si una estrategia de este proyecto vive o
muere, y valía 0.30 $ porque alguien lo puso. Medido con los ticks de Dukascopy
—3.189.713 ticks de 230 horas y 20 días— el spread real de XAU/USD es 0.60 $ en
la ventana en que salta la orden y 0.68 $ al cierre: el doble.

Eso cambia el resultado histórico de la estrategia de +0.1143 a +0.1030 R por
operación, y con un coste fijo mal puesto en la dirección contraria (0.60 $ para
todo el histórico) lo dejaría en +0.0680. De ahí la tabla por años.
"""

from __future__ import annotations

import pytest

from oro.config import ConfiguracionSistema
from oro.spread import SPREAD_POR_ANIO, spread_de


def test_el_coste_configurado_es_el_medido():
    """0.60 $ es la mediana medida en las horas que opera la estrategia. Si
    alguien lo vuelve a bajar a 0.30 sin medir, el sistema apuntará sus
    resultados mejores de lo que son."""
    assert ConfiguracionSistema().riesgo.coste_operacion == pytest.approx(0.60)


def test_la_tabla_cubre_el_historico_que_se_reconstruye():
    assert min(SPREAD_POR_ANIO) <= 2008
    assert max(SPREAD_POR_ANIO) >= 2026
    assert len(SPREAD_POR_ANIO) >= 15


def test_los_spreads_medidos_son_plausibles():
    """Un error de decodificación daría números absurdos y nadie se enteraría:
    el sistema seguiría funcionando y sus R serían mentira."""
    for anio, s in SPREAD_POR_ANIO.items():
        assert 0.05 < s < 3.0, f"{anio}: {s} $ no es un spread de oro creíble"


def test_spread_de_interpola_los_anios_sin_muestra():
    assert spread_de(2016) == pytest.approx(SPREAD_POR_ANIO[2016])
    # 2012 no se muestreó: queda entre 2011 y 2013.
    entre = spread_de(2012)
    assert min(SPREAD_POR_ANIO[2011], SPREAD_POR_ANIO[2013]) <= entre
    assert entre <= max(SPREAD_POR_ANIO[2011], SPREAD_POR_ANIO[2013])


def test_para_el_futuro_no_supone_que_el_spread_mejore():
    """Suponer que seguirá bajando sería optimismo sin dato que lo sostenga, y
    el optimismo en el coste es exactamente lo que infla una estrategia."""
    ultimo = max(SPREAD_POR_ANIO)
    assert spread_de(ultimo + 5) == SPREAD_POR_ANIO[ultimo]


def test_el_spread_sube_con_el_oro_pero_baja_en_relativo():
    """En dólares el spread de 2026 es mayor que el de 2016; en puntos básicos
    es mucho menor. Es lo que hace que la estrategia sea MÁS viable hoy pese a
    pagar más dólares: el rango de Londres también es mucho más ancho."""
    assert SPREAD_POR_ANIO[2026] > SPREAD_POR_ANIO[2016]


def test_la_reconstruccion_usa_el_spread_de_cada_anio():
    """Con un coste fijo, el histórico sale falso en los dos extremos: cobrarle
    a 2016 el spread de 2026 baja el resultado de +0.1030 a +0.0680 R."""
    import inspect

    from oro import historico

    fuente = inspect.getsource(historico.reconstruir)
    assert "spread_de(" in fuente, (
        "la reconstrucción ha vuelto a usar un coste fijo para 21 años")


def test_las_fichas_guardan_el_spread_que_se_les_aplico():
    """Sin esto no se puede saber con qué coste se calculó un R de hace meses,
    y el registro deja de ser auditable."""
    import datetime as dt

    from oro.historico import reconstruir
    from oro.tests.test_ruptura_sesion import ASIA_SUBE, LONDRES, _marco

    cfg = ConfiguracionSistema()
    df = _marco("2026-07-15", {**ASIA_SUBE, **LONDRES,
                               8: (4010, 3990), 9: (3995, 3950)})
    fichas = reconstruir(df, cfg)
    assert fichas and "spread_usado" in fichas[0]
    assert fichas[0]["spread_usado"] == pytest.approx(spread_de(2026))
