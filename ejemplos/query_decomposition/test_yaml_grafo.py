"""Query Decomposition (paralela, grafo puro) descrita en YAML vs. construida en Python — sin LLM real.

    python3 test_yaml_grafo.py
"""
import asyncio
import json
import re
import sys
import time
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
from google.adk.agents.config_agent_utils import from_config

import qd
from modelo_falso import ModeloFalso, textos, ultimo_texto
from traza import correr, texto_final

RUTA = "yaml_qd_grafo/root_agent.yaml"
PREG = "Un cliente Premium envía el equivalente a 1000 USD desde una cuenta en pesos al exterior. ¿Cuánto paga en comisiones?"
SUBS = ["¿Cuál es la comisión de las transferencias internacionales?", "¿Qué bonificación otorga el plan Premium?",
        "¿Qué costo tiene la conversión de moneda?"]
FALLAS = []


def chequeo(nombre, ok, detalle=""):
    print(f"  [{'OK ' if ok else 'FALLA'}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    if not ok:
        FALLAS.append(nombre)


norm = lambda t: re.sub(r"\s+", " ", str(t)).strip()
aristas = lambda wf: sorted((getattr(e.from_node, "name", str(e.from_node)), getattr(e.to_node, "name", str(e.to_node)), e.route) for e in wf.graph.edges)


def nodo(wf, nombre):
    n = next(x for x in wf.graph.nodes if x.name == nombre)
    return getattr(n, "_node", n)         # el worker paralelo viene envuelto en _ParallelWorker; `_node` es un atributo
                                          # PRIVADO de ADK (se usa solo en este test) y es una COPIA del agente original


print("== Y1 · equivalencia estructural YAML vs Python")
wy = from_config(RUTA)
d, s, r, y = qd.crear_agentes(respondedor_paralelo=True)
wp = qd.construir_paralela_grafo(d, r, y)
chequeo("mismos nodos", sorted(n.name for n in wy.graph.nodes) == sorted(n.name for n in wp.graph.nodes))
chequeo("mismas aristas", aristas(wy) == aristas(wp), f"{len(aristas(wy))} aristas")
for nombre, pyag in (("descomponer", d), ("sintetizador", y)):
    a = nodo(wy, nombre)
    chequeo(f"{nombre}: include_contents, output_schema e instrucción iguales",
            (a.include_contents, a.output_schema, norm(a.instruction)) == (pyag.include_contents, pyag.output_schema, norm(pyag.instruction)),
            f"{a.include_contents!r}, {getattr(a.output_schema, '__name__', None)}")
w = nodo(wy, "respondedor")
envoltorio = next(x for x in wy.graph.nodes if x.name == "respondedor")
chequeo("el worker viene de qd.respondedor_worker: envuelto como _ParallelWorker, con mismos campos e instrucción",
        type(envoltorio).__name__ == "_ParallelWorker" and (w.include_contents, w.output_schema, norm(w.instruction)) == ("none", qd.Respuesta, norm(qd.respondedor_worker.instruction)),
        f"{type(envoltorio).__name__} → {type(w).__name__}; la copia interna tiene parallel_worker={w.parallel_worker} (el envoltorio absorbe la marca)")
chequeo("ADK trabaja con una COPIA del agente (no con el objeto original) al armar el grafo", w is not qd.respondedor_worker)


def yaml_con(demora=0.0, n_subs=3):
    subs = (SUBS * 4)[:n_subs]

    class Lento(ModeloFalso):
        async def generate_content_async(self, llm_request, stream=False):
            await asyncio.sleep(demora)
            async for x in super().generate_content_async(llm_request, stream):
                yield x

    def resp(req):
        ident = re.search(r"\[([A-Z]+-\d+)\]", ultimo_texto(req))
        return json.dumps({"respuesta": "ok", "fuente": ident.group(1) if ident else "sin evidencia"})
    md = ModeloFalso(responder=lambda r_: json.dumps({"sub_preguntas": subs}))
    mr, ms = Lento(responder=resp), ModeloFalso(responder=lambda r_: "SINTESIS")
    qd.respondedor_worker.model = mr          # ANTES de cargar: el grafo trabaja con una copia del agente
    wf = from_config(RUTA)
    nodo(wf, "descomponer").model, nodo(wf, "sintetizador").model = md, ms
    t = time.perf_counter()
    fin = texto_final(correr(wf, PREG, mostrar=False))
    return mr, ms, fin, time.perf_counter() - t, subs


print("== Y2 · comportamiento del YAML con modelos falsos (mismos escenarios que test_grafo.py)")
mr, ms, fin, _, subs = yaml_con(n_subs=3)
chequeo("un respondedor por sub-pregunta", len(mr.llamadas) == 3)
chequeo("cada respondedor recibe 1 solo contenido y no ve la pregunta original",
        all(len(q.contents) == 1 for q in mr.llamadas) and not any(PREG[:40] in t for q in mr.llamadas for t in textos(q)))
payload = json.loads(ultimo_texto(ms.llamadas[0]))
chequeo("el sintetizador recibe las respuestas parciales en orden", [p["fuente"] for p in payload["respuestas_parciales"]] == ["TAR-01", "PLA-02", "FX-04"])
chequeo("la salida final es la del sintetizador", fin == "SINTESIS", repr(fin))
mr, *_ = yaml_con(n_subs=9)
chequeo(f"tope de código: 9 propuestas → {qd.MAX_SUBPREGUNTAS} llamadas", len(mr.llamadas) == qd.MAX_SUBPREGUNTAS, f"{len(mr.llamadas)}")
mr, ms, fin, seg, _ = yaml_con(demora=0.4, n_subs=4)
chequeo("paralelismo real: 4 respondedores de 0,4 s en ~1 llamada", seg < 1.2, f"{seg:.2f} s")

print()
if FALLAS:
    print("FALLARON:", FALLAS); sys.exit(1)
print("Todos los chequeos pasaron")
