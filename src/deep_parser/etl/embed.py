"""Embedding generation module."""

import asyncio
from typing import Any

from deep_parser.config.settings import EmbedConfig
from deep_parser.logging_config import logger
from deep_parser.services.llm_service import LLMService


class EmbeddingProcessor:
    """Processor for generating embeddings for text chunks."""

    def __init__(self, config: EmbedConfig, llm_service: LLMService):
        """Initialize the embedding processor.

        Args:
            config: Embedding configuration
            llm_service: LLM service instance
        """
        self.config = config
        self.llm_service = llm_service

    async def embed_chunks(self, chunks: list[dict]) -> list[dict]:
        """Generate embeddings for a list of chunks.

        Args:
            chunks: List of chunk dictionaries with 'content' field

        Returns:
            List of chunks with added 'embedding' field
        """
        if not chunks:
            return []

        texts = [chunk.get("content", "") for chunk in chunks]
        embeddings = await self._embed_batch(texts)

        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding

        logger.info(f"Successfully generated embeddings for {len(chunks)} chunks")
        return chunks

    async def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text

        Returns:
            Embedding vector as list of floats
        """
        embeddings = await self._embed_batch([text])
        return embeddings[0] if embeddings else []

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        all_embeddings = []
        batch_size = self.config.batch_size

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_embeddings = await self._process_batch_with_retry(batch_texts)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    async def _process_batch_with_retry(self, texts: list[str]) -> list[list[float]]:
        """Process a batch of texts with retry logic.

        Args:
            texts: Batch of texts to embed

        Returns:
            List of embedding vectors
        """
        for attempt in range(self.config.max_retries):
            try:
                embeddings = await asyncio.wait_for(
                    self.llm_service.get_embeddings(texts),
                    timeout=self.config.timeout_sec,
                )

                if len(embeddings) != len(texts):
                    logger.warning(
                        f"Embedding count mismatch: expected {len(texts)}, got {len(embeddings)}"
                    )
                    if attempt == self.config.max_retries - 1:
                        return [[] for _ in texts]
                    await asyncio.sleep(1)
                    continue

                return embeddings

            except asyncio.TimeoutError:
                logger.warning(f"Timeout generating embeddings, attempt {attempt + 1}")
                if attempt == self.config.max_retries - 1:
                    logger.error("Max retries reached for embedding generation")
                    return [[] for _ in texts]
                await asyncio.sleep(1)

            except Exception as e:
                logger.warning(f"Error generating embeddings, attempt {attempt + 1}: {e}")
                if attempt == self.config.max_retries - 1:
                    logger.error("Max retries reached for embedding generation")
                    return [[] for _ in texts]
                await asyncio.sleep(1)

        return [[] for _ in texts]
