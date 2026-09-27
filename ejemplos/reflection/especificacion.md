# Especificación — Reflection (respuesta a un reclamo en un banco ficticio)

Documento que escribe el usuario antes de pedirle a un asistente de código que construya el agente. Instancia de `../../references/plantilla_especificacion.md`.

## 1. Objetivo y alcance

- **Problema:** redactar la respuesta a un reclamo de cobro duplicado sin prometer lo que la política no permite. El cliente presiona («hoy mismo y garantizado»).
- **Arquetipo elegido:** Reflection, porque un error (una promesa indebida) es costoso y existe un criterio verificable (reglas de la política) además de uno semántico (tono, empatía).
- **Por qué no uno más simple:** una sola pasada (Reflex/ReAct) no verifica; no hay pasos que planificar.
- **Datos:** sintéticos (`refl.py`): un caso, una política, un pedido.

## 2. Las tres decisiones

### ¿Quién decide qué se ejecuta después?

- **El código fija el lazo:** generar → validar → criticar → decidir. Lo implementa un `Workflow` con un ciclo por rutas (`revisar` vuelve al generador).
- **El LLM** redacta/corrige (generador) y da un veredicto (crítico).
- **`decidir` (código)** exige que el crítico apruebe **y** el validador determinista no marque fallas. Si el crítico aprueba algo que el validador rechaza, gana el validador.

### ¿Con qué contexto?

- Generador y crítico corren con `include_contents="none"`: ven solo su `node_input` y las variables de estado de su instrucción.
- **Generador:** el pedido, el caso y la política (estado) y, desde la ronda 2, el feedback de la ronda anterior.
- **Crítico:** el caso, el borrador y la evidencia del validador. **No** ve la instrucción del generador.
- **Entre rondas viaja el feedback** (estado), no el historial de borradores.

### ¿Cuándo se detiene?

- `aprobado`: el crítico aprueba y el validador no marca fallas.
- **Tope:** `MAX_RONDAS = 3` (contador en el estado). Al agotarse, la ruta `escalar` entrega el último borrador **y** lo pendiente, para revisión humana.

## 3. Criterios de aceptación

1. Con un generador correcto y un crítico que aprueba: publica en la ronda 1.
2. Con un crítico que nunca aprueba: escala tras exactamente `MAX_RONDAS` rondas e informa lo pendiente.
3. Con un crítico complaciente (aprueba un borrador que promete de más): no publica hasta que el validador conforme.
4. El feedback de la ronda N llega al generador de la ronda N+1.
5. Generador y crítico reciben 1 contenido en todas las rondas.
6. El crítico no ve la instrucción del generador.
7. Con Gemini real: la respuesta final no contiene promesas prohibidas.

## 4. Restricciones

- Sin datos reales. Solo invocación de modelo. Sin `LoopAgent` ni otros agentes deprecados: solo `Workflow`.
- Una regla determinista puede tener falsos positivos: debe probarse contra el texto correcto (una **negación** de la promesa no es una promesa).
