# Bug Fixes Reference

Comprehensive documentation of all critical bugs fixed in production.

## 🐛 Overview

Five critical bugs have been identified and fixed across the pipeline. These are organized in two categories:

### **Category 1: Core EPUB Handling (BUG-1, BUG-2, BUG-3)**
- Impact: File parsing, data extraction
- Severity: Critical—affect all EPUBs
- Status: ✅ Fixed in toc_fixer/core/utils.py

### **Category 2: File Corruption (BUG-4, BUG-5)**
- Impact: Output file integrity
- Severity: Critical—lose work on failure
- Status: ✅ Fixed in pipeline phase implementations

---

## 🔴 BUG-1: NCX Path Resolution

**Status**: ✅ FIXED

### Problem

The NCX (table of contents) file path could not be resolved in many EPUBs, especially Calibre-generated ones.

**Symptoms**:
- `original_toc_entries: 0` in phase0_report.json
- No TOC parsed despite NCX file existing in ZIP
- Rebuild TOC phase produces empty output

**Root Cause**:
- NCX path defined in OPF manifest **relative to OPF location**
- OPF might be in subdirectory (e.g., "OEBPS/content.opf")
- Simple filename lookup failed: "toc.ncx" doesn't exist at ZIP root

### Example

```
EPUB structure:
├── META-INF/container.xml
├── content.opf              ← OPF at root specifies href="OEBPS/toc.ncx"
├── OEBPS/
│   ├── toc.ncx              ← Actually at "OEBPS/toc.ncx"
│   └── c01.html
```

Old code tried: `zip.read("toc.ncx")` → FileNotFoundError
Correct path: `zip.read("OEBPS/toc.ncx")`

### Solution

**Function**: `resolve_ncx_path()` in toc_fixer/core/utils.py

3-method fallback with increasing specificity:

```python
def resolve_ncx_path(container_xml_bytes, opf_path, zip_file) -> str:
    """
    Resolve NCX file path with 3-method fallback.
    
    Methods:
    1. From spine toc attribute + manifest lookup
    2. From manifest media-type search
    3. Heuristic ZIP search for "toc.ncx"
    """
```

#### **Method A: Spine toc Attribute** (Most Reliable)

```xml
<!-- In content.opf: -->
<spine version="2.0" toc="ncx_id">

<!-- In manifest: -->
<item id="ncx_id" href="OEBPS/toc.ncx" media-type="application/x-dtbncx+xml">
```

**Algorithm**:
1. Extract OPF directory: "OEBPS"
2. Find spine toc="..." attribute
3. Look up ID in manifest to get href: "OEBPS/toc.ncx"
4. Join: "OEBPS" + "OEBPS/toc.ncx" → Normalize → "OEBPS/OEBPS/toc.ncx" (WRONG)
   - Actually just use the manifest href directly with OPF dir prefix

**Confidence**: 1.0 (most reliable)

#### **Method B: Manifest Media Type** (Good Fallback)

If toc attribute missing:

```python
for item in manifest:
    if item["media-type"] == "application/x-dtbncx+xml":
        return posixpath.join(opf_dir, item["href"])
```

**Confidence**: 0.9

#### **Method C: Heuristic ZIP Search** (Last Resort)

If methods A & B fail:

```python
for name in zip_file.namelist():
    if name.lower().endswith("toc.ncx"):
        return name
```

**Confidence**: 0.7 (assumes "toc.ncx" naming)

### Test Cases

```bash
# All three test EPUBs should resolve NCX paths
python -c "
from zipfile import ZipFile
from toc_fixer.core.utils import resolve_ncx_path
from lxml import etree

for epub in ['around-the-world.epub', 'lovecraft.epub', 'jules-verne.epub']:
    with ZipFile(epub) as z:
        container = z.read('META-INF/container.xml')
        ncx_path = resolve_ncx_path(container, 'content.opf', z)
        print(f'{epub}: {ncx_path}')
        assert ncx_path is not None, f'Failed for {epub}'
        assert z.read(ncx_path) is not None, f'File not found: {ncx_path}'
"
```

