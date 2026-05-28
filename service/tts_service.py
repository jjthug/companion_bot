from google.cloud import texttospeech_v1beta1 as tts
from collections.abc import AsyncGenerator
from fastapi import WebSocket

class TTSService:
    def __init__(self, voice_name: str = "en-US-Journey-F"):
        self.voice_name = voice_name
        self.client = tts.TextToSpeechAsyncClient()
        self.streaming_config = tts.StreamingSynthesizeConfig(
            voice=tts.VoiceSelectionParams(language_code="en-US", name=voice_name),
        )

    async def synthesize_streaming(self, text_stream: AsyncGenerator[str,None], websocket: WebSocket) -> int:
        total_bytes = 0
        buffer = ""
        async for token in text_stream:
            buffer += token
            should_flush = len(buffer) > 200 or any(buffer.rstrip().endswith(mark) for mark in (".", "?", "!"))
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
        
        if buffer.strip():
            chunk = await self._synthesize_chunk(buffer.strip())
            if chunk:
                await websocket.send_bytes(chunk)
                total_bytes += len(chunk)
        return total_bytes
        
    
    async def _synthesize_chunk(self, text: str) -> bytes:
        if self.client is None or tts is None:
            return text.encode("utf-8")

        try:
            response = await self.client.synthesize_speech(
                input=tts.SynthesisInput(text=text),
                voice=tts.VoiceSelectionParams(language_code="en-US", name=self.voice_name),
                audio_config=tts.AudioConfig(audio_encoding=tts.AudioEncoding.MP3),
            )
            return getattr(response, "audio_content", b"") or b""
        except Exception:
            return text.encode("utf-8")