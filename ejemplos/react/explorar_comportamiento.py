"""Qué hace ADK 2.9.1 con un LlmAgent con herramientas (bucle ReAct), medido con un modelo falso (sin red ni costo).

    python3 explorar_comportamiento.py
"""
import asyncio
import logging
import time
import warnings

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)      # ADK loguea con detalle los errores que aquí se provocan a propósito
import react
from modelo_react import ModeloFalsoReAct
from traza import correr_agente, texto_del_modelo

PREG = "Me cobraron dos veces la cuota de mi préstamo. Cuenta C-001."
GUION_OK = [("call", "consultar_movimientos", {"cuenta": "C-001"}), ("call", "consultar_prestamo", {"id_prestamo": "P-77"}),
            ("call", "buscar_politica", {"tema": "cobro duplicado"}),
            ("call", "solicitar_reembolso", {"cuenta": "C-001", "monto_usd": 120, "motivo": "cobro duplicado verificado"}),
            ("text", "Verifiqué el duplicado y abrí la solicitud.")]


def correr(guion, ic="default", tope=None, herramientas=None):
    m = ModeloFalsoReAct(guion=guion)
    react.LOG_CONTEXTO.clear(); react.SOLICITUDES.clear()
    t = time.perf_counter()
    ev, err = asyncio.run(correr_agente(react.crear_agente(modelo=m, include_contents=ic, herramientas=herramientas), PREG, tope))
    return m, ev, err, time.perf_counter() - t


print("== 1) progresión del contexto por vuelta del modelo")
for ic in ("default", "none"):
    m, ev, err, _ = correr(GUION_OK, ic)
    print(f"   include_contents={ic!r:9} llamadas al modelo={len(m.llamadas)}  n_contents por llamada={[len(r.contents) for r in m.llamadas]}  "
          f"solicitudes={len(react.SOLICITUDES)}  texto final={texto_del_modelo(ev)!r}  error={type(err).__name__ if err else None}")

print("== 2) tope externo: un modelo que NUNCA termina (siempre pide una herramienta)")
BUCLE = [("call", "consultar_movimientos", {"cuenta": "C-001"})]
for tope in (5, None):
    m, ev, err, seg = correr(BUCLE, tope=tope)
    print(f"   max_llm_calls={tope!r:5} → llamadas al modelo={len(m.llamadas)}  error={type(err).__name__ if err else None}: {str(err)[:90] if err else ''}  ({seg:.1f} s)")
    print(f"       ¿el usuario recibió algún texto final? {texto_del_modelo(ev)!r}")

print("== 3) una herramienta que LANZA una excepción")
def consultar_prestamo_roto(id_prestamo: str) -> dict:
    """Devuelve los datos de un préstamo."""
    raise RuntimeError("el servicio de préstamos no responde")
GUION_ERR = [("call", "consultar_prestamo_roto", {"id_prestamo": "P-77"}), ("text", "No pude consultar el préstamo.")]
m, ev, err, _ = correr(GUION_ERR, herramientas=[consultar_prestamo_roto])
print(f"   llamadas al modelo={len(m.llamadas)}  error propagado={type(err).__name__ if err else None}: {str(err)[:80] if err else ''}  texto final={texto_del_modelo(ev)!r}")

print("== 4) el modelo llama a una herramienta que NO existe")
m, ev, err, _ = correr([("call", "borrar_cuenta", {"cuenta": "C-001"}), ("text", "listo")])
resp4 = [p.function_response.response for e in ev for p in (e.content.parts if e.content else []) if p.function_response]
print(f"   llamadas al modelo={len(m.llamadas)}  error={type(err).__name__ if err else None}  respuesta que recibió el modelo={str(resp4)[:170]}")

print("== 5) el modelo llama a una herramienta con argumentos equivocados")
m, ev, err, _ = correr([("call", "consultar_prestamo", {"loan": "P-77"}), ("text", "listo")])
resp = [p.function_response.response for e in ev for p in (e.content.parts if e.content else []) if p.function_response]
print(f"   llamadas al modelo={len(m.llamadas)}  error={type(err).__name__ if err else None}  respuesta que recibió el modelo={str(resp)[:140]}")
