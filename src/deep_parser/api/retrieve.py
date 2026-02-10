from fastapi import APIRouter, HTTPException

from src.deep_parser.config.settings import get_settings
from src.deep_parser.logging_config import logger
from src.deep_parser.retrieval.retriever import RetrieverService
from src.deep_parser.services.llm_service import get_llm_service

router = APIRouter(prefix="/retrieve", tags=["retrieve"])

# Initialize retrieval service
settings = get_settings()
llm_service = get_llm_service()
retriever_service = RetrieverService(settings, llm_service)


@router.post("/")
async def retrieve(request: dict):
    """Execute multi-route document retrieval.

    This endpoint provides advanced retrieval capabilities including:
    - Multi-route search (ES text, vector search)
    - Query rewriting (keywords, LLM-based)
    - Result fusion (weighted sum, RRF)
    - Flexible filtering

    Request format:
    {
        "query": "search query",
        "top_k": 20,
        "routes": {
            "es_text": true,
            "vector": {
                "enabled": true,
                "backend": "milvus"
            }
        },
        "rewrite": {
            "enabled": false,
            "method": "keywords",
            "params": {}
        },
        "fusion": {
            "method": "weighted_sum",
            "weights": {
                "es_text": 0.5,
                "vector_milvus": 0.5
            }
        },
        "filters": {
            "doc_ids": [],
            "source_type": []
        }
    }

    Response format:
    {
        "query_used": "actual query used for retrieval",
        "results": [
            {
                "chunk_id": "uuid",
                "doc_id": "uuid",
                "score": 0.95,
                "route_scores": {
                    "es_text": 0.8,
                    "vector_milvus": 0.9
                },
                "content": "chunk content",
                "keywords": ["keyword1", "keyword2"],
                "metadata": {
                    "level": 0,
                    "order_index": 3,
                    "chunk_type": "original"
                }
            }
        ]
    }

    Args:
        request: Retrieval request dictionary

    Returns:
        Dictionary with query_used and results list

    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.info(f"Received retrieval request: query='{request.get('query', '')}'")

        # Validate request
        if not request.get("query"):
            raise HTTPException(status_code=400, detail="Query parameter is required")

        # Execute retrieval
        result = await retriever_service.retrieve(request)

        logger.info(f"Retrieval completed: {len(result.get('results', []))} results")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")