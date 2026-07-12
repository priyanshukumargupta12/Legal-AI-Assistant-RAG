"""
app/llm/prompt_templates/verification_prompt.py
================================================
Prompt template for verification/guardrails step.

PURPOSE:
    Verifies that the generated answer is strictly grounded in the context chunks and does
    not introduce hallucinations.
"""

VERIFICATION_PROMPT_TEMPLATE = """
DOCUMENT CONTEXT CHUNKS:
=========================================
{context_text}
=========================================

GENERATED ANSWER:
=========================================
{answer_text}
=========================================

Task:
Evaluate whether the GENERATED ANSWER contains any statements, assumptions, or citations that are NOT directly supported by the DOCUMENT CONTEXT CHUNKS.

Output a JSON response in the following format:
{
  "is_fully_grounded": true/false,
  "unsupported_sentences": ["sentence 1 containing hallucination", "sentence 2 containing hallucination"],
  "hallucination_detected": true/false
}
"""
