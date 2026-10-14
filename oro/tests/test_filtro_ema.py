"""El filtro de la EMA 200 horaria del plan de ruptura (H19).

La venta solo se deja si a las 8:00 ET el precio está por debajo de su EMA 200
horaria; el día de empleo va solo la orden a favor, y se anula si el otro lado
del rango se rompe antes. Medido: ver ConfiguracionRuptura.filtro_ema200_h1.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from oro.config import ConfiguracionSistema
from oro.dominio import Direccion
from oro.seguimiento import EstadoPlan, seguir
from oro.sesiones import construir_plan
from oro.tests.test_solo_ventas import ASIA_SUBE, DIA, LONDRES, _a_las, _con_sesion, _marco

# El cierre de la vela de 7:00 ET de LONDRES es 4008.5.


def _cfg(**k):
    cfg = ConfiguracionSistema()
    cfg.riesgo.coste_operacion = 0.30
    cfg.ruptura.filtro_ema200_h1 = True
    for a, b in k.items():
        setattr(cfg.ruptura, a, b)
    return cfg


def _res(ema, cfg=None):
    return construir_plan(_marco(DIA, {**ASIA_SUBE, **LONDRES}), cfg or _cfg(),
                          ahora=_a_las(8), ema200=ema)


def test_precio_por_debajo_de_la_ema_va_la_venta():
    r = _res(4100.0)
    assert r.hay_plan and r.plan.solo_ventas and r.plan.ema200 == 4100.0
    assert [o.direccion for o in r.plan.ordenes] == [Direccion.VENTA]


def test_precio_por_encima_no_hay_plan_y_se_dice_por_que():
    r = _res(3900.0)
    assert not r.hay_plan
    assert r.aviso_sin_plan and "por encima de su media de 200 horas" in r.aviso_sin_plan


def test_sin_ema_no_se_manda_nada():
    r = _res(None)
    assert not r.hay_plan and not r.aviso_sin_plan


def test_sin_filtro_la_ema_no_cambia_nada():
    r = _res(3900.0, _cfg(filtro_ema200_h1=False))
    assert r.hay_plan and r.plan.solo_ventas and r.plan.ema200 is None


def test_dia_de_empleo_por_encima_solo_la_compra(monkeypatch):
    monkeypatch.setattr("oro.calendario.es_dia_de_empleo", lambda d: True)
    r = _res(3900.0)
    assert r.hay_plan and r.plan.solo_compras and not r.plan.solo_ventas
    assert r.plan.dia_de_empleo
    assert [o.direccion for o in r.plan.ordenes] == [Direccion.COMPRA]


def test_dia_de_empleo_por_debajo_solo_la_venta(monkeypatch):
    monkeypatch.setattr("oro.calendario.es_dia_de_empleo", lambda d: True)
    r = _res(4100.0)
    assert r.hay_plan and r.plan.solo_ventas and not r.plan.solo_compras


@pytest.fixture()
def plan_compra(monkeypatch):
    monkeypatch.setattr("oro.calendario.es_dia_de_empleo", lambda d: True)
    return _res(3900.0).plan


def test_compra_sola_se_anula_si_rompe_antes_por_abajo(plan_compra):
    s = seguir(plan_compra, _con_sesion({8: (4010, 3990)}), ahora=_a_las(9, 3))
    assert s.estado is EstadoPlan.ANULADO
    assert "CANCELA la orden de compra" in s.avisos[0].titulo
    assert "ha bajado de 3998.00" in s.avisos[0].destacado


def test_compra_sola_se_dispara_al_romper_por_arriba(plan_compra):
    s = seguir(plan_compra, _con_sesion({8: (4030, 4015)}), ahora=_a_las(9, 3))
    assert s.estado is EstadoPlan.ABIERTA and s.direccion is Direccion.COMPRA


def test_correo_de_la_compra_sola(plan_compra, monkeypatch):
    from oro.notificaciones.plan import mensaje_de_plan, mensaje_html_de_plan
    monkeypatch.setenv("ORO_RUPTURA_SOLO_PAPEL", "0")
    for t in (mensaje_de_plan(plan_compra), mensaje_html_de_plan(plan_compra)):
        assert "BUY STOP" in t and "SELL STOP" not in t
        assert "baja de 3998.00" in t
        assert "media de 200 horas" in t


def test_asunto_de_la_compra_sola(plan_compra, monkeypatch):
    from oro.notificaciones.base import Notificador

    class Espia(Notificador):
        def enviar(self, titulo, cuerpo, evento=None, html=None):
            self.titulo = titulo; return True

    monkeypatch.setenv("ORO_RUPTURA_SOLO_PAPEL", "0")
    e = Espia(); e.notificar_plan(plan_compra)
    assert "deja 1 orden: compra 4024.00 (anula si baja de 3998.00)" in e.titulo
    assert "DÍA DE EMPLEO" in e.titulo


def test_el_correo_con_filtro_da_las_cifras_de_verdad(monkeypatch):
    from oro.notificaciones.plan import mensaje_de_plan
    monkeypatch.setenv("ORO_RUPTURA_SOLO_PAPEL", "0")
    t = mensaje_de_plan(_res(4100.0).plan)
    assert "+0,012 R por operación" in t and "NO es una ventaja demostrada" in t


# ---- La EMA horaria guardada ----

def _velas(desde, n, precio=100.0):
    idx = pd.date_range(desde, periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({"close": [precio + i for i in range(n)]}, index=idx)


def test_la_ema_avanza_y_guarda(tmp_path, monkeypatch):
    from oro import ema_horaria as e
    monkeypatch.setenv("ORO_RUTA_EMA", str(tmp_path / "ema.json"))
    base = e.desde_cierres(_velas("2026-10-05 00:00", 600)["close"])
    nuevas = _velas("2026-10-05 00:00", 610)
    st = e.avanzar(nuevas, base)
    assert st["hasta"] == nuevas.index[-1].isoformat()
    completo = nuevas["close"].ewm(span=200, adjust=False).mean().iloc[-1]
    assert st["ema"] == pytest.approx(completo, abs=1e-3)
    assert json.loads((tmp_path / "ema.json").read_text())["hasta"] == st["hasta"]


def test_la_ema_no_enlaza_si_falta_una_hora_de_mercado(tmp_path, monkeypatch):
    from oro import ema_horaria as e
    monkeypatch.setenv("ORO_RUTA_EMA", str(tmp_path / "ema.json"))
    base = e.desde_cierres(_velas("2026-10-05 00:00", 600)["close"])   # martes…
    hueco = _velas(pd.Timestamp(base["hasta"]) + pd.Timedelta(hours=5), 3)
    assert e.avanzar(hueco, base) is None


def test_el_fin_de_semana_no_es_un_hueco(tmp_path, monkeypatch):
    from oro import ema_horaria as e
    monkeypatch.setenv("ORO_RUTA_EMA", str(tmp_path / "ema.json"))
    # Hasta el viernes 9-oct a las 20:00 UTC; lo siguiente, el domingo a las 22:00.
    viernes = _velas("2026-09-18 21:00", 0)
    serie = _velas("2026-09-14 00:00", 24 * 5 - 3)["close"]       # lun 00:00 → vie 20:00
    base = e.desde_cierres(serie)
    assert base["hasta"].startswith("2026-09-18T20:00")
    domingo = _velas("2026-09-20 22:00", 3)
    assert e.avanzar(domingo, base) is not None


# ---- De punta a punta: plan_sesion con el filtro encendido ----

class _Espia:
    def __init__(self): self.planes, self.avisos = [], []
    def notificar_plan(self, plan): self.planes.append(plan); return True
    def enviar(self, titulo, cuerpo, evento=None, html=None):
        self.avisos.append((titulo, cuerpo)); return True


@pytest.fixture()
def vivo(tmp_path, monkeypatch):
    from oro import plan_sesion
    monkeypatch.setenv("ORO_RUPTURA_FILTRO_EMA200", "1")
    monkeypatch.setenv("ORO_PLAN_ESTADO", str(tmp_path / "plan.json"))
    monkeypatch.setenv("ORO_RUTA_EMA", str(tmp_path / "ema.json"))
    df = _marco(DIA, {**ASIA_SUBE, **LONDRES})
    prov = type("P", (), {"historico": lambda s, n: df})()
    monkeypatch.setattr(plan_sesion, "_proveedor", lambda sintetico: prov)
    espia = _Espia()
    monkeypatch.setattr(plan_sesion, "_construir_notificador", lambda: espia)

    def estado(ema):
        hasta = (df.index[0] - pd.Timedelta(hours=1)).isoformat()
        (tmp_path / "ema.json").write_text(json.dumps({"hasta": hasta, "ema": ema}))
    return plan_sesion, espia, estado, tmp_path


def test_con_el_precio_bajo_la_ema_se_manda_la_venta(vivo):
    plan_sesion, espia, estado, tmp = vivo
    estado(5000.0)
    assert plan_sesion.ejecutar(ahora=_a_las(8)) == 0
    assert len(espia.planes) == 1 and espia.planes[0].solo_ventas
    assert espia.planes[0].ema200 > 4008.5
    guardado = json.loads((tmp / "plan.json").read_text())
    assert guardado["plan"]["ema200"] == espia.planes[0].ema200


def test_con_el_precio_sobre_la_ema_llega_el_aviso_de_que_no_hay_plan(vivo):
    plan_sesion, espia, estado, tmp = vivo
    estado(3000.0)
    assert plan_sesion.ejecutar(ahora=_a_las(8)) == 0
    assert espia.planes == []
    assert len(espia.avisos) == 1 and "hoy no hay plan" in espia.avisos[0][0]
    assert json.loads((tmp / "plan.json").read_text())["ultimo_plan"] == DIA
    # Y no se repite en la pasada siguiente.
    plan_sesion.ejecutar(ahora=_a_las(8, 3))
    assert len(espia.avisos) == 1
