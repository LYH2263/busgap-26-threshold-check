"""迁移可执行性：模拟老库（lines 表无四约束）跑 run_migrations。

迁移后四条具名约束就位、存量 B12（8/3/15）不被清理，且再跑一次迁移幂等不报错。
"""
import psycopg2
from sqlalchemy import text

from app.database import engine
from app.migrate import run_migrations

DSN = "postgresql://busgap:busgap@localhost:5447/busgap_test"
CONSTRAINTS = [
    "lines_planned_headway_positive",
    "lines_bunch_threshold_positive",
    "lines_bunch_below_headway",
    "lines_large_above_headway",
]


def _existing_constraints() -> set[str]:
    conn = psycopg2.connect(DSN)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT conname FROM pg_constraint WHERE conname = ANY(%s)", (CONSTRAINTS,))
            return {r[0] for r in cur.fetchall()}
    finally:
        conn.close()


def test_migration_adds_constraints_to_legacy_table_and_keeps_b12(client):
    # client 夹具已播种 B12(8/3/15)。先退回老库形态：卸掉四约束
    with engine.begin() as conn:
        for name in CONSTRAINTS:
            conn.execute(text(f"ALTER TABLE lines DROP CONSTRAINT IF EXISTS {name}"))
    assert _existing_constraints() == set()

    # 执行迁移
    run_migrations(engine)

    assert _existing_constraints() == set(CONSTRAINTS)

    # B12 与 8/3/15 原样存活
    conn = psycopg2.connect(DSN)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT code, planned_headway_min, bunch_threshold, large_threshold "
                        "FROM lines WHERE code = 'B12'")
            row = cur.fetchone()
    finally:
        conn.close()
    assert row == ("B12", 8.0, 3.0, 15.0)

    # 再跑一遍：幂等，不报错、不重复
    run_migrations(engine)
    assert _existing_constraints() == set(CONSTRAINTS)
