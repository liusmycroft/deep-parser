"""Image to text processor module."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from deep_parser.config.settings import I2tConfig
from deep_parser.logging_config import logger
from deep_parser.services.llm_service import LLMService


class ImageToTextProcessor:
    """Processor for converting images in markdown to text descriptions."""

    def __init__(self, config: I2tConfig, llm_service: LLMService):
        """Initialize the image to text processor.

        Args:
            config: I2t configuration
            llm_service: LLM service instance
        """
        self.config = config
        self.llm_service = llm_service

    async def process_markdown(
        self,
        markdown_text: str,
        doc_dir: Path,
        image_host_service: Any,
    ) -> str:
        """Process markdown text to convert images to text descriptions.

        Args:
            markdown_text: Original markdown text
            doc_dir: Document directory path
            image_host_service: Image hosting service instance

        Returns:
            Processed markdown text with image descriptions

        Raises:
            Exception: If fallback_on_error is 'fail' and processing fails
        """
        if not self.config.enabled:
            return markdown_text

        image_refs = self._parse_image_references(markdown_text)
        if not image_refs:
            return markdown_text

        processed_text = markdown_text
        offset = 0

        for ref in image_refs:
            try:
                local_image_path = doc_dir / ref["path"]
                if not local_image_path.exists():
                    logger.warning(f"Image file not found: {local_image_path}")
                    await self._handle_error(processed_text, ref, offset, "skip")
                    continue

                image_url = await image_host_service.upload_image(local_image_path)

                processed_text = self._replace_image_url(processed_text, ref, offset, image_url)

                prompt = "Please describe this image in detail."
                description = await self._get_image_description(local_image_path, prompt)

                i2t_block = f"\n<i2t>\n{description}\n</i2t>"
                insertion_point = processed_text.find(ref["full_match"], offset) + len(ref["full_match"])
                processed_text = processed_text[:insertion_point] + i2t_block + processed_text[insertion_point:]
                offset = insertion_point + len(i2t_block)

                logger.info(f"Successfully processed image: {ref['path']}")

            except Exception as e:
                logger.error(f"Error processing image {ref['path']}: {e}")
                await self._handle_error(processed_text, ref, offset, self.config.fallback_on_error, e)

        return processed_text

    def _parse_image_references(self, markdown_text: str) -> list[dict]:
        """Parse image references from markdown text.

        Args:
            markdown_text: Markdown text to parse

        Returns:
            List of image references with full_match, alt, and path
        """
        pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        matches = re.finditer(pattern, markdown_text)
        return [
            {"full_match": match.group(0), "alt": match.group(1), "path": match.group(2)}
            for match in matches
        ]

    def _replace_image_url(
        self,
        text: str,
        ref: dict,
        offset: int,
        new_url: str,
    ) -> str:
        """Replace image path with hosting URL in markdown text.

        Args:
            text: Current markdown text
            ref: Image reference dict
            offset: Current offset in text
            new_url: New image URL

        Returns:
            Updated markdown text
        """
        old_pattern = ref["full_match"]
        new_pattern = f'![{ref["alt"]}]({new_url})'
        return text.replace(old_pattern, new_pattern, 1)

    async def _get_image_description(self, image_path: Path, prompt: str) -> str:
        """Get description for an image using LLM service.

        Args:
            image_path: Path to image file
            prompt: Prompt for image description

        Returns:
            Image description text
        """
        for attempt in range(self.config.max_retries):
            try:
                response = await asyncio.wait_for(
                    self.llm_service.chat_with_image(image_path, prompt),
                    timeout=self.config.timeout_sec,
                )
                return response.strip()
            except asyncio.TimeoutError:
                logger.warning(f"Timeout getting description for {image_path}, attempt {attempt + 1}")
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Error getting description for {image_path}, attempt {attempt + 1}: {e}")
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(1)

        return ""

    async def _handle_error(
        self,
        text: str,
        ref: dict,
        offset: int,
        fallback_mode: str,
        error: Exception | None = None,
    ) -> None:
        """Handle error during image processing.

        Args:
            text: Current markdown text
            ref: Image reference dict
            offset: Current offset in text
            fallback_mode: Fallback mode (skip/empty/fail)
            error: Exception that occurred

        Raises:
            Exception: If fallback_mode is 'fail'
        """
        if fallback_mode == "skip":
            logger.info(f"Skipping image due to error: {ref['path']}")
        elif fallback_mode == "empty":
            i2t_block = "\n<i2t>\n</i2t>"
            insertion_point = text.find(ref["full_match"], offset) + len(ref["full_match"])
            text = text[:insertion_point] + i2t_block + text[insertion_point:]
            logger.info(f"Inserted empty i2t block for: {ref['path']}")
        elif fallback_mode == "fail":
            if error:
                raise error
            raise Exception(f"Failed to process image: {ref['path']}")
