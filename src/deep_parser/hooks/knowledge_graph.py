"""Knowledge graph hook interface for document processing.

This module provides the abstract interface for knowledge graph extraction
and storage during the document processing pipeline.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphNode:
    """Represents a node in the knowledge graph.
    
    Attributes:
        node_id: Unique identifier for the node
        label: Type or category of the node (e.g., "Person", "Organization")
        properties: Dictionary of node properties and attributes
    """
    node_id: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """Represents an edge (relationship) in the knowledge graph.
    
    Attributes:
        source_id: ID of the source node
        target_id: ID of the target node
        relation: Type of relationship (e.g., "WORKS_FOR", "LOCATED_IN")
        properties: Dictionary of edge properties and attributes
    """
    source_id: str
    target_id: str
    relation: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphResult:
    """Container for knowledge graph extraction results.
    
    Attributes:
        nodes: List of extracted nodes
        edges: List of extracted relationships between nodes
    """
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


class KnowledgeGraphHook(ABC):
    """Abstract base class for knowledge graph extraction hooks.
    
    Implementations of this hook can extract structured knowledge graphs
    from document chunks and persist them to graph databases.
    """
    
    @abstractmethod
    async def on_chunks_ready(self, doc_id: str, chunks: list[dict]) -> GraphResult:
        """Called when document chunks are ready for knowledge graph extraction.
        
        Args:
            doc_id: Unique identifier of the document
            chunks: List of document chunks with metadata
            
        Returns:
            GraphResult containing extracted nodes and edges
        """
        pass
    
    @abstractmethod
    async def save_graph(self, result: GraphResult) -> None:
        """Save the knowledge graph result to persistent storage.
        
        Args:
            result: GraphResult containing nodes and edges to save
        """
        pass


class NoOpKnowledgeGraphHook(KnowledgeGraphHook):
    """Default no-op implementation that does nothing.
    
    This implementation is used when knowledge graph extraction
    is not required or configured.
    """
    
    async def on_chunks_ready(self, doc_id: str, chunks: list[dict]) -> GraphResult:
        """Returns empty graph result without processing.
        
        Args:
            doc_id: Unique identifier of the document (ignored)
            chunks: List of document chunks (ignored)
            
        Returns:
            Empty GraphResult
        """
        return GraphResult()
    
    async def save_graph(self, result: GraphResult) -> None:
        """Does nothing - no-op implementation.
        
        Args:
            result: GraphResult (ignored)
        """
        pass


def get_knowledge_graph_hook() -> KnowledgeGraphHook:
    """Factory function to get the knowledge graph hook instance.
    
    Returns:
        KnowledgeGraphHook instance (defaults to NoOpKnowledgeGraphHook)
    """
    return NoOpKnowledgeGraphHook()
