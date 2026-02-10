

## PRD / 技术规格 v1.0

功能要点总结：
- 端到端内容处理流水线：面向微信公众号/知乎等文章的批量上传、清洗、分割、向量化、落库与检索召回，整体采用 Python + Airflow 实现可编排 ETL。 
- 多形态上传：支持手动上传 一个/多个压缩包（md + assets 图片目录）或 一个/多个 Markdown 文件。 
- Markdown 清洗与结构化增强：自动去除广告/日期等无意义片段；将文内图片链接替换为内部图床链接；调用外部**图生文（I2T）**服务并以 <i2t>...</i2t> 形式插入到图片位置下方。 
- 可配置分割策略：按配置的分隔符规则切片，支持最小/最大 token 约束；<i2t> 段落 不可被切割，需整体归并到相邻段。 
- 段落级内容增强：对每个分段支持生成 N 个关键词（外部 LLM）、抽取 N 对 Q&A；支持 滑动窗口 + 多层递进总结 产出多粒度段落摘要，并对摘要同样提取关键词。 
- 向量化与扩展能力：对分割/总结后的段落进行 embedding 生成向量；预留接口支持后续接入知识图谱生成等扩展。 
- 多存储落库：文本段落与关键词写入 Elasticsearch；向量写入 Elasticsearch / Milvus / ClickHouse。 
- 多路召回与融合排序：检索支持 ES 文本检索 + 向量检索（ES/Milvus/ClickHouse 可选）并行；支持对问题进行改写/关键词提取等优化后再召回；多路结果按加权分数融合排序。 
- 召回质量评测：集成 Ragas 框架对 RAG 召回质量进行测试评估。 
- 压测与性能对比：支持对检索接口压测，对比三种向量存储方案的性能表现。 
- 可视化 WebUI：上述上传、流程执行、检索/评测/压测等能力均可通过 WebUI 发起与配置，满足“可扩展、可配置、可视化”的目标。

### 0. 术语与约束
- **文章（Document）**：一篇 markdown 原文及其元信息（来源、标题、作者、时间等）。
- **段落（Chunk）**：分割后的最小检索单元。
- **派生段落（Derived Chunk）**：滑窗/多层总结产生的段落。
- **i2t 段**：图片转文本插入的 `<i2t>...</i2t>` 块。
- **向量（Embedding）**：对 Chunk 文本生成的向量。
- **图床链接**：系统内网访问即可，不要求公网。
- **目标**：可扩展、可配置、可视化 WebUI + 可 API 调用；Airflow 负责任务编排；支持 ES/Milvus/ClickHouse 落库与召回；支持 RAGAS 评测与压测。


## 1. 总体架构

### 1.1 模块划分（必须实现）
1. **Ingestion 服务**：上传 zip/md，解压、存储原始文件，创建处理任务。
2. **Storage 服务**
    - 原始文件存储：本地磁盘或对象存储（先默认本地）。
    - 图床服务：图片上传/访问。
3. **ETL Pipeline（Airflow）**
    - 清洗（clean）
    - 图片替换 + i2t 插入（i2t）
    - 分割（split）
    - 关键词提取（keywords）
    - Q&A 生成（qa）
    - 滑窗总结（summary，可选）
    - embedding（embed）
    - 落库（index）
4. **Retrieval 服务**：多路召回、Query 改写、融合排序。
5. **Evaluation 服务**：RAGAS 评测任务（离线/触发式）。
6. **Load Test 服务**：对检索接口压测（可用内置或集成 Locust/k6）。
7. **WebUI**：上传、配置、任务状态、召回测试、评测、压测页面。

### 1.2 技术栈建议（可替换，但需契约一致）
- Python 3.10+
- Airflow 2.x
- FastAPI（API + WebUI 后端）
- WebUI：React/Vue 任意；或先用 FastAPI + Jinja/简单前端（但要模块化）
- DB（任务与元数据）：Mysql
- Elasticsearch 8.x（文本索引 + 可选向量）
- Milvus 2.x（向量）
- ClickHouse（向量/检索实验）
- RAGAS（评测）

---

## 2. 数据模型（明确字段，便于直接建表/建索引）

