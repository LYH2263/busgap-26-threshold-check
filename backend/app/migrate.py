"""轻量可执行迁移：启动时按文件名顺序跑 migrations/*.sql。

每条迁移都写成幂等形式（查 pg_constraint / IF EXISTS 的 DO 块），
重复执行（含 create_all 已建约束的全新库）不会报错。
切分语句时识别单引号与 $$ dollar-quote，DO 块内部的分号不会被切断。
"""
from __future__ import annotations

import pathlib
import re

from sqlalchemy import text
from sqlalchemy.engine import Engine

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"
_DOLLAR_TAG = re.compile(r"\$[A-Za-z_0-9]*\$")


def run_migrations(engine: Engine) -> None:
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not sql_files:
        return
    with engine.begin() as conn:
        for path in sql_files:
            for stmt in split_sql_statements(path.read_text(encoding="utf-8")):
                conn.execute(text(stmt))


def split_sql_statements(sql: str) -> list[str]:
    """按顶层分号切语句；跳过 -- 注释，正确穿过单引号与 dollar-quoted 块。"""
    statements: list[str] = []
    buf: list[str] = []
    i, n = 0, len(sql)
    quote_char: str | None = None  # "'" 或 dollar-quote 标签（如 "$$"）
    while i < n:
        ch = sql[i]
        if quote_char is None and ch == "-" and i + 1 < n and sql[i + 1] == "-":
            j = sql.find("\n", i)
            i = n if j == -1 else j
            continue
        if quote_char is None:
            m = _DOLLAR_TAG.match(sql, i)
            if m:
                quote_char = m.group(0)
                buf.append(quote_char)
                i += len(quote_char)
                continue
            if ch == "'":
                quote_char = "'"
                buf.append(ch)
                i += 1
                continue
            if ch == ";":
                stmt = "".join(buf).strip()
                if stmt:
                    statements.append(stmt)
                buf = []
                i += 1
                continue
            buf.append(ch)
            i += 1
        elif quote_char == "'":
            buf.append(ch)
            i += 1
            # SQL 单引号转义 ''
            if ch == "'":
                if i < n and sql[i] == "'":
                    buf.append("'")
                    i += 1
                else:
                    quote_char = None
        else:  # dollar-quoted 块，找同名闭合标签
            close = sql.find(quote_char, i)
            if close == -1:
                buf.append(sql[i:])
                break
            buf.append(sql[i:close + len(quote_char)])
            i = close + len(quote_char)
            quote_char = None
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements
