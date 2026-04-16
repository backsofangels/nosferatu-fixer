"""Core utilities and data models."""

from .epub_utils import EPUBRepackager, EPUBRepackingError
from .models import NavNode, PipelineReport, SpineItem, TocEntry
from .phase_base import EPUBPhaseBase
from .se_tools import SEToolError, SEToolWrapper
from .utils import (
    build_zip_key,
    parse_ncx_entries,
    resolve_ncx_path,
    safe_read,
    select_parser,
)

__all__ = [
    "TocEntry",
    "NavNode",
    "SpineItem",
    "PipelineReport",
    "resolve_ncx_path",
    "build_zip_key",
    "safe_read",
    "select_parser",
    "parse_ncx_entries",
    "EPUBRepackager",
    "EPUBRepackingError",
    "SEToolWrapper",
    "SEToolError",
    "EPUBPhaseBase",
]
