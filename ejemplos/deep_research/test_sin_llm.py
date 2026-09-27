"""Pruebas sin LLM real (modelos falsos) del arquetipo Deep Research.

    python3 test_sin_llm.py
"""
import asyncio
import json
import logging
import re
import sys
import time
import warnings

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
import dr
from modelo_falso import ModeloFalso, textos, ultimo_texto
from modelo_react import ModeloFalsoReAct
from traza import correr, salida_final

FALLAS = []


def chequeo(nombre, ok, detalle=""):
    print(f"  [{'OK ' if ok else 'FALLA'}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    if not ok:
        FALLAS.append(nombre)


TEMAS5 = [("identidad societaria", "identidad societaria Logística Andina"), ("litigios", "litigios Logística Andina"),
          ("reputación", "reputación Logística Andina"), ("situación financiera", "situación financiera Logística Andina"),
          ("riesgos regulatorios", "riesgos regulatorios Logística Andina")]


def ronda_json(pares):
    return json.dumps({"consultas": [{"tema": t, "consulta": c} for t, c in pares]})


class Montaje:
    """Arma los cuatro agentes con modelos falsos y corre el workflow."""

    def __init__(self, planes, evaluaciones, demora=0.0, falla_tema=None, informe=None):
        self.planes, self.evaluaciones, self.n = list(planes), list(evaluaciones), {"p": 0, "e": 0}
        self.consultas_investigadas = []
        m = self

        def planificar(req):
            i = min(m.n["p"], len(m.planes) - 1); m.n["p"] += 1
            return m.planes[i]

        def evaluar(req):
            i = min(m.n["e"], len(m.evaluaciones) - 1); m.n["e"] += 1
            return json.dumps(m.evaluaciones[i])

        def guion_inv(n, req):
            entrada = [t for t in textos(req) if t.startswith("TEMA:")]
            tema = re.search(r"TEMA: (.*)", entrada[0]).group(1) if entrada else "?"
            resp = [p.function_response.response for c in req.contents for p in (c.parts or []) if p.function_response]
            if not resp:
                m.consultas_investigadas.append(tema)
                if falla_tema and tema == falla_tema:
                    raise RuntimeError("el investigador falló")
                return ("call", "buscar_fuentes", {"consulta": re.search(r"CONSULTA: (.*)", entrada[0]).group(1)})
            ids = [f["id"] for r in resp for f in r.get("fuentes", [])]
            return ("text", json.dumps({"tema": tema, "resumen": f"Hallazgo de {tema}", "fuentes": ids, "sin_evidencia": not ids}))

        def redactar(req):
            if informe is not None:
                return informe
            notas = json.loads(ultimo_texto(req))["notas"]
            return "INFORME: " + " ".join(f"{v['resumen']} " + "".join(f"[{f}]" for f in v["fuentes"]) for v in notas.values())

        class InvLento(ModeloFalsoReAct):
            async def generate_content_async(self, llm_request, stream=False):
                await asyncio.sleep(demora)
                async for x in super().generate_content_async(llm_request, stream):
                    yield x
        self.mp, self.me, self.mr = ModeloFalso(responder=planificar), ModeloFalso(responder=evaluar), ModeloFalso(responder=redactar)
        self.mi = InvLento(guion=guion_inv)
        self.agentes = dr.crear_agentes(modelos={"planificador": self.mp, "investigador": self.mi, "evaluador": self.me, "redactor": self.mr})

    def correr(self):
        dr.LLAMADAS_BUSQUEDA.clear(); dr.LOG_CONTEXTO.clear()
        t = time.perf_counter()
        fin = salida_final(correr(dr.construir(*self.agentes), dr.PREGUNTA, mostrar=False))
        self.seg = time.perf_counter() - t
        return fin


SUF = {"cobertura_suficiente": True, "brechas": []}
BRECHA = {"cobertura_suficiente": False, "brechas": ["litigios de la sociedad argentina"]}
PLAN1 = ronda_json(TEMAS5)
PLAN2 = ronda_json([("litigios", "litigios Argentina")])

print("== D1 · una ronda: cobertura suficiente")
m = Montaje([PLAN1], [SUF]); fin = m.correr()
chequeo("1 ronda, motivo «cobertura suficiente», sin brechas", fin["rondas"] == 1 and fin["motivo_fin"] == "cobertura suficiente" and fin["brechas_abiertas"] == [], str(fin["motivo_fin"]))
chequeo("5 investigadores en la ronda (uno por tema)", len(m.consultas_investigadas) == 5, str(m.consultas_investigadas))
chequeo("el informe se escribe DESDE las notas y cita fuentes reales (auditoría de citas limpia)", fin["informe"].startswith("INFORME:") and fin["citas_invalidas"] == [], fin["informe"][:80])

print("== D2 · dos rondas: el evaluador detecta una brecha y la segunda ronda investiga SOLO eso")
m = Montaje([PLAN1, PLAN2], [BRECHA, SUF]); fin = m.correr()
chequeo("2 rondas y cobertura suficiente al final", fin["rondas"] == 2 and fin["motivo_fin"] == "cobertura suficiente", f"rondas={fin['rondas']}")
chequeo("la 2ª ronda investigó 1 sola consulta (5 + 1 en total), sin repetir lo cubierto", len(m.consultas_investigadas) == 6, str(m.consultas_investigadas[5:]))
req_p2 = m.mp.llamadas[1]
chequeo("el planificador de la 2ª ronda recibe las brechas y las notas COMPACTAS", "litigios de la sociedad argentina" in ultimo_texto(req_p2) and "identidad societaria" in ultimo_texto(req_p2))
chequeo("las brechas ya cubiertas no quedan abiertas", fin["brechas_abiertas"] == [])
chequeo("las notas fusionan lo de dos rondas: «litigios» reúne las fuentes de las dos rondas",
        len(m.consultas_investigadas) == 6 and "Hallazgo de litigios" in fin["informe"], fin["informe"][:0] or "")

print("== D3 · presupuesto: el evaluador NUNCA queda conforme")
m = Montaje([PLAN1, PLAN2, PLAN2], [BRECHA]); fin = m.correr()
chequeo(f"corta en MAX_RONDAS={dr.MAX_RONDAS} con motivo «presupuesto (rondas)»", fin["rondas"] == dr.MAX_RONDAS and fin["motivo_fin"] == "presupuesto (rondas)", f"rondas={fin['rondas']}, {fin['motivo_fin']}")
chequeo("entrega igualmente el informe Y las brechas abiertas", bool(fin["informe"]) and fin["brechas_abiertas"] == BRECHA["brechas"], str(fin["brechas_abiertas"]))
viejo = dr.MAX_LLAMADAS_AGENTE; dr.MAX_LLAMADAS_AGENTE = 8
m = Montaje([PLAN1, PLAN2, PLAN2], [BRECHA]); fin = m.correr(); dr.MAX_LLAMADAS_AGENTE = viejo
chequeo("el presupuesto de LLAMADAS corta antes que las rondas", fin["motivo_fin"] == "presupuesto (llamadas)" and fin["rondas"] < dr.MAX_RONDAS, f"rondas={fin['rondas']}, {fin['motivo_fin']}, llamadas={fin['llamadas_agente']}")

print("== D4 · tope de fan-out")
m = Montaje([ronda_json([(f"tema {i}", f"tema {i} Andina") for i in range(9)])], [SUF]); fin = m.correr()
chequeo(f"9 consultas propuestas → a lo sumo MAX_INVESTIGADORES={dr.MAX_INVESTIGADORES} investigadores", len(m.consultas_investigadas) == dr.MAX_INVESTIGADORES, str(len(m.consultas_investigadas)))

print("== D5 · los investigadores corren en paralelo (5 × 2 llamadas de 0,3 s)")
m = Montaje([PLAN1], [SUF], demora=0.3); m.correr()
chequeo("el tiempo total es ~1 investigador, no la suma", m.seg < 2.2, f"{m.seg:.2f} s (serial: ≥ 3,0 s solo de investigadores)")

print("== D6 · contexto de cada rol")
m = Montaje([PLAN1], [SUF]); fin = m.correr()
por_agente = {}
for e in dr.LOG_CONTEXTO:
    por_agente.setdefault(e["agente"], []).append(e["n_contents"])
chequeo("planificador, evaluador y redactor ven 1 contenido", all(set(por_agente[a]) == {1} for a in ("planificador", "evaluador", "redactor")), str({a: por_agente[a] for a in ("planificador", "evaluador", "redactor")}))
chequeo("cada investigador: 1 contenido y luego 3 (llamada + resultado de su propia búsqueda)", sorted(set(por_agente["investigador"])) == [1, 3], str(sorted(set(por_agente["investigador"]))))
todo_inv = " ".join(t for r in m.mi.llamadas for t in textos(r))
def busquedas_ajenas(req):
    """Consultas de búsqueda (llamadas a herramienta) que aparecen en el contexto y NO son la del propio investigador."""
    propias = [x.strip() for x in re.findall(r"CONSULTA: (.*)", " ".join(textos(req)))]
    llamadas = [dict(p.function_call.args).get("consulta") for c in req.contents for p in (c.parts or []) if p.function_call]
    return [q for q in llamadas if (q or "").strip() not in propias]
chequeo("ningún investigador ve la pregunta original ni las BÚSQUEDAS de los demás (use_sub_branch=True)",
        "debida diligencia" not in todo_inv.lower() and all(busquedas_ajenas(r) == [] for r in m.mi.llamadas), "0 búsquedas ajenas visibles")
chequeo("el redactor NO recibe el material crudo de las fuentes (solo las notas)", "Capital social" not in ultimo_texto(m.mr.llamadas[0]) and "notas" in ultimo_texto(m.mr.llamadas[0]))

print("== D7 · un investigador falla: no tira a los demás")
m = Montaje([PLAN1], [SUF], falla_tema="reputación"); fin = m.correr()
notas_txt = fin["informe"]
chequeo("la corrida continúa y termina", fin["rondas"] == 1 and bool(fin["informe"]))
chequeo("los otros 4 temas quedaron investigados", len(m.consultas_investigadas) == 5 and "Hallazgo de litigios" in notas_txt and "Hallazgo de riesgos regulatorios" in notas_txt)
chequeo("el tema que falló quedó marcado como sin evidencia", "falló la investigación" in notas_txt, notas_txt[:60])

print("== D8 · auditoría de citas (determinista)")
m = Montaje([PLAN1], [SUF], informe="Se halló X [LI-02] y Z [ZZ-99]. Otra cosa [DX-01]."); fin = m.correr()
chequeo("detecta una cita inexistente y una fuente que ningún investigador reunió",
        any("ZZ-99" in p for p in fin["citas_invalidas"]) and any("DX-01" in p for p in fin["citas_invalidas"]), str(fin["citas_invalidas"]))

print("== D8b · las citas AGRUPADAS también se auditan (la primera versión de la auditoría era ciega a ellas)")
chequeo("«[LI-01, RG-01]» y «[LI-02]» se leen como 3 citas", sorted(dr.citas_de("A [LI-01, RG-01]. B [LI-02]; C [ZZ-99, DX-01].")) == ["DX-01", "LI-01", "LI-02", "RG-01", "ZZ-99"])
m = Montaje([PLAN1], [SUF], informe="Fue constituida en 2011 [ID-01, ZZ-99, DX-01]."); fin = m.correr()
chequeo("una cita inexistente DENTRO de un grupo se detecta", any("ZZ-99" in p for p in fin["citas_invalidas"]), str(fin["citas_invalidas"]))

print("== D9 · notas: fusionar y compactar (unitarias)")
n = {}
dr.fusionar(n, dr.Hallazgo(tema="Litigios", resumen="Chile: 1 demanda.", fuentes=["LI-02"]))
dr.fusionar(n, dr.Hallazgo(tema="litigios", resumen="Argentina: 2 causas.", fuentes=["LI-01", "LI-02"]))
v = n["litigios"]
chequeo("el mismo tema (sin importar mayúsculas) se fusiona, une fuentes y acumula el resumen", v["fuentes"] == ["LI-02", "LI-01"] and "Chile" in v["resumen"] and "Argentina" in v["resumen"], str(v["fuentes"]))
dr.fusionar(n, dr.Hallazgo(tema="Reputación", resumen="falló", sin_evidencia=True))
dr.fusionar(n, dr.Hallazgo(tema="reputación", resumen="Premio 2024.", fuentes=["RE-01"], sin_evidencia=False))
chequeo("un tema sin evidencia se completa con un hallazgo posterior", n[dr._clave("Reputación")]["sin_evidencia"] is False and n[dr._clave("Reputación")]["fuentes"] == ["RE-01"])
largo = {"x": {"tema": "x", "resumen": "a" * 1000, "fuentes": [], "sin_evidencia": False}}
chequeo(f"compactar recorta a {dr.CHARS_NOTA} caracteres por tema", len(dr.compactar(largo)["x"]["resumen"]) == dr.CHARS_NOTA and len(largo["x"]["resumen"]) == 1000)

print()
if FALLAS:
    print("FALLARON:", FALLAS); sys.exit(1)
print("Todos los chequeos pasaron (ADK", __import__("google.adk", fromlist=["x"]).__version__, ")")
