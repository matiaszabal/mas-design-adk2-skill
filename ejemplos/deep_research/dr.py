"""Deep Research sobre ADK 2.9.1 — un Workflow con un DIRECTOR dinámico (rondas) y un redactor.

    START → iniciar → investigar (director, nodo dinámico) → redactor (LLM, solo desde las notas) → cerrar
                        │
                        └ por ronda:  planificador (LLM) → N investigadores EN PARALELO (cada uno un ReAct con
                          herramienta de búsqueda y contexto propio) → notas (código) → evaluador de brechas (LLM)
                          → ¿cobertura suficiente? / ¿presupuesto? → otra ronda o fin

Las tres decisiones de orquestación, tal como quedan en este código:

  ¿Quién decide qué sigue?  Un LLM decide QUÉ investigar (planificador) y CUÁNDO hay suficiente (evaluador). El número
                            de rondas no se conoce de antemano. El CÓDIGO reparte el trabajo en paralelo, agrega las
                            notas, impone el presupuesto y compone la salida final.
  ¿Con qué contexto?        Los investigadores trabajan AISLADOS (include_contents="none": ven solo su consulta) y
                            devuelven hallazgos condensados con fuentes. El director mantiene un BLOC DE NOTAS compacto
                            (no la conversación). El informe se escribe SOLO desde las notas.
  ¿Cuándo se detiene?       Cobertura suficiente según el evaluador, O presupuesto agotado (MAX_RONDAS / MAX_LLAMADAS).
                            La segunda condición es la que garantiza el fin. Se entrega lo logrado y las BRECHAS ABIERTAS.

Los datos son SINTÉTICOS (proveedor ficticio, «web» ficticia).
"""
import asyncio
import json
import math
import os
import re
import unicodedata

from google.adk import Agent, Event, Workflow
from google.adk.workflow import START, node
from pydantic import BaseModel

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")
MAX_RONDAS = 3
MAX_INVESTIGADORES = 5          # tope de fan-out por ronda
MAX_LLAMADAS_AGENTE = 24        # presupuesto: llamadas a agentes (planificador + investigadores + evaluador) por corrida
CHARS_NOTA = 320                # compactación: máximo de caracteres por tema en la vista que ven planificador/evaluador

PREGUNTA = ("Hacé una debida diligencia del proveedor Logística Andina S.A. (Argentina) y de su filial Logística Andina Chile SpA: "
            "identidad societaria, litigios, reputación, situación financiera y riesgos regulatorios.")

# ------------------------------------------------------------- «web» sintética
CORPUS = {
    "ID-01": "Identidad societaria — Registro mercantil (Argentina): Logística Andina S.A., constituida en 2011, con sede en Rosario. Capital social de 2 millones de USD.",
    "ID-02": "Identidad societaria — Registro societario (Chile): Logística Andina Chile SpA, filial constituida en 2016, participación de la casa matriz 100%.",
    "LI-01": "Litigios — Registro judicial (Argentina): 2 causas laborales contra Logística Andina S.A. entre 2021 y 2023, ambas cerradas con acuerdo.",
    "LI-02": "Litigios — Registro judicial (Chile): 1 demanda comercial vigente contra Logística Andina Chile SpA por incumplimiento de contrato (2025), monto reclamado 300.000 USD.",
    "RE-01": "Reputación — Prensa sectorial (2024): Logística Andina S.A. recibió el premio a la mejor flota regional de transporte de carga.",
    "RE-02": "Reputación — Foro de clientes (2025): quejas reiteradas por demoras en entregas de la filial chilena; puntaje 3,1 sobre 5.",
    "FI-01": "Situación financiera — Balance 2025 (Argentina): ingresos 18 millones de USD, deuda financiera equivalente a 0,9 veces el EBITDA.",
    "FI-02": "Situación financiera — Calificación crediticia (2025): perspectiva estable, categoría A-.",
    "RG-01": "Riesgos regulatorios — Habilitaciones (Argentina): licencia de transporte interjurisdiccional de Logística Andina S.A. vigente hasta 2027.",
    "RG-02": "Riesgos regulatorios — Superintendencia (Chile): sumario abierto contra Logística Andina Chile SpA por normativa de tiempos de conducción, sin sanción firme.",
    "DX-01": "Nota de prensa: otra empresa, Logística Andes Ltda., fue sancionada por evasión fiscal.",
    "DX-02": "Clima: alerta meteorológica en Rosario por tormentas.",
}
_STOP = {"de", "la", "el", "los", "las", "un", "una", "por", "que", "en", "y", "a", "del", "al", "se", "es", "con", "su", "sus", "lo", "para", "s", "sa", "spa"}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _tokens(t: str) -> set[str]:
    return {w[:6] for w in re.findall(r"[a-z0-9]+", _norm(t)) if w not in _STOP and len(w) > 1}


_DF: dict[str, int] = {}
for _t in CORPUS.values():
    for _w in _tokens(_t):
        _DF[_w] = _DF.get(_w, 0) + 1

