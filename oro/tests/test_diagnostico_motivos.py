"""El diagnóstico debe decir QUÉ MOTIVOS funcionan, en el idioma del usuario.

Cerrar el círculo que se pidió —"por qué mandé esta señal, por qué se cumplió o
no, cómo lo hago mejor"— exige comparar el acierto CON cada motivo presente
frente a SIN él. La tasa a secas engaña: un motivo que aparece en todas las
señales tendrá la tasa global y no explicará nada.
"""

from __future__ import annotations

import random

from oro.diagnostico import _bloque_motivos

BUENO = "El precio acaba de barrer stops y girar: suele preceder al movimiento."
MALO = "El precio está del lado bueno del precio medio del día (VWAP)."
SIEMPRE = "El oro viene subiendo y compramos a favor de ese movimiento."


def _muestra(n=60, semilla=4):
    rng = random.Random(semilla)
    ops = []
    for _ in range(n):
        motivos = [SIEMPRE]
        bueno, malo = rng.random() < 0.45, rng.random() < 0.5
        if bueno:
            motivos.append(BUENO)
        if malo:
            motivos.append(MALO)
        p = (0.75 if bueno else 0.30) - (0.20 if malo else 0.0)
        ops.append({"motivos": motivos, "label": 1 if rng.random() < p else 0})
    return ops


def test_encuentra_el_motivo_que_de_verdad_ayuda():
    texto = "\n".join(_bloque_motivos(_muestra()))
    assert "✓" in texto and BUENO[:40] in texto


def test_nunca_pone_un_visto_bueno_a_un_motivo_que_resta():
    # Un ✓ sobre algo que hace daño invita a fiarse justo de lo peor.
    lineas = _bloque_motivos(_muestra())
    for i, linea in enumerate(lineas):
        if linea.strip().startswith("✓"):
            detalle = lineas[i + 1]
            assert "(+" in detalle, f"marcado con ✓ pero resta: {detalle}"
        if linea.strip().startswith("✗"):
            assert "(-" in lineas[i + 1]


def test_un_motivo_presente_siempre_no_se_atribuye_nada():
    # Sin contraste no se puede saber si aporta: no debe aparecer.
    texto = "\n".join(_bloque_motivos(_muestra()))
    assert SIEMPRE[:40] not in texto


def test_se_calla_cuando_ninguno_destaca():
    ops = [{"motivos": [BUENO] if i % 2 else [MALO], "label": i % 3 == 0}
           for i in range(40)]
    texto = "\n".join(_bloque_motivos(ops))
    assert "Ninguno destaca" in texto
    assert "✓" not in texto and "✗" not in texto


def test_se_abstiene_con_pocas_senales():
    texto = "\n".join(_bloque_motivos(_muestra(n=6)))
    assert "Faltan" in texto
    assert "✓" not in texto


def test_los_motivos_se_guardan_al_cerrar_la_operacion():
    # Sin esto el bloque anterior nunca tendría datos: quedan las features
    # numéricas, que nadie lee, y se pierde el porqué de cada señal.
    import datetime as dt

    from oro.config import cargar_configuracion
    from oro.dominio import Direccion, Signal
    from oro.riesgo import calcular_niveles
    from oro.vivo.gestor import GestorOperaciones

    cfg = cargar_configuracion()
    n = calcular_niveles(4451.90, Direccion.COMPRA, atr=8.4, cfg=cfg)
    sig = Signal(momento=dt.datetime.now(dt.timezone.utc), direccion=Direccion.COMPRA,
                 entrada=n.entrada, stop_loss=n.stop_loss, take_profits=n.take_profits,
                 probabilidad=0.6, confianza=0.8, riesgo_recompensa=n.riesgo_recompensa,
                 tamano_posicion=1.0, motivos_entrada=[BUENO, MALO], riesgos=[],
                 contexto_tecnico="alcista", puntuacion=0.7)
    g = GestorOperaciones(sig)
    assert g.motivos == [BUENO, MALO]
    # Y deben sobrevivir a una reanudación (GitHub Actions reinicia el proceso).
    revivido = GestorOperaciones.desde_dict(g.a_dict())
    assert revivido.motivos == [BUENO, MALO]
