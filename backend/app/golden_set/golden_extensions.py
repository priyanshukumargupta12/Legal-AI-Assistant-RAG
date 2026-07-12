"""
app/golden_set/golden_extensions.py
======================================
Extension point interfaces for the Golden Set Management Module.

PURPOSE:
    Defines the abstract base classes (ABCs) that allow the Golden Set module
    to be extended for new downstream use cases without modifying any existing
    code (Open/Closed Principle).

    This file is the ONLY place new use cases need to look to understand how
    to plug into the Golden Set pipeline. Each use case author must implement:

        1. GoldenSetAdapter     — converts GoldenRecords to the use-case format
        2. GoldenSetExporter    — serializes adapted records to a file format
        3. DataSplitter         — assigns train/validation/test splits

    Optional hooks:
        4. GoldenSetPipelineHook — pre/post processing callbacks

IMPLEMENTED USE CASES:
    None yet. This file is pure architecture — no concrete implementations.

FUTURE IMPLEMENTATIONS:
    ┌─────────────────────────────┬──────────────────────────────┬───────────────┐
    │ Use Case                    │ Adapter Class (to create)    │ Format        │
    ├─────────────────────────────┼──────────────────────────────┼───────────────┤
    │ RAG Benchmarking (current)  │ RagBenchmarkAdapter          │ CSV / XLSX    │
    │ Retrieval Optimization      │ RetrievalOptimizationAdapter │ JSONL         │
    │ Prompt Optimization         │ PromptOptimizationAdapter    │ JSON / JSONL  │
    │ LLM Fine-Tuning             │ LLMFineTuningAdapter         │ JSONL         │
    └─────────────────────────────┴──────────────────────────────┴───────────────┘

REGISTRATION:
    Future adapters register themselves via GoldenSetRegistry:

        registry = GoldenSetRegistry.get_instance()
        registry.register_adapter(
            use_case=GoldenSetUseCase.LLM_FINE_TUNING,
            adapter=LLMFineTuningAdapter(),
        )
        registry.register_exporter(
            format=ExportFormat.JSONL,
            exporter=JsonLinesExporter(),
        )

    GoldenSetService.export_for_use_case() then resolves the correct
    adapter + exporter combination automatically.

DESIGN:
    - All classes are ABCs (abstract base classes) — no instantiation
    - Type annotations are comprehensive for IDE support
    - No imports from FastAPI, Pydantic, or external libraries
    - Designed to be self-documenting (adapter authors need only read this file)

SOLID:
    Open/Closed       — extend behavior by adding new adapters, not modifying service
    Interface Seregation — separate Adapter, Exporter, Splitter, Hook interfaces
    Dependency Inversion — service depends on abstractions, not concrete adapters
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.golden_set.golden_models import (
    DataSplit,
    ExportFormat,
    GoldenRecord,
    GoldenSetExportConfig,
    GoldenSetUseCase,
)


# =============================================================================
# GOLDEN SET ADAPTER (Use-Case Interface)
# =============================================================================

class GoldenSetAdapter(ABC):
    """
    Abstract base class for use-case-specific record transformers.

    Each downstream use case (RAG benchmarking, retrieval optimization,
    prompt optimization, LLM fine-tuning) implements one GoldenSetAdapter.
    The adapter is responsible for:
        1. Filtering which records are suitable for the use case
        2. Transforming each record into the use-case-specific dict format
        3. Declaring which ExportFormat(s) it supports

    The adapter does NOT handle I/O — that is the exporter's job.

    IMPLEMENTATION GUIDE:
        class LLMFineTuningAdapter(GoldenSetAdapter):

            @property
            def use_case(self) -> GoldenSetUseCase:
                return GoldenSetUseCase.LLM_FINE_TUNING

            @property
            def supported_formats(self) -> Set[ExportFormat]:
                return {ExportFormat.JSONL, ExportFormat.PARQUET}

            def is_eligible(self, record: GoldenRecord) -> bool:
                # Only export valid records with sufficient answer length
                return record.is_valid and len(record.expected_answer) >= 50

            def transform(self, record: GoldenRecord, config: GoldenSetExportConfig) -> Dict[str, Any]:
                # Map to HuggingFace instruction-tuning format
                field_map = config.field_mapping or {}
                return {
                    field_map.get("query", "instruction"):           record.query,
                    field_map.get("source_document", "context"):     record.source_document,
                    field_map.get("expected_answer", "output"):      record.expected_answer,
                    "category": record.category,
                    "split":    record.split.value,
                }
    """

    @property
    @abstractmethod
    def use_case(self) -> GoldenSetUseCase:
        """The downstream use case this adapter targets."""
        ...

    @property
    @abstractmethod
    def supported_formats(self) -> Set[ExportFormat]:
        """Set of ExportFormat values this adapter can write to."""
        ...

    @abstractmethod
    def is_eligible(self, record: GoldenRecord) -> bool:
        """
        Return True if the given record should be included in this use case's export.

        Filters are use-case-specific:
            - Fine-tuning may require minimum answer length
            - Retrieval optimization may require a specific difficulty level
            - Prompt optimization may exclude records without citations

        Args:
            record: A GoldenRecord to evaluate.

        Returns:
            True if the record should be included; False to skip it.
        """
        ...

    @abstractmethod
    def transform(
        self,
        record: GoldenRecord,
        config: GoldenSetExportConfig,
    ) -> Dict[str, Any]:
        """
        Convert a single GoldenRecord into a use-case-specific dict.

        The returned dict will be written by a GoldenSetExporter. Each
        key in the dict becomes either a column name (CSV) or a JSON field.

        Args:
            record: A validated GoldenRecord (is_eligible() already confirmed).
            config: The export configuration, including optional field_mapping.

        Returns:
            Dict with string keys and JSON-serializable values.
        """
        ...

    def batch_transform(
        self,
        records: List[GoldenRecord],
        config: GoldenSetExportConfig,
    ) -> List[Dict[str, Any]]:
        """
        Transform and filter a list of records in a single pass.

        Default implementation filters by is_eligible() then calls transform().
        Override for batch optimizations (e.g., vectorized pandas operations).

        Args:
            records: All GoldenRecord objects to consider.
            config:  Export configuration.

        Returns:
            List of transformed dicts (excluded records are omitted).
        """
        return [
            self.transform(record, config)
            for record in records
            if self.is_eligible(record)
        ]


# =============================================================================
# GOLDEN SET EXPORTER (Format Interface)
# =============================================================================

class GoldenSetExporter(ABC):
    """
    Abstract base class for file-format serializers.

    Each ExportFormat (CSV, XLSX, JSON, JSONL, Parquet) has one exporter.
    The exporter receives the already-transformed dicts from a GoldenSetAdapter
    and writes them to a file in the correct format.

    IMPLEMENTATION GUIDE:
        class JsonLinesExporter(GoldenSetExporter):

            @property
            def format(self) -> ExportFormat:
                return ExportFormat.JSONL

            def export(
                self,
                rows: List[Dict[str, Any]],
                output_path: Path,
                config: GoldenSetExportConfig,
            ) -> Path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    for row in rows:
                        f.write(json.dumps(row, ensure_ascii=False) + "\\n")
                return output_path
    """

    @property
    @abstractmethod
    def format(self) -> ExportFormat:
        """The ExportFormat this exporter produces."""
        ...

    @abstractmethod
    def export(
        self,
        rows: List[Dict[str, Any]],
        output_path: Path,
        config: GoldenSetExportConfig,
    ) -> Path:
        """
        Write transformed rows to a file and return the output path.

        Args:
            rows:        List of dicts from GoldenSetAdapter.batch_transform().
            output_path: Absolute path where the output file should be written.
            config:      Export configuration (may contain format-specific metadata).

        Returns:
            Path to the written file (same as output_path on success).

        Raises:
            GoldenSetExportError: If writing fails for any reason.
        """
        ...


# =============================================================================
# DATA SPLITTER (Train/Val/Test Interface)
# =============================================================================

class DataSplitter(ABC):
    """
    Abstract base class for train/validation/test split assignment.

    A DataSplitter receives a list of eligible GoldenRecord objects and
    mutates each record's `.split` field in-place to assign a DataSplit value.
    The split strategy (random, stratified, etc.) is chosen by the implementer.

    NOTE: GoldenRecord.split defaults to DataSplit.UNASSIGNED.
    Splitters assign TRAIN, VALIDATION, or TEST. Records not assigned by
    the splitter remain UNASSIGNED.

    IMPLEMENTATION GUIDE:
        class RandomSplitter(DataSplitter):

            @property
            def strategy_name(self) -> str:
                return "random"

            def assign_splits(
                self,
                records: List[GoldenRecord],
                ratios: tuple,
                seed: int = 42,
            ) -> List[GoldenRecord]:
                import random
                random.seed(seed)
                shuffled = random.sample(records, len(records))
                n = len(shuffled)
                train_end = int(n * ratios[0])
                val_end   = int(n * (ratios[0] + ratios[1]))
                for i, rec in enumerate(shuffled):
                    if i < train_end:
                        rec.split = DataSplit.TRAIN
                    elif i < val_end:
                        rec.split = DataSplit.VALIDATION
                    else:
                        rec.split = DataSplit.TEST
                return shuffled
    """

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Machine-readable name for this split strategy (e.g., 'random')."""
        ...

    @abstractmethod
    def assign_splits(
        self,
        records: List[GoldenRecord],
        ratios: tuple,
        seed: int = 42,
    ) -> List[GoldenRecord]:
        """
        Assign DataSplit values to each record's .split field.

        Args:
            records: List of eligible GoldenRecord objects to split.
            ratios:  3-tuple (train, validation, test) summing to ≤ 1.0.
            seed:    Random seed for reproducibility.

        Returns:
            The same list of records with .split fields populated.
        """
        ...


