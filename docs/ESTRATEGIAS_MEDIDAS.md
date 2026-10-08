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

---

# La auditoría de octubre de 2026 y la estrategia que salió de ella

Se pidió una auditoría de lo que el programa había aprendido. Para contestarla
hubo que bajar el histórico entero (**124.718 velas H1, 2006-2026, 249 meses de
Dukascopy**) y reconstruir todas las operaciones que el sistema habría
planteado. Lo que salió cambió la estrategia.

## Lo que se encontró primero: el aprendizaje no podía aprender

`oro/aprender.py` leía **solo** `operaciones_oro.jsonl` —las operaciones
enviadas en vivo— y exigía 50 para empezar. Llevaba meses parado en
«datos insuficientes» con 22, mientras había más de dos mil operaciones en el
histórico calculables con las **mismas** funciones (`construir_features` es la
misma en los dos caminos). No era una limitación: era un fallo de diseño.

## El motor intradía de señales: pierde en 19 de 21 años

Reconstruido con la configuración exacta de producción (`r_objetivos=(2.0,)`,
`atr_stop_mult=1.5`, `trailing_desde_entrada=True`), **4.891 operaciones**:

| | valor |
|---|---|
| R bruto medio | **−0,0314** (t = −2,43) |
| R neto medio (coste 0,30 $) | **−0,0899** (t = −6,94) |
| Años positivos | **2 de 21** |
| R acumulado | **−439,5** |

A 0,25 % de riesgo son **−157 €/año** sobre 3.000 €. Los dos años positivos son
2025 y 2026: la ventana en la que se construyó y se ajustó el sistema.

### No es el coste, y conviene no engañarse con eso

La primera explicación —que el 1R en dólares era pequeño en los años antiguos y
el spread pesaba más— **es falsa**, y la prueba que la separa es esta:

| población | n | bruto | neto |
|---|---|---|---|
| 1R ≥ 10 $, todo el histórico | 673 | +0,0648 | +0,0458 |
| **1R ≥ 10 $ pero antes de 2025** | **303** | **+0,0046** | **−0,0197** |

Si fuera el coste, las operaciones de 1R grande de 2006-2024 también ganarían.
No ganan (t = 0,09). Toda la ventaja vive en 2025-2026.

### Ninguna salida lo rescata

Seis variantes de salida sobre 2019, 2022 y 2024 (714 operaciones): producción
−0,1141, sin trailing desde la entrada −0,1095, sin trailing −0,1095, objetivo
3R −0,1000, objetivo 3R sin trailing −0,1117, stop 2,5×ATR −0,0579. **Todas
negativas en bruto.** El problema son las entradas.

### Ningún modelo lo filtra, con 21 años de datos

Walk-forward entrenando con los años anteriores y puntuando el siguiente, 18
veces, **4.294 operaciones fuera de muestra**:

| cuartil de puntuación | n | R/op | acierto |
|---|---|---|---|
| peor | 1074 | **−0,0738** | 34,6 % |
| 2º | 1073 | −0,1235 | 34,1 % |
| 3º | 1073 | −0,0700 | 38,0 % |
| **mejor** | 1074 | **−0,0900** | 35,0 % |

AUC medio **0,5054**, t = 0,63 frente a 0,50, 10 de 18 años por encima. El
cuartil «mejor» rinde menos que el «peor»: es la cuarta vez que esa inversión
aparece en este proyecto.

### Los motivos de entrada son adorno

93 motivos distintos (el valor del indicador va dentro del texto, así que cada
ADX y cada RSI es su propio motivo). De los 50 con n ≥ 100, **ninguno pasa
Bonferroni** (|t| > 3,29; el mejor da 2,87). Y la prueba que lo cierra:

| motivo | n | diferencia | t |
|---|---|---|---|
| «no es un mercado parado (ADX **28**)» | 152 | **−0,1724** | −2,77 |
| «no es un mercado parado (ADX **29**)» | 141 | **+0,1826** | +2,20 |

Enteros adyacentes, signos opuestos, los dos cerca de «significativo». Un
efecto real no cambia de signo entre 28 y 29.

## La ruptura de sesión: la contabilidad del coste estaba mal

Reconstruidas sus **4.672 operaciones**. El bruto reproduce lo documentado
(+0,0606 contra +0,0687; y para la variante con stop a BE, +0,0740 contra
+0,0768), así que la tubería de medición coincide. El neto no:

| coste | global | t | 1ª mitad | 2ª mitad |
|---|---|---|---|---|
| 0 $ (bruto) | +0,0606 | 3,35 | +0,0874 | +0,0354 |
| **0,30 $ (el del sistema)** | **+0,0133** | **0,74** | +0,0358 | **−0,0079** |
| 0,60 $ (el citado antes) | **−0,0340** | −1,88 | −0,0158 | −0,0511 |

La tabla de más arriba en este documento afirma +0,0552 con t = 3,01 y las dos
mitades positivas **«netas de 0,60 $»**. Con 0,60 $ sale −0,0340. La fórmula
usada aquí es `spread / amplitud_del_rango`, que es **la misma que usa el
sistema en vivo** (`coste_r` en `oro_rupturas.jsonl`: 0,30/34,94 = 0,0086). Las
cifras netas antiguas eran optimistas.

## Lo que sí funciona, y es la estrategia que va puesta

### Solo la rotura a la BAJA

| lado | n | R/op | t | 1ª mitad | 2ª mitad | años + |
|---|---|---|---|---|---|---|
| **venta** | 2117 | **+0,1069** | **4,02** | +0,1339 | +0,0789 | 14/21 |
| compra | 2529 | −0,0638 | −2,56 | −0,0549 | −0,0714 | 4/21 |

Las compras no son más débiles: son un lastre de **−7,7 R al año**.

### Y solo si es la PRIMERA rotura del día

Esto es el hallazgo que define la estrategia. No vale «vender oro»: lo que
funciona es la rotura a la baja que ocurre **primera**. La misma rotura, cuando
llega después de que el rango se haya roto al alza, es un latigazo que se gira:

| población de días | n | R/op | t | años + |
|---|---|---|---|---|
| rompe abajo primero (se opera) | 2117 | **+0,1069** | 4,02 | 14/21 |
| rompe arriba y **luego** abajo (se anula) | 869 | **−0,2863** | **−8,73** | 2/21 |
| las dos juntas | 2986 | −0,0075 | −0,35 | 10/21 |

**Si la orden de venta se queda puesta cuando el rango rompe al alza, la
ventaja no baja: desaparece** (−1,07 R/año en lugar de +10,78). De ahí que la
anulación sea un aviso propio (`EstadoPlan.ANULADO`) y no una nota al pie.

Esto explica además las 12 operaciones en vivo de septiembre: el sistema tomaba
la que saltara primero, así que dio el lado malo 10 de 12 veces. Las 2 ventas
promediaron +0,684 R y las 10 compras −0,453 R.

### La salida

Siete variantes declaradas antes de medir, sobre las 2.117 ventas:

