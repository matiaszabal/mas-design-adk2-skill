"""Qué palancas de ADK 2.9.1 cambian el contexto que recibe un agente invocado por ctx.run_node desde un worker.

Sin LLM real (modelo falso). Compara, para el MISMO flujo (planificador → workers paralelos → respondedor):
  a) include_contents='default'                      b) include_contents='none'
  c) ctx.run_node(..., use_sub_branch=True)          d) ctx.run_node(..., override_isolation_scope='w')
y dos planificadores: una FUNCIÓN (no hay LLM antes) o un LlmAgent (hay un agente que corrió antes).
    python3 explorar_palancas.py
"""
import json

from google.adk import Agent, Event, Workflow
from google.adk.workflow import START, node

import qd
from modelo_falso import ModeloFalso, textos
from traza import correr

PREG = "Un cliente Premium envía el equivalente a 1000 USD desde una cuenta en pesos al exterior. ¿Cuánto paga en comisiones?"
SUBS = ["¿Cuál es la comisión de las transferencias internacionales?", "¿Qué bonificación otorga el plan Premium?"]


def armar(palanca: str, planificador: str):
    ic = "none" if palanca == "include_contents='none'" else "default"
    kw = {"use_sub_branch=True": dict(use_sub_branch=True),
          "override_isolation_scope='w'": dict(override_isolation_scope="w")}.get(palanca, {})
    mr = ModeloFalso(responder=lambda r: json.dumps({"respuesta": "ok", "fuente": "X"}))
    md = ModeloFalso(responder=lambda r: json.dumps({"sub_preguntas": SUBS}))
    d, _, resp, _ = qd.crear_agentes(include_contents=ic, modelos={"respondedor": mr, "descomponer": md})

    if planificador == "funcion":
        @node(rerun_on_resume=True)
        async def plan(ctx, node_input):
            yield Event(output=SUBS)
    else:
        @node(rerun_on_resume=True)
        async def plan(ctx, node_input):
            p = qd.coercion(await ctx.run_node(d, node_input=qd.texto_de(node_input)), qd.Descomposicion)
            yield Event(output=p.sub_preguntas)

    @node(parallel_worker=True, rerun_on_resume=True)
    async def resolver(ctx, node_input):
        out = await ctx.run_node(resp, node_input=qd.entrada_respondedor(node_input), **kw)
        yield Event(output=str(out)[:40])

    return Workflow(name="x", edges=[(START, plan, resolver)]), mr


print(f"{'palanca':<32}{'planificador':<14}n_contents  ¿ve la pregunta original?")
for planificador in ("funcion", "llmagent"):
    for palanca in ("default", "include_contents='none'", "use_sub_branch=True", "override_isolation_scope='w'"):
        wf, mr = armar(palanca, planificador)
        correr(wf, PREG, mostrar=False)
        req = mr.llamadas[0]
        print(f"{palanca:<32}{planificador:<14}{len(req.contents):<12}{any(PREG[:40] in t for t in textos(req))}")
