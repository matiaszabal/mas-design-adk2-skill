"""Query Decomposition sobre ADK 2.9.1 — variante paralela y variante secuencial.

Las tres decisiones de orquestación, tal como quedan en este código:

  ¿Quién decide qué sigue?
    - El LLM decide UNA vez cómo partir la pregunta (paralela) o, en la secuencial, decide tras cada
      respuesta si hace falta otra sub-pregunta. El resto es código: recuperar, repartir, juntar.
  ¿Con qué contexto?
    - Cada sub-pregunta se resuelve en una llamada propia cuyo `node_input` es SOLO la sub-pregunta
      + los fragmentos recuperados. HALLAZGO (2.9.1): el aislamiento NO es automático; hay que pedirlo con
      `include_contents="none"` en el agente. Lo que el agente recibe realmente lo mide LOG_CONTEXTO.
  ¿Cuándo se detiene?
    - Topes de CÓDIGO: MAX_SUBPREGUNTAS (recorta el plan), MAX_PARALELO (concurrencia) y
      MAX_PASOS (la secuencial corta aunque el modelo siga pidiendo sub-preguntas).
"""
import json
import os

from google.adk import Agent, Event, Workflow
from google.adk.workflow import START, node
from pydantic import BaseModel

from kb import buscar

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")
MAX_SUBPREGUNTAS = 4
MAX_PARALELO = 4
MAX_PASOS = 4


# --------------------------------------------------------------------- esquemas
class Descomposicion(BaseModel):
    sub_preguntas: list[str]


class Respuesta(BaseModel):
    respuesta: str
    fuente: str          # id del documento, o "sin evidencia"


class Siguiente(BaseModel):
    terminar: bool
    sub_pregunta: str = ""


# ----------------------------------------------------- evidencia de "con qué contexto"
LOG_CONTEXTO: list[dict] = []


def log_contexto(callback_context, llm_request):
    """before_model_callback: registra qué recibe el modelo en cada llamada (no lo modifica)."""
    contents = llm_request.contents or []
    LOG_CONTEXTO.append({
        "agente": callback_context.agent_name,
        "n_contents": len(contents),
        "roles": [c.role for c in contents],
        "textos": [(p.text or "")[:110].replace("\n", " ⏎ ") for c in contents for p in (c.parts or [])],
    })
    return None


# ------------------------------------------------------------------- utilidades
def texto_de(x) -> str:
    """Texto plano de un node_input (str, Content, dict o modelo)."""
    if isinstance(x, str):
        return x
    if hasattr(x, "parts") and x.parts:
        return "".join(getattr(p, "text", "") or "" for p in x.parts)
    if isinstance(x, BaseModel):
        return x.model_dump_json()
    return str(x)


def coercion(x, esquema):
    if isinstance(x, esquema):
        return x
    if isinstance(x, dict):
        return esquema.model_validate(x)
    return esquema.model_validate_json(texto_de(x).strip().removeprefix("```json").removeprefix("```").removesuffix("```"))


def entrada_respondedor(sub_pregunta: str) -> str:
    frag = buscar(sub_pregunta)
    txt = "\n".join(f"[{i}] {t}" for i, t in frag) or "(sin fragmentos)"
    return f"SUB-PREGUNTA: {sub_pregunta}\nFRAGMENTOS:\n{txt}"


# ------------------------------------------------------------------ agentes reales
def crear_agentes(include_contents: str = "none", modelos: dict | None = None, respondedor_paralelo: bool = False):
    """`include_contents="none"` (default): cada agente ve SOLO su node_input; todo el contexto viaja explícito.
    Con "default" ADK 2.9.1 le suma la pregunta original y una transcripción del plan (ver test_sin_llm.py).
    `modelos` permite inyectar otro modelo por agente (p. ej. uno falso en los tests).
    `respondedor_paralelo=True` marca al respondedor como worker paralelo (variante de grafo puro)."""
    m = lambda nombre: (modelos or {}).get(nombre, MODEL)
    descomponer = Agent(
        name="descomponer", model=m("descomponer"), include_contents=include_contents, output_schema=Descomposicion, before_model_callback=log_contexto,
        instruction=(
            "Partí la pregunta del cliente en 2 a 4 sub-preguntas independientes. Cada una debe poder "
            "responderse con UN documento de una base de tarifas y planes. No respondas la pregunta."))
    siguiente = Agent(
        name="siguiente", model=m("siguiente"), include_contents=include_contents, output_schema=Siguiente, before_model_callback=log_contexto,
        instruction=(
            "Recibís un JSON con la pregunta y los 'hechos' ya establecidos (sub-pregunta, respuesta, fuente). "
            "NO termines hasta que estén establecidos TODOS los datos que la pregunta necesita. Si la pregunta "
            "habla de una entidad (p. ej. un cliente), primero averiguá sus atributos relevantes (p. ej. su plan); "
            "después la regla que se aplica a esos atributos y el valor base. Si ya alcanza para responder: "
            "terminar=true. Si falta un dato: terminar=false y UNA sola sub-pregunta nueva, concreta, que use los "
            "hechos previos."))
    respondedor = Agent(
        name="respondedor", model=m("respondedor"), output_schema=Respuesta, before_model_callback=log_contexto,
        include_contents=include_contents, parallel_worker=True if respondedor_paralelo else None,
        instruction=(
            "Respondé la SUB-PREGUNTA usando SOLO los FRAGMENTOS. En 'fuente' poné el id del fragmento "
            "usado (p. ej. TAR-01). Si los fragmentos no alcanzan: respuesta='sin evidencia', fuente='sin evidencia'."))
    sintetizador = Agent(
        name="sintetizador", model=m("sintetizador"), include_contents=include_contents, before_model_callback=log_contexto,
        instruction=(
            "Recibís un JSON con la pregunta original y las respuestas parciales con su fuente. Respondé la "
            "pregunta con el cálculo paso a paso, citando las fuentes. Usá SOLO esas respuestas parciales; "
            "si falta información, decilo."))
    return descomponer, siguiente, respondedor, sintetizador


