import requests
from typing import Generator


def stream_chat(base_url: str, payload: dict) -> Generator[str, None, None]:
    """
    Streams model output token-by-token from FastAPI backend.
    Handles:
      - partial UTF-8 chunks
      - disconnect errors
      - gracefully finishes upon end of stream
    """

    url = f"{base_url}/api/v1/chat/stream"

    try:
        with requests.post(url, json=payload, stream=True, timeout=300) as resp:
            resp.raise_for_status()

            buffer = b""

            # Iterate raw chunks
            for chunk in resp.iter_content(chunk_size=512):
                if not chunk:
                    continue

                # Accumulate in buffer until a full UTF-8 sequence is available
                buffer += chunk

                try:
                    decoded = buffer.decode("utf-8")
                    buffer = b""  # reset buffer
                    yield decoded
                except UnicodeDecodeError:
                    # Partial UTF-8 sequence → wait for more bytes
                    continue

    except requests.exceptions.RequestException as exc:
        yield f"[Stream Error] {str(exc)}"
    except Exception as exc:
        yield f"[Unexpected Error] {str(exc)}"

