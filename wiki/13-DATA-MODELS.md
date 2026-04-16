# Data Models Reference

Complete documentation of all data structures used throughout TOC Fixer.

## 📦 Core Models

All models defined in `toc_fixer/core/models.py`

---

## 🔤 TocEntry

Represents a table of contents entry with metadata.

### Definition

```python
@dataclass
class TocEntry:
    title: str              # Entry title/heading text
    href: str               # Link to file (e.g., "c01.html" or "c01.html#ch1")
    file_part: str          # Spine file basename (e.g., "c01.html")
    anchor: Optional[str]   # Fragment identifier (e.g., "ch1" from href)
    level: int              # Nesting level (1 = h1, 2 = h2, etc.)
    children: List['TocEntry'] = field(default_factory=list)  # Nested entries
    source: str = "detected"  # Source: "ncx", "detected", "title", etc.
    confidence: float = 1.0   # Confidence score (0.0-1.0)
```

### Fields

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `title` | str | Display text for TOC | "Chapter 1: The Beginning" |
| `href` | str | Link to location | "c01.html" or "c01.html#ch1" |
| `file_part` | str | Spine file | "c01.html" |
| `anchor` | str or None | Fragment ID | "ch1" |
| `level` | int | Heading level | 1 (h1), 2 (h2) |
| `children` | list | Nested entries | [TocEntry(...), ...] |
| `source` | str | How detected | "ncx", "detected", "semantic", "title" |
| `confidence` | float | Quality score | 0.3 to 1.0 |

### Confidence Scoring

Different detection methods have different confidence levels:

| Source | Method | Confidence | Notes |
|--------|--------|-----------|-------|
| "semantic" | Semantic tag (h1-h6) | 1.0 | Most reliable |
| "css_class" | CSS class heuristic | 0.85 | Good for Calibre |
| "bold" | Bold as heading | 0.7 | Risky but works |
| "uppercase" | Uppercase heuristic | 0.55 | Low confidence |
| "title" | Document title | 0.4 | Last resort |
| "ncx" | Original NCX | 0.3 | Fallback source |

### Usage Examples

```python
from toc_fixer.core.models import TocEntry

# Create simple entry
entry = TocEntry(
    title="Chapter 1",
    href="c01.html",
    file_part="c01.html",
    anchor=None,
    level=1,
    source="semantic",
    confidence=1.0
)

# Create entry with fragment
entry_with_anchor = TocEntry(
    title="Section 1.1",
    href="c01.html#s1",
    file_part="c01.html",
    anchor="s1",
    level=2,
    source="detected",
    confidence=0.85
)

# Create nested structure
main_entry = TocEntry(
    title="Part I",
    href="part1.html",
    file_part="part1.html",
    anchor=None,
    level=1,
    children=[entry, entry_with_anchor]
)

# Access properties
print(f"Title: {main_entry.title}")
print(f"Location: {main_entry.href}")
print(f"Confidence: {main_entry.confidence:.0%}")
print(f"Children: {len(main_entry.children)}")
```

### Operations

```python
# Flatten nested structure
def flatten_toc(entries: List[TocEntry]) -> List[TocEntry]:
    flat = []
    for entry in entries:
        flat.append(entry)
        flat.extend(flatten_toc(entry.children))
    return flat

# Filter by confidence
high_confidence = [e for e in entries if e.confidence >= 0.9]

# Find max nesting level
max_level = max(e.level for e in flatten_toc(entries))

# Group by file
by_file = {}
for entry in flatten_toc(entries):
    if entry.file_part not in by_file:
        by_file[entry.file_part] = []
    by_file[entry.file_part].append(entry)
```

---

## 📄 SpineItem

Represents an EPUB spine file (content file).

### Definition

```python
@dataclass
class SpineItem:
    id: str                 # Manifest ID (e.g., "c1")
    href: str               # File path (e.g., "OEBPS/c01.html")
    media_type: str         # MIME type (e.g., "application/xhtml+xml")
    properties: Optional[str] = None  # EPUB3 properties (e.g., "rendition:layout-reflowable")
    file_path: Optional[str] = None   # Computed full ZIP path
```

