from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Line
from app.services.line_validation import errors_to_dicts, validate_line_params

router = APIRouter(prefix="/lines", tags=["lines"])


class LineParams(BaseModel):
    planned_headway_min: float
    bunch_threshold: float
    large_threshold: float


class LineCreate(LineParams):
    code: str
    name: str


class LineUpdate(LineParams):
    pass


def _line_payload(r: Line) -> dict:
    return {"id": r.id, "code": r.code, "name": r.name,
            "planned_headway_min": r.planned_headway_min,
            "bunch_threshold": r.bunch_threshold,
            "large_threshold": r.large_threshold}


def _require_valid_params(planned: float, bunch: float, large: float) -> None:
    """创建与改写共用的唯一校验入口；失败回 422 且字段名与线路页同词。"""
    errors = validate_line_params(planned, bunch, large)
    if errors:
        raise HTTPException(status_code=422, detail={
            "message": "线路参数校验未通过",
            "errors": errors_to_dicts(errors),
        })


@router.get("")
def list_lines(db: Session = Depends(get_db)):
    rows = db.scalars(select(Line).order_by(Line.id)).all()
    return [_line_payload(r) for r in rows]


@router.post("", status_code=201)
def create_line(payload: LineCreate, db: Session = Depends(get_db)):
    # 进库（也即未来的任何检测）前先过共用例程
    _require_valid_params(payload.planned_headway_min,
                          payload.bunch_threshold,
                          payload.large_threshold)
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=422, detail={
            "message": "线路参数校验未通过",
            "errors": [{"field": "code", "label": "编码", "message": "编码不能为空"}],
        })
    if db.scalar(select(Line.id).where(Line.code == code)):
        raise HTTPException(status_code=409, detail=f"线路编码 {code} 已存在")

    line = Line(code=code, name=payload.name.strip() or code,
                planned_headway_min=payload.planned_headway_min,
                bunch_threshold=payload.bunch_threshold,
                large_threshold=payload.large_threshold)
    db.add(line)
    db.commit()
    db.refresh(line)
    return _line_payload(line)


@router.put("/{line_id}")
def update_line(line_id: int, payload: LineUpdate, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="线路不存在")

    # 先校验、后写库：被拒时行内数字保持改前值，历史报告也不会被改写动作触及。
    _require_valid_params(payload.planned_headway_min,
                          payload.bunch_threshold,
                          payload.large_threshold)

    line.planned_headway_min = payload.planned_headway_min
    line.bunch_threshold = payload.bunch_threshold
    line.large_threshold = payload.large_threshold
    db.commit()
    db.refresh(line)
    return _line_payload(line)
