# Especificación — ReAct (soporte de un banco ficticio: reclamo de cobro duplicado)

Instancia de `../../references/plantilla_especificacion.md`.

## 1. Objetivo y alcance

- **Problema:** un cliente dice que le cobraron dos veces la cuota de su préstamo. El agente debe verificarlo con los datos y, solo si es cierto, abrir una solicitud de reembolso.
- **Arquetipo:** ReAct: el camino no se conoce de antemano (cada paso depende del resultado del anterior) y hay pocas herramientas.
- **Por qué no uno más simple / más estructurado:** una pasada no puede consultar datos; no se pide aprobación previa del plan (eso sería Planner-Executor).
- **Datos:** sintéticos (`react.py`).

## 2. Las tres decisiones

- **¿Quién decide qué sigue?** El **modelo**, en cada vuelta: qué herramienta llamar o si responder. El código ejecuta lo pedido e impone límites.
- **¿Con qué contexto?** Una ventana única que **crece** (llamada + respuesta de cada herramienta). Las herramientas deben devolver resultados **acotados**.
- **¿Cuándo se detiene?** El modelo responde sin pedir herramientas, o se agota el **tope externo** `RunConfig(max_llm_calls=N)` (por defecto 500: hay que fijarlo). El llamador debe **atrapar** `LlmCallsLimitExceededError`.

## 3. Criterios de aceptación

1. Con el duplicado real (C-001): se abre **un** reembolso y el cliente recibe una respuesta coherente.
2. Con un duplicado inexistente (C-002): **no** se abre ningún reembolso.
3. Toda afirmación o promesa del modelo sobre acciones tiene respaldo en las herramientas ejecutadas (**auditoría**).
4. Una herramienta que falla no mata la corrida: devuelve `{"error": …}`.
5. Hay un tope propio de llamadas y el llamador responde algo útil si se agota.

## 4. Restricciones

- Sin datos reales. Solo `LlmAgent` con herramientas; sin agentes deprecados.
- La acción con efecto (`solicitar_reembolso`) **no tiene compuerta** en este arquetipo: si hace falta aprobación previa, corresponde Planner-Executor.
