"""Verify whether BibTeX cited works exist across open scholarly sources."""

from .pipeline import LIMITS, parse_job, summarize, verify_bibliography, verify_one

__version__ = "0.1.2"
__all__ = [
    "LIMITS",
    "parse_job",
    "summarize",
    "verify_bibliography",
    "verify_one",
    "__version__",
]
