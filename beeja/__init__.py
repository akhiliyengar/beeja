"""beeja — interview-driven artifact builder for self-improving agent systems."""

from beeja import ops
from beeja.builder import (
    InterviewState,
    NeedAnswer,
    SuccessSpec,
    absorb_handoff,
    derive_name,
    draft,
    extract_json,
    interview,
    parse_bundle,
    read_bundle,
    revise,
    run_interview,
    shadow_root,
    write_bundle,
)

__version__ = "0.1.0"

__all__ = [
    "InterviewState",
    "NeedAnswer",
    "SuccessSpec",
    "absorb_handoff",
    "derive_name",
    "draft",
    "extract_json",
    "interview",
    "ops",
    "parse_bundle",
    "read_bundle",
    "revise",
    "run_interview",
    "shadow_root",
    "write_bundle",
    "__version__",
]
