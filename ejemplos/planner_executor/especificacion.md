# Especificación — Planner-Executor (conciliación mensual de un banco ficticio)

Documento que escribe el alumno antes de pedirle a un asistente de código que construya el agente. Instancia de `../../references/plantilla_especificacion.md`.

## 1. Objetivo y alcance

- **Problema:** conciliar los movimientos internos con el extracto bancario de un período y redactar un informe de diferencias.
- **Arquetipo elegido:** Planner-Executor, porque el camino es conocido y largo, tiene pasos con dependencias (algunos independientes) y conviene poder **revisar el plan antes de ejecutar**.
- **Por qué no uno más simple:** una pasada no alcanza; **por qué no ReAct:** no es exploratorio y se exige aprobación previa.
- **Datos:** sintéticos (`pe.py`).

## 2. Las tres decisiones

### ¿Quién decide qué se ejecuta después?

- **El LLM (planner) decide una vez** el recorrido completo, como un **plan**: lista de pasos con `id`, `herramienta`, `entradas` (ids de pasos previos) y `parametro`.
- **El código valida el plan** antes de ejecutar: herramientas conocidas, cantidad de entradas correcta, dependencias hacia pasos anteriores o ya completados, sin ids repetidos, máximo de pasos.
- **Una persona aprueba** el plan (`RequestInput`) cuando `APROBACION_HUMANA` está activa.
- **El ejecutor es código:** corre los pasos por **oleadas** según sus dependencias (los independientes en paralelo). No vuelve a decidir «qué sigue».

### ¿Con qué contexto?

- **Planner** (`include_contents="none"`): el objetivo, el catálogo de herramientas y, al replanificar, lo ya hecho y el error. **No ve datos reales.**
- **Cada paso** recibe solo `{parametro, entradas}`: su parámetro y las **salidas de sus dependencias**. No ve el objetivo ni el resto del plan.
- **El plan** es el artefacto compartido (en el estado); los resultados de los pasos hechos también.

### ¿Cuándo se detiene?

- **Cierre normal:** todos los pasos hechos → `COMPLETADO`.
- **Si un paso falla:** se replanifica hasta `MAX_REPLANES = 1` vez, **conservando lo ya hecho**. Un plan inválido o unas observaciones del revisor también cuentan como replanificación.
- **Tope:** al agotarse, se **escala a una persona** informando lo hecho, lo pendiente y el **historial completo de fallas** (incluido el error original de la herramienta).

## 3. Criterios de aceptación

1. Con un plan correcto: `COMPLETADO` y un informe que menciona las diferencias reales (M3 solo en libros; B9 solo en el banco).
2. Los pasos independientes corren en paralelo.
3. Cada herramienta recibe solo su parámetro y las salidas de sus dependencias.
4. Si un paso falla, el replan reutiliza lo ya hecho y no repite pasos completados.
5. Un plan inválido no ejecuta ninguna herramienta.
6. Con aprobación humana, no se ejecuta nada antes de aprobar, y reanudar no vuelve a llamar al planner.
7. Con un planner que insiste con un plan que falla, se escala tras el tope y el historial conserva el error original.

## 4. Restricciones

- Sin datos reales. Solo invocación de modelo (solo el planner es un LLM). Solo `Workflow`; sin agentes deprecados.
- El ejecutor no debe ser un agente LLM: las herramientas son funciones deterministas.
