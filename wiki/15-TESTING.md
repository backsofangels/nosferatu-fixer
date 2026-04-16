# Testing Guide

Comprehensive testing strategy for TOC Fixer pipeline.

## 📋 Test Categories

### Unit Tests

**Location**: `tests/unit/`

Individual component testing for core utilities and data models.

```python
# tests/unit/test_utils.py
def test_resolve_ncx_path_method_a():
    """Test NCX resolution via spine toc attribute"""

def test_resolve_ncx_path_method_b():
    """Test NCX resolution via manifest media-type"""

def test_resolve_ncx_path_method_c():
    """Test NCX resolution via heuristic search"""

def test_parse_ncx_entries_lxml():
    """Test NCX parsing with lxml+DAISY namespace"""

def test_build_zip_key_relative_paths():
    """Test ZIP key building with various path formats"""

def test_safe_read_case_insensitive():
    """Test case-insensitive ZIP fallback"""

def test_select_parser_html_vs_xhtml():
    """Test parser selection by extension"""
```

**Run**:
```bash
pytest tests/unit/test_utils.py -v
pytest tests/unit/test_models.py -v
pytest tests/unit/test_file_manager.py -v
```

### Integration Tests

**Location**: `tests/integration/`

Phase-by-phase testing with real EPUB files.

```python
# tests/integration/test_phase_pipeline.py
class TestPhase0Analysis:
    """Phase 0 diagnosis functionality"""
    
    def test_phase0_on_around_the_world(self):
        """Should correctly analyze around-the-world.epub"""
        # Assert: 40 NCX entries detected
        # Assert: 42 semantic headings found
        # Assert: Markup quality: "partial"
    
    def test_phase0_on_lovecraft(self):
        """Should handle Lovecraft EPUB with 480 spine items"""
        # Assert: Not crash on large spine
        # Assert: Correct OPF parsing

class TestPhase1Cleanup:
    """HTML cleanup functionality"""
    
    def test_phase1_removes_calibre_boilerplate(self):
        """Should remove Calibre-generated HTML"""
        # Assert: <div id="calibre..."> removed
        # Assert: Extraneous <p> tags cleaned

class TestPhase2Semantic:
    """Semantic upgrade functionality"""
    
    def test_phase2_detects_headings_all_methods(self):
        """Should use all 6 detection passes"""
        # Assert: Semantic h1-h6 tags detected (pass 1)
        # Assert: CSS class heuristic detected (pass 2)
        # Assert: Bold-as-heading detected (pass 3)
        # Assert: Uppercase heuristic detected (pass 4)
        # Assert: Document title detected (pass 5)
        # Assert: NCX fallback detected (pass 6)
    
    def test_phase2_inject_anchors(self):
        """Should inject anchors for headings"""
        # Assert: Anchors added to <h1-h6> tags
        # Assert: Anchor IDs unique across file

class TestPhase4TOCRebuild:
    """TOC rebuild functionality"""
    
    def test_phase4_generates_ncx_epub2(self):
        """Should generate valid NCX for EPUB2 compat"""
        # Assert: NCX XML parsing succeeds
        # Assert: navLabel entries present
        # Assert: content@src attributes valid

    def test_phase4_generates_nav_xhtml_epub3(self):
        """Should generate valid XHTML nav doc"""
        # Assert: XHTML parsing succeeds
        # Assert: nav@type="toc" present
        # Assert: <a> href attributes valid

class TestPhase7Validation:
    """Validation and scoring functionality"""
    
    def test_phase7_se_lint(self):
        """Should run se lint checks"""
        # Assert: Returns lint error list
        # Assert: Separates blocking vs warnings
    
    def test_phase7_f1_scoring(self):
        """Should compute F1 score vs ground truth"""
        # Assert: F1 score in range [0, 1]
        # Assert: Precision and recall calculated
```

**Run**:
```bash
pytest tests/integration/test_phase_pipeline.py -v
pytest tests/integration/test_around_the_world.py -v
pytest tests/integration/test_lovecraft.py -v
```

### End-to-End Tests

**Location**: `tests/e2e/`

Full pipeline runs with quality assertions.

