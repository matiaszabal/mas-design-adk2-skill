# Repos y plantillas de referencia

**No se copia código de estos repos al skill:** se desactualizan y no se sabe qué versión de ADK usan. Se listan como punteros. Fecha de consulta: 2026-09-26.

## Código del curso (fuera de este repositorio)

Son archivos de un curso de arquitectura de agentes (Módulo 5) que **no están incluidos en este repositorio**; se listan solo como punteros. **Ninguno fue re-ejecutado en este trabajo.**

- `ejemplos_slides_adk2/planner_executor_workflow.py` — Planner-Executor como Workflow (validación con rutas).
- `ejemplos_slides_adk2/loop_workflow.py` — lazo generador → crítico → decidir (Reflection), con tope en el estado y ruta `escalar`.
- `ejemplos_slides_adk2/parallel_join_workflow.py` — fan-out + `JoinNode`.
- `codelab_adk2_orquestacion/adk2-tutorial/` (`L2b_router`, `L3a_collaborative`, `L4a_flat_research`, `L4b_recursion`) — patrones de router, colaboración y research dinámico. **Pinneado a ADK 2.3.0**; L3a y L4b tienen ajustes propios del curso (ver `adk2_orch_tecnico_experimentos/README.md` del curso).
- `adk2_orch_tecnico_experimentos/` — 10 scripts sin LLM con salidas guardadas sobre rutas, estado, paralelismo, dinámico, human input y versiones 2.3.0 vs 2.9.1.
- `L4a_flat_research` ya implementa la forma decomponer → investigar en paralelo → sintetizar, **pasando la pregunta original a cada worker** en su `node_input`. El ejemplo de este skill, en cambio, no se la pasa (`include_contents='none'`), porque el arquetipo Query Decomposition exige aislamiento.

## GitHub

- **`google/adk-recipes`** (antes `google/adk-samples`; la API resuelve el nombre viejo al nuevo). Agentes de Python en `python/agents/`. Solo se leyeron los README; **no se leyó el código ni se verificó la versión de ADK que usan**.
  - `deep-search` — Deep Research: plan aprobado por el usuario, búsqueda en bucle, reflexión sobre brechas, síntesis. Adaptado de un quickstart de LangGraph.
  - `llm-auditor` — crítico + revisor (Reflection parcial): extrae afirmaciones, verifica con búsqueda, reescribe. No se verificó si itera.
  - `sdlc-task-planner` — Planner (sin fase de ejecución), dentro de un flujo SDLC.
  - `high-volume-document-analyzer` — procesamiento por lotes con estado y corte anticipado.
  - `skills/` del repo: solo `retail`; no hay skills de orquestación.
- No se encontraron ejemplos de **Reflex** ni de **Query Decomposition**. Para **ReAct** solo un demo de juguete (`doug7410/adk-react-agent-demo`, sin estrellas).
- Repos pequeños mencionados (contenido **no revisado**): `JNK234/Google-ADK-Agentic-Patterns`, `d3xvn/adk-samples`, `AnkitBajpaii/google-adk-practice`.

## Skills de agents-cli (instalados en `~/.agents/skills/`)

- `google-agents-cli-adk-code` — referencia de código; `references/adk-2.0.md` describe el Workflow (lo marca «experimental, pre-GA»; **no coincide con el uso del curso en 2.9.1**, ver `hallazgos_adk2_2_9_1.md`).
- `google-agents-cli-scaffold`, `-eval`, `-deploy`, `-publish`, `-observability`, `-workflow` — ciclo de vida del proyecto.
- Los skills están desfasados respecto de la CLI (1.5.0 instalada; la CLI avisa una 1.7.0).
