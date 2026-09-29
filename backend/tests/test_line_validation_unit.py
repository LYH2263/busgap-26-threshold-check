"""共享例程 validate_line_params 的纯单元测试：六种非法组合 + 边界。

字段名必须与线路页 / 接口回包同一套键：
planned_headway_min（班距计划）、bunch_threshold（近车阈）、large_threshold（疏车阈）。
"""
from app.services.line_validation import (
    FIELD_BUNCH,
    FIELD_LARGE,
    FIELD_PLANNED,
    validate_line_params,
)


def fields_of(planned, bunch, large):
    return {e["field"] for e in validate_line_params(planned, bunch, large)}


def test_valid_b12_seed_values():
    assert validate_line_params(8.0, 3.0, 15.0) == []


def test_bunch_equal_headway_is_illegal():
    # 近车等于班距：开区间 (0, 班距计划)，等号非法
    errs = validate_line_params(8.0, 8.0, 15.0)
    assert FIELD_BUNCH in {e["field"] for e in errs}
    assert FIELD_PLANNED not in {e["field"] for e in errs}
    assert FIELD_LARGE not in {e["field"] for e in errs}


def test_bunch_greater_than_headway_is_illegal():
    # 近车大于班距
    assert FIELD_BUNCH in fields_of(8.0, 9.0, 15.0)


def test_large_equal_headway_is_illegal():
    # 疏车等于班距
    assert FIELD_LARGE in fields_of(8.0, 3.0, 8.0)


def test_large_below_headway_is_illegal():
    # 疏车小于班距
    assert FIELD_LARGE in fields_of(8.0, 3.0, 7.0)


def test_headway_non_positive_is_illegal():
    # 班距非正（0 与负数）
    assert FIELD_PLANNED in fields_of(0.0, 3.0, 15.0)
    assert FIELD_PLANNED in fields_of(-8.0, 3.0, 15.0)


def test_bunch_non_positive_is_illegal():
    # 近车非正（0 与负数）
    assert FIELD_BUNCH in fields_of(8.0, 0.0, 15.0)
    assert FIELD_BUNCH in fields_of(8.0, -3.0, 15.0)


def test_six_required_illegal_combos_have_field_and_label():
    # 题面点名的六种非法，逐一核对字段键与中文用词
    cases = [
        ((8.0, 8.0, 15.0), FIELD_BUNCH, "近车阈"),
        ((8.0, 9.0, 15.0), FIELD_BUNCH, "近车阈"),
        ((8.0, 3.0, 8.0), FIELD_LARGE, "疏车阈"),
        ((8.0, 3.0, 7.0), FIELD_LARGE, "疏车阈"),
        ((0.0, 3.0, 15.0), FIELD_PLANNED, "班距计划"),
        ((8.0, 0.0, 15.0), FIELD_BUNCH, "近车阈"),
    ]
    for (planned, bunch, large), field, label in cases:
        errs = validate_line_params(planned, bunch, large)
        hit = [e for e in errs if e["field"] == field]
        assert hit, f"({planned},{bunch},{large}) 未报字段 {field}"
        assert hit[0]["label"] == label
        assert hit[0]["message"]


def test_boundary_edges_1_8_9_writable():
    # 合法边：班距 8、近车 1、疏车 9（近车取最小侧、疏车取紧贴班距上侧）
    assert validate_line_params(8.0, 1.0, 9.0) == []


def test_edge_8_8_not_writable():
    # 近车 8 与班距 8 相等，不可
    errs = validate_line_params(8.0, 8.0, 9.0)
    assert any(e["field"] == FIELD_BUNCH for e in errs)