### 2.1 元数据库表（Mysql）
#### documents
- `doc_id` (uuid, pk)
- `source_type` (enum: wechat/zhihu/manual)
- `title` (text, nullable)
- `author` (text, nullable)
- `published_at` (timestamp, nullable)
- `raw_storage_path` (text) 原始文件路径（md/zip 解压目录）
- `cleaned_markdown_path` (text, nullable)
- `status` (enum: uploaded/cleaned/splitted/indexed/failed)
- `created_at`, `updated_at`
- `error_message` (text, nullable)

#### assets
- `asset_id` (uuid, pk)
- `doc_id` (uuid, fk)
- `orig_path` (text)
- `mime_type` (text)
- `size` (bigint)
- `image_host_url` (text, nullable) 图床 URL
- `created_at`

#### chunks
- `chunk_id` (uuid, pk)
- `doc_id` (uuid, fk)
- `chunk_type` (enum: original/summary)
- `level` (int) 总结层级，原始为 0
- `window_size` (int, nullable)
- `order_index` (int) 在文档中的顺序
- `content` (text)
- `token_count` (int)
- `keywords` (jsonb, nullable) e.g. ["a","b"]
- `qas` (jsonb, nullable) e.g. [{"q":"", "a":""}]
- `embedding_status` (enum: pending/done/failed)
- `created_at`

#### embeddings（可选：也可不建表，只写向量库；但建议保留索引映射）
- `chunk_id` (uuid, pk, fk)
- `embedding_model` (text)
- `dim` (int)
- `vector_ref` (text) 指向 milvus/ch/es 的存储主键
- `created_at`

#### jobs（任务）
- `job_id` (uuid, pk)
- `job_type` (enum: ingest/etl/retrieval_eval/load_test)
- `params` (jsonb)
- `status` (queued/running/success/failed)
- `airflow_dag_run_id` (text, nullable)
- `created_at`, `updated_at`
- `error_message` (text, nullable)

---

## 3. 文件/压缩包规范（必须严格定义）

### 3.1 zip 上传格式
- zip 内必须包含 **一个且仅一个** `.md`
- 可包含 `assets/` 或任意目录，但 markdown 中图片引用必须能解析到 zip 内文件
- 示例：
```
xxx.zip
|- xxx.md
|- assets/
   |- 1.png
   |- 2.jpg
```

### 3.2 md 直接上传
- 允许上传多个 `.md`
- 若 md 引用本地图片：
    - v1.1 约束：仅支持与 md 同目录的 `assets/`（否则标记为 missing asset 并可配置“跳过/失败”）

---

## 4. ETL 处理规则（明确算法契约 + 可配置项）

### 4.1 清洗（clean）
#### 输入
- 原始 markdown 文本
#### 输出
- 清洗后的 markdown（仍为 markdown）
#### 规则（可配置，提供默认策略）
- 移除无意义片段：
    - 头部/尾部的广告、关注引导、版权声明、发布日期等
- 实现方式：
    - 支持 **规则链**：正则规则 + 关键字规则 + 可选 LLM 清洗（v1.1 默认不用 LLM 清洗）
- 配置项（config/clean.yaml）
    - `remove_regex: [ ... ]`
    - `remove_contains: [ ... ]`
    - `min_length_after_clean: 200`（低于则标记异常）

#### 验收
- 清洗后 token/字符数减少、且正文保留（至少不为空）
- 清洗前后可追溯：保存 diff 或保留原文路径

---

### 4.2 图片替换 + i2t（i2t）
#### 输入
- 清洗后的 markdown + 解析出的图片引用列表
#### 输出
- 图片链接替换为图床 URL 的 markdown
- 在图片引用后插入 `<i2t>...</i2t>`（若启用 i2t）

#### 处理流程
1. 解析 markdown 图片语法：`![](path)` / `![alt](path)`
2. 将 path 映射到本地 asset 文件
3. 上传至图床，返回 `image_host_url`
4. 替换 markdown 图片链接为 `image_host_url`
5. 若启用 i2t：
    - 调用外部图生文服务，生成文本 `t`
    - 在该图片 markdown 行后插入：
      ```
      <i2t>
      t
      </i2t>
      ```

