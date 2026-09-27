"""ReAct sobre ADK 2.9.1 — un LlmAgent con herramientas: el bucle razonar → actuar → observar lo maneja ADK.

    usuario → LlmAgent ⇄ herramientas   (el modelo decide en CADA vuelta: qué herramienta llamar o si responder)

Las tres decisiones de orquestación, tal como quedan en este código:

  ¿Quién decide qué sigue?  El MODELO, en cada vuelta. El código solo provee el marco: ejecuta la herramienta
                            pedida, devuelve el resultado e impone límites (RunConfig.max_llm_calls).
  ¿Con qué contexto?        Una única ventana que CRECE: cada llamada a herramienta y su resultado se anexan
                            (include_contents="default"). Ver test_sin_llm.py para la progresión medida.
  ¿Cuándo se detiene?       Cuando el modelo responde sin pedir herramientas, o cuando se agota el tope EXTERNO
                            (max_llm_calls; por defecto 500). Que el modelo diga «listo» no es confiable por sí solo.

Los datos son SINTÉTICOS (banco ficticio).
"""
import os
import re
import unicodedata

from google.adk import Agent

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")

MOVIMIENTOS = {
    "C-001": [{"fecha": "2026-09-10", "concepto": "Supermercado", "monto_usd": 45},
              {"fecha": "2026-09-12", "concepto": "Cuota préstamo P-77", "monto_usd": 120},
              {"fecha": "2026-09-12", "concepto": "Cuota préstamo P-77", "monto_usd": 120}],
    "C-002": [{"fecha": "2026-09-11", "concepto": "Cuota préstamo P-90", "monto_usd": 80}],
}
PRESTAMOS = {"P-77": {"cuotas_vigentes_por_mes": 1, "cuota_mensual_usd": 120}, "P-90": {"cuotas_vigentes_por_mes": 1, "cuota_mensual_usd": 80}}
POLITICAS = {"cobro duplicado": "Si se verifica un cobro duplicado, corresponde solicitar el reembolso; se acredita en 5 días hábiles."}

SOLICITUDES: list[dict] = []          # gancho de prueba: acciones con efecto que se pidieron


# ------------------------------------------------------------- herramientas (código)
def consultar_movimientos(cuenta: str) -> dict:
    """Devuelve los movimientos recientes de una cuenta (por ejemplo 'C-001')."""
    if cuenta not in MOVIMIENTOS:
        return {"error": f"la cuenta {cuenta} no existe"}
    return {"cuenta": cuenta, "movimientos": MOVIMIENTOS[cuenta]}


def consultar_prestamo(id_prestamo: str) -> dict:
    """Devuelve los datos de un préstamo (por ejemplo 'P-77'): cuotas vigentes por mes y monto de la cuota."""
    if id_prestamo not in PRESTAMOS:
        return {"error": f"el préstamo {id_prestamo} no existe"}
    return {"id": id_prestamo, **PRESTAMOS[id_prestamo]}


def buscar_politica(tema: str) -> dict:
    """Busca la política del banco sobre un tema (por ejemplo 'cobro duplicado')."""
    for k, v in POLITICAS.items():
        if k in tema.lower():
            return {"tema": k, "politica": v}
    return {"error": f"no hay política sobre «{tema}»"}


def solicitar_reembolso(cuenta: str, monto_usd: float, motivo: str) -> dict:
    """Abre una solicitud de reembolso (ACCIÓN CON EFECTO: úsala solo tras verificar el cobro duplicado)."""
    SOLICITUDES.append({"cuenta": cuenta, "monto_usd": monto_usd, "motivo": motivo})
    return {"ticket": f"RB-{len(SOLICITUDES):03d}", "estado": "abierta"}


HERRAMIENTAS = [consultar_movimientos, consultar_prestamo, buscar_politica, solicitar_reembolso]

LOG_CONTEXTO: list[dict] = []


def log_contexto(callback_context, llm_request):
    contents = llm_request.contents or []
    LOG_CONTEXTO.append({"agente": callback_context.agent_name, "n_contents": len(contents), "roles": [c.role for c in contents]})
    return None


def crear_agente(modelo=None, include_contents: str = "default", herramientas=None):
    return Agent(
        name="soporte", model=modelo or MODEL, tools=herramientas or HERRAMIENTAS, include_contents=include_contents,
        before_model_callback=log_contexto,
        instruction=(
            "Sos un agente de soporte de un banco. Resolvé el reclamo del cliente usando las herramientas; no inventes "
            "datos. Antes de solicitar un reembolso verificá con los movimientos y con el préstamo que el cobro es "
            "realmente un duplicado y consultá la política. Al terminar, informá al cliente qué verificaste y qué hiciste."))


# ---------------------------------------------------------------- auditoría (código)
def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def auditar_respuesta(texto: str, solicitudes: int | None = None) -> list[str]:
    """Contrasta lo que el modelo AFIRMA o PROMETE con lo que REALMENTE se ejecutó (SOLICITUDES).

    En corridas reales el modelo llegó a decir «he solicitado el reembolso» sin haber llamado a la herramienta, y
    también «procederé a solicitar el reembolso» y terminar el turno sin hacerlo. Es una regla determinista y chica
    (con falsos positivos y negativos posibles): se prueba contra textos correctos y contra los fallos observados."""
    hechas = len(SOLICITUDES) if solicitudes is None else solicitudes
    t = _norm(texto)
    problemas = []
    if hechas == 0:
        if re.search(r"(?<!no )(he solicitado|solicite|solicitamos|se ha (generado|abierto|creado)|se (genero|abrio|creo)|abri)\b[^.]{0,80}reembolso", t):
            problemas.append("afirma haber abierto un reembolso, pero ninguna herramienta lo abrió")
        if re.search(r"(?<!no )(procedere a|voy a|proceder[eé] a|solicitare|abrire|gestionare)\b[^.]{0,60}(solicitar|abrir|gestionar)?[^.]{0,40}reembolso", t):
            problemas.append("promete abrir un reembolso y termina el turno sin hacerlo")
    return problemas
