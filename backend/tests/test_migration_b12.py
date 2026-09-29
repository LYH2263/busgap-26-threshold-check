"""迁移与起服测试（独立模块/独立库）。

模拟「按旧模型建好、无 CHECK 约束」的库：
  旧表 + B12(8/3/15) -> 执行可执行迁移 -> 约束就位且 B12 不动 ->
  再跑一遍（幂等）-> 对 B12 检测，报告与时间轴仍能出「市民中心」串车。

与接口拒测、直插败测分文件：本模块只关心迁移可执行与迁移后起服。
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

_PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TEST_PG_PORT", "5447")
_PG_USER = os.environ.get("TEST_PG_USER", "busgap")
_PG_PASS = os.environ.get("TEST_PG_PASS", "busgap")
_ROOT = f"postgresql+psycopg2://{_PG_USER}:{_PG_PASS}@{_PG_HOST}:{_PG_PORT}"
ADMIN_DSN = f"{_ROOT}/postgres"
LEGACY_DSN = f"{_ROOT}/busgap_test_legacy"


@pytest.fixture
def legacy_engine():
    admin = create_engine(ADMIN_DSN, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text("DROP DATABASE IF EXISTS busgap_test_legacy"))
            conn.execute(text("CREATE DATABASE busgap_test_legacy"))
    except OperationalError as exc:
        admin.dispose()
        pytest.skip(f"无可用 PostgreSQL，跳过迁移起服用例：{exc}")
    admin.dispose()

    eng = create_engine(LEGACY_DSN)
    # 旧版 lines 表：没有任何 CHECK 约束（其余表尚不存在）
    with eng.begin() as conn:
        conn.execute(text("""
            CREATE TABLE lines (
                id SERIAL PRIMARY KEY,
                code VARCHAR(32) UNIQUE,
                name VARCHAR(128),
                planned_headway_min DOUBLE PRECISION,
                bunch_threshold DOUBLE PRECISION,
                large_threshold DOUBLE PRECISION
            )
        """))
        conn.execute(text("""
            INSERT INTO lines (code, name, planned_headway_min, bunch_threshold, large_threshold)
            VALUES ('B12', '城东环线', 8.0, 3.0, 15.0)
        """))
    yield eng
    eng.dispose()


@pytest.fixture
def migrated(legacy_engine, monkeypatch):
    import migrations.migrate as migrate

    monkeypatch.setattr(migrate, "engine", legacy_engine)
    # 迁移前：lines 无约束
    with legacy_engine.connect() as conn:
        before = {r[0] for r in conn.execute(text(
            "SELECT conname FROM pg_constraint WHERE conrelid='lines'::regclass"
        ))}
    assert before == {"lines_code_key", "lines_pkey"}

    migrate.run_migrations()
    migrate.run_migrations()  # 再跑一遍必须幂等成功
    return legacy_engine


def _seed_b12_traffic(eng) -> None:
    """复刻 seed.py 的班次/到站（市民中心 7:06/7:08/7:24/7:32）。"""
    base = datetime(2026, 9, 17, 7, 0, 0)
    with eng.begin() as c:
        specs = [("T01", "粤A1001", 0), ("T02", "粤A1002", 2),
                 ("T03", "粤A1003", 18), ("T04", "粤A1004", 26)]
        for trip_no, vehicle, offset in specs:
            c.execute(text(
                "INSERT INTO trips (line_id, trip_no, planned_depart, vehicle_no) "
                "VALUES (1, :t, :d, :v)"
            ), {"t": trip_no, "d": base + timedelta(minutes=offset), "v": vehicle})
        trip_ids = {r[1]: r[0] for r in c.execute(text("SELECT id, trip_no FROM trips"))}
        stops = ["起点站", "市民中心", "火车站", "终点站"]
        rows = []
        for trip_no, _, offset in specs:
            for seq, stop in enumerate(stops):
                arrive = base + timedelta(minutes=offset + seq * 6)
                if stop == "市民中心" and trip_no == "T02":
                    arrive = base + timedelta(minutes=8)
                if stop == "火车站" and trip_no == "T03":
                    arrive = base + timedelta(minutes=30)
                rows.append({"tid": trip_ids[trip_no], "stop": stop,
                             "seq": seq, "arrive": arrive})
        for r in rows:
            c.execute(text(
                "INSERT INTO arrivals (trip_id, stop_name, stop_seq, actual_arrive) "
                "VALUES (:tid, :stop, :seq, :arrive)"
            ), r)


def test_migration_adds_constraints_and_keeps_b12(migrated):
    eng = migrated
    with eng.connect() as conn:
        names = {r[0] for r in conn.execute(text(
            "SELECT conname FROM pg_constraint WHERE conrelid='lines'::regclass"
        ))}
        assert {"ck_lines_headway_positive",
                "ck_lines_bunch_open_range",
                "ck_lines_large_above_headway"} <= names
        row = conn.execute(text(
            "SELECT planned_headway_min, bunch_threshold, large_threshold "
            "FROM lines WHERE code='B12'"
        )).fetchone()
    # 迁移后 B12 的 8/3/15 原样起服
    assert row == (8.0, 3.0, 15.0)


def test_b12_detection_and_timeline_after_migration(migrated):
    from app.database import get_db
    from app.main import app

    eng = migrated
    _seed_b12_traffic(eng)
    LegacySession = sessionmaker(bind=eng)

    def _legacy_db():
        s = LegacySession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _legacy_db
    try:
        with TestClient(app) as client:  # lifespan 不播种；数据已在 legacy 库
            # 对 B12 跑检测
            res = client.post("/api/reports/run?line_id=1")
            assert res.status_code == 200, res.text
            events = res.json()["events"]

            bunch = [e for e in events
                     if e["stop_name"] == "市民中心" and e["status"] == "bunching"]
            assert bunch, "市民中心应仍能检出串车"
            e = bunch[0]
            assert e["earlier_trip"] == "T01" and e["later_trip"] == "T02"
            assert e["gap_min"] == 2.0
            assert e["planned_headway_min"] == 8.0

            # 报告落库一行
            reports = client.get("/api/reports").json()
            assert len(reports) == 1
            assert reports[0]["line_id"] == 1

            # 时间轴仍出市民中心 4 个点
            tl = client.get("/api/reports/timeline?line_id=1").json()
            assert tl["stop_name"] == "市民中心"
            assert [m["trip_no"] for m in tl["marks"]] == ["T01", "T02", "T03", "T04"]
    finally:
        app.dependency_overrides = {}


def test_migrated_constraints_still_reject_dirty_insert(migrated):
    # 迁移后直插「近车阈 >= 班距计划」依旧败
    from psycopg2.errors import CheckViolation
    from sqlalchemy.exc import IntegrityError

    eng = migrated
    with pytest.raises(IntegrityError) as exc:
        with eng.begin() as c:
            c.execute(text("""
                INSERT INTO lines (code, name, planned_headway_min, bunch_threshold, large_threshold)
                VALUES ('DIRTY', '脏', 8.0, 8.0, 15.0)
            """))
    assert isinstance(exc.value.orig, CheckViolation)
