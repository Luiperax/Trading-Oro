# Estrategias del oro que hemos medido

Registro de lo probado sobre 19,6 años de XAU/USD (118.452 velas H1 de Dukascopy,
ene-2007 a ago-2026), para no volver a medir lo mismo. Todo con costes reales y
comparado siempre contra una referencia honesta.

## El problema que lo condiciona todo: la frecuencia

El coste de operar es **fijo por operación** (el spread), así que lo que decide la
viabilidad no es la ventaja, sino la ventaja **por operación** frente al coste.
Con un spread de 1,45 $ sobre oro a 4.400 $:

| Sistema | Operaciones/año | Coste del spread al año |
|---|---|---|
| Intradía H1 (el actual) | 239 | **19 %** |
| Tendencia diaria | ~2,4 | **0,03 %** |

Un 19 % anual en spread no lo compensa ninguna estrategia. Ese único número
explica por qué lo intradía no cuadra y lo de mayor plazo sí.

## Descartadas, con la medición

| Estrategia | Resultado | Por qué se descarta |
|---|---|---|
| Dirección desde el dólar (DXY) | corr. −0,364 **simultánea**; +0,001 a una vela | Nadie se mueve primero |
| Plata, cobre, VIX, bitcoin como adelanto | todas se desploman a ~0 fuera de k=0 | Igual |
| Reversión tras movimientos extremos | \|t\| < 1,2, signos que se invierten entre mitades | Ruido |
| Día de la semana | viernes t=2,78, pero las mitades difieren 5× | Ruido |
| Estacionalidad intradía (18:00 NY) | +0,0377 % de cuerpo, t=12,92, 4/4 periodos | **Real**, pero cabe entera en el spread de la reapertura (1,45-2 $) |
| Filtro por coste en R | neto −0,028 → +0,074 | Trampa: selecciona 2025-26 (lo pasa el 0 % de 2015-19 y el 100 % de 2026) |
| Ensanchar el stop | coste 0,058 R → 0,029 R | La ventaja bruta cae de +0,0298 R a +0,0015 R: se cancelan |
| Subir a H4 | coste 0,195 R → 0,099 R | La ventaja cae de +0,0277 R a +0,0062 R: se cancelan |

## La única que sobrevive: tendencia + escalado por volatilidad

Ruptura Donchian de 100 días para estar dentro o fuera, y tamaño de posición
inversamente proporcional a la volatilidad de los últimos 60 días (la receta
clásica de los fondos de gestión sistemática; Moreira & Muir 2017 para la parte
del escalado).

| | CAGR | Sharpe | Peor caída |
|---|---|---|---|
| Comprar y esperar | 8,3 % | 0,57 | −44,9 % |
| Solo Donchian 100d | 7,1 % | 0,57 | −31,7 % |
| Solo escalado por volatilidad | 8,8 % | 0,66 | −48,6 % |
| **Las dos juntas** | **9,0 %** | **0,80** | **−23,0 %** |

Ninguna de las dos piezas por separado mejora el Sharpe de forma clara. Juntas sí.

**Validación** (porque el 100 se eligió después de ver una tabla):

* Sensibilidad: **todas** las combinaciones con Donchian ≥55 días y cualquier
  ventana de volatilidad entre 20 y 120 días baten a comprar y esperar
  (Sharpe 0,50-0,80). No es una celda afortunada, es una región.
* El tope del escalado no importa: 0,79-0,80 para cualquier valor ≥1,5.
* **Walk-forward** (elegir la ventana con el pasado, cobrar el año siguiente,
  17 años): Sharpe **0,72 vs 0,53**, CAGR 8,3 % vs 7,0 %, peor caída −37,5 %
  vs −44,9 %.

**Dónde está la ventaja**: en el desplome del oro de 2011-2015. Comprar y esperar
perdió el 41,9 %; esto perdió el 11,8 %. En las subidas fuertes va por detrás
(2007-2011: 98 % frente a 146 %). Es el perfil típico del seguimiento de
tendencia: renuncia a parte de la subida a cambio de no comerse los desplomes.

**Aguanta el swap nocturno**, que es su equivalente del spread:

| Swap por noche | Al año | Comprar y esperar | Tendencia + escalado |
|---|---|---|---|
| 0,005 % | 1,3 % | 7,0 % (Sh 0,50) | 8,1 % (Sh 0,73) |
| 0,010 % | 2,5 % | 5,6 % (Sh 0,42) | 7,2 % (Sh 0,66) |
| 0,020 % | 5,0 % | 3,0 % (Sh 0,26) | 5,4 % (Sh 0,51) |

Aguanta mejor porque está **fuera del mercado un tercio del tiempo**.

## La otra restricción: el horario de quien lo usa

Medido sobre las 4.410 entradas, repartidas por hora de Madrid:

| Franja | Entradas | % | Ventaja bruta |
|---|---|---|---|
| **00:00-07:00 (durmiendo)** | 1.561 | **35,4 %** | **+0,0622 R** |
| 07:00-13:00 | 1.059 | 24,0 % | +0,0192 R |
| 13:00-19:00 | 1.207 | 27,4 % | +0,0163 R |
| 19:00-24:00 | 583 | 13,2 % | −0,0094 R |

**La sesión asiática concentra la ventaja del sistema intradía, y cae de noche.**
Restringido a horas despiertas (07:00-24:00), con spread de 0,30 $:

| Periodo | Ops/año | Bruto | Neto | t |
|---|---|---|---|---|
| 2007-2026 | 145 | +0,0121 | −0,0453 | −2,80 |
| 2020-2026 | 142 | +0,0016 | −0,0345 | −1,24 |
| 2024-2026 | 151 | +0,0609 | +0,0360 | 0,81 |

Entrar tarde tampoco vale: tomando las señales nocturnas y entrando a las 08:00,
la ventaja cae de +0,0622 R a +0,0174 R. Y no es porque el movimiento ya haya
ocurrido —solo el 6 % había tocado el stop y el 1 % el objetivo—, sino porque la
señal deja de ser válida al envejecer.

**Consecuencia**: el sistema intradía necesita ejecución automática para capturar
su propia ventaja. A mano y de día es, en el mejor de los casos, neutro.

La estrategia de tendencia esquiva esta restricción igual que esquiva el spread:
cambia de posición 2-3 veces al año, así que da igual la hora a la que llegue el
aviso.

## Lo que NO es

No es un sistema de señales intradía. Cambia de posición unas 2-3 veces al año y
hay que mantenerla abierta durante meses. Y una caída del 37,5 % fuera de muestra
sobre 3.000 € son 1.125 € de pérdida flotante en el peor momento: hay que poder
aguantarla sin cerrar.
