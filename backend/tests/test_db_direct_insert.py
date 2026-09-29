"""直插败测（库侧约束模块）：绕过应用层、直接 INSERT 也必须失败。

与 test_lines_api_rejects.py 分文件：那边打 HTTP 接口（应用例程拒），
这边直插 PostgreSQL（CHECK 约束挡）。重点覆盖
「近车阈 >= 班距计划」的等于与大于两支。
"""
from __future__ import annotations

import pytest
from psycopg2.errors import CheckViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

pytestmark = pytest.mark.usefixtures("clean_db")


def _insert(db, planned, bunch, large, code="DBX"):
    db.execute(text(
        "INSERT INTO lines (code, name, planned_headway_min, bunch_threshold, large_threshold) "
        "VALUES (:code, :name, :p, :b, :l)"
    ), {"code": code, "name": "直插线", "p": planned, "b": bunch, "l": large})
    db.commit()


def test_constraints_present(db):
    names = {r[0] for r in db.execute(text(
        "SELECT conname FROM pg_constraint WHERE conrelid = 'lines'::regclass"
    ))}
    assert {"ck_lines_headway_positive",
            "ck_lines_bunch_open_range",
            "ck_lines_large_above_headway"} <= names


@pytest.mark.parametrize(
    "planned,bunch,large,violating",
    [
        (8.0, 8.0, 15.0, "ck_lines_bunch_open_range"),   # 近车等于班距
        (8.0, 9.0, 15.0, "ck_lines_bunch_open_range"),   # 近车大于班距（>= 必败的大于支）
        (8.0, 3.0, 8.0, "ck_lines_large_above_headway"),  # 疏车等于班距
        (8.0, 3.0, 7.0, "ck_lines_large_above_headway"),  # 疏车小于班距
        (0.0, 3.0, 15.0, None),                          # 班距非正（可能连带触发开区间约束）
        (-4.0, 3.0, 15.0, None),
        (8.0, 0.0, 15.0, "ck_lines_bunch_open_range"),    # 近车非正（开区间下界）
        (8.0, -1.0, 15.0, "ck_lines_bunch_open_range"),
    ],
)
def test_direct_insert_illegal_fails(db, planned, bunch, large, violating):
    with pytest.raises(IntegrityError) as exc:
        _insert(db, planned, bunch, large, code=f"BAD{planned}{bunch}{large}")
    db.rollback()
    assert isinstance(exc.value.orig, CheckViolation)
    if violating is not None:
        assert exc.value.orig.diag.constraint_name == violating
    # 被拒后表里没有脏行
    n = db.execute(text("SELECT count(*) FROM lines")).scalar()
    assert n == 0


def test_direct_insert_bunch_ge_headway_explicit(db):
    """任务点名：直插「近车大于等于班距」必须败 —— 等于、大于两支各自失败。"""
    for bunch in (8.0, 8.0000001, 100.0):
        with pytest.raises(IntegrityError):
            _insert(db, 8.0, bunch, 15.0, code=f"GE{bunch}")
        db.rollback()
    assert db.execute(text("SELECT count(*) FROM lines")).scalar() == 0


def test_direct_insert_legal_edges_succeed(db):
    # 近车阈 1 / 班距计划 8 / 疏车阈 9
    _insert(db, 8.0, 1.0, 9.0, code="EDGE1")
    # 贴边：近车阈任意小正数；疏车阈贴着班距上方
    _insert(db, 1.0, 0.0001, 1.0001, code="EDGE2")
    rows = db.execute(text(
        "SELECT code, planned_headway_min, bunch_threshold, large_threshold "
        "FROM lines ORDER BY code"
    )).fetchall()
    assert rows == [("EDGE1", 8.0, 1.0, 9.0), ("EDGE2", 1.0, 0.0001, 1.0001)]


def test_orm_insert_illegal_fails(db):
    from app.models.models import Line
    db.add(Line(code="ORMBAD", name="ORM 脏线",
                planned_headway_min=8.0, bunch_threshold=8.0, large_threshold=15.0))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert db.execute(text("SELECT count(*) FROM lines")).scalar() == 0


def test_orm_update_to_illegal_fails(db):
    # 先直插一条合法线（不用 ORM 校验路径），再尝试 ORM 改成 8/8，必须被挡且旧值保留
    _insert(db, 8.0, 3.0, 15.0, code="UPD")
    from app.models.models import Line
    line = db.query(Line).filter_by(code="UPD").one()
    line.bunch_threshold = 8.0
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    row = db.execute(text(
        "SELECT bunch_threshold FROM lines WHERE code='UPD'"
    )).fetchone()
    assert row[0] == 3.0
