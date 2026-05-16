# Three Chain System Demo Backend

`system_demo_backend` 是三链仿真系统 demo 的后端层。它不替代原始仿真脚本，而是在原始脚本之上增加：

- MySQL 入库。
- 批次管理。
- FastAPI HTTP 接口。
- 前端可直接调用的汇总和分析接口。

原始数据仿真器位于：

```text
../three_chain_mock_generator_v2.py
```

## 当前架构

```text
前端页面
  -> HTTP API
FastAPI 后端
  -> 调用 three_chain_mock_generator_v2.py
  -> 生成 CSV / Excel
  -> 写入 MySQL
MySQL
  -> 34 张仿真数据表
  -> 1 张 simulation_run 批次表
```

## 目录结构

```text
system_demo_backend/
  app/
    __init__.py
    main.py              FastAPI 路由入口
    services.py          生成、入库、查询、分析逻辑
    db.py                MySQL 连接和元数据表初始化
    config.py            环境变量和路径配置
    generator_bridge.py  动态加载原始仿真脚本
  .env                   本机真实数据库连接配置
  .env.example           配置模板
  requirements.txt       pip 依赖参考
  README.md              当前说明文档
```

## Conda 环境

当前已创建命名环境：

```text
sanlian -> D:\anaconda3\envs\sanlian
```

激活环境：

```bash
conda activate sanlian
```

核心依赖包括：

- `fastapi`
- `uvicorn`
- `pandas`
- `sqlalchemy`
- `pymysql`
- `python-dotenv`
- `openpyxl`

如需重新安装依赖：

```bash
conda install -n sanlian fastapi uvicorn pandas sqlalchemy pymysql python-dotenv openpyxl
```

## MySQL 配置

当前本机 MySQL 状态：

- 服务名：`MySQL80`
- 端口：`127.0.0.1:3306`
- 数据库：`three_chain_demo`
- 后端通过 `.env` 中的 `DATABASE_URL` 连接 MySQL。

创建数据库的 SQL：

```sql
CREATE DATABASE IF NOT EXISTS three_chain_demo
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

`.env` 示例：

```text
DATABASE_URL=mysql+pymysql://root:你的密码@127.0.0.1:3306/three_chain_demo?charset=utf8mb4
API_HOST=127.0.0.1
API_PORT=8000
```

说明：
s
- `.env.example` 是模板。
- `.env` 是本机真实配置。
- 不建议把 `.env` 提交到远程仓库。

## run_id 设计

每次后端生成数据时，会创建一个新的 `run_id`，例如：

```text
20260512_163732
```

同一个 `run_id` 会同时用于：

- 文件输出目录：`mock_output_v2/{run_id}/`
- MySQL 中每张业务表的 `run_id` 字段
- `simulation_run.run_id`
- 前端 API 查询路径

数据库会多一张批次表：

```text
simulation_run
- run_id
- run_name
- generated_at
- output_dir
- seed
- status
- error_message
```

每张业务表写入 MySQL 时会额外增加 `run_id` 字段。CSV 文件本身不增加这个字段。

示例：

```text
CSV:
vehicle_id,product_id,vehicle_code,...

MySQL:
run_id,vehicle_id,product_id,vehicle_code,...
```

重要：前端查询时必须使用 MySQL 里存在且 `status = SUCCESS` 的 `run_id`。  
先调用 `GET /runs`，复制返回的 `run_id`，再查询 summary 或 gap。

## 启动后端

在项目根目录或 `system_demo_backend` 目录均可启动。推荐：

```bash
conda activate sanlian
cd system_demo_backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动后访问：

```text
http://127.0.0.1:8000/docs
```

这是 FastAPI 自动生成的 Swagger 调试页面。

前端页面入口：

```text
http://127.0.0.1:8000/frontend
```

说明：

- 驾驶舱、数据表、风险缺口模块只调用 FastAPI，不直接读 CSV，也不直接连 MySQL。
- 本体管理模块保留原 Demo 的前端静态本体图谱，不依赖后端本体接口，支持领域筛选、节点拖拽、滚轮缩放和点击节点查看详情。

