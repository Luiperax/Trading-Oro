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

*(Actualización posterior: se cambió a **cerrar a mano al final de la sesión**,
con un objetivo a 10R como red de seguridad. Ver abajo.)*

### La salida, revisada

El objetivo a 3R costaba un tercio de la ventaja porque cortaba las ganadoras
grandes. Medido con la frecuencia con que cada objetivo llega a ejecutarse:

| Salida | R/op | t | Lo toca |
|---|---|---|---|
| sin objetivo cercano | +0,0685 | 3,37 | 0,0 % |
| **objetivo 10R** | **+0,0673** | **3,34** | **0,1 %** |
| objetivo 8R | +0,0642 | 3,24 | 0,2 % |
| objetivo 6R | +0,0626 | 3,20 | 0,8 % |
| objetivo 4R | +0,0513 | 2,74 | 2,7 % |
| objetivo 3R *(anterior)* | +0,0501 | 2,77 | 6,1 % |
| **sin objetivo + stop a BE en 1R** | **+0,0768** | **3,91** | 0,0 % |

Se implementa el objetivo a **10R como red de seguridad** (cuesta 0,0012 R, el
1,7 % de la ventaja, y cubre el día extraordinario) más **cierre a mano a las
21:50**. El movimiento del stop a break-even en 1R va como paso opcional en el
correo, con su cifra al lado, porque exige mirar el móvil una vez.

Adelantar el cierre no cuesta nada apreciable (22:00 → +0,0685; 21:00 → +0,0593;
20:00 → +0,0620; 19:00 → +0,0611), así que los 10 minutos de margen sobran.

### Efecto día de la semana: MEDIDO Y DESCARTADO

Los primeros viernes de mes (nóminas de EE. UU.) dan **+0,5315 R/op, t = 4,47**,
18 de 20 años positivos, mediana +0,32, y aguantan quitando las 10 mejores
operaciones (+0,3677, t = 3,19). Tiene mecanismo: el dato sale a las 8:30 ET,
dentro de la ventana de disparo, sobre un rango formado antes (3:00-8:00) que
todavía no sabe nada. Predicción confirmada: en la regla de la apertura de NY
—cuyo rango 8:00-9:00 contiene el dato— el efecto desaparece (t = 1,12).

**Y aun así no se implementa.** La ventaja entera cabe dentro del deslizamiento
del propio evento, que el backtest no puede ver:

| Deslizamiento extra sobre 1,45 $ | R/op | t |
|---|---|---|
| 0 $ | +0,3821 | 3,15 |
| 1 $ | +0,2063 | 1,62 |
| **2 $** | **+0,0305** | **0,23** |
| 3 $ | −0,1453 | −1,00 |

Con 2 $ de deslizamiento —lo normal en unas nóminas, no lo malo— no queda nada.

El resto del efecto día de la semana se disuelve al quitar las nóminas: los
viernes normales dan +0,0681 con t = 1,46 y segunda mitad +0,0309. Quitar lunes
y miércoles mide mejor (+0,0949, t = 4,00) pero esos días se eligieron mirando
el histórico entero. El walk-forward honesto da +0,0972 frente a +0,0501, pero
la ventaja depende de un solo año (2021, +0,40 de diferencia); sin él la media
cae a +0,022 con 9 de 14 años. El conjunto de días que elige cambia cada año
(MJV, MXJV, XJV, XV, V, LV, LJV, LMJV): es ruido. **No se implementa.**

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

* 14 años positivos de 20, no 20. **De 2017 a 2020 perdió cuatro años seguidos**
  incluso con spread de 0,60 $.
* Acierta el 44,7 %. La mayoría de los días la operación pierde.
* Con el spread actual del usuario (1,45-2 $) **no se enviará ningún plan**, y
  eso es correcto: la ventaja medida a ese coste es negativa.


---

## Indicios anticipados: dos fuentes que NO son precio del oro

La pregunta era la buena: *indicios reales de lo que va a hacer el precio antes
de que lo haga*. Se probaron las dos únicas fuentes gratuitas alcanzables desde
el entorno (Yahoo, FRED y Stooq están bloqueados).

### 1. Posicionamiento COT de la CFTC — descartado

870 semanas (2010-2026) del informe desagregado del oro: posiciones declaradas
del dinero gestionado y de los comerciales. 5 hipótesis pre-declaradas × 3
horizontes (1, 2 y 4 semanas) = 15 contrastes. Bonferroni: t > 2,93.

| Hipótesis | Mejor \|t\| de los 3 horizontes |
|---|---|
| fondos muy largos → baja (contrario) | 0,77 |
| aumenta posición larga → sigue subiendo | 1,66 |
| z de fondos, exposición continua | 0,65 |
| comerciales muy cortos → baja | 1,50 |
| z de comerciales, exposición continua | 1,91 |

