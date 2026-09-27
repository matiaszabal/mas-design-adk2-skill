# Lista de revisión — con cómo comprobar cada punto

Sirve para revisar código propio o generado **sin leerlo línea por línea**. Cada punto tiene una comprobación concreta; si no se puede comprobar, se anota como «no verificado».

## Terminación

1. **Hay un tope de código en todo bucle, fan-out o gasto abierto.**
   - Buscar: contadores, `max_*`, `for _ in range(N)`, `RunConfig(max_llm_calls=…)`.
   - Comprobar: reemplazar el modelo por uno falso que **nunca** termina y verificar que el sistema corta (`test_sin_llm.py`, chequeo S1).
2. **El tope no depende de que el modelo lo respete.** El modelo puede dar por terminado demasiado pronto (hallazgo A6) o no terminar nunca.
3. **Al cortar por tope se informa.** El resultado dice que fue por tope (`motivo_fin`) y qué quedó pendiente.

## Contexto

4. **Cada agente ve solo lo que debe.**
   - Comprobar: `before_model_callback` que loguee `len(llm_request.contents)` y los roles (`qd.log_contexto`); o el modelo falso (`ModeloFalso.llamadas`).
   - Esperado para agentes aislados: **1** contenido. Si aparece más de uno, ADK está sumando contexto (ver A1).
5. **Lo que persiste entre iteraciones está en el estado**, no en el `node_input` (al volver por un ciclo, `node_input` es la salida del nodo de decisión).
6. **Los artefactos son inspeccionables** (plan, borrador, notas, hechos): aparecen como `output` de un nodo y se ven en la traza.

## Orquestación

7. **Fan-out con agentes o funciones `async`.** Una función síncrona serializa el fan-out. Comprobar el tiempo total contra la suma (`test_sin_llm.py`, P4).
8. **Cada nodo emite un solo `output`.**
9. **No hay ciclos incondicionales** (ADK los rechaza al construir el grafo); todo ciclo tiene una arista con ruta.
10. **Especialistas `single_turn`:** `disallow_transfer_to_parent=True` y `disallow_transfer_to_peers=True`.
11. **No hay `mode='task'` dentro de un grafo.**

## Calidad y honestidad

12. **Camino sin evidencia:** una entrada sin respuesta en los datos produce «sin evidencia», no una invención. Probar con una pregunta cuya respuesta no está.
13. **Corridas reales repetidas** (≥3) con datos sintéticos, y se reporta la tasa de aciertos. Una sola corrida no prueba nada.
14. **Los fallos se registran**, no se retocan hasta que desaparezcan. Guardar la salida (`salidas/`).
15. **Datos:** ¿alguno es real o sensible? Si sí, el destino (modelo, región, almacenamiento) está aprobado **antes** de correr.

## Qué reportar al terminar

- Qué se verificó y cómo (con qué archivo de salida).
- Qué **no** se verificó.
- Qué se cambió en el camino para que pasara (p. ej. una instrucción, un parámetro de recuperación) y por qué.
