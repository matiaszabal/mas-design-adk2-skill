"""Corrida REAL con Gemini (Vertex AI). Solo invocación de modelo; datos sintéticos (ver kb.py).

    export GOOGLE_GENAI_USE_VERTEXAI=TRUE GOOGLE_CLOUD_PROJECT=<proyecto> GOOGLE_CLOUD_LOCATION=us-central1
    python3 correr_real.py paralela|secuencial|grafo|yaml_grafo [none|default]
"""
import sys
import time

import qd
from traza import correr, texto_final

PREG_PAR = "Un cliente Premium envía el equivalente a 1000 USD desde una cuenta en pesos al exterior. ¿Cuánto paga en comisiones?"
ESPERADO_PAR = "19,5"        # 50% de 15 USD (=7,5) + spread 1,2% de 1000 USD (=12)
PREG_SEC = "¿Cuánto paga de comisión fija por una transferencia internacional el cliente C-001?"
ESPERADO_SEC = "7,5"         # C-001 es Premium (50%) sobre 15 USD

variante = sys.argv[1] if len(sys.argv) > 1 else "paralela"
ic = sys.argv[2] if len(sys.argv) > 2 else "none"
if variante == "yaml_grafo":
    import warnings
    warnings.filterwarnings("ignore")
    from google.adk.agents.config_agent_utils import from_config
    wf, preg, esp = from_config("yaml_qd_grafo/root_agent.yaml"), PREG_PAR, ESPERADO_PAR     # el YAML fija include_contents="none"
else:
    d, s, r, y = qd.crear_agentes(include_contents=ic, respondedor_paralelo=(variante == "grafo"))
    wf, preg, esp = {"paralela": (qd.construir_paralela(d, r, y), PREG_PAR, ESPERADO_PAR),
                     "grafo": (qd.construir_paralela_grafo(d, r, y), PREG_PAR, ESPERADO_PAR),
                     "secuencial": (qd.construir_secuencial(s, r, y), PREG_SEC, ESPERADO_SEC)}[variante]
print(f"### {variante} · modelo={qd.MODEL} · include_contents={ic!r}\nPREGUNTA: {preg}\n")
t = time.perf_counter()
ev = correr(wf, preg)
final = texto_final(ev)
import json
parciales = [e.output for e in ev if isinstance(getattr(e, "output", None), list) and e.output and isinstance(e.output[0], dict)]
hechos = [e.output["hechos"] for e in ev if isinstance(getattr(e, "output", None), dict) and "hechos" in e.output]
for e in ev:                                          # variante de grafo puro: `juntar` emite un JSON con las parciales
    o = getattr(e, "output", None)
    if isinstance(o, str) and '"respuestas_parciales"' in o:
        parciales = [json.loads(o)["respuestas_parciales"]]
for etiqueta, dato in (("respuestas parciales", parciales[-1] if parciales else None), ("hechos (secuencial)", hechos[-1] if hechos else None)):
    if dato:
        print(f"\n{etiqueta}:")
        for x in dato:
            print(f"  - {x['sub_pregunta']}\n      → {x['respuesta']}  [{x['fuente']}]")
print(f"\nRESPUESTA FINAL:\n{final}\n")
print(f"tiempo total: {time.perf_counter() - t:.1f} s")
print("contexto recibido por cada llamada al modelo (agente, n_contents, roles):")
for e in qd.LOG_CONTEXTO:
    print(f"  {e['agente']:<13} n={e['n_contents']} {e['roles']}")
ok = esp.replace(",", ".") in str(final).replace(",", ".")
print(f"\n¿contiene el resultado esperado ({esp} USD)? {'SÍ' if ok else 'NO'}")
