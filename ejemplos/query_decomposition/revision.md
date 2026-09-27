# Revisión del ejemplo contra la lista de verificación

Se aplica `../../references/checklist_revision.md` a este ejemplo. Estado: **OK** (comprobado, con dónde) · **PARCIAL** · **N/A** · **NO VERIFICADO**.

## Terminación

1. **Tope de código:** OK. `MAX_SUBPREGUNTAS`, `MAX_PARALELO`, `MAX_PASOS` en `qd.py`. Comprobado con un modelo falso que propone 9 sub-preguntas (P3) y con uno que nunca dice «terminar» (S1). `test_sin_llm.py` → `salidas/test_sin_llm.salida.txt`.
   - **PARCIAL:** `max_parallel_workers` se acepta pero **no se midió** que limite la concurrencia.
2. **El tope no depende del modelo:** OK. En la corrida real inicial el modelo dio por terminado el trabajo tras un solo hecho; el tope de código no lo habría evitado, y por eso se corrigió la instrucción (A6). Un tope protege del bucle infinito, no de la terminación prematura.
3. **Al cortar por tope se informa:** OK en la secuencial (`motivo_fin` llega al sintetizador; S1). **NO aplica** a la paralela, donde el recorte de sub-preguntas se guarda en el estado (`recortadas`) pero no se le informa al sintetizador.

## Contexto

4. **Cada agente ve solo lo que debe:** OK con `include_contents='none'`: 1 contenido en todas las llamadas (modelo falso P1, y Gemini real en 3 corridas de paralela y 3 de secuencial). Con `default` se filtra la pregunta original y el plan completo (P2, `explorar_palancas.py`, corridas reales).
5. **Lo que persiste va al estado:** OK. La pregunta original viaja por `Event(state=…)` hasta el sintetizador (corrida real).
6. **Artefactos inspeccionables:** OK. El plan (lista de sub-preguntas) y las respuestas parciales aparecen como `output` en la traza (`traza.py`, `correr_real.py`).

## Orquestación

7. **Fan-out en paralelo real:** OK. 4 workers de 0,4 s → 0,42 s (P4).
8. **Un `output` por nodo:** OK (cada nodo hace un solo `yield Event(output=…)`).
9. **Ciclos incondicionales:** N/A (no hay ciclos en el grafo; el bucle secuencial es un `for` dentro de un nodo dinámico).
10. **`single_turn` con `disallow_transfer_*`:** N/A (no se usan subagentes).
11. **Sin `mode='task'`:** OK.

## Calidad y honestidad

12. **Camino «sin evidencia»:** PARCIAL. Ocurrió en una corrida real (la de la mala descomposición) y el sintetizador lo informó sin inventar (`salidas/salida_real_paralela_none_2.txt`), pero **no se probó a propósito** con una pregunta cuya respuesta no está en la base.
13. **Corridas reales repetidas:** OK, 3 por configuración: paralela aislada **2/3**, paralela con contexto por defecto **2/3**, secuencial **3/3** (`salidas/salida_real_*_N.txt`). n=3: no alcanza para comparar calidad entre configuraciones.
14. **Fallos registrados:** PARCIAL. Se conserva la tanda intermedia (top-2, sin IDF) en `salidas/_previas_k2/`. **No se conservaron** las salidas de las corridas anteriores (incluida la primera secuencial que dio 15 USD); constan solo en la conversación. La instrucción de `siguiente` cambió tras ese fallo (A6) y la recuperación tras un confound (A6).
15. **Datos:** OK. Base sintética de un banco ficticio (`kb.py`), sin datos reales.

## Pendiente en este ejemplo

- Probar a propósito una pregunta sin respuesta en la base (punto 12).
- Informar al sintetizador cuando se recortan sub-preguntas (punto 3).
- Mitigar la mala descomposición, p. ej. dándole al descomponedor el catálogo de temas de la base. **No se aplicó**: se dejó el fallo visible.
- Abrir `adk web` en el navegador y revisar la traza en su interfaz (solo se verificó `/list-apps`).
