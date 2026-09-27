"""Pruebas sin LLM real (modelo falso solo para el planner) del arquetipo Planner-Executor.

    python3 test_sin_llm.py
"""
import asyncio
import json
import sys
import time
import warnings

warnings.filterwarnings("ignore")
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.workflow.utils._workflow_hitl_utils import create_request_input_response, get_request_input_interrupt_ids
from google.genai import types

import pe
from modelo_falso import ModeloFalso
from traza import correr, salida_final

FALLAS = []


def chequeo(nombre, ok, detalle=""):
    print(f"  [{'OK ' if ok else 'FALLA'}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    if not ok:
        FALLAS.append(nombre)


def P(*pasos):
    return json.dumps({"pasos": [{"id": i, "herramienta": h, "entradas": e, "parametro": p} for i, h, e, p in pasos]})


PLAN_JULIO = P((1, "extraer_movimientos_internos", [], "2026-07"), (2, "extraer_extracto_banco", [], "2026-07"),
               (3, "cruzar", [1, 2], ""), (4, "listar_diferencias", [3], ""), (5, "redactar_informe", [4], ""))
PLAN_AGOSTO = PLAN_JULIO.replace("2026-07", "2026-08")
PLAN_REPLAN = P((6, "extraer_extracto_banco", [], "2026-08;alt"), (7, "cruzar", [1, 6], ""), (8, "listar_diferencias", [7], ""),
                (9, "redactar_informe", [8], ""))
INVALIDO = P((1, "borrar_todo", [], ""), (2, "cruzar", [1], ""))
OBJ_JULIO = "Conciliar los movimientos internos y el extracto bancario de 2026-07 y redactar el informe de diferencias."
OBJ_AGOSTO = OBJ_JULIO.replace("2026-07", "2026-08")


def reset():
    pe.LLAMADAS_HERRAMIENTAS.clear(); pe.LOG_CONTEXTO.clear()
    pe.APROBACION_HUMANA, pe.DEMORA = False, 0.0


def planner_falso(planes, ic="none"):
    n = {"i": 0}

    def resp(req):
        p = planes[min(n["i"], len(planes) - 1)]; n["i"] += 1; return p
    m = ModeloFalso(responder=resp)
    return m, pe.crear_planner(modelo=m, include_contents=ic)


def sysinst(req):
    return str(getattr(req.config, "system_instruction", "") or "")


def correr_pe(planes, objetivo=OBJ_JULIO, ic="none"):
    reset()
    m, pl = planner_falso(planes, ic)
    t = time.perf_counter()
    fin = salida_final(correr(pe.construir(pl), objetivo, mostrar=False))
    return m, fin, time.perf_counter() - t


print("== reglas deterministas del plan (unitarias)")
def problemas(plan_json, hechos=frozenset()):
    return pe.validar_reglas(pe.plan_de(plan_json), set(hechos))
chequeo("un plan correcto no tiene problemas", problemas(PLAN_JULIO) == [])
chequeo("herramienta desconocida y aridad incorrecta", len(problemas(INVALIDO)) >= 2, str(problemas(INVALIDO))[:80])
chequeo("dependencia hacia adelante", any("no es un paso anterior" in x for x in problemas(P((1, "cruzar", [2, 3], ""), (2, "extraer_extracto_banco", [], "x"), (3, "extraer_movimientos_internos", [], "x")))))
chequeo("más de MAX_PASOS", any("máximo" in x for x in problemas(P(*[(i, "extraer_movimientos_internos", [], "x") for i in range(1, pe.MAX_PASOS + 2)]))))
chequeo("una entrada puede ser un paso ya completado", problemas(P((6, "cruzar", [1, 5], "")), hechos={1, 5}) == [])

print("== T1 · camino feliz (2026-07)")
m, fin, _ = correr_pe([PLAN_JULIO])
chequeo("COMPLETADO sin replanificar", fin.get("estado") == "COMPLETADO" and fin.get("replanificaciones") == 0, str(fin)[:90])
chequeo("ejecutó los 5 pasos en orden de dependencias", fin.get("pasos") == [1, 2, 3, 4, 5])
chequeo("el informe menciona las dos diferencias reales (M3 y B9)", "M3" in fin["informe"] and "B9" in fin["informe"], fin["informe"])
chequeo("el planner se llamó una sola vez", len(m.llamadas) == 1)

print("== T2 · cada paso ve SOLO su parámetro y las salidas de sus dependencias")
por = {}
for nombre, ni in pe.LLAMADAS_HERRAMIENTAS:
    por[nombre] = ni
chequeo("las herramientas reciben solo {parametro, entradas}", all(set(ni) == {"parametro", "entradas"} for _, ni in pe.LLAMADAS_HERRAMIENTAS))
chequeo("cruzar recibe exactamente las salidas de los pasos 1 y 2", por["cruzar"]["entradas"] == [pe.INTERNOS, pe.EXTRACTO])
chequeo("los pasos sin dependencias reciben entradas vacías", por["extraer_movimientos_internos"]["entradas"] == [] and por["extraer_extracto_banco"]["entradas"] == [])
chequeo("el objetivo no llega a ningún paso", not any(pe.texto_de(OBJ_JULIO)[:30] in json.dumps(ni) for _, ni in pe.LLAMADAS_HERRAMIENTAS))

print("== T3 · pasos independientes en paralelo (4 oleadas × 0,4 s; serial serían 5 × 0,4 s)")
reset(); pe.DEMORA = 0.4
m, pl = planner_falso([PLAN_JULIO])
t = time.perf_counter(); correr(pe.construir(pl), OBJ_JULIO, mostrar=False); seg = time.perf_counter() - t
chequeo("el tiempo total es ~4 oleadas, no 5 pasos", seg < 1.85, f"{seg:.2f} s")

print("== T4 · replanificación: agosto falla en el extracto; el replan conserva lo ya hecho")
m, fin, _ = correr_pe([PLAN_AGOSTO, PLAN_REPLAN], OBJ_AGOSTO)
chequeo("COMPLETADO tras 1 replanificación", fin.get("estado") == "COMPLETADO" and fin.get("replanificaciones") == 1, str(fin)[:100])
chequeo("no repitió el paso ya hecho (movimientos internos: 1 sola llamada)", [n for n, _ in pe.LLAMADAS_HERRAMIENTAS].count("extraer_movimientos_internos") == 1)
chequeo("el paso 1 se reutilizó como entrada del nuevo cruce", 1 in fin.get("pasos") and 6 in fin.get("pasos"), str(fin.get("pasos")))
req2 = m.llamadas[1]
chequeo("el planner de la 2ª vuelta recibe el error, lo ya hecho y el id siguiente",
        "formato de extracto no soportado" in sysinst(req2) and "1 = extraer_movimientos_internos" in sysinst(req2) and "comienzan" not in "" and "6" in sysinst(req2))
chequeo("el planner ve 1 solo contenido en ambas vueltas", [len(r.contents) for r in m.llamadas] == [1, 1], str([len(r.contents) for r in m.llamadas]))

print("== T5 · tope: el planner insiste con el plan que falla")
m, fin, _ = correr_pe([PLAN_AGOSTO], OBJ_AGOSTO)
chequeo("escala a un humano tras MAX_REPLANES", fin.get("estado") == "ESCALADO A HUMANO" and len(m.llamadas) == pe.MAX_REPLANES + 1, f"{len(m.llamadas)} llamadas al planner")
chequeo("informa lo hecho y lo pendiente", fin.get("hecho") == [1] and bool(fin.get("pendiente")), f"hecho={fin.get('hecho')}")
chequeo("el historial conserva el ERROR ORIGINAL de la herramienta (no solo el último rechazo del plan)",
        any("formato de extracto no soportado" in x for x in fin.get("historial_de_fallas", [])), f"{len(fin.get('historial_de_fallas', []))} fallas registradas")

print("== T6 · plan inválido: se rechaza ANTES de ejecutar y se replanifica")
m, fin, _ = correr_pe([INVALIDO, PLAN_JULIO])
chequeo("COMPLETADO tras 1 replanificación", fin.get("estado") == "COMPLETADO" and fin.get("replanificaciones") == 1)
chequeo("el plan inválido no ejecutó ninguna herramienta ('borrar_todo' no existe)", len(pe.LLAMADAS_HERRAMIENTAS) == 5)
chequeo("el planner recibió el motivo del rechazo", "herramienta desconocida" in sysinst(m.llamadas[1]))

print("== T7 · aprobación humana con RequestInput (pausa y reanudación)")


async def hitl(planes, respuestas):
    reset(); pe.APROBACION_HUMANA = True
    m, pl = planner_falso(planes)
    runner = Runner(node=pe.construir(pl), app_name="pe", session_service=InMemorySessionService(), auto_create_session=True)
    turnos = []

    async def turno(msg):
        evs = [e async for e in runner.run_async(user_id="u", session_id="s", new_message=msg)]
        ids = [i for e in evs for i in get_request_input_interrupt_ids(e)]
        turnos.append({"pausa": bool(ids), "id": ids[0] if ids else None, "final": salida_final(evs) if not ids else None,
                       "herramientas": len(pe.LLAMADAS_HERRAMIENTAS), "planner": len(m.llamadas)})
        return ids
    ids = await turno(types.Content(role="user", parts=[types.Part(text=OBJ_JULIO)]))
    for r in respuestas:
        if not ids:
            break
        ids = await turno(types.Content(role="user", parts=[create_request_input_response(ids[0], {"result": r})]))
    return turnos, m


turnos, m = asyncio.run(hitl([PLAN_JULIO], ["aprobar"]))
chequeo("el flujo se PAUSA antes de ejecutar: 0 herramientas ejecutadas", turnos[0]["pausa"] and turnos[0]["herramientas"] == 0, str(turnos[0]))
chequeo("al aprobar, ejecuta y completa", turnos[1]["final"] and turnos[1]["final"].get("estado") == "COMPLETADO", str(turnos[1]["final"])[:70])
chequeo("reanudar NO vuelve a llamar al planner", turnos[1]["planner"] == 1, f"{turnos[1]['planner']} llamada")
turnos, m = asyncio.run(hitl([PLAN_JULIO, PLAN_JULIO.replace('"2026-07"', '"2026-07"')], ["cambiá el orden de los pasos", "aprobar"]))
chequeo("con observaciones: replanifica y vuelve a pedir aprobación (2 pausas, 0 herramientas)", len(turnos) == 3 and turnos[1]["pausa"] and turnos[1]["herramientas"] == 0, str([t["pausa"] for t in turnos]))
chequeo("el planner recibió las observaciones del revisor", "Observaciones del revisor: cambiá el orden" in sysinst(m.llamadas[1]))
chequeo("tras aprobar el 2º plan completa con 1 replanificación", turnos[-1]["final"] and turnos[-1]["final"].get("replanificaciones") == 1)

print("== T8 · contexto del planner con include_contents='default' (observación)")
m, fin, _ = correr_pe([PLAN_AGOSTO, PLAN_REPLAN], OBJ_AGOSTO, ic="default")
print(f"     contenidos por llamada del planner: {[len(r.contents) for r in m.llamadas]}")
chequeo("con 'default' el planner ve más de 1 contenido al replanificar", len(m.llamadas[1].contents) > 1)

reset()
print()
if FALLAS:
    print("FALLARON:", FALLAS); sys.exit(1)
print("Todos los chequeos pasaron (ADK", __import__("google.adk", fromlist=["x"]).__version__, ")")
