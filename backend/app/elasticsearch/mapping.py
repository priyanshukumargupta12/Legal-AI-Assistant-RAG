"""
app/elasticsearch/mapping.py
=============================
Elasticsearch index mapping and custom analyzer definitions.

PURPOSE:
    Defines the legal-document-optimised index mapping that is applied when
    the ``legal_documents`` index is created. Encapsulates all field type
    definitions, custom analyzers, and index settings in one place so that
    index schema changes only ever require editing this file.

CUSTOM LEGAL ANALYZER — WHY?
------------------------------
The built-in ``english`` analyzer:
  - Performs aggressive stemming (good for general text).
  - Does NOT preserve legal codes such as ``§ 401(k)`` or ``IRC-162``.
  - Strips punctuation, losing structural tokens important in legal search.

The ``legal_analyzer`` defined here:
  - Uses ``standard`` tokenizer (unicode-aware, splits on whitespace + punct).
  - Adds a ``lowercase`` filter for case-insensitive matching.
  - Applies a ``word_delimiter_graph`` filter to split hyphenated codes while
    preserving the original form (e.g. ``IRC-162`` becomes ``IRC``, ``162``,
    AND ``IRC-162``).
  - Applies ``english`` stemming so plurals/conjugations still match.
  - Applies ``english`` stop-words removal to strip noise words.

FIELD DECISIONS:
    chunk_text     — full-text BM25, analyzed with legal_analyzer
    document_name  — full-text + keyword sub-field for exact sort/filter
    category       — keyword (exact enum values, not free text)
    document_id    — keyword (UUID, no tokenization)
    chunk_id       — keyword (UUID, used as _id)
    page_number    — integer (range queries)
    chunk_index    — integer (ordering within document)
    source         — keyword (always "keyword")
    indexed_at     — date (temporal queries)
    metadata       — object (dynamic, preserved as-is)
"""

from __future__ import annotations

# ── Index Settings ─────────────────────────────────────────────────────────────

ELASTICSEARCH_INDEX_SETTINGS: dict = {
    "settings": {
        # Number of primary shards — 1 is optimal for a single-node setup
        # and Elastic Cloud deployments up to ~50 GB.
        "number_of_shards": 1,
        "number_of_replicas": 1,
        # Refresh interval: how often Elasticsearch makes new documents
        # searchable. Increase for bulk indexing, decrease for real-time search.
        # Overridden at runtime by settings.elasticsearch_refresh_interval.
        "refresh_interval": "30s",
        "analysis": {
            "analyzer": {
                # ── Custom legal text analyser ─────────────────────────────
                "legal_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "legal_word_delimiter",
                        "english_stop",
                        "english_stemmer",
                    ],
                },
                # ── Exact search analyser (no stemming) ───────────────────
                # Used for exact phrase searches. Lowercase only.
                "legal_exact_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "legal_word_delimiter",
                    ],
                },
            },
            "filter": {
                # Splits hyphenated tokens but preserves originals.
                # IRC-162 → [IRC, 162, IRC-162]
                "legal_word_delimiter": {
                    "type": "word_delimiter_graph",
                    "preserve_original": True,
                    "catenate_words": True,
                    "catenate_numbers": True,
                    "split_on_numerics": False,
                    "stem_english_possessive": True,
                },
                "english_stop": {
                    "type": "stop",
                    "stopwords": "_english_",
                },
                "english_stemmer": {
                    "type": "stemmer",
                    "language": "english",
                },
            },
        },
    },
    # ── Index Mapping ──────────────────────────────────────────────────────────
    "mappings": {
        "dynamic": "strict",   # Reject unknown fields to prevent mapping explosions
        "properties": {
            # Primary identifier — use chunk_id as Elasticsearch _id
            "chunk_id": {
                "type": "keyword",
            },
            # Parent document UUID — used for document-level filter queries
            "document_id": {
                "type": "keyword",
            },
            # Human-readable document filename
            "document_name": {
                "type": "text",
                "analyzer": "legal_analyzer",
                "fields": {
                    "keyword": {
                        "type": "keyword",   # Exact match / sort / aggregation
                        "ignore_above": 512,
                    }
                },
            },
            # Category enum — always exact filter, never free text
            "category": {
                "type": "keyword",
            },
            # Source page number — numeric range queries
            "page_number": {
                "type": "integer",
            },
            # Position within the document
            "chunk_index": {
                "type": "integer",
            },
            # ── Primary BM25 search field ──────────────────────────────────
            # chunk_text is the field that BM25 operates on.
            # We store two analysis forms:
            #   chunk_text         — stemmed (default BM25)
            #   chunk_text.exact   — no stemming (for phrase / exact queries)
            "chunk_text": {
                "type": "text",
                "analyzer": "legal_analyzer",
                "search_analyzer": "legal_analyzer",
                "fields": {
                    "exact": {
                        "type": "text",
                        "analyzer": "legal_exact_analyzer",
                    }
                },
            },
            # Retrieval source tag
            "source": {
                "type": "keyword",
            },
            # UTC timestamp of when the document was indexed
            "indexed_at": {
                "type": "date",
            },
            # Arbitrary metadata preserved from the chunking phase
            "metadata": {
                "type": "object",
                "dynamic": True,   # Allow nested metadata keys
            },
        },
    },
}
