"""Pruebas del proveedor de Dukascopy, sin tocar la red.

Lo que de verdad puede romperse en silencio aquí es el DESCIFRADO del formato
binario: un orden de campos equivocado o un divisor mal puesto no lanza ningún
error, solo produce precios plausibles y falsos. Por eso se construyen ficheros
``.bi5`` sintéticos con valores conocidos y se comprueba byte a byte.

El otro fallo mudo es el relleno de fines de semana: Dukascopy entrega las horas
de mercado cerrado como velas planas de volumen 0. Colarlas hundiría el ATR y la
estrategia creería haber visto un mercado quieto que nunca existió.
"""

from __future__ import annotations

import datetime as dt
import lzma
import struct

import pandas as pd
import pytest

from oro.datos import ProveedorDukascopy
from oro.datos.base import ProveedorDatos


def _bi5(registros) -> bytes:
    """Empaqueta ``(segundos, open, close, low, high, volumen)`` como Dukascopy."""
    crudo = b"".join(struct.pack(">5if", *r) for r in registros)
    return lzma.compress(crudo, format=lzma.FORMAT_ALONE)


def test_descifra_precios_y_orden_de_campos():
    # Dukascopy sirve (open, close, low, high) —no OHLC— y en puntos.
    p = ProveedorDukascopy()
    df = p._decodificar(_bi5([(3600, 1183700, 1185000, 1183000, 1186000, 42.0)]), 2015, 1)

    assert len(df) == 1
    fila = df.iloc[0]
    assert fila["open"] == pytest.approx(1183.7)
    assert fila["close"] == pytest.approx(1185.0)
    assert fila["low"] == pytest.approx(1183.0)
    assert fila["high"] == pytest.approx(1186.0)
    # El máximo y el mínimo deben serlo de verdad: si el orden estuviera mal,
    # esto fallaría aunque los precios parecieran razonables.
    assert fila["high"] >= max(fila["open"], fila["close"])
    assert fila["low"] <= min(fila["open"], fila["close"])


def test_la_marca_de_tiempo_es_utc_y_relativa_al_inicio_del_mes():
    p = ProveedorDukascopy()
    df = p._decodificar(_bi5([(0, 10, 10, 9, 11, 1.0), (7200, 10, 10, 9, 11, 1.0)]), 2020, 3)
    assert df.index[0] == pd.Timestamp("2020-03-01 00:00", tz="UTC")
    assert df.index[1] == pd.Timestamp("2020-03-01 02:00", tz="UTC")


def test_descarta_el_relleno_de_fin_de_semana():
    p = ProveedorDukascopy()
    df = p._decodificar(_bi5([
        (0, 1200000, 1200000, 1200000, 1200000, 0.0),   # plana: mercado cerrado.
        (3600, 1200000, 1201000, 1199000, 1202000, 5.0),  # real.
        (7200, 0, 0, 0, 0, 0.0),                         # hueco a cero.
    ]), 2021, 6)
    assert len(df) == 1
    assert df.iloc[0]["volume"] == 5.0


def test_cumple_el_contrato_de_proveedor_de_datos():
    p = ProveedorDukascopy()
    df = p._decodificar(_bi5([(i * 3600, 1200000, 1201000, 1199000, 1202000, 1.0)
                              for i in range(5)]), 2022, 2)
    ProveedorDatos.validar(df)          # no debe lanzar.
    assert {"open", "high", "low", "close", "volume", "spread"} <= set(df.columns)


def test_no_se_declara_en_vivo():
    # El runner usa `en_vivo` para fiarse del reloj real. Dukascopy sirve meses
    # cerrados y no da el último tick: marcarlo en vivo dejaría operaciones
    # abiertas creyendo que el mercado sigue donde lo dejó el fichero.
    assert ProveedorDukascopy.en_vivo is False


def test_no_cachea_el_mes_en_curso(tmp_path, monkeypatch):
    # El mes actual todavía está creciendo: guardarlo congelaría un mes a medias.
    p = ProveedorDukascopy(cache=tmp_path)
    hoy = dt.datetime.now(dt.timezone.utc)
    monkeypatch.setattr(p, "_descargar", lambda a, m, intentos=None: p._decodificar(
        _bi5([(0, 1200000, 1201000, 1199000, 1202000, 1.0)]), a, m))

    p._mes(hoy.year, hoy.month)
    assert not (tmp_path / "XAUUSD" / f"{hoy.year}-{hoy.month:02d}.csv").exists()

    p._mes(2015, 1)
    assert (tmp_path / "XAUUSD" / "2015-01.csv").exists()


def test_un_mes_ausente_no_aborta_la_serie(tmp_path, monkeypatch):
    # El servidor es intermitente. Un mes que falle no puede tumbar 19 años.
    p = ProveedorDukascopy(cache=tmp_path)
    def falso(anio, mes, intentos=None):
        if (anio, mes) == (2015, 2):
            return None
        return p._decodificar(_bi5([(0, 1200000, 1201000, 1199000, 1202000, 1.0)]), anio, mes)
    monkeypatch.setattr(p, "_descargar", falso)

    df = p.rango(dt.date(2015, 1, 1), dt.date(2015, 3, 31))
    assert len(df) == 2                              # enero y marzo.
    assert df.index.is_monotonic_increasing


def test_si_no_hay_nada_falla_claro(tmp_path, monkeypatch):
    p = ProveedorDukascopy(cache=tmp_path)
    monkeypatch.setattr(p, "_descargar", lambda a, m, intentos=None: None)
    with pytest.raises(RuntimeError, match="ninguna vela"):
        p.rango(dt.date(2015, 1, 1), dt.date(2015, 2, 28))


def test_no_insiste_doce_veces_con_el_mes_en_curso(tmp_path, monkeypatch):
    # Un 404 del mes actual suele ser "aún no publicado". Insistir con espera
    # creciente gastaría minutos en algo que no existe, y `historico()` empieza
    # justamente por ahí.
    p = ProveedorDukascopy(cache=tmp_path, intentos=12)
    llamadas = {"n": 0}

    def contar(anio, mes, intentos=None):
        llamadas["n"] = intentos
        return None

    monkeypatch.setattr(p, "_descargar", contar)
    hoy = dt.datetime.now(dt.timezone.utc)

    p._mes(hoy.year, hoy.month)
    assert llamadas["n"] == 2, "el mes en curso no debe reintentarse doce veces"

    p._mes(2015, 1)
    assert llamadas["n"] is None, "un mes cerrado sí merece toda la insistencia"
