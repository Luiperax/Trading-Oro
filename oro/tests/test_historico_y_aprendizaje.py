"""La reconstrucción del histórico y la puerta de promoción del aprendizaje.

LO QUE ESTAS PRUEBAS PROTEGEN
-----------------------------
La auditoría del sistema encontró que las cifras documentadas se habían medido
con una configuración distinta de la que se enviaba al correo. El bruto
coincidía; el neto, no. Eso solo puede pasar cuando la investigación tiene su
propia copia de la estrategia.

:mod:`oro.historico` existe para que no vuelva a pasar: llama a
`construir_plan` y `seguir`, las de producción. Estas pruebas comprueban las
dos cosas que lo hacen fiable —que no mira el futuro y que usa esas funciones—
y las tres condiciones de la puerta de promoción, que son las tres lecciones
que costaron caro.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from oro.aprender import ANIO_CORTE, _cerradas, _leer_jsonl, vigilar
from oro.config import ConfiguracionSistema
from oro.historico import _por_dia_de_sesion, reconstruir
from oro.tests.test_ruptura_sesion import ASIA_SUBE, LONDRES, _marco

NY = ZoneInfo("America/New_York")


def _dia(fecha: str, sesion: dict):
    return _marco(fecha, {**ASIA_SUBE, **LONDRES, **sesion})


def test_parte_el_historico_por_dias_de_sesion_sin_perder_velas():
    import pandas as pd

    df = pd.concat([_dia("2026-07-15", {8: (4010, 3990)}),
                    _dia("2026-07-16", {8: (4035, 4020)})]).sort_index()
    trozos = list(_por_dia_de_sesion(df))
    assert len(trozos) >= 2
    assert sum(len(t) for _, t in trozos) == len(df)
    # Y en orden, que es lo que permite recorrerlos una sola vez.
    dias = [d for d, _ in trozos]
    assert dias == sorted(dias)


def test_reconstruye_una_operacion_con_el_formato_del_registro_en_vivo():
    """Las fichas del histórico y las de en vivo tienen que ser el MISMO objeto.
    Si no, el aprendizaje tendría que traducir, y traducir es donde se cuelan
    los errores silenciosos."""
    cfg = ConfiguracionSistema()
    cfg.riesgo.coste_operacion = 0.30
    fichas = reconstruir(_dia("2026-07-15", {8: (4010, 3990), 9: (3995, 3950)}), cfg)
    assert len(fichas) == 1
    f = fichas[0]
    assert f["origen"] == "historico"
    assert f["estrategia"] == "ruptura_sesion"
    assert f["direccion"] == "venta"
    assert f["r_neto"] is not None
    # Las claves del registro en vivo, una por una.
    for clave in ("dia", "estado", "entrada", "salida", "motivo_cierre",
                  "r_bruto", "r_neto", "coste_r", "amplitud",
                  "rango_alto", "rango_bajo", "sesgo_cuerpo"):
        assert clave in f, f"falta {clave}"


def test_reconstruir_no_mira_el_futuro():
    """El plan se construye con las velas de ANTES de que abra la ventana.

    Si se le pasara el día entero, la guarda de «el rango ya se ha roto» vería
    la sesión completa y no habría plan ningún día. Que salga plan es la prueba
    de que solo ve la mañana.
    """
    cfg = ConfiguracionSistema()
    # Un día que rompe con fuerza por los dos lados después de las 8:00.
    fichas = reconstruir(_dia("2026-07-15", {8: (4010, 3990), 9: (4100, 3900)}), cfg)
    assert len(fichas) == 1, "la guarda de 'ya roto' se está comiendo el día"
    assert fichas[0]["rango_alto"] == pytest.approx(4024.0)
    assert fichas[0]["rango_bajo"] == pytest.approx(3998.0)


def test_reconstruir_usa_la_configuracion_y_no_una_copia_de_la_estrategia():
    """Cambiando la configuración tiene que cambiar el resultado. Es lo que
    demuestra que llama a `construir_plan` y no a una reimplementación."""
    df = _dia("2026-07-15", {8: (4010, 3990), 9: (3995, 3950)})
    cfg = ConfiguracionSistema()
    assert len(reconstruir(df, cfg)) == 1

    apagada = ConfiguracionSistema()
    apagada.ruptura.activa = False
    assert reconstruir(df, apagada) == []

    # Y con la ventana del rango recortada, el rango medido es otro: el mínimo
    # de Londres (3998) está en la vela de las 5:00 ET, así que cortando en 5
    # desaparece.
    movida = ConfiguracionSistema()
    movida.ruptura.rango_hasta_et = 5
    movida.ruptura.velas_minimas = 2
    f = reconstruir(df, movida)
    assert f and f[0]["rango_bajo"] == pytest.approx(4004.0)


def test_los_dias_anulados_entran_en_el_historico_sin_resultado():
    """Tienen que estar —son el 41 % de los días con plan y documentan la regla
    de anulación— pero sin resultado, para que no cuenten como operación."""
    cfg = ConfiguracionSistema()
    fichas = reconstruir(_dia("2026-07-15", {8: (4035, 4020), 9: (4030, 3980)}), cfg)
    assert len(fichas) == 1
    assert fichas[0]["estado"] == "anulado"
    assert fichas[0]["r_neto"] is None
    assert _cerradas(fichas) == []


# ---------------------------------------------------------------------------
# la puerta de promoción
# ---------------------------------------------------------------------------
def _ops(valores, anio_desde=2006, por_anio=100):
    """Operaciones sintéticas, una por día REAL, con el resultado que se pida.

    Los días tienen que ser distintos: `_cerradas` deduplica por (día,
    dirección), así que repetir fechas deja la muestra en una fracción de lo
    pedido y las pruebas pasan por el camino equivocado.
    """
    import datetime as dt

    salida = []
    for i, r in enumerate(valores):
        anio = anio_desde + i // por_anio
        fecha = dt.date(anio, 1, 1) + dt.timedelta(days=i % por_anio)
        # Las condiciones VARÍAN: con features constantes el modelo da la
        # misma probabilidad a todo y el año se descarta por degenerado, así
        # que la prueba no llegaría a ejercitar la puerta de promoción.
        amplitud = 15.0 + (i % 17)
        salida.append({"dia": fecha.isoformat(), "direccion": "venta",
                       "r_neto": float(r), "amplitud": amplitud,
                       "coste_r": 0.30 / amplitud,
                       "sesgo_cuerpo": float((i % 11) - 5),
                       "sesgo_rango": 8.0 + (i % 7),
                       "acompaña_al_sesgo": bool(i % 2)})
    return salida


def test_cerradas_descarta_dias_repetidos_y_sin_resultado():
    filas = [{"dia": "2026-01-02", "direccion": "venta", "r_neto": 0.5},
             {"dia": "2026-01-02", "direccion": "venta", "r_neto": 0.5},
             {"dia": "2026-01-03", "direccion": None, "r_neto": None},
             {"r_neto": 1.0}]                     # sin día: inservible.
    assert len(_cerradas(filas)) == 1


def test_cerradas_devuelve_las_operaciones_en_orden_cronologico():
    """El walk-forward entrena con el pasado. Si el orden no es el real, parte
    del entrenamiento vendría del futuro y el AUC saldría inflado."""
    filas = [{"dia": "2026-03-01", "direccion": "venta", "r_neto": 1.0},
             {"dia": "2026-01-01", "direccion": "venta", "r_neto": -1.0},
             {"dia": "2026-02-01", "direccion": "venta", "r_neto": 0.5}]
    assert [f["dia"] for f in _cerradas(filas)] == [
        "2026-01-01", "2026-02-01", "2026-03-01"]


def test_el_corte_de_las_mitades_esta_fijado_y_no_se_ajusta_al_resultado():
    """Si el corte se eligiera mirando los datos, «positivo en las dos mitades»
    dejaría de significar nada: siempre hay algún corte que lo cumple."""
    assert ANIO_CORTE == 2016


def test_no_promociona_nada_con_la_evidencia_actual():
    """El resultado medido: AUC 0,52 fuera de muestra sobre 17 años. Si algún
    día esta prueba falla, es que alguien aflojó la puerta."""
    ops = _cerradas(_ops([0.8 if i % 5 == 0 else -0.3 for i in range(2000)]))
    informe = {}
    try:
        from oro.aprender import aprender
    except Exception:  # pragma: no cover
        pytest.skip("sin ML")
    res = aprender(ops, informe).get("aprendizaje", {})
    if "auc" not in res:
        pytest.skip(res.get("error") or res.get("motivo") or "sin validación")
    assert res["promocionado"] is False
    assert res["razones_para_no_promocionar"]


def test_la_puerta_exige_mejorar_el_r_AL_ANO_no_por_operacion():
    """La lección que costó más caro: filtrar por coste subía el R por
    operación de +0,013 a +0,035 y bajaba el R al año de +2,96 a +2,35, porque
    descartaba más operaciones de las que compensaba. Un filtro que opera menos
    y gana menos en total no es una mejora, y la puerta tiene que saberlo."""
    import inspect

    from oro import aprender as modulo

    fuente = inspect.getsource(modulo.aprender)
    assert "r_ano_filtrado <= r_ano_todo" in fuente, (
        "la condición de R al año ha desaparecido de la puerta de promoción")


def test_las_condiciones_del_modelo_no_pueden_venir_del_resultado():
    """Si entre las condiciones se colara `r_maximo`, `salida` o `motivo_cierre`,
    el modelo acertaría en las pruebas y fallaría en producción. Es el fallo que
    más veces ha aparecido en este proyecto."""
    from oro.aprender import _condiciones

    ficha = {"amplitud": 20.0, "coste_r": 0.015, "sesgo_cuerpo": 2.0,
             "sesgo_rango": 10.0, "acompaña_al_sesgo": True,
             # lo que NO puede entrar:
             "r_neto": 1.5, "r_bruto": 1.6, "r_maximo": 2.4,
             "salida": 3990.0, "motivo_cierre": "stop", "estado": "cerrada"}
    cond = _condiciones(ficha)
    for prohibido in ("r_neto", "r_bruto", "r_maximo", "salida",
                      "motivo_cierre", "estado", "entrada"):
        assert prohibido not in cond, f"se cuela {prohibido}, que es del futuro"


# ---------------------------------------------------------------------------
# la vigilancia
# ---------------------------------------------------------------------------
def test_la_vigilancia_no_se_alarma_por_una_mala_racha_normal():
    """12 operaciones a -0,26 R con una media esperada de +0,11 es z = -1,1.
    Eso es ruido, y decir lo contrario sería apagar una estrategia buena."""
    hist = _cerradas(_ops([1.2 if i % 3 == 0 else -0.55 for i in range(2000)]))
    vivo = _cerradas(_ops([-0.3] * 12, anio_desde=2026))
    v = vigilar(hist, vivo, {})["vigilancia"]
    assert v["operaciones_en_vivo"] == 12
    assert v["veredicto"] == "compatible con lo medido"
    assert v["alerta"] is None
    assert v["operaciones_para_demostrar_la_ventaja"] > 100


def test_la_vigilancia_avisa_cuando_lo_de_en_vivo_se_separa_de_verdad():
    hist = _cerradas(_ops([1.2 if i % 3 == 0 else -0.55 for i in range(2000)]))
    vivo = _cerradas(_ops([-1.0] * 120, anio_desde=2026))
    v = vigilar(hist, vivo, {})["vigilancia"]
    assert v["veredicto"] == "se ha separado de lo medido"
    assert v["alerta"] and "por debajo" in v["alerta"]


def test_la_vigilancia_dice_que_no_sabe_cuando_no_hay_datos():
    hist = _cerradas(_ops([0.5] * 500))
    v = vigilar(hist, [], {})["vigilancia"]
    assert "todavía no hay operaciones" in v["motivo"]


def test_leer_jsonl_aguanta_lineas_rotas(tmp_path):
    """El registro vive en un repositorio y lo escriben varias ejecuciones. Una
    línea a medio escribir no puede dejar el aprendizaje muerto."""
    ruta = tmp_path / "r.jsonl"
    ruta.write_text('{"dia": "2026-01-02", "r_neto": 0.5}\n'
                    '{roto\n'
                    '\n'
                    '{"dia": "2026-01-03", "r_neto": -1.0}\n', encoding="utf-8")
    assert len(_leer_jsonl(ruta)) == 2


def test_leer_jsonl_sin_fichero_no_revienta(tmp_path):
    assert _leer_jsonl(tmp_path / "no_existe.jsonl") == []
