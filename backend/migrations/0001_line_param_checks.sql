-- 0001: 线路三参库侧兜底（班距计划 / 近车阈 / 疏车阈）
-- 与 app/models/models.py 的 __table_args__ 同名同义；可重复执行
-- （create_all 已建同名约束的全新库上再跑也不报错）。
-- 规则：班距计划 > 0；0 < 近车阈 < 班距计划；疏车阈 > 班距计划。
-- 存量 B12（8 / 3 / 15）满足全部约束，加约束后照常起服。

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'lines_planned_headway_positive'
    ) THEN
        ALTER TABLE lines
            ADD CONSTRAINT lines_planned_headway_positive CHECK (planned_headway_min > 0);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'lines_bunch_threshold_positive'
    ) THEN
        ALTER TABLE lines
            ADD CONSTRAINT lines_bunch_threshold_positive CHECK (bunch_threshold > 0);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'lines_bunch_below_headway'
    ) THEN
        ALTER TABLE lines
            ADD CONSTRAINT lines_bunch_below_headway CHECK (bunch_threshold < planned_headway_min);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'lines_large_above_headway'
    ) THEN
        ALTER TABLE lines
            ADD CONSTRAINT lines_large_above_headway CHECK (large_threshold > planned_headway_min);
    END IF;
END $$;
