"""LLM service abstraction layer for Deep Parser.

This module provides:
- Abstract base class for LLM service implementations
- OpenAI implementation with retry logic
- Factory function for service instantiation
"""

import asyncio
from abc import ABC, abstractmethod
from typing import List

from openai import AsyncOpenAI

from deep_parser.logging_config import logger


class LLMService(ABC):
    """Abstract base class for LLM service implementations."""

    @abstractmethod
    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        """Send a chat request to the LLM.

        Args:
            prompt: User prompt text
            system_prompt: Optional system prompt for context

        Returns:
            LLM response text

        Raises:
            Exception: If the request fails after retries
        """
        pass

    @abstractmethod
    async def chat_with_image(self, prompt: str, image_url: str) -> str:
        """Send a chat request with image to the LLM.

        Args:
            prompt: User prompt text
            image_url: URL of the image to analyze

        Returns:
            LLM response text describing the image

        Raises:
            Exception: If the request fails after retries
        """
        pass

    @abstractmethod
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a batch of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors, one per input text

        Raises:
            Exception: If the request fails after retries
        """
        pass


class OpenAILLMService(LLMService):
    """OpenAI implementation of LLM service with retry logic."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        embedding_model: str,
        embedding_dim: int,
    ):
        """Initialize OpenAI LLM service.

        Args:
            api_key: OpenAI API key
            base_url: OpenAI base URL
            model: Chat completion model name
            embedding_model: Embedding model name
            embedding_dim: Embedding dimension
        """
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.embedding_model = embedding_model
        self.embedding_dim = embedding_dim
        self.max_retries = 3

    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        """Send a chat request to OpenAI.

        Args:
            prompt: User prompt text
            system_prompt: Optional system prompt for context

        Returns:
            LLM response text
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model, messages=messages
                )
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                logger.warning(
                    f"LLM chat attempt {attempt + 1}/{self.max_retries} failed: {str(e)}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt)

        logger.error(f"LLM chat failed after {self.max_retries} attempts", error=last_error)
        raise last_error

    async def chat_with_image(self, prompt: str, image_url: str) -> str:
        """Send a chat request with image to OpenAI.

        Args:
            prompt: User prompt text
            image_url: URL of the image to analyze

        Returns:
            LLM response text describing the image
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ]

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model, messages=messages
                )
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                logger.warning(
                    f"LLM chat_with_image attempt {attempt + 1}/{self.max_retries} failed: {str(e)}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt)

        logger.error(
            f"LLM chat_with_image failed after {self.max_retries} attempts", error=last_error
        )
        raise last_error

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a batch of texts from OpenAI.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors, one per input text
        """
        if not texts:
            return []

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self.client.embeddings.create(
                    model=self.embedding_model, input=texts
                )
                embeddings = [item.embedding for item in response.data]
                return embeddings
            except Exception as e:
                last_error = e
                logger.warning(
                    f"LLM get_embeddings attempt {attempt + 1}/{self.max_retries} failed: {str(e)}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt)

        logger.error(
            f"LLM get_embeddings failed after {self.max_retries} attempts", error=last_error
        )
        raise last_error


def get_llm_service() -> LLMService:
    """Factory function to get LLM service based on settings.

    Returns:
        LLMService implementation based on configured provider

    Raises:
        ValueError: If the provider is not supported
    """
    from deep_parser.config.settings import get_settings

    settings = get_settings()

    if settings.llm_provider.lower() == "openai":
        return OpenAILLMService(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            embedding_model=settings.embedding_model,
            embedding_dim=settings.embedding_dim,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
