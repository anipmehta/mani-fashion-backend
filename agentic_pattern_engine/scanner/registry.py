"""AdapterRegistry — ordered registry of ScannerAdapter instances."""
from __future__ import annotations

from agentic_pattern_engine.scanner.adapters import (
    GenericAdapter,
    ThreeDLookAdapter,
)
from agentic_pattern_engine.scanner.models import ScanResult
from agentic_pattern_engine.scanner.protocol import ScannerAdapter


class AdapterRegistry:
    """Ordered registry that auto-selects the first matching adapter.

    Default order: ``[ThreeDLookAdapter(), GenericAdapter()]``.
    Vendor-specific adapters are always checked before the generic fallback.
    """

    def __init__(self) -> None:
        self._adapters: list[ScannerAdapter] = [
            ThreeDLookAdapter(),
            GenericAdapter(),
        ]

    @property
    def adapters(self) -> list[ScannerAdapter]:
        """Return a shallow copy of the adapter list."""
        return list(self._adapters)

    def parse(self, data: dict) -> ScanResult:
        """Iterate adapters and use the first whose ``can_handle`` returns True.

        Raises ``ValueError`` if no adapter can handle the data.
        """
        for adapter in self._adapters:
            if adapter.can_handle(data):
                return adapter.parse(data)
        raise ValueError(
            "Scan format not recognized: no registered adapter can handle "
            "the provided data."
        )

    def register(self, adapter: ScannerAdapter) -> None:
        """Insert *adapter* before the GenericAdapter (last position).

        If no GenericAdapter is present, the adapter is appended at the end.
        """
        for idx, existing in enumerate(self._adapters):
            if isinstance(existing, GenericAdapter):
                self._adapters.insert(idx, adapter)
                return
        self._adapters.append(adapter)
