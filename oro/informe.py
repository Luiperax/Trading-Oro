"""Resumen del registro real de señales: cuántas se cumplieron y con qué resultado.

Lee el histórico permanente de operaciones (``operaciones_oro.jsonl``, que el
vigilante va rellenando al cerrar cada operación) y calcula las métricas reales:
acierto, Profit Factor, expectativa, resultado total y rachas.

Uso:
    python -m oro.informe
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .config import cargar_configuracion


def _cargar(ruta: Path) -> list:
    if not ruta.exists():
        return []
    registros = []
    for linea in ruta.open(encoding="utf-8"):
        linea = linea.strip()
        if linea:
            try:
                registros.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    return registros


def main(argv=None) -> int:
    cfg = cargar_configuracion()
    ruta = Path(cfg.ruta_operaciones)
    ops = _cargar(ruta)

    print("=" * 52)
    print("  REGISTRO REAL DE SEÑALES — XAU/USD")
    print("=" * 52)
    if not ops:
        print("Todavía no hay operaciones cerradas registradas.")
        print(f"(Se irán guardando en {ruta} conforme el sistema cierre operaciones.)")
        return 0

    erres = [o.get("resultado_r", 0.0) for o in ops]
    ganadas = [r for r in erres if r > 0]
    perdidas = [r for r in erres if r <= 0]
    n = len(erres)
    win = len(ganadas) / n if n else 0.0
    suma_g = sum(ganadas)
    suma_p = abs(sum(perdidas))
    pf = (suma_g / suma_p) if suma_p > 0 else float("inf")
    expectancy = sum(erres) / n if n else 0.0

    # Rachas.
    max_g = max_p = act_g = act_p = 0
    for r in erres:
        if r > 0:
            act_g += 1; act_p = 0
        else:
            act_p += 1; act_g = 0
        max_g = max(max_g, act_g); max_p = max(max_p, act_p)

    print(f"Operaciones cerradas : {n}")
    print(f"Ganadas / Perdidas   : {len(ganadas)} / {len(perdidas)}")
    print(f"% de ACIERTO         : {win:.1%}")
    print(f"Profit Factor        : {pf:.2f}" if pf != float('inf') else "Profit Factor        : ∞")
    print(f"Expectancy (R media) : {expectancy:+.3f}R")
    print(f"Resultado total      : {sum(erres):+.2f}R")
    print(f"Racha ganadora máx   : {max_g}   | perdedora máx: {max_p}")
    print("-" * 52)
    print("Últimas 5 operaciones:")
    for o in ops[-5:]:
        marca = "✓ GANADA" if o.get("ganada") else "✗ perdida"
        print(f"  {o.get('apertura','')[:16]}  {o.get('direccion','').upper():6} "
              f"@ {o.get('entrada')}  -> {o.get('resultado_r'):+.2f}R  {marca}")
    print("\nNota: datos reales de tus señales. Herramienta de análisis, no")
    print("asesoramiento financiero.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
