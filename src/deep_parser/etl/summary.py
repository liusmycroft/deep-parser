"""Sliding window summarization module."""

import asyncio
from typing import Any

from deep_parser.config.settings import SummaryConfig
from deep_parser.logging_config import logger
from deep_parser.services.llm_service import LLMService


class SlidingWindowSummarizer:
    """Summarizer using sliding window technique across multiple layers."""

    def __init__(self, config: SummaryConfig, llm_service: LLMService):
        """Initialize the sliding window summarizer.

        Args:
            config: Summary configuration
            llm_service: LLM service instance
        """
        self.config = config
        self.llm_service = llm_service

    async def summarize(self, chunks: list[dict]) -> list[dict]:
        """Generate multi-level sliding window summaries from chunks.

        Args:
            chunks: List of chunk dictionaries with 'content' and other metadata

        Returns:
            List of summary chunks from all layers
        """
        if not self.config.enabled:
            return []

        if len(chunks) < self.config.window_size:
            logger.info("Not enough chunks for sliding window summarization")
            return []

        all_summaries = []
        current_chunks = chunks

        for level in range(self.config.layers):
            if len(current_chunks) < self.config.window_size:
                logger.info(f"Layer {level + 1}: Not enough chunks, stopping")
                break

            logger.info(f"Processing layer {level + 1} with {len(current_chunks)} chunks")
            summaries = await self._generate_layer_summaries(current_chunks, level)
            
            if not summaries:
                break

            all_summaries.extend(summaries)
            current_chunks = summaries

        logger.info(f"Generated {len(all_summaries)} summaries across {len([s for s in all_summaries if s['level'] == 0]) + 1} layers")
        return all_summaries

    async def _generate_layer_summaries(
        self,
        chunks: list[dict],
        level: int,
    ) -> list[dict]:
        """Generate summaries for a single layer using sliding window.

        Args:
            chunks: List of chunks to summarize
            level: Current layer level

        Returns:
            List of summary chunks for this layer
        """
        summaries = []
        window_size = self.config.window_size
        num_windows = len(chunks) - window_size + 1

        tasks = []
        for i in range(num_windows):
            window_chunks = chunks[i:i + window_size]
            window_texts = [chunk["content"] for chunk in window_chunks]
            tasks.append(self._summarize_window(window_texts))

        window_summaries = await asyncio.gather(*tasks)

        for i, summary_text in enumerate(window_summaries):
            if not summary_text:
                continue

            summary_chunk = {
                "doc_id": chunks[0].get("doc_id", ""),
                "chunk_type": "summary",
                "level": level + 1,
                "window_size": window_size,
                "order_index": i,
                "content": summary_text,
                "token_count": len(summary_text.split()),
            }
            summaries.append(summary_chunk)

        return summaries

    async def _summarize_window(self, texts: list[str]) -> str:
        """Summarize a window of texts.

        Args:
            texts: List of texts in the window

        Returns:
            Summary text
        """
        combined_text = "\n\n".join(texts)
        
        prompt = self.config.prompt_template.format(
            max_tokens=self.config.max_tokens_summary,
            text=combined_text,
        )

        try:
            response = await asyncio.wait_for(
                self.llm_service.chat(prompt),
                timeout=self.config.timeout_sec,
            )
            return response.strip()
        except asyncio.TimeoutError:
            logger.warning("Timeout during window summarization")
            return ""
        except Exception as e:
            logger.warning(f"Error during window summarization: {e}")
            return ""
