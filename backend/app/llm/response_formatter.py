"""
app/llm/response_formatter.py
==============================
Parses and normalizes raw LLM responses.

PURPOSE:
    Extracts JSON payloads from LLM outputs, cleans formatting anomalies,
    computes deterministic confidence scores based on retrieval metrics,
    and constructs validated LLMResult entities.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List
from app.llm.llm_logger import llm_log
from app.llm.llm_models import Citation, LLMResult
from app.retrieval.retrieval_models import FusionCandidate


class ResponseFormatter:
    """Formatter to clean and parse the raw LLM responses."""

    @staticmethod
    def clean_json_string(raw: str) -> str:
        """
        Cleans markdown wrappers and extra text from the LLM output.
        E.g., ```json ... ``` or whitespace.
        """
        cleaned = raw.strip()
        # Remove leading/trailing markdown blocks
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    @classmethod
    def parse_response(
        cls,
        raw_response: str,
        retrieved_chunks: List[FusionCandidate],
    ) -> LLMResult:
        """
        Parse raw JSON string from LLM into a validated LLMResult.

        If parsing fails, generates a safe error-state LLMResult.
        """
        cleaned = cls.clean_json_string(raw_response)
        try:
            data = json.loads(cleaned)
            answer = data.get("answer", "").strip()
            summary = data.get("summary", "").strip()

            # Process citations
            citations: List[Citation] = []
            raw_cits = data.get("citations", [])
            for c in raw_cits:
                if isinstance(c, dict) and "document" in c and "page" in c:
                    doc_name = c.get("document", "")
                    page_num = int(c.get("page", 1))
                    
                    # Try to find a matching snippet from the retrieved chunks
                    matched_snippet = None
                    for chunk in retrieved_chunks:
                        chunk_doc = getattr(chunk, "document_name", getattr(chunk, "document", ""))
                        chunk_page = getattr(chunk, "page_number", getattr(chunk, "page", 1))
                        if chunk_doc.lower() == doc_name.lower() and int(chunk_page) == page_num:
                            matched_snippet = getattr(chunk, "text", getattr(chunk, "chunk_text", ""))
                            break
                            
                    citations.append(
                        Citation(
                            document=doc_name,
                            page=page_num,
                            category=c.get("category", "Tax"),
                            snippet=matched_snippet,
                        )
                    )

            # Compute programmatic confidence score to avoid LLM self-hallucination
            conf = cls.calculate_confidence(retrieved_chunks, citations)

            return LLMResult(
                answer=answer,
                summary=summary,
                citations=citations,
                confidence_score=conf,
            )

        except Exception as exc:
            llm_log.error("Failed to parse LLM response JSON | error={err}", err=str(exc))
            # Safe fallback response
            return LLMResult(
                answer="Information not found in the provided legal documents.",
                summary="Insufficient information available to process request.",
                citations=[],
                confidence_score=0.0,
            )

    @staticmethod
    def calculate_confidence(
        retrieved_chunks: List[FusionCandidate],
        citations: List[Citation],
    ) -> float:
        """
        Calculate confidence score dynamically based on retrieval quality.

        Formula elements:
            1. Average hybrid score of top chunks.
            2. Ratio of cited documents to retrieved documents (coverage).
            3. Min supporting chunks count (penalizes single-chunk source answers).
        """
        if not retrieved_chunks:
            return 0.0

        # 1. Average hybrid score (Weighted Rank Fusion produces scores in range [0, 1])
        avg_score = sum(c.hybrid_score for c in retrieved_chunks) / len(retrieved_chunks)

        # 2. Context coverage (how many of our retrieved chunks matched the citation list by name)
        cited_docs = {c.document.lower() for c in citations}
        retrieved_docs = {getattr(c, "document_name", "").lower() for c in retrieved_chunks}
        retrieved_docs.discard("")

        if retrieved_docs:
            coverage = len(cited_docs.intersection(retrieved_docs)) / len(retrieved_docs)
        else:
            coverage = 0.0

        # 3. Quantity factor (reward multiple supporting sources, up to 5)
        quantity_factor = min(len(citations) / 3.0, 1.0) if citations else 0.0

        # Combine metrics with safe defaults (Weights: 50% retriever score, 30% coverage, 20% quantity)
        raw_conf = (0.5 * avg_score) + (0.3 * coverage) + (0.2 * quantity_factor)

        # Clamp between 0.0 and 1.0
        return float(max(0.0, min(1.0, round(raw_conf, 2))))
