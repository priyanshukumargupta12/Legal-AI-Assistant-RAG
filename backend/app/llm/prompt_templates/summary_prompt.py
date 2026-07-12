"""
app/llm/prompt_templates/summary_prompt.py
===========================================
Prompt template for generating summaries.

PURPOSE:
    Instructs the LLM on how to summarize a legal answer, ensuring it does not add any information
    outside the source answer and respects the 150-word limit.
"""

SUMMARY_PROMPT_TEMPLATE = """
LEGAL RESPONSE TO SUMMARIZE:
=========================================
{answer_text}
=========================================

Instructions:
1. Summarize the answer above in a concise and clear manner.
2. The summary must be under 150 words.
3. Do NOT include any facts, details, or assumptions that are not explicitly stated in the response above.
4. Output only the summarized text, no headers or outer quotes.
"""