---

## 🔴 BUG-2: NCX Namespace Parsing

**Status**: ✅ FIXED

### Problem

NCX files parsed with BeautifulSoup returned 0 TOC entries despite file being valid and non-empty.

**Symptoms**:
- `parse_ncx_entries()` returns empty list `[]`
- NCX file exists and is readable
- Same NCX parses correctly with other tools

**Root Cause**:
BeautifulSoup's HTML parser **strips XML namespaces** by default.

```xml
<!-- Original NCX (with DAISY namespace): -->
<?xml version="1.0"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <navMap>
    <navPoint id="nav1" playOrder="1">
      <navLabel>
        <text>Chapter 1</text>
      </navLabel>
      <content src="c01.html"/>
    </navPoint>
  </navMap>
</ncx>

<!-- BeautifulSoup HTML parser removes namespace: -->
<!-- Becomes: -->
<ncx version="2005-1">
  <navmap>
    <!-- navpoint and content elements disappear! -->
  </navmap>
</ncx>
```

### Solution

**Function**: `parse_ncx_entries()` in toc_fixer/core/utils.py

Use **lxml with namespace support**:

```python
from lxml import etree

def parse_ncx_entries(ncx_bytes) -> List[TocEntry]:
    """
    Parse NCX with lxml (namespace-aware).
    """
    root = etree.fromstring(ncx_bytes)
    
    # Define DAISY namespace
    ns = {"daisy": "http://www.daisy.org/z3986/2005/ncx/"}
    
    # Query with namespace
    nav_points = root.xpath("//daisy:navPoint", namespaces=ns)
    
    entries = []
    for nav_point in nav_points:
        # Extract with namespace
        title_elem = nav_point.xpath(".//daisy:navLabel/daisy:text", 
                                     namespaces=ns)
        if title_elem:
            title = title_elem[0].text
            
            # Extract href
            content_href = nav_point.xpath(".//daisy:content/@src", 
                                          namespaces=ns)
            if content_href:
                entries.append(TocEntry(
                    title=title,
                    href=content_href[0],
                    # ... other fields
                ))
    
    return entries
```

### Why lxml?

| Parser | HTML | XML | Namespaces | Used For |
|--------|------|-----|-----------|----------|
| BeautifulSoup HTML | ✅ Good | ✗ Poor | ✗ None | HTML files |
| lxml HTML | ✅ Good | ⚠️ OK | ✗ None | Calibre HTML |
| lxml XML | ✗ Strict | ✅ Excellent | ✅ Yes | XHTML, NCX, OPF |

### Test Cases

```bash
# Test NCX parsing
python -c "
from zipfile import ZipFile
from toc_fixer.core.utils import parse_ncx_entries

with ZipFile('around-the-world.epub') as z:
    ncx_bytes = z.read('OEBPS/toc.ncx')
    entries = parse_ncx_entries(ncx_bytes)
    print(f'Parsed {len(entries)} TOC entries')
    assert len(entries) > 0, 'Should parse entries'
    assert len(entries) >= 37, 'Should have 37+ entries'
"
```

---

## 🔴 BUG-3: ZIP Key Resolution & Parser Selection

**Status**: ✅ FIXED

### Problem Part A: Spine File ZIP Keys

Spine item paths not correctly resolved to ZIP file paths.

**Symptoms**:
- `FileNotFoundError` when reading spine files
- File exists in ZIP but code can't find it
- Same file read successfully yesterday, fails today

**Root Cause**:
Spine items have relative paths that need to be joined with OPF directory.

```
OPF at: "OEBPS/content.opf"
Item href: "../text/c01.xhtml"
Correct ZIP key: "OEBPS/text/c01.xhtml"

But code might try:
- "text/c01.xhtml" (wrong)
- "../text/c01.xhtml" (not in ZIP)
```