LLAMADAS_BUSQUEDA: list[str] = []          # gancho de prueba
TRAZA_RONDAS: list[dict] = []              # traza de lo que decidió el director en cada ronda


def buscar_fuentes(consulta: str) -> dict:
    """Busca en la web sintética y devuelve la fuente más relevante (id y texto). Podés llamarla varias veces con consultas distintas."""
    LLAMADAS_BUSQUEDA.append(consulta)
    q, n = _tokens(consulta), len(CORPUS)
    puntaje = sorted(((sum(math.log(n / _DF[w]) for w in q & _tokens(t) if w in _DF), i) for i, t in CORPUS.items()), reverse=True)
    if not puntaje or puntaje[0][0] <= 0:
        return {"fuentes": [], "nota": "sin resultados"}
    return {"fuentes": [{"id": puntaje[0][1], "texto": CORPUS[puntaje[0][1]]}]}


# ------------------------------------------------------------------- esquemas
class Consulta(BaseModel):
    tema: str
    consulta: str


class Ronda(BaseModel):
    consultas: list[Consulta]


class Hallazgo(BaseModel):
    tema: str
    resumen: str
    fuentes: list[str] = []
    sin_evidencia: bool = False


class Evaluacion(BaseModel):
    cobertura_suficiente: bool
    brechas: list[str] = []


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


def como(x, esquema):
    if isinstance(x, esquema):
        return x
    if isinstance(x, dict):
        return esquema.model_validate(x)
    return esquema.model_validate_json(texto_de(x).strip().removeprefix("```json").removeprefix("```").removesuffix("```"))


# ------------------------------------------------------------ agentes reales
def crear_agentes(modelos: dict | None = None, include_contents: str = "none"):
    m = lambda n: (modelos or {}).get(n, MODEL)
    planificador = Agent(
        name="planificador", model=m("planificador"), output_schema=Ronda, include_contents=include_contents, before_model_callback=log_contexto,
        instruction=(
            "Sos el director de una investigación. Recibís un JSON con la pregunta, las NOTAS compactas ya reunidas y las "
            f"BRECHAS pendientes. Proponé hasta {MAX_INVESTIGADORES} consultas de investigación (tema + consulta concreta). "
            "En la primera ronda cubrí todos los temas de la pregunta y ambas entidades; luego, SOLO las brechas, sin repetir "
            "lo ya cubierto."))
    investigador = Agent(
        name="investigador", model=m("investigador"), tools=[buscar_fuentes], output_schema=Hallazgo, include_contents=include_contents,
        before_model_callback=log_contexto,
        instruction=(
            "Sos un investigador. Recibís UNA consulta (tema y consulta). Buscá en las fuentes con la herramienta (podés buscar "
            "varias veces, por ejemplo por país o entidad) y resumí SOLO lo que encontraste, citando los ids de las fuentes "
            "usadas en 'fuentes'. Si no hay evidencia: sin_evidencia=true y explicalo. No inventes."))
    evaluador = Agent(
        name="evaluador", model=m("evaluador"), output_schema=Evaluacion, include_contents=include_contents, before_model_callback=log_contexto,
        instruction=(
            "Sos el evaluador de cobertura. Recibís la pregunta y las NOTAS compactas. Decidí si cubren TODOS los temas para "
            "AMBAS entidades (la sociedad argentina y la filial chilena). Si no, cobertura_suficiente=false y 'brechas' con "
            "lo concreto que falta (tema y entidad). Un tema con sin_evidencia=true cuenta como brecha SOLO si es plausible "
            "encontrarlo; no pidas repetir búsquedas ya agotadas."))
    redactor = Agent(
        name="redactor", model=m("redactor"), include_contents=include_contents, before_model_callback=log_contexto,
        instruction=(
            "Redactá el informe de debida diligencia SOLO a partir de las notas que recibís (JSON con pregunta, notas y brechas "
            "abiertas). Citá las fuentes entre corchetes con su id, por ejemplo [LI-02]. No afirmes nada que no esté en las notas. "
            "Terminá con la sección «Brechas abiertas» listando lo que no se pudo cubrir."))
    return planificador, investigador, evaluador, redactor


# ------------------------------------------------------------- notas (código)
def _clave(tema: str) -> str:
    return _norm(tema).strip()


def fusionar(notas: dict, h: Hallazgo) -> None:
    k = _clave(h.tema)
    if k not in notas:
        notas[k] = {"tema": h.tema, "resumen": h.resumen, "fuentes": list(dict.fromkeys(h.fuentes)), "sin_evidencia": h.sin_evidencia}
        return
    n = notas[k]
    if h.resumen and h.resumen not in n["resumen"]:
        n["resumen"] = (n["resumen"] + " " + h.resumen).strip() if not n["sin_evidencia"] else h.resumen
    n["fuentes"] = list(dict.fromkeys(n["fuentes"] + h.fuentes))
    n["sin_evidencia"] = n["sin_evidencia"] and h.sin_evidencia


