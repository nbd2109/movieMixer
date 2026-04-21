"""Router /health — liveness check."""

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    repo = request.app.state.repository
    try:
        count = await run_in_threadpool(repo.count_all)
        return {"status": "ok", "movies_in_db": count}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
