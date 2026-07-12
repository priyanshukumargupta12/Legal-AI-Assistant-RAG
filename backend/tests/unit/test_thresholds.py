import pytest
from unittest.mock import AsyncMock, MagicMock
from app.llm.llm_service import LLMService
from app.core.config import Settings
from app.llm.llm_models import LLMResult, Citation
from app.retrieval.retrieval_models import FusionCandidate

# A dummy implementation of LLMProvider
class DummyLLMProvider:
    def __init__(self):
        self.generate_called = False
        self.generate_mock = AsyncMock(return_value='{"answer": "A valid grounded answer", "summary": "Summary", "citations": []}')

    async def generate(self, prompt: str) -> str:
        self.generate_called = True
        return await self.generate_mock(prompt)

    async def health_check(self) -> bool:
        return True

# Dummy Repository
class DummyHistoryRepository:
    def load_messages(self):
        return []
    def save_messages(self, messages):
        pass
    def clear(self):
        pass

# Dummy Memory
class DummyHistoryMemory:
    def __init__(self):
        self.exchanges = []
    def add_exchange(self, question, answer):
        self.exchanges.append((question, answer))
    def get_history_string(self):
        return "No prior exchanges."
    def get_messages(self):
        return []
    def clear(self):
        self.exchanges = []


@pytest.fixture
def base_settings():
    return Settings(
        min_vector_score=0.35,
        min_rerank_score=0.0,
        min_hybrid_score=0.005,
        use_reranker=False,
        gemini_api_key="dummy_key",
        secret_key="dummy_secret"
    )


@pytest.mark.asyncio
async def test_out_of_domain_no_chunks(base_settings):
    provider = DummyLLMProvider()
    service = LLMService(
        provider=provider,
        repository=DummyHistoryRepository(),
        memory=DummyHistoryMemory(),
        settings=base_settings
    )

    result = await service.answer_question(
        raw_query="How do I cook lasagna?",
        retrieved_chunks=[]
    )

    assert result.answer == "This assistant is designed only for US Tax & Legal documents. The requested information is outside the supported domain."
    assert not provider.generate_called


@pytest.mark.asyncio
async def test_out_of_domain_low_vector_score(base_settings):
    provider = DummyLLMProvider()
    service = LLMService(
        provider=provider,
        repository=DummyHistoryRepository(),
        memory=DummyHistoryMemory(),
        settings=base_settings
    )

    # Chunks exist but all have vector_score below 0.35
    chunks = [
        FusionCandidate(
            chunk_id="chunk_1",
            document_id="doc_1",
            document_name="doc_1.pdf",
            category="Acts",
            page_number=1,
            chunk_index=0,
            text="Random lasagna recipe text",
            vector_score=0.25,
            hybrid_score=0.008
        )
    ]

    result = await service.answer_question(
        raw_query="How do I cook lasagna?",
        retrieved_chunks=chunks
    )

    assert result.answer == "This assistant is designed only for US Tax & Legal documents. The requested information is outside the supported domain."
    assert not provider.generate_called


@pytest.mark.asyncio
async def test_low_confidence_hybrid(base_settings):
    provider = DummyLLMProvider()
    service = LLMService(
        provider=provider,
        repository=DummyHistoryRepository(),
        memory=DummyHistoryMemory(),
        settings=base_settings
    )

    # Vector score exceeds threshold (0.4 > 0.35)
    # But hybrid score is below 0.005
    chunks = [
        FusionCandidate(
            chunk_id="chunk_1",
            document_id="doc_1",
            document_name="doc_1.pdf",
            category="Acts",
            page_number=1,
            chunk_index=0,
            text="Vague tax reference",
            vector_score=0.4,
            hybrid_score=0.002
        )
    ]

    result = await service.answer_question(
        raw_query="Vague tax query?",
        retrieved_chunks=chunks
    )

    assert result.answer == "Information not found in the provided legal documents."
    assert not provider.generate_called


@pytest.mark.asyncio
async def test_low_confidence_rerank(base_settings):
    base_settings.use_reranker = True
    base_settings.min_rerank_score = 0.5
    provider = DummyLLMProvider()
    service = LLMService(
        provider=provider,
        repository=DummyHistoryRepository(),
        memory=DummyHistoryMemory(),
        settings=base_settings
    )

    # Vector score exceeds threshold (0.4 > 0.35)
    # But rerank score (which uses hybrid_score) is below min_rerank_score (0.1 < 0.5)
    chunks = [
        FusionCandidate(
            chunk_id="chunk_1",
            document_id="doc_1",
            document_name="doc_1.pdf",
            category="Acts",
            page_number=1,
            chunk_index=0,
            text="Tax reference",
            vector_score=0.4,
            hybrid_score=0.1
        )
    ]

    result = await service.answer_question(
        raw_query="Vague tax query?",
        retrieved_chunks=chunks
    )

    assert result.answer == "Information not found in the provided legal documents."
    assert not provider.generate_called


@pytest.mark.asyncio
async def test_successful_query(base_settings):
    provider = DummyLLMProvider()
    service = LLMService(
        provider=provider,
        repository=DummyHistoryRepository(),
        memory=DummyHistoryMemory(),
        settings=base_settings
    )

    # Vector score (0.5 > 0.35) and hybrid score (0.01 > 0.005) exceed thresholds
    chunks = [
        FusionCandidate(
            chunk_id="chunk_1",
            document_id="doc_1",
            document_name="doc_1.pdf",
            category="Acts",
            page_number=1,
            chunk_index=0,
            text="Legitimate tax information about filing deadlines",
            vector_score=0.5,
            hybrid_score=0.01
        )
    ]

    result = await service.answer_question(
        raw_query="What is the filing deadline?",
        retrieved_chunks=chunks
    )

    assert result.answer == "A valid grounded answer"
    assert provider.generate_called
