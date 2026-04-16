# Architecture Overview

TOC Fixer follows a clean, modular architecture designed for extensibility and maintainability.

## 🏗️ System Design

```
CLI Entry (main.py)
    ↓
[FileManager] ← manages tmp/, cleanup
    ↓
Phase 0 (Diagnosis)
    ↓
Phases 1-7 (Transformation)
    Each Phase:
    1. Try SE Tool (subprocess)
    2. Fall back to Custom impl.
    3. Error handling + cleanup
    ↓
[PipelineReport] ← metrics, F1 score
    ↓
Output + Reports
```

## 📦 Core Components

### 1. **Core Package** (`nosferatu-fixer/core/`)

#### **models.py**
Data structures shared across all phases:
- `TocEntry` — TOC entry with confidence tracking
- `SpineItem` — Spine file metadata
- `PipelineReport` — Phase metrics and results

See [Data Models](13-DATA-MODELS.md) for detailed documentation.

#### **utils.py**
Critical EPUB utilities with bug fixes:
- `resolve_ncx_path()` — NCX path resolution (BUG-1 fix)
- `parse_ncx_entries()` — NCX parsing with lxml (BUG-2 fix)
- `build_zip_key()` — ZIP key construction (BUG-3 fix)
- `safe_read()` — Case-insensitive ZIP access
- `select_parser()` — Parser selection by file extension

See [Core Utilities](02-CORE-UTILITIES.md) for detailed documentation.

#### **epub_utils.py**
EPUB format utilities:
- EPUB ZIP extraction and manipulation
- Container/metadata parsing
- Manifest and spine operations

#### **se_tools.py**
Standard Ebooks tool integration:
- Subprocess wrappers for SE tools
- Fallback handling and error management
- Tool availability detection

#### **file_manager.py**
File lifecycle management:
- `FileManager` — Entry point tracking
- `PipelineFileTracker` — Phase output tracking
- `BatchResult` — Batch processing results
- Auto-cleanup in normal mode
- Debug mode preservation

See [File Manager](03-FILE-MANAGER.md) for detailed documentation.

#### **phase_base.py**
Base class for all phase implementations:
- Common phase interface
- Error handling patterns
- Logging and reporting

#### **profiler.py**
Performance profiling utilities:
- Memory tracking
- Execution time measurement
- Resource monitoring

#### **performance_optimization.py**
Optimization utilities:
- Performance analysis tools
- Bottleneck identification
- Optimization recommendations

### 2. **Pipeline Package** (`nosferatu-fixer/pipeline/`)

7 independent phase implementations:

| Phase | File | Purpose | Status |
|-------|------|---------|--------|
| 0 | phase0.py | Diagnosis | ✅ Complete |
| 1 | phase1.py | HTML cleanup | ✅ Complete |
| 2 | phase2.py | Semantic upgrade | ✅ Complete |
| 3 | phase3.py | Spine realignment | ✅ Complete |
| 4 | phase4.py | TOC rebuild | ✅ Complete |
| 5 | phase5.py | Typography | ✅ Complete |
| 6 | phase6.py | CSS rewrite | ✅ Complete |
| 7 | phase7.py | Validation | ✅ Complete |

See [Pipeline Overview](04-PIPELINE-OVERVIEW.md) and individual phase guides.

### 3. **CLI Entry** (`main.py`)

Orchestrates the complete pipeline:
- Argument parsing (12 flags)
- Phase selection and execution
- File management coordination
- Error handling and reporting

## 🔄 Pipeline Flow

```
main.py
  ↓
1. Create tmp/ directory
2. Parse arguments
3. Initialize FileManager + PipelineFileTracker
4. Phase 0 (Diagnosis)
  ├─ Generate phase0_report.json
  └─ Set recommended phases
5. Phases 1-7 (Optional, based on flags/recommendations)
  ├─ Phase 1 → tmp/{name}_p1.epub
  ├─ Phase 2 → tmp/{name}_p2.epub
  ├─ Phase 3 → tmp/{name}_p3.epub (optional, --realign-spine)
  ├─ Phase 4 → tmp/{name}_p4.epub
  ├─ Phase 5 → tmp/{name}_p5.epub
  ├─ Phase 6 → tmp/{name}_p6.epub
  └─ Phase 7 → phase7_report.json (validation only)
6. Finalize
  ├─ Copy final output to {name}_clean.epub
  ├─ Save reports/ directory
  └─ Clean up tmp/ (unless --debug-output)
```

## 💾 Data Flow

