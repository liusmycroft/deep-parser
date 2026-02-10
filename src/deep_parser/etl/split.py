"""Markdown splitting module for Deep Parser.

This module provides text chunking functionality for RAG preprocessing:
- Recursive splitting by separator priority
- Token count validation
- Small chunk merging
- I2T block protection from splitting
"""

import re
import tiktoken
from typing import Dict, List, Tuple

from deep_parser.config.settings import SplitConfig
from deep_parser.logging_config import logger


class ChunkSplitter:
    """Split markdown text into chunks based on token count and separators."""

    def __init__(self, config: SplitConfig):
        """Initialize chunk splitter with configuration.

        Args:
            config: SplitConfig containing splitting rules
        """
        self.config = config
        try:
            self.tokenizer = tiktoken.get_encoding(config.tokenizer)
        except KeyError:
            logger.warning(f"Tokenizer {config.tokenizer} not found, using cl100k_base")
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def split(self, text: str, doc_id: str) -> List[Dict]:
        """Split text into chunks with metadata.

        Args:
            text: Input markdown text
            doc_id: Document identifier for metadata

        Returns:
            List of chunk dictionaries with keys:
                - doc_id: Document identifier
                - order_index: Sequential chunk index
                - content: Chunk text content
                - token_count: Number of tokens in chunk
        """
        if not text:
            logger.warning(f"Split empty text doc_id={doc_id}")
            return []

        protected_text, i2t_mapping = self._protect_i2t_blocks(text)

        chunks = self._recursive_split(protected_text, 0)

        merged_chunks = self._merge_small_chunks(chunks)

        restored_chunks = [
            self._restore_i2t_blocks(chunk, i2t_mapping) for chunk in merged_chunks
        ]

        result = []
        for order_index, chunk_content in enumerate(restored_chunks):
            token_count = self._count_tokens(chunk_content)
            result.append(
                {
                    "doc_id": doc_id,
                    "order_index": order_index,
                    "content": chunk_content,
                    "token_count": token_count,
                }
            )

        logger.info(f"Split text success doc_id={doc_id} chunks={len(result)}")
        return result

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using configured tokenizer.

        Args:
            text: Input text

        Returns:
            Number of tokens
        """
        if not text:
            return 0
        tokens = self.tokenizer.encode(text)
        return len(tokens)

    def _protect_i2t_blocks(self, text: str) -> Tuple[str, Dict]:
        """Replace i2t blocks with placeholders to prevent splitting.

        Args:
            text: Input text with potential i2t blocks

        Returns:
            Tuple of (text_with_placeholders, placeholder_to_content_mapping)
        """
        i2t_pattern = r"<i2t>.*?</i2t>"
        matches = re.finditer(i2t_pattern, text, re.DOTALL)

        mapping = {}
        result = text
        offset = 0

        for match in matches:
            placeholder = f"__I2T_BLOCK_{len(mapping)}__"
            mapping[placeholder] = match.group(0)
            start = match.start() + offset
            end = match.end() + offset
            result = result[:start] + placeholder + result[end:]
            offset += len(placeholder) - len(match.group(0))

        return result, mapping

    def _restore_i2t_blocks(self, text: str, mapping: Dict) -> str:
        """Restore i2t blocks from placeholders.

        Args:
            text: Text with placeholders
            mapping: Placeholder to content mapping

        Returns:
            Text with i2t blocks restored
        """
        result = text
        for placeholder, content in mapping.items():
            result = result.replace(placeholder, content)
        return result

    def _recursive_split(self, text: str, separator_index: int) -> List[str]:
        """Recursively split text using separators by priority.

        Args:
            text: Input text
            separator_index: Current separator index in the list

        Returns:
            List of text chunks
        """
        if separator_index >= len(self.config.separators):
            return [text]

        separator = self.config.separators[separator_index]
        chunks = text.split(separator)

        result = []
        for chunk in chunks:
            token_count = self._count_tokens(chunk)

            if token_count <= self.config.max_tokens:
                result.append(chunk)
            else:
                if separator_index + 1 < len(self.config.separators):
                    sub_chunks = self._recursive_split(chunk, separator_index + 1)
                    result.extend(sub_chunks)
                else:
                    result.append(chunk)

        result = [chunk for chunk in result if chunk.strip()]
        return result

    def _merge_small_chunks(self, chunks: List[str]) -> List[str]:
        """Merge chunks that are too small.

        Args:
            chunks: List of chunks to merge

        Returns:
            List of merged chunks
        """
        if not chunks:
            return chunks

        result = []
        current_chunk = ""

        for chunk in chunks:
            if not current_chunk:
                current_chunk = chunk
                continue

            current_tokens = self._count_tokens(current_chunk)
            chunk_tokens = self._count_tokens(chunk)

            if current_tokens < self.config.min_tokens:
                merged = current_chunk + "\n\n" + chunk
                merged_tokens = self._count_tokens(merged)

                if merged_tokens <= self.config.max_tokens:
                    current_chunk = merged
                    continue

            result.append(current_chunk)
            current_chunk = chunk

        if current_chunk:
            result.append(current_chunk)

        return result