| salida | bruto | neto | t | 1ª | 2ª | R/año |
|---|---|---|---|---|---|---|
| sin objetivo, sin mover stop | +0,1419 | +0,0956 | 3,48 | +0,1227 | +0,0674 | +9,64 |
| **sin objetivo + BE en 1R** | **+0,1533** | **+0,1069** | **4,02** | +0,1339 | +0,0789 | **+10,78** |
| sin objetivo + BE en 1,5R | +0,1527 | +0,1064 | 3,92 | +0,1344 | +0,0772 | +10,72 |
| sin objetivo + trailing 1R | +0,1628 | +0,1164 | 4,80 | +0,1390 | +0,0929 | +11,74 |
| objetivo 6R + BE en 1R | +0,1534 | +0,1071 | 4,08 | +0,1376 | +0,0753 | +10,80 |
| objetivo 3R + BE en 1R | +0,1451 | +0,0988 | 4,07 | +0,1279 | +0,0684 | +9,96 |
| objetivo 2R | +0,1258 | +0,0795 | 3,44 | +0,0903 | +0,0682 | +8,01 |

El trailing gana por 0,01 R y **no se elige**: su medición es optimista, porque
coloca el stop con el pico de la misma vela y solo comprueba si salta en la
siguiente. Dentro de una vela de una hora no se sabe el orden. Se queda el
**break-even en 1R**, que es casi igual, es una sola acción para quien opera, y
no depende de un supuesto que no se puede verificar con velas horarias.

### Robustez

11 perturbaciones de horario (rango 2-8, 4-8, 3-7, 3-9; validez 1h, 3h, 4h;
cierre a las 14 y 15 ET; velas mínimas 3): **las 11 positivas**, 10 de ellas con
las dos mitades positivas (solo falla rango 3-9). Quitando a la vez el mejor y
el peor año quedan **+0,0989 R/op con t = 3,84** y 13 de 19 años a favor. Con 31
pruebas acumuladas en el estudio, Bonferroni exige |t| > 3,25, y el resultado
da 4,02.

### Medido otra vez, con el código de producción

`python -m oro.historico` no reimplementa nada: llama a `construir_plan` y
`seguir`, las que deciden en vivo. **2.131 operaciones:**

| | valor |
|---|---|
| R neto medio | **+0,1143** (t = 4,37) |
| Mitades bloqueadas | +0,1270 (t = 3,32) / +0,1009 (t = 2,84) |
| Años positivos | **17 de 21** |
| R al año | **+11,59** |
| Acierto | 40,0 % (ganadora +1,205 R, perdedora −0,612 R) |
| Peor año | −8,3 R (2009) |
| Peor racha | −23,0 R |
| Días anulados | 2.182 de 5.370 con plan (41 %) |

A 0,5 % de riesgo sobre 3.000 € son **+174 €/año**, con un peor año de −125 € y
una peor racha de −345 €.

## Un fallo propio que conviene dejar escrito

Al optimizar el número de operaciones, «validez 8h + reentrada» dio +0,0811
R/op con **t = 5,77** y 20 de 21 años positivos: cinco veces mejor que todo lo
demás. Era un fallo. El **55,7 % de las segundas entradas tenían relleno
imposible**: el precio ya estaba fuera del nivel, así que entrar a ese nivel
exigía un precio que el mercado nunca dio. Corregido, los +27,75 R/año se
quedan en +1,36 y el t desaparece.

La regla que lo detectó: para una venta, la vela que dispara tiene que **abrir
en o por encima** del nivel. Si abre por debajo, el relleno real es la apertura,
no el nivel. Vale para cualquier medición de órdenes stop, y conviene aplicarla
siempre que un resultado parezca demasiado bueno.

## Limitaciones honestas de todo lo anterior

* **El instrumento no es el mismo.** La investigación usa XAU/USD **al contado**
  de Dukascopy; el motor en vivo usa Yahoo **`GC=F`, futuros de COMEX**. La base
  medida en septiembre de 2026 fue de +40,17 $ y derivó de 48,63 a 31,70 en el
  mes. Los rangos H1 del futuro son un 1,5 % más anchos (t = 5,08, mayores en el
  72 % de las horas). Que la estrategia sea intradía es lo que lo hace
  soportable: 0,7 $/día de convergencia sobre un 1R de 35 $ son 0,002 R en unas
  horas. No hay forma gratuita de validar 20 años de futuros en H1 (Yahoo da
  ~45 días), así que **ninguna ventaja de este sistema se ha medido nunca sobre
  el instrumento que de verdad opera**.
* **Los años antiguos tienen rangos diminutos.** En 2006 el rango de Londres
  medía 1,13 $ y el coste en R llegaba al 26 %. En esos días la ejecución real
  sería peor que la simulada (distancia mínima de stop, spread proporcionalmente
  mayor). Filtrar por coste en R se midió y **empeora el R al año**, así que no
  se filtra, pero el resultado de 2006-2010 hay que leerlo con esa reserva.
* **101 operaciones al año no demuestran nada rápido.** Para distinguir
  +0,114 R de cero al 80 % de potencia hacen falta ~690 operaciones, unos
  **6 años**. La vigilancia de `oro/aprender.py` existe precisamente porque la
  media tarda, mientras que el acierto y la forma de las salidas convergen
  antes.

---

## Decisiones tomadas tras la auditoría

### El motor de señales intradía queda APAGADO

`ConfiguracionSistema.senales_activas = False`. No deja de ejecutarse el
vigilante —en su bucle atiende también el seguimiento de la ruptura— pero no
abre operaciones nuevas. Las razones están arriba: −0,0899 R netos por
operación sobre 4.891 operaciones de 21 años, 2 años positivos de 21, −439,5 R
acumulados, −157 €/año a 0,25 % de riesgo. Y lo que lo cierra: seis variantes
de salida negativas **en bruto**, un walk-forward con AUC 0,5054 que ordena al
revés, y 93 motivos de los que ninguno pasa Bonferroni.

Se enciende otra vez con `ORO_SENALES_ACTIVAS=1`. Las operaciones que estuvieran
abiertas se siguen gestionando y cerrando: la compuerta está solo en la entrada.

### El instrumento que se opera no es el que se investigó, y ahora se dice

Yahoo **no sirve XAU/USD al contado en velas horarias**: `XAUUSD=X`, `XAU=X` y
`GCUSD=X` devuelven 404, y `^XAU` es el índice de mineras (cotiza a 361). El
único feed horario gratuito es **`GC=F`, el futuro de oro de COMEX**.

Toda la investigación de este documento está medida sobre el contado de
Dukascopy. Eso no se puede arreglar —Yahoo da ~45 días de histórico horario de
futuros— así que se **declara**:

* `ConfiguracionSistema.simbolo_vivo` separa el símbolo de investigación
  (`XAUUSD`, Dukascopy) del que se opera (`GC=F`, Yahoo). Antes `ProveedorYahoo`
  usaba su propio `GC=F` por defecto y nadie le pasaba `cfg.simbolo`: la
  configuración decía una cosa y el sistema hacía otra.
* El correo del plan lleva una línea diciendo de dónde salen los precios y que,
  si el bróker cotiza el contado, marcará 30-50 $ menos. **Es el fallo más caro
  posible** —las órdenes se ejecutarían al instante en vez de esperar a la
  ruptura— y el sistema no puede detectarlo, porque solo ve un feed.

