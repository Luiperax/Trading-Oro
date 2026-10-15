"""Los avisos del v3 en H1 (oro.v3_vivo).

Lo que importa: que en vivo, pasada a pasada, haga exactamente lo mismo que
la medición del histórico (oro.estudio_v3.simular), con los ajustes elegidos
en H30. Si no, lo medido no describiría lo que se opera.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from oro import estudio_v3, v3_vivo
from oro.config import ConfiguracionV3

V3 = ConfiguracionV3()          # los ajustes elegidos en H30


def _serie(n=900, semilla=3):
    rng = np.random.default_rng(semilla)
    idx = pd.date_range("2026-06-01", periods=n, freq="1h", tz="UTC")
    p = 4000 + np.cumsum(rng.normal(0, 4, n))
    o = np.r_[p[0], p[:-1]]
    h = np.maximum(o, p) + np.abs(rng.normal(0, 2, n))
    l = np.minimum(o, p) - np.abs(rng.normal(0, 2, n))
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": p}, index=idx)


class _Espia:
    def __init__(self): self.titulos = []
    def enviar(self, titulo, cuerpo, evento=None, html=None):
        self.titulos.append(titulo); return True


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("ORO_V3_ACTIVA", "1")
    monkeypatch.setenv("ORO_RUTA_V3", str(tmp_path / "v3.json"))
    monkeypatch.setenv("ORO_RUTA_V3_REGISTRO", str(tmp_path / "v3.jsonl"))
    monkeypatch.setattr(v3_vivo, "_FED", {"v": 0.04})
    espia = _Espia()
    monkeypatch.setattr("oro.cli._construir_notificador", lambda: espia)
    return espia, tmp_path


def _primera_senal(serie, desde=400):
    d = estudio_v3.senales(estudio_v3.indicadores(serie), min_score=V3.min_score,
                              h4_obligatorio=V3.h4_obligatorio)
    return d[(d["senal"] != 0) & (np.arange(len(d)) >= desde)].index[0], d


def test_la_senal_llega_una_vez_con_sus_niveles(entorno):
    espia, tmp = entorno
    serie = _serie()
    t, d = _primera_senal(serie)
    ahora = t + pd.Timedelta(hours=1, minutes=3)
    v3_vivo.ejecutar(ahora=ahora, serie=serie)
    v3_vivo.ejecutar(ahora=ahora + pd.Timedelta(minutes=3), serie=serie)
    assert len(espia.titulos) == 1 and "v3 ·" in espia.titulos[0]
    op = json.loads((tmp / "v3.json").read_text())["abierta"]
    s, c, atr = op["dir"], d.loc[t, "close"], d.loc[t, "atr"]
    assert op["stop"] == pytest.approx(c - s * 3 * atr, abs=0.01)
    assert op["tp1"] == pytest.approx(c + s * 3 * atr, abs=0.01)
    assert op["tp2"] == pytest.approx(c + s * 5 * atr, abs=0.01)


def test_una_senal_que_llega_tarde_no_se_manda(entorno):
    espia, tmp = entorno
    serie = _serie()
    t, _ = _primera_senal(serie)
    v3_vivo.ejecutar(ahora=t + pd.Timedelta(hours=3), serie=serie[serie.index <= t])
    assert espia.titulos == []
    assert json.loads((tmp / "v3.json").read_text()).get("abierta") is None


def test_en_papel_lo_dice(entorno, monkeypatch):
    espia, tmp = entorno
    monkeypatch.setenv("ORO_V3_PAPEL", "1")
    serie = _serie()
    t, _ = _primera_senal(serie)
    v3_vivo.ejecutar(ahora=t + pd.Timedelta(hours=1, minutes=3), serie=serie)
    assert espia.titulos[0].startswith("📝 [papel]")


def test_en_vivo_hace_lo_mismo_que_la_medicion(entorno):
    """Pasada a pasada, hora a hora, frente a estudio_v3.simular."""
    espia, tmp = entorno
    serie = _serie(1100, semilla=11)
    inicio = serie.index[450]
    for t in serie.index[450:]:
        v3_vivo.ejecutar(ahora=t + pd.Timedelta(hours=1, minutes=3), serie=serie)
    vivo = [json.loads(l) for l in (tmp / "v3.jsonl").read_text().splitlines()]
    d = estudio_v3.senales(estudio_v3.indicadores(serie), min_score=V3.min_score,
                              h4_obligatorio=V3.h4_obligatorio)
    medido = estudio_v3.simular(serie, d, inicio, serie.index[-1], pd.Series(dtype=float),
                                vela=pd.Timedelta(hours=1), sl_atr=V3.sl_atr,
                                tp1_atr=V3.tp1_atr, tp2_atr=V3.tp2_atr)
    medido = [m for m in medido if pd.Timestamp(m["salida"]) < serie.index[-1]]
    assert len(vivo) >= 3
    assert [(v["t"], v["r_bruto"]) for v in vivo] == \
           [(m["t"], pytest.approx(m["r_bruto"], abs=1e-3)) for m in medido[:len(vivo)]]
    # Y cada operación tuvo su aviso de entrada y el de su final.
    assert sum("v3 ·" in x for x in espia.titulos) >= len(vivo)
    assert sum("operación terminada" in x for x in espia.titulos) == len(vivo)


def test_tras_la_sesion_con_el_mercado_cerrado_dice_entrar_al_abrir():
    """La vela de 20:00-21:00 UTC cierra, en verano, con el oro en su parada
    diaria (y el viernes, en el fin de semana): la medición entra al abrir."""
    U = lambda x: pd.Timestamp(x, tz="UTC")
    assert v3_vivo._apertura(U("2026-07-08 21:00")) == U("2026-07-08 22:00")   # miércoles
    assert v3_vivo._apertura(U("2026-07-10 21:00")) == U("2026-07-12 22:00")   # viernes
    assert v3_vivo._apertura(U("2026-12-09 21:00")) == U("2026-12-09 21:00")   # invierno: abierto
    op = {"t": "2026-07-10T20:00:00+00:00", "dir": 1, "ref": 4000.0, "stop": 3970.0,
          "tp1": 4030.0, "tp2": 4050.0, "puntos": 4, "abre": "2026-07-12T22:00:00+00:00"}
    titulo, cuerpo = v3_vivo.correo_entrada(op)
    assert "al abrir" in titulo and "13-Jul 00:00" in titulo
    assert "mercado está cerrado" in cuerpo
    titulo, cuerpo = v3_vivo.correo_entrada({k: v for k, v in op.items() if k != "abre"})
    assert "ahora" in titulo and "entra a mercado en COMPRA ya" in cuerpo


def test_si_abre_mas_alla_del_stop_no_hay_operacion():
    idx = pd.date_range("2026-07-10 20:00", periods=3, freq="1h", tz="UTC")
    serie = pd.DataFrame({"open": [4000, 3960, 3950], "high": [4005, 3965, 3960],
                          "low": [3995, 3950, 3940], "close": [4000, 3955, 3950]}, index=idx)
    op = {"t": idx[0].isoformat(), "dir": 1, "stop": 3970.0, "tp1": 4030.0, "tp2": 4050.0}
    sucesos = v3_vivo.seguir_operacion(op, serie)
    assert [x["tipo"] for x in sucesos] == ["entrada", "anulada"]
    assert v3_vivo._resultado(op, sucesos) is None
    titulo, _ = v3_vivo.correo_suceso(op, sucesos[-1], None)
    assert "NO entres" in titulo


def test_si_falta_una_hora_reciente_espera_y_no_pierde_su_senal(entorno):
    """Dukascopy da a veces 503 en una hora y sí en la siguiente: la señal de
    la hora que faltaba no puede perderse por llegar después."""
    from oro.datos.dukascopy_vivo import ProveedorDukascopyVivo as P

    espia, tmp = entorno
    serie = _serie(1100, semilla=11)
    d = estudio_v3.senales(estudio_v3.indicadores(serie), min_score=V3.min_score,
                           h4_obligatorio=V3.h4_obligatorio)
    abiertas = [t for t in d.index[450:] if d.at[t, "senal"] != 0
                and not P.mercado_cerrado(t.to_pydatetime())]
    t = abiertas[0]
    h = pd.Timedelta(hours=1)
    # Pasada anterior: revisado hasta la hora de antes.
    v3_vivo.ejecutar(ahora=t + pd.Timedelta(minutes=3), serie=serie[serie.index < t])
    # La hora t no llega, la siguiente sí.
    v3_vivo.ejecutar(ahora=t + 2 * h + pd.Timedelta(minutes=3),
                     serie=serie[(serie.index <= t + h) & (serie.index != t)])
    assert espia.titulos == []
    assert json.loads((tmp / "v3.json").read_text())["procesada"] == (t - h).isoformat()
    # Llega a los pocos minutos: se manda la señal de t.
    v3_vivo.ejecutar(ahora=t + 2 * h + pd.Timedelta(minutes=9), serie=serie[serie.index <= t + h])
    assert len(espia.titulos) == 1 and "v3 ·" in espia.titulos[0]
    estado = json.loads((tmp / "v3.json").read_text())
    assert estado["abierta"]["t"] == t.isoformat()
    assert estado["procesada"] == (t + h).isoformat()


def test_las_confirmaciones_del_correo_son_las_de_la_senal():
    """El 15-oct el correo dijo «1 de 6» en una señal que exige 3: los bool de
    numpy se sumaban como un «o» lógico."""
    serie = _serie(1100, semilla=11)
    d = estudio_v3.senales(estudio_v3.indicadores(serie), min_score=V3.min_score,
                           h4_obligatorio=V3.h4_obligatorio)
    rsi, mh, e21, e50, c = d["rsi"], d["macdh"], d["ema21"], d["ema50"], d["close"]
    largo = ((c > d["ema50h4"]).astype(int) + (e21 > e50).astype(int)
             + ((rsi > rsi.shift(1)) & (rsi.shift(1) > rsi.shift(2)) & (rsi < 60)).astype(int)
             + ((mh > mh.shift(1)) & (mh.shift(1) > mh.shift(2))).astype(int)
             + ((c > e21 * 0.994) & (c < e21 * 1.008) & (e21 > e50)).astype(int)
             + (d["adx"] > 18).astype(int))
    corto = ((c < d["ema50h4"]).astype(int) + (e21 < e50).astype(int)
             + ((rsi < rsi.shift(1)) & (rsi.shift(1) < rsi.shift(2)) & (rsi > 40)).astype(int)
             + ((mh < mh.shift(1)) & (mh.shift(1) < mh.shift(2))).astype(int)
             + ((c < e21 * 1.006) & (c > e21 * 0.992) & (e21 < e50)).astype(int)
             + (d["adx"] > 18).astype(int))
    senales = d[d["senal"] != 0]
    assert len(senales) >= 5
    for t, fila in senales.iterrows():
        s = int(fila["senal"])
        esperado = int((largo if s > 0 else corto)[t])
        assert v3_vivo._puntos(d, s, t) == esperado >= V3.min_score
