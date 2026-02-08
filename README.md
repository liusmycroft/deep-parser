# RAG Testing System

A comprehensive Python-based platform for testing and evaluating Retrieval-Augmented Generation (RAG) pipelines.

## Features

- **Document Processing**: Clean and process markdown documents with image-to-text conversion
- **Multi-Database Storage**: Store data in Elasticsearch, ClickHouse, Milvus, and HBase
- **Multi-Path Retrieval**: Query across multiple databases with different strategies
- **Evaluation**: Assess cleaning accuracy and retrieval performance
- **Performance Testing**: Conduct load tests and measure query performance
- **Workflow Orchestration**: Automate ETL pipelines using Apache Airflow
- **Web Interface**: FastAPI-based REST API for easy interaction

## Installation

### Requirements

- Python 3.9 or higher
- pip or poetry for package management

### Install from source

```bash
# Clone the repository
git clone https://github.com/rag-testing-system/rag-testing-system.git
cd rag-testing-system

# Install dependencies
pip install -e .

# For development
pip install -e ".[dev]"
```

## Configuration

The system supports configuration from multiple sources with the following precedence (highest to lowest):

1. Command-line arguments
2. Environment variables
3. Configuration file
4. Default values

### Configuration File

Create a `config.yaml` file:

```yaml
database:
  elasticsearch:
    hosts:
      - http://localhost:9200
    index_name: rag_chunks
  milvus:
    host: localhost
    port: 19530
    collection_name: rag_chunks
  clickhouse:
    host: localhost
    port: 9000
    database: rag_system
  hbase:
    host: localhost
    port: 9090

embedding:
  model_name: sentence-transformers/all-MiniLM-L6-v2
  batch_size: 32

processing:
  chunk_size: 512
  chunk_overlap: 50

logging:
  level: INFO
  format: json
  enable_console: true
```

### Environment Variables

Set environment variables with the `RAG_` prefix:

```bash
export RAG_DATABASE__ELASTICSEARCH__HOSTS='["http://localhost:9200"]'
export RAG_EMBEDDING__MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
export RAG_LOGGING__LEVEL=DEBUG
```

### Command-Line Arguments

```bash
python -m rag_testing_system.web.app \
  --config config.yaml \
  --log-level INFO \
  --elasticsearch-hosts http://localhost:9200 \
  --chunk-size 512
```

## Usage

### Starting the Web API

```bash
python -m rag_testing_system.web.app --config config.yaml
```

The API will be available at `http://localhost:8000`. Visit `http://localhost:8000/docs` for interactive API documentation.

### Using the Python API

```python
from rag_testing_system.config import load_config
from rag_testing_system.document_processing import DocumentProcessor
from rag_testing_system.storage import StorageManager
from rag_testing_system.retrieval import RetrievalEngine

# Load configuration
config = load_config(config_file="config.yaml")

# Process documents
processor = DocumentProcessor(config.processing)
documents = await processor.process_folder("/path/to/documents")

# Store in databases
storage = StorageManager(config)
await storage.store_documents(documents, targets=["elasticsearch", "milvus"])

# Query documents
retrieval = RetrievalEngine(config)
results = await retrieval.query_elasticsearch("your query here", top_k=10)
```

## Testing

The project uses both unit tests and property-based tests for comprehensive coverage.

### Run all tests

```bash
pytest
```

### Run with coverage

```bash
pytest --cov=rag_testing_system --cov-report=html
```

### Run only property-based tests

```bash
pytest -m property
```

### Run only unit tests

```bash
pytest -m unit
```

## Project Structure

```
rag-testing-system/
├── src/
│   └── rag_testing_system/
│       ├── config/              # Configuration management
│       ├── document_processing/ # Document cleaning and processing
│       ├── storage/             # Multi-database storage
│       ├── retrieval/           # Multi-path retrieval
│       ├── evaluation/          # Evaluation and metrics
│       ├── performance/         # Performance testing
│       ├── workflow/            # Airflow orchestration
│       ├── web/                 # FastAPI web interface
│       └── utils/               # Utility functions
├── tests/                       # Test suite
├── config.yaml                  # Example configuration
├── pyproject.toml              # Project metadata and dependencies
└── README.md                   # This file
```

## Development

### Code Style

The project uses:
- `black` for code formatting
- `isort` for import sorting
- `mypy` for type checking
- `flake8` for linting

Run all checks:

```bash
black src/ tests/
isort src/ tests/
mypy src/
flake8 src/ tests/
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Documentation

For detailed documentation, visit [https://rag-testing-system.readthedocs.io](https://rag-testing-system.readthedocs.io)

## Support

For issues and questions, please use the [GitHub issue tracker](https://github.com/rag-testing-system/rag-testing-system/issues).