**Los 15 fallan, y 13 de los 15 tienen media negativa.** El posicionamiento
declarado no anticipa el precio del oro a ningún horizonte.

*Trampa esquivada:* el informe es del martes pero se publica el viernes a las
15:30 ET. Se usa desde el lunes siguiente. Con la fecha del martes se estaría
mirando el futuro tres días, y con eso casi cualquier cosa parece funcionar.

*Fallo propio:* la CFTC cambió de columna de fecha hacia 2013. La primera
versión solo interpretaba hasta 2012 y medía tres años creyendo que medía
diecisiete, sin dar ningún error. Se caza con un `assert` sobre las fechas.

### 2. El dólar (EUR/USD horario de Dukascopy) — descartado, y es instructivo

122.739 velas horarias, 2007-2026, la misma tubería y la misma hora que el oro.
El diseño separa **anticipar** de **acompañar**:

| Hipótesis | Diferencia a favor/en contra | t |
|---|---|---|
| H1 dólar en la mañana de Londres (3-8 ET), **antes** | +0,0004 | **0,01** |
| H2 dólar en la sesión asiática (0-3 ET), **antes** | +0,0145 | 0,26 |
| H4 dólar **durante** la sesión (8-16 ET) — control | +0,9956 | **18,06** |

El control es abrumador y las dos anticipadas son exactamente cero. El dólar
explica el movimiento del oro **a la vez que ocurre**, no antes.

Con retrasos, la correlación horaria se desploma de golpe:

| Retraso | Correlación |
|---|---|
| misma hora | **−0,355** |
| 1 hora | +0,003 |
| 2 horas | +0,003 |
| 24 horas | +0,004 |

Un matiz que parece una excepción y no lo es: el dólar de la mañana de Londres
**sí acierta el lado por el que rompe el oro el 58,1 % de las veces** (z = 10,4).
Pero eso es mecánico —si el dólar ha caído, el oro ha subido y está pegado al
techo del rango, así que romperá por arriba— y **no dice nada del resultado**
(H1: t = 0,01). Además el sistema deja las dos órdenes puestas, así que saber
cuál saltará no vale nada. Acertar el lado y no acertar la continuación es
justamente la diferencia entre parecer que predices y predecir.

### Conclusión

El dólar explica el 13-14 % de la varianza del oro, y lo explica en tiempo real.
Para anticipar el oro por esa vía habría que anticipar el dólar, que es el
mercado más líquido del planeta. Ninguna de las dos fuentes aporta un indicio
anticipado utilizable.


---

## Intentos de rescatar el motor intradía de señales

El motor de señales técnicas (`oro/senales`) tiene una ventaja **bruta** de
+0,025 a +0,030 R por operación sobre 4.410 entradas de 19,6 años, con 1R
valiendo 7,4 $ de media. Su spread de equilibrio son 0,15 $. Estos son todos los
intentos de hacerlo viable, con su resultado.

### Lo probado antes

| Intento | Resultado |
|---|---|
| Predecir la dirección (ML) | AUC 0,489-0,520: moneda al aire |
| Filtrar por régimen de volatilidad | el efecto se evapora con más datos (p = 0,40) |
| Filtrar por coste | trampa de minería: selecciona años recientes |
| Ensanchar el stop (2-4 × ATR) | baja el coste en R y hunde la ventaja: se cancelan |
| Subir de marco (H2, H4) | lo mismo: 0,195 R → 0,099 R de coste, +0,0277 → +0,0062 de ventaja |
| Operar solo despierto | la ventaja vive de noche (35 % de las entradas, 00-07 Madrid) |

### Contexto de sesión como filtro — descartado por LOOKAHEAD

La idea: la ruptura del rango de Londres dice si el día es direccional y hacia
dónde. Filtrar las señales técnicas para que vayan a favor.

Medido en crudo parecía extraordinario:

| Filtro | Bruto | Neto 0,60 $ | t |
|---|---|---|---|
| sin filtro | −0,0611 | −0,1771 | −12,08 |
| **a favor de la ruptura** | **+0,1647** | **+0,0507** | **2,49** |
| en contra de la ruptura | −0,3852 | −0,5063 | −19,67 |

*(Estas cifras usan la política de salida antigua, por eso la referencia sale
negativa en bruto; lo comparable entre sí es la diferencia, no el nivel.)*

**Y es lookahead.** La dirección de la ruptura no se conoce hasta las 10:00 ET,
pero el filtro se estaba aplicando también a señales de la madrugada. Separando
por si la ruptura ya se conocía:

