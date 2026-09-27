# Revisión del ejemplo Deep Research contra la lista de verificación

Estado: **OK** · **PARCIAL** · **N/A** · **NO VERIFICADO**. Lista: `../../references/checklist_revision.md`.

## Terminación

1. **Tope de código:** OK. `MAX_RONDAS = 3`, `MAX_LLAMADAS_AGENTE = 24` y `MAX_INVESTIGADORES = 5` (D3, D4). Con un evaluador que nunca queda conforme corta en la ronda 3; el presupuesto de llamadas corta antes cuando corresponde.
2. **El tope no depende del modelo:** OK. **Y fue necesario:** en las **3 corridas reales el evaluador nunca quedó conforme** y las tres agotaron las 3 rondas.
3. **Al cortar se informa:** OK. La salida lleva `motivo_fin` y `brechas_abiertas`, y el informe termina con «Brechas abiertas».

## Contexto

4. **Cada agente ve solo lo que debe:** OK. Planificador, evaluador y redactor: 1 contenido en todas las llamadas (falso y Gemini real). Investigadores (ReAct en paralelo): crecen **de a 2 por búsqueda** (1, 3, 5, 7…, hasta 17 con 8 búsquedas), sin saltos ajenos. **Requiere `use_sub_branch=True`:** sin él, cada investigador vio las llamadas a herramientas de sus hermanos (5 contenidos en vez de 3; con 5 investigadores, 7) — `explorar_fuga_paralelos.py`.
5. **Lo que persiste va al estado:** OK (`notas`, `brechas_abiertas`, `rondas`, `motivo_fin`, `llamadas_agente`).
6. **Artefactos inspeccionables:** OK. `TRAZA_RONDAS` muestra por ronda las consultas, los hallazgos y las brechas.

## Orquestación

7. **Fan-out en paralelo:** OK. 5 investigadores ReAct de 2 llamadas de 0,3 s → 0,64 s (serial ≥ 3,0 s) (D5). 8-11. **OK.** Nodo dinámico con `ctx.run_node` y `rerun_on_resume=True`; sin agentes deprecados. `Agent(tools=…, output_schema=…)` funciona: ADK agrega una herramienta interna `set_model_response`.
- **Un investigador que falla no tira a los demás:** OK (D7): se captura dentro del investigador y queda «sin evidencia». Sin ese `try/except`, un fallo cancelaría a los hermanos (E6 de los experimentos del módulo).

## Calidad y honestidad

12. **Camino sin evidencia:** OK. En la ronda 1 un investigador con una consulta larga recuperó fuentes equivocadas y devolvió «SIN EVIDENCIA»; las rondas siguientes lo corrigieron.
13. **Corridas reales repetidas:** OK, **3 corridas** con Gemini: **82,5 s, 118,5 s y 130,6 s**; 17–21 llamadas a agentes; **31–51 búsquedas**; **3 rondas las tres** (`presupuesto (rondas)`). Adaptativo: la ronda 2 usó 4 investigadores y la 3, 2. Cobertura de fuentes esperadas **10/10, 10/10, 9/10**; **0 citas inexistentes o no reunidas**; el **homónimo** (`DX-01`, otra empresa) **no se citó nunca**. n=3.
14. **Fallos registrados:** OK.
    - **Mi auditoría de citas era ciega** a las citas agrupadas (`[LI-01, RG-01]`): informó «0/10» e «inválidas: []» sin haber visto ninguna cita. Se corrigió (`dr.citas_de`) y se **reevaluó sobre las salidas guardadas** (`auditar_salidas.py`) sin volver a llamar al modelo. Las cifras de arriba son las corregidas.
    - **Citas diluidas:** el redactor atribuye a cada afirmación **todas** las fuentes del tema («constituida en 2011 [LI-01, RG-01, LI-02, RG-02, ID-01, ID-02]»): hasta 6 ids por grupo (media 3,0 / 1,3 / 2,4). La auditoría verifica que la cita **exista y se haya reunido**, **no** que respalde la afirmación.
    - **Evaluador que no converge:** exigió datos que la «web» no contiene (estructura accionaria, directorio, estados financieros de tres años) y quedó en `cobertura_suficiente=false` siempre, aun con la instrucción de no pedir búsquedas agotadas. **Sin mitigación.**
15. **Datos:** OK, sintéticos.

## Costo

El arquetipo es órdenes de magnitud más caro que los demás ejemplos: **80–130 s y 17–21 llamadas a agentes** para 12 documentos, frente a ~10–20 s de Query Decomposition o ~8 s de Reflection.

## Pendiente en este ejemplo

- Mitigar el evaluador que no converge (p. ej. compararlo contra lo **disponible** y no contra un ideal, o exigir que cada brecha se acompañe de una consulta que aún no se probó).
- **Citas por afirmación** (salida estructurada con una fuente por hecho) para poder verificar respaldo, no solo existencia.
- Probar con un corpus más grande y un buscador real; mi búsqueda es léxica y de juguete.
- Describirlo en YAML (pendiente general).
