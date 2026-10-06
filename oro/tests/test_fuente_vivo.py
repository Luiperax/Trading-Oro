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


def test_el_proveedor_al_contado_es_uno_por_proceso(monkeypatch):
    """El vigilante pide datos cada 3 minutos durante 5 horas. Con un
    proveedor nuevo cada vez, ~4.800 peticiones por ejecución para horas que
    no cambian."""
    from oro import plan_sesion

    monkeypatch.setenv("ORO_FUENTE_VIVO", "dukascopy")
    monkeypatch.setattr(plan_sesion, "_DUKASCOPY", None)
    assert plan_sesion._proveedor(False) is plan_sesion._proveedor(False)


def test_una_hora_reciente_sin_publicar_no_se_memoriza_como_vacia(monkeypatch):
    """Si se memorizara, un proveedor que vive cinco horas no volvería a pedir
    esa hora nunca y el seguimiento se quedaría ciego."""
    import datetime as dt

    from oro.datos.dukascopy_vivo import ProveedorDukascopyVivo

    class R:
        status_code, content = 404, b""

    monkeypatch.setattr("requests.get", lambda *a, **k: R())
    monkeypatch.setattr("time.sleep", lambda s: None)
    p = ProveedorDukascopyVivo(intentos=1)
    reciente = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    p.mercado_cerrado = lambda h: False
    assert p._ticks_de(reciente) is None and reciente not in p._memoria


def test_una_hora_de_mercado_abierto_fallida_no_se_memoriza_nunca(monkeypatch):
    """Antes se memorizaba como vacía si tenía más de 3 horas. Con el proveedor
    del vigilante viviendo cinco horas, una descarga fallida de la mañana de
    Londres dejaba el hueco fijo toda la tarde. Solo se memoriza el vacío de
    una hora que el horario dice cerrada."""
    import datetime as dt

    from oro.datos.dukascopy_vivo import ProveedorDukascopyVivo

    pedidas = []

    class R:
        status_code, content = 404, b""

    monkeypatch.setattr("requests.get", lambda url, **k: pedidas.append(url) or R())
    monkeypatch.setattr("time.sleep", lambda s: None)
    p = ProveedorDukascopyVivo(intentos=3)
    U = dt.timezone.utc
    martes_londres = dt.datetime(2026, 9, 29, 9, tzinfo=U)      # abierto
    sabado = dt.datetime(2026, 10, 3, 12, tzinfo=U)             # cerrado
    assert p._ticks_de(martes_londres) is None
    assert martes_londres not in p._memoria
    assert len(pedidas) == 3                   # con el mercado abierto se insiste
    pedidas.clear()
    assert p._ticks_de(sabado) is None and sabado in p._memoria
    assert len(pedidas) == 1                   # cerrado: se pregunta una vez


def test_horario_del_contado():
    """Cierra el viernes a las 17:00 de Nueva York, abre el domingo a las 18:00
    y para una hora cada día a las 17:00. En hora de Nueva York, así que vale
    igual en verano y en invierno."""
    import datetime as dt

    from oro.datos.dukascopy_vivo import ProveedorDukascopyVivo as P

    U = dt.timezone.utc
    # Verano (EDT, UTC-4).
    assert not P.mercado_cerrado(dt.datetime(2026, 10, 2, 20, tzinfo=U))  # vie 16 ET
    assert P.mercado_cerrado(dt.datetime(2026, 10, 2, 21, tzinfo=U))      # vie 17 ET
    assert P.mercado_cerrado(dt.datetime(2026, 10, 3, 12, tzinfo=U))      # sábado
    assert P.mercado_cerrado(dt.datetime(2026, 10, 4, 21, tzinfo=U))      # dom 17 ET
    assert not P.mercado_cerrado(dt.datetime(2026, 10, 4, 22, tzinfo=U))  # dom 18 ET
    assert P.mercado_cerrado(dt.datetime(2026, 10, 6, 21, tzinfo=U))      # parada diaria
    assert not P.mercado_cerrado(dt.datetime(2026, 10, 6, 7, tzinfo=U))   # Londres
    # Invierno (EST, UTC-5): la parada pasa a las 22 UTC.
    assert not P.mercado_cerrado(dt.datetime(2026, 12, 1, 21, tzinfo=U))
    assert P.mercado_cerrado(dt.datetime(2026, 12, 1, 22, tzinfo=U))


def test_un_429_espera_de_verdad(monkeypatch):
    """El servidor contesta 429 a casi todo durante más de un minuto cuando se
    le pide mucho seguido. Reintentar al segundo solo alarga el castigo."""
    import datetime as dt

    from oro.datos.dukascopy_vivo import ProveedorDukascopyVivo

    esperas = []

    class R:
        status_code, content = 429, b""

    monkeypatch.setattr("requests.get", lambda *a, **k: R())
    monkeypatch.setattr("time.sleep", esperas.append)
    p = ProveedorDukascopyVivo(intentos=3)
    p._ticks_de(dt.datetime(2026, 9, 29, 9, tzinfo=dt.timezone.utc))
    assert esperas and min(esperas) >= 5


def test_una_hora_recien_cerrada_se_pide_una_sola_vez(monkeypatch):
    """El 6-oct el plan salió diez minutos tarde por reintentar una hora que
    Dukascopy aún no había publicado. La pasada siguiente ya la recoge."""
    import datetime as dt

    from oro.datos.dukascopy_vivo import ProveedorDukascopyVivo

    pedidas = []

    class R:
        status_code, content = 404, b""

    monkeypatch.setattr("requests.get", lambda url, **k: pedidas.append(url) or R())
    monkeypatch.setattr("time.sleep", lambda s: None)
    p = ProveedorDukascopyVivo(intentos=6)
    p.mercado_cerrado = lambda h: False
    # Una hora que cerró hace un minuto.
    recien = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=61)
    assert p._ticks_de(recien) is None
    assert len(pedidas) == 1 and recien not in p._memoria
