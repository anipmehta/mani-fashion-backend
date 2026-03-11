"""Audit Trail Recorder — records every iteration of the agent loop.

Maintains a chronologically ordered list of AuditEntry objects,
one per iteration (including iteration 0 for the initial sloper).
"""

from __future__ import annotations

from agentic_pattern_engine.models import AuditEntry, AuditTrail


class AuditTrailRecorder:
    """Append-only recorder for agent loop iterations."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(self, entry: AuditEntry) -> None:
        """Append an iteration entry. Enforces chronological ordering."""
        if self._entries:
            last = self._entries[-1].iteration
            if entry.iteration <= last:
                raise ValueError(
                    f"Entry iteration {entry.iteration} must be > "
                    f"last recorded iteration {last}"
                )
        self._entries.append(entry)

    def get_trail(self) -> AuditTrail:
        """Return the complete audit trail."""
        return AuditTrail(entries=list(self._entries))

    def reset(self) -> None:
        """Clear all entries (for reuse across runs)."""
        self._entries.clear()
