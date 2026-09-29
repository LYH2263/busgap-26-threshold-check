-- 线路三参数库侧兜底约束（与 app/services/line_validation.py 同一套规则）
--   班距计划 > 0
--   0 < 近车阈 < 班距计划
--   疏车阈 > 班距计划
-- 幂等：约束已存在时跳过；现存数据非法时 ADD CONSTRAINT 会自行失败回滚。
-- B12 种子数据 8 / 3 / 15 满足全部约束，迁移后照常起服。

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_lines_headway_positive') THEN
        ALTER TABLE lines
            ADD CONSTRAINT ck_lines_headway_positive CHECK (planned_headway_min > 0);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_lines_bunch_open_range') THEN
        ALTER TABLE lines
            ADD CONSTRAINT ck_lines_bunch_open_range
            CHECK (bunch_threshold > 0 AND bunch_threshold < planned_headway_min);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_lines_large_above_headway') THEN
        ALTER TABLE lines
            ADD CONSTRAINT ck_lines_large_above_headway
            CHECK (large_threshold > planned_headway_min);
    END IF;
END $$;
