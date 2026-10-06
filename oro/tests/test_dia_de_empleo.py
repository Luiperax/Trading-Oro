"""El día del dato de empleo de EE. UU. van las dos órdenes.

POR QUÉ, MEDIDO CON EL RELLENO REAL (tick a tick)
-------------------------------------------------
El informe sale a las 8:30 de Nueva York, dentro de la ventana de disparo. Ese
día la rotura es el mercado reaccionando al dato, y sigue en la dirección en
que sale, en las DOS:

    venta    83  +0.5646  t=2.83   mitades +0.533 / +0.594
    compra   76  +0.7947  t=4.01   mitades +0.827 / +0.764
    las dos 159  +0.6746  t=4.79   19 años positivos de 21

Fue la hipótesis 11 de 11 declaradas antes de mirar; Bonferroni pedía 2,84.
"""

from __future__ import annotations

import datetime as dt
from datetime import timezone
from zoneinfo import ZoneInfo

import pytest

from oro.calendario import dia_de_empleo, es_dia_de_empleo
from oro.config import ConfiguracionSistema
from oro.dominio import Direccion

NY = ZoneInfo("America/New_York")

# Publicaciones REALES del informe de empleo (mes de referencia → publicación).
REALES = {(2023, 8): "2023-09-01", (2023, 9): "2023-10-06", (2023, 12): "2024-01-05",
          (2024, 6): "2024-07-05", (2024, 8): "2024-09-06", (2022, 12): "2023-01-06",
          (2019, 12): "2020-01-10", (2020, 2): "2020-03-06", (2021, 4): "2021-05-07",
          (2014, 12): "2015-01-09",
          # Enero el día 4: NO se retrasa (la primera versión fallaba estas tres).
          (2007, 12): "2008-01-04", (2012, 12): "2013-01-04", (2018, 12): "2019-01-04",
          # Festivo del 4 de julio: se adelanta al jueves.
          (2008, 6): "2008-07-03", (2014, 6): "2014-07-03", (2020, 6): "2020-07-02",
          (2025, 6): "2025-07-03"}


@pytest.mark.parametrize("ref,publicacion", REALES.items())
def test_la_regla_del_bls_acierta_las_publicaciones_reales(ref, publicacion):
    """Sin la excepción de enero fallaban 2020 y 2015: el BLS retrasa una
    semana el informe cuando la regla cae el 1-4 de enero."""
    assert dia_de_empleo(*ref).isoformat() == publicacion


def test_es_dia_de_empleo_reconoce_el_dia_y_solo_ese():
    assert es_dia_de_empleo(dt.date(2024, 9, 6))
    assert not es_dia_de_empleo(dt.date(2024, 9, 5))
    assert not es_dia_de_empleo(dt.date(2024, 9, 13))
    # La excepción de enero en los dos sentidos.
    assert es_dia_de_empleo(dt.date(2020, 1, 10))
    assert not es_dia_de_empleo(dt.date(2020, 1, 3))


def test_sale_en_viernes_salvo_el_festivo_de_julio():
    """La regla da viernes, salvo el jueves del 4 de julio."""
    for anio in range(2006, 2027):
        for mes in range(1, 13):
            d = dia_de_empleo(anio, mes)
            assert d.weekday() == 4 or (d.month == 7 and d.weekday() == 3)


def test_con_clave_de_fred_manda_su_calendario(monkeypatch):
    """Los cierres del Gobierno (2013, 2025) solo los sabe FRED. Con su
    calendario, el 20-nov-2025 es día de empleo aunque la regla diga que no."""
    from oro import calendario

    monkeypatch.setenv("ORO_FRED_CLAVE", "falsa")
    monkeypatch.setattr(calendario, "fechas_fred",
                        lambda clave: {dt.date(2025, 11, 20), dt.date(2026, 12, 4)})
    assert es_dia_de_empleo(dt.date(2025, 11, 20))
    assert not es_dia_de_empleo(dt.date(2025, 11, 7))


def test_si_fred_no_responde_vuelve_a_la_regla(monkeypatch):
    from oro import calendario

    monkeypatch.setenv("ORO_FRED_CLAVE", "falsa")
    monkeypatch.setattr(calendario, "fechas_fred", lambda clave: set())
    assert es_dia_de_empleo(dt.date(2024, 9, 6))


def test_ninguna_clave_de_fred_pegada_en_el_codigo():
    """La clave es un secreto de GitHub (ORO_FRED_CLAVE). El repositorio es
    público: una clave escrita en un fichero la tendría cualquiera."""
    import pathlib
    import re
    import subprocess

    raiz = pathlib.Path(__file__).resolve().parents[2]
    ficheros = subprocess.run(["git", "ls-files", "*.py", "*.yml", "*.md", "*.json"],
                              cwd=raiz, capture_output=True, text=True).stdout.split()
    patron = re.compile(r"api_key[\"'=:\s]+[0-9a-f]{32}")
    for f in ficheros:
        texto = (raiz / f).read_text(encoding="utf-8", errors="ignore")
        assert not patron.search(texto), f"parece una clave de FRED en {f}"


