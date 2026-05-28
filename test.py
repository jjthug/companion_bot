import asyncio
import json
from pathlib import Path
import websockets

WS_URL = "ws://127.0.0.1:8000/ws/session/test-user?token=test"
AUDIO_FILE = "shortstory.webm"
OUTPUT_DIR = Path("tts_chunks")


async def receive_messages(websocket):
    OUTPUT_DIR.mkdir(exist_ok=True)
    chunk_index = 0
    while True:
        try:
            msg = await websocket.recv()
            if isinstance(msg, bytes):
                filename = OUTPUT_DIR / f"chunk_{chunk_index:03d}.mp3"
                with open(filename, "wb") as f:
                    f.write(msg)
                print(f"[SERVER AUDIO] saved {filename} ({len(msg)} bytes)")
                chunk_index += 1
            else:
                try:
                    data = json.loads(msg)
                    if data.get("type") == "audio_stream_end":
                        print(
                            f"[SERVER] Stream complete — "
                            f"{chunk_index} chunks, "
                            f"{data.get('total_bytes', '?')} total bytes"
                        )
                        return  # All chunks received, exit cleanly
                    else:
                        print(f"[SERVER TEXT] {msg}")
                except json.JSONDecodeError:
                    print(f"[SERVER TEXT] {msg}")
        except websockets.ConnectionClosed:
            print("Connection closed")
            break
        except asyncio.CancelledError:
            break


async def send_text_message(websocket):
    payload = {
        "content": (
            "Please summarize the attached audio "
            "and respond conversationally."
        )
    }
    await websocket.send(json.dumps(payload))
    print("[CLIENT] Sent text prompt")


async def send_audio(websocket):
    with open(AUDIO_FILE, "rb") as f:
        audio_bytes = f.read()
    await websocket.send(audio_bytes)
    print(f"[CLIENT] Sent audio file ({len(audio_bytes)} bytes)")


async def main():
    async with websockets.connect(
        WS_URL,
        max_size=50 * 1024 * 1024,
    ) as websocket:
        initial = await websocket.recv()
        print("[SERVER]", initial)

        receiver_task = asyncio.create_task(receive_messages(websocket))

        await send_audio(websocket)

        # Wait for stream_end signal or a timeout as fallback
        try:
            await asyncio.wait_for(receiver_task, timeout=60)
        except asyncio.TimeoutError:
            print("[CLIENT] Timeout reached before stream_end signal")
            receiver_task.cancel()
            try:
                await receiver_task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    asyncio.run(main())