```python
# tests/e2e/test_pipeline_full.py
def test_full_pipeline_around_the_world():
    """Full pipeline: aw.epub → aw_clean.epub"""
    # Setup: Copy around-the-world.epub to temp
    # Run: All phases 0-7
    # Assert: Output file valid EPUB
    # Assert: Spine structure preserved
    # Assert: TOC entries ≥37
    # Assert: F1 score ≥0.95
    # Assert: se lint errors = 0

def test_full_pipeline_with_ground_truth():
    """Full pipeline with F1 scoring enabled"""
    # Setup: Copy both EPUBs to temp
    # Run: Phases 0-7 with ground-truth comparison
    # Assert: F1 score ≥0.95
    # Assert: Precision ≥0.92
    # Assert: Recall ≥0.92

def test_full_pipeline_debug_mode():
    """Full pipeline with debug output preservation"""
    # Setup: Enable --debug-output flag
    # Run: Phases 0-7
    # Assert: All phase outputs (_p1-p6.epub) created
    # Assert: tmp/ directory contains all files
    # Assert: Phase chaining successful

def test_full_pipeline_realign_spine():
    """Full pipeline with optional spine realignment"""
    # Setup: Enable --realign-spine flag
    # Run: Phases 0-7 including Phase 3
    # Assert: Spine files split at h1 boundaries
    # Assert: Spine item count increased
```

**Run**:
```bash
pytest tests/e2e/test_pipeline_full.py -v
pytest tests/e2e/test_pipeline_with_ground_truth.py -v

# Run all E2E tests
pytest tests/e2e/ -v --tb=short
```

### Regression Tests

**Location**: `tests/regression/`

Tests ensuring known bugs don't resurface.

```python
# tests/regression/test_bug_fixes.py
class TestBug1NCXResolution:
    """BUG-1: NCX path resolution"""
    
    def test_bug1_spine_toc_method(self):
        """Should resolve NCX via spine toc='' attribute"""
    
    def test_bug1_manifest_media_type_method(self):
        """Should resolve NCX via manifest media-type attribute"""
    
    def test_bug1_heuristic_search_method(self):
        """Should fallback to heuristic search"""

class TestBug2NCXParsing:
    """BUG-2: NCX returns 0 entries with BeautifulSoup"""
    
    def test_bug2_lxml_with_daisy_namespace(self):
        """Should use lxml with DAISY namespace registration"""
    
    def test_bug2_returns_nonzero_entries(self):
        """Should return >0 entries from valid NCX"""

class TestBug3SpineZIPAccess:
    """BUG-3: Spine ZIP keys wrong, .html parsed as XHTML"""
    
    def test_bug3_html_parser_selection(self):
        """Should select lxml for .html files"""
    
    def test_bug3_xhtml_parser_selection(self):
        """Should select lxml-xml for .xhtml files"""
    
    def test_bug3_zip_key_construction(self):
        """Should build correct ZIP keys"""

class TestBug4Phase6FileCorruption:
    """BUG-4: Phase 6 corrupts input file"""
    
    def test_bug4_phase6_preserves_input(self):
        """Should not modify input EPUB"""
    
    def test_bug4_write_to_output_only(self):
        """Should write only to output_path"""

class TestBug5Phase3FileCorruption:
    """BUG-5: Phase 3 had same corruption issue"""
    
    def test_bug5_phase3_preserves_input(self):
        """Should not modify input EPUB"""
```

**Run**:
```bash
pytest tests/regression/test_bug_fixes.py -v
```

---

## 🧪 Test EPUBs

### Primary Test EPUBs

| EPUB | Source | Size | Spine | TOC | Purpose |
|------|--------|------|-------|-----|---------|
| `around-the-world.epub` | Calibre | ~2.5MB | 42 | 40 NCX | Main test input |
| `jules-verne_...epub` | Standard Ebooks | ~1.8MB | 40 | 40 XML | Ground truth / F1 scoring |
| `lovecraft.epub` | Gutenberg | ~5.2MB | 480+ | Rich | Large spike test |

### Test EPUB Characteristics

**around-the-world.epub**:
- Calibre-generated (poor markup)
- 40 NCX entries vs 42 actual headings
- Mix of semantic + non-semantic headings
- Ideal for general testing

**jules-verne (SE ground truth)**:
- Standard Ebooks quality
- Properly semantic markup
- Correct TOC structure
- Used for F1 score computation

**lovecraft.epub**:
- Large spine (480+ items)
- Complex structure
- Tests performance and scalability

---

## 🚀 Running Tests

### Quick Test (5 min)

```bash
# Unit tests only
pytest tests/unit/ -q
```

### Standard Test (15 min)

```bash
# Unit + Integration
pytest tests/unit/ tests/integration/test_phase_pipeline.py -v
```

### Full Test Suite (30 min)

