"""线路三参数共用校验例程：班距计划 / 近车阈 / 疏车阈。

创建线路、改写线路、以及检测引擎入口之前都调用本模块，
失败时点出的字段名与「线路」页校验提示使用同一套用词：

* 班距计划（planned_headway_min）必须大于 0；
* 近车阈（bunch_threshold）在开区间 (0, 班距计划) 内；
* 疏车阈（large_threshold）严格大于班距计划。

库侧 lines 表另有同名 CHECK 约束兜底，二者规则必须保持一致。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# API / 数据库字段名（回包中的 field 键，前端按此锚定提示）
FIELD_PLANNED = "planned_headway_min"
FIELD_BUNCH = "bunch_threshold"
FIELD_LARGE = "large_threshold"

# 与线路页统一的中文用词
LABEL_PLANNED = "班距计划"
LABEL_BUNCH = "近车阈"
LABEL_LARGE = "疏车阈"


@dataclass(frozen=True)
class LineParamError:
    field: str
    label: str
    message: str

    def to_dict(self) -> dict:
        return {"field": self.field, "label": self.label, "message": self.message}


def _is_number(value: object) -> bool:
    # bool 是 int 的子类，阈值不接受布尔值；NaN / Inf 一律拒绝
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_line_params(
    planned_headway_min: object,
    bunch_threshold: object,
    large_threshold: object,
) -> list[LineParamError]:
    """返回校验错误列表；空列表表示三参合法。"""
    errors: list[LineParamError] = []
    numbers: dict[str, float] = {}

    for field, label, value in (
        (FIELD_PLANNED, LABEL_PLANNED, planned_headway_min),
        (FIELD_BUNCH, LABEL_BUNCH, bunch_threshold),
        (FIELD_LARGE, LABEL_LARGE, large_threshold),
    ):
        if not _is_number(value):
            errors.append(LineParamError(field, label, f"{label}必须为数字"))
        else:
            numbers[field] = float(value)

    headway = numbers.get(FIELD_PLANNED)
    bunch = numbers.get(FIELD_BUNCH)
    large = numbers.get(FIELD_LARGE)

    # 单边规则
    if headway is not None and headway <= 0:
        errors.append(LineParamError(FIELD_PLANNED, LABEL_PLANNED,
                                     f"{LABEL_PLANNED}必须大于 0（当前为 {headway:g} 分钟）"))
    if bunch is not None and bunch <= 0:
        errors.append(LineParamError(FIELD_BUNCH, LABEL_BUNCH,
                                     f"{LABEL_BUNCH}必须大于 0（开区间下界，当前为 {bunch:g} 分钟）"))

    # 交叉规则仅在班距计划为正时才有意义，避免班距非正时刷出误导性连带错误
    if headway is not None and headway > 0:
        if bunch is not None:
            if bunch == headway:
                errors.append(LineParamError(FIELD_BUNCH, LABEL_BUNCH,
                                             f"{LABEL_BUNCH}必须严格小于{LABEL_PLANNED}，不能等于{LABEL_PLANNED}"
                                             f"（均为 {bunch:g} 分钟）"))
            elif bunch > headway:
                errors.append(LineParamError(FIELD_BUNCH, LABEL_BUNCH,
                                             f"{LABEL_BUNCH}必须小于{LABEL_PLANNED}"
                                             f"（当前近车阈 {bunch:g} ≥ 班距计划 {headway:g}）"))
        if large is not None:
            if large == headway:
                errors.append(LineParamError(FIELD_LARGE, LABEL_LARGE,
                                             f"{LABEL_LARGE}必须严格大于{LABEL_PLANNED}，不能等于{LABEL_PLANNED}"
                                             f"（均为 {large:g} 分钟）"))
            elif large < headway:
                errors.append(LineParamError(FIELD_LARGE, LABEL_LARGE,
                                             f"{LABEL_LARGE}必须大于{LABEL_PLANNED}"
                                             f"（当前疏车阈 {large:g} ≤ 班距计划 {headway:g}）"))

    return errors


def is_valid_line_params(
    planned_headway_min: object,
    bunch_threshold: object,
    large_threshold: object,
) -> bool:
    return not validate_line_params(planned_headway_min, bunch_threshold, large_threshold)


def errors_to_dicts(errors: list[LineParamError]) -> list[dict]:
    return [e.to_dict() for e in errors]


def error_fields(errors: list[LineParamError]) -> list[str]:
    return [e.field for e in errors]
