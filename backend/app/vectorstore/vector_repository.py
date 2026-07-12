"""
app/vectorstore/vector_repository.py
====================================
Vector repository interface re-export.

PURPOSE:
    Re-exports the core VectorRepository contract to maintain cohesive import
    interfaces within the vectorstore package.
"""

from __future__ import annotations

from app.repositories.vector_repository import VectorRepository

__all__ = ["VectorRepository"]
