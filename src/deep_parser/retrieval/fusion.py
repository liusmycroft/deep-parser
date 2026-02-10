"""Fusion ranking module for combining multiple retrieval routes.

This module provides fusion algorithms to combine results from different
retrieval routes (e.g., ES text search, vector search) into a single
ranked list.
"""

from collections import defaultdict
from typing import Any

from src.deep_parser.logging_config import logger


class FusionRanker:
    """Fusion ranking service for combining retrieval results.

    This class provides multiple fusion algorithms to combine results
    from different retrieval routes into a unified ranking.

    Supported algorithms:
        - weighted_sum: Min-max normalized weighted sum
        - rrf: Reciprocal Rank Fusion
    """

    def weighted_sum(
        self,
        results_by_route: dict[str, list[dict]],
        weights: dict[str, float]
    ) -> list[dict]:
        """Fuse results using weighted sum with min-max normalization.

        This method normalizes scores from each route to [0, 1] range using
        min-max normalization, then combines them using the provided weights.

        Args:
            results_by_route: Dictionary mapping route names to result lists
                Each result dict must contain a 'score' field
            weights: Dictionary mapping route names to their weights
                Weights are normalized to sum to 1

        Returns:
            List of result dicts sorted by fused score in descending order.
                Each result includes:
                    - All original fields
                    - route_scores: Dict of scores from each route
                    - score: Final fused score
        """
        if not results_by_route:
            return []

        logger.info(f"Fusing {len(results_by_route)} routes using weighted sum")

        # Normalize weights
        total_weight = sum(weights.values())
        if total_weight == 0:
            logger.warning("Total weight is 0, using equal weights")
            normalized_weights = {
                route: 1.0 / len(weights)
                for route in weights
            }
        else:
            normalized_weights = {
                route: weight / total_weight
                for route, weight in weights.items()
            }

        # Collect all chunk_ids across all routes
        all_results = defaultdict(lambda: {"route_scores": {}, "final_score": 0.0})

        # Normalize scores per route using min-max
        for route, results in results_by_route.items():
            if not results:
                continue

            scores = [r.get("score", 0.0) for r in results]
            min_score = min(scores)
            max_score = max(scores)

            # Avoid division by zero
            score_range = max_score - min_score
            weight = normalized_weights.get(route, 0.0)

            for result in results:
                chunk_id = result.get("chunk_id")
                if not chunk_id:
                    continue

                # Min-max normalization
                if score_range > 0:
                    normalized_score = (result.get("score", 0.0) - min_score) / score_range
                else:
                    normalized_score = 1.0

                all_results[chunk_id]["route_scores"][route] = normalized_score
                all_results[chunk_id]["final_score"] += normalized_score * weight

                # Store original result data
                for key, value in result.items():
                    if key not in all_results[chunk_id]:
                        all_results[chunk_id][key] = value

        # Convert to list and sort by final score
        fused_results = []
        for chunk_id, data in all_results.items():
            data["score"] = data["final_score"]
            data["chunk_id"] = chunk_id
            fused_results.append(data)

        fused_results.sort(key=lambda x: x["score"], reverse=True)

        logger.info(f"Fused to {len(fused_results)} results")
        return fused_results

    def rrf(
        self,
        results_by_route: dict[str, list[dict]],
        k: int = 60
    ) -> list[dict]:
        """Fuse results using Reciprocal Rank Fusion.

        RRF is a robust fusion method that combines rankings from multiple
        systems using the formula: score = sum(1 / (k + rank))

        Args:
            results_by_route: Dictionary mapping route names to result lists
                Each result dict must contain a 'score' field
            k: Constant parameter for RRF (default: 60)

        Returns:
            List of result dicts sorted by RRF score in descending order.
                Each result includes:
                    - All original fields
                    - route_scores: Dict of scores from each route
                    - score: Final RRF score
        """
        if not results_by_route:
            return []

        logger.info(f"Fusing {len(results_by_route)} routes using RRF with k={k}")

        all_results = defaultdict(lambda: {"route_scores": {}, "final_score": 0.0})

        # Calculate RRF scores
        for route, results in results_by_route.items():
            if not results:
                continue

            # Sort by score to get ranking
            sorted_results = sorted(results, key=lambda x: x.get("score", 0.0), reverse=True)

            for rank, result in enumerate(sorted_results, start=1):
                chunk_id = result.get("chunk_id")
                if not chunk_id:
                    continue

                # RRF formula: 1 / (k + rank)
                rrf_score = 1.0 / (k + rank)

                all_results[chunk_id]["route_scores"][route] = rrf_score
                all_results[chunk_id]["final_score"] += rrf_score

                # Store original result data
                for key, value in result.items():
                    if key not in all_results[chunk_id]:
                        all_results[chunk_id][key] = value

        # Convert to list and sort by RRF score
        fused_results = []
        for chunk_id, data in all_results.items():
            data["score"] = data["final_score"]
            data["chunk_id"] = chunk_id
            fused_results.append(data)

        fused_results.sort(key=lambda x: x["score"], reverse=True)

        logger.info(f"Fused to {len(fused_results)} results")
        return fused_results

    def fuse(
        self,
        results_by_route: dict[str, list[dict]],
        method: str = "weighted_sum",
        weights: dict[str, float] | None = None
    ) -> list[dict]:
        """Fuse results from multiple routes using specified method.

        This is the main entry point for fusion, dispatching to the
        appropriate fusion algorithm.

        Args:
            results_by_route: Dictionary mapping route names to result lists
            method: Fusion method ("weighted_sum" or "rrf")
            weights: Weights for weighted_sum method (ignored for rrf)

        Returns:
            List of fused and sorted results
        """
        if method == "weighted_sum":
            if weights is None:
                logger.warning("Weights not provided for weighted_sum, using equal weights")
                weights = {route: 1.0 for route in results_by_route.keys()}
            return self.weighted_sum(results_by_route, weights)
        elif method == "rrf":
            return self.rrf(results_by_route)
        else:
            logger.warning(f"Unknown fusion method: {method}, falling back to weighted_sum")
            weights = weights or {route: 1.0 for route in results_by_route.keys()}
            return self.weighted_sum(results_by_route, weights)
