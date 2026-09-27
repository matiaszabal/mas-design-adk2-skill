"""Pruebas sin LLM real ni red (modelo falso) del arquetipo Reflection.

    python3 test_sin_llm.py
"""
import json
import sys

import refl
from modelo_falso import ModeloFalso, textos
from traza import correr, salida_final

MALO = "Lamentamos el inconveniente. Le garantizamos el reembolso de 120 USD hoy mismo."
BUENO = ("Lamentamos el inconveniente. Verificaremos el cobro duplicado de 120 USD y, si se confirma, "
         "el reembolso se acredita en 5 días hábiles luego de la verificación.")
FALLAS = []


def chequeo(nombre, ok, detalle=""):
    print(f"  [{'OK ' if ok else 'FALLA'}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    if not ok:
        FALLAS.append(nombre)


def sysinst(req) -> str:
    return str(getattr(req.config, "system_instruction", "") or "")


def todo(req) -> str:
    return sysinst(req) + " " + " ".join(textos(req))


def correr_refl(borradores, veredictos, ic="none"):
    """borradores / veredictos: listas por ronda; la última se repite si hacen falta más."""
    n = {"g": 0, "c": 0}

    def gen(req):
        b = borradores[min(n["g"], len(borradores) - 1)]
        n["g"] += 1
        return b

    def cri(req):
        a, c = veredictos[min(n["c"], len(veredictos) - 1)]
        n["c"] += 1
        return json.dumps({"aprobado": a, "critica": c})
    mg, mc = ModeloFalso(responder=gen), ModeloFalso(responder=cri)
    refl.LOG_CONTEXTO.clear()
    g, c = refl.crear_agentes(include_contents=ic, modelos={"generador": mg, "critico": mc})
    ev = correr(refl.construir(g, c), refl.PEDIDO, mostrar=False)
    return mg, mc, salida_final(ev), list(refl.LOG_CONTEXTO)


print("== validador determinista")
chequeo("el borrador malo falla y el bueno pasa",
        not refl.validar_texto(MALO)["ok"] and refl.validar_texto(BUENO)["ok"], str(refl.validar_texto(MALO)["fallas"][:2]))

NEGADO = "Lamentamos el inconveniente. Verificaremos los 120 USD; el reembolso se acredita en 5 días hábiles luego de la verificación. No es posible garantizar un reembolso inmediato."
chequeo("una NEGACIÓN de la promesa no es una falla", refl.validar_texto(NEGADO)["ok"], str(refl.validar_texto(NEGADO)["fallas"]))
chequeo("una promesa afirmativa sí es una falla", not refl.validar_texto(MALO)["ok"] and any("hoy mismo" in f or "garantizamos" in f for f in refl.validar_texto(MALO)["fallas"]))

print("== R1 · camino feliz: el borrador bueno y el crítico aprueba")
mg, mc, fin, _ = correr_refl([BUENO], [(True, "ok")])
chequeo("estado PUBLICADO en la ronda 1", fin.get("estado") == "PUBLICADO" and fin.get("rondas") == 1, str(fin)[:80])
chequeo("una llamada al generador y una al crítico", len(mg.llamadas) == 1 and len(mc.llamadas) == 1)

print(f"== R2 · tope: el generador insiste con el borrador malo y el crítico nunca aprueba (MAX_RONDAS={refl.MAX_RONDAS})")
mg, mc, fin, _ = correr_refl([MALO], [(False, "promete lo que no puede")])
chequeo("corta y escala a un humano", fin.get("estado") == "ESCALADO A HUMANO", str(fin.get("estado")))
chequeo(f"exactamente {refl.MAX_RONDAS} rondas (generador y crítico)", len(mg.llamadas) == refl.MAX_RONDAS == len(mc.llamadas) and fin.get("rondas") == refl.MAX_RONDAS)
chequeo("informa lo que quedó pendiente", bool(fin.get("pendiente")), str(fin.get("pendiente"))[:70])

print("== R3 · corrección: ronda 1 mala (el crítico la rechaza), ronda 2 buena")
mg, mc, fin, _ = correr_refl([MALO, BUENO], [(False, "promete reembolso hoy"), (True, "ok")])
chequeo("PUBLICADO en la ronda 2", fin.get("estado") == "PUBLICADO" and fin.get("rondas") == 2, str(fin)[:60])
chequeo("el feedback llega al generador de la ronda 2 (instrucción y contenido)",
        "promete algo que la política no permite" in sysinst(mg.llamadas[1]) and "Observaciones a corregir" in " ".join(textos(mg.llamadas[1])))
chequeo("la ronda 1 NO tenía feedback", "promete algo" not in sysinst(mg.llamadas[0]))

print("== R4 · crítico complaciente: aprueba el borrador malo; el validador de código prevalece")
mg, mc, fin, _ = correr_refl([MALO, BUENO], [(True, "se ve bien"), (True, "ok")])
chequeo("no publica en la ronda 1 aunque el crítico aprobó", fin.get("estado") == "PUBLICADO" and fin.get("rondas") == 2, str(fin)[:60])

print("== R5 · contexto por ronda (3 rondas: falla, falla, pasa)")
resultados = {}
for ic in ("none", "default"):
    mg, mc, fin, log = correr_refl([MALO, MALO, BUENO], [(False, "x"), (False, "x"), (True, "ok")], ic=ic)
    resultados[ic] = {a: [e["n_contents"] for e in log if e["agente"] == a] for a in ("generador", "critico")}
    print(f"     include_contents={ic!r}: {resultados[ic]}")
chequeo("con 'none': generador y crítico ven siempre 1 contenido", all(n == 1 for v in resultados["none"].values() for n in v))
chequeo("con 'default': el contexto del generador crece entre rondas",
        resultados["default"]["generador"][-1] > resultados["default"]["generador"][0], str(resultados["default"]["generador"]))

print("== R6 · el crítico no ve la instrucción del generador")
mg, mc, fin, _ = correr_refl([BUENO], [(True, "ok")])
chequeo("la instrucción del generador no aparece en el request del crítico", "atención al cliente de un banco" not in todo(mc.llamadas[0]))
chequeo("el crítico sí recibe el borrador y la evidencia del validador", "validacion" in todo(mc.llamadas[0]) and "120 USD" in todo(mc.llamadas[0]))

print()
if FALLAS:
    print("FALLARON:", FALLAS); sys.exit(1)
print("Todos los chequeos pasaron (ADK", __import__("google.adk", fromlist=["x"]).__version__, ")")
