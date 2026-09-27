"""Planner-Executor sobre ADK 2.9.1 — un Workflow (grafo con ciclo por rutas + un nodo dinámico ejecutor).

  START → iniciar → planner ─► validar_plan ─┬ "ok" → pedir_aprobacion → recibir_respuesta ─┬ "aprobado" → ejecutar ─┬ "completo" → informar
                       ▲                     └ "invalido" ──┐                               └ "observaciones" ─┐     └ "falla" ───┐
                       └───── "replanificar" ── decidir_falla ◄───────────────────────────────────────────────┴────────────────────┘
                                                     └ "escalar" → escalar_a_humano

Las tres decisiones de orquestación, tal como quedan en este código:

  ¿Quién decide qué sigue?
    - El LLM (planner) decide UNA vez el recorrido completo, como un PLAN (artefacto). El EJECUTOR es código: no
      vuelve a decidir «qué sigue»; corre los pasos por oleadas según sus dependencias (los independientes en paralelo).
    - El plan lo valida código (`validar_plan`) y, si APROBACION_HUMANA, una persona (RequestInput) ANTES de ejecutar.
  ¿Con qué contexto?
    - El planner (include_contents="none") ve el objetivo, el catálogo de herramientas y, al replanificar, lo ya
      hecho y el error; NO ve datos reales. Cada paso ve SOLO su parámetro y las salidas de sus dependencias.
  ¿Cuándo se detiene?
    - Todos los pasos hechos ("completo"), o falla: se replanifica hasta MAX_REPLANES veces conservando lo ya
      hecho, y luego se escala a una persona informando lo hecho y lo pendiente.

Los datos son SINTÉTICOS (conciliación de un banco ficticio).
"""
import asyncio
import json
import os
import re

from google.adk import Agent, Event, Workflow
from google.adk.events import RequestInput
from google.adk.workflow import START, node
from pydantic import BaseModel

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")
MAX_PASOS = 6
MAX_REPLANES = 1
APROBACION_HUMANA = False       # True: el flujo se PAUSA con RequestInput antes de ejecutar el plan
DEMORA = 0.0                    # segundos que "tarda" cada herramienta (para probar el paralelismo)

# ---------------------------------------------------------------- datos sintéticos
INTERNOS = [{"id": "M1", "monto": 100}, {"id": "M2", "monto": 250}, {"id": "M3", "monto": 75}]
EXTRACTO = [{"id": "M1", "monto": 100}, {"id": "M2", "monto": 250}, {"id": "B9", "monto": 40}]

CATALOGO = {
    "extraer_movimientos_internos": "0 entradas. parametro = período AAAA-MM.",
    "extraer_extracto_banco": "0 entradas. parametro = período AAAA-MM. Si el extracto viene en otro formato, el error indica cómo reintentar.",
    "cruzar": "2 entradas: [id de los movimientos internos, id del extracto]. Sin parametro.",
    "listar_diferencias": "1 entrada: [id del cruce]. Sin parametro.",
    "redactar_informe": "1 entrada: [id de las diferencias]. Sin parametro.",
}
ARIDAD = {"extraer_movimientos_internos": 0, "extraer_extracto_banco": 0, "cruzar": 2, "listar_diferencias": 1, "redactar_informe": 1}


class Paso(BaseModel):
    id: int
    herramienta: str
    entradas: list[int] = []
    parametro: str = ""


class Plan(BaseModel):
    pasos: list[Paso]


# ------------------------------------------------------------ herramientas (código)
LLAMADAS_HERRAMIENTAS: list[tuple[str, dict]] = []     # gancho de prueba: qué recibió cada herramienta


@node
async def extraer_movimientos_internos(node_input):
    LLAMADAS_HERRAMIENTAS.append(("extraer_movimientos_internos", node_input))
    await asyncio.sleep(DEMORA)
    return {"ok": True, "valor": INTERNOS}


@node
async def extraer_extracto_banco(node_input):
    LLAMADAS_HERRAMIENTAS.append(("extraer_extracto_banco", node_input))
    await asyncio.sleep(DEMORA)
    periodo = node_input["parametro"]
    if periodo.startswith("2026-08") and ";alt" not in periodo:      # el extracto de agosto viene en otro formato
        return {"ok": False, "error": f"formato de extracto no soportado para {periodo}; reintentar con parametro='{periodo};alt'"}
    return {"ok": True, "valor": EXTRACTO}


@node
async def cruzar(node_input):
    LLAMADAS_HERRAMIENTAS.append(("cruzar", node_input))
    await asyncio.sleep(DEMORA)
    internos, extracto = node_input["entradas"]
    ids_i, ids_e = {m["id"] for m in internos}, {m["id"] for m in extracto}
    return {"ok": True, "valor": {"coinciden": sorted(ids_i & ids_e), "solo_libros": sorted(ids_i - ids_e), "solo_banco": sorted(ids_e - ids_i)}}


