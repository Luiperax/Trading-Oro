"""El árbitro de fuera: que los precios sean oro al contado y no otra cosa.

ESTA PRUEBA EXISTE POR UN FALLO REAL
------------------------------------
Durante semanas el sistema calculó los niveles sobre GC=F —el futuro de COMEX—
mientras el correo decía «busca XAU/USD (oro)», que es el contado. 43 $ de
diferencia, y nadie se enteró porque el sistema solo veía un feed.

El criterio: el LBMA Gold Price (subasta de las 10:30 de Londres) tiene que caer
dentro de la vela horaria que contiene la subasta. Medido: con el contado, 32 de
32 días; con el futuro, 0 de 16.

Y un fallo propio: la primera versión pedía 5 días de un marco que en vivo solo
tiene 48 horas. No se habría activado nunca.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from oro.referencia import comprobar_fuente, hora_de_la_subasta


FIXES = {dt.date(2026, 9, 28): 4144.40, dt.date(2026, 9, 30): 4188.75,
         dt.date(2026, 10, 1): 4159.85, dt.date(2026, 10, 2): 4186.60}


@pytest.fixture()
def fixes(monkeypatch):
    monkeypatch.setattr("oro.referencia.serie_fix", lambda **kw: FIXES)


class _PorHora:
    """Proveedor que contesta vela a vela, como Dukascopy en vivo."""

    def __init__(self, desplazamiento: float, ancho: float = 12.0):
        self.d, self.ancho, self.peticiones = desplazamiento, ancho, 0

    def vela_de(self, hora):
        self.peticiones += 1
        fix = FIXES.get(hora.date())
        if fix is None:
            return None
        centro = fix + self.d
        return {"low": centro - self.ancho / 2, "high": centro + self.ancho / 2}


class _Marco:
    """Proveedor que solo sabe devolver un marco, como Yahoo."""

    def __init__(self, desplazamiento: float):
        idx, filas = [], []
        for dia, fix in FIXES.items():
            h = hora_de_la_subasta(dia)
            idx.append(h)
            c = fix + desplazamiento
            filas.append({"open": c, "high": c + 6, "low": c - 6, "close": c, "volume": 1})
        self.df = pd.DataFrame(filas, index=pd.DatetimeIndex(idx))

    def historico(self, n):
        return self.df


def test_el_contado_pasa(fixes):
    vale, msg = comprobar_fuente(_PorHora(desplazamiento=+2.0))
    assert vale, msg
    assert "contado" in msg


def test_el_futuro_de_comex_se_detecta(fixes):
    """+43 $ es la prima del contrato. Esto es lo que había que cazar."""
    vale, msg = comprobar_fuente(_PorHora(desplazamiento=+43.0))
    assert not vale
    assert "NO ES ORO AL CONTADO" in msg
    assert "GC=F" in msg and "ORO_FUENTE_VIVO" in msg


def test_funciona_tambien_con_un_proveedor_de_marco(fixes):
    """Yahoo no sabe dar una vela suelta; se le pide el marco una sola vez."""
    assert comprobar_fuente(_Marco(+1.0))[0] is True
    assert comprobar_fuente(_Marco(+43.0))[0] is False


def test_con_un_solo_dia_ya_decide(fixes):
    """El criterio de la vela separa con un solo día (32/32 frente a 0/16).
    Es lo que permite que funcione en vivo, donde no hay cinco días a mano."""
    vale, _ = comprobar_fuente(_PorHora(+43.0), dias=1)
    assert vale is False


def test_pide_pocas_velas(fixes):
    """Cada vela de Dukascopy es una petición. El árbitro no puede costar más
    que el propio plan."""
    p = _PorHora(+2.0)
    comprobar_fuente(p, dias=3)
    assert p.peticiones <= 9


def test_sin_referencia_se_sigue_adelante(monkeypatch):
    """Una web caída no puede dejar al sistema sin mandar el plan."""
    monkeypatch.setattr("oro.referencia.serie_fix", lambda **kw: {})
    vale, msg = comprobar_fuente(_PorHora(+43.0))
    assert vale and "sin árbitro" in msg


def test_sin_velas_a_esa_hora_no_se_pronuncia(fixes):
    class Vacio:
        def vela_de(self, hora):
            return None
    vale, msg = comprobar_fuente(Vacio())
    assert vale and "Sin árbitro" in msg


def test_la_hora_de_la_subasta_sigue_el_cambio_de_hora_britanico():
    """10:30 de Londres son las 09:30 UTC en verano y las 10:30 en invierno."""
    assert hora_de_la_subasta(dt.date(2026, 7, 15)).hour == 9
    assert hora_de_la_subasta(dt.date(2026, 12, 15)).hour == 10


def test_el_plan_no_se_manda_si_el_arbitro_dice_que_no():
    """Un día sin plan es mucho mejor que un plan con niveles que en el bróker
    no existen: esas órdenes se ejecutan al instante en vez de esperar."""
    import inspect

    from oro import plan_sesion

    fuente = inspect.getsource(plan_sesion.ejecutar)
    i = fuente.find("comprobar_fuente")
    j = fuente.find("notificar_plan")
    assert 0 < i < j, "el árbitro tiene que correr ANTES de mandar el correo"
