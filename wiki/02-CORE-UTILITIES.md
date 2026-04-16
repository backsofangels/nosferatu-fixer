# Core Utilities Reference

Detailed documentation of utility functions in `toc_fixer/core/utils.py`.

## 🔍 EPUB Path Resolution (BUG-1 Fix)

### `resolve_ncx_path(container_xml_bytes, opf_path, zip_file) → str`

Resolves the path to the NCX (table of contents) file from EPUB metadata.

**Problem (BUG-1)**:
- NCX path defined in OPF manifest
- Path relative to OPF location, not ZIP root
- Calibre EPUBs store OPF in subdirectories
- Path resolution failed → 0 TOC entries parsed

**Solution**:
3-method fallback with increasing specificity

### **Method A: Spine toc Attribute**
```python
# From OPF spine element:
<spine version="2.0" toc="ncx_id">

# Look up ncx_id in manifest:
<item id="ncx_id" href="toc.ncx" media-type="application/x-dtbncx+xml">

# Resolve relative to OPF directory:
ncx_path = posixpath.join(opf_dir, href)
```
**When**: Most reliable, works for properly formatted EPUBs
**Confidence**: 1.0

### **Method B: Manifest Media Type**
```python
# Search manifest for NCX media type:
for item in manifest:
    if item.media_type == "application/x-dtbncx+xml":
        return posixpath.join(opf_dir, item.href)
```
**When**: spine toc attribute missing
**Confidence**: 0.9

### **Method C: Heuristic Search**
```python
# Search ZIP for toc.ncx (case-insensitive):
for name in zip_file.namelist():
    if name.lower().endswith("toc.ncx"):
        return name
```
**When**: Methods A & B fail; extremely broken EPUBs
**Confidence**: 0.7

### Usage Example
```python
from toc_fixer.core.utils import resolve_ncx_path
import zipfile

with zipfile.ZipFile("wild.epub") as z:
    container_xml = z.read("META-INF/container.xml")
    ncx_path = resolve_ncx_path(container_xml, "content.opf", z)
    # Returns: "OEBPS/toc.ncx" or "toc.ncx" or similar
```

---

## 📖 NCX Parsing (BUG-2 Fix)

### `parse_ncx_entries(ncx_bytes) → list[TocEntry]`

Parses NCX (EPUB2 table of contents) file.

**Problem (BUG-2)**:
- BeautifulSoup HTML parser ignored XML namespaces
- Returned 0 entries from valid NCX files
- Root cause: HTML parser strips DAISY namespace prefixes

**Solution**:
Use lxml with DAISY namespace support

### Implementation
```python
from lxml import etree

def parse_ncx_entries(ncx_bytes):
    # Parse with lxml (namespace-aware)
    root = etree.fromstring(ncx_bytes)
    
    # Define DAISY namespace
    ns = {"daisy": "http://www.daisy.org/z3986/2005/ncx/"}
    
    # Query with namespace:
    nav_points = root.xpath("//daisy:navPoint", namespaces=ns)
    
    entries = []
    for nav_point in nav_points:
        title = nav_point.xpath(".//daisy:navLabel/daisy:text", 
                               namespaces=ns)[0].text
        href = nav_point.xpath(".//daisy:content/@src", 
                              namespaces=ns)[0]
        level = int(nav_point.get("playOrder", 0))
        
        entries.append(TocEntry(
            title=title,
            href=href,
            level=level,
            source="ncx",
            confidence=1.0
        ))
    
    return entries
```

### Why lxml?
- **BeautifulSoup HTML parser**: Strips namespaces (default)
- **lxml with xml parser**: Preserves namespaces (required)

### Usage Example
```python
from toc_fixer.core.utils import parse_ncx_entries

with zipfile.ZipFile("wild.epub") as z:
    ncx_bytes = z.read("OEBPS/toc.ncx")
    entries = parse_ncx_entries(ncx_bytes)
    # Returns: [TocEntry(...), TocEntry(...), ...]
```

---

## 🗂️ ZIP Key Construction (BUG-3 Fix)

### `build_zip_key(opf_base: str, item_href: str) → str`

Constructs proper ZIP file path for spine items.

**Problem (BUG-3)**:
- Spine manifests have relative paths (e.g., `../OEBPS/c01.html`)
- OPF might be in subdirectory (e.g., `content.opf` or `OEBPS/content.opf`)
- Incorrect path resolution → file not found in ZIP

**Solution**:
Proper relative path normalization

