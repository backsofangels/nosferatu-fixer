# Phase 0: Diagnosis

**Purpose**: Analyze EPUB structure and quality without modifications.

**Input**: Wild EPUB (Gutenberg/Calibre-generated)
**Output**: phase0_report.json + PipelineReport with recommendations
**Modifies EPUB**: ✗ No
**Optional**: ✗ Always runs

## 🎯 Overview

Phase 0 is the foundation of the pipeline. It:
1. Analyzes EPUB structure (version, language, spine count)
2. Detects existing semantic structure (headings)
3. Reads original TOC (NCX/nav.xhtml)
4. Assesses markup quality
5. Makes **recommendations** for which subsequent phases to run
6. Generates phase0_report.json for user review

## 📚 Implementation

Located in `nosferatu-fixer/pipeline/phase0.py`

### Class: Phase0Analyzer

```python
class Phase0Analyzer:
    """Analyze EPUB structure and quality"""
    
    def __init__(self, epub_path: str, report: PipelineReport):
        self.epub_path = epub_path
        self.report = report
    
    def run_phase(self) -> bool:
        """Main analysis entry point"""
        try:
            with ZipFile(self.epub_path, 'r') as z:
                # Analyze each component
                self._analyze_metadata(z)
                self._analyze_spine(z)
                self._analyze_toc(z)
                self._analyze_markup_quality(z)
                self._generate_recommendations()
            
            return True
        except Exception as e:
            self.report.add_error(f"Phase 0 analysis failed: {str(e)}")
            return False
    
    # Individual analysis methods
    def _analyze_metadata(self, z: ZipFile): ...
    def _analyze_spine(self, z: ZipFile): ...
    def _analyze_toc(self, z: ZipFile): ...
    def _analyze_markup_quality(self, z: ZipFile): ...
    def _generate_recommendations(self): ...
```

## 🔍 Analysis Components

### 1. **Metadata Analysis**

Extracts EPUB version, language, and encoding:

```python
def _analyze_metadata(self, z: ZipFile):
    # Read container.xml to find OPF path
    container_xml = z.read("META-INF/container.xml")
    root = etree.fromstring(container_xml)
    
    # Extract OPF path
    opf_path = root.xpath("//opf:rootfile/@full-path", namespaces=ns)[0]
    
    # Read OPF
    opf_data = z.read(opf_path)
    opf_root = etree.fromstring(opf_data)
    
    # Extract version
    version = opf_root.get("version")  # "2.0", "3.0", etc.
    self.report.epub_version = version
    
    # Extract language
    lang_elem = opf_root.xpath("//*[@xml:lang]")[0]
    lang = lang_elem.get("{http://www.w3.org/XML/1998/namespace}lang", "en")
    self.report.epub_language = lang
    
    # Check for RTL support
    self.report.rtl_support = "ar" in lang or "he" in lang
```

**Recorded in report:**
- `epub_version` — "2.0" or "3.0"
- `epub_language` — "en", "it", etc.
- `rtl_support` — True if right-to-left language
- `fixed_layout` — True if fixed-layout EPUB
- `drm_protected` — True if DRM detected

### 2. **Spine Analysis**

Counts spine items and file types:

```python
def _analyze_spine(self, z: ZipFile):
    # Parse OPF to get spine items
    spine_items = opf_root.xpath("//opf:spine/opf:itemref", namespaces=ns)
    
    self.report.spine_items = len(spine_items)
    
    # Count file types
    file_types = {}
    for itemref in spine_items:
        item_id = itemref.get("idref")
        item = manifest.find(f".//*[@id='{item_id}']")
        if item is not None:
            ext = Path(item.href).suffix
            file_types[ext] = file_types.get(ext, 0) + 1
    
    # Record
    self.report.spine_file_types = file_types  # {".html": 40, ".xhtml": 2}
```

**Recorded in report:**
- `spine_items` — Total number of spine files
- `spine_file_types` — Dictionary of file extensions and counts

### 3. **TOC Analysis**

Reads original table of contents:

```python
def _analyze_toc(self, z: ZipFile):
    # Resolve NCX path
    ncx_path = resolve_ncx_path(container_xml, opf_path, z)
    
    if ncx_path is None:
        self.report.add_warning("Could not resolve NCX path")
        return
    
    # Parse NCX
    ncx_bytes = z.read(ncx_path)
    toc_entries = parse_ncx_entries(ncx_bytes)
    
    self.report.original_toc_entries = len(toc_entries)
    self.report.toc_entries = toc_entries  # For later phases
    
    # Check for gaps/issues
    if len(toc_entries) == 0:
        self.report.add_warning("NCX parsed but contains 0 entries")
    if len(toc_entries) < len(spine_items) / 2:
        self.report.add_warning(f"TOC ({len(toc_entries)}) is sparse vs spine ({len(spine_items)})")
```

**Recorded in report:**
- `original_toc_entries` — Count of entries in NCX/nav.xhtml
- `toc_entries` — List of TocEntry objects for later phases

### 4. **Markup Quality Assessment**

Analyzes semantic structure:

```python
def _analyze_markup_quality(self, z: ZipFile):
    semantic_headings = 0
    total_files = 0
    
    # Sample spine files
    for spine_item in spine_items[:min(10, len(spine_items))]:  # Sample first 10
        total_files += 1
        
        # Read file
        content = safe_read(z, spine_item.href)
        parser = select_parser(spine_item.href)
        soup = BeautifulSoup(content, parser)
        
        # Count heading tags
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        semantic_headings += len(headings)
    
    self.report.semantic_headings_detected = semantic_headings
    
    # Assess quality
    if semantic_headings >= len(spine_items) * 0.5:
        self.report.markup_quality = "good"
    elif semantic_headings >= 1:
        self.report.markup_quality = "partial"
    else:
        self.report.markup_quality = "poor"
```

**Recorded in report:**
- `semantic_headings_detected` — Count of `<h1-6>` tags found
- `markup_quality` — "poor", "partial", or "good"

## 💡 Recommendations

### Generation Logic

```python
def _generate_recommendations(self):
    """Determine which phases user should run"""
    recommendations = []
    
    # Phase 1: HTML cleanup (almost always beneficial)
    recommendations.append(1)
    
    # Phase 2: Semantic upgrade (only if headings sparse)
    if self.report.semantic_headings_detected < self.report.spine_items * 0.3:
        recommendations.append(2)
    
    # Phase 3: Spine realignment (optional, guide user)
    # Not automatically recommended—user must use --realign-spine
    
    # Phase 4: TOC rebuild (if TOC is sparse or missing)
    if self.report.original_toc_entries < self.report.spine_items * 0.3:
        recommendations.append(4)
    
    # Phase 5: Typography (almost always beneficial)
    recommendations.append(5)
    
    # Phase 6: CSS rewrite (recommended if many Calibre artifacts detected)
    if self.report.spine_file_types.get(".html", 0) > 0:
        recommendations.append(6)
    
    self.report.recommendations = recommendations
```

### Example Output

```json
{
  "epub_version": "2.0",
  "epub_language": "en",
  "spine_items": 42,
  "original_toc_entries": 40,
  "semantic_headings_detected": 0,
  "markup_quality": "poor",
  "recommended_phases": [1, 2, 4, 5, 6],
  "validation_errors": [
    "DOCTYPE missing",
    "NCX navLabel mismatch"
  ],
  "spine_file_types": {
    ".html": 40,
    ".xhtml": 2
  }
}
```

## 🔗 Integration

### Entry Point

```python
from toc_fixer.pipeline.phase0 import run_phase0

# In main.py
report = PipelineReport()
success = run_phase0(epub_path, report)

if success:
    # Save report
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"{epub_path.stem}_phase0_report.json"
    save_report(report, report_path)
```

### Report Usage

```python
# Parse recommendations
recommended_phases = report.recommendations

# If user didn't specify --phases, use recommendations
if not user_specified_phases:
    phases_to_run = recommended_phases
```

## 🧪 Testing

```python
def test_phase0_around_the_world(test_epubs_dir):
    """Test Phase 0 with around-the-world.epub"""
    epub_path = test_epubs_dir / "around-the-world.epub"
    report = PipelineReport()
    
    success = run_phase0(str(epub_path), report)
    
    assert success
    assert report.epub_version == "2.0"
    assert report.spine_items == 42
    assert report.original_toc_entries == 40
    assert report.semantic_headings_detected == 0
    assert report.markup_quality == "poor"
    assert 1 in report.recommendations  # Phase 1 always recommended
    assert 2 in report.recommendations  # Phase 2 recommended (no headings)

def test_phase0_ground_truth():
    """Test Phase 0 with Standard Ebooks EPUB"""
    epub_path = test_epubs_dir / "jules-verne_around-the-world-in-eighty-days_george-makepeace-towle.epub"
    report = PipelineReport()
    
    success = run_phase0(str(epub_path), report)
    
    assert success
    assert report.semantic_headings_detected > report.spine_items * 0.8
    assert report.markup_quality == "good"
    # May not need Phase 2 if already has headings
```

## 📊 Metrics

### Expected Output (around-the-world.epub)

| Metric | Value |
|--------|-------|
| EPUB Version | 2.0 |
| Language | en |
| Spine Items | 42 |
| Original TOC Entries | 40 |
| Semantic Headings Detected | 0 |
| Markup Quality | poor |
| Phase 1 Recommended | Yes |
| Phase 2 Recommended | Yes |

## 🚀 Next Steps

Phase 0 does not modify the EPUB. It prepares a diagnostic report that informs which subsequent phases to run.

**For users**:
- Review phase0_report.json
- Use recommended phases or customize with `--phases` flag

**For developers**:
- Read the generated recommendations
- Each phase (1-7) builds on this foundation
- phase0_report.json guides the workflow

---

**Next Phase**: [Phase 1: HTML Cleanup](06-PHASE-1.md)

**Related**: [Architecture](01-ARCHITECTURE.md) | [Data Models](13-DATA-MODELS.md) | [Core Utilities](02-CORE-UTILITIES.md)