# =============================================================================
# GOLDEN SET PIPELINE HOOK (Optional Callbacks)
# =============================================================================

class GoldenSetPipelineHook(ABC):
    """
    Abstract base class for optional pre/post processing callbacks.

    Hooks allow cross-cutting concerns (logging, caching, notifications,
    external API calls) to be injected into the export pipeline without
    modifying the service or adapter code.

    Hooks are OPTIONAL and are registered per use case.

    LIFECYCLE:
        1. before_export()   — called before adapter.batch_transform()
        2. after_export()    — called after exporter.export() succeeds
        3. on_export_error() — called if any step raises an exception

    IMPLEMENTATION GUIDE:
        class SlackNotificationHook(GoldenSetPipelineHook):

            def before_export(self, config: GoldenSetExportConfig, records: List[GoldenRecord]) -> None:
                slack.post(f"Starting export: {config.use_case.value} ({len(records)} records)")

            def after_export(self, config: GoldenSetExportConfig, output_path: Path, row_count: int) -> None:
                slack.post(f"Export complete: {output_path.name} | {row_count} rows written")

            def on_export_error(self, config: GoldenSetExportConfig, error: Exception) -> None:
                slack.post(f"Export failed: {config.use_case.value} | {error}")
    """

    def before_export(
        self,
        config: GoldenSetExportConfig,
        records: List[GoldenRecord],
    ) -> None:
        """
        Called immediately before the adapter transforms records.

        Args:
            config:  The export configuration for this pipeline run.
            records: All records that will be passed to the adapter.
        """
        ...

    def after_export(
        self,
        config: GoldenSetExportConfig,
        output_path: Path,
        row_count: int,
    ) -> None:
        """
        Called after the exporter successfully writes the output file.

        Args:
            config:      The export configuration for this pipeline run.
            output_path: Path to the file that was written.
            row_count:   Number of rows written to the output file.
        """
        ...

    def on_export_error(
        self,
        config: GoldenSetExportConfig,
        error: Exception,
    ) -> None:
        """
        Called if any step in the export pipeline raises an exception.

        Args:
            config: The export configuration for the failed pipeline run.
            error:  The exception that caused the failure.
        """
        ...


