# Debugging Guide

Comprehensive debugging strategies and tools for TOC Fixer pipeline.

## 🛠️ Debug Modes

### Enable Debug Output

Preserve intermediate files for inspection:

```bash
python main.py around-the-world.epub --debug-output
```

**Result**:
```
toc-fixer/
├── around-the-world.epub          # Original input
├── around-the-world_clean.epub    # Final output
├── tmp/
│   ├── around-the-world_p1.epub   # Phase 1 output
│   ├── around-the-world_p2.epub   # Phase 2 output
│   ├── around-the-world_p4.epub   # Phase 4 output
│   ├── around-the-world_p5.epub   # Phase 5 output
│   └── around-the-world_p6.epub   # Phase 6 output
└── reports/
    ├── around-the-world_phase0_report.json
    └── around-the-world_phase7_report.json
```

### Generate JSON Reports

Create detailed debug reports for each phase:

```bash
python main.py around-the-world.epub --json-reports
```

**Report Contents**:

**phase0_report.json**:
```json
{
  "epub_version": "3.0",
  "epub_language": "en",
  "spine_items": 42,
  "original_toc_entries": 40,
  "semantic_headings_detected": 37,
  "markup_quality": "partial",
  "ncx_path": "OEBPS/toc.ncx",
  "opf_path": "OEBPS/package.opf",
  "recommendations": ["phase1", "phase2", "phase4", ...]
}
```

**phase7_report.json**:
```json
{
  "original_toc_entries": 40,
  "rebuilt_toc_entries": 37,
  "f1_score": 0.956,
  "precision": 0.941,
  "recall": 0.950,
  "phases_executed": [0, 1, 2, 4, 5, 6, 7],
  "se_lint_errors": [],
  "epubcheck_errors": []
}
```

---

## 🔍 Inspecting Intermediate Files

### Extract EPUB Contents

```bash
# Extract EPUB to folder for inspection
unzip around-the-world_p2.epub -d around-the-world_p2/
```

**Check OPF metadata**:
```bash
cat around-the-world_p2/OEBPS/package.opf
```

**Check NCX structure**:
```bash
cat around-the-world_p2/OEBPS/toc.ncx
```

**Check spine file content**:
```bash
cat around-the-world_p2/OEBPS/ch01.html
```

### Use Calibre's EPUB Editor

Open any EPUB in Calibre and inspect:
- Metadata (right panel → Book details)
- Table of contents (right panel → Table of Contents)
- Spine (bottom panel → Spine)
- Individual files (double-click to open)

---

## 📊 Analyzing Report Data

### Phase 0 Report Analysis

```python
import json

with open("reports/around-the-world_phase0_report.json") as f:
    report = json.load(f)

print(f"Original TOC entries: {report['original_toc_entries']}")
print(f"Semantic headings detected: {report['semantic_headings_detected']}")
print(f"Markup quality: {report['markup_quality']}")
print(f"Recommendations: {', '.join(report['recommendations'])}")

# Markup quality interpretation:
# - "good": Well-formed XHTML, semantic markup
# - "partial": Mix of semantic + non-semantic
# - "poor": Mostly broken markup
```

### Phase 7 Report Analysis

```python
import json

with open("reports/around-the-world_phase7_report.json") as f:
    report = json.load(f)

print(f"TOC entries: {report['original_toc_entries']} → {report['rebuilt_toc_entries']}")
print(f"F1 Score: {report['f1_score']:.3f}")
print(f"Precision: {report['precision']:.3f}")
print(f"Recall: {report['recall']:.3f}")

if report['se_lint_errors']:
    print(f"SE Lint Errors: {len(report['se_lint_errors'])}")
    for error in report['se_lint_errors'][:3]:
        print(f"  - {error}")

if report['epubcheck_errors']:
    print(f"EPUBCheck Errors: {len(report['epubcheck_errors'])}")
```

---

## 🐛 Common Issues & Solutions

