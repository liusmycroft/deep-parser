"""Milvus indexer for vector storage and similarity search.

This module provides functionality to store and search document chunk vectors
using Milvus vector database with IVF_FLAT indexing.
"""

from typing import Any

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, MilvusClient, connections

from deep_parser.logging_config import logger


class MilvusIndexer:
    """Milvus indexer for chunk embeddings with vector similarity search.

    Provides synchronous methods to create collections, insert vectors,
    delete documents, and perform vector similarity searches.

    Attributes:
        host: Milvus server host
        port: Milvus server port
        embedding_dim: Dimension of embedding vectors (default 1536)
        client: MilvusClient instance for connection management
    """

    def __init__(self, host: str, port: int, embedding_dim: int = 1536):
        """Initialize Milvus indexer.

        Args:
            host: Milvus server host
            port: Milvus server port
            embedding_dim: Dimension of embedding vectors
        """
        self.host = host
        self.port = port
        self.embedding_dim = embedding_dim
        self.client: MilvusClient | None = None

    def connect(self) -> None:
        """Connect to Milvus server."""
        if self.client is None:
            self.client = MilvusClient(
                uri=f"http://{self.host}:{self.port}"
            )
            logger.info(f"Milvus connect success {self.host}:{self.port}")

    def close(self) -> None:
        """Close Milvus connection."""
        if self.client is not None:
            self.client.close()
            self.client = None
            logger.info("Milvus close success")

    def create_collection(self, collection_name: str = "chunks_embedding_v1") -> None:
        """Create Milvus collection with proper schema and IVF_FLAT index.

        Args:
            collection_name: Name of the collection to create
        """
        if self.client is None:
            raise RuntimeError("Milvus client not connected")

        if self.client.has_collection(collection_name):
            logger.info(f"Milvus collection {collection_name} already exists")
            return

        schema = CollectionSchema(
            fields=[
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=256, is_primary=True),
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="chunk_type", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="level", dtype=DataType.INT64),
                FieldSchema(name="order_index", dtype=DataType.INT64),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
            ],
            description="Chunk embeddings for similarity search"
        )

        self.client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params={
                "index_type": "IVF_FLAT",
                "metric_type": "COSINE",
                "params": {"nlist": 128}
            }
        )
        logger.info(f"Milvus create_collection success {collection_name}")

    def insert_vectors(self, chunks: list[dict], collection_name: str = "chunks_embedding_v1") -> None:
        """Batch insert chunk vectors with idempotent upsert behavior.

        Args:
            chunks: List of chunk dictionaries with chunk_id, doc_id, chunk_type,
                   level, order_index, and embedding fields
            collection_name: Name of the collection to insert into
        """
        if self.client is None:
            raise RuntimeError("Milvus client not connected")

        if not chunks:
            return

        # Delete existing records by chunk_id for idempotency
        chunk_ids = [chunk.get("chunk_id") for chunk in chunks if chunk.get("chunk_id")]
        if chunk_ids:
            self.client.delete(
                collection_name=collection_name,
                ids=chunk_ids
            )

        # Prepare data for insertion
        data = []
        for chunk in chunks:
            data.append({
                "chunk_id": chunk.get("chunk_id"),
                "doc_id": chunk.get("doc_id"),
                "chunk_type": chunk.get("chunk_type"),
                "level": chunk.get("level", 0),
                "order_index": chunk.get("order_index", 0),
                "embedding": chunk.get("embedding", [])
            })

        self.client.insert(collection_name=collection_name, data=data)
        logger.info(f"Milvus insert_vectors success {len(chunks)} chunks")

    def delete_by_doc_id(self, doc_id: str, collection_name: str = "chunks_embedding_v1") -> None:
        """Delete all vectors belonging to a document.

        Args:
            doc_id: Document ID to delete vectors for
            collection_name: Name of the collection to delete from
        """
        if self.client is None:
            raise RuntimeError("Milvus client not connected")

        # Query to get all chunk_ids for the document
        collection = Collection(name=collection_name)
        collection.load()

        results = collection.query(
            expr=f'doc_id == "{doc_id}"',
            output_fields=["chunk_id"]
        )

        chunk_ids = [result.get("chunk_id") for result in results if result.get("chunk_id")]

        if chunk_ids:
            self.client.delete(collection_name=collection_name, ids=chunk_ids)
            logger.info(f"Milvus delete_by_doc_id success {len(chunk_ids)} chunks for doc {doc_id}")
        else:
            logger.info(f"Milvus delete_by_doc_id no chunks found for doc {doc_id}")

    def search_vectors(
        self,
        vector: list[float],
        top_k: int = 20,
        filters: str | None = None,
        collection_name: str = "chunks_embedding_v1"
    ) -> list[dict]:
        """Perform vector similarity search on chunks.

        Args:
            vector: Query vector for similarity search
            top_k: Number of results to return
            filters: Optional filter expression (e.g., 'chunk_type == "original"')
            collection_name: Name of the collection to search

        Returns:
            List of matching chunks with similarity scores
        """
        if self.client is None:
            raise RuntimeError("Milvus client not connected")

        results = self.client.search(
            collection_name=collection_name,
            data=[vector],
            limit=top_k,
            output_fields=["chunk_id", "doc_id", "chunk_type", "level", "order_index"],
            filter_expr=filters,
            consistency_level="Strong"
        )

        formatted_results = []
        if results and len(results) > 0 and len(results[0]) > 0:
            for result in results[0]:
                formatted_results.append({
                    "chunk_id": result.get("entity", {}).get("chunk_id"),
                    "doc_id": result.get("entity", {}).get("doc_id"),
                    "chunk_type": result.get("entity", {}).get("chunk_type"),
                    "level": result.get("entity", {}).get("level"),
                    "order_index": result.get("entity", {}).get("order_index"),
                    "_score": result.get("distance", 0)
                })

        logger.info(f"Milvus search_vectors success found {len(formatted_results)} results")
        return formatted_results


def get_milvus_indexer() -> MilvusIndexer:
    """Factory function to create MilvusIndexer instance.

    Returns:
        Configured MilvusIndexer instance
    """
    from deep_parser.config.settings import get_settings

    settings = get_settings()
    return MilvusIndexer(
        host=settings.milvus_host,
        port=settings.milvus_port,
        embedding_dim=settings.embedding_dim
    )
