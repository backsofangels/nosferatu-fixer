"""Core data models for the EPUB pipeline."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TocEntry:
    """Table of contents entry."""
    title: str
    href: str                              # e.g. "Text/chapter01.xhtml#section-1"
    file_part: str                         # e.g. "Text/chapter01.xhtml"
    anchor: Optional[str] = None
    level: int = 1                         # 1=top, 2=sub, 3=sub-sub
    children: list["TocEntry"] = field(default_factory=list)
    source: str = "unknown"                # "semantic_heading" | "css_class" | "bold_paragraph"
                                           # | "uppercase_heuristic" | "ncx_fallback"
    confidence: float = 0.0                # 0.0 → 1.0


@dataclass
class NavNode:
    """Navigation tree node for hierarchical nav.xhtml generation."""
    level: int                             # Heading level (0 for virtual root, 1-6 for real headings)
    entry: Optional["TocEntry"] = None     # The TOC entry (None for virtual root)
    children: list["NavNode"] = field(default_factory=list)
    
    def add_child(self, node: "NavNode") -> None:
        """Add a node as a direct child."""
        self.children.append(node)


@dataclass
class SpineItem:
    """Spine manifest item."""
    id: str
    href: str                              # relative to OPF
    media_type: str
    properties: str = ""


@dataclass
class PipelineReport:
    """Comprehensive pipeline report."""
    input: str
    output: str = ""
    epub_version: str = "2.0"
    fixed_layout: bool = False
    rtl: bool = False
    phases_run: list[str] = field(default_factory=list)
    original_toc_entries: int = 0
    rebuilt_toc_entries: int = 0
    injected_anchors: int = 0
    detection_sources: dict = field(default_factory=dict)  # {"semantic_heading": N, ...}
    spine_files_without_toc_entry: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    f1_score: Optional[float] = None       # None if no ground truth provided

    # Phase 0 diagnostic fields
    language: str = ""
    drm: bool = False
    dominant_pattern: str = ""             # "calibre_split" | "one_file_one_chapter" | "single_file" | "fixed_layout"
    markup_quality: str = ""               # "clean" | "partial" | "flat_calibre" | "no_markup"
    spine_items: int = 0
    estimated_chapters: int = 0
    semantic_headings_found: int = 0
    epub_type_tags_found: int = 0
    recommended_phases: list[str] = field(default_factory=list)
    original_toc_format: str = "ncx"       # "ncx" | "nav" | "both" | "none"