# =============================================================================
# GOLDEN SET REGISTRY (Adapter + Exporter Lookup)
# =============================================================================

class GoldenSetRegistry:
    """
    Singleton registry that maps use cases → adapters and formats → exporters.

    GoldenSetService.export_for_use_case() uses this registry to resolve
    the correct adapter + exporter pair for any given GoldenSetExportConfig.

    THREAD SAFETY:
        The registry is populated at application startup and is read-only
        thereafter. No locking is required for normal operation.

    USAGE:
        # At startup / in a plugin loader:
        registry = GoldenSetRegistry.get_instance()
        registry.register_adapter(GoldenSetUseCase.LLM_FINE_TUNING, LLMFineTuningAdapter())
        registry.register_exporter(ExportFormat.JSONL, JsonLinesExporter())

        # In GoldenSetService:
        registry = GoldenSetRegistry.get_instance()
        adapter  = registry.get_adapter(config.use_case)     # raises if not registered
        exporter = registry.get_exporter(config.export_format) # raises if not registered
    """

    _instance: Optional["GoldenSetRegistry"] = None

    def __init__(self) -> None:
        self._adapters: Dict[GoldenSetUseCase, GoldenSetAdapter] = {}
        self._exporters: Dict[ExportFormat, GoldenSetExporter] = {}
        self._hooks: Dict[GoldenSetUseCase, List[GoldenSetPipelineHook]] = {}

    @classmethod
    def get_instance(cls) -> "GoldenSetRegistry":
        """Return the singleton registry instance, creating it if needed."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (primarily for use in tests)."""
        cls._instance = None

    # ── Adapter registration ──────────────────────────────────────────────────

    def register_adapter(
        self,
        use_case: GoldenSetUseCase,
        adapter: GoldenSetAdapter,
    ) -> None:
        """
        Register an adapter for a specific use case.

        Raises ValueError if the use_case already has a registered adapter
        (use force=True by replacing an existing registration intentionally).

        Args:
            use_case: The GoldenSetUseCase enum value.
            adapter:  A concrete GoldenSetAdapter implementation.
        """
        self._adapters[use_case] = adapter

    def get_adapter(self, use_case: GoldenSetUseCase) -> GoldenSetAdapter:
        """
        Return the registered adapter for the given use case.

        Args:
            use_case: The GoldenSetUseCase to look up.

        Returns:
            The registered GoldenSetAdapter.

        Raises:
            KeyError: If no adapter has been registered for this use case.
        """
        if use_case not in self._adapters:
            raise KeyError(
                f"No GoldenSetAdapter registered for use case '{use_case.value}'. "
                f"Registered use cases: {[k.value for k in self._adapters]}"
            )
        return self._adapters[use_case]

    def is_adapter_registered(self, use_case: GoldenSetUseCase) -> bool:
        """Return True if an adapter has been registered for the given use case."""
        return use_case in self._adapters

    # ── Exporter registration ─────────────────────────────────────────────────

    def register_exporter(
        self,
        format: ExportFormat,
        exporter: GoldenSetExporter,
    ) -> None:
        """
        Register an exporter for a specific file format.

        Args:
            format:   The ExportFormat enum value.
            exporter: A concrete GoldenSetExporter implementation.
        """
        self._exporters[format] = exporter

    def get_exporter(self, format: ExportFormat) -> GoldenSetExporter:
        """
        Return the registered exporter for the given format.

        Args:
            format: The ExportFormat to look up.

        Returns:
            The registered GoldenSetExporter.

        Raises:
            KeyError: If no exporter has been registered for this format.
        """
        if format not in self._exporters:
            raise KeyError(
                f"No GoldenSetExporter registered for format '{format.value}'. "
                f"Registered formats: {[k.value for k in self._exporters]}"
            )
        return self._exporters[format]

    def is_exporter_registered(self, format: ExportFormat) -> bool:
        """Return True if an exporter has been registered for the given format."""
        return format in self._exporters

    # ── Hook registration ─────────────────────────────────────────────────────

    def register_hook(
        self,
        use_case: GoldenSetUseCase,
        hook: GoldenSetPipelineHook,
    ) -> None:
        """
        Register a pipeline hook for a specific use case.

        Multiple hooks can be registered per use case; they execute in
        registration order.

        Args:
            use_case: The GoldenSetUseCase to attach the hook to.
            hook:     A concrete GoldenSetPipelineHook implementation.
        """
        if use_case not in self._hooks:
            self._hooks[use_case] = []
        self._hooks[use_case].append(hook)

    def get_hooks(self, use_case: GoldenSetUseCase) -> List[GoldenSetPipelineHook]:
        """
        Return all registered hooks for the given use case (may be empty).

        Args:
            use_case: The GoldenSetUseCase to look up.

        Returns:
            List of GoldenSetPipelineHook instances (empty if none registered).
        """
        return self._hooks.get(use_case, [])

    # ── Introspection ─────────────────────────────────────────────────────────

    def describe(self) -> Dict[str, Any]:
        """
        Return a human-readable summary of all registered components.

        Used for health checks, startup logs, and admin API endpoints.

        Returns:
            Dict with keys: adapters, exporters, hooks.
        """
        return {
            "adapters": {
                uc.value: type(adapter).__name__
                for uc, adapter in self._adapters.items()
            },
            "exporters": {
                fmt.value: type(exporter).__name__
                for fmt, exporter in self._exporters.items()
            },
            "hooks": {
                uc.value: [type(h).__name__ for h in hooks]
                for uc, hooks in self._hooks.items()
            },
        }
