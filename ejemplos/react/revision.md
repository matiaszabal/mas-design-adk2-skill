# Revisión del ejemplo ReAct contra la lista de verificación

Estado: **OK** · **PARCIAL** · **N/A** · **NO VERIFICADO**. Lista: `../../references/checklist_revision.md`.

## Terminación

1. **Tope de código:** PARCIAL. `RunConfig(max_llm_calls=N)` corta: con un modelo que nunca termina, **lanza `LlmCallsLimitExceededError`** tras N llamadas y **el usuario no recibe ningún texto** (A3; con Gemini real y N=2 también). **Sin tope explícito el valor por defecto deja pasar 500 llamadas** (5,3 s con modelo falso). El ejemplo **no** trae el manejo de esa excepción: el llamador debe atraparla y responder algo.
2. **El tope no depende del modelo:** OK (lo aplica ADK). **Pero ADK no detecta llamadas repetidas** (A3).
3. **Al cortar se informa:** NO VERIFICADO/no implementado: la excepción llega sin respuesta final.

## Contexto

4. **Cada agente ve solo lo que debe:** N/A: en ReAct el historial es la memoria de trabajo. Medido: el contexto crece **2 contenidos por herramienta** (1, 3, 5, 7, 9) y **`include_contents='none'` no lo cambia** dentro de la invocación (A2): solo excluye turnos previos.
5-6. **Estado y artefactos:** las llamadas y resultados de herramientas se ven en la traza.

## Orquestación

7-11. **N/A o OK.** Sin grafo ni fan-out; sin agentes deprecados.
- **Herramientas que fallan:** OK, medido. Una herramienta que **lanza una excepción mata toda la corrida** y el modelo nunca ve el error (A4). Una que **devuelve `{"error": …}` deja continuar**. Una herramienta inexistente o con argumentos equivocados: ADK devuelve al modelo un mensaje que lista las herramientas disponibles o el parámetro que falta.
- **No hay compuerta:** OK, medido. Si el modelo pide `solicitar_reembolso` sin verificar, **se ejecuta** (A5). «Verificá antes» es solo una instrucción.

## Calidad y honestidad

12. **Camino sin evidencia / decisión correcta:** OK. Sin duplicado real (C-002): **6/6** sin reembolso y sin afirmaciones falsas.
13. **Corridas reales repetidas:** OK. Con el duplicado real (C-001), **9 corridas** (dos tandas): **5/9** abrieron el reembolso; **4/9** dijeron haberlo abierto (3) o prometieron hacerlo (1) **sin llamar a la herramienta**. n pequeño.
14. **Fallos registrados:** OK.
    - **Acción alucinada:** «Se ha generado una solicitud de reembolso» / «he solicitado el reembolso» con solo 3 llamadas a herramientas (ninguna `solicitar_reembolso`). Es el fallo más importante del arquetipo.
    - **Mi auditoría tuvo un falso negativo** en su primera versión (no detectaba «Procederé a solicitar…», una promesa futura); se amplió y se reevaluó sobre las salidas guardadas sin volver a llamar al modelo (`auditar_salidas.py`).
    - Las salidas de la primera tanda (sin auditoría) están en `salidas/_previas_sin_auditoria/`.
15. **Datos:** OK, sintéticos.

## Pendiente en este ejemplo

- Mitigar la acción alucinada (p. ej., respuesta final estructurada que incluya el `ticket`, o que el código redacte la confirmación desde el resultado real de la herramienta) y medir.
- Implementar el manejo de `LlmCallsLimitExceededError` y una respuesta de degradación.
- Probar más herramientas / un bucle largo para ver el crecimiento del contexto y su costo real.
- Describirlo en YAML (pendiente general).
