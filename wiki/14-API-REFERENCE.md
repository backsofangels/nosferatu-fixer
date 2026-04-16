# API Reference

Complete API documentation for TOC Fixer modules.

## 📦 nosferatu-fixer.core

Core utilities and data models.

### models

```python
from nosferatu-fixer.core.models import TocEntry, SpineItem, PipelineReport

class TocEntry:
    """Table of contents entry"""
    title: str
    href: str
    file_part: str
    anchor: Optional[str]
    level: int
    children: List['TocEntry']
    source: str
    confidence: float

class SpineItem:
    """EPUB spine file"""
    id: str
    href: str
    media_type: str
    properties: Optional[str]
    file_path: Optional[str]

class PipelineReport:
    """Pipeline execution report"""
    epub_version: str
    epub_language: str
    spine_items: int
    original_toc_entries: int
    # ... 20+ fields
```

See [Data Models](13-DATA-MODELS.md) for detailed documentation.

### utils

```python
from nosferatu-fixer.core.utils import (
    resolve_ncx_path,
    parse_ncx_entries,
    build_zip_key,
    safe_read,
    select_parser,
)

def resolve_ncx_path(container_xml: bytes, opf_path: str, zip_file) -> Optional[str]:
    """Resolve NCX file path (BUG-1 fix)"""

def parse_ncx_entries(ncx_bytes: bytes) -> List[TocEntry]:
    """Parse NCX entries with lxml (BUG-2 fix)"""

def build_zip_key(opf_base: str, item_href: str) -> str:
    """Build ZIP file path (BUG-3 fix)"""

def safe_read(z: ZipFile, zip_key: str) -> Optional[bytes]:
    """Read from ZIP with case-insensitive fallback"""

def select_parser(filename: str) -> str:
    """Select HTML parser by extension (BUG-3 fix)"""
```

See [Core Utilities](02-CORE-UTILITIES.md) for detailed documentation.

### file_manager

```python
from nosferatu-fixer.core.file_manager import FileManager, PipelineFileTracker

class FileManager:
    """Manage file lifecycle and cleanup"""
    def __init__(self, entry_point: str, keep_debug_output: bool)
    def finalize(self, final_output: str, tmp_dir: Optional[Path]) -> int

class PipelineFileTracker:
    """Track phase outputs for chaining"""
    def register_phase_output(self, phase: int, path: str)
    def get_phase_input(self, phase: int) -> Optional[str]
    def get_status(self) -> Dict[str, Dict]
    def get_latest_output(self) -> Optional[str]
```

See [File Manager](03-FILE-MANAGER.md) for detailed documentation.

---

## 📦 nosferatu-fixer.pipeline

Phase implementations.

```python
from nosferatu-fixer.pipeline.phase0 import run_phase0
from nosferatu-fixer.pipeline.phase1 import run_phase1
from nosferatu-fixer.pipeline.phase2 import run_phase2
# ... phase3 through phase7

def run_phaseN(epub_path: str, output_path: str, report: PipelineReport) -> bool:
    """Run phase N, return True if successful"""
```

Each phase follows the same interface:
- **Input**: EPUB path, output path, report object
- **Output**: Boolean success status
- **Behavior**: Modify report in-place with results
- **Errors**: Logged to report, never thrown

Phase documentation:
- [Phase 0: Diagnosis](05-PHASE-0.md)
- [Phase 1: HTML Cleanup](06-PHASE-1.md)
- [Phase 2: Semantic Upgrade](07-PHASE-2.md)
- [Phase 3: Spine Realignment](08-PHASE-3.md)
- [Phase 4: TOC Rebuild](09-PHASE-4.md)
- [Phase 5: Typography](10-PHASE-5.md)
- [Phase 6: CSS Rewrite](11-PHASE-6.md)
- [Phase 7: Validation](12-PHASE-7.md)

---

## 🔗 Functions by Category

### EPUB Analysis

```python
resolve_ncx_path(container_xml, opf_path, zip_file) -> str
extract_spine_items(opf_bytes) -> List[SpineItem]
extract_toc_entries(opf_bytes, ncx_bytes) -> List[TocEntry]
```

### EPUB Manipulation

```python
safe_read(z, zip_key) -> bytes
build_zip_key(opf_base, item_href) -> str
select_parser(filename) -> str
parse_ncx_entries(ncx_bytes) -> List[TocEntry]
```

### File Management

