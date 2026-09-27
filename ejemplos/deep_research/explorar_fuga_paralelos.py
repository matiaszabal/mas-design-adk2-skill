"""¿Los investigadores ReAct que corren EN PARALELO se ven entre sí? (modelo falso, sin red)

Cada investigador es un LlmAgent con herramienta (ReAct) invocado con ctx.run_node y include_contents='none'.
Mide, para la 2ª llamada al modelo de cada investigador (la que sigue a su búsqueda), cuántos contenidos recibe y si entre
ellos aparece la consulta o la búsqueda de OTRO investigador.

    python3 explorar_fuga_paralelos.py
"""
import asyncio
import json
import logging
import re
import warnings

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
import dr
from google.adk import Event, Workflow
from google.adk.workflow import START, node
from modelo_falso import textos
from modelo_react import ModeloFalsoReAct
from traza import correr

TEMAS = ["identidad", "litigios", "reputación"]


def guion(n, req):
    mio = [t for t in textos(req) if t.startswith("TEMA:")]
    resp = [p.function_response.response for c in req.contents for p in (c.parts or []) if p.function_response]
    if not resp:
        return ("call", "buscar_fuentes", {"consulta": mio[-1].split("CONSULTA: ")[-1]})
    return ("text", json.dumps({"tema": "x", "resumen": "r", "fuentes": [], "sin_evidencia": False}))


def experimento(nombre, paralelo):
    m = ModeloFalsoReAct(guion=guion)
    _, inv, _, _ = dr.crear_agentes(modelos={"investigador": m})

    @node(rerun_on_resume=True)
    async def director(ctx, node_input):
        entradas = [f"TEMA: {t}\nCONSULTA: {t} Andina" for t in TEMAS]
        if paralelo:
            await asyncio.gather(*[ctx.run_node(inv, node_input=e) for e in entradas])
        else:
            for e in entradas:
                await ctx.run_node(inv, node_input=e)
        yield Event(output="ok")

    correr(Workflow(name="x", edges=[(START, director)]), "pregunta original", mostrar=False)
    segundas = [r for r in m.llamadas if any(p.function_response for c in r.contents for p in (c.parts or []))]
    print(f"{nombre}: llamadas al modelo={len(m.llamadas)} | contenidos en la 2ª llamada de cada investigador={[len(r.contents) for r in segundas]}")
    for r in segundas[:1]:
        for t in textos(r):
            print("     >", t[:110].replace("\n", " ⏎ "))
    ajenos = sum(1 for r in segundas for t in textos(r) if t.startswith("TEMA:") and sum(x in t for x in TEMAS) and len({x for x in TEMAS if f"TEMA: {x}" in " ".join(textos(r))}) > 1)
    return segundas


print("== investigadores SECUENCIALES (uno después de otro)")
experimento("secuencial", paralelo=False)
print("== investigadores EN PARALELO (asyncio.gather)")
experimento("paralelo  ", paralelo=True)


def partes(req):
    """Describe cada contenido: rol y qué partes trae (texto, llamada a herramienta con sus args, resultado)."""
    out = []
    for c in req.contents:
        d = []
        for p in c.parts or []:
            if p.function_call:
                d.append(f"call {p.function_call.name}({dict(p.function_call.args)})")
            elif p.function_response:
                d.append("response(...)")
            elif p.text:
                d.append("texto: " + p.text[:40].replace("\n", " ⏎ "))
        out.append(f"{c.role}: {'; '.join(d)}")
    return out


def variante(nombre, opciones):
    m = ModeloFalsoReAct(guion=guion)
    _, inv, _, _ = dr.crear_agentes(modelos={"investigador": m})

    @node(rerun_on_resume=True)
    async def director(ctx, node_input):
        await asyncio.gather(*[ctx.run_node(inv, node_input=f"TEMA: {t}\nCONSULTA: {t} Andina", **opciones(i)) for i, t in enumerate(TEMAS)])
        yield Event(output="ok")
    try:
        correr(Workflow(name="x", edges=[(START, director)]), "pregunta original", mostrar=False)
        segundas = [r for r in m.llamadas if any(p.function_response for c in r.contents for p in (c.parts or []))]
        ajenos = sum(1 for r in segundas for x in partes(r) if x.startswith("model: call") and "consulta" in x) - len(segundas)
        print(f"   {nombre:<42} contenidos en la 2ª llamada: {[len(r.contents) for r in segundas]}  búsquedas AJENAS visibles: {max(ajenos, 0)}")
        return segundas
    except Exception as e:
        print(f"   {nombre:<42} ERROR {type(e).__name__}: {str(e)[:80]}")


print("== qué se filtra, en detalle (paralelo, sin ninguna palanca)")
seg = variante("gather sin palancas", lambda i: {})
if seg:
    for x in partes(seg[0]):
        print("     ·", x)
print("== palancas de ctx.run_node para aislar a los hermanos")
variante("use_sub_branch=True", lambda i: {"use_sub_branch": True})
variante("override_isolation_scope='inv{i}'", lambda i: {"override_isolation_scope": f"inv{i}"})
variante("override_branch='inv{i}'", lambda i: {"override_branch": f"inv{i}"})
variante("run_id='inv{i}'", lambda i: {"run_id": f"inv{i}"})
