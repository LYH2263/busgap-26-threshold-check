"""纯例程测试：六种非法组合逐一核对字段名与统一用词；合法边值放行。

字段命名约定（与线路页同一套用词）：
    planned_headway_min -> 班距计划
    bunch_threshold     -> 近车阈
    large_threshold     -> 疏车阈
"""
from __future__ import annotations

import pytest

from app.services.line_validation import (
    FIELD_BUNCH,
    FIELD_LARGE,
    FIELD_PLANNED,
    LABEL_BUNCH,
    LABEL_LARGE,
    LABEL_PLANNED,
    error_fields,
    validate_line_params,
)


@pytest.mark.parametrize(
    "planned,bunch,large,bad_field,bad_label,phrase",
    [
        # 1) 近车阈 == 班距计划（开区间上界，非法）
        (8.0, 8.0, 15.0, FIELD_BUNCH, LABEL_BUNCH, "不能等于班距计划"),
        # 2) 近车阈 > 班距计划（即「近车大于等于班距」的大于分支，直插必败）
        (8.0, 9.0, 15.0, FIELD_BUNCH, LABEL_BUNCH, "必须小于班距计划"),
        # 3) 疏车阈 == 班距计划（严格大于，等号非法）
        (8.0, 3.0, 8.0, FIELD_LARGE, LABEL_LARGE, "不能等于班距计划"),
        # 4) 疏车阈 < 班距计划
        (8.0, 3.0, 7.0, FIELD_LARGE, LABEL_LARGE, "必须大于班距计划"),
        # 5) 班距计划非正
        (0.0, 3.0, 15.0, FIELD_PLANNED, LABEL_PLANNED, "必须大于 0"),
        (-4.0, 3.0, 15.0, FIELD_PLANNED, LABEL_PLANNED, "必须大于 0"),
        # 6) 近车阈非正
        (8.0, 0.0, 15.0, FIELD_BUNCH, LABEL_BUNCH, "必须大于 0"),
        (8.0, -2.0, 15.0, FIELD_BUNCH, LABEL_BUNCH, "必须大于 0"),
    ],
)
def test_illegal_combos_name_the_exact_field(planned, bunch, large, bad_field, bad_label, phrase):
    errors = validate_line_params(planned, bunch, large)
    assert errors, f"({planned},{bunch},{large}) 应判非法"
    hit = next((e for e in errors if e.field == bad_field), None)
    assert hit is not None, f"应点名字段 {bad_field}，实际点名 {error_fields(errors)}"
    assert hit.label == bad_label
    assert phrase in hit.message
    # 提示中出现的字段名必须与线路页表头同一套用词
    assert bad_label in hit.message


def test_seed_params_are_valid():
    # B12 的 8/3/15 合法
    assert not validate_line_params(8.0, 3.0, 15.0)


def test_legal_edge_1_8_9():
    # 围绕班距计划 8 的合法边：近车阈 1（开区间内，>0）、疏车阈 9（严格大于 8）
    assert validate_line_params(8.0, 1.0, 9.0) == []
    # 近车阈贴着 0 但仍为正，同样合法
    assert validate_line_params(1.0, 0.5, 1.5) == []


def test_8_8_rejected():
    # 近车阈 8 等于班距 8：不可
    errors = validate_line_params(8.0, 8.0, 9.0)
    assert error_fields(errors) == [FIELD_BUNCH]


def test_nan_and_strings_rejected():
    assert validate_line_params("8", 3.0, 15.0)
    assert validate_line_params(float("nan"), 3.0, 15.0)
    assert validate_line_params(8.0, 3.0, None)
