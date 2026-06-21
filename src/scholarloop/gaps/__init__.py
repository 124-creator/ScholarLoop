"""M070 research-gap detection layer."""

from scholarloop.gaps.detect import GapDetector, GapRunConfig, PaperRecord
from scholarloop.gaps.narrate import NarrationResult, narrate_candidates, validate_narration_ids

__all__ = [
    "GapDetector",
    "GapRunConfig",
    "PaperRecord",
    "NarrationResult",
    "narrate_candidates",
    "validate_narration_ids",
]
