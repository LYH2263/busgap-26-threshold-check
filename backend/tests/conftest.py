"""共享夹具：PostgreSQL 测试库 + FastAPI TestClient。

连接信息取自环境变量（默认对齐 docker-compose 的 5447 端口）：
    TEST_PG_HOST / TEST_PG_PORT / TEST_PG_USER / TEST_PG_PASS / TEST_PG_DB
本机临时验证时也可直接设 DATABASE_URL。
没有可用 PostgreSQL 时，依赖本模块夹具的用例整体跳过，
纯函数单测（如 test_bunch_engine / test_line_validation）不受影响。
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

_PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TEST_PG_PORT", "5447")
_PG_USER = os.environ.get("TEST_PG_USER", "busgap")
_PG_PASS = os.environ.get("TEST_PG_PASS", "busgap")
_PG_DB = os.environ.get("TEST_PG_DB", "busgap_test")

TEST_DSN = (f"postgresql+psycopg2://{_PG_USER}:{_PG_PASS}"
            f"@{_PG_HOST}:{_PG_PORT}/{_PG_DB}")

# 必须在 import app.* 之前定好应用将使用的测试库
os.environ.setdefault("DATABASE_URL", TEST_DSN)
os.environ.setdefault("SEED_ON_EMPTY", "false")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base  # noqa: E402
import app.models.models as models  # noqa: E402
from app.main import app  # noqa: E402


def _admin_dsns():
    """建库连接：先试标准 postgres 库，再退回与用户同名的库。"""
    for dbname in ("postgres", _PG_USER):
        yield (f"postgresql+psycopg2://{_PG_USER}:{_PG_PASS}"
               f"@{_PG_HOST}:{_PG_PORT}/{dbname}")


def _ensure_test_database() -> bool:
    last_err = None
    for dsn in _admin_dsns():
        try:
            admin = create_engine(dsn, isolation_level="AUTOCOMMIT")
            with admin.connect() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :d"),
                    {"d": _PG_DB},
                ).scalar()
                if not exists:
                    # 不能对库名做参数绑定，标识符已由内部环境变量控制
                    conn.execute(text(f'CREATE DATABASE "{_PG_DB}"'))
            admin.dispose()
            return True
        except OperationalError as exc:
            last_err = exc
            continue
    pytest.skip(f"无可用 PostgreSQL（{_PG_HOST}:{_PG_PORT}），跳过库相关用例：{last_err}")
    return False


engine = create_engine(TEST_DSN)
TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session")
def _schema():
    _ensure_test_database()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def clean_db(_schema):
    """每例清空并复位自增 id（CASCADE 连带 trips/arrivals/reports）。
    非自动夹具：纯函数单测不连库也能跑，需要库的用例经 db/client 依赖链触发。
    """
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE TABLE bunch_reports, arrivals, trips, lines RESTART IDENTITY CASCADE"
        ))
    yield


@pytest.fixture
def db(clean_db) -> Session:
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(clean_db):
    def _get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides = {}
    from app.database import get_db
    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:  # 不走 lifespan 播种（SEED_ON_EMPTY=false），数据由各例自备
        yield c
    app.dependency_overrides = {}


@pytest.fixture
def b12(db):
    """播种 B12：班距 8 / 近车阈 3 / 疏车阈 15 + 四班次到到站数据。"""
    from app.services.seed import seed_if_empty
    seed_if_empty(db)
    return db.query(models.Line).filter_by(code="B12").one()
