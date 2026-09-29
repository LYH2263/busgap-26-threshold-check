"""可执行迁移：为 lines 表补齐三参数 CHECK 约束。

用法（在 backend/ 目录下）：
    python -m migrations.migrate            # 建表（若缺）+ 应用全部幂等迁移 + 空库播种
    DATABASE_URL=postgresql+psycopg2://... python -m migrations.migrate --no-seed

对已按旧模型建好的库：create_all 不会改动已存在的表，随后执行
migrations/*.sql 用 DO 块幂等地 ADD CONSTRAINT；
对全新库：create_all 直接按当前模型建出带约束的表，SQL 再跑一遍也安全。
现存数据非法时 ADD CONSTRAINT 失败并整体回滚，不会留下半截约束。
"""
from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, SessionLocal, engine

# 确保模型已注册到 metadata
import app.models.models  # noqa: F401

MIGRATIONS_DIR = Path(__file__).parent


def run_migrations(bind_engine=None) -> None:
    # 全新库先建表；已存在的表保持原样，交给 SQL 迁移做增量变更。
    target_engine = bind_engine or engine
    Base.metadata.create_all(bind=target_engine)

    # 会话就地按目标 engine 构造，便于测试替换 bind
    Session = sessionmaker(bind=target_engine)
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    db = Session()
    try:
        for sql_file in sql_files:
            db.execute(text(sql_file.read_text(encoding="utf-8")))
            print(f"[migrate] applied {sql_file.name}")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="BusGap database migrations")
    parser.add_argument("--no-seed", action="store_true", help="空库不播种 B12 示例数据")
    args = parser.parse_args()

    print(f"[migrate] database = {settings.database_url.split('@')[-1]}")
    run_migrations()

    if not args.no_seed and settings.seed_on_empty:
        from app.services.seed import seed_if_empty
        db = SessionLocal()
        try:
            seed_if_empty(db)
            print("[migrate] seed ensured")
        finally:
            db.close()

    print("[migrate] done")


if __name__ == "__main__":
    main()