### Los avisos de la sesión van en tarjeta

Salían en texto plano, todos con el mismo aspecto. El de CANCELAR es el que
sostiene la ventaja (sin él, +10,78 R/año se quedan en −1,07), así que ahora
lleva cabecera roja, el precio que anula la orden en grande y texto blanco
—sobre `#F04438` el texto oscuro se queda por debajo del contraste legible.

---

# El coste, por fin medido (octubre de 2026)

`coste_operacion` valía **0,30 $ porque alguien lo puso**. El coste es la
restricción que decide todas las estrategias de este proyecto —está en cada R
que el sistema registra y en cada conclusión de este documento— así que un coste
inventado invalida lo demás.

## Lo que se buscó

Se probaron todas las fuentes gratuitas de oro al contado en velas horarias:

| fuente | resultado |
|---|---|
| Yahoo `XAUUSD=X`, `XAU=X`, `GCUSD=X` | **404** |
| Yahoo `^XAU` | es el índice de **mineras** (cotiza a 361) |
| Yahoo `GC=F`, `MGC=F` | funcionan, pero son **futuros** de COMEX |
| Stooq `xauusd` | devuelve HTML, no CSV: bloqueado |
| Binance `PAXGUSDT` | **451** (bloqueo legal), y PAXG no es oro al contado |
| exchangerate.host, frankfurter | solo diario |
| **Dukascopy ticks** | **contado, con bid y ask reales** |

## Lo que da Dukascopy y nadie más

Ficheros de ticks por hora, `…/XAUUSD/AAAA/MM/DD/HHh_ticks.bi5`, con **bid y ask
reales** y 10.000-17.000 ticks por hora. Sondeado el 5-oct-2026: la hora que
cerró a las 11:00 estuvo disponible **a los 2,2 minutos**. (El fichero MENSUAL
de velas H1 no existe para el mes en curso: 503 tras 12 reintentos. Por eso hay
que armar las velas desde los ticks.)

## El spread real

3.189.713 ticks, 230 horas, 20 días de mercado:

| hora UTC | hora ET | mediana $ | |
|---|---|---|---|
| 0 | 20 | 0,802 | |
| 7-11 | 3-7 | 0,575 | ventana del rango |
| **12-13** | **8-9** | **0,595** | **ventana de disparo** |
| 14 | 10 | 0,605 | |
| **19-20** | **15-16** | **0,680** | **cierre de sesión** |
| 22 | 18 | 0,810 | |

**El doble de lo que se asumía.** `coste_operacion` pasa a **0,60 $**, y
`python -m oro.spread` lo vuelve a medir cuando haga falta.

### Y por años, porque un coste fijo también es falso hacia atrás

| periodo | spread $ | puntos básicos |
|---|---|---|
| 2007-2011 | 0,45-0,55 | 2,7-6,9 |
| 2013-2016 | 0,29-0,30 | 2,1-2,6 |
| 2018-2022 | 0,22-0,39 | 1,7-2,2 |
| 2024 | 0,373 | 1,53 |
| 2025 | 0,550 | 1,64 |
| **2026** | **0,630** | **1,35** |

En dólares sube con el oro; en puntos básicos no ha parado de mejorar. La tabla
vive en `oro.spread.SPREAD_POR_ANIO` y `oro/historico.py` la usa: cobrarle a
2016 el spread de 2026 dejaría el histórico en +0,0680 R/op en vez de +0,1030.

## Qué le hace a la estrategia

| modelo de coste | R/op | t | 1ª mitad | 2ª mitad | R/año |
|---|---|---|---|---|---|
| 0,30 $ fijo (lo que se suponía) | +0,1143 | 4,37 | +0,1270 | +0,1009 | +11,59 |
| **spread real de cada año** | **+0,1030** | **3,93** | +0,1067 | +0,0990 | **+10,45** |
| 1,5 spreads | +0,0742 | 2,83 | +0,0713 | +0,0771 | +7,53 |
| 2 spreads (cota) | +0,0454 | 1,73 | +0,0360 | +0,0553 | +4,60 |
| 3 spreads | −0,0122 | −0,46 | −0,0348 | +0,0116 | −1,24 |

**Aguanta el coste real y aguanta el doble; a tres spreads muere.** Las cotas
importan porque el nivel del rango se mide sobre BID: la venta entra a bid (sin
coste) y el cierre compra a ask (un spread), pero el STOP se dispara cuando el
ASK llega al máximo, o sea **antes** de lo que ve la simulación. Esa media parte
no está en el modelo de un spread.

En las condiciones de hoy —1R de 31,5 $ y spread de 0,63 $— sale **+0,0995 R por
operación**: el coste pesa 0,020 R, un tercio de la media histórica (0,0575 R),
porque el rango de Londres es mucho más ancho que cuando el oro valía 1.200 $.

## La fuente en vivo: disponible, no activada

`oro/datos/dukascopy_vivo.py` arma velas H1 del contado desde los ticks.
`ORO_FUENTE_VIVO=dukascopy` lo enciende. **No va puesto**, por dos razones:

1. Cambiar la fuente mueve los niveles del correo unos 40 $, y cuál es el bueno
   depende de qué cotice el bróker de quien opera. Desde el sistema no se puede
   saber: solo ve un feed.
2. Dukascopy no publica la hora EN CURSO, así que el seguimiento reaccionaría
   hasta una hora más tarde. Yahoo sirve la vela a medias. Para el aviso de
   cancelar —el que sostiene la ventaja— eso importa.

Lo que sí se arregló para poder usarlo: se pedían **400 velas** en vivo, que era
el calentamiento del motor intradía (EMA 200). La ruptura solo mira el día de
sesión, y está medido sobre el código real que **con 8 velas sale el mismo plan
y el mismo resultado**. Ahora se piden 48. Con 400, una fuente que va hora a
hora necesita 628 peticiones y más de media hora por ciclo.

---

# TradingView y gold.org, probadas

Se pidió probar las dos como alternativas. Esto es lo que dieron.

## TradingView: no

| endpoint | resultado |
|---|---|
| `scanner.tradingview.com/forex/scan` (GET) | 200, **6.333 pares — ninguno es XAU/USD** (los dos «XAU» son UGX/AUD y EUR/AUD) |
| el mismo con POST y tickers de oro | `{"totalCount":0,"data":[]}` |
| `symbol-search.tradingview.com` | **403** |
| `api.tradingview.com/history` | sin respuesta |

No hay API pública gratuita, el scanner no lleva oro al contado, y sus
condiciones de uso prohíben el scraping y la redistribución. Aunque se pudiera
forzar, un workflow que depende de un endpoint no documentado es exactamente la
fragilidad que ya costó semanas de correos perdidos en este proyecto.

## gold.org / Goldhub: sí, pero no para operar

La API real es `fsapi.gold.org/api/goldprice/v13/chart/main` (se saca del HTML
de la página de precios). Da 16 series: `lbma_am_usd`, `lbma_pm_usd`, las mismas
en GBP y EUR, `sge_am_cny` (Shanghái), `lme_*`, `mcx_*` (India). 383 puntos de
los últimos 3 años.

