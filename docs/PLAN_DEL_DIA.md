# El plan del día: la ruptura del rango de la mañana

Esto es la **segunda estrategia** del sistema. Funciona aparte del vigilante
intradía y no interfiere con él: puedes usar las dos, una, o ninguna.

## Qué recibes

Un correo a las **14:00 de Madrid** (a veces 13:00, cuando Europa y Estados
Unidos no han cambiado la hora a la vez) con **una** orden ya calculada:

```
Rango de la mañana de Londres: 3998.00 — 4024.00

VENTA  (sell stop) en 3998.00   stop 4024.00   objetivo 3842.00

ANULA LA ORDEN si el precio sube de 4024.00 antes de que salte.
```

La tecleas en el bróker y te olvidas. No hay que estar delante — con una
excepción, la única de toda la estrategia: **si el precio rompe el techo del
rango antes de que salte tu venta, hay que cancelarla.** Te llega un correo en
cuanto pasa, y conviene además dejar una alerta en ese precio.

## La idea

Entre las 3:00 y las 8:00 de Nueva York —la mañana de Londres— el oro deja un
máximo y un mínimo. Cuando Nueva York abre y el precio **pierde el mínimo** de
esa caja, suele seguir cayendo durante la sesión.

### Por qué solo a la baja, y por qué hay que cancelar

Las dos preguntas tienen la misma respuesta: están medidas sobre 21 años.

| población de días | n | R/op | t | años + |
|---|---|---|---|---|
| **rompe abajo primero** (se opera) | 2131 | **+0,114** | 4,37 | 17/21 |
| rompe arriba (no se opera) | 2529 | −0,064 | −2,56 | 4/21 |
| rompe arriba y **luego** abajo | 869 | **−0,286** | −8,73 | 2/21 |

La fila de abajo es la importante. La **misma** rotura a la baja, cuando llega
después de que el rango se haya roto al alza, pierde 0,29 R de media. Si dejas
la venta puesta en esos días, la estrategia pasa de +11,6 R al año a **−1,1**:
no pierde parte de la ventaja, pierde toda.

Antes se dejaban las dos órdenes y decidía el mercado. Eso daba +0,013 R por
operación (t = 0,74), indistinguible de cero: el lado de las compras se comía
lo que ganaba el de las ventas.

* **La entrada** es el borde de la caja. Como es un precio conocido de antemano,
  la orden se deja puesta y no hace falta vigilar nada.
* **El stop** es el otro borde. Si el precio vuelve a cruzar la caja entera, la
  ruptura era falsa.
* **El objetivo** está a 6 veces esa distancia: es una red de seguridad para
  el día extraordinario, no la salida. Se ejecuta 17 veces en 21 años.
* **La salida es cerrar a mano a las 21:50** (tu hora), gane o pierda. Medido:
  un objetivo cercano corta las ganadoras grandes y cuesta un tercio de la
  ventaja (objetivo 2R: +0,080 R/op; sin objetivo: +0,107).
* **Mueve el stop a la entrada al llegar a 1R.** Esto ya no es opcional: sube la
  ventaja de +0,096 a +0,114 R por operación, y desde ahí la operación no puede
  perder dinero.
* **Caduca a las dos horas.** Si a las 16:00 de Madrid no ha saltado, se
  cancela: lo que se rompe por la tarde ya no es la ruptura de la mañana, y
  está medido que no compensa.
* **Nunca se queda de un día para otro.**

## Lo que pasa después: el seguimiento

El plan se manda por la mañana, pero la operación dura toda la sesión. Un
segundo trabajo (`oro-seguimiento.yml`) mira el mercado cada 15 minutos y te
avisa cuando toca:

| Cuándo | Qué te llega |
|---|---|
| El rango se rompe **al alza** antes que a la baja | **Cancela la orden de venta.** Hoy no se opera. |
| Se acaba la ventana sin que salte | **Cancela la orden.** Hoy no hay operación. |
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

> **Nota de octubre de 2026.** Con una sola orden esta sección es historia: no
> hay dos órdenes entre las que elegir, así que el correo ya no marca ninguna y
> el sesgo solo se guarda en el registro. Se deja escrito porque el camino de
> dos órdenes sigue existiendo (`ORO_RUPTURA_SOLO_VENTAS=0`) y porque explica
> por qué se quitó la estrella.

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

**Y ya no se usa para nada.** Con una sola orden no hay entre qué elegir, así
que el correo no marca ninguna: la pregunta dejó de existir. La medición del
sesgo asiático sigue guardada en el registro por si algún día hace falta.

## Lo que hay que saber antes de usarla

Medido con `python -m oro.historico`, que no reimplementa la estrategia: llama
a las mismas funciones que deciden en vivo. **21 años, 124.718 velas horarias,
2.131 operaciones**, con un coste de 0,30 $ por operación:

| | |
|---|---|
| Operaciones | ~101 al año (se opera el 40 % de los días) |
| Acierto | **40,0 %**: la mayoría de los días pierde |
| Ganadora media | +1,205 R |
| Perdedora media | −0,612 R |
| Ventaja | **+0,114 R por operación** (t = 4,37) |
| Al año | **+11,6 R** |
| Años positivos | **17 de 21** |
| Peor año | **−8,3 R** (2009) |
| Peor racha | **−23,0 R** |

Sobre una cuenta de 3.000 € con 0,5 % de riesgo por operación (15 €/R), eso son
**+174 € al año de media, un peor año de −125 € y una racha mala de −345 €**.

Gana porque las ganadoras valen el doble que las perdedoras, no porque acierte
a menudo. Si perder seis días de cada diez te va a sacar del plan, esta
estrategia no es para ti, y es mejor saberlo ahora.

**Y 101 operaciones al año tardan en demostrar algo.** Para distinguir +0,114 R
de cero con 80 % de potencia hacen falta unas 690 operaciones, **seis años**.
Lo que sí se puede comprobar desde la primera semana es que el *mecanismo*
funcione —el acierto, dónde caen los stops, la forma de las salidas— y de eso
se encarga `python -m oro.aprender`, que compara lo real con lo medido y avisa
si se separan más de lo que explica el azar.

El detalle de todo lo que se midió —incluidas las dos reglas parecidas que se
descartaron y por qué— está en [ESTRATEGIAS_MEDIDAS.md](ESTRATEGIAS_MEDIDAS.md).

## Cómo se ajusta

Todo desde **Settings → Secrets and variables → Actions → Variables** de GitHub,
sin tocar código:

| Variable | Por defecto | Qué hace |
|---|---|---|
| `ORO_RUPTURA_ACTIVA` | `1` | `0` apaga la estrategia entera. |
| `ORO_RUPTURA_SOLO_VENTAS` | `1` | `0` vuelve a dejar las dos órdenes. Medido: cuesta 7,7 R al año. |
| `ORO_RUPTURA_ANULAR_SI_ROMPE_ARRIBA` | `1` | `0` deja la venta puesta aunque el rango rompa al alza. **Medido: borra la ventaja entera.** |
| `ORO_RUPTURA_R_OBJETIVO` | `6.0` | Dónde va la red de seguridad, en múltiplos del rango. |
| `ORO_RUPTURA_HORAS_VALIDEZ` | `2` | Cuántas horas vale la orden. |
| `ORO_RUPTURA_SESGO_CUERPO_MINIMO` | `0.20` | Umbral del sesgo asiático (ya solo se registra). |

Para probarlo sin esperar a las 14:00: **Actions → «Plan del día XAU/USD» → Run
workflow → marca `forzar`**. O en local: `python -m oro.cli plan`.
