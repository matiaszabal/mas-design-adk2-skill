"""Corrida REAL de Deep Research con Gemini (Vertex AI). Solo invocación de modelo; «web» y proveedor sintéticos (ver dr.py).

    export GOOGLE_GENAI_USE_VERTEXAI=TRUE GOOGLE_CLOUD_PROJECT=<proyecto> GOOGLE_CLOUD_LOCATION=us-central1
    python3 correr_real.py
"""
import asyncio
import logging
import time
import warnings
from collections import Counter

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
import dr
from traza import correr_async, texto_final

ESPERADAS = {"ID-01", "ID-02", "LI-01", "LI-02", "RE-01", "RE-02", "FI-01", "FI-02", "RG-01", "RG-02"}   # lo que un informe completo debería citar
HOMONIMO = "DX-01"                                                                                   # otra empresa (Logística Andes Ltda.)


async def main():
    print(f"### deep research · modelo={dr.MODEL} · MAX_RONDAS={dr.MAX_RONDAS} MAX_INVESTIGADORES={dr.MAX_INVESTIGADORES} MAX_LLAMADAS_AGENTE={dr.MAX_LLAMADAS_AGENTE}\nPREGUNTA: {dr.PREGUNTA}\n")
    t = time.perf_counter()
    fin = texto_final(await correr_async(dr.construir(*dr.crear_agentes()), dr.PREGUNTA, mostrar=False))
    seg = time.perf_counter() - t
    for r in dr.TRAZA_RONDAS:
        print(f"--- RONDA {r['ronda']}: {len(r['consultas'])} investigadores")
        for tema, consulta in r["consultas"]:
            print(f"      · {tema}: «{consulta}»")
        for tema, h in r["hallazgos"].items():
            print(f"      → {tema}: fuentes={h['fuentes']}{'  (SIN EVIDENCIA)' if h['sin_evidencia'] else ''}")
        print(f"      evaluador: cobertura_suficiente={r['cobertura_suficiente']}  brechas={r['brechas']}")
    print(f"\nINFORME:\n{fin['informe']}\n")
    citadas = set(dr.citas_de(fin["informe"]))
    print(f"tiempo total: {seg:.1f} s | rondas={fin['rondas']} | motivo_fin={fin['motivo_fin']} | llamadas a agentes (presupuesto)={fin['llamadas_agente']}")
    print(f"búsquedas realizadas por los investigadores: {len(dr.LLAMADAS_BUSQUEDA)}")
    print("contexto por llamada al modelo (agente: n_contents):", {a: dict(Counter(e['n_contents'] for e in dr.LOG_CONTEXTO if e['agente'] == a)) for a in ("planificador", "investigador", "evaluador", "redactor")})
    print(f"brechas abiertas declaradas: {fin['brechas_abiertas']}")
    print(f"AUDITORÍA DE CITAS (código): inválidas={fin['citas_invalidas']} | cobertura de fuentes esperadas: {len(citadas & ESPERADAS)}/{len(ESPERADAS)} "
          f"(faltan {sorted(ESPERADAS - citadas)}) | cita al HOMÓNIMO {HOMONIMO}: {'SÍ' if HOMONIMO in citadas else 'no'}")

asyncio.run(main())
