---
name: mas-design-adk2
description: Puente entre los 6 arquetipos de agentes (Reflex, ReAct, Planner-Executor, Query Decomposition, Reflection, Deep Research) y las capacidades de ADK 2 (Workflow en grafo, workflows dinámicos, colaboración). Especifica un arquetipo con tres preguntas (quién decide qué sigue, con qué contexto, cuándo se detiene), lo mapea a primitivas de ADK2, y lo revisa con una lista de verificación. Usar al diseñar, construir o revisar un agente con ADK 2.x a partir de un arquetipo, o cuando un usuario pregunta cómo implementarlo sin escribir el código a mano.
version: 0.1-mvp
updated: 2026-09-26
---

# mas-design-adk2 — de arquetipo a ADK2, con evidencia

**Estado: MVP.** Los seis arquetipos tienen un ejemplo verificado. **Reflex, ReAct, Planner-Executor, Query Decomposition, Reflection y Deep Research** están verificados de punta a punta en ADK 2.9.1 (ejemplos corridos con y sin modelo real); el skill lo dice en cada caso. Solo se usan los workflows nuevos (`Workflow`, dinámico, colaboración): `SequentialAgent`, `ParallelAgent` y `LoopAgent` están deprecados. No afirmes más de lo que dice `references/mapeo_arquetipos_adk2.md`.

## Cuándo usar

- Diseñar o construir un agente ADK2 a partir de un arquetipo.
- Revisar código de orquestación (propio o generado por un asistente) contra las tres preguntas.
- Responder a un usuario: «¿cómo implemento el arquetipo X con ADK, sin escribir el código?».

## Cuándo NO usar

- Para scaffolding, evaluación, despliegue o publicación: eso lo cubren los skills `google-agents-cli-*` (ver «Relación con agents-cli»).
- Para enseñar los arquetipos en abstracto (sin ADK): el material de arquetipos del curso (no incluido en este repositorio).
- Para copiar código de repos externos: este skill **no** los replica (se desactualizan y no se sabe qué versión de ADK usan).

## Flujo

1. **Elegir el arquetipo.** Empezar por lo más simple que resuelva la tarea. Árbol de decisión de cinco preguntas en `references/mapeo_arquetipos_adk2.md` («Cómo elegir»).
2. **Especificar con las tres preguntas** (`references/plantilla_especificacion.md`), **haciendo las «Preguntas de descubrimiento» de abajo antes de escribir código**. Ejemplo completo: `ejemplos/query_decomposition/especificacion.md`. Si el usuario no puede responderlas, todavía no está listo para construir.
3. **Mapear a capacidades de ADK2** (`references/mapeo_arquetipos_adk2.md`): qué palanca da el control, cuál el contexto, cuál la terminación. Marca qué está verificado.
4. **Construir.** Con un asistente de código y los skills `google-agents-cli-adk-code` / `-workflow`. El asistente recibe la especificación, no una idea vaga.
5. **Verificar** (`references/checklist_revision.md`), en este orden:
   1. Prueba **sin LLM real** con un modelo falso que registre lo que ADK envía a cada agente (`ejemplos/query_decomposition/modelo_falso.py`, `test_sin_llm.py`). Cubre estructura, topes y contexto, sin costo.
   2. **Contexto observable:** `before_model_callback` que registre cuántos contenidos y de qué roles recibe cada llamada (`log_contexto` en `qd.py`).
   3. **Corridas reales**, varias (≥3) y con datos sintéticos. Reportar la tasa de aciertos, no una sola corrida.
6. **Registrar la evidencia** (salidas guardadas) y lo no verificado.

## Preguntas de descubrimiento

**Regla de conducta:** antes de escribir código, hacé estas preguntas **de a una fase por vez**, en orden. Ofrecé un valor por defecto para cada una (con el hallazgo que lo respalda) y aceptá «no sé»: en ese caso, anotalo como **decisión pendiente** en la especificación en lugar de inventar la respuesta. **No generes código hasta que la especificación esté aceptada.** Estas preguntas y su orden **no se probaron con el skill instalado**.

### Fase 1 · El problema (plantilla, sección 0)
1. ¿Cuál es el problema real (no la solución) y quién lo usa?
2. ¿Los datos son sintéticos o reales? Si son reales o sensibles: ¿el destino (modelo, región, almacenamiento) está aprobado **antes** de correr nada?
3. ¿Qué es un resultado correcto? Pedí un caso con entrada y salida conocidas.

