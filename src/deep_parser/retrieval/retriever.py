"""Retrieval service for multi-route document search.

This module provides the main retrieval service that orchestrates
multi-route search including text search, vector search, query rewriting,
and result fusion.
"""

import asyncio
from typing import Any

from src.deep_parser.config.settings import Settings
from src.deep_parser.indexing.clickhouse_indexer import ClickHouseIndexer
from src.deep_parser.indexing.es_indexer import ElasticsearchIndexer
from src.deep_parser.indexing.milvus_indexer import MilvusIndexer
from src.deep_parser.logging_config import logger
from src.deep_parser.retrieval.fusion import FusionRanker
from src.deep_parser.retrieval.query_rewriter import QueryRewriter
from src.deep_parser.services.llm_service import LLMService


class RetrieverService:
    """Main retrieval service for multi-route document search.

    This service orchestrates the complete retrieval pipeline:
    1. Optional query rewriting
    2. Parallel execution of enabled retrieval routes
    3. Fusion of results from multiple routes
    4. Return ranked results with score breakdown

    Attributes:
        settings: Application settings
        llm_service: LLM service for query rewriting
        query_rewriter: Query rewriter instance
        fusion_ranker: Fusion ranker instance
        es_indexer: Elasticsearch indexer
        milvus_indexer: Milvus indexer
        clickhouse_indexer: ClickHouse indexer
    """

    def __init__(self, settings: Settings, llm_service: LLMService):
        """Initialize retrieval service with dependencies.

        Args:
            settings: Application settings
            llm_service: LLM service for query rewriting
        """
        self.settings = settings
        self.llm_service = llm_service
        self.query_rewriter = QueryRewriter(llm_service)
        self.fusion_ranker = FusionRanker()
        self.es_indexer = ElasticsearchIndexer(settings)
        self.milvus_indexer = MilvusIndexer(settings)
        self.clickhouse_indexer = ClickHouseIndexer(settings)

    async def retrieve(self, request: dict[str, Any]) -> dict[str, Any]:
        """Execute retrieval request with multi-route search and fusion.

        This method processes a retrieval request by:
        1. Parsing request parameters
        2. Optionally rewriting the query
        3. Executing enabled retrieval routes in parallel
        4. Fusing results from multiple routes
        5. Returning ranked results with score breakdown

        Args:
            request: Retrieval request containing:
                - query: Search query string
                - top_k: Number of results to return
                - routes: Dict of enabled routes (es_text, vector)
                - rewrite: Dict with rewrite config (enabled, method, params)
                - fusion: Dict with fusion config (method, weights)
                - filters: Dict of filters (doc_ids, source_type)

        Returns:
            Dictionary containing:
                - query_used: The query actually used for retrieval
                - results: List of ranked results with metadata
        """
        # Parse request parameters
        query = request.get("query", "")
        top_k = request.get("top_k", 20)
        routes = request.get("routes", {})
        rewrite_config = request.get("rewrite", {})
        fusion_config = request.get("fusion", {})
        filters = request.get("filters", {})

        logger.info(f"Retrieval request: query='{query}', top_k={top_k}, routes={routes}")

        # Query rewriting
        query_used = query
        keywords = []

        if rewrite_config.get("enabled", False):
            rewrite_method = rewrite_config.get("method", "keywords")
            rewrite_params = rewrite_config.get("params", {})

            logger.info(f"Rewriting query using method: {rewrite_method}")
            rewrite_result = await self.query_rewriter.rewrite(
                query,
                method=rewrite_method,
                params=rewrite_params
            )
            query_used = rewrite_result.get("query", query)
            keywords = rewrite_result.get("keywords", [])
            logger.info(f"Rewritten query: '{query_used}', keywords: {keywords}")

        # Execute retrieval routes in parallel
        results_by_route = {}
        tasks = []

        # ES text search
        if routes.get("es_text", False):
            tasks.append(("es_text", self._search_es_text(query_used, top_k, filters)))

        # Vector search
        vector_config = routes.get("vector", {})
        if vector_config.get("enabled", False):
            backend = vector_config.get("backend", "milvus")
            tasks.append((f"vector_{backend}", self._search_vector(
                query_used, top_k, filters, backend
            )))

        # Execute parallel searches
        if tasks:
            logger.info(f"Executing {len(tasks)} retrieval routes in parallel")
            completed_tasks = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)

            for (route_name, _), result in zip(tasks, completed_tasks):
                if isinstance(result, Exception):
                    logger.error(f"Route {route_name} failed: {result}")
                else:
                    results_by_route[route_name] = result
                    logger.info(f"Route {route_name} returned {len(result)} results")

        # Fusion of results
        if len(results_by_route) > 1:
            fusion_method = fusion_config.get("method", "weighted_sum")
            fusion_weights = fusion_config.get("weights", {})

            logger.info(f"Fusing results using method: {fusion_method}")
            fused_results = self.fusion_ranker.fuse(
                results_by_route,
                method=fusion_method,
                weights=fusion_weights
            )
        elif len(results_by_route) == 1:
            # Single route, just use results directly
            fused_results = list(results_by_route.values())[0]
        else:
            # No results
            fused_results = []

        # Limit to top_k
        fused_results = fused_results[:top_k]

        # Format results with metadata
        formatted_results = []
        for result in fused_results:
            formatted_result = {
                "chunk_id": result.get("chunk_id"),
                "doc_id": result.get("doc_id"),
                "score": result.get("score", 0.0),
                "route_scores": result.get("route_scores", {}),
                "content": result.get("content", ""),
                "keywords": result.get("keywords", []),
                "metadata": {
                    "level": result.get("level", 0),
                    "order_index": result.get("order_index", 0),
                    "chunk_type": result.get("chunk_type", "original"),
                }
            }
            formatted_results.append(formatted_result)

        logger.info(f"Returning {len(formatted_results)} results")
        return {
            "query_used": query_used,
            "results": formatted_results
        }

    async def _search_es_text(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any]
    ) -> list[dict]:
        """Execute Elasticsearch text search.

        Args:
            query: Search query
            top_k: Number of results
            filters: Filter criteria

        Returns:
            List of search results
        """
        try:
            results = await self.es_indexer.search_text(
                query=query,
                top_k=top_k,
                filters=filters
            )
            return results
        except Exception as e:
            logger.error(f"ES text search failed: {e}")
            return []

    async def _search_vector(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any],
        backend: str
    ) -> list[dict]:
        """Execute vector search on specified backend.

        Args:
            query: Search query
            top_k: Number of results
            filters: Filter criteria
            backend: Vector backend (milvus, es, clickhouse)

        Returns:
            List of search results
        """
        try:
            if backend == "milvus":
                results = await self.milvus_indexer.search_vectors(
                    query=query,
                    top_k=top_k,
                    filters=filters
                )
            elif backend == "es":
                results = await self.es_indexer.search_vector(
                    query=query,
                    top_k=top_k,
                    filters=filters
                )
            elif backend == "clickhouse":
                results = await self.clickhouse_indexer.search_vectors(
                    query=query,
                    top_k=top_k,
                    filters=filters
                )
            else:
                logger.warning(f"Unknown vector backend: {backend}")
                return []

            return results
        except Exception as e:
            logger.error(f"Vector search on {backend} failed: {e}")
            return []
