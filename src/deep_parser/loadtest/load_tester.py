"""Load testing module for performance assessment.

This module provides load testing capabilities for the retrieval API,
including concurrent request execution and performance metrics calculation.
"""

import asyncio
import time
from typing import Any

import httpx

from src.deep_parser.logging_config import logger


class LoadTester:
    """Load tester for performance assessment.

    This class executes concurrent requests to the retrieval API
    and calculates performance metrics like QPS, percentiles, and error rate.

    Attributes:
        base_url: Base URL of the API to test
    """

    def __init__(self, base_url: str):
        """Initialize the load tester with a base URL.

        Args:
            base_url: Base URL of the API to test
        """
        self.base_url = base_url.rstrip("/")

    async def run_builtin_test(
        self,
        queries: list[str],
        concurrency: int = 10,
        duration_seconds: int = 60,
        retrieval_params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Run a built-in load test with specified parameters.

        Executes concurrent requests to the retrieval endpoint and
        collects performance metrics.

        Args:
            queries: List of query strings to test
            concurrency: Number of concurrent requests
            duration_seconds: Test duration in seconds
            retrieval_params: Additional retrieval parameters

        Returns:
            Dictionary containing performance metrics
        """
        if not queries:
            logger.error("No queries provided for load test")
            return {
                "qps": 0.0,
                "tp50_ms": 0.0,
                "tp90_ms": 0.0,
                "tp99_ms": 0.0,
                "error_rate": 0.0,
                "avg_response_ms": 0.0,
                "total_requests": 0,
                "duration_seconds": 0.0
            }

        retrieval_params = retrieval_params or {}
        latencies: list[float] = []
        error_count = 0
        total_requests = 0
        start_time = time.time()
        end_time = start_time + duration_seconds

        logger.info(
            f"Starting load test: concurrency={concurrency}, "
            f"duration={duration_seconds}s, queries={len(queries)}"
        )

        semaphore = asyncio.Semaphore(concurrency)
        url = f"{self.base_url}/api/retrieve"

        async def make_request(query: str) -> tuple[bool, float]:
            """Make a single request and return success status and latency."""
            async with semaphore:
                try:
                    request_body = {
                        "query": query,
                        "top_k": 10,
                        "routes": {"es_text": True, "vector": {"enabled": True, "backend": "milvus"}},
                        "rewrite": {"enabled": False},
                        "fusion": {"method": "weighted_sum"},
                        "filters": {}
                    }
                    request_body.update(retrieval_params)

                    request_start = time.time()
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.post(url, json=request_body)
                        request_end = time.time()

                    latency_ms = (request_end - request_start) * 1000
                    return response.status_code == 200, latency_ms

                except Exception as e:
                    logger.warning(f"Request failed for query '{query}': {e}")
                    return False, 0.0

        async def run_queries():
            """Run queries until duration expires."""
            nonlocal total_requests, error_count, latencies

            query_index = 0
            while time.time() < end_time:
                query = queries[query_index % len(queries)]
                query_index += 1

                success, latency = await make_request(query)
                total_requests += 1

                if success:
                    latencies.append(latency)
                else:
                    error_count += 1

        await run_queries()

        actual_duration = time.time() - start_time

        if latencies:
            avg_response = sum(latencies) / len(latencies)
            tp50 = self._calculate_percentile(latencies, 50)
            tp90 = self._calculate_percentile(latencies, 90)
            tp99 = self._calculate_percentile(latencies, 99)
        else:
            avg_response = 0.0
            tp50 = 0.0
            tp90 = 0.0
            tp99 = 0.0

        qps = total_requests / actual_duration if actual_duration > 0 else 0.0
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0.0

        logger.info(
            f"Load test complete: {total_requests} requests, "
            f"QPS={qps:.2f}, error_rate={error_rate:.2f}%"
        )

        return {
            "qps": round(qps, 2),
            "tp50_ms": round(tp50, 2),
            "tp90_ms": round(tp90, 2),
            "tp99_ms": round(tp99, 2),
            "error_rate": round(error_rate, 2),
            "avg_response_ms": round(avg_response, 2),
            "total_requests": total_requests,
            "duration_seconds": round(actual_duration, 2)
        }

    def _calculate_percentile(self, latencies: list[float], percentile: float) -> float:
        """Calculate percentile value from a list of latencies.

        Args:
            latencies: List of latency values in milliseconds
            percentile: Percentile to calculate (0-100)

        Returns:
            Percentile value in milliseconds
        """
        if not latencies:
            return 0.0

        sorted_latencies = sorted(latencies)
        index = int(len(sorted_latencies) * percentile / 100)

        if index >= len(sorted_latencies):
            index = len(sorted_latencies) - 1

        return sorted_latencies[index]