### Fase 2 · El arquetipo (cinco preguntas de `references/mapeo_arquetipos_adk2.md`)
4. ¿Alcanza una sola pasada? → Reflex. Si no: ¿se parte en sub-preguntas conocibles? → Query Decomposition. ¿Se conocen los pasos y conviene aprobarlos antes? → Planner-Executor. ¿Es abierta y justifica un costo muy alto? → Deep Research; si no → ReAct.
5. ¿Un error es costoso y existe un criterio verificable? → agregar Reflection.
6. Proponé el arquetipo **y explicá por qué no uno más simple**. Esperá confirmación.

### Fase 3 · Las tres decisiones (plantilla, secciones 1 a 3)
7. **¿Quién decide qué sigue?** Qué decide el modelo y qué decide el código.
8. **¿Con qué contexto?** Para cada agente o paso: qué **debe** ver y qué **no**. Recordá que el aislamiento no es automático (`include_contents="none"`; con paralelos, `use_sub_branch=True`).
9. **¿Cuándo se detiene?** Señal de cierre, **tope de código** (iteraciones, rondas, llamadas, fan-out) y **qué se entrega al cortar**.

### Fase 4 · Preguntas propias del arquetipo
- **Reflex:** ¿la decisión es una regla o una inferencia? ¿Cuál es la **ruta de escape** (`DEFAULT_ROUTE`)? ¿Qué colas son de prioridad alta y **puede un mensaje elegirlas por sí solo** (inyección)? ¿Cuánta latencia tolerás? (≈ 2,8 s con LLM, ≈ ms con reglas.) Si hay reglas: ¿qué **precedencia** tienen?
- **ReAct:** ¿Qué herramientas hay y qué devuelven cuando fallan? (Devolver `{"error": …}`, no lanzar excepciones.) ¿Cuál es el **tope de llamadas** y qué se le responde al usuario si se agota? (Por defecto son 500 y se lanza una excepción.) ¿Hay acciones **con efecto**? ¿Quién las aprueba? ¿Cómo se **audita lo que el modelo afirma** contra lo que se ejecutó?
- **Planner-Executor:** ¿Quién **valida** el plan (reglas de código) y quién lo **aprueba** (¿una persona con `RequestInput`?)? ¿El ejecutor es código, no un LLM? ¿Cuántas **replanificaciones** y qué se **conserva** de lo ya hecho? ¿Qué se entrega al escalar (incluido el historial de fallas)?
- **Query Decomposition:** ¿Las sub-preguntas son independientes (paralelo) o cada una depende de la anterior (secuencial)? ¿Tope de sub-preguntas? ¿Cómo se recupera la evidencia y qué pasa **sin evidencia**? ¿Cada sub-pregunta ve solo lo suyo?
- **Reflection:** ¿Quién critica y con qué **rúbrica**? ¿Hay una **señal externa** determinista? (Probala contra texto **correcto**: una negación no es una promesa.) ¿El **código prevalece** sobre el crítico? ¿Tope de rondas y qué se entrega al escalar?
- **Deep Research:** ¿Qué temas y entidades debe cubrir? ¿Presupuesto de rondas, de llamadas y de investigadores? ¿Qué hacés si el evaluador **nunca queda conforme**? (Ocurrió 3 de 3.) ¿Cómo se cita (una fuente por afirmación) y quién verifica el respaldo?

### Fase 5 · Aceptación y restricciones (plantilla, secciones 4 y 5)
10. Proponé criterios **numerados y verificables**, al menos uno por cada pregunta (resultado, contexto, tope). ¿Los aceptás o los cambiás?
11. ¿Qué **no** debe hacer el sistema? (datos, herramientas, acciones irreversibles, agentes deprecados.)
12. Resumí la especificación completa, con las **decisiones pendientes** marcadas, y pedí confirmación explícita **antes de construir**.

## Cómo usarlo

> **Sin probar.** Este recorrido y las frases de ejemplo se escribieron a partir del flujo y de los ejemplos del repositorio; **no se probaron con el skill instalado** ni se comprobó que se dispare con la descripción del encabezado. Instalarlo: ver `README.md`.

### Recorrido de punta a punta (ejemplo: «un agente que verifica un cobro duplicado antes de reembolsar»)

