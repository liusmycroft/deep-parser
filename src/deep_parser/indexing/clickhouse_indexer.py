"""ClickHouse indexer for chunk storage and vector similarity search.

This module provides functionality to store document chunks and perform
vector similarity searches using ClickHouse database.
"""

from typing import Any

import clickhouse_connect

from deep_parser.logging_config import logger


class ClickHouseIndexer:
    """ClickHouse indexer for chunk embeddings with vector similarity search.

    Provides synchronous methods to create tables, insert chunks,
    delete documents, and perform vector similarity searches using cosine distance.

    Attributes:
        host: ClickHouse server host
        port: ClickHouse server port
        user: ClickHouse username
        password: ClickHouse password
        client: ClickHouse client instance
    """

    def __init__(self, host: str, port: int, user: str = "default", password: str = ""):
        """Initialize ClickHouse indexer.

        Args:
            host: ClickHouse server host
            port: ClickHouse server port
            user: ClickHouse username
            password: ClickHouse password
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.client: clickhouse_connect.driver.client.Client | None = None

    def connect(self) -> None:
        """Connect to ClickHouse server."""
        if self.client is None:
            self.client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.user,
                password=self.password
            )
            logger.info(f"ClickHouse connect success {self.host}:{self.port}")

    def close(self) -> None:
        """Close ClickHouse connection."""
        if self.client is not None:
            self.client.close()
            self.client = None
            logger.info("ClickHouse close success")

    def create_table(self, table_name: str = "chunks_embedding_v1") -> None:
        """Create ClickHouse table with proper schema and MergeTree engine.

        Args:
            table_name: Name of the table to create
        """
        if self.client is None:
            raise RuntimeError("ClickHouse client not connected")

        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            chunk_id UUID,
            doc_id UUID,
            content String,
            chunk_type String,
            level Int32,
            order_index Int32,
            embedding Array(Float32),
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY (doc_id, chunk_id)
        """

        self.client.command(create_table_sql)
        logger.info(f"ClickHouse create_table success {table_name}")

    def insert_chunks(self, chunks: list[dict], table_name: str = "chunks_embedding_v1") -> None:
        """Batch insert chunks with idempotent upsert behavior.

        Args:
            chunks: List of chunk dictionaries with chunk_id, doc_id, content,
                   chunk_type, level, order_index, and embedding fields
            table_name: Name of the table to insert into
        """
        if self.client is None:
            raise RuntimeError("ClickHouse client not connected")

        if not chunks:
            return

        # Delete existing records by chunk_id for idempotency
        chunk_ids = [chunk.get("chunk_id") for chunk in chunks if chunk.get("chunk_id")]
        if chunk_ids:
            chunk_ids_str = ", ".join([f"'{cid}'" for cid in chunk_ids])
            delete_sql = f"ALTER TABLE {table_name} DELETE WHERE chunk_id IN ({chunk_ids_str})"
            self.client.command(delete_sql)

        # Prepare data for insertion
        data = []
        for chunk in chunks:
            data.append({
                "chunk_id": chunk.get("chunk_id"),
                "doc_id": chunk.get("doc_id"),
                "content": chunk.get("content", ""),
                "chunk_type": chunk.get("chunk_type", ""),
                "level": chunk.get("level", 0),
                "order_index": chunk.get("order_index", 0),
                "embedding": chunk.get("embedding", [])
            })

        self.client.insert(table_name, data)
        logger.info(f"ClickHouse insert_chunks success {len(chunks)} chunks")

    def delete_by_doc_id(self, doc_id: str, table_name: str = "chunks_embedding_v1") -> None:
        """Delete all chunks belonging to a document.

        Args:
            doc_id: Document ID to delete chunks for
            table_name: Name of the table to delete from
        """
        if self.client is None:
            raise RuntimeError("ClickHouse client not connected")

        delete_sql = f"ALTER TABLE {table_name} DELETE WHERE doc_id = '{doc_id}'"
        self.client.command(delete_sql)
        logger.info(f"ClickHouse delete_by_doc_id success for doc {doc_id}")

    def search_vectors(
        self,
        vector: list[float],
        top_k: int = 20,
        filters: dict | None = None,
        table_name: str = "chunks_embedding_v1"
    ) -> list[dict]:
        """Perform vector similarity search using cosine distance.

        Args:
            vector: Query vector for similarity search
            top_k: Number of results to return
            filters: Optional filter conditions (e.g., {"chunk_type": "original"})
            table_name: Name of the table to search

        Returns:
            List of matching chunks with similarity scores
        """
        if self.client is None:
            raise RuntimeError("ClickHouse client not connected")

        # Convert vector to string for SQL
        vector_str = ", ".join([str(v) for v in vector])

        # Build WHERE clause for filters
        where_conditions = []
        if filters:
            for field, value in filters.items():
                where_conditions.append(f"{field} = '{value}'")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        search_sql = f"""
        SELECT
            chunk_id,
            doc_id,
            content,
            chunk_type,
            level,
            order_index,
            1 - cosineDistance(embedding, [{vector_str}]) as _score
        FROM {table_name}
        WHERE {where_clause}
        ORDER BY _score DESC
        LIMIT {top_k}
        """

        result = self.client.query(search_sql)

        results = []
        for row in result.named_results():
            results.append({
                "chunk_id": row.get("chunk_id"),
                "doc_id": row.get("doc_id"),
                "content": row.get("content"),
                "chunk_type": row.get("chunk_type"),
                "level": row.get("level"),
                "order_index": row.get("order_index"),
                "_score": row.get("_score", 0)
            })

        logger.info(f"ClickHouse search_vectors success found {len(results)} results")
        return results


def get_clickhouse_indexer() -> ClickHouseIndexer:
    """Factory function to create ClickHouseIndexer instance.

    Returns:
        Configured ClickHouseIndexer instance
    """
    from deep_parser.config.settings import get_settings

    settings = get_settings()
    return ClickHouseIndexer(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        user=settings.clickhouse_user,
        password=settings.clickhouse_password
    )
