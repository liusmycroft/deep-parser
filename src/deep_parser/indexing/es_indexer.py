"""Elasticsearch indexer for text and vector storage.

This module provides functionality to index and search document chunks
using Elasticsearch, supporting both full-text search and vector search.
"""

from typing import Any

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

from deep_parser.logging_config import logger


class ElasticsearchIndexer:
    """Elasticsearch indexer for chunks with text and vector support.

    Provides async methods to create indices, index chunks, delete documents,
    and perform full-text and vector searches.

    Attributes:
        hosts: Elasticsearch hosts connection string
        username: Elasticsearch username for authentication
        password: Elasticsearch password for authentication
        embedding_dim: Dimension of embedding vectors (default 1536)
        client: AsyncElasticsearch client instance
    """

    def __init__(self, hosts: str, username: str = "", password: str = "", embedding_dim: int = 1536):
        """Initialize Elasticsearch indexer.

        Args:
            hosts: Elasticsearch hosts connection string
            username: Elasticsearch username for authentication
            password: Elasticsearch password for authentication
            embedding_dim: Dimension of embedding vectors
        """
        self.hosts = hosts
        self.username = username
        self.password = password
        self.embedding_dim = embedding_dim
        self.client: AsyncElasticsearch | None = None

    async def connect(self) -> None:
        """Create AsyncElasticsearch client."""
        if self.client is None:
            self.client = AsyncElasticsearch(
                hosts=[self.hosts],
                basic_auth=(self.username, self.password) if self.username and self.password else None,
            )
            await self.client.ping()
            logger.info("ES connect success")

    async def close(self) -> None:
        """Close Elasticsearch connection."""
        if self.client is not None:
            await self.client.close()
            self.client = None
            logger.info("ES close success")

    async def create_index(self, index_name: str = "chunks_v1") -> None:
        """Create Elasticsearch index with proper mappings.

        Args:
            index_name: Name of the index to create
        """
        if self.client is None:
            raise RuntimeError("Elasticsearch client not connected")

        if await self.client.indices.exists(index=index_name):
            logger.info(f"ES index {index_name} already exists")
            return

        mapping = {
            "mappings": {
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "doc_id": {"type": "keyword"},
                    "chunk_type": {"type": "keyword"},
                    "level": {"type": "integer"},
                    "order_index": {"type": "integer"},
                    "content": {
                        "type": "text",
                        "analyzer": "ik_max_word",
                        "fields": {
                            "standard": {
                                "type": "text",
                                "analyzer": "standard"
                            }
                        }
                    },
                    "keywords": {"type": "keyword"},
                    "qas": {
                        "type": "nested",
                        "properties": {
                            "q": {"type": "text", "analyzer": "ik_max_word"},
                            "a": {"type": "text", "analyzer": "ik_max_word"}
                        }
                    },
                    "embedding": {
                        "type": "dense_vector",
                        "dims": self.embedding_dim,
                        "index": True,
                        "similarity": "cosine"
                    },
                    "created_at": {"type": "date"}
                }
            }
        }

        await self.client.indices.create(index=index_name, body=mapping)
        logger.info(f"ES create_index success {index_name}")

    async def index_chunks(self, chunks: list[dict], index_name: str = "chunks_v1") -> None:
        """Bulk index chunks using Elasticsearch bulk API with upsert.

        Args:
            chunks: List of chunk dictionaries to index
            index_name: Name of the index to write to
        """
        if self.client is None:
            raise RuntimeError("Elasticsearch client not connected")

        if not chunks:
            return

        def generate_actions():
            for chunk in chunks:
                action = {
                    "_op_type": "index",
                    "_index": index_name,
                    "_id": chunk.get("chunk_id"),
                    "_source": chunk
                }
                yield action

        success, failed = await async_bulk(self.client, generate_actions(), raise_on_error=False)

        if failed:
            logger.error(f"ES index_chunks fail {failed} failed, {success} success")
        else:
            logger.info(f"ES index_chunks success {success} chunks")

    async def delete_by_doc_id(self, doc_id: str, index_name: str = "chunks_v1") -> None:
        """Delete all chunks belonging to a document.

        Args:
            doc_id: Document ID to delete chunks for
            index_name: Name of the index to delete from
        """
        if self.client is None:
            raise RuntimeError("Elasticsearch client not connected")

        query = {
            "query": {
                "term": {
                    "doc_id": doc_id
                }
            }
        }

        response = await self.client.delete_by_query(index=index_name, body=query)
        deleted_count = response.get("deleted", 0)
        logger.info(f"ES delete_by_doc_id success {deleted_count} chunks for doc {doc_id}")

    async def search_text(
        self,
        query: str,
        top_k: int = 20,
        filters: dict | None = None,
        index_name: str = "chunks_v1"
    ) -> list[dict]:
        """Perform full-text search on chunks.

        Args:
            query: Search query string
            top_k: Number of results to return
            filters: Optional filter conditions
            index_name: Name of the index to search

        Returns:
            List of matching chunks with scores
        """
        if self.client is None:
            raise RuntimeError("Elasticsearch client not connected")

        search_body = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["content", "content.standard", "keywords"],
                                "type": "best_fields"
                            }
                        }
                    ]
                }
            },
            "size": top_k
        }

        if filters:
            filter_terms = []
            for field, value in filters.items():
                filter_terms.append({"term": {field: value}})
            search_body["query"]["bool"]["filter"] = filter_terms

        response = await self.client.search(index=index_name, body=search_body)
        hits = response.get("hits", {}).get("hits", [])

        results = []
        for hit in hits:
            source = hit["_source"]
            source["_score"] = hit["_score"]
            results.append(source)

        logger.info(f"ES search_text success found {len(results)} results")
        return results

    async def search_vector(
        self,
        vector: list[float],
        top_k: int = 20,
        filters: dict | None = None,
        index_name: str = "chunks_v1"
    ) -> list[dict]:
        """Perform vector similarity search on chunks.

        Args:
            vector: Query vector for similarity search
            top_k: Number of results to return
            filters: Optional filter conditions
            index_name: Name of the index to search

        Returns:
            List of matching chunks with similarity scores
        """
        if self.client is None:
            raise RuntimeError("Elasticsearch client not connected")

        search_body = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "knn": {
                                "field": "embedding",
                                "query_vector": vector,
                                "k": top_k,
                                "num_candidates": top_k * 10
                            }
                        }
                    ]
                }
            },
            "size": top_k
        }

        if filters:
            filter_terms = []
            for field, value in filters.items():
                filter_terms.append({"term": {field: value}})
            search_body["query"]["bool"]["filter"] = filter_terms

        response = await self.client.search(index=index_name, body=search_body)
        hits = response.get("hits", {}).get("hits", [])

        results = []
        for hit in hits:
            source = hit["_source"]
            source["_score"] = hit["_score"]
            results.append(source)

        logger.info(f"ES search_vector success found {len(results)} results")
        return results


def get_es_indexer() -> ElasticsearchIndexer:
    """Factory function to create ElasticsearchIndexer instance.

    Returns:
        Configured ElasticsearchIndexer instance
    """
    from deep_parser.config.settings import get_settings

    settings = get_settings()
    return ElasticsearchIndexer(
        hosts=settings.es_hosts,
        username=settings.es_username,
        password=settings.es_password,
        embedding_dim=settings.embedding_dim
    )
