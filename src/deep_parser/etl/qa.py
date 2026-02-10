"""Q&A generation module."""

import asyncio
import json
from typing import Any

from deep_parser.config.settings import QaConfig
from deep_parser.logging_config import logger
from deep_parser.services.llm_service import LLMService


class QAGenerator:
    """Generator for question-answer pairs from text using LLM."""

    def __init__(self, config: QaConfig, llm_service: LLMService):
        """Initialize the Q&A generator.

        Args:
            config: Q&A configuration
            llm_service: LLM service instance
        """
        self.config = config
        self.llm_service = llm_service

    async def generate(self, text: str) -> list[dict]:
        """Generate Q&A pairs from text.

        Args:
            text: Input text to generate Q&A from

        Returns:
            List of Q&A dictionaries with 'q' and 'a' keys
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

                qa_pairs = self._parse_qa_response(response)
                if qa_pairs:
                    logger.info(f"Successfully generated {len(qa_pairs)} Q&A pairs")
                    return qa_pairs

                logger.warning(f"Failed to parse Q&A response, attempt {attempt + 1}")

            except asyncio.TimeoutError:
                logger.warning(f"Timeout generating Q&A, attempt {attempt + 1}")
                if attempt == self.config.max_retries - 1:
                    logger.error("Max retries reached for Q&A generation")
                    return []
                await asyncio.sleep(1)

            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error, attempt {attempt + 1}: {e}")
                if attempt == self.config.max_retries - 1:
                    logger.error("Max retries reached for Q&A generation")
                    return []
                await asyncio.sleep(1)

            except Exception as e:
                logger.warning(f"Error generating Q&A, attempt {attempt + 1}: {e}")
                if attempt == self.config.max_retries - 1:
                    logger.error("Max retries reached for Q&A generation")
                    return []
                await asyncio.sleep(1)

        return []

    async def generate_batch(self, texts: list[str]) -> list[list[dict]]:
        """Generate Q&A pairs from multiple texts concurrently.

        Args:
            texts: List of input texts

        Returns:
            List of Q&A pair lists, one per input text
        """
        tasks = [self.generate(text) for text in texts]
        return await asyncio.gather(*tasks)

    def _parse_qa_response(self, response: str) -> list[dict]:
        """Parse LLM response to extract Q&A pairs.

        Args:
            response: Raw LLM response string

        Returns:
            List of Q&A dictionaries

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
            qa_list = json.loads(response)
            if isinstance(qa_list, list):
                return [{"q": str(qa.get("q", "")), "a": str(qa.get("a", ""))} for qa in qa_list]
            elif isinstance(qa_list, dict) and "qas" in qa_list:
                return [{"q": str(qa.get("q", "")), "a": str(qa.get("a", ""))} for qa in qa_list["qas"]]
            return []
        except json.JSONDecodeError:
            return []
