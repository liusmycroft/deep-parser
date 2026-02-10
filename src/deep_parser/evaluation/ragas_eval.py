"""RAGAS evaluation module for RAG system performance assessment.

This module provides comprehensive evaluation capabilities for retrieval systems
using the RAGAS framework with fallback to simple metrics when RAGAS is unavailable.
"""

import json
from pathlib import Path
from typing import Any

from src.deep_parser.logging_config import logger
from src.deep_parser.retrieval.retriever import RetrieverService


class RagasEvaluator:
    """Evaluator for RAG system using RAGAS framework.

    This class provides evaluation capabilities for retrieval systems,
    including both advanced metrics via RAGAS and simple fallback metrics.

    Attributes:
        retriever_service: Retrieval service for executing queries
        use_ragas: Whether to use RAGAS framework
    """

    def __init__(self, retriever_service: RetrieverService):
        """Initialize the evaluator with a retrieval service.

        Args:
            retriever_service: Service for executing retrieval queries
        """
        self.retriever_service = retriever_service
        self.use_ragas = self._check_ragas_available()

    def _check_ragas_available(self) -> bool:
        """Check if RAGAS framework is available.

        Returns:
            True if RAGAS can be imported, False otherwise
        """
        try:
            import ragas
            logger.info("RAGAS framework is available")
            return True
        except ImportError:
            logger.warning("RAGAS framework not available, using simple metrics")
            return False

    async def evaluate(
        self,
        dataset_path: str,
        retrieval_params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Evaluate retrieval performance on a dataset.

        This method loads a JSONL dataset, executes retrieval queries,
        and computes evaluation metrics using RAGAS or simple fallback metrics.

        Args:
            dataset_path: Path to JSONL dataset file
            retrieval_params: Parameters for retrieval requests

        Returns:
            Dictionary containing:
                - metrics: Evaluation metrics
                - failed_cases: List of failed cases
                - total: Total number of queries
                - evaluated: Number of successfully evaluated queries
        """
        retrieval_params = retrieval_params or {}
        dataset = await self._load_dataset(dataset_path)

        if not dataset:
            logger.error(f"Failed to load dataset from {dataset_path}")
            return {
                "metrics": {},
                "failed_cases": [],
                "total": 0,
                "evaluated": 0
            }

        logger.info(f"Evaluating {len(dataset)} queries from dataset")

        results = []
        failed_cases = []

        for item in dataset:
            question = item.get("question", "")
            ground_truth = item.get("ground_truth", [])
            doc_id = item.get("doc_id")

            if not question or not ground_truth:
                logger.warning(f"Skipping invalid item: {item}")
                continue

            try:
                retrieval_request = {
                    "query": question,
                    "top_k": 10,
                    "routes": {"es_text": True, "vector": {"enabled": True, "backend": "milvus"}},
                    "rewrite": {"enabled": False},
                    "fusion": {"method": "weighted_sum"},
                    "filters": {}
                }
                retrieval_request.update(retrieval_params)

                response = await self.retriever_service.retrieve(retrieval_request)
                retrieved_docs = [r.get("doc_id") for r in response.get("results", [])]

                result = {
                    "question": question,
                    "ground_truth": ground_truth,
                    "retrieved_docs": retrieved_docs,
                    "hit": any(doc_id in ground_truth for doc_id in retrieved_docs)
                }

                if doc_id:
                    result["expected_doc_id"] = doc_id

                results.append(result)

                if not result["hit"]:
                    failed_cases.append({
                        "question": question,
                        "ground_truth": ground_truth,
                        "retrieved_docs": retrieved_docs[:5]
                    })

            except Exception as e:
                logger.error(f"Failed to evaluate question '{question}': {e}")
                failed_cases.append({
                    "question": question,
                    "ground_truth": ground_truth,
                    "error": str(e)
                })

        if self.use_ragas:
            metrics = self._calculate_ragas_metrics(results)
        else:
            metrics = self._calculate_simple_metrics(results)

        logger.info(f"Evaluation complete: {len(results)}/{len(dataset)} queries evaluated")

        return {
            "metrics": metrics,
            "failed_cases": failed_cases,
            "total": len(dataset),
            "evaluated": len(results)
        }

    async def _load_dataset(self, dataset_path: str) -> list[dict[str, Any]]:
        """Load JSONL dataset file.

        Args:
            dataset_path: Path to JSONL file

        Returns:
            List of dataset items
        """
        path = Path(dataset_path)

        if not path.exists():
            logger.error(f"Dataset file not found: {dataset_path}")
            return []

        dataset = []

        try:
            with open(path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        item = json.loads(line)
                        dataset.append(item)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse line {line_num}: {e}")

            logger.info(f"Loaded {len(dataset)} items from {dataset_path}")
            return dataset

        except Exception as e:
            logger.error(f"Failed to load dataset: {e}")
            return []

    def _calculate_simple_metrics(self, results: list[dict[str, Any]]) -> dict[str, float]:
        """Calculate simple evaluation metrics.

        Computes hit rate and mean reciprocal rank (MRR) for retrieval results.

        Args:
            results: List of evaluation results

        Returns:
            Dictionary containing simple metrics
        """
        if not results:
            return {"hit_rate": 0.0, "mrr": 0.0}

        hit_count = 0
        reciprocal_ranks = []

        for result in results:
            ground_truth = result.get("ground_truth", [])
            retrieved_docs = result.get("retrieved_docs", [])

            if not ground_truth:
                continue

            hit_found = False
            for i, doc_id in enumerate(retrieved_docs):
                if doc_id in ground_truth:
                    hit_found = True
                    reciprocal_ranks.append(1.0 / (i + 1))
                    break

            if hit_found:
                hit_count += 1
            else:
                reciprocal_ranks.append(0.0)

        hit_rate = hit_count / len(results) if results else 0.0
        mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0

        return {
            "hit_rate": round(hit_rate, 4),
            "mrr": round(mrr, 4)
        }

    def _calculate_ragas_metrics(self, results: list[dict[str, Any]]) -> dict[str, float]:
        """Calculate RAGAS metrics for retrieval evaluation.

        Attempts to use RAGAS framework for advanced metrics calculation.
        Falls back to simple metrics if RAGAS computation fails.

        Args:
            results: List of evaluation results

        Returns:
            Dictionary containing RAGAS metrics
        """
        try:
            from ragas import evaluate
            from ragas.metrics import context_precision, context_recall, faithfulness
            from datasets import Dataset

            ragas_data = []
            for result in results:
                ragas_data.append({
                    "question": result["question"],
                    "contexts": [result.get("retrieved_docs", [])],
                    "ground_truths": [result["ground_truth"]]
                })

            dataset = Dataset.from_list(ragas_data)

            result = evaluate(
                dataset=dataset,
                metrics=[context_precision, context_recall, faithfulness]
            )

            logger.info("RAGAS metrics calculated successfully")

            return {
                "context_precision": result["context_precision"],
                "context_recall": result["context_recall"],
                "faithfulness": result["faithfulness"],
                "hit_rate": result.get("hit_rate", 0.0),
                "mrr": result.get("mrr", 0.0)
            }

        except Exception as e:
            logger.warning(f"RAGAS calculation failed, using simple metrics: {e}")
            return self._calculate_simple_metrics(results)