```bash
# Everything
pytest tests/ -v --tb=short
```

### Test Specific Phase

```bash
pytest tests/integration/test_phase_pipeline.py::TestPhase2Semantic -v
pytest tests/integration/test_phase_pipeline.py::TestPhase4TOCRebuild -v
pytest tests/integration/test_phase_pipeline.py::TestPhase7Validation -v
```

### Test with Coverage

```bash
pytest tests/ --cov=toc_fixer --cov-report=html
# Open htmlcov/index.html
```

### Performance Test

```bash
pytest tests/e2e/test_pipeline_full.py -v --durations=10
```

---

## 📊 Test Metrics

### Coverage Targets

| Module | Target | Current |
|--------|--------|---------|
| core/utils.py | 95% | TBD |
| core/models.py | 90% | TBD |
| pipeline/phase0.py | 85% | TBD |
| pipeline/phase2.py | 90% | TBD |
| **Overall** | **90%** | TBD |

### Performance Targets

| Phase | Timeout | Target | Current |
|-------|---------|--------|---------|
| Phase 0 | 10s | <2s | TBD |
| Phase 1 | 30s | <5s | TBD |
| Phase 2 | 60s | <10s | TBD |
| Phase 4 | 30s | <3s | TBD |
| Phase 5 | 30s | <4s | TBD |
| Phase 6 | 30s | <3s | TBD |
| Phase 7 | 60s | <5s | TBD |
| **Full Pipeline** | 300s | <40s | TBD |

### Quality Gates

- ✅ All tests pass
- ✅ Coverage ≥90%
- ✅ No regressions
- ✅ F1 score ≥0.95 on ground truth
- ✅ se lint errors = 0 (blocking) on output

---

## 🔍 Debugging Tests

### Run with Verbose Output

```bash
pytest tests/integration/test_phase_pipeline.py::TestPhase2Semantic -vv
```

### Run with Python Debugger

```bash
pytest tests/unit/test_utils.py --pdb
# Drops into debugger on failure
```

### Keep Temporary Files

```bash
pytest tests/e2e/test_pipeline_full.py -v --keep-tmp
# Preserves /tmp/test_* directories for inspection
```

### Print Debug Info

```python
def test_phase2_detects_headings():
    report = PipelineReport()
    # ... test code ...
    if VERBOSE:
        print(f"Semantic headings: {report.semantic_headings_detected}")
        for entry in report.toc_entries:
            print(f"  {entry.title} ({entry.source}, confidence={entry.confidence})")
```

Run with:
```bash
pytest test_file.py -vv -s  # -s shows print statements
```

---

## 📝 Writing New Tests

### Test Template

```python
import pytest
from toc_fixer.core import TocEntry, PipelineReport
from toc_fixer.pipeline import run_phase2

class TestNewFeature:
    """Description of what feature is being tested"""
    
    @pytest.fixture
    def sample_epub(self, tmp_path):
        """Setup: Return path to sample EPUB"""
        epub_path = tmp_path / "test.epub"
        # ... copy/create test EPUB ...
        return str(epub_path)
    
    def test_behavior_under_condition(self, sample_epub):
        """Should do X when Y"""
        # Setup
        report = PipelineReport()
        
        # Execute
        result = run_phase2(sample_epub, "output.epub", report)
        
        # Assert
        assert result is True
        assert len(report.toc_entries) > 0
        assert report.semantic_headings_detected >= 10
    
    def test_error_handling(self):
        """Should handle invalid input gracefully"""
        # Setup: Invalid EPUB
        # Execute: Call phase with bad input
        # Assert: Returns False, adds to report.errors
        pass
```

### Best Practices

1. **One assertion per test**: Or group related assertions with comments
2. **Descriptive names**: `test_phase2_detects_bold_as_heading_with_confidence()`
3. **Use fixtures**: Share setup across tests via `@pytest.fixture`
4. **Test both success + error paths**: Happy path + edge cases
5. **Don't rely on file system**: Use `tmp_path` fixture for isolation
6. **Comment complex assertions**: Explain why the assertion matters

---

## 🔗 Related Documentation

- [Architecture](01-ARCHITECTURE.md) — System overview
- [API Reference](14-API-REFERENCE.md) — Complete API docs
- [Debugging Guide](16-DEBUGGING.md) — Troubleshooting strategies

---

**Categories**: [Test Categories](#-test-categories) | [Test EPUBs](#-test-epubs) | [Running Tests](#-running-tests) | [Writing Tests](#-writing-new-tests)
