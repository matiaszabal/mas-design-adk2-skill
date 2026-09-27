"""El Workflow de Reflection descrito en YAML (yaml_reflection/root_agent.yaml) vs. el construido en Python.

Sin LLM real: se carga el YAML con from_config y se reemplaza el modelo de los dos agentes por uno falso.
    python3 test_yaml.py
"""
import json
import re
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
from google.adk.agents.config_agent_utils import from_config

import refl
from modelo_falso import ModeloFalso, textos
from traza import correr, salida_final

RUTA = "yaml_reflection/root_agent.yaml"
MALO = "Lamentamos el inconveniente. Le garantizamos el reembolso de 120 USD hoy mismo."
BUENO = ("Lamentamos el inconveniente. Verificaremos el cobro duplicado de 120 USD y, si se confirma, "
         "el reembolso se acredita en 5 días hábiles luego de la verificación.")
FALLAS = []


def chequeo(nombre, ok, detalle=""):
    print(f"  [{'OK ' if ok else 'FALLA'}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    if not ok:
        FALLAS.append(nombre)


def norm(t):
    return re.sub(r"\s+", " ", str(t)).strip()


def aristas(wf):
    return sorted((getattr(e.from_node, "name", str(e.from_node)), getattr(e.to_node, "name", str(e.to_node)), e.route)
                  for e in wf.graph.edges)


def agentes(wf):
    return {n.name: n for n in wf.graph.nodes if n.name in ("generador", "critico")}


print("== E1 · equivalencia estructural YAML vs Python")
wy = from_config(RUTA)
wp = refl.construir(*refl.crear_agentes())
chequeo("mismos nodos", sorted(n.name for n in wy.graph.nodes) == sorted(n.name for n in wp.graph.nodes))
chequeo("mismas aristas y rutas (incluido el ciclo `revisar`)", aristas(wy) == aristas(wp), f"{len(aristas(wy))} aristas")
ay, ap = agentes(wy), agentes(wp)
for nombre in ("generador", "critico"):
    chequeo(f"{nombre}: include_contents, output_key y output_schema iguales",
            (ay[nombre].include_contents, ay[nombre].output_key, ay[nombre].output_schema)
            == (ap[nombre].include_contents, ap[nombre].output_key, ap[nombre].output_schema),
            f"{ay[nombre].include_contents!r}, {ay[nombre].output_key!r}, {getattr(ay[nombre].output_schema, '__name__', None)}")
    chequeo(f"{nombre}: la instrucción coincide (ignorando saltos de línea)", norm(ay[nombre].instruction) == norm(ap[nombre].instruction))
    chequeo(f"{nombre}: tiene el callback de contexto", bool(ay[nombre].before_model_callback))


def correr_yaml(borradores, veredictos):
    n = {"g": 0, "c": 0}

    def gen(req):
        b = borradores[min(n["g"], len(borradores) - 1)]; n["g"] += 1; return b

    def cri(req):
        a, c = veredictos[min(n["c"], len(veredictos) - 1)]; n["c"] += 1
        return json.dumps({"aprobado": a, "critica": c})
    mg, mc = ModeloFalso(responder=gen), ModeloFalso(responder=cri)
    wf = from_config(RUTA)
    a = agentes(wf)
    a["generador"].model, a["critico"].model = mg, mc
    refl.LOG_CONTEXTO.clear()
    fin = salida_final(correr(wf, refl.PEDIDO, mostrar=False))
    return mg, mc, fin, list(refl.LOG_CONTEXTO)


print("== E2 · comportamiento del YAML con modelos falsos (mismos escenarios que test_sin_llm.py)")
mg, mc, fin, _ = correr_yaml([BUENO], [(True, "ok")])
chequeo("feliz: PUBLICADO en la ronda 1", fin.get("estado") == "PUBLICADO" and fin.get("rondas") == 1, str(fin)[:60])
mg, mc, fin, _ = correr_yaml([MALO], [(False, "promete lo que no puede")])
chequeo(f"tope: escala tras {refl.MAX_RONDAS} rondas", fin.get("estado") == "ESCALADO A HUMANO" and len(mg.llamadas) == refl.MAX_RONDAS, f"{len(mg.llamadas)} llamadas")
mg, mc, fin, _ = correr_yaml([MALO, BUENO], [(False, "promete reembolso hoy"), (True, "ok")])
chequeo("corrección: PUBLICADO en la ronda 2 y el feedback llega al generador",
        fin.get("rondas") == 2 and "promete algo que la política no permite" in str(mg.llamadas[1].config.system_instruction))
mg, mc, fin, _ = correr_yaml([MALO, BUENO], [(True, "se ve bien"), (True, "ok")])
chequeo("crítico complaciente: el validador de código prevalece", fin.get("estado") == "PUBLICADO" and fin.get("rondas") == 2)
mg, mc, fin, log = correr_yaml([MALO, MALO, BUENO], [(False, "x"), (False, "x"), (True, "ok")])
chequeo("contexto: 1 contenido por llamada en las 3 rondas", all(e["n_contents"] == 1 for e in log), str([(e["agente"], e["n_contents"]) for e in log]))

print()
if FALLAS:
    print("FALLARON:", FALLAS); sys.exit(1)
print("Todos los chequeos pasaron")