### Issue: Phase 0 Reports 0 Original TOC Entries

**Symptoms**:
- `original_toc_entries: 0` in phase0_report.json
- Pipeline skips phases that depend on TOC entries

**Root Causes**:
1. NCX file not found (BUG-1 regression)
2. NCX parsing returns empty (BUG-2 regression)
3. Invalid EPUB structure

**Debug Steps**:
```python
from toc_fixer.core.utils import resolve_ncx_path, parse_ncx_entries
import zipfile

# Step 1: Check NCX path resolution
with zipfile.ZipFile("around-the-world.epub") as z:
    container = z.read("META-INF/container.xml")
    opf_path = "OEBPS/package.opf"  # Usually this
    ncx_path = resolve_ncx_path(container, opf_path, z)
    print(f"NCX path resolved to: {ncx_path}")
    
    # Step 2: Check NCX content
    if ncx_path:
        ncx_bytes = z.read(ncx_path)
        entries = parse_ncx_entries(ncx_bytes)
        print(f"Parsed {len(entries)} TOC entries")
    else:
        print("ERROR: NCX path not found!")
```

**Solutions**:
- Verify `META-INF/container.xml` exists and is valid
- Check `rootfile@full-path` attribute in container.xml
- Ensure `package.opf` references NCX correctly

### Issue: Phase 2 Detects 0 Headings

**Symptoms**:
- `semantic_headings_detected: 0` in phase0_report.json
- TOC rebuild (Phase 4) creates minimal TOC

**Root Causes**:
1. Calibre output with no semantic markup
2. Markup uses non-standard heading methods
3. HTML parser selected incorrectly (BUG-3 regression)

**Debug Steps**:
```python
from bs4 import BeautifulSoup
import zipfile

# Step 1: Check parser selection
from toc_fixer.core.utils import select_parser

filename = "ch01.html"
parser = select_parser(filename)
print(f"Selected parser: {parser}")  # Should be "lxml" not "lxml-xml"

# Step 2: Parse sample file
with zipfile.ZipFile("around-the-world.epub") as z:
    content = z.read("OEBPS/ch01.html")
    soup = BeautifulSoup(content, parser)
    
    # Check for heading tags
    h_tags = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    print(f"Found {len(h_tags)} heading tags")
    
    # Check for bold/strong as heading
    likely_headings = soup.find_all("b")
    print(f"Found {len(likely_headings)} <b> tags (may be headings)")
```

**Solutions**:
- Run Phase 2 to upgrade markup with semantic tags
- Check CSS classes for heuristic patterns (chapter, heading, title, section)
- Verify HTML vs XHTML detection (should be "lxml" for Calibre .html files)

### Issue: Phase 6 Corrupts EPUB

**Symptoms**:
- Input EPUB becomes unreadable after running
- `_clean.epub` is corrupted

**Root Causes**:
- Writing to input file instead of output file (BUG-4 regression)
- ZIP write during read

**Debug Steps**:
```python
# Check Phase 6 implementation
import zipfile

# Verify input file still works
try:
    with zipfile.ZipFile("around-the-world.epub") as z:
        z.testzip()
    print("Input EPUB is valid")
except Exception as e:
    print(f"Input EPUB corrupted: {e}")

# Verify output file
try:
    with zipfile.ZipFile("around-the-world_p6.epub") as z:
        z.testzip()
    print("Output EPUB is valid")
except Exception as e:
    print(f"Output EPUB corrupted: {e}")
```

**Solutions**:
- Verify Phase 6 uses `output_path` parameter, not input file
- Check file handle lifecycle (close before ZIP operations)
- Ensure `shutil.copy2()` executed before modifications

### Issue: Phase 4 TOC Missing Entries

**Symptoms**:
- Original TOC: 40 entries
- Rebuilt TOC: 25 entries
- Missing chapters in output

**Root Causes**:
1. Semantic headings not detected (Phase 2 skipped or failed)
2. TOC entry HREFs incorrect
3. Anchor injection failed

