"""
app/llm/llm_service.py
=======================
Orchestration service for the Legal QA LLM pipeline.

PURPOSE:
    Coalesces input validation, conversation memory, prompt construction, LLM generation,
    response parsing, and audit logging into a single cohesive execution flow.
"""

from __future__ import annotations

import time
from typing import List, Optional
from app.core.config import Settings
from app.core.exceptions import LLMError, RetrievalError
from app.models.document import RetrievedChunk
from app.retrieval.retrieval_models import FusionCandidate
from app.llm.base_provider import LLMProvider
from app.llm.conversation_memory import ConversationHistoryMemory
from app.llm.llm_logger import llm_log
from app.llm.llm_models import LLMResult
from app.llm.llm_repository import ConversationHistoryRepository
from app.llm.prompt_builder import PromptBuilder
from app.llm.response_formatter import ResponseFormatter
from app.llm.llm_utils import (
    validate_llm_query,
    check_context_presence,
    get_empty_context_result,
)


class LLMService:
    """
    Orchestration service for the LLM legal question answering pipeline.

    Args:
        provider:    Active concrete ``LLMProvider`` (Gemini or OpenAI).
        repository:  ``ConversationHistoryRepository`` for persistent message storage.
        memory:      ``ConversationHistoryMemory`` for runtime sliding-window buffer.
        settings:    Application Settings.
    """

    def __init__(
        self,
        provider: LLMProvider,
        repository: ConversationHistoryRepository,
        memory: ConversationHistoryMemory,
        settings: Settings,
    ) -> None:
        self.provider = provider
        self.repository = repository
        self.memory = memory
        self.settings = settings

        # Hydrate memory with persisted chat messages on startup
        self._hydrate_memory()

    def _hydrate_memory(self) -> None:
        """Loads historical messages from repository into runtime memory."""
        try:
            persisted = self.repository.load_messages()
            for msg in persisted:
                self.memory.add_exchange(msg.question, msg.answer)
            llm_log.info("Hydrated conversation memory | count={n}", n=len(persisted))
        except Exception as exc:
            llm_log.warning("Failed to hydrate conversation memory | error={err}", err=str(exc))

    async def answer_question(
        self,
        raw_query: str,
        retrieved_chunks: List[FusionCandidate] | List[RetrievedChunk],
    ) -> LLMResult:
        """
        Executes the entire legal QA pipeline.

        Steps:
            1. Validate the user input query format and length.
            2. Check context sufficiency. If empty, return standard fallback answer.
            3. Load history strings and build the composite instruction prompt.
            4. Query the LLM provider API.
            5. Clean and parse raw JSON text.
            6. Append the successful QA exchange to persistent and runtime memory.
            7. Log metrics and return the result.
        """
        start_time = time.perf_counter()

        # Step 1 — Input validation
        try:
            validate_llm_query(raw_query)
        except ValueError as exc:
            llm_log.warning("Query validation failed | error={err}", err=str(exc))
            raise

        clean_query = raw_query.strip()

        # Step 1.5 — Score calculation and threshold validation
        max_vector_score = 0.0
        max_hybrid_score = 0.0
        max_rerank_score = 0.0

        if retrieved_chunks:
            vector_scores = []
            hybrid_scores = []
            for chunk in retrieved_chunks:
                # Extract vector score
                if hasattr(chunk, "vector_score"):
                    vector_scores.append(chunk.vector_score)
                elif hasattr(chunk, "source") and chunk.source == "vector":
                    vector_scores.append(chunk.score)

                # Extract hybrid or rerank score
                if hasattr(chunk, "hybrid_score"):
                    hybrid_scores.append(chunk.hybrid_score)
                elif hasattr(chunk, "rrf_score"):
                    hybrid_scores.append(chunk.rrf_score)
                elif hasattr(chunk, "score"):
                    hybrid_scores.append(chunk.score)

            if vector_scores:
                max_vector_score = max(vector_scores)
            if hybrid_scores:
                if self.settings.use_reranker:
                    max_rerank_score = max(hybrid_scores)
                else:
                    max_hybrid_score = max(hybrid_scores)

        # Apply Domain Constraint Check
        if not retrieved_chunks or max_vector_score < self.settings.min_vector_score:
            llm_log.warning(
                "Query rejected (Out of Domain) | query={q} | max_vector_score={m_v:.4f} (min={min_v:.4f}) | docs={docs}",
                q=clean_query[:80],
                m_v=max_vector_score,
                min_v=self.settings.min_vector_score,
                docs=len(retrieved_chunks)
            )
            return LLMResult(
                answer="This assistant is designed only for US Tax & Legal documents. The requested information is outside the supported domain.",
                summary="Query rejected: Request is outside the supported domain.",
                citations=[],
                confidence_score=0.0
            )

        # Apply Confidence Constraint Check
        if self.settings.use_reranker:
            if max_rerank_score < self.settings.min_rerank_score:
                llm_log.warning(
                    "Query rejected (Low Rerank Confidence) | query={q} | max_rerank_score={m_r:.4f} (min={min_r:.4f})",
                    q=clean_query[:80],
                    m_r=max_rerank_score,
                    min_r=self.settings.min_rerank_score
                )
                return LLMResult(
                    answer="Information not found in the provided legal documents.",
                    summary="Query rejected: Low retrieval confidence.",
                    citations=[],
                    confidence_score=0.0
                )
        else:
            if max_hybrid_score < self.settings.min_hybrid_score:
                llm_log.warning(
                    "Query rejected (Low Hybrid Confidence) | query={q} | max_hybrid_score={m_h:.4f} (min={min_h:.4f})",
                    q=clean_query[:80],
                    m_h=max_hybrid_score,
                    min_h=self.settings.min_hybrid_score
                )
                return LLMResult(
                    answer="Information not found in the provided legal documents.",
                    summary="Query rejected: Low retrieval confidence.",
                    citations=[],
                    confidence_score=0.0
                )

        # Step 2 — Context presence check (Anti-hallucination shield)
        if not check_context_presence(retrieved_chunks):
            llm_log.warning("Empty context provided — bypassing LLM API request")
            return get_empty_context_result()

        # Step 3 — Build prompts using memory buffer
        chat_history_str = self.memory.get_history_string()
        full_prompt = PromptBuilder.build_qa_prompt(
            query=clean_query,
            chunks=retrieved_chunks,
            chat_history=chat_history_str,
        )

        # Step 4 — Execute generation call against active provider
        try:
            t0 = time.perf_counter()
            raw_response = await self.provider.generate(full_prompt)
            latency_ms = (time.perf_counter() - t0) * 1000

            # Step 5 — Parse and format results
            result = ResponseFormatter.parse_response(raw_response, retrieved_chunks)

            # Step 6 — Memory updates (Only save if a valid factual answer was produced)
            is_fallback = "information not found" in result.answer.lower()
            if not is_fallback:
                self.memory.add_exchange(clean_query, result.answer)
                # Persist the updated memory window to repository storage
                self.repository.save_messages(self.memory.get_messages())

            elapsed_total = (time.perf_counter() - start_time) * 1000
            llm_log.info(
                "QA pipeline complete | latency={total:.1f}ms | api_time={api:.1f}ms | conf={conf}",
                total=elapsed_total,
                api=latency_ms,
                conf=result.confidence_score,
            )
            return result

        except LLMError as exc:
            provider_name = exc.detail.get("provider", "unknown") if isinstance(exc.detail, dict) else "unknown"
            llm_log.error("LLM Generation call failed | provider={prov} | error={err}", prov=provider_name, err=str(exc))
            raise

        except Exception as exc:
            llm_log.error("Unexpected error in LLM service | error={err}", err=str(exc))
            raise LLMError(f"Unexpected error in LLM pipeline: {exc}", provider="service")

    def clear_memory(self) -> None:
        """Clears both runtime and persistent memory states."""
        self.memory.clear()
        self.repository.clear()
        llm_log.info("Cleared all conversation history memory states")
