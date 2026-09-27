"""Reevalúa la auditoría (react.auditar_respuesta) sobre las salidas reales YA guardadas, sin volver a llamar al modelo.

    python3 auditar_salidas.py [carpeta]      # por defecto: salidas/
"""
import glob
import re
import sys
import warnings

warnings.filterwarnings("ignore")
import react

carpeta = sys.argv[1] if len(sys.argv) > 1 else "salidas"
tot = flag = 0
for f in sorted(glob.glob(f"{carpeta}/salida_real_*_[0-9].txt")):
    txt = open(f, encoding="utf-8").read()
    m = re.search(r"reembolsos solicitados=(\d+)", txt)
    cuerpo = re.search(r"RESPUESTA FINAL AL CLIENTE:\n(.*?)\n\ntiempo total", txt, re.S)
    if not (m and cuerpo):
        continue
    hechas, p = int(m.group(1)), react.auditar_respuesta(cuerpo.group(1), solicitudes=int(m.group(1)))
    tot += 1; flag += bool(p)
    print(f"{f.split('/')[-1]:<38} reembolsos ejecutados={hechas}  auditoría: {p if p else 'sin inconsistencias'}")
print(f"\n{flag} de {tot} respuestas con una afirmación o promesa sin respaldo en las herramientas")
