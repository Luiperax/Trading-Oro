# Plantilla de seguimiento de señales

`Seguimiento_XAUUSD.xlsx` — hoja de cálculo para anotar cada señal del sistema en
tu **cuenta demo** y medir tu porcentaje de acierto real.

## Cómo usarla
1. Ábrela con **Excel**, **Google Sheets** (Archivo → Importar) o **LibreOffice**.
2. Por cada señal que te llegue por email, añade **una fila** en la hoja
   **«Operaciones»**: fecha, dirección, entrada, stop, TP y la confianza que
   indica el aviso.
3. Cuando la operación **cierre**, rellena:
   - **Resultado**: `Ganada`, `Perdida`, `BE` (break-even) o `En curso`.
   - **R obtenido**: el resultado en múltiplos de riesgo. Guía rápida:
     `+1.7` si llegó a todos los objetivos, `+0.5` si salió en break-even tras el
     primer objetivo, `-1` si saltó el stop.
4. La hoja **«Resumen»** se actualiza sola: **% de acierto**, Profit Factor,
   expectativa (R media), resultado total y rachas.

## Regenerarla
```bash
python plantillas/generar_plantilla.py
```

> Herramienta de análisis, no asesoramiento financiero. Mide con muestra
> suficiente (decenas de operaciones) antes de sacar conclusiones, y recuerda que
> la demo suele dar ejecuciones algo mejores que el real.
