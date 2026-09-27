"""Arnés mínimo: corre un Workflow y devuelve/imprime la traza de eventos (nodo, ruta, salida)."""
import asyncio

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


async def correr_async(wf, texto: str, mostrar: bool = True):
    runner = Runner(node=wf, app_name="qd", session_service=InMemorySessionService(), auto_create_session=True)
    msg = types.Content(role="user", parts=[types.Part(text=texto)])
    eventos = []
    async for ev in runner.run_async(user_id="u", session_id="s", new_message=msg):
        eventos.append(ev)
        if mostrar and getattr(ev, "output", None) is not None:
            ruta = getattr(getattr(ev, "actions", None), "route", None)
            path = ev.node_info.path if getattr(ev, "node_info", None) else "?"
            print(f"  [{path.rsplit('/', 1)[-1]:<22}] route={ruta} salida={str(ev.output)[:120]}")
    return eventos


def correr(wf, texto: str, mostrar: bool = True):
    return asyncio.run(correr_async(wf, texto, mostrar))


def salida_final(eventos):
    outs = [e.output for e in eventos if getattr(e, "output", None) is not None]
    return outs[-1] if outs else None


def texto_final(eventos):
    """Texto del ÚLTIMO evento que trae algo: `output` (nodos función) o el texto de `content` (los agentes LLM
    de texto libre dejan su respuesta en `content`, no en `output`)."""
    for e in reversed(eventos):
        if getattr(e, "output", None) is not None:
            return e.output
        cont = getattr(e, "content", None)
        if cont and cont.parts:
            t = "".join(p.text or "" for p in cont.parts)
            if t:
                return t
    return None