**Debug Steps**:
```python
import json

# Check phase0 report: Were headings detected?
with open("reports/phase0_report.json") as f:
    p0 = json.load(f)
    print(f"Phase 0: {p0['semantic_headings_detected']} headings detected")

# Check phase7 report: How many entries rebuilt?
with open("reports/phase7_report.json") as f:
    p7 = json.load(f)
    print(f"Phase 7: {p7['rebuilt_toc_entries']} entries rebuilt")

# Extract phase 4 output EPUB
import zipfile
with zipfile.ZipFile("around-the-world_p4.epub") as z:
    # Check NCX structure
    ncx = z.read("OEBPS/toc.ncx")
    print(ncx.decode('utf-8'))  # Inspect generated NCX
```

**Solutions**:
- Ensure Phase 2 runs before Phase 4 (semantic headlines are critical)
- Verify anchors injected in spine files (check Phase 2 output)
- Test TOC entry HREFs point to valid files
- Check nav.xhtml generation (EPUB3 format)

---

## 📈 Performance Profiling

### Measure Execution Time

```bash
# Add timing info
time python main.py around-the-world.epub

# Result:
# real    0m12.456s
# user    0m11.123s
# sys     0m1.333s
```

### Profile Specific Phase

```python
import cProfile
import pstats
from io import StringIO
from toc_fixer.pipeline.phase2 import run_phase2
from toc_fixer.core import PipelineReport

# Create profiler
profiler = cProfile.Profile()
report = PipelineReport()

# Run phase with profiling
profiler.enable()
run_phase2("around-the-world_p1.epub", "around-the-world_p2.epub", report)
profiler.disable()

# Print results
stats = pstats.Stats(profiler, stream=StringIO())
stats.strip_dirs()
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

### Memory Profiling

```bash
# Install memory_profiler
pip install memory-profiler

# Run with memory profiling
python -m memory_profiler main.py around-the-world.epub
```

---

## 🔬 Unit Testing for Debugging

### Test Specific Function

```python
import pytest
from toc_fixer.core.utils import build_zip_key

def test_build_zip_key_examples():
    """Test ZIP key construction for various paths"""
    examples = [
        ("OEBPS", "ch01.html", "OEBPS/ch01.html"),
        ("OEBPS", "./ch01.html", "OEBPS/ch01.html"),
        ("OEBPS", "../styles/style.css", "styles/style.css"),
    ]
    
    for base, href, expected in examples:
        result = build_zip_key(base, href)
        print(f"{base} + {href} = {result}")
        assert result == expected, f"Expected {expected}, got {result}"
```

**Run**:
```bash
pytest test_file.py::test_build_zip_key_examples -vv -s
```

---

## 📋 Checklist for Debugging

- [ ] Verify input EPUB is valid (`unzip -t around-the-world.epub`)
- [ ] Check `--json-reports` output for early issues
- [ ] Review phase0_report.json recommendations
- [ ] Extract and inspect intermediate files (`--debug-output`)
- [ ] Verify parser selection (HTML vs XHTML)
- [ ] Check NCX resolution (all 3 methods tested)
- [ ] Confirm Phase 2 semantic markup generated
- [ ] Verify anchor injection in spine files
- [ ] Test TOC entry HREFs are valid
- [ ] Check output EPUB structure with Calibre
- [ ] Run se lint checks vs se lint output
- [ ] Compare F1 score vs ground truth (if available)

---

## 🔗 Related Documentation

- [API Reference](14-API-REFERENCE.md) — Function signatures
- [Testing Guide](15-TESTING.md) — Test strategies
- [Architecture](01-ARCHITECTURE.md) — System overview
- [PLAN.md](../PLAN.md) — Technical specification

---

**Categories**: [Debug Modes](#-debug-modes) | [Common Issues](#-common-issues--solutions) | [Profiling](#-performance-profiling) | [Testing](#-unit-testing-for-debugging)