#### 配置项（config/i2t.yaml）
- `enabled: true/false`
- `provider: aliyun_bailian/local`
- `timeout_sec`
- `max_retries`
- `fallback_on_error: skip/empty/fail`

#### 关键约束
- i2t 生成文本必须与图片一一对应，存储到 chunks 前保留在 markdown 中。

---

### 4.3 分割（split）
#### 输入
- 处理后的 markdown（包含 i2t）
#### 输出
- `chunks[]`（chunk content 为纯文本或 markdown？建议统一为纯文本，保留少量结构）

#### 规则
1. 支持配置多个分割符（按优先级匹配）：如 `\n## `、`\n### `、`\n\n` 等
2. Token 约束（使用同一 tokenizer）：
    - `min_tokens_per_chunk`
    - `max_tokens_per_chunk`
    - 超过 max：继续按更细粒度分隔符切
    - 小于 min：与前一段或后一段合并（可配置优先合并方向）
3. i2t 块不可被切割：
    - `<i2t>...</i2t>` 必须整体归属同一 chunk
    - 若 i2t 单独落在边界：按配置并入上一个或下一个
4. 输出 chunk 保留字段：`doc_id, order_index, content, token_count`

#### 配置项（config/split.yaml）
- `separators: ["\n## ", "\n### ", "\n\n", "\n"]`
- `min_tokens: 200`
- `max_tokens: 800`
- `merge_strategy: prefer_prev|prefer_next`
- `tokenizer: cl100k_base|...`

---

### 4.4 关键词提取（keywords）
#### 输入
- chunks
#### 输出
- 每个 chunk 的 `keywords: [string]`

#### 规则
- 对每个 chunk 调用 LLM（可云/本地）提取 N 个关键词
- 要求输出可解析 JSON 数组

#### 配置项（config/keywords.yaml）
- `enabled: true/false`
- `top_n: 8`
- `llm_provider`
- `prompt_template`
- `timeout_sec/retry`

---

### 4.5 Q&A 生成（qa）
#### 输入
- chunks
#### 输出
- 每个 chunk 的 `qas: [{"q": "...", "a": "..."}]`

#### 配置项（config/qa.yaml）
- `enabled: true/false`
- `top_n: 3`
- `llm_provider`
- `prompt_template`（要求 JSON 输出）

---

### 4.6 滑窗总结（summary，可选）
#### 输入
- 原始 chunks（level=0）
#### 输出
- 多层 summary chunks（level>=1），并对 summary chunk 也要抽关键词、embedding、落库

#### 规则（按你的描述形式化）
- 给定：
    - window size = N（例如 2）
    - layers = M（例如 3）
- 第 1 层：对相邻 N 个 chunk 做总结，步长 1  
  若原始有 5 段，N=2：产生 4 段 summary
- 第 2 层：对第 1 层结果再做同样滑窗总结，直到层数 M 或段落数不足 N
- 每次总结限制 `max_tokens_summary`
- summary chunk 的 `chunk_type=summary`，记录 `level` 与 `window_size`

#### 配置项（config/summary.yaml）
- `enabled`
- `window_size`
- `layers`
- `max_tokens_summary`
- `llm_provider`
- `prompt_template`

---

### 4.7 Embedding（embed）
#### 输入
- 所有最终 chunks（原始+summary，如果启用）
#### 输出
- 每个 chunk 的向量

#### 配置项（config/embed.yaml）
- `provider: openai|bge-m3|...`
- `model`
- `dim`
- `batch_size`
- `timeout_sec/retry`

---

## 5. 落库（index）

### 5.1 Elasticsearch（文本 + 可选向量）
#### Index: `chunks_v1`
字段建议：
- `chunk_id` keyword
- `doc_id` keyword
- `chunk_type` keyword
- `level` integer
- `order_index` integer
- `content` text（启用中文分词）
- `keywords` keyword（或 text+keyword multi-field）
- `qas` nested（可选）
- `embedding` dense_vector（可选，如果也存 ES 向量）
- `created_at` date

