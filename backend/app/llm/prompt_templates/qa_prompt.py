"""
app/llm/prompt_templates/qa_prompt.py
======================================
Prompt template for the core Legal Question-Answering step.

PURPOSE:
    Formats context chunks and user question.
    Conversation history is intentionally excluded to prevent Gemini from
    using parametric memory or prior answers as a source of facts.
"""

QA_PROMPT_TEMPLATE = """
RETRIEVED DOCUMENT EXCERPTS — THE ONLY PERMITTED SOURCE FOR YOUR ANSWER:
=========================================
{context_text}
=========================================

TASK: Answer the USER QUESTION below using ONLY the above document excerpts.
- Every single fact, name, number, and legal finding in your answer MUST come from the excerpts above.
- Do NOT use any knowledge from your training data, memory, or prior conversation.
- If the excerpts do not contain the answer, respond with exactly: "Information not found in the provided legal documents."

USER QUESTION: {query}

Generate your response in the required JSON format:
"""
