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

## Sesión de Londres: ruptura del rango asiático

La única familia medida que encaja con las dos restricciones a la vez (operar
despierto y un spread alto), porque **el precio de entrada se conoce de
antemano**: es el borde del rango asiático, así que la orden se deja puesta y no
hay que mirar la pantalla.

### La estadística cruda (5.087 días)

* Londres rompe el rango asiático el **96,5 %** de los días: no es un filtro.
* Cierra a favor de la ruptura el **51,2 %** de las veces (50,8 % / 51,6 % por
  mitades). Casi una moneda.
* Recorrido a favor 1,08× el rango, en contra 1,02×: casi simétrico.

Es decir: la ruptura por sí sola no vale. Lo que sí aparece es una cola derecha
(media +0,99 $ frente a mediana +0,25 $).

### Lo que sí filtra

Entrando solo cuando la ruptura ocurre en la **segunda** vela de Londres —no en
la primera, que suele ser ruido— y con stop al otro lado del rango asiático:

| Filtro de anchura | Ops/año | 0,30 $ | | 1,45 $ | |
|---|---|---|---|---|---|
| | | $/op | t | $/op | t |
| ninguno | 35 | +1,39 | 2,50 | +0,24 | 0,43 |
| ≥ p50 | 17 | +2,75 | **2,72** | +1,60 | 1,59 |
| ≥ p75 | 9 | +4,27 | 2,31 | **+3,12** | **1,69** |
| ≥ p85 | 5 | +4,47 | 1,71 | +3,32 | 1,27 |

Con spread bajo conviene filtrar poco (más muestra); con spread alto hay que
filtrar mucho (menos operaciones, más grandes). Con 1,45 $ lo mejor es el
cuartil superior de anchura: **9 operaciones al año, +0,137 R cada una**.

### Robustez: lo que aguanta y lo que no

* **El filtro de anchura aguanta**: de p0 a p85 todas dan resultado positivo
  (t entre 1,83 y 3,04). No es una celda con suerte.
* **La vela de ruptura NO aguanta**: vela 0 → t=2,13; vela 1 → 2,47;
  vela 2 → **0,37**; vela 3 → 1,60. Sin estructura: parámetro ajustado.
* **El fin de la sesión asiática NO aguanta**: hace pico exactamente en las 8:00
  de Londres, que fue la elección inicial (6h→1,71; 7h→1,98; 8h→2,47; 9h→1,22).

Por periodos de 5 años el resultado es positivo en los cuatro, pero en R dos de
ellos son prácticamente cero (+0,238 / +0,044 / +0,005 / +0,267).

### Veredicto

**Prometedora y bien encajada, pero NO probada.** t=1,69 al spread actual no es
significativo, y dos de los tres parámetros son ajustados. Lo que la hace
interesante no es la estadística sino la operativa:

* entrada a precio conocido → **orden pendiente puesta a las 10:00 de Madrid**;
* 9 operaciones al año → el spread casi no importa;
* toda la actividad en horario de Londres → despierto y con el mejor spread.

A 9 operaciones al año hacen falta muchos años para validarla en vivo. Si se
adopta, que sea con tamaño pequeño y sabiendo que es una apuesta razonable, no un
resultado demostrado.

---

## Continuación: por qué esa versión se descartó y cuál la sustituye

*(medición posterior, con las mismas 118.452 velas horarias de Dukascopy)*

La conclusión de arriba —«9 operaciones al año, prometedora pero no probada»—
tenía dos problemas que la medición siguiente destapó.

**Primero: la frecuencia era un artefacto del filtro malo.** El embudo era
5.087 días → 679 que rompen en la *segunda* vela → 170 que además tienen rango
ancho. Ese primer filtro descarta el 87 % de los días, y es exactamente el que
ya había fallado la prueba de robustez. Sin él hay ruptura casi todos los días.

**Segundo: el rango asiático roto en Londres no aguanta las mitades bloqueadas.**
Partiendo el histórico en 2006-2016 y 2016-2026 —mitades elegidas antes de mirar
y no tocadas después— pierde dinero en la segunda. Una regla que solo funciona en
la mitad que le conviene no es una regla.

### Las tres candidatas, netas de 0,60 $ de spread

| Regla | Ops/año | R/op | t | 1ª mitad | 2ª mitad |
|---|---|---|---|---|---|
| Rango de Londres (3-8 ET) roto durante NY | 234 | +0,0552 | 3,01 | +0,0596 | +0,0515 |
| Apertura de NY (1ª hora) rota después | 223 | +0,0480 | 2,45 | +0,0241 | +0,0691 |
| Rango asiático (0-3 ET) roto en Londres | 247 | +0,0079 | 0,32 | +0,0275 | −0,0088 |

Solo la primera es positiva en las dos mitades. La de Nueva York solo funciona en
la segunda: es la misma enfermedad que la asiática, con el signo cambiado.

### Filtros pre-declarados sobre la superviviente

Cinco hipótesis declaradas antes de medir, con Bonferroni (α = 0,05/5 → t > 2,81)
**y** las dos mitades positivas como requisito adicional:

| Filtro | Ops/año | R/op | t | 1ª mitad | 2ª mitad | |
|---|---|---|---|---|---|---|
| sin filtro | 234 | +0,0552 | 3,01 | +0,0596 | +0,0515 | pasa |
| rango estrecho (< mediana) | 117 | +0,0908 | 2,99 | +0,1129 | +0,0778 | pasa |
| rango ancho (≥ mediana) | 117 | +0,0197 | 0,96 | +0,0242 | +0,0139 | no |
| a favor de la media de 20 días | 129 | +0,0749 | 3,02 | +0,0922 | +0,0599 | pasa |
| **ruptura en las 2 primeras horas** | **207** | **+0,0687** | **3,38** | **+0,0816** | **+0,0575** | **pasa** |
| cierre de Londres cerca del borde | 148 | +0,0526 | 2,37 | +0,0227 | +0,0783 | no |

