"""Variante PARALELA como grafo puro (LlmAgent con parallel_worker=True) — sin LLM real (modelo falso).

    python3 test_grafo.py
"""
import asyncio
import json
import re
import sys
import time

import qd
from modelo_falso import ModeloFalso, textos, ultimo_texto
from traza import correr, texto_final

PREG = "Un cliente Premium envía el equivalente a 1000 USD desde una cuenta en pesos al exterior. ¿Cuánto paga en comisiones?"
SUBS = ["¿Cuál es la comisión de las transferencias internacionales?", "¿Qué bonificación otorga el plan Premium?",
        "¿Qué costo tiene la conversión de moneda?"]
FALLAS = []


def chequeo(nombre, ok, detalle=""):
    print(f"  [{'OK ' if ok else 'FALLA'}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    if not ok:
        FALLAS.append(nombre)


def resp(req):
    ident = re.search(r"\[([A-Z]+-\d+)\]", ultimo_texto(req))
    return json.dumps({"respuesta": "ok", "fuente": ident.group(1) if ident else "sin evidencia"})


def grafo(n_subs=3, demora=0.0):
    subs = (SUBS * 4)[:n_subs]

    class Lento(ModeloFalso):
        async def generate_content_async(self, llm_request, stream=False):
            await asyncio.sleep(demora)
            async for x in super().generate_content_async(llm_request, stream):
                yield x
    md = ModeloFalso(responder=lambda r: json.dumps({"sub_preguntas": subs}))
    mr, ms = Lento(responder=resp), ModeloFalso(responder=lambda r: "SINTESIS")
    d, _, r, y = qd.crear_agentes(modelos={"descomponer": md, "respondedor": mr, "sintetizador": ms}, respondedor_paralelo=True)
    t = time.perf_counter()
    ev = correr(qd.construir_paralela_grafo(d, r, y), PREG, mostrar=False)
    return mr, ms, texto_final(ev), time.perf_counter() - t, subs


print("== G1 · grafo puro: forma, aislamiento y orden")
mr, ms, fin, _, subs = grafo(3)
chequeo("un respondedor por sub-pregunta (fan-out por parallel_worker)", len(mr.llamadas) == 3, f"{len(mr.llamadas)} llamadas")
chequeo("cada respondedor recibe 1 solo contenido", all(len(q.contents) == 1 for q in mr.llamadas), str([len(q.contents) for q in mr.llamadas]))
chequeo("ningún respondedor ve la pregunta original", not any(PREG[:40] in t for q in mr.llamadas for t in textos(q)))
payload = json.loads(ultimo_texto(ms.llamadas[0]))
chequeo("el sintetizador recibe las respuestas parciales en el orden de las sub-preguntas",
        [p["sub_pregunta"] for p in payload["respuestas_parciales"]] == subs and [p["fuente"] for p in payload["respuestas_parciales"]] == ["TAR-01", "PLA-02", "FX-04"],
        str([p["fuente"] for p in payload["respuestas_parciales"]]))
chequeo("la pregunta original llega al sintetizador por el estado", payload["pregunta"] == PREG)
chequeo("la salida final es la del sintetizador", fin == "SINTESIS")

print("== G2 · tope de código: el modelo propone 9 sub-preguntas")
mr, *_ = grafo(9)
chequeo(f"se resuelven a lo sumo MAX_SUBPREGUNTAS={qd.MAX_SUBPREGUNTAS}", len(mr.llamadas) == qd.MAX_SUBPREGUNTAS, f"{len(mr.llamadas)} llamadas")

print("== G3 · paralelismo real de un LlmAgent con parallel_worker=True: 4 respondedores de 0,4 s")
*_, seg, _ = grafo(4, demora=0.4)
chequeo("el tiempo total es ~1 llamada, no la suma", seg < 1.2, f"{seg:.2f} s (serial: ≥1,6 s)")

print()
if FALLAS:
    print("FALLARON:", FALLAS); sys.exit(1)
print("Todos los chequeos pasaron")
