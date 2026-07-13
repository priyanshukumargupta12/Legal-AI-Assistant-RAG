"""
app/llm/prompt_builder.py
==========================
Constructs formatted prompts for the LLM pipeline.

PURPOSE:
    Formats context chunks, conversation history, and query inputs into completed prompts
    based on predefined system and user templates.
"""

from __future__ import annotations

from typing import List
from app.models.document import RetrievedChunk
from app.retrieval.retrieval_models import FusionCandidate
from app.llm.prompt_templates.system_prompt import SYSTEM_PROMPT
from app.llm.prompt_templates.qa_prompt import QA_PROMPT_TEMPLATE
from app.llm.prompt_templates.summary_prompt import SUMMARY_PROMPT_TEMPLATE
from app.llm.prompt_templates.verification_prompt import VERIFICATION_PROMPT_TEMPLATE


class PromptBuilder:
    """Builder for constructing LLM prompt strings."""

    @staticmethod
    def build_context_text(chunks: List[FusionCandidate] | List[RetrievedChunk]) -> str:
        """
        Formats a list of retrieved chunks into a standardized text block.

        Format:
            [Document: document_name | Page: page_number | Category: category]
            Text: ...
        """
        if not chunks:
            return "No document context chunks provided."

        formatted_chunks = []
        for idx, chunk in enumerate(chunks, start=1):
            doc_name = getattr(chunk, "document_name", getattr(chunk, "document", ""))
            page = getattr(chunk, "page_number", getattr(chunk, "page", 1))
            cat = chunk.category
            text = getattr(chunk, "text", getattr(chunk, "chunk_text", ""))

            header = f"Chunk #{idx} | Document: {doc_name} | Page: {page} | Category: {cat}"
            formatted_chunks.append(f"{header}\nText: {text.strip()}")

        return "\n\n".join(formatted_chunks)

    @classmethod
    def build_qa_prompt(
        cls,
        query: str,
        chunks: List[FusionCandidate] | List[RetrievedChunk],
        chat_history: str = "",  # Kept for signature compatibility but intentionally unused
    ) -> str:
        """Constructs the full system instructions + user input QA prompt.
        
        Note: chat_history is intentionally NOT injected into the prompt to prevent
        Gemini from using parametric memory or prior answers as a source of facts.
        """
        context_text = cls.build_context_text(chunks)
        user_prompt = QA_PROMPT_TEMPLATE.format(
            context_text=context_text,
            query=query,
        )
        return f"{SYSTEM_PROMPT}\n\n{user_prompt}"

    @staticmethod
    def build_summary_prompt(answer: str) -> str:
        """Constructs prompt for standalone summarization if needed."""
        return SUMMARY_PROMPT_TEMPLATE.format(answer_text=answer)

    @classmethod
    def build_verification_prompt(
        cls,
        answer: str,
        chunks: List[FusionCandidate] | List[RetrievedChunk],
    ) -> str:
        """Constructs prompt for grounding verification."""
        context_text = cls.build_context_text(chunks)
        return VERIFICATION_PROMPT_TEMPLATE.format(
            context_text=context_text,
            answer_text=answer,
        )