**Es diario.** Para una estrategia que opera roturas de rangos horarios no sirve
como fuente de precios, y nunca va a servir.

### Pero vale para algo que al proyecto le hacía falta

El LBMA Gold Price es el **precio de referencia oficial del oro al contado**:
el que se fija en subasta dos veces al día y contra el que se liquida medio
mercado. Eso lo convierte en un árbitro de fuera, y este proyecto acababa de
descubrir que lo necesitaba: durante semanas calculó los niveles sobre el futuro
de COMEX mientras el correo pedía operar XAU/USD, y nadie se enteró porque el
sistema solo veía un feed y un feed no puede contradecirse a sí mismo.

Comparando a la MISMA hora (la vela de las 09:00 UTC, que contiene la subasta AM
de las 10:30 de Londres):

| fuente | diferencia media | \|dif\| mediana | n |
|---|---|---|---|
| **Dukascopy contado** | **+3,34 $** | 3,99 $ | 21 |
| Yahoo `GC=F` (futuro) | **+43,08 $** | 44,62 $ | 16 |

Los 3-4 $ del contado son la deriva de los 30 minutos entre la subasta y el
cierre de la vela. Los 43 $ del futuro son la prima del contrato.

**Eso zanja la pregunta que quedaba abierta.** El correo dice «busca XAU/USD
(oro)», que es el contado por definición, mientras los niveles salían del
futuro. Las dos cosas no pueden ser correctas.

### Cómo se usa: ¿cae el fix dentro de la vela en que se subastó?

La subasta se hace a precios que se negocian en ese momento, así que el fix
tiene que caer dentro del máximo y el mínimo de la vela horaria que contiene
las 10:30 de Londres:

| fuente | el fix cae dentro de la vela |
|---|---|
| Dukascopy contado | **32 de 32 días** |
| Yahoo `GC=F` futuro | **0 de 16 días** (fuera por 35,66 $ de media) |

Separación perfecta y con **un solo día** ya decide. El árbitro pide él mismo
las 3 velas que necesita (3 peticiones) en vez de mirar el marco del plan.

*Fallo propio, cazado antes de que llegara a producción:* la primera versión
comparaba una media de 5 días sobre el marco que carga el plan. Ese marco son
48 horas —unos 2 días—, así que en vivo no habría tenido nunca 5 días y **no se
habría activado jamás**, dando siempre por bueno el precio sin decirlo.

Si el árbitro dice que no, **no se manda el plan**. Un día sin plan es mucho
mejor que un plan con niveles que en la pantalla del bróker no existen. Si la
web de gold.org no responde, se sigue adelante avisando de que esta vez no hubo
árbitro: es una comprobación, no una dependencia.

## La fuente en vivo pasa a ser el contado

`fuente_vivo` queda en **`dukascopy`**. Lo que se pierde: no publica la hora en
curso, así que los avisos del seguimiento llegan hasta una hora más tarde (Yahoo
servía la vela a medias). Se acepta porque un aviso tardío es un coste ocasional
y un instrumento equivocado es un error permanente. `ORO_FUENTE_VIVO=yahoo` lo
revierte.

---

# CFTC, FRED y el resto de fuentes macro, contra la estrategia actual

Se pidió analizar el informe COT de la CFTC y FRED (Reserva Federal de St. Louis)
y aprovechar lo que sirviera. La pregunta ahora es distinta de la de antes: no
«¿anticipa X la dirección del oro?» (ya medido, no), sino «¿mejora X la VENTA en
la rotura del rango de Londres?».

## Las fuentes

| fuente | acceso | qué da |
|---|---|---|
| **CFTC** (API Socrata) | ✓ | COT desagregado del oro, 1.060 semanas (2006-2026) |
| **Tesoro de EE. UU.** | ✓ | tipos reales (TIPS) y nominales a 10 años, 5.443 días |
| **CBOE** | ✓ | **GVZ** (volatilidad implícita del oro, desde 2009) y VIX |
| **Fed** | ✓ | fechas de las reuniones del FOMC, 2006-2026 |
| FRED (web) | ✗ | no responde desde el entorno de desarrollo |
| FRED (API) | clave | responde pero exige `api_key` (gratuita) |
| BLS | ✗ | 403 |

Los datos de FRED que interesaban (tipos reales, inflación esperada, VIX) se
sacaron de sus fuentes primarias. La API de FRED solo haría falta para una
cosa que no da ninguna otra: las fechas del IPC (ver al final).

## Ocho hipótesis declaradas antes de mirar

Todas son condiciones conocidas antes de las 8:00 ET. Sin futuro: datos diarios
del día anterior; COT desde el lunes siguiente a su publicación.

| hipótesis | R/op sí | R/op no | dif | t | mitades |
|---|---|---|---|---|---|
| tipos reales subiendo (5 sesiones) | +0,154 | +0,057 | +0,097 | 1,84 | +0,210 / **−0,022** |
| inflación esperada cayendo | +0,121 | +0,087 | +0,033 | 0,63 | +0,153 / −0,093 |
| GVZ por encima de su mediana | +0,072 | +0,174 | −0,102 | −1,73 | −0,095 / −0,098 |
| VIX por encima de su mediana | +0,082 | +0,121 | −0,040 | −0,76 | −0,038 / −0,041 |
| fondos muy largos (COT) | +0,158 | +0,104 | +0,054 | 0,86 | +0,002 / +0,099 |
| fondos vendiendo (COT) | +0,086 | +0,133 | −0,047 | −0,87 | +0,027 / −0,120 |
| oro bajo su media de 50 | +0,116 | +0,093 | +0,023 | 0,43 | +0,038 / +0,005 |
| GVZ subiendo | +0,096 | +0,146 | −0,050 | −0,85 | −0,108 / −0,011 |

**Ninguna pasa** (Bonferroni para 8: |t| > 2,73). La mejor, los tipos reales,
sale entera de la primera mitad. Y **ningún filtro mejora el R al año**: todos
lo bajan.

**Lo útil está en otra lectura: la estrategia es positiva a los DOS lados de
las ocho condiciones.** No depende de los tipos, ni de la volatilidad, ni del
posicionamiento de los fondos, ni de la tendencia. Su ventaja no es una
apuesta macro disfrazada.

## El dato de empleo: lo que sí aguanta

El informe de empleo de EE. UU. (NFP) sale a las 8:30 ET, **dentro de la
ventana en que salta la orden**. La fecha se calcula con la regla del propio
BLS (tercer viernes tras la semana del día 12, con la excepción de enero) y
acierta las 10 publicaciones reales con que se comprobó.

Hipótesis 9 (declarada antes de mirar): la venta rinde distinto ese día.

| | n | R/op | t | mitades |
|---|---|---|---|---|
| días de empleo | 83 | +0,724 | 3,52 | +0,663 / +0,632 |
| resto | 2.048 | +0,078 | | |

### La objeción de siempre, medida por fin: el deslizamiento

Una sesión anterior vio esto mismo con dos órdenes (+0,53 R, t = 4,47) y lo
**descartó**, suponiendo 2 $ de deslizamiento a las 8:30 sin poder medirlo.
Con los ticks se mide el relleno REAL: el primer tick cuyo bid cruza el nivel.

