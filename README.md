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

1. 在「线路」查看运营线路与阈值，可新建线路或改写既有线路三参。
2. 在「班次」「到站」核对计划与实际到站时间。
3. 打开「串车报告」执行间隔判定。
4. 在「时间轴」观察到站分布，在「建议」查看调班提示。

### 线路三参校验

班距计划（`planned_headway_min`）、近车阈（`bunch_threshold`）、疏车阈（`large_threshold`）共用一枚校验例程，创建（`POST /api/lines`）与改写（`PUT /api/lines/{id}`）都先校验后写库：

- 班距计划严格大于 0；
- 近车阈在开区间 `(0, 班距计划)` 内（等于班距非法）；
- 疏车阈严格大于班距计划（等于班距非法）。

非法组合在进检测引擎前以 `400` 拒绝，回包 `detail.errors[].field/label/message` 点名字段，用词与线路页提示一致；改写被拒时库中数字保持改前，历史报告不被清理。库侧另有四条同名 CHECK 约束兜底（迁移 `migrations/0001_line_param_checks.sql`，启动时自动执行，幂等），绕过接口直插库同样被拒。

## 开发与测试

```bash
docker compose exec api pytest -q
```

测试按职责分模块：`test_line_validation_unit.py`（例程六种非法+边界）、`test_line_api_reject.py`（接口拒测、进引擎前拦截、改写保旧）、`test_db_constraints.py`（裸连接直插败测）、`test_migration_legacy.py`（老库迁移幂等）、`test_b12_regression.py`（迁移后 B12 8/3/15 仍起服并检出市民中心串车）。