Se elige **el de las dos primeras horas** y no los otros, aunque su ventaja *por
operación* sea menor: en R al año rinde más (207 × 0,0687 = **+14,2 R**) que
combinar los tres (61 × 0,1512 = +9,2 R), y con tres veces más muestra.

Perturbando las horas (2-8, 3-7, 4-8, cerrar a las 15, 8-10, 9-10…), las **10
variantes probadas dan resultado positivo**: no depende de acertar la hora
exacta. El walk-forward —elegir filtro con los 5 años anteriores y operar el
sexto— da +0,1350 R/op con 10 de 15 años positivos (t = 2,74) y converge por su
cuenta en la misma combinación, sin haber visto el futuro.

### La salida

| Salida | Acierto | 0,30 $ | 0,60 $ | R/año a 0,60 $ |
|---|---|---|---|---|
| dejar correr al cierre de NY | 47,5 % | +0,1137 | +0,0687 | +14,2 |
| stop a break-even en 1R, sin objetivo | 42,4 % | +0,1220 | +0,0770 | +16,0 |
| objetivo 4R + stop a BE | 42,4 % | +0,1053 | +0,0602 | +12,5 |
| **objetivo 3R + stop a BE** | 42,7 % | +0,1026 | +0,0575 | +11,9 |
| **objetivo 3R, sin tocar nada** | 47,8 % | +0,0954 | +0,0503 | +10,4 |
| objetivo 2R | 48,7 % | +0,0858 | +0,0407 | +8,4 |

Se implementa **objetivo 3R sin gestión**: conserva el 73 % de la ventaja de
dejar correr y se puede poner en el bróker y olvidar, que era el requisito.

### Y el coste, que sigue mandando

| Spread | R/op | t | R/año |
|---|---|---|---|
| 0,30 $ | +0,1137 | 5,60 | +23,6 |
| 0,60 $ | +0,0687 | 3,38 | +14,2 |
| **1,45 $** | **−0,0590** | **−2,90** | **−12,2** |

Filtrar por «que el spread no se lleve más de X R» **no lo rescata**: a 1,45 $
deja 33 operaciones al año con t = 0,63, indistinguible de cero. Por eso el
sistema no emite el plan por encima de 0,60 $ (`ConfiguracionRuptura.coste_max`).

Lo que sí cambia respecto al sistema intradía es el tamaño de 1R: aquí es el
rango entero de la mañana (10,3 $ de media histórica, **24-30 $ hoy**) frente a
1,5 × ATR (7,4 $ de media, 27 $ hoy). El mismo spread pesa la mitad.

### ¿Se puede saber cuál de las dos órdenes es la buena?

Cinco discriminadores pre-declarados, todos calculables a las 8:00 ET sin mirar
el futuro. Se compara la ruptura *a favor* del indicador contra la *en contra*:

| Discriminador | A favor | En contra | Diferencia | t |
|---|---|---|---|---|
| **dirección de la sesión asiática** | **+0,0883** | **+0,0133** | **+0,0750** | **2,07** |
| tendencia de 20 días | +0,0663 | +0,0352 | +0,0311 | 0,85 |
| tendencia de 5 días | +0,0539 | +0,0450 | +0,0089 | 0,24 |
| rango sobre/bajo el cierre de ayer | +0,0518 | +0,0493 | +0,0025 | 0,07 |
| dónde cierra Londres en el rango | +0,0380 | +0,0370 | +0,0009 | 0,02 |

**Ninguno pasa Bonferroni** (t > 2,81). Solo la sesión asiática tiene las dos
mitades del mismo signo (+0,1165 / +0,0369) y una diferencia con tamaño. Se
sometió a las comprobaciones que mataron a otras candidatas:

* **5 variantes de la medida** (cierre−apertura, cierre vs punto medio, ventana
  1-3 ET, ventana 0-4 ET, exigir cuerpo grande): las 5 dan diferencia positiva
  (+0,033 a +0,087). No es la celda con suerte de una tabla.
* **15 de 20 años** la diferencia va a favor.
* **Control:** las compras dan +0,0486 y las ventas +0,0521 por separado. No es
  un sesgo direccional disfrazado.
* **Días planos** (cuerpo < 20 % del rango asiático): 885 días, −0,0162 R/op, y
  los dos lados se parecen (−0,029 / −0,004). Ahí no se señala favorita.

Se implementa **solo como etiqueta, no como filtro**: operar únicamente el lado
bueno da +9,1 R al año frente a +10,4 R operando los dos. Y el correo dice el
t = 2,07 en voz alta, porque una indicación presentada como certeza es peor que
no darla.

### Veredicto

**Se implementa** (`oro/sesiones.py`, workflow `oro-plan.yml`), con estas
reservas dichas en voz alta y repetidas en el propio correo:

* 14 años positivos de 20, no 20. **De 2016 a 2021 perdió cinco años seguidos**
  incluso con spread de 0,60 $.
* Acierta el 42,7 %. La mayoría de los días la operación pierde.
* Con el spread actual del usuario (1,45-2 $) **no se enviará ningún plan**, y
  eso es correcto: la ventaja medida a ese coste es negativa.
