"""Locust load testing script for Deep Parser.

This module provides a Locust-based load test for the retrieval API,
supporting distributed load testing scenarios.
"""

import os
from typing import Any

from locust import HttpUser, between, task

from src.deep_parser.logging_config import logger


class DeepParserUser(HttpUser):
    """User class for Locust load testing.

    Simulates user behavior by sending retrieval requests to the API.
    """

    wait_time = between(1, 3)

    def on_start(self):
        """Initialize user session and load queries."""
        self.queries = self._load_queries()
        logger.info(f"Loaded {len(self.queries)} queries for load testing")

    def _load_queries(self) -> list[str]:
        """Load queries from environment variable or file.

        Returns:
            List of query strings
        """
        queries_str = os.getenv("LOCUST_QUERIES", "")

        if queries_str:
            return [q.strip() for q in queries_str.split(";") if q.strip()]

        queries_file = os.getenv("LOCUST_QUERIES_FILE", "queries.txt")

        if os.path.exists(queries_file):
            try:
                with open(queries_file, "r", encoding="utf-8") as f:
                    return [line.strip() for line in f if line.strip()]
            except Exception as e:
                logger.warning(f"Failed to load queries from file: {e}")

        return [
            "What is machine learning?",
            "How does deep learning work?",
            "Explain neural networks",
            "What is natural language processing?",
            "How do transformers work?"
        ]

    @task(3)
    def retrieve_documents(self):
        """Send retrieval request to the API.

        This is the main task that simulates user queries to the retrieval system.
        """
        if not self.queries:
            return

        import random
        query = random.choice(self.queries)

        request_body: dict[str, Any] = {
            "query": query,
            "top_k": 10,
            "routes": {
                "es_text": True,
                "vector": {
                    "enabled": True,
                    "backend": os.getenv("LOCUST_BACKEND", "milvus")
                }
            },
            "rewrite": {"enabled": False},
            "fusion": {"method": "weighted_sum"},
            "filters": {}
        }

        try:
            self.client.post(
                "/api/retrieve",
                json=request_body,
                name="/api/retrieve"
            )
        except Exception as e:
            logger.warning(f"Request failed: {e}")

    @task(1)
    def health_check(self):
        """Send health check request to the API.

        Lightweight task to verify API availability.
        """
        try:
            self.client.get("/health", name="/health")
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
