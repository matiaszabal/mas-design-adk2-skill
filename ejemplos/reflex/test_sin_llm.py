"""Pruebas sin LLM real (modelo falso) del arquetipo Reflex.

    python3 test_sin_llm.py
"""
import json
import sys
import warnings

warnings.filterwarnings("ignore")
from google.adk import Event, Workflow
from google.adk.workflow import DEFAULT_ROUTE, START, node

import reflex
from modelo_falso import ModeloFalso, textos
from traza import correr, salida_final

FALLAS = []


def chequeo(nombre, ok, detalle=""):
    print(f"  [{'OK ' if ok else 'FALLA'}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    if not ok:
        FALLAS.append(nombre)


def con_modelo(intencion, confianza):
    m = ModeloFalso(responder=lambda r: json.dumps({"intencion": intencion, "confianza": confianza}))
    reflex.LOG_CONTEXTO.clear()
    ev = correr(reflex.construir(reflex.crear_clasificador(modelo=m)), "mensaje de prueba", mostrar=False)
    return m, ev, salida_final(ev)


print("== R1 · una pasada: cada intención inequívoca va a su cola con UNA sola llamada al modelo")
for intencion, cola, prio in (("tarjetas", "tarjetas", "normal"), ("prestamos", "prestamos", "normal"), ("fraude", "fraude", "alta")):
    m, ev, fin = con_modelo(intencion, "alta")
    chequeo(f"{intencion} → cola {cola} (prioridad {prio}), 1 llamada, 1 contenido",
            fin["cola"] == cola and fin["prioridad"] == prio and len(m.llamadas) == 1 and len(m.llamadas[0].contents) == 1,
            f"{len(m.llamadas)} llamada(s), {len(m.llamadas[0].contents)} contenido(s)")
chequeo("sin bucle: cada nodo se ejecutó una sola vez", all(e.node_info.path.endswith("@1") for e in ev if e.node_info and e.output is not None),
        str(sorted({e.node_info.path.rsplit('/', 1)[-1] for e in ev if e.node_info})))

print("== R2 · ruta de escape: lo que el modelo no afirma con seguridad va a un humano")
for intencion, confianza in (("tarjetas", "baja"), ("fraude", "media"), ("otro", "alta")):
    m, ev, fin = con_modelo(intencion, confianza)
    chequeo(f"({intencion}, confianza {confianza}) → humano", fin["cola"] == "humano" and "no clasificable" in fin["motivo"], fin.get("motivo", "")[:60])

print("== R3 · el mensaje llega intacto a la cola (por el estado)")
m, ev, fin = con_modelo("fraude", "alta")
chequeo("la cola recibe el mensaje original", fin["mensaje"] == "mensaje de prueba")

print("== R4 · DEFAULT_ROUTE: una ruta inesperada no se pierde")


@node
def raro(ctx, node_input):
    yield Event(output="x", route="cripto")           # una ruta que nadie mapeó
ctx_state = {}
wf = Workflow(name="t", edges=[(START, reflex.iniciar, raro), (raro, reflex._destinos())])
fin = salida_final(correr(wf, "hola", mostrar=False))
chequeo("con la ruta por defecto: va al escape", fin and fin["cola"] == "humano", str(fin)[:60])
d = reflex._destinos(); d.pop(DEFAULT_ROUTE)
wf2 = Workflow(name="t2", edges=[(START, reflex.iniciar, raro), (raro, d)])
ev2 = correr(wf2, "hola", mostrar=False)
llego = [e for e in ev2 if e.output is not None and isinstance(e.output, dict) and "cola" in e.output]
chequeo("SIN ruta por defecto: la rama termina EN SILENCIO (nadie recibe nada)", not llego, "0 colas recibieron el mensaje")

print("== R5 · variante SIN LLM (reglas): mismas rutas y mismo escape, 0 llamadas al modelo")
casos = [("Me clonaron la tarjeta", "fraude"), ("Quiero bloquear mi tarjeta", "tarjetas"), ("¿Cuánto me queda de cuota del préstamo?", "prestamos"),
         ("Hola, ¿qué hora es?", "humano"), ("Perdí la tarjeta y quiero saber la cuota del préstamo", "humano")]
for msg, esperado in casos:
    fin = salida_final(correr(reflex.construir_reglas(), msg, mostrar=False))
    chequeo(f"«{msg[:42]}» → {esperado}", fin["cola"] == esperado, fin["cola"])

reflex.LOG_CONTEXTO.clear()
print()
if FALLAS:
    print("FALLARON:", FALLAS); sys.exit(1)
print("Todos los chequeos pasaron (ADK", __import__("google.adk", fromlist=["x"]).__version__, ")")
