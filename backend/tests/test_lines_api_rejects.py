"""接口拒测（HTTP 层）：非法组合必须在进检测引擎前被拒。

覆盖：
* POST /lines 六种非法组合 -> 422，回包字段名与线路页同词；
* 合法边 1/8/9（近车阈/班距计划/疏车阈）可写，8/8（近车阈=班距）不可；
* PUT /lines/{id} 被拒时行内数字保持改前，历史报告不被清掉；
* 直插绕过 API 造成的脏线路，/reports/run 与 /reports/suggestions 拒绝、
  报告行数不变；时间轴不依赖三参，仍可出点（且不新增脏点）。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.models.models import BunchReport

pytestmark = pytest.mark.usefixtures("clean_db")


def _errors_of(res) -> dict[str, dict]:
    assert res.status_code == 422, res.text
    body = res.json()["detail"]
    assert body["message"]
    return {e["field"]: e for e in body["errors"]}


CREATE_BODY = {"code": "X1", "name": "测试线"}


@pytest.mark.parametrize(
    "planned,bunch,large,bad_field,bad_label",
    [
        (8.0, 8.0, 15.0, "bunch_threshold", "近车阈"),       # 近车等于班距
        (8.0, 9.0, 15.0, "bunch_threshold", "近车阈"),       # 近车大于班距（>= 班距直插必败）
        (8.0, 3.0, 8.0, "large_threshold", "疏车阈"),        # 疏车等于班距
        (8.0, 3.0, 7.0, "large_threshold", "疏车阈"),        # 疏车小于班距
        (0.0, 3.0, 15.0, "planned_headway_min", "班距计划"),  # 班距非正
        (-1.0, 3.0, 15.0, "planned_headway_min", "班距计划"),
        (8.0, 0.0, 15.0, "bunch_threshold", "近车阈"),       # 近车非正
        (8.0, -3.0, 15.0, "bunch_threshold", "近车阈"),
    ],
)
def test_create_rejects_six_illegal_combos(client: TestClient, planned, bunch, large, bad_field, bad_label):
    res = client.post("/api/lines", json={**CREATE_BODY,
                                      "planned_headway_min": planned,
                                      "bunch_threshold": bunch,
                                      "large_threshold": large})
    errs = _errors_of(res)
    assert bad_field in errs, f"应点名字段 {bad_field}，实际 {sorted(errs)}"
    assert errs[bad_field]["label"] == bad_label
    # 回包点名字段与线路页提示用词一致
    assert bad_label in errs[bad_field]["message"]
    # 被拒不得落库
    res2 = client.get("/api/lines")
    assert all(row["code"] != "X1" for row in res2.json())


def test_legal_edge_1_8_9_writable(client: TestClient):
    # 顺序：近车阈 1 / 班距计划 8 / 疏车阈 9
    res = client.post("/api/lines", json={"code": "E1", "name": "边线",
                                      "planned_headway_min": 8,
                                      "bunch_threshold": 1,
                                      "large_threshold": 9})
    assert res.status_code == 201, res.text
    saved = res.json()
    assert (saved["planned_headway_min"], saved["bunch_threshold"], saved["large_threshold"]) == (8.0, 1.0, 9.0)


def test_8_8_not_writable(client: TestClient):
    # 近车阈 = 班距计划 = 8
    res = client.post("/api/lines", json={"code": "E2", "name": "贴边线",
                                      "planned_headway_min": 8,
                                      "bunch_threshold": 8,
                                      "large_threshold": 9})
    errs = _errors_of(res)
    assert "bunch_threshold" in errs


def test_create_duplicate_code_conflicts(client: TestClient):
    body = {"code": "D1", "name": "一", "planned_headway_min": 8,
            "bunch_threshold": 3, "large_threshold": 15}
    assert client.post("/api/lines", json=body).status_code == 201
    res = client.post("/api/lines", json=body)
    assert res.status_code == 409


# ---------------------------------------------------------------- 改写


def test_update_happy_path(client: TestClient, b12):
    res = client.put(f"/api/lines/{b12.id}", json={"planned_headway_min": 10,
                                               "bunch_threshold": 4,
                                               "large_threshold": 16})
    assert res.status_code == 200, res.text
    got = client.get("/api/lines").json()[0]
    assert (got["planned_headway_min"], got["bunch_threshold"], got["large_threshold"]) == (10.0, 4.0, 16.0)


def test_update_rejected_keeps_old_numbers_and_reports(client: TestClient, b12):
    # 先跑一次合法检测，留下历史报告
    run = client.post(f"/api/reports/run?line_id={b12.id}")
    assert run.status_code == 200
    before = client.get("/api/reports").json()
    assert len(before) == 1

    # 改写为非法：近车阈 8 >= 班距 8
    res = client.put(f"/api/lines/{b12.id}", json={"planned_headway_min": 8,
                                               "bunch_threshold": 8,
                                               "large_threshold": 9})
    errs = _errors_of(res)
    assert "bunch_threshold" in errs

    # 页上数字保持改前 8/3/15
    got = next(r for r in client.get("/api/lines").json() if r["id"] == b12.id)
    assert (got["planned_headway_min"], got["bunch_threshold"], got["large_threshold"]) == (8.0, 3.0, 15.0)

    # 历史报告不被改写动作清掉
    after = client.get("/api/reports").json()
    assert len(after) == len(before) == 1
    assert after[0]["id"] == before[0]["id"]
    assert after[0]["events"] == before[0]["events"]


def test_update_missing_line_404(client: TestClient):
    res = client.put("/api/lines/9999", json={"planned_headway_min": 8,
                                          "bunch_threshold": 3,
                                          "large_threshold": 15})
    assert res.status_code == 404


# ------------------------------------------------- 进引擎前拦截（API 侧）


def test_engine_guard_blocks_illegal_line_object():
    # 直插脏数据的库侧验证在 test_db_direct_insert.py；
    # 这里直接验证检测入口的最后一道闸：非法线路对象在进引擎前抛 422。
    import pytest
    from fastapi import HTTPException

    from app.api.reports import _require_line_detectable
    from app.models.models import Line

    dirty = Line(id=42, code="Z9", name="脏线",
                 planned_headway_min=8.0, bunch_threshold=8.0, large_threshold=15.0)
    with pytest.raises(HTTPException) as exc:
        _require_line_detectable(dirty)
    assert exc.value.status_code == 422
    fields = {e["field"] for e in exc.value.detail["errors"]}
    assert "bunch_threshold" in fields


def test_rejected_writes_leave_reports_and_timeline_clean(client: TestClient, b12, db):
    # 合法线路先跑一次检测，留下基线报告
    run = client.post(f"/api/reports/run?line_id={b12.id}")
    assert run.status_code == 200
    base_count = db.scalar(select(func.count()).select_from(BunchReport))
    assert base_count == 1

    # 一串非法写入尝试（新建 + 改写）全部在进引擎前被拒
    for body in (
        {"code": "BAD", "name": "坏", "planned_headway_min": 0, "bunch_threshold": 3, "large_threshold": 15},
        {"code": "BAD", "name": "坏", "planned_headway_min": 8, "bunch_threshold": 9, "large_threshold": 15},
        {"code": "BAD", "name": "坏", "planned_headway_min": 8, "bunch_threshold": 3, "large_threshold": 8},
    ):
        assert client.post("/api/lines", json=body).status_code == 422
    assert client.put(f"/api/lines/{b12.id}",
                      json={"planned_headway_min": 8, "bunch_threshold": 8, "large_threshold": 9}
                      ).status_code == 422

    # 报告行数不变，时间轴不增脏点（B12 在市民中心仍为 4 个点）
    assert db.scalar(select(func.count()).select_from(BunchReport)) == base_count
    tl = client.get(f"/api/reports/timeline?line_id={b12.id}")
    assert tl.status_code == 200
    assert len(tl.json()["marks"]) == 4

    # B12 三参未被任何失败动作改动，检测仍可正常出报告
    run2 = client.post(f"/api/reports/run?line_id={b12.id}")
    assert run2.status_code == 200
    assert db.scalar(select(func.count()).select_from(BunchReport)) == base_count + 1
