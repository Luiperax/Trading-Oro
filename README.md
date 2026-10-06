# trading-oro — Sistema de análisis de XAU/USD

Sistema **profesional, modular y probado** que analiza el mercado del oro
(XAU/USD) con datos reales, genera oportunidades de trading de alta calidad
(*setups A+*, 2–4 al día) y **avisa cuándo entrar y cuándo salir** por email,
Telegram o push. La gestión del riesgo es la prioridad número uno.

> ## ⚠️ Aviso imprescindible
> Esto es una **herramienta de análisis y apoyo a la decisión, NO asesoramiento
> financiero ni una promesa de beneficios.** El trading con apalancamiento puede
> hacerte **perder todo tu capital**. Ningún modelo predice el mercado con
> certeza; la probabilidad que muestra el sistema es una **estimación, no una
> garantía**, y habrá rachas de pérdidas. Antes de arriesgar dinero real, valida
> con *backtesting* y en **cuenta demo** durante meses. El uso es de tu entera
> responsabilidad.

---

## Qué hace

- **Datos reales**: precio del oro (Yahoo Finance), prensa financiera
  (Yahoo/Google News) para el sentimiento, y calendario económico (ForexFactory)
  para no operar en eventos de alto impacto (FED, IPC, NFP…).
- **Motor de señales A+** por confluencia de estructura de mercado (Smart Money
  Concepts) + indicadores de confirmación; si no hay ventaja, lo dice: *«Hoy no
  existen operaciones con suficiente ventaja estadística.»*
- **Gestión de riesgo estricta**: stop y objetivos por ATR, tamaño de posición a
  un % fijo del capital, y guardas que prohíben operar en condiciones malas.
- **Salida sin vigilar la pantalla**: la operación se especifica entera al
  abrirla —entrada, stop, objetivo y la distancia del stop dinámico— y el aviso
  trae los pasos numerados, en el orden en que se teclean en el bróker.
- **Avisos de ajuste**: conforme la operación avanza llegan correos diciendo a
  qué precio mover el stop (por si tu bróker no tiene trailing stop) y, si el
  precio se acerca al objetivo sin llegar, una propuesta para subirlo. Es
  opcional: si no da tiempo a moverlo, el objetivo original se ejecuta igual.
- **Aprende de sus propias señales**: guarda por qué mandó cada una y si se
  cumplió, y el diagnóstico compara el acierto CON cada motivo presente frente
  a SIN él, para saber cuáles ayudan de verdad.
- **Backtesting** con métricas (Profit Factor, Drawdown, Sharpe, Expectancy…) y
  **modelo ML con validación walk-forward anti-sobreajuste**.
- **Avisos al móvil**: email (SMTP), Telegram, webhook/push.
- **54 pruebas automáticas.**

## Puesta en marcha rápida (local)

```bash
pip install -r oro/requirements.txt

python -m oro.cli demo         # demostración de extremo a extremo (offline)
python -m oro.cli sentimiento  # noticias + sentimiento + riesgo macro ahora
python -m oro.cli vivo         # vigila el mercado real y avisa entradas/salidas
pytest oro/tests -q            # ejecutar las pruebas
```

## Recibir las señales en el móvil (sin servidor propio)

Este repo incluye un **vigilante en la nube gratuito con GitHub Actions**: revisa
el mercado cada ~15 min y te avisa por **email** (o Telegram). Guía paso a paso:
👉 **[`oro/DESPLIEGUE_MOVIL.md`](oro/DESPLIEGUE_MOVIL.md)**

Resumen: en **Settings → Secrets and variables → Actions** de este repo, crea los
secretos de tu correo (`ORO_SMTP_HOST`, `ORO_SMTP_USUARIO`, `ORO_SMTP_CLAVE`,
`ORO_SMTP_DESTINO`) y pruébalo en **Actions → «Alertas XAU/USD» → Run workflow →
modo_prueba**.

## Qué está encendido

