# El plan del día: la ruptura del rango de la mañana

Esto es la **segunda estrategia** del sistema. Funciona aparte del vigilante
intradía y no interfiere con él: puedes usar las dos, una, o ninguna.

## Qué recibes

Un correo a las **14:00 de Madrid** (a veces 13:00, cuando Europa y Estados
Unidos no han cambiado la hora a la vez) con dos órdenes ya calculadas:

```
Rango de la mañana de Londres: 3998.00 — 4024.00

COMPRA (buy stop)  en 4024.00   stop 3998.00   objetivo 4102.00
VENTA  (sell stop) en 3998.00   stop 4024.00   objetivo 3920.00
```

Las tecleas las dos en el bróker, cancelas la otra en cuanto una salte, y te
olvidas. No hay que estar delante.

## La idea

Entre las 3:00 y las 8:00 de Nueva York —la mañana de Londres— el oro deja un
máximo y un mínimo. Cuando Nueva York abre y el precio sale de esa caja, suele
seguir en esa dirección. Ni tú ni yo sabemos hacia qué lado saldrá, así que se
deja preparada una orden a cada lado y decide el mercado.

* **La entrada** es el borde de la caja. Como es un precio conocido de antemano,
  la orden se deja puesta y no hace falta vigilar nada.
* **El stop** es el otro borde. Si el precio vuelve a cruzar la caja entera, la
  ruptura era falsa.
* **El objetivo** está a 10 veces esa distancia: es una red de seguridad para
  el día extraordinario, no la salida. Se ejecuta 1 de cada 1.000 veces.
* **La salida es cerrar a mano a las 21:50** (tu hora), gane o pierda. Medido:
  +0,069 R por operación frente a +0,050 con un objetivo cercano, porque un
  objetivo cerca corta las ganadoras grandes.
* **Opcional:** cuando la operación te dé 1R de beneficio, mueve el stop al
  precio de entrada. Sube la ventaja a +0,077 y desde ahí ya no puede perder.
* **Caduca a las dos horas.** Si a las 16:00 de Madrid no ha saltado ninguna, se
  cancelan las dos: lo que se rompe por la tarde ya no es la ruptura de la
  mañana, y está medido que no compensa.
* **Nunca se queda de un día para otro.**

## Lo que pasa después: el seguimiento

El plan se manda por la mañana, pero la operación dura toda la sesión. Un
segundo trabajo (`oro-seguimiento.yml`) mira el mercado cada 15 minutos y te
avisa cuando toca:

| Cuándo | Qué te llega |
|---|---|
| Se acaba la ventana sin que salte ninguna | **Cancela las dos órdenes.** Hoy no hay operación. |
| La operación te da 1R de beneficio | **Mueve el stop a la entrada.** Desde ahí ya no puede perder. |
| Final de la sesión con la operación viva | **Ciérrala a mercado**, gane o pierda. |

Y cuando el día termina guarda la ficha en `oro_rupturas.jsonl`: el rango, la
dirección, el resultado **neto de costes**, hasta dónde llegó a favor, y si
acompañaba o no al sesgo asiático. Eso es lo que permitirá contestar «¿por qué
salió bien o mal?» cuando haya operaciones suficientes.

Un detalle de diseño: en cada ejecución se **reproduce el día entero desde las
velas**, no se acumula estado. Es más caro y es deliberado — si una ejecución
falla (GitHub cancela tareas, la red se cae), la siguiente ve el día completo y
llega a la misma conclusión. Lo único que se recuerda entre ejecuciones es qué
avisos ya se mandaron.

Lo que el seguimiento **no** puede saber, y lo asume por lo conservador: con
velas de una hora, si dentro de la misma vela el precio toca el stop y el
objetivo, se supone el stop. Y si en el primer tramo sale del rango por los dos
lados, no se registra ninguna operación: inventarse la dirección envenenaría el
aprendizaje.

## Qué dice el sesgo asiático (y qué NO dice)

**No dice cuál de las dos órdenes va a saltar.** Medido sobre 3.180 días, la
marcada es la que salta el **50,0 %** de las veces (z = 0,00): como predicción
vale exactamente lo que una moneda al aire.

Lo que dice es qué pasa *después*, una vez que ya ha saltado una:

| Ruptura | R por operación | t |
|---|---|---|
| la que acompaña a la asiática | **+0,129** | 3,91 |
| la contraria | +0,034 | 1,14 |

Por eso el correo lo explica en texto y **no marca ninguna de las dos órdenes**.
Hubo una estrella junto a la favorita y era engañosa: puesta al lado de una
orden se lee como predicción, y el **49 % de los días parecía equivocarse** —un
25 % saltaba la marcada y perdía, un 24 % saltaba la otra y ganaba— aunque el
dato fuese correcto. Un dato que parece fallar la mitad de las veces destruye la
confianza en todo lo demás que dice el correo.

**Y es una indicación, no un hecho probado.** La diferencia entre lados da
t = 2,07 y no supera la corrección de Bonferroni (haría falta 2,81). Se dejan
las dos órdenes puestas siempre: el sistema no elige lado, elige el mercado.

## Lo que hay que saber antes de usarla

Está medida sobre 19,6 años de velas horarias reales (118.452 velas), y esto es
lo que sale — con un spread de 0,60 $ por operación:

| | |
|---|---|
| Operaciones | ~207 al año, casi una por día de mercado |
| Acierto | **44,7 %**: la mayoría de los días pierde |
| Ventaja | +0,067 R por operación (≈ +14 R al año) |
| Años positivos | **14 de 20** |
| Peor racha | **de 2017 a 2020 perdió cuatro años seguidos** |

Gana porque las operaciones ganadoras son mucho mayores que las perdedoras, no
porque acierte a menudo. Si perder cuatro días de cada siete te va a sacar del
plan, esta estrategia no es para ti, y es mejor saberlo ahora.

El detalle de todo lo que se midió —incluidas las dos reglas parecidas que se
descartaron y por qué— está en [ESTRATEGIAS_MEDIDAS.md](ESTRATEGIAS_MEDIDAS.md).

## Cómo se ajusta

Todo desde **Settings → Secrets and variables → Actions → Variables** de GitHub,
sin tocar código:

| Variable | Por defecto | Qué hace |
|---|---|---|
| `ORO_RUPTURA_ACTIVA` | `1` | `0` apaga la estrategia entera. |
| `ORO_RUPTURA_R_OBJETIVO` | `3.0` | Dónde va el objetivo, en múltiplos del rango. |
| `ORO_RUPTURA_HORAS_VALIDEZ` | `2` | Cuántas horas valen las órdenes. |
| `ORO_RUPTURA_SESGO_CUERPO_MINIMO` | `0.20` | Cuánto tiene que moverse Asia para señalar favorita. |

Para probarlo sin esperar a las 14:00: **Actions → «Plan del día XAU/USD» → Run
workflow → marca `forzar`**. O en local: `python -m oro.cli plan`.
