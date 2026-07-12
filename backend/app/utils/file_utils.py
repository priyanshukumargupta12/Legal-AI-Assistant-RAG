"""
utils/file_utils.py
====================
File system utility functions.

PURPOSE:
    Pure functions for file operations used across the application.
    No side effects beyond file I/O.

SOLID: Single Responsibility — file system helpers only.
DRY:   Centralized; called by DatasetScanner, PDFParser, and importers.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def compute_md5(file_path: str | Path, chunk_size: int = 8192) -> str:
    """
    Compute MD5 checksum of a file for duplicate detection.

    Args:
        file_path:  Path to the file.
        chunk_size: Read buffer size in bytes.

    Returns:
        Lowercase hexadecimal MD5 hash string.

    Raises:
        FileNotFoundError: If file_path does not exist.
        IOError: If the file cannot be read.
    """
    # TODO: Implement in Milestone 1
    ...


def ensure_directory(path: str | Path) -> Path:
    """
    Create a directory and all parents if they do not exist.

    Args:
        path: Directory path to create.

    Returns:
        Resolved absolute Path object.
    """
    # TODO: Implement in Milestone 1
    ...


def get_file_size_bytes(file_path: str | Path) -> int:
    """
    Return file size in bytes.

    Args:
        file_path: Path to the file.

    Returns:
        File size in bytes.

    Raises:
        FileNotFoundError: If file_path does not exist.
    """
    # TODO: Implement in Milestone 1
    ...


def is_pdf_file(file_path: str | Path) -> bool:
    """
    Check if a file has .pdf extension (case-insensitive).

    Args:
        file_path: Path to check.

    Returns:
        True if the file extension is .pdf.
    """
    return Path(file_path).suffix.lower() == ".pdf"
