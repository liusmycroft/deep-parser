# Deep Parser — 任务进度跟踪

> 每完成一个任务打 ✅，进行中标 🔄，未开始标 ⬜
>
> 最后更新：2026-02-09

---

**总体进度：26/26 ✅ — 完成率 100%**

---

## Phase 1: 项目基础设施

| # | 任务 | 状态 | 关键文件 |
|---|------|------|---------|
| 1.1 | 项目脚手架搭建（pyproject.toml、目录结构、依赖） | ✅ | `pyproject.toml` |
| 1.2 | 配置系统实现（YAML 加载 + 版本化配置） | ✅ | `config/settings.py`, `config/versioned_config.py` |
| 1.3 | 数据库 ORM 模型（5张表） | ✅ | `models/document.py`, `models/chunk.py`, `models/job.py` 等 |
| 1.4 | 数据库迁移（Alembic） | ✅ | `alembic/`, `alembic.ini` |
| 1.5 | 日志与错误处理框架 | ✅ | `logging_config.py` |
| 1.6 | FastAPI 应用骨架 | ✅ | `main.py` |

## Phase 2: Ingestion 服务

| # | 任务 | 状态 | 关键文件 |
|---|------|------|---------|
| 2.1 | 文件存储服务与图床服务 | ✅ | `services/storage.py`, `services/image_host.py` |
| 2.2 | ZIP/MD 上传解析与上传 API | ✅ | `services/ingestion.py`, `api/upload.py` |

## Phase 3: ETL Pipeline 核心

| # | 任务 | 状态 | 关键文件 |
|---|------|------|---------|
| 3.1 | LLM 服务抽象层 | ✅ | `services/llm_service.py` |
| 3.2 | 清洗模块（clean） | ✅ | `etl/clean.py` |
| 3.3 | 图片替换 + I2T 模块 | ✅ | `etl/i2t.py` |
| 3.4 | 分割模块（split） | ✅ | `etl/split.py` |
| 3.5 | 关键词提取模块（keywords） | ✅ | `etl/keywords.py` |
| 3.6 | Q&A 生成模块（qa） | ✅ | `etl/qa.py` |
| 3.7 | 滑窗总结模块（summary） | ✅ | `etl/summary.py` |
| 3.8 | Embedding 模块（embed） | ✅ | `etl/embed.py` |

## Phase 4: 多存储落库

| # | 任务 | 状态 | 关键文件 |
|---|------|------|---------|
| 4.1 | Elasticsearch 索引与写入 | ✅ | `indexing/es_indexer.py` |
| 4.2 | Milvus Collection 与写入 | ✅ | `indexing/milvus_indexer.py` |
| 4.3 | ClickHouse 表与写入 | ✅ | `indexing/clickhouse_indexer.py` |
| 4.4 | 落库编排与开关配置 | ✅ | `indexing/index_manager.py` |

## Phase 5: Airflow DAG 编排

| # | 任务 | 状态 | 关键文件 |
|---|------|------|---------|
| 5.1 | Airflow DAG 实现（doc_etl_v1） | ✅ | `dags/doc_etl_v1.py` |

## Phase 6: 召回服务

| # | 任务 | 状态 | 关键文件 |
|---|------|------|---------|
| 6.1 | 召回服务（多路检索+改写+融合排序+API） | ✅ | `retrieval/query_rewriter.py`, `retrieval/fusion.py`, `retrieval/retriever.py`, `api/retrieve.py` |

## Phase 7: 评测与压测

| # | 任务 | 状态 | 关键文件 |
|---|------|------|---------|
| 7.1 | RAGAS 评测集成与 API | ✅ | `evaluation/ragas_eval.py`, `api/evaluate.py` |
| 7.2 | 压测模块（Locust）与 API | ✅ | `loadtest/load_tester.py`, `loadtest/locustfile.py`, `api/loadtest.py` |

## Phase 8: WebUI 前端

| # | 任务 | 状态 | 关键文件 |
|---|------|------|---------|
| 8.1 | WebUI 前端实现（6个页面） | ✅ | `webui/routes.py`, `webui/templates/` |

## Phase 9: 扩展与收尾

| # | 任务 | 状态 | 关键文件 |
|---|------|------|---------|
| 9.1 | 知识图谱预留接口 + Docker Compose + 文档 | ✅ | `hooks/knowledge_graph.py`, `docker-compose.yaml`, `Dockerfile`, `README.md` |

---

## 额外完成的 API

| API | 状态 | 关键文件 |
|-----|------|---------|
| 任务管理 API（GET/POST /api/jobs） | ✅ | `api/jobs.py` |
| 配置管理 API（GET/PUT /api/config） | ✅ | `api/config_api.py` |

---

## 变更记录

| 日期 | 变更内容 |
|------|---------|
| 2026-02-09 | 初始化计划与任务列表 |
| 2026-02-09 | Phase 1-9 全部完成，所有 26 个任务标记为 ✅ |
