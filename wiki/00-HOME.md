# TOC Fixer Wiki

Welcome to the TOC Fixer technical documentation. This wiki provides detailed technical guidance for understanding and contributing to the project.

## 📚 Quick Navigation

### Getting Started
- [**Contributing Guide**](16-CONTRIBUTING.md) — How to set up your environment and contribute code
- [**Architecture Overview**](01-ARCHITECTURE.md) — System design and component relationships
- [**Testing Guide**](15-TESTING.md) — Running tests and validating changes

### Core Concepts
- [**Data Models**](13-DATA-MODELS.md) — TocEntry, SpineItem, PipelineReport structures
- [**Core Utilities**](02-CORE-UTILITIES.md) — Utility functions and helpers
- [**File Manager**](03-FILE-MANAGER.md) — File tracking and cleanup system

### Pipeline Implementation
- [**Pipeline Overview**](04-PIPELINE-OVERVIEW.md) — General patterns and common code
- [**Phase 0: Diagnosis**](05-PHASE-0.md) — Structure analysis and quality assessment
- [**Phase 1: HTML Cleanup**](06-PHASE-1.md) — Remove boilerplate and Calibre noise
- [**Phase 2: Semantic Upgrade**](07-PHASE-2.md) — Detect and inject headings (6-pass heuristic)
- [**Phase 3: Spine Realignment**](08-PHASE-3.md) — Split files at chapter boundaries
- [**Phase 4: TOC Rebuild**](09-PHASE-4.md) — Generate NCX and nav.xhtml
- [**Phase 5: Typography**](10-PHASE-5.md) — Enhance typography and spacing
- [**Phase 6: CSS Rewrite**](11-PHASE-6.md) — Consolidate and standardize CSS
- [**Phase 7: Validation**](12-PHASE-7.md) — Validate and compute F1 score

### Reference
- [**API Reference**](14-API-REFERENCE.md) — Detailed function and class documentation
- [**Bug Fixes**](13-BUG-FIXES.md) — Critical bugs and their solutions
- [**Troubleshooting**](17-TROUBLESHOOTING.md) — Common issues and solutions
- [**Performance Optimization**](18-PERFORMANCE.md) — Performance tips and benchmarks

## 🎯 Project Goals

**Transform wild EPUBs into clean, Standard Ebooks-quality EPUBs through 7 automated phases.**

- Wild EPUB (Gutenberg/Calibre) → Clean EPUB (Standard Ebooks compliant)
- Flat markup → Semantic structure with proper headings
- Poor TOC → Rebuilt with 37+ entries (F1 ≥ 0.95)
- Calibre noise → Clean CSS and standardized formatting

## 🏗️ Project Structure

```
nosferatu-fixer/
├── main.py                    # CLI entry point
├── nosferatu-fixer/                 # Main package
│   ├── __init__.py
│   ├── batch_processor.py     # Batch processing logic
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py          # TocEntry, SpineItem, PipelineReport
│   │   ├── utils.py           # ZIP/EPUB utilities (BUG fixes 1-3)
│   │   ├── epub_utils.py      # EPUB format utilities
│   │   ├── se_tools.py        # Standard Ebooks tool wrappers
│   │   ├── file_manager.py    # File tracking and cleanup
│   │   ├── phase_base.py      # Base class for phases
│   │   ├── profiler.py        # Performance profiling
│   │   └── performance_optimization.py  # Optimization utilities
│   └── pipeline/
│       ├── __init__.py
│       ├── phase0.py          # Phase 0: Diagnosis ✅
│       ├── phase1.py          # Phase 1: HTML cleanup ✅
│       ├── phase2.py          # Phase 2: Semantic upgrade ✅
│       ├── phase3.py          # Phase 3: Spine realignment ✅
│       ├── phase4.py          # Phase 4: TOC rebuild ✅
│       ├── phase5.py          # Phase 5: Typography ✅
│       ├── phase6.py          # Phase 6: CSS rewrite ✅
│       └── phase7.py          # Phase 7: Validation ✅
├── wiki/                      # This documentation
├── reports/                   # JSON reports from phase runs
└── [README, AGENTS, LICENSE]
```

## 🔑 Key Concepts

### 1. **7-Phase Pipeline**
Each phase is independent, with optional SE Tool integration:
- Try standard-ebooks tool first (via subprocess)
- Fall back to custom Python implementation if needed
- Graceful error handling with cleanup

