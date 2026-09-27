# Revisión del ejemplo Planner-Executor contra la lista de verificación

Estado: **OK** · **PARCIAL** · **N/A** · **NO VERIFICADO**. Lista: `../../references/checklist_revision.md`.

## Terminación

1. **Tope de código:** OK. `MAX_REPLANES = 1` y `MAX_PASOS = 6` (T5, T6). Con un planner que insiste con el plan que falla: escala tras 2 llamadas al planner.
2. **El tope no depende del modelo:** OK. Lo aplica `decidir_falla` (código).
3. **Al cortar se informa:** OK. `ESCALADO A HUMANO` incluye `hecho`, `pendiente` e `historial_de_fallas`. **Mejora hecha tras un fallo de mi propio test (T5):** al principio solo reportaba el último motivo (un plan inválido) y se perdía el error original de la herramienta; ahora se acumula el historial.

## Contexto

4. **Cada agente/paso ve solo lo que debe:** OK. Planner con `include_contents='none'`: 1 contenido en todas las llamadas (falso y Gemini real). Cada herramienta recibe solo `{parametro, entradas}` (T2). Con `default`, el planner ve `[2, 4]` contenidos en dos vueltas (T8, modelo falso).
5. **Lo que persiste va al estado:** OK. `plan`, `resultados`, `replanes`, `feedback`, `historial`.
6. **Artefactos inspeccionables:** OK. El plan validado se ve en la traza (`validar_plan`) y es lo que se le muestra al aprobador.

## Orquestación

7. **Fan-out paralelo:** OK. Oleadas con `asyncio.gather` de `ctx.run_node`: 4 oleadas × 0,4 s → 1,62 s (serial: ≥ 2,0 s) (T3).
8. **Un `output` por nodo:** OK. 9. **Ciclos:** OK (ciclo por ruta `replanificar`). 10. **`single_turn`:** N/A. 11. **Sin `mode='task'` ni agentes deprecados:** OK.
12. **Camino sin evidencia:** N/A. **Plan inválido:** OK, se rechaza antes de ejecutar (T6).
13. **Corridas reales repetidas:** OK, 3 por escenario con Gemini como planner: julio **3/3** (0 replanificaciones), agosto **3/3** (1 replanificación cada una: el planner leyó el error y usó `;alt`), agosto con aprobación humana simulada **3/3** (2 pausas cada una). n=3.
14. **Fallos registrados:** OK. T5 falló al principio y llevó a acumular el historial de fallas.
15. **Datos:** OK, sintéticos.

## Aprobación humana

- **OK:** `RequestInput` pausa el flujo **antes** de ejecutar (0 herramientas ejecutadas), la respuesta reanuda, y **reanudar no vuelve a llamar al planner** (T7). Con observaciones: replanifica y vuelve a pedir aprobación.
- **PARCIAL:** se usa `google.adk.workflow.utils._workflow_hitl_utils` (módulo privado de ADK: `create_request_input_response`, `get_request_input_interrupt_ids`), como en los experimentos del módulo. La persistencia entre procesos distintos **no se probó aquí** (sesión en memoria).

## Pendiente en este ejemplo

- Probar un planner real que **repita ids ya usados** o proponga un plan inválido (no ocurrió en las corridas reales).
- Probar la aprobación humana con una sesión persistente (proceso distinto entre pausa y reanudación).
- Describirlo en YAML (pendiente general de la próxima iteración).
- Comparar con `ejemplos_slides_adk2/planner_executor_workflow.py`, cuyo ejecutor es un único agente LLM con herramientas: ahí «el ejecutor no decide» no se cumple.
