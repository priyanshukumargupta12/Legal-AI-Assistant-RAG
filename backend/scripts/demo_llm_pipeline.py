"""
scripts/demo_llm_pipeline.py
==============================
Demonstration script for the LLM Module and full RAG pipeline.

PURPOSE:
    Demonstrates:
        1. Preprocessing and validating a user question.
        2. Performing Hybrid Retrieval (vector + BM25) to get relevant chunks.
        3. Formulating the system and user prompts using prompt builders.
        4. Interfacing with Google Gemini (with graceful mock fallback if no API key is set).
        5. Cleaning and parsing the response into a structured JSON schema.
        6. Preserving conversation history in memory.

USAGE:
    From the backend directory:
        python scripts/demo_llm_pipeline.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

# Fix Windows terminal encoding for special characters
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

# Ensure backend root is on the Python path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.elasticsearch.elastic_client import get_elasticsearch_client
from app.elasticsearch.elastic_repository import ElasticsearchRepository
from app.embeddings.embedder import BGEEmbedder
from app.retrieval.hybrid_ranker import WeightedRankFuser
from app.retrieval.retrieval_repository import HybridRetrievalRepository
from app.retrieval.retrieval_service import HybridRetrievalService
from app.llm.base_provider import LLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.conversation_memory import ConversationHistoryMemory
from app.llm.llm_repository import ConversationHistoryRepository
from app.llm.llm_service import LLMService
from app.llm.prompt_builder import PromptBuilder
from app.vectorstore import get_qdrant_client, QdrantRepository



# ── Mock LLM Provider for safe execution out-of-the-box ──────────────────────


class MockGeminiProvider(LLMProvider):
    """
    Mock LLM provider used when no valid Gemini API key is configured.
    Ensures the pipeline is fully testable and runnable without API key crashes.
    """

    async def generate(self, prompt: str) -> str:
        # Simulate API network delay
        await asyncio.sleep(1.0)

        # Realistic response corresponding to "What is the Child Tax Credit?"
        mock_data = {
            "answer": (
                "The Child Tax Credit is a federal benefit that allows qualified taxpayers "
                "to claim a credit for each qualifying child. Under IRS Publication 3, page 18, "
                "this credit is listed alongside other credits like the excess social security "
                "tax withholding. Generally, if a child meets the qualifying rules, only one "
                "taxpayer can claim the child as a qualifying child for the credit, as outlined "
                "in IRS Publication 501, page 15, and IRS Publication 17, page 32."
            ),
            "summary": (
                "The Child Tax Credit reduces tax liability for qualifying children, "
                "documented in IRS Publications 3, 17, and 501."
            ),
            "citations": [
                {
                    "document": "IRS_Publication_3.pdf",
                    "page": 18,
                    "category": "Tax"
                },
                {
                    "document": "IRS_Publication_501.pdf",
                    "page": 15,
                    "category": "Tax"
                },
                {
                    "document": "IRS_Publication_17.pdf",
                    "page": 32,
                    "category": "Tax"
                }
            ],
            "confidence_score": 0.94
        }
        return json.dumps(mock_data)

    async def health_check(self) -> bool:
        return True


# ── Execution ──────────────────────────────────────────────────────────────────


async def main() -> None:
    settings = get_settings()

    print("=" * 80)
    print("         END-TO-END RAG LLM PIPELINE DEMONSTRATION")
    print("=" * 80)

    # 1. Initialize Hybrid Retrieval
    print("\n[STEP 1] Loading Hybrid Retrieval Services...")
    qdrant_client = get_qdrant_client(settings)
    vector_repo = QdrantRepository(client=qdrant_client, settings=settings)

    es_client = get_elasticsearch_client(settings)
    keyword_repo = ElasticsearchRepository(client=es_client, settings=settings)

    retrieval_repo = HybridRetrievalRepository(
        vector_repo=vector_repo,
        keyword_repo=keyword_repo,
        timeout_s=settings.retrieval_timeout_s,
    )

    embedder = BGEEmbedder(
        model_name=settings.embedding_model_name,
        cache_dir=settings.embedding_cache_dir,
    )

    fuser = WeightedRankFuser(
        vector_weight=settings.vector_weight,
        bm25_weight=settings.bm25_weight,
    )

    retrieval_service = HybridRetrievalService(
        repository=retrieval_repo,
        embedder=embedder,
        fuser=fuser,
        retrieval_top_k=settings.retrieval_top_k,
        final_top_k=settings.retrieval_final_top_k,
    )

    # 2. Wire up LLM provider (real or mock fallback)
    print("\n[STEP 2] Wiring LLM provider...")
    api_key = settings.gemini_api_key
    is_real = api_key and "<YOUR" not in api_key and api_key.strip() != ""

    if is_real:
        print("  Active: Real ChatGoogleGenerativeAI (Gemini) [OK]")
        provider = GeminiProvider(settings)
    else:
        print("  [WARNING] GEMINI_API_KEY is placeholder or empty in .env.")
        print("  Active: MockGeminiProvider (Simulated fallback) [OK]")
        provider = MockGeminiProvider()

    # Create memory & repository
    memory = ConversationHistoryMemory(max_history=10)
    repository = ConversationHistoryRepository(settings)

    # Wipe any previous demo records to ensure clean slate
    repository.clear()

    llm_service = LLMService(
        provider=provider,
        repository=repository,
        memory=memory,
        settings=settings,
    )

    # 3. Fire Question 1 (RAG Search)
    question = "What is the Child Tax Credit?"
    print(f"\n[STEP 3] User asks: '{question}'")
    print("  Executing Hybrid Retrieval (Qdrant + Elasticsearch)...")

    retrieval_result = await retrieval_service.retrieve(
        raw_query=question,
        final_top_k=5,
    )

    print(f"  Retrieved {len(retrieval_result.results)} relevant document chunks.")

    # 4. Generate QA response via LLM service
    print("\n[STEP 4] Constructing prompt and generating answer...")
    print("  Enforcing strict context boundaries & anti-hallucination templates...")

    llm_result = await llm_service.answer_question(
        raw_query=question,
        retrieved_chunks=retrieval_result.results,
    )

    # 5. Output structured JSON response
    print("\n[STEP 5] Fused Structured Response Output:")
    print("=" * 80)
    output_dict = {
        "query": question,
        "results": [
            {
                "answer": llm_result.answer,
                "summary": llm_result.summary,
                "citations": [
                    {
                        "document": c.document,
                        "page": c.page,
                        "category": c.category
                    }
                    for c in llm_result.citations
                ],
                "confidence_score": llm_result.confidence_score
            }
        ]
    }
    print(json.dumps(output_dict, indent=2))
    print("=" * 80)

    # 6. Verify Conversation memory
    print("\n[STEP 6] Checking Conversation Memory buffer...")
    history_str = memory.get_history_string()
    print("  Active chat history buffer:")
    print("-" * 50)
    print(history_str)
    print("-" * 50)

    print("\n[OK] LLM Module pipeline test complete.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
