"""
app/llm/prompt_templates/qa_prompt.py
======================================
Prompt template for the core Legal Question-Answering step.

PURPOSE:
    Formats context chunks, conversation history, and user question.
"""

QA_PROMPT_TEMPLATE = """
DOCUMENT CONTEXT CHUNKS:
=========================================
{context_text}
=========================================

CONVERSATION HISTORY:
=========================================
{chat_history}
=========================================

USER QUESTION: {query}

Generate your response in the required JSON format:
"""
