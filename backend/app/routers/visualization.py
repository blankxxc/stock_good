from threading import BoundedSemaphore

from fastapi import APIRouter, HTTPException, Response

from backend.app.services.visualization import SeriesRequest, query_series, visualization_metadata

router = APIRouter(prefix="/api/visualization", tags=["visualization"])
_slots = BoundedSemaphore(2)


@router.get("")
def metadata(response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        return visualization_metadata()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/series")
def series(body: SeriesRequest, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if not _slots.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="图表数据正在加载，请稍后重试。", headers={"Retry-After": "2"})
    try:
        return query_series(body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="行情或因子文件暂不可用，请更新数据后重试。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        _slots.release()