def compactar(notas: dict) -> dict:
    """Vista COMPACTA de las notas para el planificador y el evaluador: no ven el material crudo ni textos largos."""
    return {k: {"tema": v["tema"], "resumen": v["resumen"][:CHARS_NOTA], "fuentes": v["fuentes"], "sin_evidencia": v["sin_evidencia"]} for k, v in notas.items()}


def citas_de(texto: str) -> list[str]:
    """Ids citados en el texto, incluidas las citas AGRUPADAS: «[LI-01, RG-01]» y «[LI-02]». (La primera versión solo
    reconocía un id por corchete y quedó ciega al formato que el modelo realmente usa.)"""
    ids: list[str] = []
    for grupo in re.findall(r"\[([^\]]*)\]", texto):
        ids += re.findall(r"[A-Z]{2}-\d{2}", grupo)
    return ids


def auditar_citas(informe: str, notas: dict) -> list[str]:
    """Determinista: toda cita del informe debe existir en el corpus y haber sido reunida en las notas.
    NO verifica que la fuente RESPALDE la afirmación (para eso hace falta revisión humana o un verificador semántico)."""
    citadas = set(citas_de(informe))
    reunidas = {f for n in notas.values() for f in n["fuentes"]}
    problemas = [f"cita {c} inexistente en las fuentes" for c in sorted(citadas - set(CORPUS))]
    problemas += [f"cita {c} que ningún investigador reunió" for c in sorted((citadas & set(CORPUS)) - reunidas)]
    return problemas


# --------------------------------------------------------------------- nodos
@node
def iniciar(ctx, node_input):
    yield Event(output=texto_de(node_input), state={"pregunta": texto_de(node_input)})


def construir(planificador, investigador, evaluador, redactor) -> Workflow:
    @node(rerun_on_resume=True)
    async def investigar(ctx, node_input):
        pregunta = texto_de(node_input)
        notas, brechas, motivo, llamadas, rondas = {}, [], "cobertura suficiente", 0, 0

        async def uno(c: Consulta) -> Hallazgo:                       # un investigador: aislado, con su propio contexto
            try:
                # use_sub_branch=True es IMPRESCINDIBLE con investigadores ReAct en paralelo: sin él, cada uno ve las
                # llamadas a herramientas (y las consultas) de sus hermanos (explorar_fuga_paralelos.py).
                return como(await ctx.run_node(investigador, node_input=f"TEMA: {c.tema}\nCONSULTA: {c.consulta}", use_sub_branch=True), Hallazgo)
            except Exception as e:                                    # un fallo no debe tirar a los demás: se registra como sin evidencia
                return Hallazgo(tema=c.tema, resumen=f"falló la investigación: {type(e).__name__}", sin_evidencia=True)

        for r in range(MAX_RONDAS):                                   # presupuesto 1: rondas
            if llamadas >= MAX_LLAMADAS_AGENTE:                       # presupuesto 2: llamadas a agentes
                motivo = "presupuesto (llamadas)"; break
            ronda = como(await ctx.run_node(planificador, node_input=json.dumps(
                {"pregunta": pregunta, "notas": compactar(notas), "brechas": brechas}, ensure_ascii=False)), Ronda)
            consultas = ronda.consultas[:MAX_INVESTIGADORES]           # tope de fan-out
            llamadas += 1 + len(consultas)
            rondas += 1
            hallazgos = await asyncio.gather(*[uno(c) for c in consultas])
            for h in hallazgos:
                fusionar(notas, h)
            ev = como(await ctx.run_node(evaluador, node_input=json.dumps(
                {"pregunta": pregunta, "notas": compactar(notas)}, ensure_ascii=False)), Evaluacion)
            llamadas += 1
            brechas = [] if ev.cobertura_suficiente else ev.brechas
            TRAZA_RONDAS.append({"ronda": r + 1, "consultas": [(c.tema, c.consulta) for c in consultas],
                                 "hallazgos": {h.tema: {"sin_evidencia": h.sin_evidencia, "fuentes": h.fuentes} for h in hallazgos},
                                 "cobertura_suficiente": ev.cobertura_suficiente, "brechas": brechas})
            if ev.cobertura_suficiente:
                break
            if r == MAX_RONDAS - 1:
                motivo = "presupuesto (rondas)"
        yield Event(output=json.dumps({"pregunta": pregunta, "notas": compactar(notas), "brechas_abiertas": brechas}, ensure_ascii=False),
                    state={"notas": notas, "brechas_abiertas": brechas, "rondas": rondas, "motivo_fin": motivo, "llamadas_agente": llamadas})

    @node
    def cerrar(ctx, node_input):
        informe = texto_de(node_input)
        yield Event(output={"informe": informe, "rondas": ctx.state["rondas"], "motivo_fin": ctx.state["motivo_fin"],
                            "brechas_abiertas": ctx.state["brechas_abiertas"], "llamadas_agente": ctx.state["llamadas_agente"],
                            "citas_invalidas": auditar_citas(informe, ctx.state["notas"])})

    return Workflow(name="deep_research", edges=[(START, iniciar, investigar, redactor, cerrar)])