@node
async def listar_diferencias(node_input):
    LLAMADAS_HERRAMIENTAS.append(("listar_diferencias", node_input))
    await asyncio.sleep(DEMORA)
    (cruce,) = node_input["entradas"]
    return {"ok": True, "valor": [f"{i}: solo en libros" for i in cruce["solo_libros"]] + [f"{i}: solo en el banco" for i in cruce["solo_banco"]]}


@node
async def redactar_informe(node_input):
    LLAMADAS_HERRAMIENTAS.append(("redactar_informe", node_input))
    await asyncio.sleep(DEMORA)
    (difs,) = node_input["entradas"]
    return {"ok": True, "valor": "Conciliación: " + ("; ".join(difs) if difs else "sin diferencias") + "."}


HERRAMIENTAS = {"extraer_movimientos_internos": extraer_movimientos_internos, "extraer_extracto_banco": extraer_extracto_banco,
                "cruzar": cruzar, "listar_diferencias": listar_diferencias, "redactar_informe": redactar_informe}


# ----------------------------------------------------- evidencia de "con qué contexto"
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


def plan_de(x) -> Plan:
    if isinstance(x, Plan):
        return x
    if isinstance(x, dict):
        return Plan.model_validate(x)
    return Plan.model_validate_json(texto_de(x).strip().removeprefix("```json").removeprefix("```").removesuffix("```"))


def validar_reglas(plan: Plan, hechos: set[int]) -> list[str]:
    """Reglas DETERMINISTAS del plan (código). Devuelve la lista de problemas (vacía si es válido)."""
    p = []
    if not plan.pasos:
        p.append("el plan no tiene pasos")
    if len(plan.pasos) > MAX_PASOS:
        p.append(f"el plan tiene {len(plan.pasos)} pasos (máximo {MAX_PASOS})")
    ids = [x.id for x in plan.pasos]
    if len(set(ids)) != len(ids):
        p.append("hay ids de paso repetidos")
    for x in plan.pasos:
        if x.herramienta not in HERRAMIENTAS:
            p.append(f"paso {x.id}: herramienta desconocida «{x.herramienta}»")
            continue
        if len(x.entradas) != ARIDAD[x.herramienta]:
            p.append(f"paso {x.id}: {x.herramienta} necesita {ARIDAD[x.herramienta]} entradas y tiene {len(x.entradas)}")
        for e in x.entradas:
            if e >= x.id or (e not in ids and e not in hechos):
                p.append(f"paso {x.id}: la entrada {e} no es un paso anterior ni uno ya completado")
        if x.id in hechos:
            p.append(f"paso {x.id}: ya estaba completado, no se repite")
    return p


# -------------------------------------------------------------------- agente real
def crear_planner(modelo=None, include_contents: str = "none"):
    return Agent(
        name="planner", model=modelo or MODEL, output_schema=Plan, include_contents=include_contents,
        before_model_callback=log_contexto,
        instruction=(
            "Sos un planificador. NO ejecutás nada: devolvés un plan. Cada paso tiene id (entero, los nuevos empiezan en "
            "{siguiente_id}), herramienta, entradas (ids de pasos previos cuyas salidas necesita) y parametro (texto).\n"
            "HERRAMIENTAS:\n{herramientas}\nOBJETIVO: {objetivo}\n"
            "Pasos ya completados que podés reutilizar como entradas (no los repitas): {resultados_previos?}\n"
            "Observaciones a corregir: {feedback?}\nUsá como máximo {max_pasos} pasos."))


# ------------------------------------------------------------------------ nodos
@node
def iniciar(ctx, node_input):
    objetivo = texto_de(node_input)
    yield Event(output=objetivo, state={
        "objetivo": objetivo, "max_pasos": MAX_PASOS, "siguiente_id": 1, "replanes": 0, "resultados": {},
        "herramientas": "\n".join(f"- {k}: {v}" for k, v in CATALOGO.items())})


@node
def validar_plan(ctx, node_input):
    plan = plan_de(node_input)
    hechos = {int(k) for k in ctx.state.get("resultados", {})}
    problemas = validar_reglas(plan, hechos)
    if problemas:
        fb = "Plan inválido: " + "; ".join(problemas)
        yield Event(output=fb, route="invalido", state={"feedback": fb})
        return
    texto = "\n".join(f"{x.id}. {x.herramienta}({x.parametro}) ← {x.entradas}" for x in plan.pasos)
    yield Event(output=texto, route="ok", state={"plan": plan.model_dump()})


