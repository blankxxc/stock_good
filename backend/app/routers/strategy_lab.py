from threading import BoundedSemaphore

from fastapi import APIRouter, HTTPException, Response

from backend.app.services.strategy_lab import ExperimentRequest, lab_metadata, run_experiment

router = APIRouter(prefix="/api/strategy-lab", tags=["strategy-lab"])
_slots = BoundedSemaphore(2)


@router.get("")
def metadata(response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        return lab_metadata()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/run")
def run(body: ExperimentRequest, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if not _slots.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="已有实验正在计算，请稍后重试。", headers={"Retry-After": "5"})
    try:
        return run_experiment(body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        _slots.release()
