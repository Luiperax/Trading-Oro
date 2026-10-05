"""El árbitro de fuera: que los precios sean oro al contado y no otra cosa.

ESTA PRUEBA EXISTE POR UN FALLO REAL
------------------------------------
Durante semanas el sistema calculó los niveles sobre GC=F —el futuro de COMEX—
mientras el correo decía «busca XAU/USD (oro)», que es el contado. 43 $ de
diferencia. Nadie se enteró porque el sistema solo veía un feed, y un feed solo
no puede contradecirse a sí mismo.

El LBMA Gold Price del World Gold Council es el patrón oficial del contado.
Contrastado a la misma hora: Dukascopy +3,34 $ de media, GC=F +43,08 $.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from oro.referencia import MINIMO_DIAS, TOLERANCIA, comprobar_marco


def _marco(precios, hora=9):
    """Velas horarias a la hora del fix, un día por precio."""
    idx, filas = [], []
    d = dt.date(2026, 9, 1)
    for p in precios:
        while d.weekday() >= 5:
            d += dt.timedelta(days=1)
        idx.append(dt.datetime(d.year, d.month, d.day, hora, tzinfo=dt.timezone.utc))
        filas.append({"open": p, "high": p, "low": p, "close": p, "volume": 1.0})
        d += dt.timedelta(days=1)
    return pd.DataFrame(filas, index=pd.DatetimeIndex(idx))


@pytest.fixture()
def fixes(monkeypatch):
    """Un fix de 4.000 $ todos los días, para medir el desvío sin ruido."""
    base = {}
    d = dt.date(2026, 9, 1)
    for _ in range(40):
        base[d] = 4000.0
        d += dt.timedelta(days=1)
    monkeypatch.setattr("oro.referencia.serie_fix", lambda **kw: base)
    return base


def test_el_contado_cuadra(fixes):
    """+3-4 $ es la deriva de los 30 minutos entre la subasta y el cierre de la
    vela: tiene que pasar."""
    vale, msg = comprobar_marco(_marco([4003.0, 3997.0, 4004.5, 3996.0,
                                        4002.0, 4005.0, 3999.0]))
    assert vale, msg
    assert "contado" in msg


def test_el_futuro_de_comex_se_detecta(fixes):
    """+43 $ es la prima del contrato. Esto es lo que había que cazar."""
    vale, msg = comprobar_marco(_marco([4043.0, 4041.0, 4046.0, 4038.0,
                                        4044.0, 4042.0, 4045.0]))
    assert not vale
    assert "NO ES ORO AL CONTADO" in msg
    # Y dice dónde mirar, que si no el aviso no sirve de nada.
    assert "GC=F" in msg and "ORO_FUENTE_VIVO" in msg


def test_la_deriva_diaria_no_dispara_el_aviso(fixes):
    """El oro se mueve 40 $ en una sesión. Si cada día suelto disparara el
    aviso, el sistema no mandaría plan nunca y el árbitro sería inservible.
    Lo que delata un cambio de instrumento es la MEDIA, no un día."""
    vale, msg = comprobar_marco(_marco([4040.0, 3960.0, 4035.0, 3968.0,
                                        4030.0, 3972.0, 4001.0]))
    assert vale, msg


def test_sin_referencia_se_sigue_adelante(monkeypatch):
    """Una web caída no puede dejar al sistema sin mandar el plan: el árbitro
    es una comprobación, no una dependencia."""
    monkeypatch.setattr("oro.referencia.serie_fix", lambda **kw: {})
    vale, msg = comprobar_marco(_marco([4000.0] * 7))
    assert vale
    assert "sin árbitro" in msg


def test_con_pocos_dias_no_se_pronuncia(fixes):
    """Con dos días la deriva puede más que la prima que se busca. Más vale
    decir que no se sabe que dar un veredicto que no se sostiene."""
    vale, msg = comprobar_marco(_marco([4050.0, 4048.0]))
    assert vale
    assert "Sin árbitro" in msg or "falta" in msg


def test_la_tolerancia_separa_las_dos_fuentes_medidas():
    """15 $ está entre los +3,34 medidos del contado y los +43,08 del futuro,
    con holgura por los dos lados."""
    assert 3.34 < TOLERANCIA < 43.08
    assert MINIMO_DIAS >= 5


def test_el_plan_no_se_manda_si_el_arbitro_dice_que_no():
    """Un día sin plan es mucho mejor que un plan con niveles que en el bróker
    no existen: esas órdenes se ejecutan al instante en vez de esperar."""
    import inspect

    from oro import plan_sesion

    fuente = inspect.getsource(plan_sesion.ejecutar)
    assert "comprobar_marco" in fuente
    i = fuente.find("comprobar_marco")
    j = fuente.find("notificar_plan")
    assert 0 < i < j, "el árbitro tiene que correr ANTES de mandar el correo"
