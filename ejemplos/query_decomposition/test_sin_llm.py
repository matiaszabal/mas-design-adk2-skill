"""Pruebas sin LLM real ni red (modelo falso). Verifican la ESTRUCTURA y el CONTEXTO del arquetipo.

    python3 test_sin_llm.py      # imprime cada chequeo y termina con código != 0 si alguno falla
"""
import asyncio
import json
import re
import sys
import time

import qd
from modelo_falso import ModeloFalso, textos, ultimo_texto
from traza import correr, salida_final

PREG = "Un cliente Premium envía el equivalente a 1000 USD desde una cuenta en pesos al exterior. ¿Cuánto paga en comisiones?"
SUBS = ["¿Cuál es la comisión de las transferencias internacionales?", "¿Qué bonificación otorga el plan Premium?",
        "¿Qué costo tiene la conversión de moneda?"]
FALLAS = []


def chequeo(nombre: str, ok: bool, detalle: str = ""):
    print(f"  [{'OK ' if ok else 'FALLA'}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    if not ok:
        FALLAS.append(nombre)


def resp_por_fragmento(req):
    ident = re.search(r"\[([A-Z]+-\d+)\]", ultimo_texto(req))
    return json.dumps({"respuesta": "ok", "fuente": ident.group(1) if ident else "sin evidencia"})


def ve_el_plan(req) -> bool:
    """¿El request contiene alguna sub-pregunta AJENA (distinta de la propia)? La transcripción del plan
    llega como JSON con acentos escapados, así que se busca también la versión escapada."""
    todo = " ".join(textos(req))
    propia = re.search(r"SUB-PREGUNTA: (.*?)\n", todo)
    propia = propia.group(1) if propia else ""
    return any(s in todo or json.dumps(s)[1:-1] in todo for s in SUBS if s != propia)


def paralela(n_subs=3, ic="none", demora=0.0):
    subs = (SUBS * 4)[:n_subs]
    md = ModeloFalso(responder=lambda r: json.dumps({"sub_preguntas": subs}))

    class Lento(ModeloFalso):
        async def generate_content_async(self, llm_request, stream=False):
            await asyncio.sleep(demora)
            async for x in super().generate_content_async(llm_request, stream):
                yield x
    mr = Lento(responder=resp_por_fragmento)
    ms = ModeloFalso(responder=lambda r: "SINTESIS")
    d, _, r, y = qd.crear_agentes(include_contents=ic, modelos={"descomponer": md, "respondedor": mr, "sintetizador": ms})
    t = time.perf_counter()
    ev = correr(qd.construir_paralela(d, r, y), PREG, mostrar=False)
    return mr, ms, salida_final(ev), time.perf_counter() - t


print("== P1 · paralela: forma del grafo y aislamiento del contexto (include_contents='none')")
mr, ms, final, _ = paralela(3)
chequeo("un respondedor por sub-pregunta", len(mr.llamadas) == 3, f"{len(mr.llamadas)} llamadas")
chequeo("cada respondedor recibe exactamente 1 contenido (su node_input)", all(len(q.contents) == 1 for q in mr.llamadas))
chequeo("ningún respondedor ve la pregunta original", not any(PREG[:40] in t for q in mr.llamadas for t in textos(q)))
chequeo("ningún respondedor ve el plan (las otras sub-preguntas)", not any(ve_el_plan(q) for q in mr.llamadas))
chequeo("el sintetizador recibe las 3 respuestas parciales con su fuente",
        all(f in ultimo_texto(ms.llamadas[0]) for f in ("TAR-01", "PLA-02", "FX-04")))
chequeo("la salida final es la del sintetizador", final == "SINTESIS", str(final))

print("== P2 · contraste: con include_contents='default' el aislamiento NO es automático (comportamiento de ADK 2.9.1)")
mr2, _, _, _ = paralela(3, ic="default")
chequeo("el respondedor recibe 4 contenidos", all(len(q.contents) == 4 for q in mr2.llamadas), f"{[len(q.contents) for q in mr2.llamadas]}")
chequeo("ve la pregunta original", all(any(PREG[:40] in t for t in textos(q)) for q in mr2.llamadas))
chequeo("ve el plan completo (las otras sub-preguntas)", all(ve_el_plan(q) for q in mr2.llamadas))

print("== P3 · tope de código: el modelo propone 9 sub-preguntas")
mr3, _, _, _ = paralela(9)
chequeo(f"se resuelven a lo sumo MAX_SUBPREGUNTAS={qd.MAX_SUBPREGUNTAS}", len(mr3.llamadas) == qd.MAX_SUBPREGUNTAS, f"{len(mr3.llamadas)} llamadas")

print("== P4 · paralelismo real: 4 respondedores de 0,4 s cada uno")
_, _, _, seg = paralela(4, demora=0.4)
chequeo("el tiempo total es ~1 llamada, no la suma", seg < 1.2, f"{seg:.2f} s (serial serían ≥1,6 s)")


def secuencial(terminar_en=None):
    """terminar_en=None: el modelo NUNCA dice terminar. terminar_en=k: dice terminar en la llamada k."""
    n = {"i": 0}
    subs = ["¿Qué plan tiene el cliente C-001?", "¿Qué bonificación otorga el plan Premium?",
            "¿Cuál es la comisión de las transferencias internacionales?", "¿Qué costo tiene la conversión de moneda?",
            "¿Cuál es la comisión de las transferencias nacionales?"]

    def sig(req):
        n["i"] += 1
        if terminar_en is not None and n["i"] >= terminar_en:
            return json.dumps({"terminar": True, "sub_pregunta": ""})
        return json.dumps({"terminar": False, "sub_pregunta": subs[(n["i"] - 1) % len(subs)]})
    msig, mr, ms = ModeloFalso(responder=sig), ModeloFalso(responder=resp_por_fragmento), ModeloFalso(responder=lambda r: "SINTESIS")
    _, s, r, y = qd.crear_agentes(modelos={"siguiente": msig, "respondedor": mr, "sintetizador": ms})
    correr(qd.construir_secuencial(s, r, y), "¿Cuánto paga de comisión internacional el cliente C-001?", mostrar=False)
    return msig, mr, ms


print("== S1 · secuencial: el modelo nunca dice 'terminar' → corta el código")
msig, mr, ms = secuencial(None)
chequeo(f"corta en MAX_PASOS={qd.MAX_PASOS}", len(mr.llamadas) == qd.MAX_PASOS and len(msig.llamadas) == qd.MAX_PASOS,
        f"{len(msig.llamadas)} pedidos, {len(mr.llamadas)} respuestas")
chequeo("el sintetizador es informado de que fue por tope", '"motivo_fin": "tope"' in ultimo_texto(ms.llamadas[0]))

print("== S2 · secuencial: el modelo termina en la 3ª llamada")
msig, mr, ms = secuencial(3)
chequeo("se resuelven 2 sub-preguntas", len(mr.llamadas) == 2, f"{len(mr.llamadas)}")
chequeo("motivo de fin = completo", '"motivo_fin": "completo"' in ultimo_texto(ms.llamadas[0]))
chequeo("la 2ª petición 'siguiente' lleva el hecho previo en su node_input", "CLI-05" in ultimo_texto(msig.llamadas[1]))
chequeo("cada respondedor recibe 1 solo contenido", all(len(q.contents) == 1 for q in mr.llamadas))

print()
if FALLAS:
    print("FALLARON:", FALLAS)
    sys.exit(1)
print("Todos los chequeos pasaron (ADK", __import__("google.adk", fromlist=["x"]).__version__, ")")
