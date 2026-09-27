"""Reflection sobre ADK 2.9.1 — un Workflow con un CICLO POR RUTAS (sin agentes deprecados).

    START → iniciar → generar → validar → criticar → decidir ─┬ "revisar"  → generar   (ciclo)
                                                              ├ "aprobado" → publicar
                                                              └ "escalar"  → escalar_a_humano

Las tres decisiones de orquestación, tal como quedan en este código:

  ¿Quién decide qué sigue?
    - El CÓDIGO fija el lazo (generar → validar → criticar → decidir). El LLM decide solo su parte:
      el generador redacta/corrige y el crítico da un veredicto. `decidir` (código) elige la ruta y
      NO obedece al crítico si el validador determinista dice que hay una falla.
  ¿Con qué contexto?
    - Generador y crítico corren con include_contents="none": ven solo su node_input y las variables
      de estado de su instrucción. Entre rondas viaja el FEEDBACK (estado), no el historial de borradores.
    - El crítico ve el borrador y la evidencia del validador, no la instrucción del generador.
  ¿Cuándo se detiene?
    - "aprobado" (crítico Y validador conformes), o MAX_RONDAS → "escalar" con lo pendiente.
      El tope es un contador en el estado, decidido por código.

Los datos son SINTÉTICOS (banco ficticio).
"""
import json
import os
import re
import unicodedata

from google.adk import Agent, Event, Workflow
from google.adk.workflow import START, node
from pydantic import BaseModel

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")
MAX_RONDAS = 3

CASO = {"cliente": "C-001", "monto_duplicado_usd": 120, "cobro_duplicado_verificado": False}
POLITICA = ("Si se verifica un cobro duplicado, el reembolso se acredita en 5 días hábiles luego de la "
            "verificación. No se puede prometer reembolso inmediato ni garantizar plazos distintos.")
PEDIDO = ("Reclamo del cliente C-001: «Me cobraron dos veces la cuota. Exijo que me devuelvan los 120 USD "
          "hoy mismo y que me lo garanticen.»")
PROHIBIDAS = ["reembolso inmediato", "hoy mismo", "de inmediato", "garantizamos", "garantizado", "garantia"]


class Veredicto(BaseModel):
    aprobado: bool
    critica: str


# ---------------------------------------------------------------- señal externa (código)
def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def validar_texto(borrador: str) -> dict:
    """Validador DETERMINISTA: la 'señal externa' del arquetipo. Devuelve {ok, fallas}.

    Una regla tiene falsos positivos: la primera versión marcaba «no es posible garantizar un reembolso
    inmediato» como promesa y contaminó el lazo (ver salidas/_previas_validador_ingenuo/)."""
    t = _norm(borrador)
    fallas = []
    if not re.search(r"\b120(?:[.,]00)?\b", t):
        fallas.append("no menciona el monto correcto (120 USD)")
    if not re.search(r"\b5 dias habiles\b", t):
        fallas.append("no cita el plazo de la política (5 días hábiles)")
    if "verific" not in t:
        fallas.append("no aclara que el reembolso está sujeto a verificación")
    for p in PROHIBIDAS:
        for m in re.finditer(re.escape(p), t):
            previo = t[max(0, m.start() - 40):m.start()]              # ventana de 40 caracteres antes
            if not re.search(r"\b(no|sin|ni|nunca|imposible)\b", previo):   # una negación NO es una promesa
                fallas.append(f"promete algo que la política no permite: «{p}»")
                break
    return {"ok": not fallas, "fallas": fallas}


# ----------------------------------------------------- evidencia de "con qué contexto"
LOG_CONTEXTO: list[dict] = []


def log_contexto(callback_context, llm_request):
    contents = llm_request.contents or []
    LOG_CONTEXTO.append({"agente": callback_context.agent_name, "n_contents": len(contents),
                         "roles": [c.role for c in contents]})
    return None


