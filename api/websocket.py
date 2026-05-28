from fastapi import APIRouter, WebSocket, Query, WebSocketDisconnect
from observability.logging import logger
from prompt.builder import build_system_prompt
from auth.auth import validate_jwt_token, AuthError
import asyncio
import json
import time
from service.llm_service import LLMService
from service.tts_service import TTSService
from config import settings
from uuid import uuid4

router = APIRouter()

def _json_error(code: str, message: str) -> dict:
    return {"type": "error", "code": code, "message": message}


@router.websocket("/ws/session/{user_id}")
async def websocket_connect(websocket: WebSocket, user_id: str, token: str = Query(...)):
    try:
        validate_jwt_token(token, user_id, settings.jwt_secret, settings.jwt_algorithm)
    except AuthError:
        await websocket.close(code=4001)
        return
    
    llm_service = LLMService(
        api_key=settings.gemini_api_key,
        model_name=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )

    tts_service = TTSService(voice_name=settings.tts_voice)

    session_id = str(uuid4())

    await websocket.accept()

    remote_addr = getattr(websocket.client, "host", "unknown") if websocket.client else "unknown"
    logger.info("websocket.connected", user_id=user_id, session_id=session_id, remote_addr=remote_addr)

    await websocket.send_json({"type": "session_ready", "session_id": session_id})

    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=600)
            except asyncio.TimeoutError:
                ended_reason = "timeout"
                break

            if message.get("type") == "websocket.disconnect":
                break

            if "text" in message:
                data= json.loads(message["text"])
                transcript = data.get("content")
                audio_bytes=None
                input_type="text"
            elif "bytes" in message:
                audio_bytes=message["bytes"]
                transcript=None
                input_type="audio"

            user_profile={}
            seven_day_summary="Nothing"

            response_chunks: list[str] = []
            system_prompt = build_system_prompt(user_profile, session_turns, seven_day_summary)
            session_turns=[{"role": "user", "content": transcript}]

            async def llm_stream():
                async for part in llm_service.generate_streaming(system_prompt, session_turns):
                    response_chunks.append(part)
                    yield part

            total_bytes = await tts_service.synthesize_streaming(llm_stream(), websocket)
    except WebSocketDisconnect:
        ended_reason = ended_reason or "disconnect"
    except Exception as exc:
        logger.error("websocket.error", user_id=user_id, session_id=session_id, error_type=type(exc).__name__, error_msg=str(exc))
        try:
            await websocket.send_json(_json_error("server_error", "I’m having a little trouble right now. Please try again in a moment."))
        except Exception:
            pass
    finally:
        logger.info("cleaned up")