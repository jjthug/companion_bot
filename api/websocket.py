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
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from observability.tracing import tracer
from observability.metrics import (
    ws_connections,
    active_sessions,
    turn_counter,
    turn_e2e_latency,
    error_counter,
)

router = APIRouter()


def _json_error(code: str, message: str) -> dict:
    return {"type": "error", "code": code, "message": message}


@router.websocket("/ws/session/{user_id}")
async def websocket_connect(websocket: WebSocket, user_id: str, token: str = Query(...)):
    # try:
    #     validate_jwt_token(token, user_id, settings.jwt_secret, settings.jwt_algorithm)
    # except AuthError:
    #     await websocket.close(code=4001)
    #     return

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

    ws_connections.add(1)
    active_sessions.add(1, {"model": settings.llm_model})

    await websocket.send_json({"type": "session_ready", "session_id": session_id})

    turn_index = 0
    ended_reason = None              # initialized before any branch references it
    session_start = time.monotonic()

    try:
        with tracer.start_as_current_span("companion.session", kind=trace.SpanKind.SERVER) as session_span:
            session_span.set_attribute("user.id", user_id)
            session_span.set_attribute("enduser.id", user_id)
            session_span.set_attribute("session.id", session_id)

            while True:
                try:
                    message = await asyncio.wait_for(websocket.receive(), timeout=600)
                except asyncio.TimeoutError:
                    ended_reason = "timeout"
                    break

                if message.get("type") == "websocket.disconnect":
                    ended_reason = "disconnect"
                    break

                # Determine input type; skip frames that carry neither text nor bytes
                transcript = None
                audio_bytes = None
                if "text" in message and message["text"] is not None:
                    try:
                        data = json.loads(message["text"])
                    except json.JSONDecodeError:
                        logger.warning("websocket.bad_json", user_id=user_id, session_id=session_id)
                        error_counter.add(1, {"error.type": "bad_json", "stage": "input"})
                        await websocket.send_json(_json_error("bad_request", "Malformed message."))
                        continue
                    transcript = data.get("content")
                elif "bytes" in message and message["bytes"] is not None:
                    audio_bytes = message["bytes"]
                else:
                    # control frame or empty payload — nothing to process
                    continue

                if not transcript and not audio_bytes:
                    continue

                user_profile = {}
                seven_day_summary = "Nothing"

                session_turns = []
                if transcript:
                    session_turns.append({"role": "user", "content": transcript})

                system_prompt = build_system_prompt(user_profile, session_turns, seven_day_summary)

                # ---- one turn ----
                turn_start = time.monotonic()
                turn_status = "ok"
                response_chunks: list[str] = []

                # Bind turn to logs so each turn's lines are distinguishable
                # within the single session span.
                with tracer.start_as_current_span("companion.turn") as turn_span:
                    turn_span.set_attribute("session.id", session_id)
                    turn_span.set_attribute("turn.index", turn_index)
                    turn_span.set_attribute("turn.input_type", "audio" if audio_bytes else "text")

                    # Capture per-turn locals explicitly so the generator
                    # doesn't close over mutated loop state.
                    _prompt = system_prompt
                    _turns = session_turns
                    _audio = audio_bytes

                    async def llm_stream(_prompt=_prompt, _turns=_turns, _audio=_audio):
                        async for part in llm_service.generate_streaming(
                            system_prompt=_prompt,
                            conversation_history=_turns,
                            audio_bytes=_audio,
                            audio_mime_type="audio/webm",
                        ):
                            response_chunks.append(part)
                            yield part

                    try:
                        total_bytes = await tts_service.synthesize_streaming(llm_stream(), websocket)
                        turn_span.set_attribute("tts.total_bytes", total_bytes or 0)
                        turn_span.set_attribute("llm.response_chars", sum(len(c) for c in response_chunks))
                    except WebSocketDisconnect:
                        raise  # handled by outer handler; ends the session
                    except Exception as exc:
                        turn_status = "error"
                        turn_span.record_exception(exc)
                        turn_span.set_status(Status(StatusCode.ERROR))
                        error_counter.add(1, {"error.type": type(exc).__name__, "stage": "turn"})
                        logger.error(
                            "websocket.turn_error",
                            user_id=user_id, session_id=session_id, turn=turn_index,
                            error_type=type(exc).__name__, error_msg=str(exc),
                        )
                        await websocket.send_json(
                            _json_error("server_error", "I'm having a little trouble right now. Please try again in a moment.")
                        )

                    turn_e2e_ms = (time.monotonic() - turn_start) * 1000
                    turn_e2e_latency.record(turn_e2e_ms, {"model": settings.llm_model, "status": turn_status})
                    turn_counter.add(1, {"model": settings.llm_model, "status": turn_status})
                    turn_span.set_attribute("turn.e2e_latency_ms", int(turn_e2e_ms))

                session_span.add_event("turn", {"turn": turn_index, "status": turn_status})
                logger.info(
                    "websocket.turn_complete",
                    user_id=user_id, session_id=session_id, turn=turn_index,
                    status=turn_status, e2e_latency_ms=int(turn_e2e_ms),
                )
                turn_index += 1

            session_span.set_attribute("session.turn_count", turn_index)
            session_span.set_attribute("session.ended_reason", ended_reason or "unknown")

    except WebSocketDisconnect:
        ended_reason = ended_reason or "disconnect"
    except Exception as exc:
        ended_reason = ended_reason or "error"
        error_counter.add(1, {"error.type": type(exc).__name__, "stage": "session"})
        logger.error(
            "websocket.error",
            user_id=user_id, session_id=session_id,
            error_type=type(exc).__name__, error_msg=str(exc),
        )
        try:
            await websocket.send_json(_json_error("server_error", "I'm having a little trouble right now. Please try again in a moment."))
        except Exception:
            pass
    finally:
        duration = time.monotonic() - session_start
        ws_connections.add(-1)
        active_sessions.add(-1, {"model": settings.llm_model})
        logger.info(
            "websocket.cleanup",
            user_id=user_id, session_id=session_id,
            ended_reason=ended_reason or "unknown",
            turn_count=turn_index, duration_seconds=round(duration, 2),
        )