"""Pruebas sin LLM real (modelo falso que emite llamadas a herramientas) del arquetipo ReAct.

    python3 test_sin_llm.py
"""
import asyncio
import logging
import sys
import time
import warnings

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)          # ADK loguea con detalle los errores que aquí se provocan a propósito
import react
from modelo_react import ModeloFalsoReAct
from traza import correr_agente, texto_del_modelo

PREG = "Me cobraron dos veces la cuota de mi préstamo. Cuenta C-001."
GUION_OK = [("call", "consultar_movimientos", {"cuenta": "C-001"}), ("call", "consultar_prestamo", {"id_prestamo": "P-77"}),
            ("call", "buscar_politica", {"tema": "cobro duplicado"}),
            ("call", "solicitar_reembolso", {"cuenta": "C-001", "monto_usd": 120, "motivo": "cobro duplicado verificado"}),
            ("text", "Verifiqué el duplicado y abrí la solicitud.")]
FALLAS = []


def chequeo(nombre, ok, detalle=""):
    print(f"  [{'OK ' if ok else 'FALLA'}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    if not ok:
        FALLAS.append(nombre)


def correr(guion, ic="default", tope=None, herramientas=None):
    m = ModeloFalsoReAct(guion=guion)
    react.LOG_CONTEXTO.clear(); react.SOLICITUDES.clear()
    t = time.perf_counter()
    ev, err = asyncio.run(correr_agente(react.crear_agente(modelo=m, include_contents=ic, herramientas=herramientas), PREG, tope))
    return m, ev, err, time.perf_counter() - t


def llamadas_a_herramientas(ev):
    return [p.function_call.name for e in ev if e.content for p in (e.content.parts or []) if p.function_call]


def respuestas_a_herramientas(ev):
    return [p.function_response.response for e in ev if e.content for p in (e.content.parts or []) if p.function_response]


print("== A1 · el bucle: el modelo decide en cada vuelta y ADK ejecuta lo que pide")
m, ev, err, _ = correr(GUION_OK)
chequeo("5 llamadas al modelo (4 herramientas + la respuesta final)", len(m.llamadas) == 5 and err is None, f"{len(m.llamadas)} llamadas")
chequeo("las herramientas se ejecutaron en el orden que pidió el modelo",
        llamadas_a_herramientas(ev) == ["consultar_movimientos", "consultar_prestamo", "buscar_politica", "solicitar_reembolso"])
chequeo("la acción con efecto se ejecutó una vez", len(react.SOLICITUDES) == 1 and react.SOLICITUDES[0]["monto_usd"] == 120)
chequeo("el usuario recibe el texto final del modelo", texto_del_modelo(ev) == "Verifiqué el duplicado y abrí la solicitud.")

print("== A2 · el contexto CRECE en cada vuelta (call + response = 2 contenidos por herramienta)")
prog = [len(r.contents) for r in m.llamadas]
chequeo("progresión de contenidos por llamada al modelo: 1, 3, 5, 7, 9", prog == [1, 3, 5, 7, 9], str(prog))
m2, *_ = correr(GUION_OK, ic="none")
chequeo("include_contents='none' NO cambia esa progresión dentro de la invocación (solo excluye turnos previos)",
        [len(r.contents) for r in m2.llamadas] == [1, 3, 5, 7, 9], str([len(r.contents) for r in m2.llamadas]))

print("== A3 · tope externo: un modelo que nunca termina")
BUCLE = [("call", "consultar_movimientos", {"cuenta": "C-001"})]
m, ev, err, _ = correr(BUCLE, tope=5)
chequeo("con max_llm_calls=5: se lanza LlmCallsLimitExceededError tras 5 llamadas", type(err).__name__ == "LlmCallsLimitExceededError" and len(m.llamadas) == 5, f"{type(err).__name__}, {len(m.llamadas)} llamadas")
chequeo("el usuario NO recibe ningún texto: el llamador debe atrapar la excepción y responder algo", texto_del_modelo(ev) is None)
m, ev, err, seg = correr(BUCLE)
chequeo("SIN tope explícito, el valor por defecto deja pasar 500 llamadas al modelo antes de cortar", type(err).__name__ == "LlmCallsLimitExceededError" and len(m.llamadas) == 500, f"{len(m.llamadas)} llamadas ({seg:.1f} s con modelo falso)")
m, ev, err, _ = correr([("call", "consultar_movimientos", {"cuenta": "C-001"})] * 3 + [("text", "listo")])
chequeo("ADK no detecta llamadas repetidas: las ejecuta las 3 veces", llamadas_a_herramientas(ev) == ["consultar_movimientos"] * 3 and err is None)

print("== A4 · herramientas que fallan")
def consultar_prestamo_roto(id_prestamo: str) -> dict:
    """Devuelve los datos de un préstamo."""
    raise RuntimeError("el servicio de préstamos no responde")
m, ev, err, _ = correr([("call", "consultar_prestamo_roto", {"id_prestamo": "P-77"}), ("text", "No pude consultar.")], herramientas=[consultar_prestamo_roto])
chequeo("una herramienta que LANZA una excepción mata toda la corrida (el modelo nunca ve el error)", isinstance(err, RuntimeError) and len(m.llamadas) == 1 and texto_del_modelo(ev) is None, f"{type(err).__name__}, {len(m.llamadas)} llamada")
m, ev, err, _ = correr([("call", "consultar_prestamo", {"id_prestamo": "P-99"}), ("text", "El préstamo no existe.")])
chequeo("una herramienta que DEVUELVE {'error': …} deja continuar al modelo", err is None and "no existe" in str(respuestas_a_herramientas(ev)[0]) and len(m.llamadas) == 2)
m, ev, err, _ = correr([("call", "borrar_cuenta", {"cuenta": "C-001"}), ("text", "listo")])
chequeo("una herramienta inexistente: ADK devuelve al modelo un error que lista las herramientas disponibles", err is None and "no tool with that name" in str(respuestas_a_herramientas(ev)[0]) and "consultar_movimientos" in str(respuestas_a_herramientas(ev)[0]))
m, ev, err, _ = correr([("call", "consultar_prestamo", {"loan": "P-77"}), ("text", "listo")])
chequeo("argumentos equivocados: ADK devuelve al modelo qué parámetro falta", err is None and "id_prestamo" in str(respuestas_a_herramientas(ev)[0]))

print("== A5 · no hay compuerta: si el modelo pide la acción con efecto sin verificar, se ejecuta")
m, ev, err, _ = correr([("call", "solicitar_reembolso", {"cuenta": "C-002", "monto_usd": 999, "motivo": "porque sí"}), ("text", "Hecho.")])
chequeo("«verificá antes de reembolsar» es solo una instrucción: la acción se ejecutó igual", len(react.SOLICITUDES) == 1 and react.SOLICITUDES[0]["monto_usd"] == 999)

print("== A6 · auditoría: lo que el modelo AFIRMA vs lo que REALMENTE se ejecutó")
react.SOLICITUDES.clear()
chequeo("afirma «he solicitado el reembolso» sin haber llamado a la herramienta → se detecta", react.auditar_respuesta("Verifiqué el duplicado. He solicitado el reembolso de USD 120.") != [])
chequeo("«Se ha generado una solicitud de reembolso» sin ticket → se detecta", react.auditar_respuesta("Se ha generado una solicitud de reembolso por USD 120 a su cuenta.") != [])
chequeo("«Procederé a solicitar el reembolso» sin haberlo hecho (promesa) → se detecta", react.auditar_respuesta("Verifiqué el duplicado. Procederé a solicitar el reembolso de USD 120.") != [])
chequeo("una negación no se marca («no corresponde… no se ha generado…»)", react.auditar_respuesta("No corresponde el reembolso: solo hay un cobro. No se ha generado ninguna solicitud.") == [])
m, ev, err, _ = correr(GUION_OK)
chequeo("si la herramienta SÍ se ejecutó, la misma afirmación no se marca", react.auditar_respuesta("He solicitado el reembolso de USD 120.") == [] and len(react.SOLICITUDES) == 1)

react.LOG_CONTEXTO.clear(); react.SOLICITUDES.clear()
print()
if FALLAS:
    print("FALLARON:", FALLAS); sys.exit(1)
print("Todos los chequeos pasaron (ADK", __import__("google.adk", fromlist=["x"]).__version__, ")")
