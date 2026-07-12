"""
app/pdf_parser/parser_repository.py
====================================
Repository interface and implementation for PDF parsing.

PURPOSE:
    Provides methods to load document metadata from documents.csv
    and save parsed output JSON summary or LangChain Document objects.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from langchain_core.documents import Document

from app.core.exceptions import DatasetScanError
from app.pdf_parser.parser_models import ParsedDocument


class ParserRepository(ABC):
    """Abstract interface for parser operations persistence."""

    @abstractmethod
    def load_registry_csv(self, csv_path: Path) -> List[Dict]:
        """
        Load Document Records from the generated documents.csv registry.

        Returns:
            List of dictionaries, each matching a DocumentRecord row.
        """
        ...

    @abstractmethod
    def save_parsed_json(self, parsed_doc: ParsedDocument, output_path: Path) -> Path:
        """
        Persist a ParsedDocument into a structured JSON file.
        """
        ...


class FileSystemParserRepository(ParserRepository):
    """File-system implementation of ParserRepository."""

    def load_registry_csv(self, csv_path: Path) -> List[Dict]:
        if not csv_path.exists():
            raise FileNotFoundError(f"Documents registry not found at '{csv_path}'.")
        try:
            df = pd.read_csv(csv_path)
            return df.to_dict("records")
        except Exception as exc:
            raise DatasetScanError(
                message=f"Failed to load registry CSV: {exc}",
                detail={"path": str(csv_path)},
            ) from exc

    def save_parsed_json(self, parsed_doc: ParsedDocument, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "document_id": parsed_doc.document_id,
            "document_name": parsed_doc.document_name,
            "category": parsed_doc.category,
            "pages": [
                {"page": p.page_number, "text": p.text}
                for p in parsed_doc.pages
            ]
        }
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return output_path
        except Exception as exc:
            raise IOError(f"Failed to write parsed JSON to '{output_path}': {exc}") from exc
