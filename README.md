# Deep Parser

A comprehensive RAG (Retrieval-Augmented Generation) content processing system for article ingestion, ETL, indexing, and retrieval.

## Overview

Deep Parser is an end-to-end solution designed to process unstructured documents, extract structured information, and enable intelligent retrieval through advanced vector search and knowledge graph capabilities. The system provides a robust API for document upload, processing pipeline management, and semantic search.

## Features

- **Document Ingestion**: Support for multiple document formats with automatic encoding detection
- **ETL Pipeline**: Configurable extraction, transformation, and loading workflows
- **Vector Search**: Integration with Milvus for high-performance similarity search
- **Full-text Search**: Elasticsearch integration for keyword-based retrieval
- **Knowledge Graph**: Extensible hook system for knowledge graph extraction
- **Analytics**: ClickHouse integration for storing and analyzing retrieval metrics
- **Evaluation**: Built-in RAGAS evaluation framework for quality assessment
- **Load Testing**: Locust-based performance testing capabilities
- **Workflow Orchestration**: Apache Airflow integration for complex ETL pipelines
- **RESTful API**: FastAPI-based interface with automatic OpenAPI documentation

## Architecture

The system follows a modular architecture with clear separation of concerns:

```
┌─────────────────┐
│   Client Apps   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  FastAPI API    │  ← This project (docker-compose.yaml)
│  (Port 8000)    │
└────────┬────────┘
         │  (connects via API/SDK)
         ├────────────┬────────────┬────────────┬────────────┐
         ▼            ▼            ▼            ▼            ▼
┌─────────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐
│   MySQL     │ │   ES    │ │  Milvus  │ │ClickHouse│ │  Airflow │
│ (Metadata)  │ │ (Search)│ │(Vectors) │ │(Analytics)│ │ (ETL)    │
└─────────────┘ └─────────┘ └──────────┘ └─────────┘ └──────────┘
         ↑ External services — provided by infrastructure, NOT in this project
```

### Components

- **API Layer**: FastAPI application providing REST endpoints
- **Processing Pipeline**: Configurable workflows for document processing
- **Storage Layer**: Multiple databases for different data types
- **Orchestration**: Airflow DAGs for complex ETL operations
- **Hooks**: Extension points for custom processing logic

## Quick Start

### Prerequisites

- Docker and Docker Compose installed (for containerized deployment)
- Python 3.10+ (for local development)
- **External services** (provided separately, not managed by this project):
  - MySQL 8.x — metadata storage
  - Elasticsearch 8.x — full-text search + optional vector search
  - Milvus 2.x — vector search
  - ClickHouse — vector search (experimental)
  - Apache Airflow 2.x — ETL workflow orchestration

### Using Docker Compose

The `docker-compose.yaml` only contains the Deep Parser API service itself. All storage and orchestration services (MySQL, ES, Milvus, ClickHouse, Airflow) must be provided externally.

1. Clone the repository:
```bash
git clone <repository-url>
cd deep-parser
```

2. Configure environment variables (point to your external services):
```bash
cp .env.example .env
# Edit .env — set DATABASE_URL, ES_HOSTS, MILVUS_HOST, CLICKHOUSE_HOST, AIRFLOW_BASE_URL, etc.
```

3. Start the API service:
```bash
docker-compose up -d
```

4. Access the API:
- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- WebUI: http://localhost:8000/ui/

5. Stop the service:
```bash
docker-compose down
```

## Development Setup

### Local Development

1. Create a virtual environment:
```bash
python3.10 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -e ".[dev,airflow]"
```

3. Set up environment variables:
```bash
cp .env.example .env
# Configure local database and service endpoints in .env
```

4. Run database migrations:
```bash
alembic upgrade head
```

5. Start the development server:
```bash
uvicorn deep_parser.main:app --reload --host 0.0.0.0 --port 8000
```

6. Run tests:
```bash
pytest tests/
```

### Configuration

Configuration files are located in the `config/` directory:

- `config.yaml`: Main application configuration
- `embed.yaml`: Embedding model settings
- `index.yaml`: Indexing pipeline configuration
- `split.yaml`: Document chunking parameters
- `summary.yaml`: Summarization settings
- `qa.yaml`: Question-answering configuration
- `keywords.yaml`: Keyword extraction settings

## API Documentation

The API provides the following main endpoints:

### Document Upload
- `POST /api/upload` - Upload and process documents
- `GET /api/jobs/{job_id}` - Get processing job status
- `GET /api/jobs` - List all processing jobs

### Retrieval
- `POST /api/retrieve` - Semantic search and retrieval
- `POST /api/retrieve/hybrid` - Hybrid vector + keyword search

### Evaluation
- `POST /api/evaluate` - Run RAG evaluation
- `GET /api/evaluate/results/{eval_id}` - Get evaluation results

### Load Testing
- `POST /api/loadtest/start` - Start load test
- `GET /api/loadtest/status/{test_id}` - Get load test status
- `POST /api/loadtest/stop` - Stop load test

### Configuration
- `GET /api/config` - Get current configuration
- `POST /api/config` - Update configuration

### Health
- `GET /health` - Health check endpoint
- `GET /` - API information

For detailed API documentation with request/response examples, visit http://localhost:8000/docs when the service is running.

## Directory Structure

```
deep-parser/
├── config/                 # Configuration files
│   ├── clean.yaml
│   ├── embed.yaml
│   ├── index.yaml
│   ├── keywords.yaml
│   ├── qa.yaml
│   ├── split.yaml
│   └── summary.yaml
├── dags/                   # Airflow DAGs
│   └── doc_etl_v1.py
├── src/
│   └── deep_parser/
│       ├── api/            # API route handlers
│       │   ├── upload.py
│       │   ├── retrieve.py
│       │   ├── evaluate.py
│       │   ├── loadtest.py
│       │   ├── jobs.py
│       │   └── config_api.py
│       ├── hooks/          # Extension hooks
│       │   ├── __init__.py
│       │   └── knowledge_graph.py
│       ├── logging_config.py
│       └── main.py         # FastAPI application
├── tests/                  # Test files
├── alembic/                # Database migrations
├── .env.example            # Environment variables template
├── docker-compose.yaml     # Docker Compose configuration
├── Dockerfile              # Docker image definition
├── pyproject.toml          # Python project configuration
└── README.md               # This file
```

## Extension Points

### Knowledge Graph Hooks

The system provides an extensible hook interface for knowledge graph extraction:

```python
from deep_parser.hooks.knowledge_graph import (
    KnowledgeGraphHook,
    GraphNode,
    GraphEdge,
    GraphResult,
    get_knowledge_graph_hook
)

# Implement custom hook
class CustomKnowledgeGraphHook(KnowledgeGraphHook):
    async def on_chunks_ready(self, doc_id: str, chunks: list[dict]) -> GraphResult:
        # Extract entities and relationships from chunks
        nodes = [GraphNode(...)]
        edges = [GraphEdge(...)]
        return GraphResult(nodes=nodes, edges=edges)
    
    async def save_graph(self, result: GraphResult) -> None:
        # Save to your graph database
        pass
```

## Technology Stack

- **Language**: Python 3.10+
- **Web Framework**: FastAPI
- **Databases**:
  - MySQL 8.0 (metadata)
  - Elasticsearch 8.x (full-text search)
  - Milvus 2.x (vector search)
  - ClickHouse (analytics)
- **Orchestration**: Apache Airflow 2.8.0
- **LLM Integration**: OpenAI API
- **Evaluation**: RAGAS
- **Load Testing**: Locust
- **Containerization**: Docker & Docker Compose

## Contributing

Contributions are welcome! Please ensure:
- Code follows the project's style guidelines
- Tests are added for new features
- Documentation is updated accordingly

## License

MIT License - see LICENSE file for details

## Support

For issues, questions, or contributions, please contact the Deep Parser Team.