def _plan(fecha: str, **ruptura):
    from oro.sesiones import construir_plan
    from oro.tests.test_ruptura_sesion import ASIA_SUBE, LONDRES, _marco

    cfg = ConfiguracionSistema()
    for k, v in ruptura.items():
        setattr(cfg.ruptura, k, v)
    y, m, d = (int(x) for x in fecha.split("-"))
    ahora = dt.datetime(y, m, d, 8, tzinfo=NY).astimezone(timezone.utc)
    return construir_plan(_marco(fecha, {**ASIA_SUBE, **LONDRES}), cfg, ahora=ahora).plan


def test_el_dia_de_empleo_van_las_dos_ordenes():
    plan = _plan("2024-09-06")
    assert plan.dia_de_empleo is True
    assert plan.solo_ventas is False
    assert [o.direccion for o in plan.ordenes] == [Direccion.COMPRA, Direccion.VENTA]


def test_el_resto_de_dias_sigue_siendo_solo_venta():
    plan = _plan("2024-09-05")
    assert plan.dia_de_empleo is False
    assert plan.solo_ventas is True
    assert [o.direccion for o in plan.ordenes] == [Direccion.VENTA]


def test_el_interruptor_lo_apaga():
    plan = _plan("2024-09-06", dos_ordenes_en_dia_de_empleo=False)
    assert plan.dia_de_empleo is False and plan.solo_ventas is True


def test_el_dia_de_empleo_no_lleva_estrella():
    """El sesgo asiático se midió para la estrategia vieja; el día de empleo
    el que manda es el dato, y no hay medición de qué lado es el bueno."""
    plan = _plan("2024-09-06")
    assert plan.favorita is None


def test_el_dia_de_empleo_la_compra_no_se_anula():
    """Si el seguimiento tratara el día de empleo como uno normal, anularía la
    compra al romper arriba y perdería justo la mitad que se añadió."""
    from oro.seguimiento import EstadoPlan, seguir
    from oro.tests.test_ruptura_sesion import ASIA_SUBE, LONDRES, _marco

    plan = _plan("2024-09-06")
    df = _marco("2024-09-06", {**ASIA_SUBE, **LONDRES, 8: (4035, 4020), 9: (4060, 4030)})
    fin = dt.datetime(2024, 9, 6, 17, tzinfo=NY).astimezone(timezone.utc)
    s = seguir(plan, df, ahora=fin)
    assert s.estado is not EstadoPlan.ANULADO
    assert s.direccion is Direccion.COMPRA


def test_el_correo_del_dia_de_empleo_avisa_del_salto_y_pide_oco():
    from oro.notificaciones.plan import mensaje_de_plan, mensaje_html_de_plan

    plan = _plan("2024-09-06")
    for t in (mensaje_de_plan(plan), mensaje_html_de_plan(plan)):
        assert "BUY STOP" in t and "SELL STOP" in t
        assert "empleo" in t
        assert "OCO" in t                      # a las 8:30 no da tiempo a mano.
        assert "34,55 $" in t                  # el peor deslizamiento medido.
        assert "LA MEJOR SI SALTA" not in t


def test_el_asunto_dice_que_es_dia_de_empleo():
    from oro.notificaciones.base import Evento, Notificador

    plan = _plan("2024-09-06")
    capturado = {}

    class Espia(Notificador):
        def enviar(self, titulo, cuerpo, evento=Evento.NUEVA_SENAL, html=None):
            capturado["titulo"] = titulo
            return True

    Espia().notificar_plan(plan)
    assert "EMPLEO" in capturado["titulo"] and "2 órdenes" in capturado["titulo"]


def test_el_dia_de_empleo_cobra_su_deslizamiento_medido():
    """Cobrarle el de un día normal (0,25 $) en vez del medido (1,31 $)
    inflaba su resultado de +0,67 a +0,75 R por operación."""
    from oro.seguimiento import deslizamiento_de

    cfg = ConfiguracionSistema()
    assert deslizamiento_de(_plan("2024-09-06"), cfg) == pytest.approx(1.30)
    assert deslizamiento_de(_plan("2024-09-05"), cfg) == pytest.approx(0.25)


def test_el_campo_viaja_por_json():
    """Si se perdiera al guardar el plan, el seguimiento de las 15:00 trataría
    el día de empleo como uno normal y anularía la compra."""
    from oro.seguir_plan import _rehidratar, serializar
    from oro.sesiones import PlanRuptura

    plan = _plan("2024-09-06")
    vuelta = PlanRuptura(**_rehidratar(serializar(plan)))
    assert vuelta.dia_de_empleo is True and vuelta.solo_ventas is False


@pytest.fixture(autouse=True)
def _correo_de_operar(monkeypatch):
    """Estas pruebas cubren el correo de OPERAR. El de «solo papel», que es el
    que va puesto desde el 6-oct-2026, está en test_solo_papel.py."""
    monkeypatch.setenv("ORO_RUPTURA_SOLO_PAPEL", "0")
