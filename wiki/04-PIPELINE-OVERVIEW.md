# Pipeline Overview

Understanding common patterns and architecture used across all 7 phases.

## 🔄 Phase Pattern

Every phase follows the same structure for consistency and robustness.

### Standard Phase Template

```python
# nosferatu-fixer/pipeline/phaseN.py

import subprocess
from pathlib import Path
from zipfile import ZipFile
from ..core import PipelineReport
from ..core.utils import build_zip_key, safe_read

class PhaseNTransformer:
    """Phase N: [Description]"""
    
    def __init__(self, epub_path: str, output_path: str, report: PipelineReport):
        self.epub_path = epub_path
        self.output_path = output_path
        self.report = report
    
    def run_phase(self) -> bool:
        """Main entry point for phase"""
        try:
            # Try SE Tool first (preferred)
            success = self._try_se_tool()
            if success:
                return True
        except Exception as e:
            # Log but continue to fallback
            self.report.add_warning(f"SE tool failed: {str(e)}")
        
        # Fall back to custom implementation
        try:
            return self._custom_implementation()
        except Exception as e:
            self.report.add_error(f"Phase N custom: {str(e)}")
            return False
    
    def _try_se_tool(self) -> bool:
        """Try Standard Ebooks tool via subprocess"""
        # Create temp extraction directory
        epub_dir = Path(f".tmp_epub_phaseN_{Path(self.epub_path).stem}")
        
        try:
            # Extract EPUB
            self._extract_epub(epub_dir)
            
            # Run SE tool
            result = subprocess.run(
                ["se", "tool-name", str(epub_dir)],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                self.report.add_warning(f"SE tool returned {result.returncode}")
                return False
            
            # Repack and verify
            self._repack_epub(epub_dir)
            return True
        except FileNotFoundError:
            self.report.add_warning("SE tool not installed")
            return False
        finally:
            # Clean up temp directory
            import shutil
            shutil.rmtree(epub_dir, ignore_errors=True)
    
    def _custom_implementation(self) -> bool:
        """Custom Python implementation (fallback)"""
        epub_dir = Path(f".tmp_epub_phaseN_custom_{Path(self.epub_path).stem}")
        
        try:
            # Extract EPUB
            self._extract_epub(epub_dir)
            
            # Process content
            self._process_content(epub_dir)
            
            # Repack EPUB
            self._repack_epub(epub_dir)
            
            return True
        finally:
            # Clean up
            import shutil
            shutil.rmtree(epub_dir, ignore_errors=True)
    
    def _extract_epub(self, target_dir: Path):
        """Extract EPUB ZIP to directory"""
        target_dir.mkdir(parents=True, exist_ok=True)
        with ZipFile(self.epub_path, 'r') as z:
            z.extractall(target_dir)
    
    def _process_content(self, epub_dir: Path):
        """Transform EPUB content (phase-specific)"""
        # Phase-specific logic here
        pass
    
    def _repack_epub(self, epub_dir: Path):
        """Repack directory back to EPUB ZIP"""
        with ZipFile(self.output_path, 'w', compression=8) as z:
            for file_path in sorted(epub_dir.rglob('*')):
                if file_path.is_file():
                    arcname = file_path.relative_to(epub_dir)
                    # Normalize path separators
                    arcname = arcname.as_posix()
                    z.write(file_path, arcname)

def run_phaseN(epub_path: str, output_path: str, report: PipelineReport) -> bool:
    """Entry point for Phase N"""
    transformer = PhaseNTransformer(epub_path, output_path, report)
    success = transformer.run_phase()
    
    if success:
        report.phases_executed.append(N)
    
    return success
```

---

## 🔌 SE Tool Integration Pattern

All phases that have SE tools follow this pattern:

### 1. Check Tool Availability
```python
try:
    result = subprocess.run(["se", "--version"], capture_output=True, timeout=5)
except FileNotFoundError:
    # Tool not installed, use fallback
```

### 2. Run with Timeout
```python
result = subprocess.run(
    ["se", "command", str(epub_dir)],
    capture_output=True,
    text=True,
    timeout=300  # 5 minutes
)
```

### 3. Check Exit Code
```python
if result.returncode == 0:
    # Success - continue with output
else:
    # Failure - log and fall back
    self.report.add_warning(f"SE tool returned: {result.stderr}")
    return False  # Will trigger custom fallback
```

### 4. Repack Result
```python
# SE tool modifies in-place, so repack same directory
self._repack_epub(epub_dir)
```

---

## 📥 Input/Output Handling

### Input Strategy
```python
def get_input_epub(phase_num: int, tracker, original_input: str) -> str:
    """Get input for this phase"""
    # Phases 1 onward use previous phase output
    if phase_num > 0:
        return tracker.get_phase_input(phase_num)
    # Phase 0 always uses original input
    return original_input
```

### Output Strategy
```python
def get_output_epub(phase_num: int, stem: str, tmp_dir: Path) -> str:
    """Get output path for this phase"""
    return str(tmp_dir / f"{stem}_p{phase_num}.epub")
```

---

## 🔗 Phase Chaining

Phases are chained through PipelineFileTracker:

```
Phase 0 (input.epub)
  └─ Output: phase0_report.json

Phase 1 (input.epub)
  └─ Output: tmp/input_p1.epub

Phase 2 (tmp/input_p1.epub) ← gets from tracker
  └─ Output: tmp/input_p2.epub

Phase 3 [OPTIONAL - requires --realign-spine AND Phase 2 success]
  └─ Output: tmp/input_p3.epub

Phase 4 (tmp/input_p3.epub or tmp/input_p2.epub) ← skips Phase 3 input if not run
  └─ Output: tmp/input_p4.epub

... etc
```

