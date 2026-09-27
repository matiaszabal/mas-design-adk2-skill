# Especificación — Query Decomposition (atención al cliente de un banco ficticio)

Este es el documento que escribe **el usuario** antes de pedirle a un asistente de código que construya el agente. Está armado con las tres preguntas de orquestación. Es la instancia completa de la plantilla que trae el skill.

## 1. Objetivo y alcance

- **Problema:** un cliente hace preguntas de comisiones que se responden combinando varios documentos (tarifa base, beneficio del plan, costo de conversión de moneda).
- **Arquetipo elegido:** Query Decomposition, porque la pregunta es multi-salto y cada parte se responde con **un** documento.
- **Por qué no otro:** una sola pasada (Reflex) no alcanza; el camino no es exploratorio (ReAct); no hay acciones con efectos ni aprobación previa (Planner-Executor).
- **Datos:** base de conocimiento **sintética** (`kb.py`). No hay datos reales de clientes.

## 2. Las tres decisiones

### ¿Quién decide qué se ejecuta después?

- **Variante paralela** (sub-preguntas independientes): el LLM decide **una vez** cómo partir la pregunta. Después el código recupera fragmentos, reparte las sub-preguntas en paralelo y junta las respuestas.
- **Variante secuencial** (una sub-pregunta depende de la respuesta anterior): el LLM decide, tras cada respuesta, si falta otro dato y cuál sería la sub-pregunta siguiente. El código ejecuta cada paso.
- **Lo que decide el código:** la recuperación, el reparto en paralelo, los topes y la síntesis final.

### ¿Con qué contexto?

- Cada agente ve **solo** su `node_input`. El aislamiento **no es automático** en ADK 2.9.1: se pide con `include_contents="none"`.
- **Respondedor:** la sub-pregunta + los fragmentos recuperados. No ve la pregunta original ni las otras sub-preguntas.
- **Sintetizador:** la pregunta original + las respuestas parciales con su fuente. No ve los documentos.
- **Secuencial:** el agente `siguiente` recibe la pregunta y los **hechos ya establecidos** dentro de su `node_input`.

### ¿Cuándo se detiene?

- **Topes de código:** `MAX_SUBPREGUNTAS = 4` (recorta el plan), `MAX_PARALELO = 4` (concurrencia), `MAX_PASOS = 4` (la secuencial corta aunque el modelo siga pidiendo).
- **Cierre normal:** todas las sub-preguntas tienen respuesta, o el modelo indica `terminar=true`.
- **Degradación:** una sub-pregunta sin evidencia devuelve `"sin evidencia"`; el sintetizador debe decirlo en vez de inventar.

## 3. Criterios de aceptación

1. Para la pregunta de la variante paralela, la respuesta final contiene **19,5 USD** (7,5 de comisión con bonificación + 12 de conversión).
2. Para la de la secuencial, contiene **7,5 USD**.
3. Ningún respondedor recibe más de un contenido.
4. Con un modelo que propone 9 sub-preguntas, se resuelven como máximo 4.
5. Con un modelo que nunca dice «terminar», la secuencial corta en `MAX_PASOS`.

## 4. Restricciones

- Sin datos reales. Sin despliegue. Solo invocación de modelo.
- No usar `mode='task'` dentro del grafo.
- Los fragmentos y las fuentes se citan en la respuesta final.
