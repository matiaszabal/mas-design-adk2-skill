# Plantilla de especificación (las tres preguntas)

Se completa **antes** de construir. Es lo que se le da a un asistente de código. Ejemplo completo: `../ejemplos/query_decomposition/especificacion.md`.

## 0. Encabezado

- **Problema** (no la solución) y **quién** lo usa.
- **Arquetipo elegido** y **por qué no uno más simple** (Reflex → ReAct → Planner-Executor / Query Decomposition → Deep Research; Reflection se agrega sobre cualquiera si un error es costoso y hay algo verificable).
- **Diagrama ASCII del diseño** (nodos, quién decide en cada uno, ruta de escape y topes), confirmado por el usuario antes de construir.
- **Datos:** sintéticos o reales. Si son reales o sensibles, **primero** confirmar que el destino está aprobado (región, contrato, control de acceso).

## 1. ¿Quién decide qué se ejecuta después?

Completar según el arquetipo:

- **Reflex:** ¿la decisión es una regla o una sola inferencia? ¿Cuál es la ruta de escape si la entrada no encaja?
- **ReAct:** ¿qué herramientas hay y cuáles descripciones evitan ambigüedad? ¿Qué pasa si una herramienta falla?
- **Planner-Executor:** ¿quién valida el plan (regla o persona)? ¿Qué se hace si un paso falla: reintentar, replanificar (cuántas veces) o escalar?
- **Query Decomposition:** ¿las sub-preguntas son independientes (paralelo) o una depende de la anterior (secuencial)? ¿Quién genera la partición?
- **Reflection:** ¿quién es el crítico y contra qué rúbrica juzga? ¿Hay una señal externa (pruebas, reglas, validador)?
- **Deep Research:** ¿qué decide el director en cada ronda? ¿Cuántos investigadores en paralelo?

## 2. ¿Con qué contexto?

- Para **cada** agente o paso: qué **debe** ver y qué **no** debe ver.
- Decidir la forma de compartir: historial completo · artefacto explícito · resumen o notas · contexto aislado.
- Anotar qué **palanca** lo garantiza. En ADK 2.9.1 el aislamiento no es automático: `include_contents='none'` + todo por `node_input` (hallazgo A1).
- Qué persiste entre iteraciones y dónde vive (estado de la sesión, no el `node_input`).

## 3. ¿Cuándo se detiene?

- **Cierre normal:** ¿qué señal, y quién la declara (el modelo, el código, un presupuesto)?
- **Topes de código** (obligatorios si hay bucle, fan-out o gasto abierto): número máximo de iteraciones, de sub-tareas, de paralelismo, de llamadas al modelo, de tiempo.
- **Qué se entrega al cortar por tope:** el mejor resultado parcial **y** la lista de lo que quedó sin resolver. Nunca un resultado que aparente estar completo.
- **Degradación:** qué hace el sistema si falta evidencia («sin evidencia», no inventar).

## 4. Criterios de aceptación

Verificables y numerados. Al menos uno por cada pregunta:

- uno de **resultado** (una entrada con salida conocida),
- uno de **contexto** (qué ve cada agente, medible),
- uno de **tope** (con un modelo que nunca termina, el sistema corta).

## 5. Restricciones

Qué no debe hacer el sistema (datos, herramientas, `mode='task'` dentro de grafos, despliegue).