### 5.2 Milvus
Collection: `chunks_embedding_v1`
- primary key: `chunk_id`
- vector: float32[dim]
- scalar fields: doc_id, level, chunk_type, order_index

### 5.3 ClickHouse
表：`chunks_embedding_v1`
- chunk_id UUID
- doc_id UUID
- content String
- embedding Array(Float32) 或 Vector 类型（看 CH 版本能力）
- 额外字段同上

### 5.4 可配置落库开关
（config/index.yaml）
- `enable_es_text: true`
- `enable_es_vector: false/true`
- `enable_milvus: true`
- `enable_clickhouse: true`

---

## 6. 召回（Retrieval API）

### 6.1 API：`POST /api/retrieve`
请求：
```json
{
  "query": "用户问题",
  "top_k": 20,
  "routes": {
    "es_text": true,
    "vector": {
      "enabled": true,
      "backend": "milvus|es|clickhouse"
    }
  },
  "rewrite": {
    "enabled": true,
    "method": "keywords|llm",
    "params": {}
  },
  "fusion": {
    "method": "weighted_sum|rrf",
    "weights": { "es_text": 0.5, "vector": 0.5 }
  },
  "filters": {
    "doc_ids": [],
    "source_type": []
  }
}
```

响应：
```json
{
  "query_used": "...",
  "results": [
    {
      "chunk_id": "...",
      "doc_id": "...",
      "score": 1.234,
      "route_scores": { "es_text": 3.2, "vector": 0.78 },
      "content": "...",
      "keywords": ["..."],
      "metadata": { "level": 0, "order_index": 3 }
    }
  ]
}
```

### 6.2 Query 改写
- `keywords`：从 query 抽关键词作为 ES 查询增强
- `llm`：生成更适合检索的 query（要求输出 JSON：`{"query": "...", "keywords": [...]}`）

### 6.3 融合排序
- `weighted_sum`: 归一化后加权求和（必须定义归一化：min-max 或 z-score；v1.1 用 min-max）
- `rrf`: Reciprocal Rank Fusion（更稳健，建议提供）

---

## 7. RAGAS 召回质量测试

### 7.1 入口
- WebUI 触发 / API 触发：
    - 选择数据集（Q/A ground truth 或标注文件）
    - 选择检索参数（routes、fusion、rewrite）
    - 输出报表（JSON + 可视化）

### 7.2 数据集格式（先定义最简单）
- JSONL：
```json
{"question":"...","ground_truth":["...可选答案或参考段落..."],"doc_id":"...可选"}
```

### 7.3 输出
- ragas 指标结果（按官方）
- 失败案例列表（query、召回内容、得分）

---

## 8. 压测

### 8.1 目标
- 对 `/api/retrieve` 做压测
- 对比 3 种向量后端（ES/Milvus/CH）的吞吐、TP50/90/99、错误率

### 8.2 方式
- 内置简单压测：并发 C、持续 T、输入 queries 文件
- 或集成 Locust：提供脚本与 WebUI 配置入口（推荐）

---

## 9. WebUI（功能清单 + 页面）

### 9.1 页面
1. **上传页面**
    - 上传 zip/md
    - 展示解析结果（md 数量、图片数量、缺失资源）
2. **任务中心**
    - job 列表、状态、日志链接、失败重试
3. **配置页面**
    - clean/split/i2t/keywords/qa/summary/embed/index/retrieve 配置
    - 配置版本管理（至少保留当前生效配置 + 历史）
4. **检索调试页面**
    - 输入 query，选择召回路由与融合方式，展示结果与分数分解
5. **RAGAS 评测页面**
6. **压测页面**

---

## 10. Airflow DAG 设计（便于直接生成代码）

### 10.1 DAG：`doc_etl_v1`
Task 顺序（建议每步幂等）：
1. `load_raw`（读取 doc_id 对应文件）
2. `clean_markdown`
3. `upload_assets_and_replace_links`
4. `run_i2t`（可选）
5. `split_chunks`
6. `extract_keywords`（可选）
7. `generate_qas`（可选）
8. `summarize_sliding_window`（可选）
9. `embed_chunks`
10. `index_to_es`
11. `index_to_milvus`
12. `index_to_clickhouse`
13. `mark_done`