# --------------------------------------------------------- variante PARALELA
def construir_paralela(descomponer, respondedor, sintetizador) -> Workflow:
    """START → planificar → resolver (un worker por sub-pregunta, en paralelo) → sintetizar."""

    @node(rerun_on_resume=True)
    async def planificar(ctx, node_input):
        pregunta = texto_de(node_input)
        plan = coercion(await ctx.run_node(descomponer, node_input=pregunta), Descomposicion)
        subs = plan.sub_preguntas[:MAX_SUBPREGUNTAS]                 # tope de código
        yield Event(output=subs, state={"pregunta": pregunta, "recortadas": len(plan.sub_preguntas) - len(subs)})

    @node(parallel_worker=True, rerun_on_resume=True, max_parallel_workers=MAX_PARALELO)
    async def resolver(ctx, node_input):                             # node_input = UNA sub-pregunta
        r = coercion(await ctx.run_node(respondedor, node_input=entrada_respondedor(node_input)), Respuesta)
        yield Event(output={"sub_pregunta": node_input, **r.model_dump()})

    @node(rerun_on_resume=True)
    async def sintetizar(ctx, node_input):
        payload = json.dumps({"pregunta": ctx.state["pregunta"], "respuestas_parciales": node_input}, ensure_ascii=False)
        out = await ctx.run_node(sintetizador, node_input=payload)
        yield Event(output=texto_de(out))

    return Workflow(name="qd_paralela", edges=[(START, planificar, resolver, sintetizar)])


# ------------------------------------------------------- variante SECUENCIAL
def construir_secuencial(siguiente, respondedor, sintetizador) -> Workflow:
    """START → investigar (bucle: el LLM pide la próxima sub-pregunta con los hechos previos) → sintetizar."""

    @node(rerun_on_resume=True)
    async def investigar(ctx, node_input):
        pregunta = texto_de(node_input)
        hechos, motivo = [], "tope"
        for _ in range(MAX_PASOS):                                   # tope de código
            sig = coercion(await ctx.run_node(
                siguiente, node_input=json.dumps({"pregunta": pregunta, "hechos": hechos}, ensure_ascii=False)),
                Siguiente)
            if sig.terminar or not sig.sub_pregunta.strip():
                motivo = "completo"
                break
            r = coercion(await ctx.run_node(respondedor, node_input=entrada_respondedor(sig.sub_pregunta)), Respuesta)
            hechos.append({"sub_pregunta": sig.sub_pregunta, **r.model_dump()})
        yield Event(output={"pregunta": pregunta, "hechos": hechos, "motivo_fin": motivo})

    @node(rerun_on_resume=True)
    async def sintetizar(ctx, node_input):
        out = await ctx.run_node(sintetizador, node_input=json.dumps(
            {"pregunta": node_input["pregunta"], "respuestas_parciales": node_input["hechos"],
             "motivo_fin": node_input["motivo_fin"]}, ensure_ascii=False))
        yield Event(output=texto_de(out))

    return Workflow(name="qd_secuencial", edges=[(START, investigar, sintetizar)])


# ------------------------------------------------ variante PARALELA como GRAFO PURO
# Sin ctx.run_node dentro de funciones: el respondedor ES el worker paralelo (LlmAgent con
# parallel_worker=True) y recibe UN elemento de la lista. Los nodos están a nivel de módulo para
# que el YAML pueda referenciarlos como `qd.iniciar_qd`, `qd.expandir` y `qd.juntar`.
@node
def iniciar_qd(ctx, node_input):
    pregunta = texto_de(node_input)
    yield Event(output=pregunta, state={"pregunta": pregunta})


@node
def expandir(ctx, node_input):
    """node_input = la Descomposicion del LLM (dict). Recorta (tope de código) y arma UNA entrada por sub-pregunta."""
    plan = coercion(node_input, Descomposicion)
    subs = plan.sub_preguntas[:MAX_SUBPREGUNTAS]
    yield Event(output=[entrada_respondedor(x) for x in subs],
                state={"subs": subs, "recortadas": len(plan.sub_preguntas) - len(subs)})


@node
def juntar(ctx, node_input):
    """node_input = lista de Respuesta (una por worker, en el mismo orden que las sub-preguntas)."""
    parciales = [{"sub_pregunta": q, **coercion(r, Respuesta).model_dump()} for q, r in zip(ctx.state["subs"], node_input)]
    yield Event(output=json.dumps({"pregunta": ctx.state["pregunta"], "respuestas_parciales": parciales}, ensure_ascii=False))


def construir_paralela_grafo(descomponer, respondedor, sintetizador) -> Workflow:
    """START → iniciar → descomponer → expandir → respondedor (parallel_worker) → juntar → sintetizador.
    El `respondedor` debe crearse con respondedor_paralelo=True."""
    return Workflow(name="qd_paralela_grafo",
                    edges=[(START, iniciar_qd, descomponer, expandir, respondedor, juntar, sintetizador)])


# Worker paralelo definido en Python para poder referenciarlo desde el YAML (`qd.respondedor_worker`):
# el cargador YAML NO acepta `parallel_worker` dentro de un agente en línea (LlmAgentConfig lo rechaza).
respondedor_worker = crear_agentes(respondedor_paralelo=True)[2]
