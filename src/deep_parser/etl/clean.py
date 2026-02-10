"""Markdown cleaning module for Deep Parser.

This module provides text cleaning functionality for RAG preprocessing:
- Remove text matching regex patterns
- Remove lines containing specific keywords
- Validate minimum text length after cleaning
"""

import re
from typing import Dict, Tuple

from deep_parser.config.settings import CleanConfig
from deep_parser.logging_config import logger


class MarkdownCleaner:
    """Cleaner for markdown text using regex and keyword rules."""

    def __init__(self, config: CleanConfig):
        """Initialize markdown cleaner with configuration.

        Args:
            config: CleanConfig containing cleaning rules
        """
        self.config = config

    def clean(self, markdown_text: str) -> Tuple[str, Dict]:
        """Clean markdown text according to configured rules.

        Args:
            markdown_text: Raw markdown text to clean

        Returns:
            Tuple of (cleaned_text, stats_dict) where stats contains:
                - original_length: Length of input text
                - cleaned_length: Length of cleaned text
                - lines_removed: Number of lines removed
                - warning: Optional warning message if text too short
        """
        original_length = len(markdown_text)
        original_lines = markdown_text.split("\n")

        cleaned_text = self._apply_regex_rules(markdown_text)
        cleaned_text = self._apply_contains_rules(cleaned_text)

        cleaned_text = cleaned_text.strip()

        cleaned_lines = cleaned_text.split("\n")
        lines_removed = len(original_lines) - len(cleaned_lines)
        cleaned_length = len(cleaned_text)

        stats = {
            "original_length": original_length,
            "cleaned_length": cleaned_length,
            "lines_removed": lines_removed,
        }

        if cleaned_length < self.config.min_length_after_clean:
            stats["warning"] = (
                f"Cleaned text length ({cleaned_length}) is below minimum "
                f"threshold ({self.config.min_length_after_clean})"
            )
            logger.warning(stats["warning"])

        logger.info(
            f"Clean markdown success original={original_length} "
            f"cleaned={cleaned_length} lines_removed={lines_removed}"
        )

        return cleaned_text, stats

    def _apply_regex_rules(self, text: str) -> str:
        """Apply regex removal rules to text.

        Args:
            text: Input text

        Returns:
            Text with regex patterns removed
        """
        result = text
        for pattern in self.config.remove_regex:
            result = re.sub(pattern, "", result, flags=re.MULTILINE)
        return result

    def _apply_contains_rules(self, text: str) -> str:
        """Apply keyword-based line removal rules.

        Args:
            text: Input text

        Returns:
            Text with lines containing keywords removed
        """
        lines = text.split("\n")
        filtered_lines = []

        for line in lines:
            should_remove = False
            for keyword in self.config.remove_contains:
                if keyword in line:
                    should_remove = True
                    break

            if not should_remove:
                filtered_lines.append(line)

        return "\n".join(filtered_lines)