@node
def pedir_aprobacion(ctx, node_input):
    if APROBACION_HUMANA:
        yield RequestInput(message=f"Plan propuesto:\n{node_input}\n\nRespondé «aprobar» o escribí observaciones.")
    else:
        yield Event(output="aprobar")


@node
def recibir_respuesta(ctx, node_input):
    r = texto_de(node_input).strip()
    if r.lower() in ("aprobar", "aprobado", "si", "sí", "ok"):
        yield Event(output="aprobado", route="aprobado")
    else:
        fb = f"Observaciones del revisor: {r}"
        yield Event(output=fb, route="observaciones", state={"feedback": fb})


@node(rerun_on_resume=True)          # ctx.run_node exige rerun_on_resume=True en el nodo que lo llama
async def ejecutar(ctx, node_input):
    plan = Plan.model_validate(ctx.state["plan"])
    resultados = dict(ctx.state.get("resultados", {}))
    pendientes = [p for p in plan.pasos if str(p.id) not in resultados]
    fallas, oleadas = [], 0
    while pendientes:
        listos = [p for p in pendientes if all(str(e) in resultados for e in p.entradas)]
        if not listos:
            break                                    # lo que queda depende de un paso que falló
        oleadas += 1
        salidas = await asyncio.gather(*[ctx.run_node(HERRAMIENTAS[p.herramienta], node_input={
            "parametro": p.parametro, "entradas": [resultados[str(e)]["valor"] for e in p.entradas]}) for p in listos])
        for p, s in zip(listos, salidas):
            if s["ok"]:
                resultados[str(p.id)] = {"herramienta": p.herramienta, "valor": s["valor"]}
            else:
                fallas.append({"id": p.id, "herramienta": p.herramienta, "error": s["error"]})
        pendientes = [p for p in pendientes if str(p.id) not in resultados and p.id not in {f["id"] for f in fallas}]
    no_ejecutados = [p.id for p in pendientes]
    estado = {"resultados": resultados, "oleadas": oleadas}
    if not fallas and not no_ejecutados:
        yield Event(output="completo", route="completo", state=estado)
        return
    fb = "Fallaron pasos: " + "; ".join(f"{f['id']} ({f['herramienta']}): {f['error']}" for f in fallas)
    if no_ejecutados:
        fb += f". No se ejecutaron por depender de un paso fallido: {no_ejecutados}"
    yield Event(output=fb, route="falla", state={**estado, "feedback": fb})


@node
def decidir_falla(ctx, node_input):
    fb = texto_de(node_input)
    r = ctx.state.get("replanes", 0) + 1
    hechos = ctx.state.get("resultados", {})
    historial = ctx.state.get("historial", []) + [fb]           # todas las fallas, para no perder el error original
    if r > MAX_REPLANES:                                         # tope de código
        yield Event(output=fb, route="escalar", state={"replanes": r - 1, "historial": historial})
        return
    prev = "; ".join(f"{k} = {v['herramienta']}" for k, v in sorted(hechos.items(), key=lambda kv: int(kv[0]))) or "(ninguno)"
    yield Event(output=fb, route="replanificar", state={
        "replanes": r, "feedback": fb, "resultados_previos": prev, "historial": historial,
        "siguiente_id": max([int(k) for k in hechos] + [x["id"] for x in ctx.state.get("plan", {}).get("pasos", [])] + [0]) + 1})


@node
def informar(ctx, node_input):
    r = ctx.state["resultados"]
    informe = next((v["valor"] for v in r.values() if v["herramienta"] == "redactar_informe"), None)
    yield Event(output={"estado": "COMPLETADO", "replanificaciones": ctx.state.get("replanes", 0),
                        "pasos": sorted(int(k) for k in r), "informe": informe})


@node
def escalar_a_humano(ctx, node_input):
    r = ctx.state.get("resultados", {})
    yield Event(output={"estado": "ESCALADO A HUMANO", "replanificaciones": ctx.state.get("replanes", 0),
                        "hecho": sorted(int(k) for k in r), "pendiente": texto_de(node_input),
                        "historial_de_fallas": ctx.state.get("historial", [])})


def construir(planner) -> Workflow:
    return Workflow(name="planner_executor", edges=[
        (START, iniciar, planner, validar_plan),
        (validar_plan, {"ok": pedir_aprobacion, "invalido": decidir_falla}),
        (pedir_aprobacion, recibir_respuesta),
        (recibir_respuesta, {"aprobado": ejecutar, "observaciones": decidir_falla}),
        (ejecutar, {"completo": informar, "falla": decidir_falla}),
        (decidir_falla, {"replanificar": planner, "escalar": escalar_a_humano}),
    ])
