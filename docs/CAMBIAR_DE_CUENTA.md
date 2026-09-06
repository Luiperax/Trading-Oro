# Bajar el coste por operación: qué medir y qué configurar

El sistema hace ~239 operaciones al año. El spread se paga entero en cada una, así
que **es el número que decide si gana o pierde**, por encima de cualquier ajuste
de la estrategia. Medido sobre 4.410 operaciones de 19,6 años:

| Spread | Resultado 19,6 años | Solo 2024-2026 |
|---|---|---|
| 0,20 $ | −0,0088 R/op | +0,0798 R/op |
| **0,30 $** | −0,0281 R/op | **+0,0715 R/op** |
| 0,50 $ | −0,0668 R/op | +0,0549 R/op |
| 1,00 $ | −0,1634 R/op | +0,0132 R/op |
| 1,45 $ | −0,2503 R/op | −0,0242 R/op |

**Objetivo: 0,25-0,30 $ por operación completa (abrir + cerrar).**

## Cómo medirlo bien

1. **Cuenta el coste TOTAL de ida y vuelta.** Si la cuenta cobra comisión aparte
   del spread, súmala. Lo que importa es lo que se pierde entre abrir y cerrar.
2. **Mídelo en las horas en que el sistema opera**, no en el mejor momento del
   día. Estas 6 horas concentran el 31 % de las entradas (hora de Madrid):

   `01:00  02:00  03:00  16:00  17:00  18:00`

   Las de la madrugada son la sesión asiática y las de la tarde la americana.
3. **No lo midas en la reapertura** (00:00 de Madrid): es el peor momento del día
   y no representa al resto.
4. Anota el peor valor que veas, no el mejor. El anunciado en la web suele ser el
   mínimo en el mejor momento.

## Qué tipo de cuenta buscar

* **Cuenta «raw» o ECN con comisión**, en vez de spread incluido. El oro suele
  quedar en 0,10-0,25 $ de spread más una comisión fija.
* **Futuros de oro** (el micro MGC son 10 oz): la comisión por ida y vuelta suele
  equivaler a 0,02-0,05 $/oz. Es la vía más barata, pero exige cuenta de futuros.
* Entre brókers de CFD el spread del oro varía mucho. Merece la pena comparar.

Esto no es una recomendación de ningún bróker concreto: son las cifras que hay
que exigirle a cualquiera.

## Qué configurar cuando la tengas

En GitHub: **Settings → Secrets and variables → Actions → pestaña «Variables»**,
botón «New repository variable»:

| Variable | Valor |
|---|---|
| `ORO_COSTE_OPERACION` | tu coste real de ida y vuelta, p. ej. `0.28` |

Con eso todos los informes pasan a calcular con tu coste real. Si pones un valor
por encima de 1 $, el sistema avisa solo al validar la configuración: por encima
de ahí pierde por costes, no por las señales.

Las demás variables de la operativa (`ORO_CAPITAL`, `ORO_RIESGO_POR_OPERACION`,
`ORO_TRAILING_R`, `ORO_ZONA_HORARIA`…) también llegan ya a producción y se
configuran igual. Antes no: se podían definir y no llegaban al proceso.