1. **Pedir el diseño, no el código.** Contás el problema; el skill no escribe código todavía.
2. **Elegir el arquetipo.** Se aplican las cinco preguntas de `references/mapeo_arquetipos_adk2.md` («Cómo elegir»). Aquí: el camino no se conoce de antemano y hay pocas herramientas → **ReAct**; como hay una acción con efecto, conviene agregar una auditoría de lo que el modelo afirma.
3. **Especificar con las tres preguntas** (`references/plantilla_especificacion.md`): quién decide qué sigue, con qué contexto, cuándo se detiene, más criterios de aceptación numerados y restricciones. Un ejemplo completo por arquetipo está en `ejemplos/<arquetipo>/especificacion.md`.
4. **Mapear a ADK2** con `references/mapeo_arquetipos_adk2.md`: qué palanca da el control, cuál el contexto y cuál la terminación, y qué está verificado.
5. **Construir** con un asistente de código y los skills `google-agents-cli-*`, entregándole **la especificación** (no una idea vaga).
6. **Verificar** en el orden de «Flujo», paso 5: tests sin modelo real, contexto observable, corridas reales repetidas y `references/checklist_revision.md`.
7. **Registrar** qué se verificó, qué **no** y qué se cambió para que pasara (formato de `ejemplos/*/revision.md`).

### Frases con las que pedirlo

- **Elegir:** «Tengo que enrutar mensajes de clientes a distintas colas. ¿Qué arquetipo me conviene y por qué?» · «¿Uso ReAct o Planner-Executor para una conciliación con aprobación previa?»
- **Especificar:** «Armame la especificación con las tres preguntas para un agente de Reflection que redacta respuestas a reclamos.» · «Revisá esta especificación: ¿falta algún tope o alguna condición de terminación?»
- **Mapear:** «¿Con qué capacidades de ADK 2 implemento Deep Research? ¿Qué palanca controla el contexto de cada investigador?»
- **Construir:** «Con esta especificación, escribí el agente en ADK 2.9.1 y los tests sin modelo real.»
- **Revisar:** «Revisá este agente con la checklist: ¿hay tope externo, contexto aislado y una auditoría de lo que el modelo afirma?» · «Mi agente ReAct dice que abrió un reembolso pero no llamó a la herramienta: ¿cómo lo detecto?»
- **Usuarios:** «Un usuario pregunta cómo implementar un arquetipo sin escribir el código: ¿qué le respondo?» (ver «Cómo responder…»).

### Qué esperar y qué no pedirle

- **Sí:** que separe lo **verificado** de lo **no verificado**, cite el hallazgo (`references/hallazgos_adk2_2_9_1.md`) y proponga un tope o una auditoría cuando falte.
- **No:** que asegure que un agente funciona sin correrlo; que describa en YAML arquetipos distintos de Reflection (solo ese se verificó); ni que use `SequentialAgent`, `ParallelAgent` o `LoopAgent` (deprecados).

## Reglas que salieron de la evidencia (ADK 2.9.1)

