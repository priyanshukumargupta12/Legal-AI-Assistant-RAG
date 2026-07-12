"""
scripts/generate_golden_set.py
==============================
CLI runner for the Golden Set Generator pipeline.

USAGE:
    From the backend directory:
        python scripts/generate_golden_set.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Fix Windows terminal encoding for special characters
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

# Ensure backend root is on the Python path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.llm.gemini_provider import GeminiProvider
from app.evaluation.golden_set_generator import GoldenSetGenerator
from app.logging.logger import configure_logging, get_logger

log = get_logger("evaluation")


async def main() -> None:
    # 1. Configure standard logger settings (sinks, etc.)
    configure_logging()
    
    settings = get_settings()
    log.info("Loaded application configuration.")

    # 2. Wire up LLM provider
    provider = GeminiProvider(settings)

    # 3. Instantiate generator and execute
    generator = GoldenSetGenerator(
        settings=settings,
        llm_provider=provider,
        workspace_dir=BACKEND_ROOT.parent
    )

    try:
        count = await generator.generate_golden_set()
        log.info("Golden Set generation completed successfully. Total records: {n}", n=count)
    except Exception as exc:
        log.exception("Golden Set Generator execution failed.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
