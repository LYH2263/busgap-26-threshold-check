# BusGap 公交串车检测

对比计划发车间隔与实际到站间隔，识别串车与大间隔，并给出调班建议。

技术栈：Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL / Vue 3 / TypeScript / Vite

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4600 |
| API | http://localhost:9600 |
| API 文档 | http://localhost:9600/docs |
| Postgres | localhost:5447 |

健康检查：`GET http://localhost:9600/api/health`

## 使用说明

1. 在「线路」查看运营线路与阈值，也可新建线路或就地改写三参。
2. 在「班次」「到站」核对计划与实际到站时间。
3. 打开「串车报告」执行间隔判定。
4. 在「时间轴」观察到站分布，在「建议」查看调班提示。

### 线路三参校验规则

班距计划 / 近车阈 / 疏车阈由后端 `app/services/line_validation.py` 统一校验，
新建与改写走同一例程，前端 `src/lineValidation.ts` 同规则、同字段、同中文用词：

* 班距计划 `planned_headway_min` 必须大于 0；
* 近车阈 `bunch_threshold` 在开区间 `(0, 班距计划)` 内；
* 疏车阈 `large_threshold` 严格大于班距计划。

非法组合返回 422，回包 `detail.errors[].field` 点名字段；库侧另有同名
CHECK 约束兜底，直接 INSERT/UPDATE 非法值会被 PostgreSQL 拒绝。

### 数据库迁移

应用启动时自动建表并幂等应用 `backend/migrations/*.sql`；也可手动执行：

```bash
python -m migrations.migrate          # 迁移 + 空库播种
python -m migrations.migrate --no-seed
```

## 开发与测试

```bash
docker compose exec api pytest -q
```

测试分模块：`test_line_validation.py`（纯例程）、
`test_lines_api_rejects.py`（接口拒测，HTTP 层）、
`test_db_direct_insert.py`（直插败测，库侧约束）、
`test_migration_b12.py`（可执行迁移后 B12 8/3/15 起服与市民中心串车）。
无可用 PostgreSQL 时，库相关用例自动跳过，纯函数用例照常运行；
可用 `TEST_PG_HOST/TEST_PG_PORT/...` 覆盖测试库连接。