## API 总览

### 1. 健康检查

```http
GET /health
```

返回：

```json
{"status": "ok"}
```

### 2. 查看所有批次

```http
GET /runs
```

用途：

- 查看哪些仿真批次已经写入 MySQL。
- 获取后续接口需要使用的 `run_id`。

返回示例：

```json
[
  {
    "run_id": "20260512_163732",
    "run_name": "initial_mysql_test_from_root",
    "generated_at": "2026-05-12T16:37:33",
    "output_dir": "D:/.../mock_output_v2/20260512_163732",
    "seed": 42,
    "status": "SUCCESS",
    "error_message": null
  }
]
```

也可以直接获取最新成功批次：

```http
GET /runs/latest
```

后端会返回 `status = SUCCESS` 且 `generated_at` 最新的一条运行记录。前端如果不想让用户手动选择批次，可以默认使用这个接口返回的 `run_id`。

### 3. 表字段与本体映射

```http
GET /ontology/table-field-mapping
```

用途：

- 返回“数据表 / 表头 / 字段”和“三链本体类 / 本体节点 / 本体属性 / 本体关系”的对应关系。
- 前端可用该接口展示每张仿真表为什么能映射到本体。
- 该接口不依赖 `run_id`，描述的是当前数据结构和本体结构之间的固定映射。

返回内容包括：

- `mapping_types`：字段映射类型说明。
- `mappings`：每张表的本体映射。
- `table_name`：数据库表名。
- `table_label`：中文表名。
- `ontology_class`：对应本体类。
- `ontology_domain`：所属本体业务域。
- `fields`：字段级映射列表。

字段映射类型：

- `data_property`：字段对应本体数据属性，例如数量、日期、名称、成本。
- `object_property`：字段对应本体对象关系，例如 `bom_line_item.component_module_id -> consumesProduct -> Module`。
- `class_discriminator`：字段用于区分本体子类，例如 `supply_chain_node.node_type = PLANT -> Plant`。

返回示例：

```json
{
  "mappings": [
    {
      "table_name": "vehicle",
      "table_label": "整车表",
      "ontology_class": "Vehicle",
      "ontology_domain": "Product Domain",
      "fields": [
        {
          "field_name": "vehicle_id",
          "ontology_target": "Vehicle.productId",
          "mapping_type": "data_property"
        }
      ]
    }
  ]
}
```

### 4. 本体类列表

```http
GET /ontology/classes
GET /ontology/classes?run_id=20260512_163732
GET /ontology/classes?run_id=latest
```

用途：

- 返回前端可以展示成按钮的本体类清单。
- 如果传入 `run_id`，会同时返回该批次下每个本体类对应的数据条数。
- `run_id=latest` 表示使用最新成功批次。
- 前端可以据此禁用当前没有实例数据的本体类按钮，或展示“暂无实例”。

返回示例：

```json
[
  {
    "ontology_class": "Vehicle",
    "ontology_domain": "Product Domain",
    "source_table": "vehicle",
    "filters": {},
    "has_table": true,
    "row_count": 8,
    "description": "整车 SKU 实例。"
  },
  {
    "ontology_class": "Plant",
    "ontology_domain": "Network Domain",
    "source_table": "supply_chain_node",
    "filters": {"node_type": "PLANT"},
    "has_table": true,
    "row_count": 4,
    "description": "工厂节点。由 supply_chain_node.node_type = PLANT 表示。"
  }
]
```

### 5. 查看某个本体类的实例记录

```http
GET /runs/{run_id}/ontology/classes/{ontology_class}/records
GET /ontology/classes/{ontology_class}/records
```

用途：

- 前端点击某个本体节点按钮后，调用该接口返回该本体类在当前批次下的全部实例记录。
- 支持分页参数：`page`、`page_size`。
- 如果不传具体 `run_id`，可以直接调用 `/ontology/classes/{ontology_class}/records`，后端默认使用最新成功批次。
- `{run_id}` 也可以传 `latest`，例如 `/runs/latest/ontology/classes/Vehicle/records`。

