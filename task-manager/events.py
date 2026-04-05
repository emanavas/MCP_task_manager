import asyncio
from typing import Set, Dict

# Manage a set of subscriber queues so each SSE client receives broadcasts
_subscribers: Set[asyncio.Queue] = set()

def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.add(q)
    return q

def unsubscribe(q: asyncio.Queue) -> None:
    try:
        _subscribers.discard(q)
    except Exception:
        pass

def push_event(payload: Dict) -> None:
    # Put payload into every subscriber queue in a thread-safe manner
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None
    for q in list(_subscribers):
        try:
            if loop and loop.is_running():
                loop.call_soon_threadsafe(q.put_nowait, payload)
            else:
                # fallback: try put_nowait
                q.put_nowait(payload)
        except Exception:
            # drop subscriber on error
            try:
                _subscribers.discard(q)
            except Exception:
                pass