### Input
```
wild.epub (Gutenberg/Calibre)
  ├─ container.xml (package metadata)
  ├─ content.opf (spine, manifest)
  ├─ toc.ncx (table of contents)
  └─ spine files (HTML/XHTML content)
```

### Processing
```
Phase 0: Parse & analyze
  → PipelineReport (metrics, recommendations)
Phase 1-7: Transform
  → Intermediate EPUBs in tmp/
Phase 7: Validate
  → phase7_report.json (F1 score, errors)
```

### Output
```
clean.epub (Standard Ebooks compatible)
  ├─ [cleaned/semantic markup]
  ├─ [rebuilt TOC with proper nesting]
  ├─ [consolidated CSS]
  └─ [typography enhanced]
```

## 🔌 Phase Pattern

Every phase follows a consistent pattern for SE Tool integration:

```python
class PhaseX:
    def __init__(self, epub_path, output_path, report):
        self.epub_path = epub_path
        self.output_path = output_path
        self.report = report
    
    def run_phase(self):
        try:
            # Try SE Tool first
            result = subprocess.run(
                ["se", "tool-name", epub_dir],
                capture_output=True,
                timeout=300
            )
            
            if result.returncode == 0:
                return True  # SE tool succeeded
            else:
                # Fall back to custom implementation
                return self._custom_implementation()
        except Exception as e:
            # Log error, fall back
            self.report.add_error(str(e))
            return self._custom_implementation()
    
    def _custom_implementation(self):
        # Extract EPUB
        # Process with custom logic
        # Repack EPUB
        pass
```

## 🔐 Error Handling

All phases implement defensive error handling:

```python
# 1. Try operation
# 2. Log to report (not exception)
# 3. Fall back to alternative
# 4. Clean up on failure
# 5. Return status (not exception)
```

**Philosophy**: Never crash the pipeline. Always fall back gracefully.

## 📊 File Organization Strategy

### Default (Clean Mode)
Minimizes clutter:
- Only input, output, and reports kept
- tmp/ auto-removed when empty
- Intermediate files never left behind

### Debug Mode (--debug-output)
Preserves everything:
- tmp/{name}_p1.epub through _p6.epub preserved
- Allows phase-by-phase inspection
- Helps troubleshoot failures

## 🔗 Module Dependencies

```
main.py
  ├─ toc_fixer.core
  │   ├─ models (TocEntry, SpineItem, PipelineReport)
  │   ├─ utils (resolve_ncx_path, build_zip_key, etc.)
  │   └─ file_manager (FileManager, PipelineFileTracker)
  └─ toc_fixer.pipeline
      ├─ phase0 (Phase0Analyzer)
      ├─ phase1 (Phase1Cleaner)
      ├─ phase2 (Phase2Analyzer)
      ├─ ... phase3-7
      └─ All use core.utils + core.models
```

**Import Convention**: Relative imports within package, absolute from main.py.

## 🎯 Design Principles

### 1. **Modularity**
- Each phase independent (can run alone)
- Core utilities are reusable
- Data models are shared

### 2. **Robustness**
- SE Tool preferred, custom fallback always available
- No hard failures; graceful degradation
- All errors logged to report (not exceptions)

### 3. **Traceability**
- Every transformation tracked in PipelineReport
- Confidence scores for heuristics
- Phase-by-phase metrics

### 4. **Extensibility**
- Easy to add new phases
- Language support (en, it, fr, etc.)
- Custom CSS rules, typography rules

### 5. **Maintainability**
- Clear separation of concerns
- Consistent patterns across phases
- Well-documented utilities

## 🚀 Scaling Considerations

### Current Capacity
- **Tested**: 480+ spine items (Lovecraft EPUB)
- **Execution time**: ~3.6 seconds (full pipeline)
- **Memory**: <200 MB (typical)

### Optimization Opportunities
- Parallel phase execution (phases 1-7 are independent)
- CSS minification (already implemented)
- Incremental processing (cache phase results)

## 🧪 Testing Architecture

Each phase has corresponding tests:
- Unit tests for utilities
- Integration tests for phases
- End-to-end tests with reference EPUBs

See [Testing Guide](15-TESTING.md) for details.

## 📈 Metrics & Reporting

### Phase 0 Report
- EPUB structure analysis
- Quality assessment
- Recommendations

### Phase 7 Report
- Lint errors/warnings
- F1 score (when ground truth available)
- Execution summary

See [Testing Guide](15-TESTING.md#reports) for detailed report structures.

---

**Next**: Read [Pipeline Overview](04-PIPELINE-OVERVIEW.md) to understand common patterns.