def texto_de(x) -> str:
    if isinstance(x, str):
        return x
    if hasattr(x, "parts") and x.parts:
        return "".join(getattr(p, "text", "") or "" for p in x.parts)
    if isinstance(x, BaseModel):
        return x.model_dump_json()
    return str(x)


def veredicto_de(x) -> Veredicto:
    if isinstance(x, Veredicto):
        return x
    if isinstance(x, dict):
        return Veredicto.model_validate(x)
    return Veredicto.model_validate_json(texto_de(x).strip().removeprefix("```json").removeprefix("```").removesuffix("```"))


# ------------------------------------------------------------------ agentes reales
def crear_agentes(include_contents: str = "none", modelos: dict | None = None):
    m = lambda nombre: (modelos or {}).get(nombre, MODEL)
    generador = Agent(
        name="generador", model=m("generador"), output_key="borrador", include_contents=include_contents,
        before_model_callback=log_contexto,
        instruction=(
            "Sos un agente de atención al cliente de un banco. Redactá una respuesta breve (máximo 90 palabras) "
            "al reclamo, usando SOLO estos datos.\nCASO: {caso}\nPOLÍTICA: {politica}\n"
            "Si hay observaciones previas, corregí el borrador según ellas: {feedback?}"))
    critico = Agent(
        name="critico", model=m("critico"), output_schema=Veredicto, include_contents=include_contents,
        before_model_callback=log_contexto,
        instruction=(
            "Sos un revisor de respuestas a reclamos. Recibís un JSON con el caso, el borrador y la evidencia de "
            "un validador automático. Evaluá con esta rúbrica: (1) los datos coinciden con el caso; (2) no promete "
            "nada que la política no permita; (3) cita el plazo de la política y aclara que está sujeto a "
            "verificación; (4) el tono es empático y profesional. aprobado=true solo si cumple las cuatro. "
            "Si no, 'critica' dice concretamente qué corregir."))
    return generador, critico


# ------------------------------------------------------------ nodos (a nivel de módulo)
# Están a nivel de módulo (no dentro de `construir`) para que el YAML pueda referenciarlos como `refl.iniciar`.
@node
def iniciar(ctx, node_input):
    yield Event(output=texto_de(node_input),
                state={"caso": json.dumps(CASO, ensure_ascii=False), "politica": POLITICA, "ronda": 0})


@node
def validar(ctx, node_input):
    borrador = texto_de(node_input)
    v = validar_texto(borrador)
    yield Event(output=json.dumps({"caso": CASO, "borrador": borrador, "validacion": v}, ensure_ascii=False),
                state={"validacion": v, "borrador_texto": borrador})


@node
def decidir(ctx, node_input):
    ver, val = veredicto_de(node_input), ctx.state["validacion"]
    ronda = ctx.state.get("ronda", 0) + 1
    borrador = ctx.state["borrador_texto"]
    if ver.aprobado and val["ok"]:                                   # el código exige AMBOS
        yield Event(output=borrador, route="aprobado", state={"ronda": ronda})
        return
    feedback = "; ".join(val["fallas"] + ([f"revisor: {ver.critica}"] if not ver.aprobado else []))
    if ronda >= MAX_RONDAS:                                          # tope de código
        yield Event(output=borrador, route="escalar", state={"ronda": ronda, "pendiente": feedback})
        return
    yield Event(output=f"Observaciones a corregir: {feedback}", route="revisar",
                state={"ronda": ronda, "feedback": feedback})


@node
def publicar(ctx, node_input):
    yield Event(output={"estado": "PUBLICADO", "rondas": ctx.state["ronda"], "respuesta": node_input})


@node
def escalar_a_humano(ctx, node_input):
    yield Event(output={"estado": "ESCALADO A HUMANO", "rondas": ctx.state["ronda"],
                        "ultimo_borrador": node_input, "pendiente": ctx.state.get("pendiente")})


def construir(generador, critico) -> Workflow:
    return Workflow(name="reflection", edges=[
        (START, iniciar, generador, validar, critico, decidir),
        (decidir, {"revisar": generador, "aprobado": publicar, "escalar": escalar_a_humano}),
    ])
