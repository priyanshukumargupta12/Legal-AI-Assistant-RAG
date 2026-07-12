"""
app/dataset/dataset_utils.py
==============================
Pure utility functions for the Dataset Management Module.

PURPOSE:
    Stateless helper functions used by DatasetService to extract
    file metadata, compute checksums, validate PDFs, and generate IDs.

    No class required — these are pure functions with no shared state.
    They can be tested in complete isolation without mocking.

FUNCTIONS:
    compute_sha256            — SHA256 hex digest of a file
    get_file_size_bytes       — file size via os.stat()
    get_file_timestamps       — (created_at, modified_at) via os.stat()
    get_pdf_page_count        — open PDF with PyMuPDF; return page count + validity
    generate_document_id      — deterministic UUID5 from sha256 + relative_path
    derive_title              — filename without extension, cleaned
    detect_category           — infer category from parent folder name
    is_pdf_by_extension       — check .pdf extension (case-insensitive)
    is_hidden_file            — detect OS hidden files (dot-prefix on Unix, hidden attr on Windows)
    get_relative_path         — compute path relative to dataset root
    format_size_human         — format bytes to human-readable string

SOLID: Single Responsibility — pure file-system and PDF metadata utilities.
DRY:   Centralized; called only from DatasetService (no duplication).
"""

from __future__ import annotations

import hashlib
import os
import platform
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from app.core.constants import (
    VALID_CATEGORIES,
    MIN_PAGE_TEXT_LENGTH,
    PDF_EXTENSION,
)
from app.dataset.dataset_logger import dataset_log


# =============================================================================
# CHECKSUM
# =============================================================================

def compute_sha256(file_path: Path, buffer_size: int = 65536) -> str:
    """
    Compute the SHA256 hex digest of a file.

    Reads the file in chunks to handle large PDFs without loading the
    entire file into memory at once.

    Args:
        file_path:   Path to the file to hash.
        buffer_size: Read buffer size in bytes (default: 64 KB).

    Returns:
        Lowercase hexadecimal SHA256 digest string (64 characters).

    Raises:
        FileNotFoundError: If file_path does not exist.
        PermissionError:   If the file cannot be read.
        OSError:           If an OS-level I/O error occurs.

    Example:
        >>> compute_sha256(Path("dataset/Acts/TaxAct.pdf"))
        'a3f2...8e91'
    """
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as file_handle:
            while chunk := file_handle.read(buffer_size):
                sha256_hash.update(chunk)
    except (OSError, PermissionError) as exc:
        dataset_log.error(
            "SHA256 computation failed | file={file} | error={error}",
            file=str(file_path),
            error=str(exc),
        )
        raise
    return sha256_hash.hexdigest()


# =============================================================================
# FILE METADATA
# =============================================================================

def get_file_size_bytes(file_path: Path) -> int:
    """
    Return the size of a file in bytes.

    Args:
        file_path: Path to the file.

    Returns:
        File size in bytes (integer).

    Raises:
        FileNotFoundError: If file_path does not exist.
        OSError:           If stat() fails.
    """
    return file_path.stat().st_size


def get_file_timestamps(file_path: Path) -> Tuple[datetime, datetime]:
    """
    Extract file creation and last-modification timestamps as UTC datetimes.

    Notes:
        - On Windows: st_ctime is the true creation time.
        - On Linux:   st_ctime is the last metadata-change time (inode ctime).
          We fall back to st_mtime as a proxy for creation time on Linux.
        - All returned datetimes are timezone-aware UTC.

    Args:
        file_path: Path to the file.

    Returns:
        Tuple of (created_at, modified_at) as timezone-aware UTC datetimes.

    Raises:
        OSError: If stat() fails.
    """
    file_stat = file_path.stat()
    modified_at = datetime.fromtimestamp(file_stat.st_mtime, tz=timezone.utc)

    if platform.system() == "Windows":
        created_at = datetime.fromtimestamp(file_stat.st_ctime, tz=timezone.utc)
    else:
        # Linux does not expose st_birthtime; use st_mtime as best approximation
        created_at = datetime.fromtimestamp(
            getattr(file_stat, "st_birthtime", file_stat.st_mtime),
            tz=timezone.utc,
        )

    return created_at, modified_at