```python
FileManager.finalize(...) -> int
PipelineFileTracker.register_phase_output(...) -> None
PipelineFileTracker.get_phase_input(...) -> str
```

### Pipeline Execution

```python
run_phase0(epub_path, report) -> bool
run_phase1(epub_path, output_path, report) -> bool
# ... etc through run_phase7
```

---

## 📊 Data Structures

### TocEntry

```python
@dataclass
class TocEntry:
    title: str
    href: str
    file_part: str
    anchor: Optional[str]
    level: int
    children: List['TocEntry'] = field(default_factory=list)
    source: str = "detected"
    confidence: float = 1.0
```

**Fields**:
- `title` (str): Display text
- `href` (str): Link (file or file#anchor)
- `file_part` (str): Spine file  
- `anchor` (str|None): Fragment identifier
- `level` (int): Heading level (1-6)
- `children` (list): Nested TOC entries
- `source` (str): Detection method
- `confidence` (float): Quality score (0-1)

### SpineItem

```python
@dataclass
class SpineItem:
    id: str
    href: str
    media_type: str
    properties: Optional[str] = None
    file_path: Optional[str] = None
```

**Fields**:
- `id` (str): Manifest ID
- `href` (str): Relative path
- `media_type` (str): MIME type
- `properties` (str|None): EPUB3 properties
- `file_path` (str|None): Computed ZIP path

### PipelineReport

```python
@dataclass
class PipelineReport:
    epub_version: str
    epub_language: str
    spine_items: int
    original_toc_entries: int
    rebuilt_toc_entries: int
    semantic_headings_detected: int
    injected_anchors: int
    markup_quality: str
    f1_score: Optional[float]
    precision: Optional[float]
    recall: Optional[float]
    phases_executed: List[int]
    execution_time_seconds: float
    errors: List[str]
    warnings: List[str]
    recommendations: List[str]
    se_lint_errors: List[str]
    epubcheck_errors: List[str]
    toc_entries: List[TocEntry]
```

**Methods**:
- `add_error(msg: str)` — Log error
- `add_warning(msg: str)` — Log warning
- `add_recommendation(msg: str)` — Add recommendation

---

## 🧪 Testing Utilities

```python
# test_utils.py
def extract_epub_from_zip(zip_path: str, output_dir: str) -> None
def repack_epub_from_dir(epub_dir: str, output_path: str) -> None
def compare_toc_entries(a: List[TocEntry], b: List[TocEntry]) -> float
def compute_epub_hash(epub_path: str) -> str
```

---

## 📈 Usage Patterns

### Complete Pipeline Run

```python
from toc_fixer.core import PipelineReport
from toc_fixer.pipeline import (
    run_phase0, run_phase1, run_phase2,
    run_phase4, run_phase5, run_phase6, run_phase7
)

report = PipelineReport()
epub_path = "wild.epub"
output_path = "wild_clean.epub"

# Phase 0: Diagnosis
if not run_phase0(epub_path, report):
    print("Phase 0 failed")
    exit(1)

# Phases 1-7: Transformation
phases = [1, 2, 4, 5, 6, 7]  # Skip 3 (optional)
for phase_num in phases:
    phase_func = globals()[f"run_phase{phase_num}"]
    if not phase_func(input_path, output_path, report):
        print(f"Phase {phase_num} failed")
        break
    input_path = output_path  # Chain

print(f"Pipeline complete: {output_path}")
print(f"F1 Score: {report.f1_score:.2f}")
```

### Access Report Data

```python
# Metrics
print(f"Spine items: {report.spine_items}")
print(f"Original TOC: {report.original_toc_entries}")
print(f"Rebuilt TOC: {report.rebuilt_toc_entries}")

# Quality
print(f"Markup quality: {report.markup_quality}")
if report.f1_score:
    print(f"F1 Score: {report.f1_score:.2f}")

# Messages
for error in report.errors:
    print(f"ERROR: {error}")
for warning in report.warnings:
    print(f"WARNING: {warning}")
```

---

## 🔗 Related Documentation

- [Architecture](01-ARCHITECTURE.md) — System overview
- [Data Models](13-DATA-MODELS.md) — Detailed model reference
- [Core Utilities](02-CORE-UTILITIES.md) — Utility function details
- [Pipeline Overview](04-PIPELINE-OVERVIEW.md) — Common patterns

---

**Categories**: [Modules](#-modules) | [Functions](#-functions-by-category) | [Data Structures](#-data-structures) | [Usage](#-usage-patterns)