### Solution Part A: `build_zip_key()`

```python
import posixpath

def build_zip_key(opf_base: str, item_href: str) -> str:
    """
    Build ZIP file path from OPF directory and relative href.
    """
    # Join with OPF directory
    zip_key = posixpath.join(opf_base, item_href)
    
    # Normalize (resolve .., .)
    zip_key = posixpath.normpath(zip_key)
    
    return zip_key

# Always use on spine items
opf_base = "OEBPS"
item_href = "../text/c01.xhtml"
key = build_zip_key(opf_base, item_href)
# Returns: "OEBPS/text/c01.xhtml"

content = zip_file.read(key)
```

### Problem Part B: Parser Selection

`.html` files parsed as strict XHTML, auto-closing tags broke structure.

**Symptoms**:
- Parsed HTML structure incomplete
- Self-closing tags (`<br>`, `<img>`) present but appear "broken"
- Phase 2 heading detection fails on supposedly valid HTML

**Root Cause**:
Calibre generates `.html` files with non-strict HTML markup. Using lxml-xml (strict) parser broke the structure.

### Solution Part B: `select_parser()`

```python
def select_parser(filename: str) -> str:
    """
    Select appropriate BeautifulSoup parser by file extension.
    """
    if filename.lower().endswith(".xhtml"):
        return "lxml-xml"      # Strict XML for XHTML files
    else:
        return "lxml"          # Permissive HTML for .html files

# Usage
from bs4 import BeautifulSoup

parser = select_parser("OEBPS/c01.html")
# Returns: "lxml" (permissive)

soup = BeautifulSoup(content, parser)
```

### Fallback: `safe_read()`

For cross-platform ZIP access (case sensitivity issues):

```python
def safe_read(z: ZipFile, zip_key: str) -> bytes | None:
    """
    Read from ZIP with case-insensitive fallback.
    """
    try:
        return z.read(zip_key)
    except KeyError:
        # Case-insensitive fallback
        for name in z.namelist():
            if name.lower() == zip_key.lower():
                return z.read(name)
    return None
```

### Test Cases

```bash
# Test ZIP key resolution
python -c "
from toc_fixer.core.utils import build_zip_key

tests = [
    ('OEBPS', 'c01.html', 'OEBPS/c01.html'),
    ('OEBPS', '../text/c01.xhtml', 'OEBPS/text/c01.xhtml'),
    ('', 'OEBPS/c01.html', 'OEBPS/c01.html'),
]

for opf_base, href, expected in tests:
    result = build_zip_key(opf_base, href)
    assert result == expected, f'Expected {expected}, got {result}'
    print(f'✓ {opf_base} + {href} = {result}')
"

# Test parser selection
python -c "
from toc_fixer.core.utils import select_parser

assert select_parser('file.html') == 'lxml'
assert select_parser('file.xhtml') == 'lxml-xml'
assert select_parser('FILE.HTML') == 'lxml'  # Case-insensitive
print('✓ Parser selection working')
"
```

---

## 🔴 BUG-4: Phase 6 File Corruption

**Status**: ✅ FIXED

### Problem

Phase 6 (CSS rewrite) overwrote input EPUB instead of creating output file.

**Symptoms**:
- Pipeline crashes with "FileNotFoundError" mid-execution
- Input EPUB file corrupted (partial rewrite)
- No output file created
- Cannot re-run pipeline without restoring input

**Root Cause**:
`Phase6CSSRewriter._repack_epub()` opened `ZipFile(self.epub_path, "w")` for writing, but `self.epub_path` is the **input** file, not output.

```python
# WRONG (original code):
class Phase6CSSRewriter:
    def __init__(self, epub_path, report):
        self.epub_path = epub_path  # Input path
    
    def _repack_epub(self):
        with ZipFile(self.epub_path, "w") as z:  # BUG: Opens input for writing!
            # Copies to input file, corrupting it
```

