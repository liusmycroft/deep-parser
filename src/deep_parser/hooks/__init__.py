"""Extension hooks for future capabilities like knowledge graph."""

from deep_parser.hooks.knowledge_graph import (
    GraphNode,
    GraphEdge,
    GraphResult,
    KnowledgeGraphHook,
    NoOpKnowledgeGraphHook,
    get_knowledge_graph_hook,
)

__all__ = [
    "GraphNode",
    "GraphEdge",
    "GraphResult",
    "KnowledgeGraphHook",
    "NoOpKnowledgeGraphHook",
    "get_knowledge_graph_hook",
]