| | estado | por qué |
|---|---|---|
| **Plan de ruptura** (venta del rango de Londres; las dos órdenes el día del dato de empleo) | **activo** | +0,073 R/op sobre 2.209 operaciones de 21 años con todos los costes medidos, t = 2,80, mitades +0,088 / +0,058; casi dos tercios salen de los días de empleo (+0,64 R/op, t = 4,58) |
| Motor de señales intradía | **apagado** | −0,090 R/op sobre 4.891 operaciones, 2 años positivos de 21, −157 €/año |

El motor de señales se apagó en octubre de 2026 tras reconstruir el histórico
entero. Se intentó arreglar antes: seis variantes de salida, todas negativas en
bruto; un modelo entrenado con 21 años que ordena al revés (AUC 0,5054); y 93
motivos de entrada de los que ninguno sobrevive a la corrección por pruebas
múltiples. Se vuelve a encender con `ORO_SENALES_ACTIVAS=1`.

Los precios salen de **XAU/USD al contado** (ticks de Dukascopy), que es el
mismo instrumento sobre el que está medida toda la investigación y el mismo que
cotiza tu bróker. Hasta octubre de 2026 salían del **futuro** de COMEX y estaban
43 $ por encima; se detectó contrastándolos con el LBMA Gold Price, el precio de
referencia oficial del oro, y ahora esa comprobación se hace **antes de mandar
cada plan**: si los precios no son oro al contado, no se manda nada.

## El plan del día (segunda estrategia)

Además de las señales intradía, el sistema manda cada mañana un **plan de
ruptura**: a las 14:00 de Madrid mide el rango que ha dejado la mañana de
Londres y te da **una orden de venta pendiente** en el mínimo de ese rango, para
dejarla puesta y olvidarte. Si salta, es la operación del día; si el precio
rompe el techo del rango antes, te llega un correo para cancelarla.

👉 **[`docs/PLAN_DEL_DIA.md`](docs/PLAN_DEL_DIA.md)**

Aviso honesto: **acierta el 39 % de las veces**, 6 de los 21 años medidos
acabaron en pérdida y la peor racha fue de 45 R. Medido sobre 2.209 operaciones
de 2006 a 2026 con el mismo código que opera y con el spread y el deslizamiento
REALES sacados de los ticks: +0,073 R por operación (t = 2,80), unos +7,8 R al
año. Casi dos tercios salen de los ~8 días al año en que se publica el dato de
empleo de EE. UU. (esos días van dos órdenes); el resto de días la venta no se
distingue de cero.

Antes dejaba **dos** órdenes, una a cada lado. Se midió el histórico completo y
el lado de las compras resultó ser un lastre de −7,7 R al año, así que se quitó.
El detalle está en
[`docs/ESTRATEGIAS_MEDIDAS.md`](docs/ESTRATEGIAS_MEDIDAS.md).

## Documentación

- Guía del paquete y todos los comandos: [`oro/README.md`](oro/README.md)
- Arquitectura y decisiones técnicas: [`docs/ARQUITECTURA_ORO.md`](docs/ARQUITECTURA_ORO.md)
- El plan del día (ruptura de sesión): [`docs/PLAN_DEL_DIA.md`](docs/PLAN_DEL_DIA.md)
- Qué se ha medido y qué se ha descartado: [`docs/ESTRATEGIAS_MEDIDAS.md`](docs/ESTRATEGIAS_MEDIDAS.md)
- Uso desde el móvil / despliegue: [`oro/DESPLIEGUE_MOVIL.md`](oro/DESPLIEGUE_MOVIL.md)

## Estructura

```
oro/                     Paquete del sistema (dominio, datos, indicadores,
                         estructura, riesgo, señales, ML, backtesting, vivo, API).
oro/sesiones.py          Ruptura del rango de sesión (el plan del día).
oro/tests/               Pruebas.
.github/workflows/       Vigilante en la nube (alertas cada ~15 min) y plan diario.
docs/                    Arquitectura, estrategias medidas y guía del plan.
```
