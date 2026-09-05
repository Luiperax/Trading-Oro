"""El registro de operaciones no puede mezclarse con el de señales emitidas.

`servicio._registrar_senal` escribía en el MISMO fichero que el runner, con otro
esquema: sin `resultado_r` ni `apertura`. Al leerlo:

  * `resultado_r` ausente se leía como 0.0, así que cada señal sin cerrar contaba
    como una operación PERDEDORA que nunca existió, inflando el total y hundiendo
    el porcentaje de acierto;
  * `deduplicar` indexa por (apertura, direccion) y ninguna tiene `apertura`, así
    que todas las de una misma dirección colapsaban en una.

Ahora van a ficheros distintos, y al leer se filtra igualmente porque el
histórico ya existente puede traer las dos formas mezcladas.
"""

from __future__ import annotations

import json

from oro.config import cargar_configuracion
from oro.informe import _cargar, construir_resumen, es_operacion_cerrada

CERRADA = {"apertura": "2026-08-07T00:00:00+00:00", "cierre": "2026-08-07T04:00:00+00:00",
           "direccion": "venta", "entrada": 4291.2, "stop_inicial": 4320.27,
           "resultado_r": -1.0, "ganada": False, "label": 0}
SENAL = {"momento": "2026-09-05T10:00:00+00:00", "direccion": "compra",
         "entrada": 4500.0, "stop_loss": 4480.0, "probabilidad": 0.6,
         "confianza": 0.8, "puntuacion": 0.7, "rr": 5.0}


def test_distingue_una_operacion_cerrada_de_una_senal():
    assert es_operacion_cerrada(CERRADA)
    assert not es_operacion_cerrada(SENAL)
    assert not es_operacion_cerrada({"apertura": "x"})            # sin resultado.
    assert not es_operacion_cerrada({"resultado_r": 1.0})          # sin apertura.
    # Una operación que acabó exactamente en 0.0 R SÍ es una operación cerrada.
    assert es_operacion_cerrada({"apertura": "x", "resultado_r": 0.0})


def test_las_senales_sin_cerrar_no_ensucian_el_marcador(tmp_path):
    ruta = tmp_path / "mix.jsonl"
    ganada = dict(CERRADA, apertura="2026-08-08T00:00:00+00:00", resultado_r=2.0,
                  ganada=True, label=1)
    filas = [CERRADA, ganada] + [dict(SENAL, momento=f"2026-09-0{i}T10:00:00+00:00")
                                 for i in range(1, 6)]
    ruta.write_text("\n".join(json.dumps(f) for f in filas), encoding="utf-8")

    ops = _cargar(ruta)
    assert len(ops) == 2, f"se colaron señales sin cerrar: {len(ops)}"
    texto = construir_resumen(ops)
    assert "Operaciones cerradas : 2" in texto
    assert "50.0%" in texto, "el acierto está contaminado por señales sin resultado"


def test_los_dos_ficheros_son_distintos():
    cfg = cargar_configuracion()
    assert cfg.ruta_operaciones != cfg.ruta_senales


def test_las_rutas_se_pueden_cambiar_por_entorno(monkeypatch):
    # Sin esto no se puede probar el ciclo real sin escribir en el histórico
    # de verdad, que es cómo se coló un falso positivo durante la revisión.
    monkeypatch.setenv("ORO_RUTA_OPERACIONES", "/tmp/x_ops.jsonl")
    monkeypatch.setenv("ORO_RUTA_SENALES", "/tmp/x_sen.jsonl")
    monkeypatch.setenv("ORO_RUTA_MODELO", "/tmp/x_modelo.pkl")
    cfg = cargar_configuracion()
    assert cfg.ruta_operaciones == "/tmp/x_ops.jsonl"
    assert cfg.ruta_senales == "/tmp/x_sen.jsonl"
    assert cfg.ruta_modelo == "/tmp/x_modelo.pkl"


def test_el_aprendizaje_ignora_las_senales_sin_resultado(tmp_path):
    from oro.aprender import _cargar_operaciones

    ruta = tmp_path / "mix.jsonl"
    con_feat = dict(CERRADA, features={"rsi_14": 40.0})
    filas = [con_feat] + [dict(SENAL, momento=f"2026-09-0{i}T10:00:00+00:00")
                          for i in range(1, 4)]
    ruta.write_text("\n".join(json.dumps(f) for f in filas), encoding="utf-8")
    assert len(_cargar_operaciones(ruta)) == 1
