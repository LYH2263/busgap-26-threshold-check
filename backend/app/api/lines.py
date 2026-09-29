from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Line
from app.services.line_validation import ensure_line_params

router = APIRouter(prefix="/lines", tags=["lines"])


class LineCreate(BaseModel):
    code: str
    name: str
    planned_headway_min: float
    bunch_threshold: float
    large_threshold: float


class LineUpdate(BaseModel):
    # 改写只动三参（名称可选一并改），编码不可改
    name: str | None = None
    planned_headway_min: float
    bunch_threshold: float
    large_threshold: float


def _serialize(r: Line) -> dict:
    return {"id": r.id, "code": r.code, "name": r.name,
            "planned_headway_min": r.planned_headway_min,
            "bunch_threshold": r.bunch_threshold,
            "large_threshold": r.large_threshold}


@router.get("")
def list_lines(db: Session = Depends(get_db)):
    rows = db.scalars(select(Line).order_by(Line.id)).all()
    return [_serialize(r) for r in rows]


@router.post("", status_code=201)
def create_line(body: LineCreate, db: Session = Depends(get_db)):
    # 进库前先走共享例程；失败抛 LineParamsError -> 400，带字段名
    ensure_line_params(body.planned_headway_min, body.bunch_threshold, body.large_threshold)
    line = Line(code=body.code, name=body.name,
                planned_headway_min=body.planned_headway_min,
                bunch_threshold=body.bunch_threshold,
                large_threshold=body.large_threshold)
    db.add(line)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"线路编码 {body.code} 已存在")
    db.refresh(line)
    return _serialize(line)


@router.put("/{line_id}")
def update_line(line_id: int, body: LineUpdate, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(404, "线路不存在")
    # 先校验、后赋值：被拒时 ORM 对象与库中数字都保持改前，历史报告不受影响
    ensure_line_params(body.planned_headway_min, body.bunch_threshold, body.large_threshold)
    if body.name is not None:
        line.name = body.name
    line.planned_headway_min = body.planned_headway_min
    line.bunch_threshold = body.bunch_threshold
    line.large_threshold = body.large_threshold
    try:
        db.commit()
    except IntegrityError:
        # 库侧约束 / 触发器兜底命中（正常已被共享例程拦下，这里仅作防御）
        db.rollback()
        raise HTTPException(400, detail={"message": "库侧拒绝该线路参数组合", "errors": []})
    db.refresh(line)
    return _serialize(line)
