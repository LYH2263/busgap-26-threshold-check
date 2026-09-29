"""B12 迁移后回归：约束加完，B12（8/3/15）照常起服。

对 B12 跑一次检测，报告里仍能出「市民中心」串车（T01->T02 间隔 2 分钟），
时间轴在市民中心也仍有对应到达点。
"""
from fastapi.testclient import TestClient


def test_b12_served_after_migration(client: TestClient):
    lines = client.get("/api/lines").json()
    b12 = [r for r in lines if r["code"] == "B12"]
    assert len(b12) == 1
    assert (b12[0]["planned_headway_min"], b12[0]["bunch_threshold"], b12[0]["large_threshold"]) == (8.0, 3.0, 15.0)


def test_b12_detection_reports_bunching_at_civic_center(client: TestClient):
    b12_id = [r for r in client.get("/api/lines").json() if r["code"] == "B12"][0]["id"]
    resp = client.post(f"/api/reports/run?line_id={b12_id}")
    assert resp.status_code == 200, resp.text
    events = resp.json()["events"]
    civic = [e for e in events if e["stop_name"] == "市民中心" and e["status"] == "bunching"]
    assert civic, "市民中心应检出串车"
    # T01 7:06 到、T02 7:08 到，间隔 2 分钟 < 近车阈 3
    assert any(e["earlier_trip"] == "T01" and e["later_trip"] == "T02" and e["gap_min"] == 2.0 for e in civic)

    # 报告已落库
    reports = client.get("/api/reports").json()
    assert any(any(e["stop_name"] == "市民中心" and e["status"] == "bunching" for e in r["events"]) for r in reports)


def test_b12_timeline_still_has_civic_center_marks(client: TestClient):
    b12_id = [r for r in client.get("/api/lines").json() if r["code"] == "B12"][0]["id"]
    tl = client.get(f"/api/reports/timeline?line_id={b12_id}&stop_name=市民中心").json()
    assert tl["stop_name"] == "市民中心"
    trips = {m["trip_no"] for m in tl["marks"]}
    assert {"T01", "T02"} <= trips
    # 前两个点（7:06、7:08）紧贴，前端按 pct<15 标红
    ordered = sorted(tl["marks"], key=lambda m: m["actual_arrive"])
    assert ordered[0]["trip_no"] == "T01"
    assert ordered[1]["trip_no"] == "T02"
