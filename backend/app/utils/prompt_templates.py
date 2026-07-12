"""
utils/prompt_templates.py
==========================
All LLM prompt templates used in the application.

PURPOSE:
    Centralizes every prompt string used across LLM providers.
    Prompts are version-controlled here; no prompt strings embedded
    in service or infrastructure files.

DESIGN:
    - All templates are module-level string constants (uppercase names)
    - build_query_prompt() assembles the final prompt from template + context

SOLID: Single Responsibility — prompt management only.
DRY:   Single location for all prompt text.
"""

from __future__ import annotations

# ─── System Instruction ───────────────────────────────────────────────────────
LEGAL_QA_SYSTEM_PROMPT = """You are an expert AI legal assistant specializing in US Tax and Legal law.

CRITICAL RULES:
1. Answer ONLY using the provided context documents.
2. Do NOT add information from your training data.
3. Do NOT hallucinate, speculate, or infer beyond what is explicitly stated in the context.
4. If the answer cannot be found in the provided documents, respond exactly with:
   "Information not found in the provided legal documents."
5. Always include the source document name and page number in your citations.
6. Provide your response as valid JSON matching the specified output format.

OUTPUT FORMAT (respond with this exact JSON structure):
{
    "answer": "<detailed answer from context>",
    "summary": "<2-3 sentence plain language summary>",
    "citations": [
        {
            "document_name": "<filename>",
            "page_number": <integer>,
            "category": "<category>",
            "excerpt": "<short excerpt from the chunk>"
        }
    ],
    "confidence_score": <float between 0.0 and 1.0>
}"""

# ─── Context Block Template ───────────────────────────────────────────────────
CONTEXT_BLOCK_TEMPLATE = """[{rank}] Source: {document_name} | Category: {category} | Page: {page_number}
{chunk_text}
---"""

# ─── Query Template ───────────────────────────────────────────────────────────
QUERY_TEMPLATE = """CONTEXT DOCUMENTS:
{context_blocks}

QUESTION:
{question}

Provide your response strictly following the JSON output format specified in your instructions."""


def build_query_prompt(question: str, context_chunks: list) -> str:
    """
    Assemble the full LLM prompt from system instruction + context + question.

    Args:
        question:       Sanitized user question.
        context_chunks: List of RetrievedChunk objects (max 5).

    Returns:
        Complete formatted prompt string ready for LLM submission.
    """
    # TODO: Implement in Milestone 7 (LLM Providers)
    ...