### Fields

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `id` | str | Manifest ID | "c1" |
| `href` | str | Relative path | "OEBPS/c01.html" |
| `media_type` | str | MIME type | "application/xhtml+xml" or "text/html" |
| `properties` | str or None | EPUB3 property | "svg", "rendition:layout-reflowable" |
| `file_path` | str or None | Computed ZIP path | "OEBPS/c01.html" |

### Usage Examples

```python
from toc_fixer.core.models import SpineItem

# Create spine item
item = SpineItem(
    id="c1",
    href="OEBPS/c01.html",
    media_type="application/xhtml+xml"
)

# With EPUB3 properties
item_with_props = SpineItem(
    id="cover",
    href="OEBPS/cover.xhtml",
    media_type="application/xhtml+xml",
    properties="rendition:layout-reflowable"
)

# Compute file path for ZIP access
from toc_fixer.core.utils import build_zip_key

opf_base = "OEBPS"  # Directory of OPF
zip_key = build_zip_key(opf_base, item.href)
print(f"ZIP key: {zip_key}")  # "OEBPS/OEBPS/c01.html" (wrong!) or "OEBPS/c01.html" (depends on href)

# Access content from EPUB
content = zip_file.read(zip_key)
```

### Determining File Type

```python
def is_xhtml(spine_item: SpineItem) -> bool:
    """Check if spine item is XHTML"""
    return spine_item.media_type == "application/xhtml+xml" or \
           spine_item.href.lower().endswith(".xhtml")

def is_html(spine_item: SpineItem) -> bool:
    """Check if spine item is HTML"""
    return "html" in spine_item.media_type or \
           spine_item.href.lower().endswith(".html")

# Usage
if is_xhtml(item):
    parser = "lxml-xml"  # Strict
else:
    parser = "lxml"      # Permissive
```

---

## 📊 PipelineReport

Accumulates metrics, errors, and results throughout pipeline execution.

### Definition

```python
@dataclass
class PipelineReport:
    # Phase information
    epub_version: str = "unknown"
    epub_language: str = "en"
    
    # Structure metrics
    spine_items: int = 0
    original_toc_entries: int = 0
    rebuilt_toc_entries: int = 0
    semantic_headings_detected: int = 0
    injected_anchors: int = 0
    
    # Quality metrics
    markup_quality: str = "unknown"  # "poor", "partial", "good"
    f1_score: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    
    # Execution info
    phases_executed: List[int] = field(default_factory=list)
    execution_time_seconds: float = 0.0
    
    # Messages
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # Detailed results
    se_lint_errors: List[str] = field(default_factory=list)
    epubcheck_errors: List[str] = field(default_factory=list)
    toc_entries: List[TocEntry] = field(default_factory=list)
```

### Usage Examples

```python
from toc_fixer.core.models import PipelineReport

# Create report
report = PipelineReport()

# Add phase execution
report.phases_executed.append(0)
report.phases_executed.append(1)

# Record findings
report.epub_version = "2.0"
report.spine_items = 42
report.original_toc_entries = 40
report.semantic_headings_detected = 37

# Add messages
report.add_error("NCX missing navLabel")
report.add_warning("Calibre images found, removing")
report.add_recommendation("Enable Phase 2 for heading detection")

# Set quality metrics
report.f1_score = 0.97
report.precision = 0.97
report.recall = 0.925

# Access data
print(f"EPUB: {report.epub_version}, Language: {report.epub_language}")
print(f"Structure: {report.spine_items} spine items, {report.original_toc_entries} TOC entries")
print(f"Headings detected: {report.semantic_headings_detected}")
print(f"Quality: {report.markup_quality}")
print(f"Errors: {len(report.errors)}")
print(f"Warnings: {len(report.warnings)}")
if report.f1_score:
    print(f"F1 Score: {report.f1_score:.2f}")
```

### Methods

```python
# Add messages
report.add_error("Error message")
report.add_warning("Warning message")
report.add_recommendation("Do this for better results")

# Set F1 score components
report.f1_score = 0.95
report.precision = 0.96
report.recall = 0.94

# Record phase execution
report.phases_executed.extend([0, 1, 2, 4, 5, 6, 7])

# Add detailed results
report.toc_entries = [TocEntry(...), ...]
report.se_lint_errors = ["error1", "error2"]
```

