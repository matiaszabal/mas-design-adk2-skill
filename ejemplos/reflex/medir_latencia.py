"""Latencia de una pasada de Reflex: variante LLM (llamadas SECUENCIALES, sin concurrencia) vs variante por reglas.

    python3 medir_latencia.py
"""
import asyncio
import statistics
import time
import warnings

warnings.filterwarnings("ignore")
import reflex
from traza import correr_async, texto_final

MSGS = ["Me clonaron la tarjeta, ayuda", "Quiero subir el límite de mi tarjeta de crédito", "¿Cuánto me falta pagar del préstamo?",
        "¿Cuál es la capital de Francia?", "Hay un movimiento en mi cuenta que no reconozco"]


async def medir(construir, msgs):
    ts = []
    for m in msgs:
        t = time.perf_counter()
        await correr_async(construir(), m, mostrar=False)
        ts.append(time.perf_counter() - t)
    return ts


async def main():
    llm = await medir(lambda: reflex.construir(reflex.crear_clasificador()), MSGS)
    reg = await medir(reflex.construir_reglas, MSGS * 20)
    print(f"LLM (gemini-2.5-flash), {len(llm)} llamadas secuenciales: mediana {statistics.median(llm):.2f} s | mín {min(llm):.2f} s | máx {max(llm):.2f} s")
    print(f"Reglas (sin LLM), {len(reg)} ejecuciones del grafo completo: mediana {statistics.median(reg) * 1000:.1f} ms | máx {max(reg) * 1000:.1f} ms")

asyncio.run(main())
