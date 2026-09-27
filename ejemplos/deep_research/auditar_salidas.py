"""Reevalúa la auditoría de citas sobre las salidas reales YA guardadas, sin volver a llamar al modelo.

Usa la traza de cada corrida (las fuentes que reunió cada investigador) para saber qué fuentes se «reunieron».
    python3 auditar_salidas.py [carpeta]
"""
import glob
import re
import statistics
import sys
import warnings

warnings.filterwarnings("ignore")
import dr

ESPERADAS = {"ID-01", "ID-02", "LI-01", "LI-02", "RE-01", "RE-02", "FI-01", "FI-02", "RG-01", "RG-02"}
carpeta = sys.argv[1] if len(sys.argv) > 1 else "salidas"
for f in sorted(glob.glob(f"{carpeta}/salida_real_[0-9].txt")):
    txt = open(f, encoding="utf-8").read()
    informe = re.search(r"\nINFORME:\n(.*?)\n\ntiempo total", txt, re.S)
    if not informe:
        continue
    informe = informe.group(1)
    reunidas = set(re.findall(r"[A-Z]{2}-\d{2}", " ".join(re.findall(r"→ .*?fuentes=(\[[^\]]*\])", txt))))
    citas = dr.citas_de(informe)
    grupos = [len(re.findall(r"[A-Z]{2}-\d{2}", g)) for g in re.findall(r"\[([^\]]*)\]", informe) if re.search(r"[A-Z]{2}-\d{2}", g)]
    citadas = set(citas)
    print(f"{f.split('/')[-1]}: citas={len(citas)} distintas={len(citadas)} | inexistentes={sorted(citadas - set(dr.CORPUS))} | no reunidas={sorted((citadas & set(dr.CORPUS)) - reunidas)}"
          f" | esperadas cubiertas={len(citadas & ESPERADAS)}/10 | homónimo DX-01 citado={'SÍ' if 'DX-01' in citadas else 'no'}"
          f" | ids por grupo de cita: media {statistics.mean(grupos):.1f}, máx {max(grupos)}" if grupos else f"{f}: sin citas")
