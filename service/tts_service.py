from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import WebSocket
from google.cloud import texttospeech_v1beta1 as tts
from google.oauth2 import service_account
from config import settings

class TTSService:
    def __init__(
        self,
        voice_name: str = "en-US-Journey-F",
    ):
        self.voice_name = voice_name

        # Uses GOOGLE_APPLICATION_CREDENTIALS automatically
        credentials = service_account.Credentials.from_service_account_file(
            settings.google_application_credentials
        )

        self.client = tts.TextToSpeechAsyncClient(
            credentials=credentials
        )

    async def synthesize_streaming(
        self,
        text_stream: AsyncGenerator[str, None],
        websocket: WebSocket,
    ) -> int:

        total_bytes = 0
        buffer = ""

        async for token in text_stream:
            buffer += token

            should_flush = (
                len(buffer) > 200
                or any(
                    buffer.rstrip().endswith(mark)
                    for mark in (".", "?", "!")
                )
            )

            if not should_flush:
                continue

            payload = buffer.strip()
            buffer = ""

            if not payload:
                continue

            chunk = await self._synthesize_chunk(payload)

            if chunk:
                await websocket.send_bytes(chunk)
                total_bytes += len(chunk)

        # Flush remaining text
        if buffer.strip():
            chunk = await self._synthesize_chunk(
                buffer.strip()
            )

            if chunk:
                await websocket.send_bytes(chunk)
                total_bytes += len(chunk)

        await websocket.send_json({"type": "audio_stream_end", "total_bytes": total_bytes})

        return total_bytes

    async def _synthesize_chunk(
        self,
        text: str,
    ) -> bytes:

        response = await self.client.synthesize_speech(
            request=tts.SynthesizeSpeechRequest(
                input=tts.SynthesisInput(text=text),
                voice=tts.VoiceSelectionParams(
                    language_code="en-US",
                    name=self.voice_name,
                ),
                audio_config=tts.AudioConfig(
                    audio_encoding=tts.AudioEncoding.MP3,
                ),
            )
        )

        return response.audio_content
    
    async def synthesize_streaming_full(
        self,
        text_stream,
        websocket,
    ):
        full_text = ""

        async for token in text_stream:
            full_text += token

        audio = await self._synthesize_chunk(full_text)

        await websocket.send_bytes(audio)

        return len(audio)