# =============================================================================
# PDF VALIDATION
# =============================================================================

def get_pdf_page_count(file_path: Path) -> Tuple[int, bool, Optional[str]]:
    """
    Open a PDF with PyMuPDF and return its page count.

    This function performs ONLY metadata extraction (page count).
    It does NOT extract text, images, or any content — that is the
    responsibility of the PDF Parser module (Milestone 3).

    Args:
        file_path: Absolute path to the PDF file.

    Returns:
        Tuple of:
            - page_count (int):   Number of pages (0 if invalid/corrupted).
            - is_valid (bool):    True if PyMuPDF opened the file successfully.
            - error_msg (str|None): Error description if not valid, else None.

    Note:
        Requires PyMuPDF (fitz) to be installed: pip install PyMuPDF
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        dataset_log.warning(
            "PyMuPDF not installed — page count unavailable | file={file}",
            file=file_path.name,
        )
        return 0, False, "PyMuPDF (fitz) is not installed."

    try:
        document = fitz.open(str(file_path))
        page_count: int = len(document)
        document.close()

        if page_count == 0:
            return 0, False, "PDF contains zero pages."

        return page_count, True, None

    except fitz.FileDataError as exc:
        return 0, False, f"Corrupted PDF file: {exc}"
    except fitz.EmptyFileError:
        return 0, False, "Empty PDF file."
    except Exception as exc:  # noqa: BLE001 — broad catch for all fitz errors
        return 0, False, f"Failed to open PDF: {exc}"


# =============================================================================
# IDENTIFIER GENERATION
# =============================================================================

def generate_document_id(sha256_checksum: str, relative_path: str) -> str:
    """
    Generate a deterministic document UUID using UUID5.

    UUID5 is deterministic: the same (sha256, relative_path) pair always
    produces the same UUID. This ensures stable document IDs across
    multiple re-scans of the same dataset without database lookups.

    Args:
        sha256_checksum: SHA256 hex digest of the file bytes.
        relative_path:   Path relative to the dataset root.

    Returns:
        Lowercase UUID5 string (e.g., "550e8400-e29b-41d4-a716-446655440000").
    """
    # Combine checksum and path as the name for UUID5
    # Using NAMESPACE_URL as the namespace — arbitrary but consistent
    name_string = f"{sha256_checksum}::{relative_path}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name_string))


# =============================================================================
# CATEGORY DETECTION
# =============================================================================

def detect_category(file_path: Path, dataset_root: Path) -> str:
    """
    Infer document category from the immediate parent folder name.

    The category is the name of the direct subdirectory of dataset_root
    that contains the file. No manual category assignment is required.

    Examples:
        dataset/Acts/TaxAct.pdf           → "Acts"
        dataset/CourtJudgement/Case.pdf   → "CourtJudgement"
        dataset/Tax/Form1040.pdf          → "Tax"
        dataset/Legal_opinion/Opinion.pdf → "Legal_opinion"

    Args:
        file_path:    Absolute path to the PDF file.
        dataset_root: Absolute path to the dataset root directory.

    Returns:
        Category name string (matches one of VALID_CATEGORIES).

    Raises:
        ValueError: If the file's parent folder is not a known category.
    """
    # Compute the relative path from dataset root
    try:
        relative = file_path.relative_to(dataset_root)
    except ValueError as exc:
        raise ValueError(
            f"File '{file_path}' is not under dataset root '{dataset_root}'."
        ) from exc

    # The first part of the relative path is the category folder
    parts = relative.parts
    if len(parts) < 2:
        raise ValueError(
            f"File '{file_path}' is directly under dataset root — expected a category subfolder."
        )

    category_folder = parts[0]

    if category_folder not in VALID_CATEGORIES:
        raise ValueError(
            f"Unknown category folder '{category_folder}'. "
            f"Expected one of: {VALID_CATEGORIES}"
        )

    return category_folder


# =============================================================================
# TITLE DERIVATION
# =============================================================================

def derive_title(file_name: str) -> str:
    """
    Derive a clean display title from a PDF filename.

    Removes the .pdf extension, replaces underscores and hyphens with
    spaces, and applies title-case formatting.

    Args:
        file_name: Original filename string (e.g., "tax_cuts_jobs_act_2017.pdf").

    Returns:
        Clean title string (e.g., "Tax Cuts Jobs Act 2017").

    Example:
        >>> derive_title("tax_cuts_jobs_act_2017.pdf")
        'Tax Cuts Jobs Act 2017'
        >>> derive_title("Brown v. Board of Education.pdf")
        'Brown V. Board Of Education'
    """
    stem = Path(file_name).stem
    # Replace underscores and hyphens with spaces
    cleaned = stem.replace("_", " ").replace("-", " ")
    # Strip excess whitespace
    cleaned = " ".join(cleaned.split())
    return cleaned.title()


# =============================================================================
# PATH UTILITIES
# =============================================================================

def get_relative_path(file_path: Path, base_path: Path) -> str:
    """
    Compute the path of file_path relative to base_path as a POSIX string.

    Using POSIX (forward-slash) separators ensures the relative path is
    platform-independent when stored in CSV or JSON.

    Args:
        file_path: Absolute path to the file.
        base_path: Absolute base path (dataset root).

    Returns:
        POSIX-style relative path string (e.g., "Acts/TaxAct.pdf").

    Raises:
        ValueError: If file_path is not under base_path.
    """
    return file_path.relative_to(base_path).as_posix()


# =============================================================================
# FILE TYPE DETECTION
# =============================================================================

def is_pdf_by_extension(file_path: Path) -> bool:
    """
    Check if a file has a .pdf extension (case-insensitive).

    Note: Extension check is a fast pre-filter. PyMuPDF performs the
    definitive validation by attempting to open the file.

    Args:
        file_path: Path to check.

    Returns:
        True if the file extension is .pdf (case-insensitive).
    """
    return file_path.suffix.lower() == PDF_EXTENSION


def is_hidden_file(file_path: Path) -> bool:
    """
    Detect operating-system hidden files.

    Detection strategy:
        - Unix/macOS: filenames starting with a dot (e.g., ".hidden.pdf")
        - Windows:    FILE_ATTRIBUTE_HIDDEN flag set on the file (0x2)

    Args:
        file_path: Path to check.

    Returns:
        True if the file is considered hidden.
    """
    # Dot-prefix check (Unix/macOS)
    if file_path.name.startswith("."):
        return True

    # Windows hidden attribute check
    if platform.system() == "Windows":
        try:
            attrs = file_path.stat().st_file_attributes  # type: ignore[attr-defined]
            return bool(attrs & stat.FILE_ATTRIBUTE_HIDDEN)  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            pass

    return False


# =============================================================================
# HUMAN-READABLE FORMATTING
# =============================================================================

def format_size_human(size_bytes: int, decimal_places: int = 2) -> str:
    """
    Format a byte count as a human-readable string.

    Args:
        size_bytes:     Size in bytes.
        decimal_places: Number of decimal places in the output.

    Returns:
        Formatted string (e.g., "4.23 MB", "1.07 GB", "512 Bytes").

    Example:
        >>> format_size_human(5_500_000)
        '5.24 MB'
    """
    if size_bytes == 0:
        return "0 Bytes"

    units = ("Bytes", "KB", "MB", "GB", "TB")
    size: float = float(size_bytes)
    unit_index = 0

    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    return f"{size:.{decimal_places}f} {units[unit_index]}"