### 2. **File Management**
- Input EPUB → tmp/ (intermediate processing)
- Phase outputs: tmp/{name}_p1.epub, _p2.epub, etc.
- Default: Auto-cleanup (clean workspace)
- Debug: `--debug-output` preserves all files

### 3. **Data Models**
All phases use consistent data structures:
- `TocEntry` — Table of contents entries
- `SpineItem` — EPUB spine files
- `PipelineReport` — Metrics and results

### 4. **Core Utilities**
Critical bug fixes (BUG-1, BUG-2, BUG-3):
- NCX path resolution with 3-method fallback
- lxml namespace-aware XML parsing
- Extension-based HTML parser selection
- Case-insensitive ZIP access

## 🐛 Critical Bugs Fixed

| Bug | Status | Details |
|-----|--------|---------|
| BUG-1 | ✅ Fixed | NCX path resolution → [link](13-BUG-FIXES.md#bug-1) |
| BUG-2 | ✅ Fixed | NCX parsing with lxml → [link](13-BUG-FIXES.md#bug-2) |
| BUG-3 | ✅ Fixed | Spine ZIP keys & parser selection → [link](13-BUG-FIXES.md#bug-3) |
| BUG-4 | ✅ Fixed | Phase 6 file corruption → [link](13-BUG-FIXES.md#bug-4) |
| BUG-5 | ✅ Fixed | Phase 3 file corruption → [link](13-BUG-FIXES.md#bug-5) |

## 📊 Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| **Phase 0** | ✅ Complete | Diagnosis, structure analysis, recommendations |
| **Phase 1** | ✅ Complete | HTML cleanup, SE tool + custom fallback |
| **Phase 2** | ✅ Complete | 6-pass heading detection, semantic upgrade |
| **Phase 3** | ✅ Complete | Spine realignment, optional phase |
| **Phase 4** | ✅ Complete | TOC rebuild (NCX + nav.xhtml) |
| **Phase 5** | ✅ Complete | Typography enhancement with language support |
| **Phase 6** | ✅ Complete | CSS consolidation and SE styling |
| **Phase 7** | ✅ Complete | Validation with F1 scoring |
| **File Manager** | ✅ Complete | Auto-cleanup, debug mode, tmp/ organization |
| **Bug Fixes** | ✅ Complete | All 5 critical bugs fixed and tested |

## 🚀 Getting Started as a Contributor

1. **Read First**: [Architecture Overview](01-ARCHITECTURE.md)
2. **Understand**: [Data Models](13-DATA-MODELS.md)
3. **Learn**: [Pipeline Overview](04-PIPELINE-OVERVIEW.md)
4. **Explore**: Phase guides (Phase 0-7)
5. **Test**: [Testing Guide](15-TESTING.md)
6. **Contribute**: [Contributing Guide](16-CONTRIBUTING.md)

## 🔗 External References

- [Standard Ebooks Tools](https://github.com/standardebooks/tools) — SE tool suite
- [EPUB 3.3 Specification](https://www.w3.org/TR/epub-33/) — W3C standard
- [BeautifulSoup4 Documentation](https://www.crummy.com/software/BeautifulSoup/)
- [Project Gutenberg](https://www.gutenberg.org/)
- [Standard Ebooks](https://standardebooks.org/)

## 💡 Common Workflows

### Running the Pipeline
```bash
python main.py wild.epub --verbose --json-reports
```

### Testing a Phase
```bash
python main.py wild.epub --phases 0,1,2 --debug-output
```

### Scoring Against Ground Truth
```bash
python main.py wild.epub --ground-truth master.epub --json-reports
```

## 📖 File Organization

- `wiki/00-HOME.md` ← **You are here**
- `wiki/01-ARCHITECTURE.md` — System design
- `wiki/02-CORE-UTILITIES.md` — Utility functions
- `wiki/03-FILE-MANAGER.md` — File management
- `wiki/04-PIPELINE-OVERVIEW.md` — Common patterns
- `wiki/05-PHASE-0.md` through `wiki/12-PHASE-7.md` — Phase guides
- `wiki/13-DATA-MODELS.md` — Data structures
- `wiki/14-API-REFERENCE.md` — API documentation
- `wiki/13-BUG-FIXES.md` — Critical bugs and fixes
- `wiki/15-TESTING.md` — Testing guide
- `wiki/16-CONTRIBUTING.md` — Contributing guide
- `wiki/17-TROUBLESHOOTING.md` — Common issues
- `wiki/18-PERFORMANCE.md` — Performance tips

---

**Last Updated**: April 2026 | **Status**: Alpha | **Contributors**: Welcome!
