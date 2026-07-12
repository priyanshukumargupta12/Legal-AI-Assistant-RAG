"""
utils/security_utils.py
========================
Input sanitization and prompt injection protection utilities.

PURPOSE:
    Detects and neutralizes prompt injection attempts in user queries.
    Applied by QueryService before any user text is included in LLM prompts.

DESIGN:
    - Regex-based pattern matching for common injection patterns
    - Raises PromptInjectionError on detection
    - sanitize_input() is the single entry point

SOLID: Single Responsibility — security input processing only.
"""

from __future__ import annotations

import re
from typing import Final

# Patterns that indicate prompt injection attempts
INJECTION_PATTERNS: Final[list[str]] = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"forget\s+(all\s+)?previous\s+instructions",
    r"you\s+are\s+now\s+(a\s+)?",
    r"act\s+as\s+(if\s+you\s+are\s+)?",
    r"disregard\s+(all\s+)?previous",
    r"new\s+system\s+prompt",
    r"</?(system|user|assistant)>",
    r"\[INST\]|\[/INST\]",
    r"<\|im_start\|>|<\|im_end\|>",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def detect_prompt_injection(text: str) -> bool:
    """
    Check if text contains known prompt injection patterns.

    Args:
        text: User input text to analyze.

    Returns:
        True if injection is detected, False otherwise.
    """
    # TODO: Implement in Milestone 15 (Security + Hardening)
    ...


def sanitize_input(text: str) -> str:
    """
    Sanitize user input by stripping leading/trailing whitespace
    and checking for injection patterns.

    Args:
        text: Raw user input.

    Returns:
        Sanitized text.

    Raises:
        PromptInjectionError: If injection patterns are detected.
    """
    # TODO: Implement in Milestone 15 (Security + Hardening)
    ...
