"""Reflex sobre ADK 2.9.1 — UNA pasada de percepción a acción, sin bucle ni estado intermedio.

    START → iniciar → clasificador (1 llamada al LLM) → enrutar ─┬ "tarjetas"  → cola_tarjetas
                                                                 ├ "prestamos" → cola_prestamos
                                                                 ├ "fraude"    → cola_fraude
                                                                 └ DEFAULT     → derivar_a_humano   (ruta de escape)

Variante SIN LLM: `construir_reglas()` reemplaza el clasificador por reglas (código); mismas rutas y mismo escape.

Las tres decisiones de orquestación, tal como quedan en este código:

  ¿Quién decide qué sigue?  Nadie decide en ejecución: el flujo está resuelto en el diseño (un solo paso). La
                            «decisión» es una regla (código) o una única inferencia del modelo; nunca un bucle.
  ¿Con qué contexto?        Solo la percepción actual (el mensaje). include_contents="none": el modelo no ve nada más.
  ¿Cuándo se detiene?       Al llegar a una cola. No hay condición de corte porque no hay iteración. El riesgo se
                            traslada a la entrada: lo que no encaja (baja confianza, «otro», ruta inesperada) va al
                            ESCAPE. Sin ruta por defecto, una ruta inesperada termina la rama EN SILENCIO.

Los datos son SINTÉTICOS (banco ficticio).
"""
import os
import re
import unicodedata
from typing import Literal

from google.adk import Agent, Event, Workflow
from google.adk.workflow import DEFAULT_ROUTE, START, node
from pydantic import BaseModel

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")


class Clasificacion(BaseModel):
    intencion: Literal["tarjetas", "prestamos", "fraude", "otro"]
    confianza: Literal["alta", "media", "baja"]


LOG_CONTEXTO: list[dict] = []


def log_contexto(callback_context, llm_request):
    contents = llm_request.contents or []
    LOG_CONTEXTO.append({"agente": callback_context.agent_name, "n_contents": len(contents), "roles": [c.role for c in contents]})
    return None


def texto_de(x) -> str:
    if isinstance(x, str):
        return x
    if hasattr(x, "parts") and x.parts:
        return "".join(getattr(p, "text", "") or "" for p in x.parts)
    return str(x)


def clasificacion_de(x) -> Clasificacion:
    if isinstance(x, Clasificacion):
        return x
    if isinstance(x, dict):
        return Clasificacion.model_validate(x)
    return Clasificacion.model_validate_json(texto_de(x).strip().removeprefix("```json").removeprefix("```").removesuffix("```"))


def crear_clasificador(modelo=None, include_contents: str = "none"):
    return Agent(
        name="clasificador", model=modelo or MODEL, output_schema=Clasificacion, include_contents=include_contents,
        before_model_callback=log_contexto,
        instruction=(
            "Clasificá el mensaje de un cliente de un banco en UNA intención: 'tarjetas' (bloqueos, límites, "
            "extravío de tarjeta), 'prestamos' (cuotas, tasas, cancelación de préstamos), 'fraude' (movimientos "
            "no reconocidos, clonación, estafa) u 'otro' (cualquier otra cosa, o si el mensaje mezcla varias "
            "intenciones). En 'confianza' poné 'alta' solo si es inequívoco; 'media' o 'baja' si hay duda."))


# ------------------------------------------------------------------------ nodos
@node
def iniciar(ctx, node_input):
    m = texto_de(node_input)
    yield Event(output=m, state={"mensaje": m})


@node
def enrutar(ctx, node_input):
    c = clasificacion_de(node_input)
    ruta = c.intencion if (c.confianza == "alta" and c.intencion != "otro") else "derivar"
    yield Event(output={"intencion": c.intencion, "confianza": c.confianza}, route=ruta,
                state={"intencion": c.intencion, "confianza": c.confianza})


def _cola(nombre, prioridad):
    @node(name=f"cola_{nombre}")
    def destino(ctx, node_input):
        yield Event(output={"cola": nombre, "prioridad": prioridad, "mensaje": ctx.state["mensaje"]})
    return destino


cola_tarjetas, cola_prestamos, cola_fraude = _cola("tarjetas", "normal"), _cola("prestamos", "normal"), _cola("fraude", "alta")


@node
def derivar_a_humano(ctx, node_input):
    yield Event(output={"cola": "humano", "prioridad": "normal", "mensaje": ctx.state["mensaje"],
                        "motivo": f"no clasificable con seguridad ({ctx.state.get('intencion', 'sin clasificar')}, "
                                  f"confianza {ctx.state.get('confianza', '-')})"})


def _destinos():
    # El escape se declara UNA sola vez, con DEFAULT_ROUTE: ADK rechaza dos aristas iguales (mismo origen y destino)
    # aunque tengan rutas distintas. `enrutar` emite «derivar» y, como no está mapeada, cae en el DEFAULT.
    return {"tarjetas": cola_tarjetas, "prestamos": cola_prestamos, "fraude": cola_fraude, DEFAULT_ROUTE: derivar_a_humano}


def construir(clasificador) -> Workflow:
    return Workflow(name="reflex", edges=[(START, iniciar, clasificador, enrutar), (enrutar, _destinos())])


# ---------------------------------------------------- variante sin LLM (reglas)
REGLAS = [("fraude", r"clonaron|no reconozco|estafa|fraude|movimiento sospechoso|no fui yo"),
          ("tarjetas", r"tarjeta|limite de credito|bloque"),
          ("prestamos", r"prestamo|cuota|tasa de interes|cancelar el credito")]


def _norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


@node
def clasificar_reglas(ctx, node_input):
    m = _norm(texto_de(node_input))
    hallados = [i for i, rx in REGLAS if re.search(rx, m)]
    if "fraude" in hallados:                                  # PRECEDENCIA: ante la duda, el fraude gana («clonaron la tarjeta»
        hallados = ["fraude"]                                 # coincide con dos reglas; sin precedencia se iba a un humano)
    if len(hallados) == 1:                                    # una sola intención: inequívoco
        yield Event(output={"intencion": hallados[0], "confianza": "alta"}, route=hallados[0], state={"intencion": hallados[0], "confianza": "alta"})
    else:                                                     # ninguna o varias: la regla NO decide → escape
        yield Event(output={"intencion": "otro", "confianza": "baja"}, route="derivar", state={"intencion": "otro", "confianza": "baja"})


def construir_reglas() -> Workflow:
    return Workflow(name="reflex_reglas", edges=[(START, iniciar, clasificar_reglas), (clasificar_reglas, _destinos())])
