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
* **El objetivo** está a 3 veces esa distancia.
* **Caduca a las dos horas.** Si a las 16:00 de Madrid no ha saltado ninguna, se
  cancelan las dos: lo que se rompe por la tarde ya no es la ruptura de la
  mañana, y está medido que no compensa.
* **Se cierra a las 22:00 de Madrid** si sigue abierta. Nunca de un día para otro.

## Lo que hay que saber antes de usarla

Está medida sobre 19,6 años de velas horarias reales (118.452 velas), y esto es
lo que sale — con un spread de 0,60 $ por operación:

| | |
|---|---|
| Operaciones | ~207 al año, casi una por día de mercado |
| Acierto | **42,7 %**: la mayoría de los días pierde |
| Ventaja | +0,069 R por operación (≈ +14 R al año) |
| Años positivos | **14 de 20** |
| Peor racha | **de 2016 a 2021 perdió cinco años seguidos** |

Gana porque las operaciones ganadoras son mucho mayores que las perdedoras, no
porque acierte a menudo. Si perder cuatro días de cada siete te va a sacar del
plan, esta estrategia no es para ti, y es mejor saberlo ahora.

El detalle de todo lo que se midió —incluidas las dos reglas parecidas que se
descartaron y por qué— está en [ESTRATEGIAS_MEDIDAS.md](ESTRATEGIAS_MEDIDAS.md).

## Por qué puede que no recibas ningún correo

Es lo más probable ahora mismo, y **es correcto**:

> `Tu coste por operación (1.45 $/oz) supera el máximo al que esta estrategia
> gana (0.60 $/oz).`

Con el spread de 1,45-2 $ de tu cuenta actual, la ventaja medida es **negativa**
(−0,059 R por operación). El sistema no manda el plan porque mandarlo sería
mandarte a perder dinero con buenos modales. En cuanto tengas una cuenta con
spread de 0,30-0,60 $ y lo pongas en `ORO_COSTE_OPERACION`, empezará a llegar.

Ver [CAMBIAR_DE_CUENTA.md](CAMBIAR_DE_CUENTA.md).

## Cómo se ajusta

Todo desde **Settings → Secrets and variables → Actions → Variables** de GitHub,
sin tocar código:

| Variable | Por defecto | Qué hace |
|---|---|---|
| `ORO_COSTE_OPERACION` | `0.30` | Tu spread real en $/onza. **El que manda.** |
| `ORO_RUPTURA_ACTIVA` | `1` | `0` apaga la estrategia entera. |
| `ORO_RUPTURA_R_OBJETIVO` | `3.0` | Dónde va el objetivo, en múltiplos del rango. |
| `ORO_RUPTURA_COSTE_MAX` | `0.60` | Spread por encima del cual no se envía nada. |
| `ORO_RUPTURA_HORAS_VALIDEZ` | `2` | Cuántas horas valen las órdenes. |
| `ORO_CAPITAL` | `3000` | Tu capital, para calcular el lote. |
| `ORO_RIESGO_POR_OPERACION` | `0.0025` | Fracción del capital por operación. |

Para probarlo sin esperar a las 14:00: **Actions → «Plan del día XAU/USD» → Run
workflow → marca `forzar`**. O en local: `python -m oro.cli plan`.

## Sobre el lote

Con 3.000 € y un objetivo de riesgo del 0,25 % (7,50 €), el lote que sale es
menor que el mínimo del bróker. Con el lote mínimo (0,01 = 1 onza) y un rango de
26 $, arriesgas **26 €, un 0,87 % del capital**. El correo te lo dice en cada
envío: no se puede bajar más con esta cuenta, y es mejor verlo escrito que
suponer que arriesgas 7 €.
