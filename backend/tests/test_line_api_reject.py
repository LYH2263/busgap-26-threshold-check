"""接口拒测（模块一）：创建 / 改写线路与进检测引擎前的 HTTP 层拦截。

与直插库的 test_db_constraints.py 分开。全部非法组合都应在进检测引擎前
以 400 拒掉，回包 detail.errors 点名字段，且：
  * 报告行数不变；时间轴不增脏点；
  * 改写被拒时库内三参保持改前、历史报告不被清掉。
"""
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.models import BunchReport

ILLEGAL_CASES = [
    # (班距, 近车, 疏车), 应被点名的字段
    ((8.0, 8.0, 15.0), "bunch_threshold"),   # 近车等于班距
    ((8.0, 9.0, 15.0), "bunch_threshold"),   # 近车大于班距
    ((8.0, 3.0, 8.0), "large_threshold"),    # 疏车等于班距
    ((8.0, 3.0, 7.0), "large_threshold"),    # 疏车小于班距
    ((0.0, 3.0, 15.0), "planned_headway_min"),  # 班距非正
    ((8.0, 0.0, 15.0), "bunch_threshold"),   # 近车非正
]


def _error_fields(resp) -> set[str]:
    return {e["field"] for e in resp.json()["detail"]["errors"]}


def test_b12_seeded_with_8_3_15(client: TestClient):
    rows = client.get("/api/lines").json()
    b12 = [r for r in rows if r["code"] == "B12"][0]
    assert (b12["planned_headway_min"], b12["bunch_threshold"], b12["large_threshold"]) == (8.0, 3.0, 15.0)


def test_create_rejects_six_illegal_combos_with_field_names(client: TestClient):
    for i, ((planned, bunch, large), field) in enumerate(ILLEGAL_CASES):
        resp = client.post("/api/lines", json={
            "code": f"X{i}", "name": "非法线",
            "planned_headway_min": planned, "bunch_threshold": bunch, "large_threshold": large,
        })
        assert resp.status_code == 400, (i, resp.status_code, resp.text)
        assert field in _error_fields(resp), (i, resp.text)
    # 六条全部没进库
    assert client.get("/api/lines").json() == [r for r in client.get("/api/lines").json() if r["code"] == "B12"]


def test_create_accepts_edge_1_8_9(client: TestClient):
    resp = client.post("/api/lines", json={
        "code": "E01", "name": "边线",
        "planned_headway_min": 8.0, "bunch_threshold": 1.0, "large_threshold": 9.0,
    })
    assert resp.status_code == 201, resp.text


def test_create_rejects_edge_8_8(client: TestClient):
    resp = client.post("/api/lines", json={
        "code": "E02", "name": "等阈线",
        "planned_headway_min": 8.0, "bunch_threshold": 8.0, "large_threshold": 9.0,
    })
    assert resp.status_code == 400
    assert "bunch_threshold" in _error_fields(resp)


def test_update_rejected_keeps_old_numbers_and_reports(client: TestClient):
    b12_id = [r for r in client.get("/api/lines").json() if r["code"] == "B12"][0]["id"]
    # 先跑一次检测，留下历史报告
    run = client.post(f"/api/reports/run?line_id={b12_id}")
    assert run.status_code == 200
    db: Session = SessionLocal()
    before = db.scalar(select(func.count()).select_from(BunchReport))
    db.close()

    resp = client.put(f"/api/lines/{b12_id}", json={
        "planned_headway_min": 8.0, "bunch_threshold": 8.0, "large_threshold": 15.0,  # 近车=班距，非法
    })
    assert resp.status_code == 400
    assert "bunch_threshold" in _error_fields(resp)

    # 库内数字保持改前
    after_line = client.get("/api/lines").json()[0]
    assert (after_line["planned_headway_min"], after_line["bunch_threshold"], after_line["large_threshold"]) == (8.0, 3.0, 15.0)
    # 历史报告未被改写动作清掉
    db = SessionLocal()
    after = db.scalar(select(func.count()).select_from(BunchReport))
    db.close()
    assert after == before


def test_update_accepts_valid_change(client: TestClient):
    b12_id = [r for r in client.get("/api/lines").json() if r["code"] == "B12"][0]["id"]
    resp = client.put(f"/api/lines/{b12_id}", json={
        "planned_headway_min": 8.0, "bunch_threshold": 1.0, "large_threshold": 9.0,
    })
    assert resp.status_code == 200, resp.text
    assert (resp.json()["planned_headway_min"], resp.json()["bunch_threshold"], resp.json()["large_threshold"]) == (8.0, 1.0, 9.0)


def test_illegal_api_write_blocked_before_engine_no_report_no_timeline_dirt(client: TestClient):
    b12_id = [r for r in client.get("/api/lines").json() if r["code"] == "B12"][0]["id"]

    # 非法写入本身已在接口层拒掉（上面已覆盖）。这里再验证引擎入口护栏：
    # 临时卸下库约束造出「近车阈等于班距」的脏状态（模拟绕过一切写入防线），
    # /reports/run 必须在进检测引擎前 400，报告行数不变、时间轴不增脏点。
    db = SessionLocal()
    marks_before = client.get(f"/api/reports/timeline?line_id={b12_id}").json()["marks"]
    reports_before = db.scalar(select(func.count()).select_from(BunchReport))
    db.execute(text("ALTER TABLE lines DROP CONSTRAINT lines_bunch_below_headway"))
    db.execute(text("UPDATE lines SET bunch_threshold = planned_headway_min WHERE id = :i"), {"i": b12_id})
    db.commit()
    db.close()
    try:
        run = client.post(f"/api/reports/run?line_id={b12_id}")
        assert run.status_code == 400
        assert "bunch_threshold" in _error_fields(run)

        db = SessionLocal()
        reports_after = db.scalar(select(func.count()).select_from(BunchReport))
        db.close()
        # 进引擎前被拒：报告行数不变
        assert reports_after == reports_before
        # 时间轴只读到站记录：脏参数未产生任何新点
        marks_after = client.get(f"/api/reports/timeline?line_id={b12_id}").json()["marks"]
        assert marks_after == marks_before
    finally:
        # 恢复合法状态并把约束装回去（存量行合法后约束方可重建）
        db = SessionLocal()
        db.execute(text("UPDATE lines SET bunch_threshold = 3.0 WHERE id = :i"), {"i": b12_id})
        db.execute(text("ALTER TABLE lines ADD CONSTRAINT lines_bunch_below_headway "
                        "CHECK (bunch_threshold < planned_headway_min)"))
        db.commit()
        db.close()
