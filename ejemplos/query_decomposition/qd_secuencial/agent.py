"""root_agent de la variante secuencial de Query Decomposition (para `adk web`)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))   # para importar qd.py y kb.py

import qd  # noqa: E402

_descomponer, _siguiente, _respondedor, _sintetizador = qd.crear_agentes()
root_agent = qd.construir_secuencial(_siguiente, _respondedor, _sintetizador)
