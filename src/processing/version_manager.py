"""
Event version management and sequence ordering.
"""

from enum import Enum
from typing import Optional


class VersionAction(str, Enum):
    APPLY = "APPLY"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    CONFLICT = "CONFLICT"
    LATE_IGNORED = "LATE_IGNORED"


def evaluate_event_version(
    current_version: Optional[int],
    incoming_version: int,
    is_duplicate: bool,
    is_exact_match: bool,
) -> VersionAction:
    """
    Evaluates whether an incoming event should be applied, ignored as an exact duplicate,
    or rejected due to version conflict or out-of-order arrival.
    """
    if is_duplicate:
        if is_exact_match:
            return VersionAction.EXACT_DUPLICATE
        return VersionAction.CONFLICT

    if current_version is None:
        # Initial version
        if incoming_version == 1:
            return VersionAction.APPLY
        # Higher version before version 1 (missing intermediate):
        # As per contract: Assume higher versions contain full replacement snapshots
        return VersionAction.APPLY

    if incoming_version > current_version:
        return VersionAction.APPLY
    elif incoming_version == current_version:
        # Same version but wasn't detected as duplicate (e.g. diff event_id)
        return VersionAction.CONFLICT
    else:
        # Lower version arriving late
        return VersionAction.LATE_IGNORED
