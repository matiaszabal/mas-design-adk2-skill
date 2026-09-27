# Especificación — Deep Research (debida diligencia de un proveedor ficticio)

Instancia de `../../references/plantilla_especificacion.md`.

## 1. Objetivo y alcance

- **Problema:** producir un informe de debida diligencia de «Logística Andina S.A.» (Argentina) y su filial «Logística Andina Chile SpA»: identidad societaria, litigios, reputación, situación financiera y riesgos regulatorios, **citando fuentes** y declarando **lo que no se pudo cubrir**.
- **Arquetipo:** Deep Research: pregunta abierta, sin límites claros, cuyo resultado lo lee una persona y cuyo valor justifica varias llamadas al modelo.
- **Por qué no uno más simple:** Query Decomposition alcanza si las sub-preguntas se conocen de antemano; aquí lo que falta **se descubre** al mirar lo reunido (por ejemplo, qué entidad quedó sin cubrir).
- **Datos:** una «web» sintética de 12 documentos (10 útiles, 1 sobre un **homónimo** distinto —«Logística Andes Ltda.»— y 1 irrelevante) y un proveedor ficticio. Ningún dato real.

## 2. Las tres decisiones

### ¿Quién decide qué sigue?

- **Un LLM decide QUÉ investigar** (planificador: hasta 5 consultas por ronda) **y CUÁNDO hay suficiente** (evaluador de brechas). El número de rondas no se conoce de antemano.
- **El código** reparte el trabajo en paralelo, agrega las notas, aplica el presupuesto y compone la salida final.
- **Cada investigador es un ReAct:** un `LlmAgent` con una herramienta de búsqueda que puede llamar varias veces y que devuelve un hallazgo estructurado.

### ¿Con qué contexto?

- **Investigadores aislados** (`include_contents="none"` + `use_sub_branch=True`): ven **solo su consulta** y su propia búsqueda; no ven la pregunta original, ni las consultas ni las búsquedas de sus hermanos.
- **Bloc de notas compacto** (código): un dict tema → resumen corto + fuentes. Es lo que ven el planificador y el evaluador; no ven material crudo.
- **El redactor** escribe **solo desde las notas** (no ve las fuentes crudas ni la conversación).

### ¿Cuándo se detiene?

- **Cobertura suficiente** según el evaluador, **o presupuesto agotado:** `MAX_RONDAS = 3` o `MAX_LLAMADAS_AGENTE = 24`. La segunda condición es la que garantiza el fin.
- **Al cortar por presupuesto** se entrega lo logrado **y** las **brechas abiertas**, sin aparentar cobertura completa.

## 3. Criterios de aceptación

1. Con cobertura suficiente en la ronda 1: un informe desde las notas, sin brechas.
2. Si el evaluador detecta una brecha: la ronda siguiente investiga **solo eso** (no repite lo cubierto).
3. Un evaluador que nunca queda conforme: corta en `MAX_RONDAS` y **entrega el informe con las brechas abiertas**.
4. El presupuesto de llamadas corta antes que las rondas cuando corresponde.
5. Nunca más de `MAX_INVESTIGADORES` investigadores por ronda; corren en paralelo.
6. Cada investigador ve solo lo suyo, **incluso con herramientas y en paralelo**.
7. Un investigador que falla no tira a los demás: queda registrado como «sin evidencia».
8. **Auditoría de citas (código):** toda cita `[ID]` del informe existe en las fuentes y fue reunida por algún investigador.
9. Con Gemini real: el informe cita fuentes de los cinco temas y de **ambas** entidades, y **no atribuye al proveedor** la fuente del homónimo.

## 4. Restricciones

- Sin datos reales. Solo `Workflow` (nodo dinámico con `ctx.run_node`); sin agentes deprecados.
- La auditoría de citas verifica que la cita **exista** y haya sido **reunida**; **no** verifica que respalde la afirmación (eso requiere revisión humana o un verificador semántico).