### Algorithm
```python
import posixpath

def build_zip_key(opf_base: str, item_href: str) -> str:
    # Join OPF directory with item href
    zip_key = posixpath.join(opf_base, item_href)
    
    # Normalize (resolve .., ., etc.)
    zip_key = posixpath.normpath(zip_key)
    
    return zip_key
```

### Examples
```
OPF: "content.opf" (in root)
Item href: "OPS/c01.html"
Result: "OPS/c01.html"

OPF: "OEBPS/content.opf"
Item href: "../text/c01.xhtml"
Result: "OEBPS/text/c01.xhtml"

OPF: "dir/content.opf"
Item href: "../../c01.html"
Result: "c01.html"
```

### Usage Example
```python
from toc_fixer.core.utils import build_zip_key

opf_base = "OEBPS"  # Directory of OPF
item_href = "../text/c01.xhtml"  # Relative path from OPF

key = build_zip_key(opf_base, item_href)
# Returns: "OEBPS/text/c01.xhtml"

content = zip_file.read(key)
```

---

## 🔒 Safe ZIP Reading

### `safe_read(z: ZipFile, zip_key: str) → bytes | None`

Case-insensitive ZIP file reading for cross-platform compatibility.

**Problem**:
- Linux ZIP is case-sensitive
- Windows/Mac ZIP is case-insensitive
- Different tools generate inconsistent casing
- Fallback needed for robustness

**Implementation**
```python
def safe_read(z, zip_key: str) -> bytes | None:
    try:
        return z.read(zip_key)
    except KeyError:
        # Case-insensitive fallback
        for name in z.namelist():
            if name.lower() == zip_key.lower():
                return z.read(name)
    return None
```

### When to Use
- Always when reading spine files
- File not found errors → try case-insensitive lookup
- Critical for cross-platform support

### Usage Example
```python
from toc_fixer.core.utils import safe_read

content = safe_read(zip_file, "OEBPS/c01.html")
# Try "OEBPS/c01.html"
# If not found, try "oebps/c01.html", "OEBPS/C01.HTML", etc.
```

---

## 🎨 HTML Parser Selection

### `select_parser(filename: str) → str`

Select appropriate BeautifulSoup parser by file extension.

**Problem (BUG-3 Related)**:
- Calibre generates `.html` files with loose HTML syntax
- lxml HTML parser auto-closes tags (breaks structure)
- XHTML files need strict XML parsing
- `.html` files need permissive HTML parsing

**Solution**:
Extension-based parser selection

### Algorithm
```python
def select_parser(filename: str) -> str:
    if filename.lower().endswith(".xhtml"):
        return "lxml-xml"  # Strict XML for XHTML
    else:
        return "lxml"      # Permissive HTML for .html
```

### Parsers
| Parser | Type | Best For | Tolerates |
|--------|------|----------|-----------|
| `lxml-xml` | Strict | `.xhtml` files | XML-compliant only |
| `lxml` | Permissive | `.html` files | Broken HTML, auto-closes |
| `html.parser` | Fallback | Last resort | Pure Python, slower |

### Usage Example
```python
from toc_fixer.core.utils import select_parser
from bs4 import BeautifulSoup

parser = select_parser("OEBPS/c01.html")
# Returns: "lxml"

soup = BeautifulSoup(content, parser)
# For .xhtml → lxml-xml (strict)
# For .html → lxml (permissive)
```

---

## 📊 Additional Utilities

### `extract_spine_items(opf_bytes: bytes) → list[SpineItem]`
Parse OPF manifest and spine to extract `SpineItem` objects.

### `extract_toc_entries(opf_bytes: bytes, ncx_bytes: bytes) → list[TocEntry]`
Combine OPF and NCX data for initial TOC.

### `posixpath Operations`
All ZIP paths use POSIX separators (/) regardless of OS.

---

## Testing Utilities

### Test Helper Functions
```python
def extract_epub_from_zip(zip_path: str, output_dir: str)
def repack_epub_from_dir(epub_dir: str, output_path: str)
def compare_toc_entries(a: list[TocEntry], b: list[TocEntry]) → float
```

---

## 🔗 Related Documentation

- [Data Models](13-DATA-MODELS.md) — TocEntry, SpineItem structures
- [Architecture](01-ARCHITECTURE.md) — How utilities fit in system
- [Bug Fixes](15-BUG-FIXES.md) — Detailed bug analysis
- [API Reference](14-API-REFERENCE.md) — Complete function signatures

---

**Next**: Read [File Manager](03-FILE-MANAGER.md) to understand file lifecycle management.
