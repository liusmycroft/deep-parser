"""Index manager for coordinating multiple storage backends.

This module provides a unified interface to manage indexing operations across
Elasticsearch, Milvus, and ClickHouse storage backends based on configuration.
"""

from deep_parser.config.settings import IndexConfig, Settings
from deep_parser.indexing.clickhouse_indexer import ClickHouseIndexer
from deep_parser.indexing.es_indexer import ElasticsearchIndexer
from deep_parser.indexing.milvus_indexer import MilvusIndexer
from deep_parser.logging_config import logger


class IndexManager:
    """Unified manager for coordinating indexing across multiple storage backends.

    Manages Elasticsearch, Milvus, and ClickHouse indexers based on configuration
    switches. Provides methods to index chunks, delete documents, and ensure
    indexes are properly initialized.

    Attributes:
        config: IndexConfig containing enable/disable flags for each backend
        settings: Settings containing connection parameters
        es_indexer: Elasticsearch indexer instance (optional)
        milvus_indexer: Milvus indexer instance (optional)
        clickhouse_indexer: ClickHouse indexer instance (optional)
    """

    def __init__(self, config: IndexConfig, settings: Settings):
        """Initialize IndexManager with configuration and settings.

        Args:
            config: IndexConfig containing enable/disable flags for each backend
            settings: Settings containing connection parameters
        """
        self.config = config
        self.settings = settings
        self.es_indexer: ElasticsearchIndexer | None = None
        self.milvus_indexer: MilvusIndexer | None = None
        self.clickhouse_indexer: ClickHouseIndexer | None = None

        # Initialize enabled indexers
        if config.enable_es_text or config.enable_es_vector:
            self.es_indexer = ElasticsearchIndexer(
                hosts=settings.es_hosts,
                username=settings.es_username,
                password=settings.es_password,
                embedding_dim=settings.embedding_dim
            )

        if config.enable_milvus:
            self.milvus_indexer = MilvusIndexer(
                host=settings.milvus_host,
                port=settings.milvus_port,
                embedding_dim=settings.embedding_dim
            )

        if config.enable_clickhouse:
            self.clickhouse_indexer = ClickHouseIndexer(
                host=settings.clickhouse_host,
                port=settings.clickhouse_port,
                user=settings.clickhouse_user,
                password=settings.clickhouse_password
            )

    async def index_chunks(self, chunks: list[dict], doc_id: str) -> None:
        """Index chunks to all enabled storage backends.

        Args:
            chunks: List of chunk dictionaries to index
            doc_id: Document ID for the chunks
        """
        if not chunks:
            logger.info("IndexManager index_chunks success no chunks to index")
            return

        # Index to Elasticsearch (text only)
        if self.config.enable_es_text and self.es_indexer:
            text_chunks = [
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "doc_id": chunk.get("doc_id"),
                    "chunk_type": chunk.get("chunk_type"),
                    "level": chunk.get("level"),
                    "order_index": chunk.get("order_index"),
                    "content": chunk.get("content"),
                    "keywords": chunk.get("keywords", []),
                    "qas": chunk.get("qas", []),
                    "created_at": chunk.get("created_at")
                }
                for chunk in chunks
            ]
            await self.es_indexer.index_chunks(text_chunks)
            logger.info(f"IndexManager index_chunks success {len(text_chunks)} chunks to ES text")

        # Index to Elasticsearch (with vectors)
        if self.config.enable_es_vector and self.es_indexer:
            vector_chunks = [
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "doc_id": chunk.get("doc_id"),
                    "chunk_type": chunk.get("chunk_type"),
                    "level": chunk.get("level"),
                    "order_index": chunk.get("order_index"),
                    "content": chunk.get("content"),
                    "keywords": chunk.get("keywords", []),
                    "qas": chunk.get("qas", []),
                    "embedding": chunk.get("embedding"),
                    "created_at": chunk.get("created_at")
                }
                for chunk in chunks
                if chunk.get("embedding")
            ]
            if vector_chunks:
                await self.es_indexer.index_chunks(vector_chunks)
                logger.info(f"IndexManager index_chunks success {len(vector_chunks)} chunks to ES vector")

        # Index to Milvus
        if self.config.enable_milvus and self.milvus_indexer:
            vector_chunks = [
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "doc_id": chunk.get("doc_id"),
                    "chunk_type": chunk.get("chunk_type"),
                    "level": chunk.get("level"),
                    "order_index": chunk.get("order_index"),
                    "embedding": chunk.get("embedding")
                }
                for chunk in chunks
                if chunk.get("embedding")
            ]
            if vector_chunks:
                self.milvus_indexer.insert_vectors(vector_chunks)
                logger.info(f"IndexManager index_chunks success {len(vector_chunks)} chunks to Milvus")

        # Index to ClickHouse
        if self.config.enable_clickhouse and self.clickhouse_indexer:
            clickhouse_chunks = [
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "doc_id": chunk.get("doc_id"),
                    "content": chunk.get("content"),
                    "chunk_type": chunk.get("chunk_type"),
                    "level": chunk.get("level"),
                    "order_index": chunk.get("order_index"),
                    "embedding": chunk.get("embedding", [])
                }
                for chunk in chunks
            ]
            self.clickhouse_indexer.insert_chunks(clickhouse_chunks)
            logger.info(f"IndexManager index_chunks success {len(clickhouse_chunks)} chunks to ClickHouse")

        logger.info(f"IndexManager index_chunks success doc {doc_id} with {len(chunks)} chunks")

    async def delete_doc_chunks(self, doc_id: str) -> None:
        """Delete all chunks for a document from all enabled backends.

        Args:
            doc_id: Document ID to delete chunks for
        """
        # Delete from Elasticsearch
        if self.es_indexer and (self.config.enable_es_text or self.config.enable_es_vector):
            await self.es_indexer.delete_by_doc_id(doc_id)
            logger.info(f"IndexManager delete_doc_chunks success doc {doc_id} from ES")

        # Delete from Milvus
        if self.milvus_indexer and self.config.enable_milvus:
            self.milvus_indexer.delete_by_doc_id(doc_id)
            logger.info(f"IndexManager delete_doc_chunks success doc {doc_id} from Milvus")

        # Delete from ClickHouse
        if self.clickhouse_indexer and self.config.enable_clickhouse:
            self.clickhouse_indexer.delete_by_doc_id(doc_id)
            logger.info(f"IndexManager delete_doc_chunks success doc {doc_id} from ClickHouse")

        logger.info(f"IndexManager delete_doc_chunks success doc {doc_id} from all backends")

    async def ensure_indexes(self) -> None:
        """Ensure all enabled backends have their indexes/collections/tables created."""
        # Ensure Elasticsearch index
        if self.es_indexer and (self.config.enable_es_text or self.config.enable_es_vector):
            await self.es_indexer.connect()
            await self.es_indexer.create_index()
            logger.info("IndexManager ensure_indexes success ES index ready")

        # Ensure Milvus collection
        if self.milvus_indexer and self.config.enable_milvus:
            self.milvus_indexer.connect()
            self.milvus_indexer.create_collection()
            logger.info("IndexManager ensure_indexes success Milvus collection ready")

        # Ensure ClickHouse table
        if self.clickhouse_indexer and self.config.enable_clickhouse:
            self.clickhouse_indexer.connect()
            self.clickhouse_indexer.create_table()
            logger.info("IndexManager ensure_indexes success ClickHouse table ready")

        logger.info("IndexManager ensure_indexes success all backends ready")

    async def close(self) -> None:
        """Close all connections to storage backends."""
        if self.es_indexer:
            await self.es_indexer.close()
            logger.info("IndexManager close success ES connection")

        if self.milvus_indexer:
            self.milvus_indexer.close()
            logger.info("IndexManager close success Milvus connection")

        if self.clickhouse_indexer:
            self.clickhouse_indexer.close()
            logger.info("IndexManager close success ClickHouse connection")

        logger.info("IndexManager close success all connections")
