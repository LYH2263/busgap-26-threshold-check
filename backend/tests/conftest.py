"""共用测试夹具：准备隔离的 busgap_test 库，每个用例前清表。

接口拒测（test_line_api_reject.py）与直插败测（test_db_constraints.py）
刻意分文件分模块；本文件只负责数据库与 TestClient。
"""
import os

import psycopg2
import pytest

ADMIN_DSN = "postgresql://busgap:busgap@localhost:5447/postgres"
TEST_URL = "postgresql+psycopg2://busgap:busgap@localhost:5447/busgap_test"


def _ensure_test_database() -> None:
    conn = psycopg2.connect(ADMIN_DSN)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = 'busgap_test'")
            if cur.fetchone() is None:
                cur.execute("CREATE DATABASE busgap_test")
    finally:
        conn.close()


_ensure_test_database()
os.environ["DATABASE_URL"] = TEST_URL
os.environ["SEED_ON_EMPTY"] = "true"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.migrate import run_migrations  # noqa: E402

# 会话级建表 + 迁移一次（迁移幂等，lifespan 内还会再跑）
Base.metadata.create_all(bind=engine)
run_migrations(engine)


@pytest.fixture(autouse=True)
def reset_db():
    # 每例清表（接口拒测 / 直插败测都受益）
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE bunch_reports, arrivals, trips, lines RESTART IDENTITY CASCADE"))


@pytest.fixture
def client(reset_db):
    # 进入 TestClient 触发生命周期，空库会重新播种 B12(8/3/15)
    with TestClient(app) as c:
        yield c
