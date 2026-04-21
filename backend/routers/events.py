"""Router /api/events — telemetría desde el frontend."""

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import Response
from slowapi import Limiter
from slowapi.util import get_remote_address

logger  = logging.getLogger("cinemix")
router  = APIRouter(prefix="/api")
limiter = Limiter(key_func=get_remote_address)


@router.post("/events")
@limiter.limit("60/minute")
async def collect_event(request: Request):
    """
    Recibe eventos de telemetría desde track.js vía navigator.sendBeacon.
    Persiste en el log de uvicorn — listo para conectar a PostHog/Mixpanel.
    """
    try:
        body  = await request.body()
        event = json.loads(body)
        logger.info(
            "EVENT %s %s",
            event.get("event", "unknown"),
            json.dumps(event.get("properties", {})),
        )
    except Exception:
        pass
    return Response(status_code=204)