| | deslizamiento mediana | media | p90 | máx |
|---|---|---|---|---|
| 83 días de empleo | 0,10 $ | 1,31 $ | 2,30 $ | 34,55 $ |
| 80 días normales (control) | 0,04 $ | 0,25 $ | 0,29 $ | 10,32 $ |

Con el relleno real, la venta del día de empleo da **+0,565 R (t = 2,83)**. El
primer tick que cruza el nivel cae a las **12:30 o 13:30 UTC**: las 8:30 ET
exactas. El efecto es el dato mismo.

Y el control destapó otra cosa: en días normales el deslizamiento medio es
0,033 R por operación, un coste que la estrategia **no estaba cobrando**. Con él,
la cifra de toda la estrategia baja de +0,103 a +0,065 R.

### Hipótesis 11: ese día, también la compra

Si el efecto es «el dato provoca un movimiento decidido», debería valer en las
dos direcciones. Hoy, si el rango rompe al alza primero, la venta se anula.

| compras en días de empleo | R/op | t | mitades |
|---|---|---|---|
| relleno exacto | +0,933 | 4,67 | |
| **relleno real (ticks)** | **+0,857** | **4,31** | +0,903 / +0,813 |

Pasa Bonferroni para 11 (2,84) con holgura. Juntando las dos direcciones, con
relleno real y **un spread extra cobrado a la compra** por si dispararla con el
ask adelanta falsas rupturas:

| | valor |
|---|---|
| operaciones | 159 |
| R/op | **+0,675** (t = 4,79) |
| años positivos | **19 de 21** (t anual 4,00) |
| sin los 3 mejores días | +0,574 (t = 4,39) |
| sin los 10 mejores días | +0,350 (t = 3,32) |

No lo sostienen unos pocos días extraordinarios.

### Lo que cambia

El día del dato de empleo **van las dos órdenes** (`oro.calendario`,
`dos_ordenes_en_dia_de_empleo`). El correo lo dice, pide OCO —a las 8:30 pueden
saltar las dos en segundos— y avisa del deslizamiento. El registro cobra a ese
día su deslizamiento medido (1,30 $), no el de un día normal.

## La estrategia, con todos los costes reales

`python -m oro.historico`, código de producción, spread de cada año y
deslizamiento medido:

| | n | R/op | t | R/año |
|---|---|---|---|---|
| **total** | **2.208** | **+0,0786** | **3,00** | **+8,26** |
| días de empleo (dos órdenes) | 160 | +0,5815 | 4,13 | +4,43 |
| resto (solo venta) | 2.048 | +0,0393 | 1,52 | +3,83 |

Mitades +0,0778 / +0,0795. 14 años positivos de 21. Peor año −19,6 R, peor
racha −45,9 R. A 0,5 % de riesgo sobre 3.000 €: +124 €/año, peor año −294 €,
peor racha −688 €.

**Más de la mitad del rendimiento sale de unos 8 días al año.** El resto de
días la venta es positiva pero no está demostrada por sí sola (t = 1,52).

## Lo que no se pudo medir: el IPC

El IPC de EE. UU. también sale a las 8:30 ET y mueve el oro tanto o más que el
empleo, sobre todo desde 2021. Pero su fecha no sigue una regla calculable, la
web del BLS da 403 y la API de FRED (que tiene el calendario de publicaciones)
exige clave. Con una clave gratuita de FRED se podría medir igual que el
empleo. Es la siguiente prueba natural.

## La Fed (hipótesis 10)

Las decisiones del FOMC salen a las 14:00 ET, con la operación ya abierta.
60 operaciones: −0,105 R/op frente a +0,109 el resto, t = −1,13. Las mitades
coinciden (−0,216 / −0,212) pero la muestra es pequeña y no pasa. No se toca.

---

# Con la clave de FRED: el IPC, y el calendario real del empleo

## El IPC no pasa (hipótesis 12)

Fechas reales del IPC desde la API de FRED (publicación 10), una por mes —se
descarta la revisión anual de factores estacionales de febrero—. 259 días de
IPC de 2006 a 2026. Mismo método que el empleo: código de producción con las
dos órdenes y relleno real tick a tick.

| | n | R/op real | t | mitades |
|---|---|---|---|---|
| venta | 78 | +0,031 | 0,25 | +0,106 / −0,084 |
| compra | 98 | +0,164 | 1,14 | −0,081 / +0,381 |
| las dos | 176 | +0,105 | 1,08 | +0,013 / +0,207 |

Lejos de Bonferroni (2,87 para 12) y con las mitades llevándose la contraria.
El IPC no se comporta como el empleo. Los días de IPC se tratan como un día
normal.

## El calendario del empleo, corregido

La regla de fechas, comprobada contra el calendario de FRED (publicación 50,
filtrada a la primera fecha de cada mes para quitar revisiones), acertaba 236 de
257. Dos causas corregibles:

* **Enero**: la excepción se aplica del 1 al 3, no del 1 al 4 (en 2008, 2013 y
  2019 el informe salió el día 4).
* **4 de julio**: si el viernes es festivo o puente, se adelanta al jueves
  (2008, 2009, 2014, 2015, 2020, 2025, 2026).

Con eso acierta **246 de 251**, y las 5 que falla son todas **retrasos por
cierre del Gobierno federal** (2013 y 2025-26), que ninguna regla puede prever.
Por eso, con el secreto `ORO_FRED_CLAVE`, el sistema usa el calendario real de
FRED, y la regla queda de respaldo.

Con el calendario real el efecto sale más fuerte —las fechas erróneas lo
diluían—:

| | n | R/op | t | R/año |
|---|---|---|---|---|
| **total** | 2.209 | **+0,0819** | **3,13** | **+8,62** |
| días de empleo | 161 | +0,6387 | 4,58 | +4,90 |
| resto (venta) | 2.048 | +0,0382 | 1,48 | +3,72 |

Mitades +0,0830 / +0,0808, 15 años positivos de 21, peor año −18,3 R.

## 5-oct-2026: el primer día con el contado, y lo que falló

El plan de ese día lo calculó el código anterior sobre el futuro de COMEX
(GC=F: venta en 4.177,90) y, al cambiar la fuente a media tarde, el seguimiento
lo siguió con el contado de Dukascopy, unos 30-40 $ más abajo. Leído contra el
contado, el nivel 4.177,90 estaba «roto» desde por la mañana: vio una venta
abierta que no existía y mandó un **aviso falso de break-even**. Se neutralizó a
mano antes de que se registrara como operación.

Con el contado, el plan correcto habría sido: rango de Londres
4.149,17-4.170,14, venta en 4.149,17 con stop en 4.170,14, disparada a las 9:00
de Nueva York, llegó a 1R (break-even) y cerró a las 16:00 en 4.139,28:
**+0,47 R** en bruto.

Tres cosas cambiadas para que no vuelva a pasar:

* **El plan guarda de qué precio salió** (`dukascopy:XAUUSD`, `yahoo:GC=F`) y el
  seguimiento se niega a seguir un plan de otra fuente: no lo registra y avisa
  una vez de que ese día no habrá avisos.