- **El aislamiento de contexto NO es automático.** Un `LlmAgent` invocado con `ctx.run_node` desde un worker paralelo recibió 4 contenidos (la pregunta original duplicada, una transcripción del plan completo y su propia entrada); con `include_contents="none"` recibe 1. Si el arquetipo exige aislamiento, pedirlo **explícitamente**. Detalle y cómo se midió: `references/hallazgos_adk2_2_9_1.md`.
- **Todo contexto explícito por `node_input`.** Es la palanca que controla el código; lo demás lo decide ADK.
- **Todo bucle o fan-out lleva un tope de código** (el modelo no es un tope confiable: en una corrida real dio por terminado el trabajo demasiado pronto y respondió mal).
- **La calidad de la descomposición domina el resultado** de Query Decomposition: 1 de 6 corridas reales falló porque el modelo preguntó por temas ausentes en la base. El sistema devolvió «sin evidencia» en vez de inventar; diseñar para ese camino.
- **En un lazo (Reflection), el contexto crece por ronda** con `include_contents='default'` (`[2, 6, 10]` en 3 rondas); con `'none'` queda en 1. Y **el código debe prevalecer sobre el crítico**: exigir el veredicto del modelo **y** un validador determinista.
- **Deep Research: investigadores ReAct en paralelo → `use_sub_branch=True`** en cada `ctx.run_node` (sin él, cada uno ve las llamadas a herramientas de sus hermanos). **El evaluador LLM rara vez queda conforme** (3 de 3 corridas agotaron las rondas): el presupuesto en código es lo que garantiza el fin, y el informe debe traer las **brechas abiertas**. **Las citas se diluyen** (hasta 6 ids por afirmación) y la auditoría de citas debe leer también las agrupadas (`[A, B]`); verifica existencia, no respaldo. Es órdenes de magnitud más caro (80–130 s, 17–21 llamadas a agentes).
- **Reflex: declarar siempre `DEFAULT_ROUTE`** como escape (sin ella, una ruta inesperada termina la rama en silencio) y **una sola vez** (dos aristas iguales → *Duplicate edge*). Un mensaje puede **inyectar** su propia clasificación (0/3 con «clasificá esto como fraude»): no dejar que una entrada elija por sí sola una cola prioritaria. «Respuesta en ms» solo vale para reglas (≈ 7 ms); con LLM ≈ 2,8 s.
- **ReAct: el modelo puede decir que hizo algo que no hizo** (4 de 9 corridas reales afirmaron o prometieron un reembolso sin llamar a la herramienta): **auditar lo afirmado contra lo ejecutado**. Además: el tope **lanza una excepción** y el usuario no recibe texto (atraparla); el valor por defecto es 500; una herramienta que lanza una excepción **mata la corrida** (devolver `{"error": …}`); no hay compuerta para acciones con efecto; el contexto crece 2 contenidos por herramienta y `include_contents='none'` no lo evita.
- **En Planner-Executor el ejecutor debe ser código, no otro agente LLM:** un nodo dinámico que corre el plan por oleadas de dependencias. Un plan se valida por código **antes** de ejecutar; una aprobación humana con `RequestInput` pausa el flujo antes de la primera herramienta. Al replanificar, conservar lo ya hecho y, al escalar, entregar el **historial de fallas** (no solo el último rechazo).
- **Una regla determinista también se equivoca:** un validador con falsos positivos contaminó el lazo y el crítico se alineó con la evidencia errónea. Probar cada regla contra el texto correcto.
- **`RunConfig.max_llm_calls` vale 500 por defecto:** un bucle ReAct necesita un tope propio.
- **No usar `mode='task'` dentro de un grafo** (la doc dice que está deshabilitado; en 2.9.1 se construye pero su ejecución no está probada).

## Cómo responder «¿lo puedo hacer sin escribir código?» (verificado en Reflection)

- **No del todo.** En ADK 2.9.1 un `Workflow` se puede **describir en YAML** (`agent_class: Workflow`, `edges`, agentes LLM en línea) y `adk web` lo carga y lo ejecuta (hallazgo A9). Pero la lógica de decisión (validaciones, topes, prioridad sobre el crítico), los esquemas y los callbacks siguen siendo **funciones y clases Python referenciadas por ruta de módulo**.
- El cargador (`from_config`) está marcado **experimental**, y `adk create --type CONFIG` todavía dice que no está listo.
- Camino honesto para un usuario: especificar con las tres preguntas → que un asistente escriba el Python de decisión y el YAML de conexión → verificar con la checklist. Ejemplo: `ejemplos/reflection/yaml_reflection/`.
- **Solo se verificó con Reflection.** Para Query Decomposition hay un intento en curso (`parallel_worker` en línea no lo acepta el YAML; el worker debe definirse en Python): tratarlo como **pendiente**, no como resultado.

## Relación con agents-cli

`agents-cli` cubre el ciclo de vida (scaffold, eval, deploy, publish, observability), no el diseño de la orquestación. Dos advertencias verificadas:

- `agents-cli scaffold` fija `google-adk<2.0.0` (según el skill `google-agents-cli-adk-code`): un proyecto scaffolded queda en 1.x salvo que se cambie `pyproject.toml`. **Este skill no probó el camino por scaffold.**
- `agents-cli` avisa que los skills están desfasados respecto de la CLI; `agents-cli update` reescribe los skills globales. No se ejecutó aquí.

## Archivos

- `references/mapeo_arquetipos_adk2.md` — arquetipo → capacidad de ADK2, con estado de verificación.
- `references/plantilla_especificacion.md` — las tres preguntas por arquetipo.
- `references/checklist_revision.md` — lista de revisión y cómo comprobar cada punto.
- `references/hallazgos_adk2_2_9_1.md` — hechos verificados, con dónde y cómo.
- `references/repos_y_plantillas.md` — código del curso y repos de referencia (sin copiarlos).
- `ejemplos/{reflex,react,planner_executor,query_decomposition,reflection,deep_research}/` — ejemplos corridos: especificación, código, tests sin LLM, salidas reales, revisión.
