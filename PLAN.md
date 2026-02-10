# Deep Parser — 实施计划

> 基于 PRD v1.0，构建端到端 RAG 内容处理系统

## 项目概览

面向微信公众号/知乎等文章的批量上传、清洗、分割、向量化、落库与检索召回系统。
采用 Python + Airflow 实现可编排 ETL，支持 ES/Milvus/ClickHouse 多存储，提供 WebUI 可视化操作。

## 技术栈

- **语言**: Python 3.10+
- **Web 框架**: FastAPI
- **任务编排**: Airflow 2.x
- **元数据库**: MySQL (SQLAlchemy 2.0 async + Alembic 迁移)
- **文本索引**: Elasticsearch 8.x
- **向量存储**: Milvus 2.x / Elasticsearch / ClickHouse
- **LLM/Embedding**: OpenAI API
- **评测**: RAGAS
- **压测**: Locust + 内置 httpx 压测
- **前端**: FastAPI + Jinja2 + Bootstrap 5
- **部署**: Docker Compose
- **日志**: Loguru
- **配置**: Pydantic Settings + YAML

## 目录结构

```
deep-parser/
├── pyproject.toml                     # 项目依赖与元信息
├── config.example.yaml                # 配置示例
├── .env.example                       # 环境变量示例
├── README.md                          # 项目文档
├── docker-compose.yaml                # 容器编排
├── alembic.ini                        # Alembic 配置
├── alembic/                           # 数据库迁移
│   └── versions/
├── config/                            # 默认配置文件
│   ├── clean.yaml
│   ├── split.yaml
│   ├── i2t.yaml
│   ├── keywords.yaml
│   ├── qa.yaml
│   ├── summary.yaml
│   ├── embed.yaml
│   └── index.yaml
├── src/
│   └── deep_parser/
│       ├── __init__.py
│       ├── main.py                    # FastAPI 入口
│       ├── config/                    # 配置系统
│       │   ├── __init__.py
│       │   ├── settings.py            # 全局配置
│       │   └── versioned_config.py    # 版本化配置管理
│       ├── models/                    # ORM 模型
│       │   ├── __init__.py
│       │   ├── database.py
│       │   ├── document.py
│       │   ├── asset.py
│       │   ├── chunk.py
│       │   ├── embedding.py
│       │   └── job.py
│       ├── api/                       # API 路由
│       │   ├── __init__.py
│       │   ├── upload.py
│       │   ├── retrieve.py
│       │   ├── evaluate.py
│       │   ├── loadtest.py
│       │   ├── jobs.py
│       │   └── config_api.py
│       ├── services/                  # 业务逻辑
│       │   ├── __init__.py
│       │   ├── ingestion.py           # 上传解析
│       │   ├── storage.py             # 文件存储
│       │   ├── image_host.py          # 图床
│       │   └── llm_service.py         # LLM 抽象层
│       ├── etl/                       # ETL 处理模块
│       │   ├── __init__.py
│       │   ├── clean.py
│       │   ├── i2t.py
│       │   ├── split.py
│       │   ├── keywords.py
│       │   ├── qa.py
│       │   ├── summary.py
│       │   └── embed.py
│       ├── indexing/                  # 落库
│       │   ├── __init__.py
│       │   ├── es_indexer.py
│       │   ├── milvus_indexer.py
│       │   └── clickhouse_indexer.py
│       ├── retrieval/                 # 召回
│       │   ├── __init__.py
│       │   ├── retriever.py
│       │   ├── query_rewriter.py
│       │   └── fusion.py
│       ├── evaluation/                # 评测
│       │   ├── __init__.py
│       │   └── ragas_eval.py
│       ├── loadtest/                  # 压测
│       │   ├── __init__.py
│       │   └── load_tester.py
│       └── hooks/                     # 扩展点
│           ├── __init__.py
│           └── knowledge_graph.py
├── dags/                              # Airflow DAGs
│   └── doc_etl_v1.py
│       ├── webui/                      # WebUI 前端
│       │   ├── routes.py              # 页面路由
│       │   └── templates/             # Jinja2 模板
│       │       ├── base.html
│       │       ├── upload.html
│       │       ├── jobs.html
│       │       ├── config.html
│       │       ├── search.html
│       │       ├── evaluate.html
│       │       └── loadtest.html
└── tests/
    ├── conftest.py
    └── ...
```

## 实施阶段

### Phase 1: 项目基础设施
搭建项目骨架、配置系统、数据库模型、FastAPI 应用框架。这是所有后续模块的基础。

### Phase 2: Ingestion 服务
实现文件上传（zip/md）、解压校验、本地存储、图床服务。

### Phase 3: ETL Pipeline 核心
实现清洗、图片替换+I2T、分割、关键词提取、Q&A 生成、滑窗总结、Embedding 等处理模块。

### Phase 4: 落库（Index）
实现 Elasticsearch、Milvus、ClickHouse 三种存储的写入，支持可配置开关。

### Phase 5: Airflow DAG 编排
实现 `doc_etl_v1` DAG，串联所有 ETL 步骤，保证幂等性。

### Phase 6: 召回服务（Retrieval）
实现多路召回、Query 改写、融合排序，提供 `/api/retrieve` 接口。

### Phase 7: 评测与压测
集成 RAGAS 评测框架，实现压测模块，支持多后端性能对比。

### Phase 8: WebUI
实现上传、任务中心、配置、检索调试、评测、压测等页面。

### Phase 9: 扩展与收尾
知识图谱预留接口、Docker Compose 部署、测试、文档。