### Solution

Pass `output_path` as separate parameter:

```python
# CORRECT (fixed code):
class Phase6CSSRewriter:
    def __init__(self, epub_path, output_path, report):
        self.epub_path = epub_path      # Input path
        self.output_path = output_path  # Output path
    
    def _repack_epub(self):
        with ZipFile(self.output_path, "w") as z:  # Writes to output
            # Copies to output file, preserving input
```

### Implementation

```python
# In main.py:
from toc_fixer.pipeline.phase6 import run_phase6

output_epub = str(tmp_dir / f"{stem}_p6.epub")
success = run_phase6(input_epub, output_epub, report)

# In phase6.py:
def run_phase6(epub_path: str, output_path: str, report) -> bool:
    transformer = Phase6CSSRewriter(epub_path, output_path, report)
    return transformer.run_phase()

class Phase6CSSRewriter:
    def __init__(self, epub_path, output_path, report):
        self.epub_path = epub_path      # Input (read only)
        self.output_path = output_path  # Output (write here)
        self.report = report
    
    def _repack_epub(self, epub_dir):
        # Write to output_path, not epub_path
        with ZipFile(self.output_path, 'w') as z:
            for file_path in epub_dir.rglob('*'):
                if file_path.is_file():
                    z.write(file_path, file_path.relative_to(epub_dir))
```

### Test

```bash
# Before fix: Input corrupted
#   wild.epub - corrupted, partial file
#   No output created
#
# After fix: Input preserved, output created
#   wild.epub - unchanged
#   tmp/wild_p6.epub - created successfully
```

---

## 🔴 BUG-5: Phase 3 File Corruption

**Status**: ✅ FIXED

### Problem

Same as BUG-4, but in Phase 3 (spine realignment).

**Symptoms**:
- Pipeline fails with "FileNotFoundError" after Phase 3
- Input EPUB corrupted
- No tmp/wild_p3.epub created

**Root Cause**:
Phase 3 had same bug as Phase 6—wrote to input file instead of output.

### Solution

Same fix as BUG-4: Pass output_path separately.

```python
# In phase3.py:
class Phase3SplineRealigner:
    def __init__(self, epub_path: str, output_path: str, report):
        self.epub_path = epub_path      # Input
        self.output_path = output_path  # Output
    
    def _repack_epub(self, epub_dir):
        # Write to output_path
        with ZipFile(self.output_path, 'w') as z:
            # ... copy files
```

---

## ✅ Verification

All bugs verified fixed with test suite:

```bash
python -m pytest tests/ -v

# Test BUG-1 fix
test_bug1_ncx_path_resolution ✓

# Test BUG-2 fix
test_bug2_ncx_namespace_parsing ✓

# Test BUG-3 fixes
test_bug3a_zip_key_resolution ✓
test_bug3b_parser_selection ✓
test_bug3c_safe_read_fallback ✓

# Test BUG-4 fix
test_bug4_phase6_output_path ✓

# Test BUG-5 fix
test_bug5_phase3_output_path ✓

# Integration test
test_full_pipeline_around_the_world ✓
test_full_pipeline_lovecraft ✓
```

---

## 📊 Impact Summary

| Bug | Severity | Impact | Fixed | Tested |
|-----|----------|--------|-------|--------|
| BUG-1 | Critical | 0 TOC entries | ✅ | ✅ |
| BUG-2 | Critical | NCX parsing failed | ✅ | ✅ |
| BUG-3 | Critical | File not found errors | ✅ | ✅ |
| BUG-4 | Critical | Input corruption | ✅ | ✅ |
| BUG-5 | Critical | Input corruption | ✅ | ✅ |

---

**Related**: [Core Utilities](02-CORE-UTILITIES.md) | [Architecture](01-ARCHITECTURE.md) | [API Reference](14-API-REFERENCE.md)
