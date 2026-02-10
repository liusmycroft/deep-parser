"""Query rewriting module for improving retrieval effectiveness.

This module provides query rewriting capabilities including:
- Keyword extraction from queries
- LLM-based query rewriting for better retrieval
"""

import json
from typing import Any

from src.deep_parser.logging_config import logger
from src.deep_parser.services.llm_service import LLMService


class QueryRewriter:
    """Query rewriting service for improving retrieval queries.

    This class provides methods to rewrite user queries to improve
    retrieval effectiveness through keyword extraction and LLM-based
    query transformation.

    Attributes:
        llm_service: LLM service for query rewriting operations
    """

    def __init__(self, llm_service: LLMService):
        """Initialize query rewriter with LLM service.

        Args:
            llm_service: LLM service instance for query rewriting
        """
        self.llm_service = llm_service

    async def rewrite_keywords(self, query: str) -> dict[str, Any]:
        """Extract keywords from the query.

        This method extracts relevant keywords from the query text
        to enhance retrieval effectiveness.

        Args:
            query: Original query string

        Returns:
            Dictionary containing:
                - query: Original query string
                - keywords: List of extracted keywords
        """
        logger.info(f"Extracting keywords from query: {query}")

        try:
            prompt = (
                f"Extract the most important keywords from the following query.\n"
                f"Return a JSON array of strings.\n"
                f"Query: {query}\n"
                f'Format: ["keyword1", "keyword2", "keyword3"]'
            )

            response = await self.llm_service.generate_text(prompt)
            keywords = json.loads(response.strip())

            if not isinstance(keywords, list):
                keywords = [str(keywords)]

            logger.info(f"Extracted keywords: {keywords}")
            return {
                "query": query,
                "keywords": keywords
            }

        except Exception as e:
            logger.warning(f"Failed to extract keywords, using query as keyword: {e}")
            return {
                "query": query,
                "keywords": [query]
            }

    async def rewrite_llm(self, query: str) -> dict[str, Any]:
        """Rewrite query using LLM for better retrieval.

        This method uses LLM to generate a more effective retrieval query
        and extract relevant keywords.

        Args:
            query: Original query string

        Returns:
            Dictionary containing:
                - query: Rewritten query string
                - keywords: List of extracted keywords
        """
        logger.info(f"Rewriting query with LLM: {query}")

        try:
            prompt = (
                f"Rewrite the following query to make it more suitable for document retrieval.\n"
                f"Also extract key search terms.\n"
                f"Return a JSON object with 'query' and 'keywords' fields.\n"
                f"Original query: {query}\n"
                f'Format: {{"query": "rewritten query", "keywords": ["keyword1", "keyword2"]}}'
            )

            response = await self.llm_service.generate_text(prompt)
            result = json.loads(response.strip())

            rewritten_query = result.get("query", query)
            keywords = result.get("keywords", [query])

            if not isinstance(keywords, list):
                keywords = [str(keywords)]

            logger.info(f"Rewritten query: {rewritten_query}, keywords: {keywords}")
            return {
                "query": rewritten_query,
                "keywords": keywords
            }

        except Exception as e:
            logger.warning(f"Failed to rewrite query with LLM, using original: {e}")
            return {
                "query": query,
                "keywords": [query]
            }

    async def rewrite(
        self,
        query: str,
        method: str = "keywords",
        params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Rewrite query using specified method.

        This is the main entry point for query rewriting, dispatching
        to the appropriate rewriting method based on the method parameter.

        Args:
            query: Original query string
            method: Rewriting method ("keywords" or "llm")
            params: Optional parameters for rewriting (currently unused)

        Returns:
            Dictionary containing rewritten query and keywords
        """
        if method == "keywords":
            return await self.rewrite_keywords(query)
        elif method == "llm":
            return await self.rewrite_llm(query)
        else:
            logger.warning(f"Unknown rewrite method: {method}, falling back to keywords")
            return await self.rewrite_keywords(query)
