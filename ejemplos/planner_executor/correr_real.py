"""Corrida REAL con Gemini (Vertex AI) como planner. Solo invocación de modelo; datos sintéticos (ver pe.py).

    export GOOGLE_GENAI_USE_VERTEXAI=TRUE GOOGLE_CLOUD_PROJECT=<proyecto> GOOGLE_CLOUD_LOCATION=us-central1
    python3 correr_real.py julio|agosto [hitl]     # hitl: pausa con RequestInput y aprueba automáticamente
"""
import asyncio
import sys
import time
import warnings

warnings.filterwarnings("ignore")
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.workflow.utils._workflow_hitl_utils import create_request_input_response, get_request_input_interrupt_ids
from google.genai import types

import pe

periodo = sys.argv[1] if len(sys.argv) > 1 else "julio"
hitl = len(sys.argv) > 2 and sys.argv[2] == "hitl"
pe.APROBACION_HUMANA = hitl
OBJ = f"Conciliar los movimientos internos y el extracto bancario de 2026-{'07' if periodo == 'julio' else '08'} y redactar el informe de diferencias."


def mostrar(e):
    nombre = e.node_info.path.rsplit("/", 1)[-1] if getattr(e, "node_info", None) else "?"
    if not nombre.startswith(("planner", "validar_plan", "ejecutar", "decidir_falla", "informar", "escalar")):
        return
    out = getattr(e, "output", None)
    if out is None and getattr(e, "content", None) and e.content.parts:
        out = "".join(p.text or "" for p in e.content.parts)
    if out is None:
        return
    ruta = getattr(getattr(e, "actions", None), "route", None)
    print(f"[{nombre}] {'route=' + str(ruta) + ' ' if ruta else ''}{str(out)[:520]}\n")


async def main():
    print(f"### planner-executor · {periodo} · modelo={pe.MODEL} · aprobación humana={hitl}\nOBJETIVO: {OBJ}\n")
    runner = Runner(node=pe.construir(pe.crear_planner()), app_name="pe", session_service=InMemorySessionService(), auto_create_session=True)
    t = time.perf_counter()
    msg, final, pausas = types.Content(role="user", parts=[types.Part(text=OBJ)]), None, 0
    while True:
        evs = []
        async for e in runner.run_async(user_id="u", session_id="s", new_message=msg):
            evs.append(e); mostrar(e)
        ids = [i for e in evs for i in get_request_input_interrupt_ids(e)]
        outs = [e.output for e in evs if getattr(e, "output", None) is not None]
        if not ids:
            final = outs[-1] if outs else None
            break
        pausas += 1
        print(f"*** PAUSA #{pausas}: el flujo espera aprobación humana (herramientas ejecutadas hasta ahora: {len(pe.LLAMADAS_HERRAMIENTAS)}) → se responde «aprobar»\n")
        msg = types.Content(role="user", parts=[create_request_input_response(ids[0], {"result": "aprobar"})])
    print(f"tiempo total: {time.perf_counter() - t:.1f} s")
    print("contexto del planner por llamada (n_contents):", [e["n_contents"] for e in pe.LOG_CONTEXTO])
    ok = isinstance(final, dict) and final.get("estado") == "COMPLETADO" and "M3" in str(final.get("informe")) and "B9" in str(final.get("informe"))
    print(f"RESULTADO: {final.get('estado') if isinstance(final, dict) else final} | replanificaciones={final.get('replanificaciones') if isinstance(final, dict) else '?'} | pausas={pausas} | ¿informe correcto (M3 y B9)? {'SÍ' if ok else 'NO'}")

asyncio.run(main())