---

## ⚠️ Error Handling Philosophy

**No exceptions propagate to CLI**: All errors logged to report

```python
# WRONG: Throws exception, crashes pipeline
x = spine_items[10]  # KeyError if < 10 items

# RIGHT: Graceful handling, continues
if len(spine_items) > 10:
    process(spine_items[10])
else:
    self.report.add_warning(f"Expected 10+ items, got {len(spine_items)}")
    # Continue without this item
```

---

## 📊 Report Updates

Each phase updates the shared report:

```python
# Phase X records what it did
report.phases_executed.append(X)

# Phase X records findings
report.semantic_headings_detected = 37
report.injected_anchors = 24

# Phase X notes issues
report.add_warning("Phase 2: 3 headings have low confidence")
report.add_error("Phase 2: NCX entry 'Part 3' not found")

# Phase 7 adds final metrics
report.f1_score = 0.97
report.se_lint_errors = []
```

---

## 🧪 Phase Testing Pattern

Each phase has corresponding tests:

```python
# test_phaseN.py

import pytest
from toc_fixer.pipeline.phaseN import run_phaseN
from toc_fixer.core import PipelineReport

def test_phaseN_basic(test_epub_path, tmp_path):
    """Test basic Phase N operation"""
    output = tmp_path / "output.epub"
    report = PipelineReport()
    
    success = run_phaseN(str(test_epub_path), str(output), report)
    
    assert success
    assert output.exists()
    # Phase-specific assertions
    assert output.stat().st_size > 0

def test_phaseN_se_tool_fallback(test_epub_path, tmp_path, monkeypatch):
    """Test fallback when SE tool fails"""
    # Simulate SE tool failure
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("se not found")
    
    monkeypatch.setattr("subprocess.run", fake_run)
    
    output = tmp_path / "output.epub"
    report = PipelineReport()
    
    success = run_phaseN(str(test_epub_path), str(output), report)
    
    # Should still succeed using custom implementation
    assert success
    assert output.exists()
```

---

## 🔐 Security & Robustness

### ZIP Safety
```python
# Always use safe_read for cross-platform compatibility
content = safe_read(zip_file, "OEBPS/c01.html")
if content is None:
    self.report.add_error("Could not read spine file")
    return False
```

### Path Normalization
```python
# Always use posixpath for ZIP paths (never backslashes)
import posixpath
zip_key = posixpath.join(opf_dir, item_href)
zip_key = posixpath.normpath(zip_key)
```

### Encoding Safety
```python
# Detect encoding before parsing
from chardet import detect

raw = z.read(file_path)
encoding = detect(raw)['encoding'] or 'utf-8'
try:
    text = raw.decode(encoding)
except:
    text = raw.decode('utf-8', errors='ignore')
```

---

## 🎯 Common Operations

### Reading a Spine File

```python
from toc_fixer.core.utils import build_zip_key, safe_read, select_parser

# Build ZIP key (relative to OPF directory)
opf_dir = "OEBPS"
zip_key = build_zip_key(opf_dir, "c01.html")

# Read with fallback
with ZipFile(epub_path) as z:
    content = safe_read(z, zip_key)
    if content is None:
        self.report.add_error(f"Could not read {zip_key}")
        return False

# Parse with correct parser
from bs4 import BeautifulSoup
parser = select_parser("c01.html")  # "lxml" for .html, "lxml-xml" for .xhtml
soup = BeautifulSoup(content, parser)
```

### Modifying Content

```python
# Find elements
headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

# Modify
for h in headings:
    # Make changes
    h.attrs['class'] = ['chapter-heading']

# Write back
modified_content = str(soup)
```

### Handling Namespaces

```python
# For XHTML with namespaces
from lxml import etree

root = etree.fromstring(content)
ns = {"x": "http://www.w3.org/1999/xhtml"}

# Query with namespace
headings = root.xpath("//x:h1", namespaces=ns)
```

---

## 🚀 Performance Considerations

### File I/O
```python
# Batch operations when possible
files_to_process = list(epub_dir.glob("OEBPS/*.html"))  # Single glob
for file_path in files_to_process:
    # Process each file
```

### Memory
```python
# For large files, process in chunks
chunk_size = 8192
for i in range(0, len(content), chunk_size):
    chunk = content[i:i+chunk_size]
    # Process chunk
```

### Compression
```python
# ZIP compression reduces size (usually helps)
with ZipFile(output_path, 'w', compression=8) as z:  # 8 = ZIP_DEFLATED
    z.write(file_path, arcname)
```

---

## 📚 Phase Checklist

When implementing a new phase, ensure:

- [ ] Follows standard template structure
- [ ] Has `run_phaseN()` entry point
- [ ] Tries SE tool, falls back to custom
- [ ] Reports errors/warnings (no exceptions)
- [ ] Updates report.phases_executed
- [ ] Handles missing/broken files gracefully
- [ ] Repacks EPUB with proper compression
- [ ] Cleans up temp directories
- [ ] Has unit tests
- [ ] Tested with all 3 test EPUBs
- [ ] Documentation in wiki/0N-PHASE-N.md

---

## 🔗 Related Documentation

- [Architecture](01-ARCHITECTURE.md) — System overview
- [Core Utilities](02-CORE-UTILITIES.md) — Helper functions
- [File Manager](03-FILE-MANAGER.md) — File lifecycle
- [Phase Guides](05-PHASE-0.md) — Individual phase details
- [Contributing](16-CONTRIBUTING.md) — How to implement

---

**Next**: Read individual [Phase Guides](05-PHASE-0.md) for specific implementations.