| | Bruto | Neto | t |
|---|---|---|---|
| señales **posteriores** a la ruptura, a favor | −0,0486 | −0,1585 | −6,93 |
| señales **posteriores**, en contra | −0,0434 | −0,1615 | −4,06 |
| señales **anteriores**, «a favor» *(lookahead)* | **+0,6060** | +0,4836 | 13,66 |

Una vez se conoce la ruptura, el filtro no distingue nada: a favor y en contra
rinden igual. Todo el efecto vivía en señales de madrugada «alineadas» con una
ruptura que aún no había ocurrido, que es una forma elegante de decir «las
señales que acertaron acertaron».

### Colocación estructural del stop — descartado

El ancho del stop ya estaba medido, pero no *dónde* se pone. La ruptura funciona
porque su stop está donde el mercado invalida la idea, no a una distancia
arbitraria. Con la salida actual (objetivo 2R + stop dinámico 1R + cierre
intradía):

| Colocación | 1R en $ | Bruto | Neto 0,60 $ | t |
|---|---|---|---|---|
| 1,5 × ATR *(el actual)* | 7,4 | +0,0247 | −0,0912 | −7,22 |
| mínimo/máximo de 6 velas | 7,1 | +0,0107 | −0,1565 | −10,69 |
| mínimo/máximo de 12 velas | 12,2 | +0,0133 | −0,0796 | −7,10 |
| mínimo/máximo de 24 velas | 19,5 | +0,0153 | **−0,0399** | −4,65 |
| borde del rango de Londres | 10,1 | −0,0532 | −0,1920 | −14,36 |

El stop de 24 velas hace que 1R valga 19,5 $ en vez de 7,4 $, con lo que el
spread pesa menos de la mitad. Pero la ventaja bruta baja de +0,0247 a +0,0153 y
el neto sigue claramente negativo. Es la misma cancelación de siempre.

### Estado

Con esto se han probado siete vías distintas. Ninguna deja al motor de señales
en positivo a un coste alcanzable. La única estrategia intradía del proyecto con
ventaja medida y sostenida sigue siendo la ruptura del rango de sesión, que
también abre y cierra el mismo día.


---

## Marcar la orden con más confianza: el análisis completo

Petición: *analizar y marcar la opción que más confianza aporte de cumplirse,
con un análisis previo*. Esto es lo que salió.

### Un modelo con 8 condiciones — NO funciona

Todo lo conocido a las 8:00 ET sin mirar el futuro: sesión asiática (cuerpo y
fuerza), dólar en la madrugada y en la mañana de Londres (EUR/USD invertido),
dónde cierra Londres dentro de su rango, precio vs medias de 5 y 20 días,
anchura del rango, posición respecto al cierre de ayer. Ridge entrenada con los
5 años anteriores, puntuando el año siguiente.

| Cuartil de puntuación (fuera de muestra) | n | R/op | Acierto |
|---|---|---|---|
| peor | 747 | **+0,0750** | 46,1 % |
| 2º | 747 | +0,0641 | 46,2 % |
| 3º | 746 | +0,0881 | 44,4 % |
| **mejor** | 747 | **+0,0380** | 41,2 % |

El cuartil «mejor» rinde **menos** que el «peor». La diferencia media entre
mitades es +0,0229 R con **t = 0,71** y 9 de 15 años a favor. No separa nada.

### La sesión asiática sola — sí aguanta

Regla fija, sin entrenar, medida año por año (cada año es una observación
independiente, así que el t no está inflado por solapamiento):

| | |
|---|---|
| Diferencia media (marcada − la otra) | **+0,0930 R** |
| Años a favor | **14 de 20** |
| t | **2,31** |
| Últimos 5 años | +0,0862 R, 4 de 5 a favor |

2025 fue el peor año (−0,2975), lo que explica la impresión reciente de que
falla.

### No se puede graduar

Si el efecto creciera con la fuerza del movimiento asiático habría relación
dosis-respuesta, que es mucho más difícil de falsificar por azar. No la hay:

| Cuerpo asiático | Diferencia | t |
|---|---|---|
| 0-10 % del rango | +0,0675 | 0,59 |
| 10-20 % | +0,0394 | 0,33 |
| 20-35 % | +0,1493 | 1,58 |
| 35-50 % | +0,0538 | 0,55 |
| 50-100 % | +0,0902 | 1,52 |

Sube y baja sin orden. La confianza se queda binaria: hay sesgo o no lo hay.

### Cómo se presenta

La marca vuelve al correo —se pidió— pero redactada **en condicional**:
`◆ LA MEJOR SI SALTA`. Nunca «esta es la que va a pasar», porque cuál salta es
50,0 % (z = 0,00) y presentarlo como predicción hacía que pareciera fallar el
49 % de los días. Y el correo dice de dónde sale, incluido que el modelo de 8
condiciones no funcionó.