* **Las horas perdidas de Dukascopy.** Medido: el servidor contesta **429**
  (demasiadas peticiones) a casi todo durante más de un minuto cuando se le
  piden unas decenas de horas seguidas. Ahora se piden 24 horas en vez de 48,
  con 3 hilos, esperando de verdad tras un 429, sin insistir en las horas que
  el horario dice cerradas, y con una segunda pasada para las que fallan. Una
  hora de mercado abierto que falla ya no se memoriza nunca como vacía.
* **El plan no se manda con el rango incompleto.** Si falta una hora de la
  mañana de Londres se espera a la pasada siguiente (el vigilante pasa cada
  tres minutos); a partir de las 9:00 de Nueva York se manda con lo que haya.
  Un rango con una hora perdida sale más estrecho y pone la orden donde salta
  con ruido.

Y el vigilante sube el estado al repositorio en cuanto cambia cualquier cosa
—también los avisos de la tarde y la ficha del día—, no solo al mandar el plan.

## 6-oct-2026: el histórico cerraba una hora tarde

Reproduciendo días reales cada 3 minutos con el código de producción salieron
dos fallos del seguimiento, y uno de ellos tocaba todas las cifras:

* **Una vela de más.** El seguimiento incluía la vela que *empieza* a la hora
  del cierre (16:00-17:00 de Nueva York). El histórico, que llama a ese mismo
  código, cerraba en realidad a las 17:00, con una hora más de stops y
  objetivos. En vivo se cierra a las 16:00. Corregido:

| | n | R/op | t | R/año |
|---|---|---|---|---|
| **total** | 2.209 | **+0,0733** | **2,80** | **+7,81** |
| días de empleo | 161 | +0,6448 | 4,58 | +5,00 |
| resto (venta) | 2.048 | +0,0284 | 1,10 | +2,80 |

  Mitades +0,0884 / +0,0575, 15 años positivos de 21, peor año −18,7 R (2006),
  peor racha −45,4 R, acierto 38,8 %, ganadoras +1,23 R y perdedoras −0,66 R.
  El total queda **justo por debajo de Bonferroni** para 12 hipótesis (2,87).
  El día de empleo lo pasa de sobra; el resto de días no se distingue de cero.

* **La última vela de cada ventana llega después de que la ventana acabe.** A
  las 10:00 de Nueva York la vela de 9:00-10:00 aún no está publicada (Dukascopy
  la sube ~2 minutos después). El 5-oct, reproducido, el seguimiento dio la
  orden por caducada a las 10:00 y mandó «CANCELA», cuando la venta se había
  ejecutado dentro de esa última hora. Ahora espera a esa vela (como mucho 45
  minutos) antes de dar la orden por caducada o grabar el cierre. El aviso de
  «CIERRA» sigue saliendo a su hora.

## 6-oct-2026: los días ambiguos. La estrategia no tiene ventaja

El histórico dejaba **fuera de las cifras** los días en que, dentro de la
ventana de disparo, una misma vela horaria cruza el techo y el suelo del rango:
con velas de una hora no se sabe qué fue primero. Eran 359 de 5.370 días con
plan. Fuera de las cifras no es fuera de la cuenta: en vivo, ese día la orden
existe.

Bajadas las velas de un minuto de Dukascopy de los 359 días y resueltos con las
mismas funciones de producción (`python -m oro.ambiguos`, y ahora dentro de
`oro.historico`):

| qué pasó | días | R neto medio |
|---|---|---|
| la venta salta primero y en esa hora sube al stop | 178 | ≈ −1,2 |
| sube primero; la venta se ejecuta antes de que pueda llegar el aviso de cancelar, y se cierra al llegar | 116 | ≈ −0,1 |
| el día de empleo, la compra salta primero y luego el stop | 33 | ≈ −1,3 |
| otros (break-even, stop tras rotura al alza) | 25 | |
| sin resolver ni con minutos | 7 | |
| **total resueltos** | **352** | **−0,745** |

Con esos días dentro:

| | n | R/op | t | R/año |
|---|---|---|---|---|
| **total** | 2.561 | **−0,0391** | **−1,64** | **−4,83** |
| días de empleo | 239 | +0,0198 | 0,18 | +0,23 |
| resto | 2.322 | −0,0452 | −1,91 | −5,06 |

Mitades −0,016 / −0,062, 7 años positivos de 21, peor año −31,8 R, peor racha
−126,8 R, acierto 35 %. Los días de empleo se hunden porque 1 de cada 3 es
ambiguo: el salto de las 8:30 cruza los dos lados en la misma hora.

**Decisión: el plan pasa a «solo papel»** (`ORO_RUPTURA_SOLO_PAPEL`, activo por
defecto). Se sigue mandando y siguiendo para medir en real, con el correo y los
avisos marcados «NO OPERES». En vivo, además, una hora ambigua ya no deja al
sistema callado: se resuelve con los ticks de esa hora y, si no se puede, se
avisa de revisar el bróker.

La lección es la misma de siempre en este proyecto, y esta vez costó la
estrategia entera: un dato que falta no es neutro. Los días que no se sabían
medir eran justo los peores.

---

# 6-oct-2026: búsqueda de una estrategia nueva — hipótesis DECLARADAS ANTES DE MEDIR

Se escriben y se suben al repositorio antes de calcular nada. Las 12 anteriores
cuentan: con estas 3 son 15 hipótesis, y el listón de Bonferroni (5 % a dos
colas) pasa a **t ≥ 2,94**.

Reglas comunes, fijadas aquí y que no se tocan después:

* Velas H1 BID de Dukascopy, 2006-01 a 2026-09. Horas en Nueva York.
* **Entradas a mercado en la apertura de una vela** (no órdenes stop dentro de
  la vela): así no hay velas ambiguas en la entrada, que es lo que hundió la
  estrategia anterior.
* **Salidas: solo el stop o la hora** (sin objetivo, sin break-even), para que
  tampoco haya ambigüedad en la salida. Si una vela toca el stop, sale en el
  stop.
* Cierre a la apertura de la vela de las 16:00 ET (= precio de las 16:00).
* Coste por operación: el spread medido de cada año (`oro.spread`) + 0,25 $ de
  deslizamiento; 1,30 $ el día de empleo y el de IPC.
* Se exige a la vez: **t ≥ 2,94**, **las dos mitades (2006-2015 y 2016-2026)
  positivas** y R/año positivo. Si ninguna lo cumple, no hay estrategia.

**H13 · Empleo, después del dato.** Los días del informe de empleo (calendario
de FRED). La vela de 8:00-9:00 ET contiene el dato de las 8:30. A las 9:00 se
entra a mercado en la dirección de esa vela (cierre frente a apertura), con el
stop en el extremo contrario de esa vela. Cierre a las 16:00.

**H14 · IPC, después del dato.** Lo mismo los días del IPC (FRED, publicación
10, primera fecha de cada mes).

**H15 · Rotura confirmada por cierre.** Todos los días. Rango de 3:00-8:00 ET.
La primera vela de 8:00 o de 9:00 ET que CIERRA fuera del rango da la
dirección; se entra a mercado en la apertura de la vela siguiente, con el stop
en el extremo contrario del rango. Compras y ventas. Cierre a las 16:00.