示例：

```http
GET /runs/20260512_163732/ontology/classes/Vehicle/records?page=1&page_size=100
GET /runs/20260512_163732/ontology/classes/Plant/records?page=1&page_size=100
GET /runs/20260512_163732/ontology/classes/SupplierSite/records?page=1&page_size=100
GET /ontology/classes/Vehicle/records?page=1&page_size=100
GET /runs/latest/ontology/classes/Plant/records?page=1&page_size=100
```

返回示例：

```json
{
  "run_id": "20260512_163732",
  "ontology_class": "Plant",
  "ontology_domain": "Network Domain",
  "source_table": "supply_chain_node",
  "filters": {"node_type": "PLANT"},
  "page": 1,
  "page_size": 100,
  "total": 4,
  "records": [
    {
      "run_id": "20260512_163732",
      "node_id": "NOD0001",
      "node_type": "PLANT"
    }
  ],
  "data_status": "ok"
}
```

说明：

- `Plant`、`SupplierSite`、`DistributionCenter`、`DeliveryCenter` 都来自 `supply_chain_node` 表，通过 `node_type` 区分。
- `Component`、`RawMaterial` 当前本体里有定义，但仿真数据暂未实例化，接口会返回空记录。
- `SourcingPolicy` 当前本体里有定义，但仿真器尚未生成对应表，接口会返回 `data_status = not_instantiated`。

### 6. 生成新批次

```http
POST /runs/generate
```

请求体：

```json
{
  "run_name": "baseline",
  "seed": 42
}
```

后端会执行：

1. 调用原始仿真器。
2. 生成 `mock_output_v2/{run_id}/`。
3. 导出 34 个 CSV 和 1 个 Excel。
4. 将 34 张表写入 MySQL。
5. 写入或更新 `simulation_run`。

返回示例：

```json
{
  "run_id": "20260512_163732",
  "run_name": "baseline",
  "status": "SUCCESS",
  "output_dir": "D:/.../mock_output_v2/20260512_163732",
  "excel_exported": true,
  "excel_path": "D:/.../three_chain_mock_data_v2.xlsx",
  "table_count": 34,
  "tables": [
    {"table_name": "vehicle", "row_count": 8},
    {"table_name": "module", "row_count": 24}
  ],
  "summary": {
    "vehicle_count": 8,
    "module_count": 24,
    "forecast_demand_qty": 37907.0
  }
}
```

### 7. 查看某批次有哪些表

```http
GET /runs/{run_id}/tables
```

返回示例：

```json
[
  {"table_name": "product", "row_count": 8},
  {"table_name": "vehicle", "row_count": 8},
  {"table_name": "demand", "row_count": 2196}
]
```

如果 `run_id` 不存在或不是成功批次，会返回 `404`。

### 8. 查看某张表数据

```http
GET /runs/{run_id}/tables/{table_name}?page=1&page_size=50
```

示例：

```http
GET /runs/20260512_163732/tables/demand?page=1&page_size=50
```

返回：

```json
{
  "table_name": "demand",
  "page": 1,
  "page_size": 50,
  "total": 2196,
  "rows": []
}
```

这个接口适合前端做原始数据浏览器。

### 9. 批次摘要

```http
GET /runs/{run_id}/summary
```

返回示例：

```json
{
  "run_id": "20260512_163732",
  "vehicle_count": 8,
  "module_count": 24,
  "forecast_demand_qty": 37907,
  "order_demand_qty": 844,
  "material_need_qty": 763695,
  "on_hand_qty": 28780,
  "inbound_qty": 74052,
  "weekly_capacity_qty": 815621.3
}
```

这个接口适合 dashboard 首页。

### 10. 物料供需缺口

```http
GET /runs/{run_id}/demand-supply-gap?limit=100
```

基于这些表计算：

- `fact_material_need_week`
- `fact_inventory_snapshot`
- `fact_inbound_eta`

返回字段：

```text
module_id
week_start
need_qty
inventory_qty
inbound_qty
gap_qty
risk_level
```

