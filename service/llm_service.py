from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
import google.genai as genai


class LLMService:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-pro", temperature: float = 0.85, max_tokens: int = 512):
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model = None
        if genai is not None:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    top_p=0.95,
                    max_output_tokens=max_tokens,
                ),
            )

    def _normalize_history(self, conversation_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        for turn in conversation_history:
            role = turn.get("role", "user")
            if role == "assistant":
                role = "model"
            content = turn.get("content", "")
            normalized.append({"role": role, "parts": [content]})
        return normalized

    async def generate_streaming(self, system_prompt: str, conversation_history: list[dict[str, Any]]) -> AsyncGenerator[str, None]:
        if self.model is None:
            fallback = "I’m sorry, I’m having a little trouble thinking right now. Could you give me a moment?"
            for part in fallback.split():
                yield part + " "
            return

        history = self._normalize_history(conversation_history)
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def worker() -> None:
            try:
                response = self.model.generate_content(
                    history,
                    system_instruction=system_prompt,
                    stream=True,
                )
                for chunk in response:
                    text = getattr(chunk, "text", None)
                    if text:
                        loop.call_soon_threadsafe(queue.put_nowait, text)
            except Exception as exc:  # pragma: no cover - runtime path
                loop.call_soon_threadsafe(queue.put_nowait, f"[LLM error] {exc}")
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        producer = asyncio.create_task(asyncio.to_thread(worker))

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

        await producer
