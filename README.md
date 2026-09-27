# mas-design-adk2-skill

**MVP** de un skill que conecta los 6 arquetipos de agentes con las capacidades de ADK 2 (Workflow en grafo, workflows dinámicos, colaboración). Módulo 5 · 2026-09-26 · ADK 2.9.1.

## Qué hay

> **Sobre las corridas reales.** Las cifras de este repositorio (p. ej. «4 de 9 corridas») provienen de una tanda de corridas con Gemini del 2026-09-26. **Sus salidas originales no se publican** (`salidas/salida_real*` y similares están en `.gitignore`), y el modelo no es determinista: al repetir `correr_real.py` los números pueden variar. Las salidas de los tests con modelo falso **sí** están incluidas y se reproducen sin costo. Los documentos que citan archivos de `salidas/` de corridas reales los citan como evidencia original, no reproducible desde este repositorio.


- `RESUMEN_HALLAZGOS.md` — **empezar por acá**: una página con los hallazgos que más importan, lo no verificado y un orden de lectura.
- `SKILL.md` — el skill (flujo, **cómo usarlo con un recorrido y frases de ejemplo**, reglas que salieron de la evidencia, límites).
- `references/` — mapeo arquetipo → ADK2 (con estado de verificación), plantilla de especificación, lista de revisión, hallazgos verificados, repos y plantillas.
- `ejemplos/{reflex,react,planner_executor,query_decomposition,reflection,deep_research}/` — ejemplos completos y corridos: especificación, código, tests sin LLM, corridas reales con Gemini, revisión. (`modelo_falso.py` y `traza.py` están copiados en ambos.)

## Licencia

MIT (ver `LICENSE`). Los datos de los ejemplos son sintéticos: no corresponden a personas ni instituciones reales.

## Estado por arquetipo

- **Verificados (ADK 2.9.1), los seis:** Reflex (ruta de escape), ReAct (bucle, tope y herramientas), Planner-Executor (ejecutor dinámico por oleadas, aprobación humana con `RequestInput` y replanificación), Query Decomposition (variantes paralela y secuencial), Reflection (ciclo por rutas, en Python **y descrito en YAML**) y Deep Research (director dinámico con investigadores ReAct en paralelo).
- **Hipótesis:** Reflex, ReAct.

## Cómo correr el ejemplo

```bash
cd ejemplos/query_decomposition
python3 test_sin_llm.py          # 17 chequeos, sin red ni costo (en ejemplos/reflection/: 16)
python3 explorar_palancas.py     # qué palancas cambian el contexto de un agente
# en ejemplos/planner_executor/: python3 test_sin_llm.py   # 32 chequeos, incluida la pausa/reanudación
# en ejemplos/reflex/ (15 chequeos), ejemplos/react/ (20) y ejemplos/deep_research/ (26): python3 test_sin_llm.py
python3 test_grafo.py            # la variante paralela como grafo puro (parallel_worker en el LlmAgent)
# en ejemplos/reflection/: python3 test_yaml.py   # el Workflow descrito en YAML vs el de Python
# con Gemini real (solo invocación de modelo; datos sintéticos):
export GOOGLE_GENAI_USE_VERTEXAI=TRUE GOOGLE_CLOUD_PROJECT=<proyecto> GOOGLE_CLOUD_LOCATION=us-central1
python3 correr_real.py paralela none      # o: secuencial none | paralela default
adk web .                                 # lista qd_paralela y qd_secuencial
```

## Instalación como skill (no se hizo)

Este repositorio **no instala** el skill en `~/.claude/skills/`. Para usarlo: copiar esta carpeta (o un enlace simbólico) a `~/.claude/skills/mas-design-adk2/`.

## Pendiente

- **Mitigaciones no aplicadas** (los fallos quedaron visibles): inyección en Reflex; acción alucinada y manejo del tope en ReAct; evaluador que no converge y citas diluidas en Deep Research.
- **Muestras chicas** (n=3 por escenario) y datos sintéticos: repetir con más corridas y datos reales aprobados antes de sacar conclusiones de calidad.
- Probar el **camino por `agents-cli scaffold`** (fija `google-adk<2.0.0`) y `agents-cli eval`; no se tocaron los skills globales.
- **YAML de Query Decomposition (próxima iteración):** ya hay un primer intento en `ejemplos/query_decomposition/yaml_qd_grafo/` (carga si el worker paralelo se define en Python; 12 chequeos; 2/3 con Gemini); falta cerrar `adk web`, decidir cuánto del YAML aporta y probar la variante secuencial. Con Deep Research (`ctx.run_node`) no se intentó. Con Reflection ya funciona (hallazgo A9). `LoopAgent`, `SequentialAgent` y `ParallelAgent` están **deprecados** en favor de `Workflow` (lo dice el código de 2.9.1) y este skill no los usa.
- Clonar `deep-search` y `llm-auditor` de `google/adk-recipes`, ver qué versión de ADK usan y si corren en 2.9.1.
- Hoja de una página para el usuario (especificación + lista de revisión).
- Pendientes del ejemplo: ver `ejemplos/query_decomposition/revision.md`.
