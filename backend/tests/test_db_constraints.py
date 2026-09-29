"""直插败测（模块二，与接口拒测分开）：绕过应用，用裸连接直接写库。

库侧 CHECK 约束（迁移 0001 与模型同名）必须挡住非法三参，
重点：直插「近车阈大于等于班距计划」必须失败（等于、大于都要败）。
"""
import psycopg2
import pytest

DSN = "postgresql://busgap:busgap@localhost:5447/busgap_test"


def _raw_insert(planned, bunch, large, code: str):
    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO lines (code, name, planned_headway_min, bunch_threshold, large_threshold) "
                "VALUES (%s, %s, %s, %s, %s)",
                (code, "直插线", planned, bunch, large),
            )
        conn.commit()
        return None
    except psycopg2.IntegrityError as exc:
        conn.rollback()
        return str(exc)
    finally:
        conn.close()


def test_direct_insert_bunch_equal_headway_must_fail():
    msg = _raw_insert(8.0, 8.0, 15.0, "D01")
    assert msg is not None
    assert "lines_bunch_below_headway" in msg


def test_direct_insert_bunch_greater_than_headway_must_fail():
    msg = _raw_insert(8.0, 9.0, 15.0, "D02")
    assert msg is not None
    assert "lines_bunch_below_headway" in msg


def test_direct_insert_non_positive_headway_must_fail():
    # 班距 0 同时违反「班距为正」与「近车<班距」，库只要拒掉即可，约束名取其一
    msg = _raw_insert(0.0, 3.0, 15.0, "D03")
    assert msg is not None
    assert ("lines_planned_headway_positive" in msg or "lines_bunch_below_headway" in msg)


def test_direct_insert_non_positive_bunch_must_fail():
    msg = _raw_insert(8.0, 0.0, 15.0, "D04")
    assert msg is not None
    assert "lines_bunch_threshold_positive" in msg


def test_direct_insert_large_equal_headway_must_fail():
    msg = _raw_insert(8.0, 3.0, 8.0, "D05")
    assert msg is not None
    assert "lines_large_above_headway" in msg


def test_direct_insert_large_below_headway_must_fail():
    msg = _raw_insert(8.0, 3.0, 7.0, "D06")
    assert msg is not None
    assert "lines_large_above_headway" in msg


def test_direct_update_to_bunch_equal_headway_must_fail():
    # 合法插入后再直改非法，UPDATE 同样要被约束挡下
    assert _raw_insert(8.0, 3.0, 15.0, "D07") is None
    conn = psycopg2.connect(DSN)
    try:
        with conn.cursor() as cur, pytest.raises(psycopg2.IntegrityError):
            cur.execute("UPDATE lines SET bunch_threshold = planned_headway_min WHERE code = 'D07'")
        conn.rollback()
    finally:
        conn.close()


def test_direct_insert_valid_edges_succeeds():
    # 合法边 1/8/9（班距8、近车1、疏车9）可直插；8/8 已在上面必败
    assert _raw_insert(8.0, 1.0, 9.0, "D08") is None