### 10.2 幂等要求
- 同一 `doc_id` 重跑不会重复写入导致脏数据：
    - 写入前按 `chunk_id` upsert / delete-then-insert
    - 图床上传可根据 hash 去重（可选）

---

## 11. 配置系统（必须实现）

### 11.1 配置原则
- 所有关键参数可通过 YAML/JSON 配置
- WebUI 修改后写入配置中心（DB 或 config 文件），Airflow 运行时读取“版本化配置”

### 11.2 配置版本
- `config_version_id`
- 生效版本标记
- 每次运行 job 记录使用的配置版本，便于回放与对比

---

## 12. 错误处理与可观测性（实现必要条件）
- 每个 doc/job 有明确状态机与错误信息
- 每个 task 记录耗时、输入输出统计（chunk 数、token 数、图片数、embedding 数）
- 日志可在 WebUI 查看（或跳转 Airflow log）

---

## 13. 验收标准（可直接转测试用例）

### 上传
- 上传 zip：能识别 md 与 assets；缺失图片时按配置失败/跳过
- 上传多个 md：每个 md 生成独立 doc_id

### 清洗
- 能按规则删除头尾噪声；清洗后不为空且长度达标

### 图片替换 + i2t
- 图片 URL 替换为图床 URL
- i2t 插入位置正确且格式严格为 `<i2t>...</i2t>`

### 分割
- chunk token 数满足 min/max（允许最后一段略小但要可配置）
- i2t 块不被切开

### 关键词/Q&A
- 输出为合法 JSON；数量满足 N；失败策略可控

### 总结
- 层数与数量符合滑窗规则；summary chunks 同样入库与可召回

### 落库
- ES 可用文本检索查到 chunk
- 向量后端可按 chunk_id 查到对应向量

### 召回
- 多路召回可开关；融合分数可解释（返回 route_scores）
- rewrite 开关生效

### RAGAS
- 可跑通并产出指标与失败样本

### 压测
- 能对不同后端输出对比数据

---

## 14. 预留扩展点（接口契约）
### 14.1 知识图谱
- split 后提供 hook：`on_chunks_ready(doc_id, chunks[]) -> graph_nodes_edges`
- graph 存储与展示暂不做，但接口保留

---

## 15. 功能要点总结（【重要】，不要忘记自己要做什么）
功能要点总结：
- 端到端内容处理流水线：面向微信公众号/知乎等文章的批量上传、清洗、分割、向量化、落库与检索召回，整体采用 Python + Airflow 实现可编排 ETL。
- 多形态上传：支持手动上传 一个/多个压缩包（md + assets 图片目录）或 一个/多个 Markdown 文件。
- Markdown 清洗与结构化增强：自动去除广告/日期等无意义片段；将文内图片链接替换为内部图床链接；调用外部**图生文（I2T）**服务并以 <i2t>...</i2t> 形式插入到图片位置下方。
- 可配置分割策略：按配置的分隔符规则切片，支持最小/最大 token 约束；<i2t> 段落 不可被切割，需整体归并到相邻段。
- 段落级内容增强：对每个分段支持生成 N 个关键词（外部 LLM）、抽取 N 对 Q&A；支持 滑动窗口 + 多层递进总结 产出多粒度段落摘要，并对摘要同样提取关键词。
- 向量化与扩展能力：对分割/总结后的段落进行 embedding 生成向量；预留接口支持后续接入知识图谱生成等扩展。
- 多存储落库：文本段落与关键词写入 Elasticsearch；向量写入 Elasticsearch / Milvus / ClickHouse。
- 多路召回与融合排序：检索支持 ES 文本检索 + 向量检索（ES/Milvus/ClickHouse 可选）并行；支持对问题进行改写/关键词提取等优化后再召回；多路结果按加权分数融合排序。
- 召回质量评测：集成 Ragas 框架对 RAG 召回质量进行测试评估。
- 压测与性能对比：支持对检索接口压测，对比三种向量存储方案的性能表现。
- 可视化 WebUI：上述上传、流程执行、检索/评测/压测等能力均可通过 WebUI 发起与配置，满足“可扩展、可配置、可视化”的目标。