返回示例：

```json
[
  {
    "module_id": "MOD0015",
    "week_start": "2026-03-30",
    "need_qty": 13672,
    "inventory_qty": 1624,
    "inbound_qty": 213,
    "gap_qty": 11835,
    "risk_level": "HIGH"
  }
]
```

### 11. 产能缺口

```http
GET /runs/{run_id}/capacity-gap?limit=100
```

基于这些表计算：

- `fact_demand_week`
- `fact_capacity_week`

返回字段：

```text
vehicle_id
plant_node_id
week_start
demand_qty
capacity_qty
gap_qty
risk_level
```

## 常见问题

### 1. 为什么 summary 全是 0？

通常是 `run_id` 用错了。

例如：

```text
mock_output_v2/20260512_150337/
```

这个可能只是文件输出批次，不一定写入了 MySQL。API 查询 MySQL，只认数据库里的成功批次。

正确做法：

1. 调用 `GET /runs`。
2. 找到 `status = SUCCESS` 的 `run_id`。
3. 用这个 `run_id` 查询 summary 或 gap。

当前接口已经增强：如果传入不存在的成功 `run_id`，会返回 `404`，而不是静默返回 0。

### 2. Swagger 里的 `{run_id}` 怎么填？

不要填 `{run_id}` 字面量，也不要填 `run_name`。

应该填真实批次号，例如：

```text
20260512_163732
```

### 3. CSV 文件夹和 MySQL 批次是什么关系？

- 直接运行 `python three_chain_mock_generator_v2.py`：只生成 CSV / Excel，不写 MySQL。
- 调用 `POST /runs/generate`：生成 CSV / Excel，并写入 MySQL。

只有后者生成的 `run_id` 才能被 API 查询。

### 4. 修改后端代码后 Swagger 没变化怎么办？

重启后端：

```bash
Ctrl+C
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 5. MySQL 连不上怎么办？

检查：

```powershell
Get-Service MySQL80
Test-NetConnection 127.0.0.1 -Port 3306
```

确认 `.env` 中：

```text
DATABASE_URL=mysql+pymysql://root:你的密码@127.0.0.1:3306/three_chain_demo?charset=utf8mb4
```

## 前端对接建议

前端推荐页面顺序：

1. 批次列表页：`GET /runs`
2. 数据生成按钮：`POST /runs/generate`
3. 仪表盘页：`GET /runs/{run_id}/summary`
4. 原始表浏览页：
   - `GET /runs/{run_id}/tables`
   - `GET /runs/{run_id}/tables/{table_name}`
5. 物料风险页：`GET /runs/{run_id}/demand-supply-gap`
6. 产能风险页：`GET /runs/{run_id}/capacity-gap`

前端不要直接读 CSV，也不要直接连 MySQL。前端只调用 FastAPI。

## 前后端对齐测试

启动后端且确认 MySQL 可用后，在项目根目录运行：

```bash
python system_demo_backend/check_alignment.py
```

该脚本会按前端实际依赖顺序检查：

1. `GET /health`
2. `GET /runs`
3. `GET /runs/latest`
4. `GET /runs/{run_id}/summary`
5. `GET /runs/{run_id}/tables`
6. `GET /runs/{run_id}/tables/{table_name}`
7. `GET /runs/{run_id}/demand-supply-gap`
8. `GET /runs/{run_id}/capacity-gap`

如果 `/runs/latest` 返回 404，说明数据库里还没有 `status = SUCCESS` 的批次，需要先在前端点击“生成”，或通过 Swagger 调用 `POST /runs/generate`。

## 当前边界

这是系统 demo 后端，不是最终生产系统。

当前重点是：

- 能生成批次。
- 能写入 MySQL。
- 能查询原始表。
- 能返回 dashboard 汇总。
- 能做基础供需缺口和产能缺口分析。

后续可增强：

- 增加场景参数。
- 增加批次删除接口。
- 增加批次对比接口。
- 增加更精细的风险等级。
- 增加前端图表接口。
