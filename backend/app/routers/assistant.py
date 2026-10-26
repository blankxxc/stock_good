import asyncio
from threading import BoundedSemaphore

import anyio

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from backend.app.services.ai_assistant import (
    ChatRequest, build_context, providers, selected_provider, stream_completion,
)
from backend.app.services.auth_service import configured_allowed_origins
from backend.app.services.ai_planner import PlanError, PlanRequest, generate_plan, prepare_catalog
from backend.app.services.ai_prediction import PredictionRequest, build_prediction_context, generate_prediction

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
_slots = BoundedSemaphore(4)


async def while_connected(request: Request, operation, *, disconnect_error=None):
    """Stop an upstream await when its caller leaves, before releasing capacity."""
    error = disconnect_error or HTTPException(499, "请求已取消。")
    if await request.is_disconnected():
        raise error

    stopped = False

    async def watch():
        while not stopped:
            if await request.is_disconnected():
                return
            await asyncio.sleep(0.1)

    work = asyncio.create_task(operation())
    disconnected = asyncio.create_task(watch())
    try:
        done, _ = await asyncio.wait((work, disconnected), return_when=asyncio.FIRST_COMPLETED)
        if disconnected in done:
            raise error
        return await work
    finally:
        stopped = True
        for task in (work, disconnected):
            if not task.done():
                task.cancel()
        with anyio.CancelScope(shield=True):
            await asyncio.gather(work, disconnected, return_exceptions=True)


class AssistantStreamingResponse(StreamingResponse):
    """The response owns its slot even if body iteration never starts."""
    async def __call__(self, scope, receive, send):
        try:
            version = tuple(map(int, scope.get("asgi", {}).get("spec_version", "2.0").split(".")))
            if version >= (2, 4):
                await while_connected(Request(scope, receive),
                    lambda: super(AssistantStreamingResponse, self).__call__(scope, receive, send),
                    disconnect_error=ClientDisconnect())
            else:
                await super().__call__(scope, receive, send)
        finally:
            try:
                with anyio.CancelScope(shield=True):
                    await self.body_iterator.aclose()
            finally:
                _slots.release()


@router.get("/config")
def config():
    return JSONResponse({"providers": providers()}, headers={"Cache-Control": "no-store"})


def validate_connection(request: Request, api_key: str, provider: str) -> str:
    origin = request.headers.get("origin")
    if origin and origin not in configured_allowed_origins():
        raise HTTPException(403, "请求来源不受支持。")
    key = api_key.strip()
    if not 8 <= len(key) <= 512 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise HTTPException(400, "请填写有效的 API Key。")
    try:
        selected_provider(provider)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    return key


@router.post("/plan")
async def plan(body: PlanRequest, request: Request, x_ai_api_key: str = Header(default="")):
    key = validate_connection(request, x_ai_api_key, body.provider)
    if not _slots.acquire(blocking=False):
        raise HTTPException(429, "助手正在处理其他请求，请稍后重试。", headers={"Retry-After": "5"})
    try:
        try:
            catalog = await run_in_threadpool(prepare_catalog, body.task)
        except Exception:
            raise HTTPException(503, "本地数据目录暂不可用，请更新数据后重试。") from None
        result = await while_connected(request, lambda: generate_plan(body, key, catalog))
        return JSONResponse(result, headers={"Cache-Control": "no-store"})
    except PlanError as exc:
        raise HTTPException(exc.status, str(exc), headers={"Cache-Control": "no-store"}) from None
    finally:
        _slots.release()


@router.post("/predict")
async def predict(body: PredictionRequest, request: Request, x_ai_api_key: str = Header(default="")):
    key = validate_connection(request, x_ai_api_key, body.provider)
    if not _slots.acquire(blocking=False):
        raise HTTPException(429, "助手正在处理其他请求，请稍后重试。", headers={"Retry-After": "5"})
    try:
        try:
            context = await run_in_threadpool(build_prediction_context, body)
        except PlanError:
            raise
        except Exception:
            raise HTTPException(503, "本地预测数据暂不可用，请更新数据后重试。") from None
        result = await while_connected(request, lambda: generate_prediction(body, key, context))
        return JSONResponse(result, headers={"Cache-Control": "no-store"})
    except PlanError as exc:
        raise HTTPException(exc.status, str(exc), headers={"Cache-Control": "no-store"}) from None
    finally:
        _slots.release()


@router.post("/chat")
async def chat(body: ChatRequest, request: Request, x_ai_api_key: str = Header(default="")):
    key = validate_connection(request, x_ai_api_key, body.provider)
    if not _slots.acquire(blocking=False):
        raise HTTPException(429, "助手正在处理其他分析，请稍后重试。", headers={"Retry-After": "5"})
    try:
        context = await run_in_threadpool(build_context, body)
    except BaseException as exc:
        _slots.release()
        if isinstance(exc, Exception):
            raise HTTPException(503, "本地研究数据暂不可用，请更新数据后重试。") from None
        raise

    return AssistantStreamingResponse(stream_completion(body, key, context), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
