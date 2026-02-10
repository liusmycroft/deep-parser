"""Keyword extraction module."""

import asyncio
import json
from typing import Any

from deep_parser.config.settings import KeywordsConfig
from deep_parser.logging_config import logger
from deep_parser.services.llm_service import LLMService


class KeywordExtractor:
    """Extractor for keywords from text using LLM."""

    def __init__(self, config: KeywordsConfig, llm_service: LLMService):
        """Initialize the keyword extractor.

        Args:
            config: Keywords configuration
            llm_service: LLM service instance
        """
        self.config = config
        self.llm_service = llm_service

    async def extract(self, text: str) -> list[str]:
        """Extract keywords from text.

        Args:
            text: Input text to extract keywords from

        Returns:
            List of extracted keywords
        """
        if not self.config.enabled:
            return []

        prompt = self.config.prompt_template.format(
            top_n=self.config.top_n,
            text=text,
        )

        for attempt in range(self.config.max_retries):
            try:
                response = await asyncio.wait_for(
                    self.llm_service.chat(prompt),
                    timeout=self.config.timeout_sec,
                )

                keywords = self._parse_keywords_response(response)
                if keywords:
                    logger.info(f"Successfully extracted {len(keywords)} keywords")
                    return keywords

                logger.warning(f"Failed to parse keywords response, attempt {attempt + 1}")

            except asyncio.TimeoutError:
                logger.warning(f"Timeout extracting keywords, attempt {attempt + 1}")
                if attempt == self.config.max_retries - 1:
                    logger.error("Max retries reached for keyword extraction")
                    return []
                await asyncio.sleep(1)

            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error, attempt {attempt + 1}: {e}")
                if attempt == self.config.max_retries - 1:
                    logger.error("Max retries reached for keyword extraction")
                    return []
                await asyncio.sleep(1)

            except Exception as e:
                logger.warning(f"Error extracting keywords, attempt {attempt + 1}: {e}")
                if attempt == self.config.max_retries - 1:
                    logger.error("Max retries reached for keyword extraction")
                    return []
                await asyncio.sleep(1)

        return []

    async def extract_batch(self, texts: list[str]) -> list[list[str]]:
        """Extract keywords from multiple texts concurrently.

        Args:
            texts: List of input texts

        Returns:
            List of keyword lists, one per input text
        """
        tasks = [self.extract(text) for text in texts]
        return await asyncio.gather(*tasks)

    def _parse_keywords_response(self, response: str) -> list[str]:
        """Parse LLM response to extract keywords list.

        Args:
            response: Raw LLM response string

        Returns:
            List of keywords

        Raises:
            json.JSONDecodeError: If response is not valid JSON
        """
        response = response.strip()

        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        response = response.strip()

        try:
            keywords = json.loads(response)
            if isinstance(keywords, list):
                return [str(k) for k in keywords]
            elif isinstance(keywords, dict) and "keywords" in keywords:
                return [str(k) for k in keywords["keywords"]]
            return []
        except json.JSONDecodeError:
            return []