## Resultado de H13-H15 (medido después de declararlas)

| | n | R/op neto | t | mitades | años + |
|---|---|---|---|---|---|
| H13 empleo, tras el dato | 244 | −1,19 | −1,31 | −2,08 / −0,34 | 8/21 |
| H14 IPC, tras el dato | 246 | −0,40 | −4,08 | −0,36 / −0,44 | 4/21 |
| H15 rotura confirmada por cierre | 3.155 | −0,077 | −4,92 | −0,085 / −0,069 | 2/21 |

**Ninguna pasa. Las tres pierden.** H13 tiene una media enorme y una t pequeña
porque, cuando la vela del dato cierra cerca de su extremo, el stop queda a
céntimos de la entrada y el coste se come varios R; es la regla declarada y no
se retoca después de ver el resultado. H14 y H15 pierden con claridad.

Que H15 pierda con t = −4,92 invita a probar lo contrario (operar contra la
rotura confirmada). No se puede validar sobre estos mismos datos: sería elegir
la regla mirando el resultado. Lo único limpio sería declararla y medirla
hacia delante, en papel, con días que aún no han ocurrido.

---

# 6-oct-2026 (tarde): seguimiento de tendencia a varios días — DECLARADAS ANTES DE MEDIR

Rompe la regla de «solo intradía»: las posiciones duran días o meses. Se mide
porque es el terreno con más respaldo en la literatura (Moskowitz, Ooi y
Pedersen 2012; Hurst, Ooi y Pedersen, «A Century of Evidence on
Trend-Following»). Con estas 3 van 18 hipótesis: listón **t ≥ 2,99**.

Reglas comunes:

* Cierre diario = cierre de la última vela H1 de cada sesión (17:00 ET). La
  señal se calcula con ese cierre y se opera en la APERTURA de la sesión
  siguiente (sin mirar el futuro).
* Coste por cada cambio de posición: el spread medido del año + 0,25 $ de
  deslizamiento, por unidad que cambia (darle la vuelta de largo a corto paga
  dos veces).
* **Financiación de un CFD** (lo que cobra el bróker por dormir con la
  posición): el largo paga (tipo de la Fed + 2,5 %) al año; el corto cobra
  (tipo de la Fed − 2,5 %), que es pagar cuando los tipos están por debajo del
  2,5 %. Tipo de la Fed: serie DFF de FRED. Por día natural.
* Resultado en % anual sobre el nominal (sin apalancamiento). Se exige a la
  vez: **t ≥ 2,99** sobre los rendimientos diarios, **las dos mitades
  (2006-2015 y 2016-2026) positivas** y que gane neto de todo.

**H16 · Media de 200 días, largo y corto.** Largo si el cierre está por encima
de su media de 200 sesiones; corto si está por debajo.

**H17 · Momento de 12 meses.** Largo si el cierre está por encima del de hace
252 sesiones, corto si por debajo. Se revisa solo la primera sesión de cada
mes.

**H18 · Media de 200 días, solo largo.** Largo por encima de la media; fuera
del mercado por debajo.

Referencia (no es hipótesis, no compite): **comprar y mantener** con la misma
financiación de CFD.

## Resultado de H16-H18 (medido después de declararlas)

Rendimiento anual sobre el nominal, neto de spread, deslizamiento y financiación
de CFD, 2006-2026:

| | % anual | t | mitades | años + | peor caída | financiación |
|---|---|---|---|---|---|---|
| H16 media 200 largo/corto | +2,3 % | 0,59 | +2,5 / +2,1 | 12/21 | −61 % | −3,7 %/año |
| H17 momento 12 meses | +2,7 % | 0,68 | +4,9 / +0,5 | 12/21 | −59 % | −3,8 %/año |
| H18 media 200 solo largo | +5,6 % | 1,73 | +4,8 / +6,3 | 11/21 | −37 % | −3,2 %/año |
| (referencia) comprar y mantener | +7,3 % | 1,86 | +5,3 / +9,1 | 14/21 | −50 % | −4,3 %/año |

**Ninguna pasa** (listón t ≥ 2,99). Ninguna mejora a simplemente tener el oro
comprado. La financiación del CFD se come entre 3 y 4 puntos al año: dormir con
un CFD de oro es caro. Tener oro físico a través de un ETC (comisión ~0,15-0,25
% al año, sin financiación) no paga ese peaje.

## ¿Con qué coste ganaría el intradía? (descriptivo, no es hipótesis)

La ruptura de sesión, con los días ambiguos contados, da **+0,078 R por
operación ANTES de costes (t = 3,26)**: el movimiento existe. Pero:

* El coste que la deja a cero es **0,48 $ por operación** (spread +
  deslizamiento). El medido es 0,60 $ de spread + 0,25 $ de deslizamiento.
* Desde 2016 la ventaja en bruto baja a +0,038 R (t = 1,20) y el coste que la
  deja a cero, a **0,26 $**: el deslizamiento solo ya es 0,25 $.

Con costes de minorista, el intradía en el oro no da para pagar al bróker.

---

# 6-oct-2026: indicadores como FILTRO del plan de ruptura — DECLARADAS ANTES DE MEDIR

Pregunta: ¿precisan los indicadores las entradas del plan actual? Cada filtro se
aplica al plan tal como está (venta en la primera rotura a la baja; las dos
órdenes el día de empleo) y deja operar solo los días que lo cumplen. Todo se
calcula con lo que se sabe a las 8:00 ET (vela H1 de 7:00-8:00 cerrada), sobre
el histórico con los días ambiguos resueltos con velas de un minuto. Un filtro
de dirección se aplica al lado de la operación (la venta pide señal bajista,
la compra del día de empleo, alcista).

Con estas 5 van 23 hipótesis: listón **t ≥ 3,06**. Se exige además que el
subconjunto filtrado gane en las dos mitades (2006-2015 y 2016-2026).

**H19 · Tendencia horaria.** Precio por encima (compra) / por debajo (venta) de
su EMA de 200 velas H1.

**H20 · Tendencia diaria.** Cierre diario anterior por encima / por debajo de
su media de 50 sesiones.

**H21 · RSI.** RSI de 14 velas H1 por encima de 50 (compra) / por debajo
(venta).

**H22 · ADX.** ADX de 14 velas H1 de al menos 20 (hay tendencia). No mira la
dirección.

**H23 · Rango estrecho.** Amplitud del rango de Londres menor que la mitad del
ATR diario de 14 sesiones (la «compresión» antes de una rotura).

## Resultado de H19-H23 (medido después de declararlas)

Sin filtro: 2.561 operaciones, −0,039 R/op (t = −1,64).

| filtro | operaciones que deja | R/op | t | mitades | las que quita |
|---|---|---|---|---|---|
| H19 EMA 200 horaria a favor | 1.331 | +0,025 | 0,73 | +0,061 / −0,014 | −0,109 (t −3,34) |
| H20 media 50 diaria a favor | 1.148 | −0,035 | −0,97 | −0,028 / −0,042 | −0,043 |
| H21 RSI a favor | 1.555 | +0,003 | 0,09 | +0,009 / −0,004 | −0,104 (t −2,77) |
| H22 ADX ≥ 20 | 1.718 | −0,061 | −2,23 | −0,045 / −0,078 | +0,006 |
| H23 rango estrecho | 2.066 | −0,061 | −2,17 | −0,030 / −0,091 | +0,051 |

