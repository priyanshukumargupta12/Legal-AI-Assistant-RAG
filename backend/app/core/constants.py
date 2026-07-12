"""
core/constants.py
=================
Application-wide constants.

PURPOSE:
    Centralizes all magic numbers, string literals, and enumerated values.
    Importing from this file is the ONLY way to use these values — never
    hardcode them in service or infrastructure files.

DESIGN:
    - Pure constants (no logic)
    - Grouped by subsystem
    - All names are UPPER_SNAKE_CASE per PEP 8 convention for constants

SOLID: Single Responsibility — only defines constants.
DRY:   Every constant defined once; referenced everywhere via import.
"""

from __future__ import annotations

# =============================================================================
# DOCUMENT CATEGORIES
# =============================================================================
# Valid category names — must match the dataset subdirectory names exactly.
CATEGORY_ACTS = "Acts"
CATEGORY_COURT_JUDGMENT = "CourtJudgement"
CATEGORY_TAX = "Tax"
CATEGORY_LEGAL_OPINION = "Legal_opinion"

# All valid categories as a tuple for validation
VALID_CATEGORIES: tuple[str, ...] = (
    CATEGORY_ACTS,
    CATEGORY_COURT_JUDGMENT,
    CATEGORY_TAX,
    CATEGORY_LEGAL_OPINION,
)

# Human-readable category display names
CATEGORY_DISPLAY_NAMES: dict[str, str] = {
    CATEGORY_ACTS: "Acts & Statutes",
    CATEGORY_COURT_JUDGMENT: "Court Judgments",
    CATEGORY_TAX: "Tax Documents",
    CATEGORY_LEGAL_OPINION: "Legal Opinions",
}

# =============================================================================
# QDRANT
# =============================================================================
QDRANT_VECTOR_SIZE = 384              # Output dimension of BAAI/bge-small-en-v1.5
QDRANT_DISTANCE_METRIC = "Cosine"    # Cosine distance for L2-normalized vectors
QDRANT_DEFAULT_COLLECTION = "legal_documents"

# Payload field names stored in Qdrant alongside each vector
QDRANT_PAYLOAD_CHUNK_ID = "chunk_id"
QDRANT_PAYLOAD_CHUNK_TEXT = "chunk_text"
QDRANT_PAYLOAD_DOCUMENT_ID = "document_id"
QDRANT_PAYLOAD_DOCUMENT_NAME = "document_name"
QDRANT_PAYLOAD_CATEGORY = "category"
QDRANT_PAYLOAD_PAGE_NUMBER = "page_number"
QDRANT_PAYLOAD_CHUNK_INDEX = "chunk_index"

# =============================================================================
# ELASTICSEARCH
# =============================================================================
ELASTICSEARCH_DEFAULT_INDEX = "legal_documents"
ELASTICSEARCH_ANALYZER = "english"   # Enables Porter stemming for legal text
ELASTICSEARCH_MAX_RESULT_WINDOW = 10_000

# Index mapping field names
ES_FIELD_CHUNK_ID = "chunk_id"
ES_FIELD_CHUNK_TEXT = "chunk_text"
ES_FIELD_DOCUMENT_ID = "document_id"
ES_FIELD_DOCUMENT_NAME = "document_name"
ES_FIELD_CATEGORY = "category"
ES_FIELD_PAGE_NUMBER = "page_number"
ES_FIELD_CHUNK_INDEX = "chunk_index"

# =============================================================================
# EMBEDDING
# =============================================================================
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_VECTOR_DIM = 384
EMBEDDING_BATCH_SIZE = 32

# Instruction prefix for query encoding (BGE retrieval tuning)
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

# =============================================================================
# CHUNKING
# =============================================================================
CHUNK_SIZE_CHARS = 1800          # ~512 tokens (1 token ≈ 3.5 chars)
CHUNK_OVERLAP_CHARS = 230        # ~64 tokens overlap
MIN_CHUNK_LENGTH = 50            # Discard chunks shorter than this

# Recursive split separators (tried in order)
CHUNK_SEPARATORS: list[str] = ["\n\n", "\n", ". ", " ", ""]

# =============================================================================
# RETRIEVAL
# =============================================================================
RETRIEVAL_TOP_K = 10             # Fetch top-10 from each retriever
RETRIEVAL_FINAL_TOP_K = 5        # Return top-5 after RRF merging
RRF_K_CONSTANT = 60              # RRF robustness parameter (standard default)
VECTOR_SCORE_THRESHOLD = 0.3     # Minimum cosine score (0–1)

# =============================================================================
# LLM
# =============================================================================
LLM_PROVIDER_GEMINI = "gemini"
LLM_PROVIDER_OPENAI = "openai"
LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY_SECONDS = 2.0

# Fallback answer when no relevant context is retrieved
NO_INFORMATION_RESPONSE = (
    "Information not found in the provided legal documents."
)

# =============================================================================
# PDF PARSING
# =============================================================================
PDF_EXTENSION = ".pdf"
MIN_PAGE_TEXT_LENGTH = 50        # Pages with fewer chars are skipped
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

# =============================================================================
# METADATA / DATASET
# =============================================================================
DOCUMENTS_CSV_FILENAME = "documents.csv"
DOCUMENTS_XLSX_FILENAME = "documents.xlsx"
GOLDEN_SET_CSV_FILENAME = "golden_set.csv"

# Required columns in the golden set CSV/Excel
GOLDEN_SET_REQUIRED_COLUMNS: tuple[str, ...] = (
    "question",
    "expected_answer",
    "relevant_doc",
    "relevant_page",
)

# documents.csv column names
DOCUMENTS_CSV_COLUMNS: list[str] = [
    "document_id",
    "file_name",
    "category",
    "file_path",
    "file_size_bytes",
    "page_count",
    "md5_hash",
    "status",
    "ingested_at",
]

# Valid document status values
DOC_STATUS_VALID = "valid"
DOC_STATUS_INVALID = "invalid"
DOC_STATUS_DUPLICATE = "duplicate"

# =============================================================================
# SEARCH HISTORY
# =============================================================================
SEARCH_HISTORY_MAX_ENTRIES = 1000

# =============================================================================
# API
# =============================================================================
API_V1_PREFIX = "/api/v1"
HEALTH_ENDPOINT = "/health"

# HTTP response messages
MSG_DOCUMENT_UPLOADED = "Document uploaded and indexed successfully."
MSG_INGESTION_STARTED = "Document ingestion pipeline started."
MSG_DATASET_SCANNED = "Dataset scan completed successfully."
MSG_EVALUATION_STARTED = "Evaluation pipeline started."
