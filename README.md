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
- **Entradas y salidas en vivo**: mueve el stop a break-even tras el primer
  objetivo y avisa de cada objetivo y del cierre.
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

## Documentación

- Guía del paquete y todos los comandos: [`oro/README.md`](oro/README.md)
- Arquitectura y decisiones técnicas: [`docs/ARQUITECTURA_ORO.md`](docs/ARQUITECTURA_ORO.md)
- Uso desde el móvil / despliegue: [`oro/DESPLIEGUE_MOVIL.md`](oro/DESPLIEGUE_MOVIL.md)

## Estructura

```
oro/                     Paquete del sistema (dominio, datos, indicadores,
                         estructura, riesgo, señales, ML, backtesting, vivo, API).
oro/tests/               54 pruebas.
.github/workflows/       Vigilante en la nube (alertas cada ~15 min).
docs/                    Arquitectura.
```