**Ninguno pasa** (listón t ≥ 3,06). Lo único que se ve es que operar CONTRA la
EMA 200 horaria o contra el RSI es claramente malo (t −3,34 y −2,77), pero lo
que queda al quitar esos días se queda en cero, no gana. Combinar filtros a
partir de esta tabla sería elegir la regla mirando el resultado.

---

# 8-oct-2026: petróleo y oro — HIPÓTESIS DECLARADAS ANTES DE MEDIR

Pregunta del usuario: «creo que cuando sube el petróleo baja el oro, y al
revés». Se mide con datos, no con lo que se lee por ahí. Con estas 4 van 27
hipótesis: listón **t ≥ 3,11** (5 % a dos colas, Bonferroni).

Datos: WTI y Brent diarios (FRED/EIA, desde 1986-87), oro diario de referencia
del World Gold Council (desde 1985), oro H1 de Dukascopy (2006-2026) y, si se
consigue, WTI H1 de Dukascopy. Dólar: índices amplios de la Fed (FRED DTWEXM
hasta 2019, DTWEXBGS desde 2006).

**H24 · La creencia, tal cual.** Los rendimientos del oro y del petróleo se
mueven en sentido CONTRARIO (correlación negativa) a plazo diario, semanal y
mensual. Se mide la correlación en toda la muestra, por décadas y en ventanas
móviles de un año, y la frecuencia con que van en sentidos opuestos.

**H25 · El petróleo de hoy anticipa el oro de mañana.** El rendimiento diario
del WTI (cierre de 14:30 ET) predice el rendimiento del oro del día siguiente
(de 15:00 ET a 15:00 ET, con el oro H1 de Dukascopy para que los dos precios
sean de la misma hora y no fabricar un adelanto falso). Regresión con t ≥ 3,11
y el mismo signo en las dos mitades.

**H26 · Anticipación intradía.** El rendimiento del WTI en una hora predice el
del oro en la hora siguiente (H1 de Dukascopy). Mismo criterio.

**H27 · Ratio oro/petróleo extremo.** Con el logaritmo del ratio oro/WTI frente
a su media de 5 años (puntuación z), cuando el oro está «caro» frente al
petróleo (z > +1) rinde menos el mes siguiente que cuando está «barato»
(z < −1). Regresión del rendimiento del oro del mes siguiente sobre la z del
mes; t ≥ 3,11 y mismo signo en las dos mitades.

Además, sin ser hipótesis: control del dólar (correlación parcial), episodios
de choques del petróleo (1990, 2008, 2014-16, abril 2020, 2022) y relación de
largo plazo entre los niveles (cointegración).

## Resultado: petróleo y oro (medido después de declararlo)

### H24 · ¿Se mueven en sentido contrario? No: en general, en el MISMO

Rendimientos logarítmicos, 1986-2026 (oro de referencia del WGC; WTI y Brent
de la EIA vía FRED):

| | n | correlación | t | van en sentido contrario |
|---|---|---|---|---|
| WTI diario | 9.464 | +0,080 | +7,8 | 45 % |
| WTI semanal | 2.121 | +0,139 | +6,5 | 45 % |
| WTI mensual | 489 | +0,130 | +2,9 | 47 % |
| Brent diario | 9.080 | +0,122 | +11,7 | 44 % |
| Brent semanal | 2.037 | +0,146 | +6,7 | 44 % |
| Brent mensual | 473 | +0,092 | +2,0 | 47 % |

Con los dos precios a la misma hora (oro de Dukascopy a las 15:00 ET, WTI a
las 14:30 ET), la correlación diaria 2006-2026 es +0,150.

La relación es positiva pero DÉBIL (explica alrededor del 2 % de los
movimientos del oro) y cambia con las épocas (Brent, semanal):

| época | correlación | t |
|---|---|---|
| 1987-1995 | +0,251 | +5,4 |
| 1996-2005 | +0,054 | +1,2 |
| 2006-2015 | +0,338 | +8,2 |
| 2016-2026 | −0,003 | −0,1 |

En ventanas móviles de 52 semanas es negativa el 31 % del tiempo (mínimo
−0,35, en julio de 2026; máximo +0,66, en mayo de 2011). **En 2026 la
correlación sí es negativa** (−0,19 en marzo, −0,31 en junio, −0,34 en
septiembre) y en los últimos 24 meses fueron en sentido contrario el 60 % de
los meses. Ya pasó antes (1992, 1996, 1999, 2001, 2019, 2021) y siempre volvió.

La creencia, directamente: en el 10 % de semanas con el petróleo más alcista
(+9 % de media) el oro SUBIÓ +0,53 % de media (t = +3,5) y solo bajó el 38 % de
esas semanas. En el 10 % más bajista (−9,8 %) el oro BAJÓ −0,60 % (t = −2,9).

Por tipo de choque (semanas extremas del Brent frente al Nasdaq): el oro va con
el petróleo en los cuatro casos, también cuando el petróleo se hunde por miedo
a una recesión (−0,56 %, t = −2,3). En ninguno va en contra más del 41 % de las
veces.

Doce episodios grandes del petróleo desde 1990: en 10 el oro fue en el mismo
sentido (más suave). Solo en 1999-2000 (petróleo +241 %, oro −5 %) y en la
caída del COVID de 2020 (petróleo −87 %, oro +7 %) fue al revés.

**El dólar explica casi todo el vínculo.** Semanal, con el índice del dólar
como control: 1987-2005 el petróleo sigue pesando (+0,036, t = +3,1), pero
2006-2026 deja de hacerlo (+0,016, t = +0,9), mientras el dólar pesa mucho
(−1,42, t = −9,6). Cuando el dólar baja, suben los dos (los dos cotizan en
dólares); cuando sube, bajan los dos.

Niveles: correlación +0,81 entre los precios, pero es la ilusión de dos
tendencias de largo plazo; no hay cointegración (Engle-Granger p = 0,52 en toda
la muestra, 0,72 y 0,91 en las mitades): no hay una «relación de equilibrio»
a la que vuelvan.

### H25 · El petróleo de hoy NO anticipa el oro de mañana

Precios sincronizados (oro 15:00 ET, WTI 14:30 ET), 2006-2026: coeficiente
+0,008, **t = +1,13** (mitades t = +0,28 y +1,24). Correlaciones a ±1, 2 y 3
días: entre −0,022 y +0,020. Operar al día siguiente el oro en contra del
petróleo de hoy: −0,1 puntos básicos al día antes de costes (t = −0,04).

### H27 · El ratio oro/petróleo NO anticipa el oro

Ratio oro/WTI hoy 43,2 (media 1986-2026: 20,5; z frente a 5 años +0,64).
Regresión del oro del mes siguiente sobre la z: coeficiente +0,0022, **t =
+1,25** (mitades t = +0,06 y +1,56), y con el signo CONTRARIO al que predice
la idea popular (con el oro «caro» frente al petróleo, el oro rindió algo más,
no menos).
