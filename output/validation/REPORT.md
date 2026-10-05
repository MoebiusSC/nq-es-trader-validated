# Resultado de la revisión y pruebas

Fecha: 5 de octubre de 2026.
Origen: `s-k-28/nq-es-trader-5k-payout`, commit
`0ee4392d4e11b1ab9a110cc05122f70c3b8af667`. Se conserva la licencia MIT.

**Conclusión: el histórico corregido tiene rentabilidad media negativa al incluir
los costos base asumidos. Las cifras anteriores del proyecto no validan esta
versión.** Pasar las pruebas de software demuestra el comportamiento comprobado;
no demuestra rentabilidad.

## Pruebas

- Suite completa: 170 pruebas aprobadas; 52 avisos de funciones obsoletas.
- Adaptador de investigación: 2 pruebas aprobadas, incluyendo igualdad de señales
  con el recorrido original de pandas sobre una muestra distribuida entre años.
- Total: 172 pruebas aprobadas en dos ejecuciones. Se conservan los resultados
  JUnit y los registros en esta carpeta.
- Casos comprobados: pérdida diaria excedida, colisión stop/objetivo, saltos de
  precio, stop móvil, comisiones, horario de cierre, límites configurados,
  infracciones por cuenta, muestras insuficientes, dependencia entre cuentas,
  registros incompletos y normalización de fechas al horario de Nueva York.

## Recálculo histórico

1.122.432 velas de un minuto, del 26 de diciembre de 2022 al 1 de mayo de 2026.
Mismas reglas y señales de estrategia; ejecución conservadora en los tres casos.
El número de operaciones cambia por los filtros de riesgo, costos y límites.

| Escenario | Operaciones | Rentabilidad media por operación | Factor de beneficio | Total R | Caída máxima R |
|---|---:|---:|---:|---:|---:|
| Sin costos, ejecución conservadora | 3.186 | +0,0269 R | 1,076 | +85,74 | -31,83 |
| Costos base | 3.182 | -0,0611 R | 0,845 | -194,43 | -231,00 |
| Costos duplicados | 3.022 | -0,1542 R | 0,646 | -465,86 | -472,45 |

R expresa el resultado como múltiplo del riesgo inicial de cada operación.
Costos base: 1 tick de deslizamiento en entrada y salidas a mercado; USD 0,62
de comisión por lado y contrato MNQ. Estrés: 2 ticks y USD 1,24 por lado.
Son supuestos configurables, no tarifas verificadas de un intermediario.

## Monte Carlo

Se ejecutaron 25.000 simulaciones de evaluación y 25.000 de cuenta fondeada por
escenario: 150.000 simulaciones en total, con semillas fijas y bloques de cinco
días. Se usaron únicamente resultados diarios del tramo 2026, de 80 días con
operaciones. Estos resultados no son comparables directamente con simulaciones
del README basadas en otras muestras y supuestos.

| Escenario | Supervivencia fondeada a 60 días | Probabilidad simulada de extraer USD 5.000 |
|---|---:|---:|
| Sin costos | 82,31% | 79,65% |
| Costos base | 61,51% | 58,74% |
| Costos duplicados | 18,92% | 13,47% |

El tramo 2026 tiene comportamiento distinto al histórico agregado. El simulador
diario no reconstruye caídas intradía, liquidez ni interrupciones de ejecución.
Remuestrear una serie favorable no acredita que la ventaja continúe en vivo.

## Límites y reproducción

No se conectó ningún broker ni se enviaron órdenes. No hay nuevos registros
reales para validar rendimiento futuro. Los cortes por año usan reglas congeladas;
la fecha original de selección y ajuste de modelos no queda demostrada.

Consultar `docs/VALIDATION_CHANGES.md` para las correcciones y los límites del
modelo. Los CSV y `research_results.json` permiten auditar el recálculo.

```
python -m pip install -r requirements-tested.txt
python -m pytest tests -q
python scripts/validate_research.py
```