### JSON Serialization

```python
import json

# Save to JSON
def save_report(report: PipelineReport, output_path: str):
    data = {
        "epub_version": report.epub_version,
        "epub_language": report.epub_language,
        "spine_items": report.spine_items,
        "original_toc_entries": report.original_toc_entries,
        "rebuilt_toc_entries": report.rebuilt_toc_entries,
        "semantic_headings_detected": report.semantic_headings_detected,
        "injected_anchors": report.injected_anchors,
        "markup_quality": report.markup_quality,
        "f1_score": report.f1_score,
        "precision": report.precision,
        "recall": report.recall,
        "phases_executed": report.phases_executed,
        "execution_time_seconds": report.execution_time_seconds,
        "errors": report.errors,
        "warnings": report.warnings,
        "recommendations": report.recommendations,
        "se_lint_errors": report.se_lint_errors,
        "epubcheck_errors": report.epubcheck_errors,
    }
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

# Load from JSON
def load_report(input_path: str) -> PipelineReport:
    with open(input_path) as f:
        data = json.load(f)
    report = PipelineReport()
    for key, value in data.items():
        if hasattr(report, key):
            setattr(report, key, value)
    return report
```

---

## 🔗 Model Relationships

```
PipelineReport (contains)
    ├─ toc_entries: List[TocEntry]
    │   ├─ Each TocEntry can have children: List[TocEntry]
    │   └─ Each references SpineItem by href
    │
    ├─ spine_items: Reference count
    │
    └─ metrics (f1_score, errors, warnings, etc.)

SpineItem (represents)
    └─ File in EPUB with href, media_type, properties

TocEntry (represents)
    ├─ Single TOC entry with title and location
    ├─ Can nest arbitrarily (children list)
    ├─ Links to SpineItem by file_part
    └─ Includes confidence and source for traceability
```

---

## 📋 Integration Points

### Phase 0 → Phase 7

```python
# Phase 0: Create initial report
report = PipelineReport()
report.epub_version = "2.0"
report.spine_items = 42
report.original_toc_entries = 40
report.semantic_headings_detected = 0

# Phase X: Modify report
report.semantic_headings_detected = 37
report.phases_executed.append(2)
report.add_warning("Some headings lowconfidence")

# Phase 7: Finalize report
report.rebuilt_toc_entries = 37
report.f1_score = 0.97
report.se_lint_errors = []
report.execution_time_seconds = 3.57
```

### Creating New Phases

Always create phase-local report updates:

```python
def run_phaseX(epub_path: str, output_path: str, report: PipelineReport) -> bool:
    try:
        # Transform
        # ...
        
        # Record results
        report.phases_executed.append(X)
        report.add_recommendation("Consider Phase X+1 for further improvement")
        return True
    except Exception as e:
        report.add_error(f"Phase X failed: {str(e)}")
        return False
```

---

## 🧪 Testing Models

```python
def test_toc_entry_nesting():
    """Test nested TOC structure"""
    child = TocEntry("Section 1.1", "c1.html#s1", "c1.html", "s1", 2)
    parent = TocEntry("Chapter 1", "c1.html", "c1.html", None, 1, children=[child])
    
    assert len(parent.children) == 1
    assert parent.children[0].level == 2

def test_pipeline_report_f1():
    """Test F1 score calculation"""
    report = PipelineReport()
    report.f1_score = 0.95
    
    assert report.f1_score >= 0.9  # Production threshold

def test_spine_item_media_type():
    """Test media type handling"""
    xhtml = SpineItem("c1", "c1.xhtml", "application/xhtml+xml")
    html = SpineItem("c2", "c2.html", "text/html")
    
    assert "html" in xhtml.media_type
    assert "html" in html.media_type
```

---

## 📚 Related Documentation

- [Architecture](01-ARCHITECTURE.md) — How models fit in system
- [API Reference](14-API-REFERENCE.md) — Complete function signatures
- [Pipeline Overview](04-PIPELINE-OVERVIEW.md) — Usage patterns

---

**Next**: Read [API Reference](14-API-REFERENCE.md) for complete function documentation.
