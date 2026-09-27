# Revisión del ejemplo Reflection contra la lista de verificación

Estado: **OK** (comprobado, con dónde) · **PARCIAL** · **N/A** · **NO VERIFICADO**. Lista: `../../references/checklist_revision.md`.

## Terminación

1. **Tope de código:** OK. `MAX_RONDAS = 3`, contador en el estado. Con un crítico que nunca aprueba, escala en la ronda 3 (R2, `salidas/test_sin_llm.salida.txt`).
2. **El tope no depende del modelo:** OK. `decidir` corta por contador aunque el modelo insista.
3. **Al cortar se informa:** OK. La ruta `escalar` entrega `ultimo_borrador` y `pendiente`.

## Contexto

4. **Cada agente ve solo lo que debe:** OK con `include_contents='none'` → 1 contenido en todas las rondas (modelo falso R5 y Gemini real). Con `default` el contexto **crece por ronda**: generador `[2, 6, 10]`, crítico `[4, 8, 12]` (R5, y confirmado con Gemini real en las corridas de `salidas/_previas_validador_ingenuo/`).
5. **Lo que persiste va al estado:** OK. `feedback`, `ronda`, `validacion`, `borrador_texto` se guardan con `Event(state=…)`; el feedback también viaja como `output` de `decidir` para que el generador no reciba un `node_input` vacío al volver por el ciclo.
6. **Artefactos inspeccionables:** OK. Borrador, evidencia del validador, veredicto y decisión aparecen en la traza (`correr_real.py`).

## Orquestación

7. **Fan-out:** N/A. 8. **Un `output` por nodo:** OK. 9. **Ciclos:** OK. El ciclo pasa por una arista con ruta (`revisar`), y ADK lo acepta. 10. **`single_turn`:** N/A. 11. **Sin `mode='task'`:** OK. **Sin agentes deprecados:** OK (solo `Workflow`).

## Calidad y honestidad

12. **Camino sin evidencia:** N/A para este arquetipo.
13. **Corridas reales repetidas:** OK, 3 por configuración (validador corregido): aislado → publicado en 1, 1 y 2 rondas; contexto por defecto → publicado en 1, 1 y 1 ronda. **El ciclo se ejercitó en 1 de 6 corridas** (el crítico pidió más empatía; el generador corrigió y se aprobó). Con n=3 no hay conclusión sobre la calidad relativa del aislamiento.
14. **Fallos registrados:** OK. La primera versión del validador marcaba una **negación** («no es posible garantizar un reembolso inmediato») como promesa. Eso forzó una revisión innecesaria y el crítico terminó **alineándose con la evidencia errónea**. Las corridas de esa versión están en `salidas/_previas_validador_ingenuo/` y **no son interpretables** como comparación de contexto, porque el validador estaba mal.
15. **Datos:** OK, sintéticos.

## Variante YAML (hecho)

`yaml_reflection/root_agent.yaml` describe el mismo `Workflow`. **OK:** carga con `from_config`; equivalencia estructural y de comportamiento (`test_yaml.py`, 13 chequeos con modelo falso); 3 corridas reales por script (publicado en la ronda 1, contexto 1); y ejecución por `adk web` + API con Gemini real (`salidas/adk_web_yaml.salida.txt`). **PARCIAL:** el camino `revisar` del YAML solo se ejerció con el modelo falso. Los nodos de decisión siguen siendo Python (hallazgo A9).

## Pendiente en este ejemplo

- Ejercitar el ciclo más veces con Gemini real (p. ej. 10 corridas) y medir cuántas rondas hacen falta.
- Probar la variante de **workflow dinámico** (`while` con `ctx.run_node`).
- Medir un crítico complaciente real (en las corridas hechas nunca aprobó algo que el validador rechazara).
