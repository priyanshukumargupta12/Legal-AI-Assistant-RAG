"""
core/config/__init__.py
=======================
Exposes the Settings singleton from the config package.
"""

from app.core.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
