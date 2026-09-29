"""线路三参（班距计划 / 近车阈 / 疏车阈）的唯一校验例程。

创建线路与改写线路都必须调用 :func:`validate_line_params`；
库侧另有同名 CHECK 约束兜底（见 migrations/0001_line_param_checks.sql）。

规则：
  * 班距计划 planned_headway_min 严格大于 0；
  * 近车阈 bunch_threshold 落在开区间 (0, 班距计划) 内；
  * 疏车阈 large_threshold 严格大于班距计划。

失败时回包中的 field 与线路页校验提示共用同一套键名与中文用词，
前端镜像见 frontend/src/lineValidation.ts。
"""
from __future__ import annotations

import math
from typing import Any

FIELD_PLANNED = "planned_headway_min"
FIELD_BUNCH = "bunch_threshold"
FIELD_LARGE = "large_threshold"

# 字段键 -> 线路页统一用词
FIELD_LABELS: dict[str, str] = {
    FIELD_PLANNED: "班距计划",
    FIELD_BUNCH: "近车阈",
    FIELD_LARGE: "疏车阈",
}


class LineParamsError(ValueError):
    """三参校验失败：errors 为 [{field, label, message}, ...]。"""

    def __init__(self, errors: list[dict[str, str]]):
        self.errors = errors
        super().__init__("; ".join(e["message"] for e in errors))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def validate_line_params(
    planned_headway_min: Any,
    bunch_threshold: Any,
    large_threshold: Any,
) -> list[dict[str, str]]:
    """返回校验错误列表；空列表表示通过。任一字段非有限数也按该字段记一条。"""
    raw = {
        FIELD_PLANNED: planned_headway_min,
        FIELD_BUNCH: bunch_threshold,
        FIELD_LARGE: large_threshold,
    }
    values: dict[str, float] = {}
    errors: list[dict[str, str]] = []
    for field, value in raw.items():
        if not _is_number(value):
            errors.append({
                "field": field,
                "label": FIELD_LABELS[field],
                "message": f"{FIELD_LABELS[field]}（分钟）必须是有限数字。",
            })
        else:
            values[field] = float(value)
    if errors:
        return errors

    planned = values[FIELD_PLANNED]
    bunch = values[FIELD_BUNCH]
    large = values[FIELD_LARGE]

    if planned <= 0:
        errors.append({
            "field": FIELD_PLANNED,
            "label": FIELD_LABELS[FIELD_PLANNED],
            "message": f"班距计划（分钟）必须大于 0，当前为 {planned:g}。",
        })
    if bunch <= 0:
        errors.append({
            "field": FIELD_BUNCH,
            "label": FIELD_LABELS[FIELD_BUNCH],
            "message": f"近车阈（分钟）必须大于 0，当前为 {bunch:g}。",
        })
    elif bunch >= planned:
        # 近车阈必须落在开区间 (0, 班距计划)：等于、大于班距皆非法
        errors.append({
            "field": FIELD_BUNCH,
            "label": FIELD_LABELS[FIELD_BUNCH],
            "message": (
                f"近车阈必须小于班距计划（开区间 (0, 班距计划)），"
                f"当前近车阈 {bunch:g}、班距计划 {planned:g}。"
            ),
        })
    if large <= planned:
        # 疏车阈严格大于班距计划：等于、小于班距皆非法
        errors.append({
            "field": FIELD_LARGE,
            "label": FIELD_LABELS[FIELD_LARGE],
            "message": (
                f"疏车阈必须严格大于班距计划，当前疏车阈 {large:g}、班距计划 {planned:g}。"
            ),
        })
    return errors


def ensure_line_params(planned_headway_min: Any, bunch_threshold: Any, large_threshold: Any) -> None:
    """校验失败直接抛 :class:`LineParamsError`，供创建 / 改写接口共用。"""
    errors = validate_line_params(planned_headway_min, bunch_threshold, large_threshold)
    if errors:
        raise LineParamsError(errors)
