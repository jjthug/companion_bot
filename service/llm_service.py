from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import suppress
import time
from observability.tracing import tracer
from typing import Any

from google import genai
from google.genai import types
from opentelemetry.trace import Status, StatusCode
from observability.metrics import llm_first_token

class LLMService:
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        temperature: float = 0.85,
        max_tokens: int = 512,
    ):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.client = genai.Client(api_key=api_key)

    def _build_contents(
        self,
        system_prompt: str,
        conversation_history: list[dict[str, Any]],
        audio_bytes: bytes | None = None,
        audio_mime_type: str = "audio/webm",
    ) -> list[types.Content]:
        contents: list[types.Content] = []

        # System prompt as first user message
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=f"System instruction:\n{system_prompt}"
                    )
                ],
            )
        )

        # Conversation history
        for turn in conversation_history:
            role = turn.get("role", "user")

            if role == "assistant":
                role = "model"

            parts: list[types.Part] = []

            content = turn.get("content")

            if content:
                parts.append(types.Part.from_text(text=content))

            if parts:
                contents.append(
                    types.Content(
                        role=role,
                        parts=parts,
                    )
                )

        # Audio input
        if audio_bytes:
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(
                            data=audio_bytes,
                            mime_type=audio_mime_type,
                        )
                    ],
                )
            )

        return contents

    async def generate_streaming(
        self,
        system_prompt: str,
        conversation_history: list[dict[str, Any]],
        audio_bytes: bytes | None = None,
        audio_mime_type: str = "audio/webm",
    ) -> AsyncGenerator[str, None]:
        with tracer.start_as_current_span("companion.llm.generate") as span:
            start = time.monotonic()
            first_token_recorded = False
            total_chars = 0

            loop = asyncio.get_running_loop()
            queue: asyncio.Queue[str | Exception | None] = asyncio.Queue()

            contents = self._build_contents(
                system_prompt=system_prompt,
                conversation_history=conversation_history,
                audio_bytes=audio_bytes,
                audio_mime_type=audio_mime_type,
            )

            config = types.GenerateContentConfig(
                temperature=self.temperature,
                top_p=0.95,
                max_output_tokens=self.max_tokens,
            )

            # Set when the consumer exits early so the worker stops pushing
            # into a queue nobody is draining.
            cancelled = asyncio.Event()

            def worker() -> None:
                try:
                    response_stream = self.client.models.generate_content_stream(
                        model=self.model_name,
                        contents=contents,
                        config=config,
                    )
                    for chunk in response_stream:
                        if cancelled.is_set():
                            break
                        text = getattr(chunk, "text", None)
                        if text:
                            loop.call_soon_threadsafe(
                                queue.put_nowait,
                                text,
                            )
                except Exception as exc:
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        exc,
                    )

                finally:
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        None,
                    )

            producer = asyncio.create_task(
                asyncio.to_thread(worker)
            )

            try:
                while True:
                    item = await queue.get()

                    if item is None:
                        break

                    if isinstance(item, Exception):   # re-raise real errors
                        span.record_exception(item)
                        span.set_status(Status(StatusCode.ERROR))
                        raise item

                    if not first_token_recorded:
                        ttft_ms = (time.monotonic() - start) * 1000
                        span.set_attribute("llm.first_token_ms", int(ttft_ms))
                        llm_first_token.record(ttft_ms, {"model": self.model_name})
                        first_token_recorded = True
                    
                    total_chars += len(item)

                    yield item
                if not first_token_recorded:
                    span.set_attribute("llm.empty_response", True)
            finally:
                cancelled.set()
                producer.cancel()
                with suppress(asyncio.CancelledError):
                    await producer
                span.set_attribute("llm.response_chars", total_chars)
                if first_token_recorded:
                    total_ms = (time.monotonic() - start) * 1000
                    span.set_attribute("llm.total_ms", int(total_ms))
                