"""De dónde salen los precios en vivo, y por qué no se cambia a la ligera.

El feed era Yahoo `GC=F`: el FUTURO de COMEX, que cotizó 40,17 $ por encima del
contado en septiembre de 2026. Toda la investigación está medida sobre el
contado de Dukascopy, así que ninguna ventaja estaba validada sobre el
instrumento que se operaba.

Yahoo no tiene alternativa: XAUUSD=X, XAU=X y GCUSD=X dan 404, y ^XAU es el
índice de mineras. Dukascopy sí da el contado, y además bid y ask reales.

Lo que impide cambiarlo sin más: mueve los niveles del correo unos 40 $, y cuál
es el bueno depende de qué cotice el bróker de quien opera.
"""

from __future__ import annotations

import pytest

from oro.config import ConfiguracionSistema, cargar_configuracion


def test_la_fuente_por_defecto_es_el_contado():
    """Contrastadas las dos contra el LBMA Gold Price, el patrón OFICIAL del oro
    al contado: Dukascopy va +3,34 $ de media y GC=F +43,08 $. Y el correo pide
    operar XAU/USD, que es el contado por definición."""
    assert ConfiguracionSistema().fuente_vivo == "dukascopy"
    # El símbolo de investigación es el mismo, que es justamente el objetivo:
    # investigar y operar el mismo instrumento.
    assert ConfiguracionSistema().simbolo == "XAUUSD"


def test_se_puede_cambiar_por_entorno(monkeypatch):
    from oro.plan_sesion import _proveedor

    monkeypatch.setenv("ORO_FUENTE_VIVO", "dukascopy")
    assert cargar_configuracion().fuente_vivo == "dukascopy"
    assert type(_proveedor(False)).__name__ == "ProveedorDukascopyVivo"

    monkeypatch.setenv("ORO_FUENTE_VIVO", "yahoo")
    assert type(_proveedor(False)).__name__ == "ProveedorYahoo"


def test_una_variable_vacia_deja_la_fuente_de_siempre(monkeypatch):
    """Una Variable de Actions sin definir llega VACÍA. Si eso cambiara la
    fuente, los niveles del correo se moverían 43 $ sin que nadie lo pidiera."""
    monkeypatch.setenv("ORO_FUENTE_VIVO", "")
    assert cargar_configuracion().fuente_vivo == "dukascopy"


def test_se_piden_pocas_velas_porque_la_ruptura_no_necesita_mas():
    """Las 400 de antes eran del motor intradía (EMA 200 de calentamiento). Con
    400, una fuente que va hora a hora necesita 628 peticiones y más de media
    hora por ciclo: inviable en Actions."""
    from oro.plan_sesion import VELAS_EN_VIVO

    assert VELAS_EN_VIVO <= 48


def test_el_proveedor_al_contado_se_niega_a_servir_historicos_largos():
    """Pedirle 400 velas lo convertiría en 628 peticiones sin avisar. Mejor
    fallar con un mensaje que explique a dónde ir."""
    from oro.datos.dukascopy_vivo import ProveedorDukascopyVivo

    p = ProveedorDukascopyVivo()
    with pytest.raises(ValueError, match="mensuales"):
        p.historico(400)


def test_el_proveedor_al_contado_arma_la_vela_sobre_el_bid():
    """La investigación usa los ficheros BID_candles. Si aquí se usara el medio,
    los niveles bailarían justo en los bordes del rango, que es donde entra."""
    import datetime as dt

    import pandas as pd

    from oro.datos.dukascopy_vivo import ProveedorDukascopyVivo

    idx = pd.DatetimeIndex(
        [dt.datetime(2026, 10, 5, 9, m, tzinfo=dt.timezone.utc) for m in (0, 20, 40)])
    ticks = pd.DataFrame({"bid": [100.0, 103.0, 101.0],
                          "ask": [100.6, 103.6, 101.6]}, index=idx)
    v = ProveedorDukascopyVivo._vela(ticks)
    assert v["open"] == 100.0 and v["close"] == 101.0
    assert v["high"] == 103.0 and v["low"] == 100.0      # bid, no medio.
    assert v["spread"] == pytest.approx(0.6)             # y da el spread real.


def test_el_proveedor_al_contado_se_declara_apto_para_vivo():
    """`ProveedorDukascopy` (mensual) tiene en_vivo=False porque sus ficheros no
    existen para el mes en curso —comprobado: 503 tras 12 reintentos—. El de
    ticks sí sirve: 2,2 minutos de retraso sobre el cierre de cada hora."""
    from oro.datos.dukascopy import ProveedorDukascopy
    from oro.datos.dukascopy_vivo import ProveedorDukascopyVivo

    assert ProveedorDukascopyVivo.en_vivo is True
    assert ProveedorDukascopy.en_vivo is False
