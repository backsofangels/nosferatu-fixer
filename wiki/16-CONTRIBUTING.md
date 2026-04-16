# Contributing Guide

Welcome to TOC Fixer! This guide helps you set up your environment, understand the codebase, and contribute effectively.

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Git
- Standard Ebooks tools (optional but recommended)

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/backs/toc-fixer.git
cd toc-fixer
```

2. **Create virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\Activate.ps1  # Windows PowerShell
```

3. **Install dependencies**
```bash
pip install beautifulsoup4 lxml chardet
```

4. **Install Standard Ebooks tools (optional)**
```bash
pipx install standardebooks
```

5. **Verify installation**
```bash
python main.py --help
```

## 📚 Learning Path

**New to the project?** Follow this order:

1. **Read**: [Architecture Overview](01-ARCHITECTURE.md)
   - Understand component relationships
   - Learn the 7-phase pipeline

2. **Explore**: [Data Models](13-DATA-MODELS.md)
   - Understand TocEntry, SpineItem, PipelineReport
   - These are used everywhere

3. **Study**: [Pipeline Overview](04-PIPELINE-OVERVIEW.md)
   - Learn common patterns
   - Understand phase structure

4. **Deep Dive**: Individual phase guides (05-PHASE-0.md through 12-PHASE-7.md)
   - See how each phase works
   - Understand SE tool wrappers and fallbacks

5. **Reference**: [Core Utilities](02-CORE-UTILITIES.md)
   - Use when debugging EPUB parsing issues
   - Understand BUG fixes (1-5)

## 🔧 Development Workflow

### 1. Creating a New Phase (if needed)

Each phase follows the same pattern:

```python
# toc_fixer/pipeline/phaseX.py

import subprocess
from pathlib import Path
from zipfile import ZipFile
from ..core import PipelineReport, build_zip_key
from ..core.utils import safe_read

class PhaseXTransformer:
    def __init__(self, epub_path: str, output_path: str, report: PipelineReport):
        self.epub_path = epub_path
        self.output_path = output_path
        self.report = report
    
    def run_phase(self) -> bool:
        """Run Phase X transformation"""
        try:
            # Try SE Tool first
            return self._try_se_tool()
        except Exception as e:
            self.report.add_warning(f"Phase X: {str(e)}")
            # Fall back to custom implementation
            return self._custom_implementation()
    
    def _try_se_tool(self) -> bool:
        """Try using Standard Ebooks tool"""
        # Extract EPUB to temp directory
        epub_dir = Path(f"tmp_epub_{self.epub_path.stem}")
        self._extract_epub(epub_dir)
        
        try:
            result = subprocess.run(
                ["se", "tool-name", str(epub_dir)],
                capture_output=True,
                timeout=300
            )
            
            if result.returncode == 0:
                # Repack and return
                self._repack_epub(epub_dir)
                return True
            else:
                return False
        finally:
            import shutil
            shutil.rmtree(epub_dir, ignore_errors=True)
    
    def _custom_implementation(self) -> bool:
        """Fall back to custom Python implementation"""
        # Extract EPUB
        epub_dir = Path(f"tmp_epub_{self.epub_path.stem}")
        self._extract_epub(epub_dir)
        
        try:
            # Process files
            self._process_files(epub_dir)
            
            # Repack
            self._repack_epub(epub_dir)
            return True
        except Exception as e:
            self.report.add_error(f"Phase X custom: {str(e)}")
            return False
        finally:
            import shutil
            shutil.rmtree(epub_dir, ignore_errors=True)
    
    def _extract_epub(self, target_dir: Path):
        """Extract EPUB to directory"""
        target_dir.mkdir(parents=True, exist_ok=True)
        with ZipFile(self.epub_path, 'r') as z:
            z.extractall(target_dir)
    
    def _process_files(self, epub_dir: Path):
        """Transform EPUB contents"""
        # Implement phase-specific logic
        pass
    
    def _repack_epub(self, epub_dir: Path):
        """Repack directory back to EPUB"""
        with ZipFile(self.output_path, 'w') as z:
            for file_path in epub_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(epub_dir)
                    z.write(file_path, arcname)

def run_phaseX(epub_path: str, output_path: str, report: PipelineReport) -> bool:
    """Entry point for Phase X"""
    transformer = PhaseXTransformer(epub_path, output_path, report)
    return transformer.run_phase()
```

### 2. Modifying an Existing Phase

When improving a phase:

1. **Read the current implementation** in `toc_fixer/pipeline/phaseN.py`
2. **Identify the issue** — SE tool or custom implementation?
3. **Write tests first** in `test_phaseN.py`
4. **Implement the fix**
5. **Run the full pipeline** with test EPUB
6. **Check F1 score** in phase7_report.json
7. **Update documentation** in wiki/0N-PHASE-N.md

### 3. Adding a Utility Function

New utilities in `toc_fixer/core/utils.py`:

```python
def new_utility_function(param1: str, param2: int) -> bool:
    """
    Short description.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        True if successful, False otherwise
    
    Raises:
        ValueError: If param validation fails
    
    Examples:
        >>> result = new_utility_function("test", 42)
        >>> result
        True
    """
    # Implementation
    pass
```

