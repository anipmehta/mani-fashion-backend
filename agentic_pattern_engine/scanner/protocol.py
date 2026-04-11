"""ScannerAdapter protocol — pluggable interface for scanner vendors."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from agentic_pattern_engine.scanner.models import ScanResult


@runtime_checkable
class ScannerAdapter(Protocol):
    """Protocol that every scanner adapter must satisfy structurally."""

    @property
    def scanner_name(self) -> str:  # pragma: no cover
        ...

    def can_handle(self, data: dict) -> bool:  # pragma: no cover
        ...

    def parse(self, data: dict) -> ScanResult:  # pragma: no cover
        ...
