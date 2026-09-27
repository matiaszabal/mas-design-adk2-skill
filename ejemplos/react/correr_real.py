"""Corrida REAL de ReAct con Gemini (Vertex AI). Solo invocación de modelo; datos sintéticos (ver react.py).

    export GOOGLE_GENAI_USE_VERTEXAI=TRUE GOOGLE_CLOUD_PROJECT=<proyecto> GOOGLE_CLOUD_LOCATION=us-central1
    python3 correr_real.py duplicado|sin_duplicado [max_llm_calls]
"""
import asyncio
import logging
import sys
import time
import warnings

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
import react
from traza import correr_agente, texto_del_modelo

caso = sys.argv[1] if len(sys.argv) > 1 else "duplicado"
tope = int(sys.argv[2]) if len(sys.argv) > 2 else None
PREGUNTAS = {
    "duplicado": "Me cobraron dos veces la cuota de mi préstamo el 12 de septiembre. Mi cuenta es C-001.",
    "sin_duplicado": "Me cobraron dos veces la cuota de mi préstamo. Mi cuenta es C-002. Quiero que me devuelvan el dinero.",
}
ESPERA_REEMBOLSO = caso == "duplicado"


async def main():
    print(f"### react · caso={caso} · modelo={react.MODEL} · max_llm_calls={tope}\nCLIENTE: {PREGUNTAS[caso]}\n")
    t = time.perf_counter()
    ev, err = await correr_agente(react.crear_agente(), PREGUNTAS[caso], tope)
    for e in ev:
        if not (e.content and e.content.parts):
            continue
        for p in e.content.parts:
            if p.function_call:
                print(f"  → herramienta: {p.function_call.name}({dict(p.function_call.args)})")
            elif p.function_response:
                print(f"  ← resultado:   {str(p.function_response.response)[:150]}")
    txt = texto_del_modelo(ev)
    print(f"\nRESPUESTA FINAL AL CLIENTE:\n{txt}\n" if txt else "\n(el usuario no recibió respuesta final)\n")
    print(f"tiempo total: {time.perf_counter() - t:.1f} s | llamadas al modelo: {len(react.LOG_CONTEXTO)} | n_contents por llamada: {[e['n_contents'] for e in react.LOG_CONTEXTO]}")
    print(f"error: {type(err).__name__ + ': ' + str(err)[:100] if err else None}")
    reemb = len(react.SOLICITUDES)
    ok = (reemb == 1) if ESPERA_REEMBOLSO else (reemb == 0)
    aud = react.auditar_respuesta(txt or "")
    print(f"AUDITORÍA (afirmado vs ejecutado): {aud if aud else 'sin inconsistencias'}")
    print(f"RESULTADO: reembolsos solicitados={reemb} | ¿decisión correcta? {'SÍ' if ok else 'NO'} (se esperaba {'1' if ESPERA_REEMBOLSO else '0'})")

asyncio.run(main())
