"""Modelo falso para tests: no llama a ninguna red y registra lo que ADK le envía a cada agente."""
from typing import Any, Callable

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import Field


class ModeloFalso(BaseLlm):
    model: str = "falso"
    responder: Any = None                          # Callable[[LlmRequest], str]
    llamadas: list = Field(default_factory=list)   # LlmRequest recibidos, en orden

    async def generate_content_async(self, llm_request, stream: bool = False):
        self.llamadas.append(llm_request)
        texto = self.responder(llm_request)
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=texto)]))


def ultimo_texto(req) -> str:
    """Texto del último contenido del usuario en el request."""
    for c in reversed(req.contents or []):
        if c.role == "user":
            return "".join(p.text or "" for p in c.parts or [])
    return ""


def textos(req) -> list[str]:
    return ["".join(p.text or "" for p in (c.parts or [])) for c in (req.contents or [])]
