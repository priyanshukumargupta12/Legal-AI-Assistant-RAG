"""
app/logging/logger.py
======================
Centralized logging configuration using Loguru.

PURPOSE:
    Configure 6 named loggers — each writing to its own rotating log file
    plus stdout (in development). Provides a factory function for getting
    a module-scoped logger with its subsystem name as a label.

LOGGERS:
    app        → logs/app/app.log           General application lifecycle
    api        → logs/api/api.log           HTTP request/response logging
    dataset    → logs/dataset/dataset.log   Dataset scanning & export events
    embedding  → logs/embedding/embedding.log  Embedding model & batch events
    retrieval  → logs/retrieval/retrieval.log  Hybrid search & RRF events
    evaluation → logs/evaluation/evaluation.log Golden set & metrics events

DESIGN:
    - Loguru sinks replace stdlib handlers; no configuration files needed
    - Structured format: timestamp | level | logger_name | module | message
    - File rotation at 10 MB; retains last 5 backups
    - Exceptions include full stack trace via diagnose=True
    - get_logger(name) is the single entry point for all modules

SOLID: Single Responsibility — only configures and exposes loggers.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from loguru import logger

# ─── Logger Names ─────────────────────────────────────────────────────────────
LoggerName = Literal["app", "api", "dataset", "embedding", "retrieval", "evaluation", "graph", "knowledge", "security", "elasticsearch"]

# ─── Log Directory (resolved relative to backend root) ────────────────────────
_LOG_ROOT = Path(__file__).resolve().parents[3] / "logs"

# ─── Loguru Format String ─────────────────────────────────────────────────────
_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[logger_name]: <12}</cyan> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{extra[logger_name]: <12} | "
    "{name}:{function}:{line} | "
    "{message}"
)


def _ensure_log_dirs() -> None:
    """Create all log subdirectories if they do not already exist."""
    for name in ("app", "api", "dataset", "embedding", "retrieval", "evaluation", "graph", "knowledge"):
        (_LOG_ROOT / name).mkdir(parents=True, exist_ok=True)


def configure_logging(log_level: str = "INFO", rotation: str = "10 MB", retention: int = 5) -> None:
    """
    Configure all Loguru sinks (stdout + 6 rotating file sinks).

    This function must be called once at application startup (in main.py
    lifespan). Calling it multiple times is safe — existing sinks are
    removed and re-added.

    Args:
        log_level: Minimum severity level to capture (e.g., "INFO").
        rotation:  Log file rotation threshold (e.g., "10 MB" or "1 day").
        retention: Number of old log files to retain per logger.
    """
    _ensure_log_dirs()

    # Apply global record patch to ensure logger_name is always set
    logger.configure(
        patcher=lambda r: r["extra"].setdefault(
            "logger_name", r["extra"].get("subsystem", r["name"].split(".")[-1])
        )
    )

    # Remove all existing sinks (prevents duplicate output on reload)
    logger.remove()


    # ── Stdout sink (coloured, development-friendly) ──────────────────────────
    logger.add(
        sink=sys.stdout,
        level=log_level,
        format=_LOG_FORMAT,
        colorize=True,
        diagnose=True,
        backtrace=True,
        filter=lambda record: True,  # All loggers go to stdout
    )

    # ── Per-subsystem file sinks ───────────────────────────────────────────────
    _subsystems: list[tuple[str, str]] = [
        ("app",          "app/app.log"),
        ("api",          "api/api.log"),
        ("dataset",      "dataset/dataset.log"),
        ("embedding",    "embedding/embedding.log"),
        ("retrieval",    "retrieval/retrieval.log"),
        ("evaluation",   "evaluation/evaluation.log"),
        ("graph",        "graph/graph.log"),
        ("knowledge",    "knowledge/knowledge.log"),
        ("security",     "app/app.log"),        # routes to app log
        ("elasticsearch","retrieval/retrieval.log"),  # routes to retrieval log
    ]

    for logger_name, relative_path in _subsystems:
        log_file = _LOG_ROOT / relative_path
        logger.add(
            sink=str(log_file),
            level=log_level,
            format=_FILE_FORMAT,
            rotation=rotation,
            retention=retention,
            compression="zip",
            encoding="utf-8",
            diagnose=True,
            backtrace=True,
            filter=lambda record, name=logger_name: record["extra"].get("logger_name") == name,
        )

    logger.bind(logger_name="app").info(
        "Logging configured | level={level} | log_dir={log_dir}",
        level=log_level,
        log_dir=str(_LOG_ROOT),
    )


def get_logger(name: LoggerName):
    """
    Return a Loguru logger instance bound to the given subsystem name.

    The logger_name is embedded in every log record via Loguru's bind()
    mechanism, enabling per-file log routing via the filter functions
    configured in configure_logging().

    Args:
        name: One of the 6 subsystem names.

    Returns:
        A bound Loguru logger instance.

    Example:
        >>> log = get_logger("embedding")
        >>> log.info("Model loaded | model={model}", model="bge-small")
    """
    return logger.bind(logger_name=name)
