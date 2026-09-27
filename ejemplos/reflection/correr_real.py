"""Corrida REAL con Gemini (Vertex AI). Solo invocación de modelo; datos sintéticos (ver refl.py).

    export GOOGLE_GENAI_USE_VERTEXAI=TRUE GOOGLE_CLOUD_PROJECT=<proyecto> GOOGLE_CLOUD_LOCATION=us-central1
    python3 correr_real.py [none|default] [python|yaml]    # yaml: carga yaml_reflection/root_agent.yaml
"""
import sys
import time

import refl
from traza import correr, salida_final

ic = sys.argv[1] if len(sys.argv) > 1 else "none"
origen = sys.argv[2] if len(sys.argv) > 2 else "python"
if origen == "yaml":
    import warnings
    warnings.filterwarnings("ignore")
    from google.adk.agents.config_agent_utils import from_config
    wf = from_config("yaml_reflection/root_agent.yaml")     # el YAML fija include_contents="none"
else:
    g, c = refl.crear_agentes(include_contents=ic)
    wf = refl.construir(g, c)
print(f"### reflection · origen={origen} · modelo={refl.MODEL} · include_contents={ic!r}\nPEDIDO: {refl.PEDIDO}\n")
t = time.perf_counter()
ev = correr(wf, refl.PEDIDO, mostrar=False)
for e in ev:
    out = getattr(e, "output", None)
    nombre = e.node_info.path.rsplit("/", 1)[-1] if getattr(e, "node_info", None) else "?"
    if not nombre.startswith(("generador", "validar", "critico", "decidir", "publicar", "escalar")):
        continue
    if out is None:                                    # los agentes LLM dejan su texto en `content`
        cont = getattr(e, "content", None)
        out = "".join(p.text or "" for p in (cont.parts or [])) if cont else None
    if out is None:
        continue
    ruta = getattr(getattr(e, "actions", None), "route", None)
    print(f"[{nombre}] {'route=' + str(ruta) + ' ' if ruta else ''}{str(out)[:600]}\n")
final = salida_final(ev)
val = refl.validar_texto(final.get("respuesta") or final.get("ultimo_borrador") or "")
print(f"tiempo total: {time.perf_counter() - t:.1f} s")
print("contexto recibido por llamada (agente, n_contents):", [(e['agente'], e['n_contents']) for e in refl.LOG_CONTEXTO])
print(f"RESULTADO: estado={final.get('estado')} rondas={final.get('rondas')} | ¿el texto final pasa el validador? {'SÍ' if val['ok'] else 'NO ' + str(val['fallas'])}")
