"""Modelo falso para ReAct: emite llamadas a herramientas y respuestas de texto según un guion (sin red)."""
from typing import Any

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import Field


class ModeloFalsoReAct(BaseLlm):
    """`guion`: lista de ("call", nombre, args) | ("text", texto), o un callable (n, llm_request) -> ese tipo de tupla.
    Si se acaba la lista, repite el último elemento."""
    model: str = "falso-react"
    guion: Any = None
    llamadas: list = Field(default_factory=list)

    async def generate_content_async(self, llm_request, stream: bool = False):
        n = len(self.llamadas)
        self.llamadas.append(llm_request)
        r = self.guion(n, llm_request) if callable(self.guion) else self.guion[min(n, len(self.guion) - 1)]
        part = types.Part(function_call=types.FunctionCall(name=r[1], args=r[2])) if r[0] == "call" else types.Part(text=r[1])
        yield LlmResponse(content=types.Content(role="model", parts=[part]))