Export in `toc_fixer/core/__init__.py`:

```python
from .utils import (
    resolve_ncx_path,
    parse_ncx_entries,
    build_zip_key,
    safe_read,
    select_parser,
    new_utility_function,  # Add here
)
```

## 🧪 Testing Your Changes

### Run the Full Pipeline

```bash
# Test with primary EPUB
python main.py around-the-world.epub --verbose --json-reports

# Test with ground truth scoring
python main.py around-the-world.epub \
    --ground-truth jules-verne_around-the-world-in-eighty-days_george-makepeace-towle.epub \
    --json-reports
```

### Run Specific Phases

```bash
# Test phases 1, 2, 6 only
python main.py around-the-world.epub --phases 1,2,6 --debug-output

# Inspect tmp/ directory for intermediate files
ls tmp/
```

### Check Results

```bash
# Check phase reports
cat reports/around-the-world_phase0_report.json
cat reports/around-the-world_phase7_report.json

# Look for:
# - rebuilt_toc_entries (target: ≥37)
# - f1_score (target: ≥0.95)
# - se_lint_errors (target: 0)
```

## 📝 Code Style

### Naming Conventions

```python
# Functions and variables
def parse_ncx_file(path: str) -> dict:
    input_data = read_file(path)
    return result

# Classes
class Phase1Cleaner:
    def run_phase(self):
        pass

# Constants
NCX_NAMESPACE = "http://www.daisy.org/z3986/2005/ncx/"
MAX_TIMEOUT = 300

# Private members
class MyClass:
    def _private_method(self):
        pass
    
    _private_var = None
```

### Documentation

All functions need docstrings:

```python
def function_name(param1: str, param2: int) -> bool:
    """
    One-line summary.
    
    Longer description if needed.
    
    Args:
        param1: Description
        param2: Description
    
    Returns:
        Description of return value
    
    Raises:
        ExceptionType: When this happens
    
    Examples:
        >>> function_name("test", 42)
        True
    """
    pass
```

### Type Hints

Use type hints for all function signatures:

```python
from typing import Optional, List, Dict

def process_entries(
    entries: List[TocEntry],
    options: Optional[Dict[str, str]] = None
) -> bool:
    pass
```

## ✅ Checklist Before Submitting PR

- [ ] Code follows naming conventions
- [ ] All functions have docstrings
- [ ] Type hints on all signatures
- [ ] Tests pass locally
- [ ] Full pipeline runs successfully
- [ ] F1 score ≥ 0.95 (where applicable)
- [ ] No new warnings/errors
- [ ] Updated documentation/wiki if needed
- [ ] Committed to feature branch, not main

## 🐛 Reporting Issues

Found a bug? Create an issue with:

1. **Title**: Clear, concise description
2. **Description**: What happened vs. what should happen
3. **Steps to reproduce**:
   ```bash
   python main.py [which EPUB]
   python main.py calm.epub --verbose
   ```
4. **Expected result**: What you thought would happen
5. **Actual result**: What actually happened
6. **Logs**: Contents of reports/\*_phase\_report.json

## 🤝 Pull Request Process

1. **Fork** the repository
2. **Create** a feature branch
   ```bash
   git checkout -b feature/fix-heading-detection
   ```
3. **Make changes** following code style guidelines
4. **Test thoroughly** against all test EPUBs
5. **Commit** with clear messages
   ```bash
   git commit -m "Fix heading detection for Calibre quotes"
   ```
6. **Push** to your fork
7. **Create PR** with description and test results

## 📊 Test EPUBs

Use these EPUBs for testing:

| EPUB | Purpose | Spine | Headings | Notes |
|------|---------|-------|----------|-------|
| `around-the-world.epub` | Primary test | 42 | 0 → 37 | Calibre-generated |
| `lovecraft.epub` | Scalability | 480+ | ~425 | Large EPUB |
| `jules-verne_...` | Ground truth | 42 | 42 | Standard Ebooks |

Expected results:
- around-the-world: F1 ≥ 0.95
- lovecraft: Completes in <5 seconds
- zero blocking lint errors after transformation

## 🚀 Optimization Opportunities

Looking to contribute optimizations?

1. **Phase parallelization** — Run phases 1-7 in  parallel
2. **CSS minification** — Further reduce stylesheet size
3. **Caching** — Cache phase results for re-runs
4. **Performance profiling** — Identify bottlenecks
5. **Language support** — Add French, Spanish, German typography

See [Performance Optimization](19-PERFORMANCE.md) for details.

## 📞 Getting Help

- **Architecture questions**: Read [Architecture](01-ARCHITECTURE.md)
- **Specific phase issues**: Read phase guide (05-PHASE-0.md, etc.)
- **Debugging help**: See [Troubleshooting](18-TROUBLESHOOTING.md)
- **API questions**: Check [API Reference](14-API-REFERENCE.md)

---

**Ready to start?** Pick an issue or optimization, follow the workflow above, and submit your PR!
