"""Base de conocimiento SINTÉTICA (banco ficticio) y recuperación por palabras clave.

Los documentos son inventados para el ejemplo: no hay datos reales de ningún cliente ni institución.
La recuperación es código determinista (no un LLM): así lo único que hace el modelo es redactar
la respuesta a partir de los fragmentos, y el contexto que ve se puede controlar y auditar.
"""
import math
import re
import unicodedata

DOCS = {
    "TAR-01": "Tarifa de transferencias internacionales: comisión fija de 15 USD por operación.",
    "TAR-07": "Tarifa de transferencias nacionales: comisión fija de 2 USD por operación.",
    "PLA-02": "Plan Premium: bonifica el 50% de la comisión fija de las transferencias internacionales.",
    "PLA-03": "Plan Básico: no incluye bonificaciones sobre comisiones de transferencias.",
    "FX-04": "Conversión de moneda: spread del 1,2% sobre el monto convertido, aplicado sobre el "
             "tipo de cambio de referencia.",
    "CLI-05": "Cliente C-001: titular de plan Premium.",
    "CLI-06": "Cliente C-002: titular de plan Básico.",
    "CAJ-08": "Extracción en cajero automático: comisión fija de 1 USD por operación.",
}

_STOP = {"de", "la", "el", "los", "las", "un", "una", "por", "que", "en", "y", "a", "del", "al",
         "se", "es", "cual", "cuanto", "cuales", "para", "con", "su", "sus", "lo", "como"}


def _tokens(texto: str) -> set[str]:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    # raíz por prefijo (6 letras): tolera singular/plural y derivaciones ("transferencia"/"transferencias",
    # "internacional"/"internacionales"). Es un truco didáctico para esta base chica, no un buen stemmer.
    return {w[:6] for w in re.findall(r"[a-z0-9\-]+", t) if w not in _STOP and len(w) > 1}


_DF: dict[str, int] = {}
for _txt in DOCS.values():
    for _w in _tokens(_txt):
        _DF[_w] = _DF.get(_w, 0) + 1


def buscar(consulta: str, k: int = 4) -> list[tuple[str, str]]:
    """Hasta k pares (id, texto) con mayor puntaje; el puntaje pesa más las palabras raras (IDF simple).

    Sin el peso, palabras comunes ("transferencia", "internacional") desplazan al documento que sí
    responde ("conversión" solo está en FX-04)."""
    q = _tokens(consulta)
    n = len(DOCS)
    puntaje = sorted(((sum(math.log(n / _DF[w]) for w in q & _tokens(txt)), i) for i, txt in DOCS.items()), reverse=True)
    return [(i, DOCS[i]) for s, i in puntaje[:k] if s > 0]
