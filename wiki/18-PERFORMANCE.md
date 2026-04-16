# Performance Optimization

Performance tuning and optimization strategies for TOC Fixer.

## 📊 Current Metrics

### Baseline Performance (around-the-world.epub)
```
| Metric | Value |
|--------|-------|
| Total Time | 3.6 sec |
| Phase 0 | 0.2 sec |
| Phase 1 | 0.5 sec |
| Phase 2 | 1.2 sec (headings detection) |
| Phase 3 | - (not run) |
| Phase 4 | 0.8 sec (TOC rebuild) |
| Phase 5 | 0.4 sec |
| Phase 6 | 0.3 sec |
| Phase 7 | 0.2 sec |
```

### Memory Usage
- Typical EPUB: <200 MB
- Large EPUB (lovecraft.epub, 480 items): <500 MB

### File Size Ratio
- Input → Output: ~1.5x (compression)
- Typical 2.5 MB → 3.8 MB

## 🚀 Optimization Opportunities

### 1. Phase Parallelization (HIGH IMPACT)

**Current**: Sequential execution (phases 1-7 in order)
**Opportunity**: Phases 1-7 are independent after Phase 0

**Implementation**:
```python
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

# Run phases 1-7 in parallel
with ProcessPoolExecutor(max_workers=4) as executor:
    futures = {}
    futures[1] = executor.submit(run_phase1, input_epub, p1_output, report)
    futures[2] = executor.submit(run_phase2, input_epub, p2_output, report)
    # ... etc
    
    for phase, future in futures.items():
        success = future.result()
```

**Expected Speed**: 3.6s → 1.5s (2.4x faster)
**Tradeoff**: More complex state management

---

### 2. CSS Minification (MEDIUM IMPACT)

**Current**: Full CSS preserved as-is
**Opportunity**: Remove comments, whitespace

**Implementation**:
```python
import re

def minify_css(css_content: str) -> str:
    # Remove comments
    css_content = re.sub(r'/\*.*?\*/', '', css_content, flags=re.DOTALL)
    
    # Remove whitespace
    css_content = re.sub(r'\s+', ' ', css_content)
    css_content = re.sub(r'\s*([{}:;,])\s*', r'\1', css_content)
    
    return css_content.strip()
```

**Expected Size Savings**: 5-15% per EPUB
**Complexity**: Low (already implemented in Phase 6)

---

### 3. Caching (MEDIUM IMPACT)

**Current**: Re-processes each EPUB from scratch
**Opportunity**: Cache phase results for re-runs

**Implementation**:
```python
import hashlib
import json
from pathlib import Path

def compute_epub_hash(epub_path: str) -> str:
    """Compute SHA256 of EPUB for caching"""
    sha256 = hashlib.sha256()
    with open(epub_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

# Cache structure:
# .cache/{epub_hash}/phase1/output.epub
# .cache/{epub_hash}/phase2/output.epub
# .cache/{epub_hash}/phase7_report.json
```

**Expected Speed**: 3.6s → 0.5s for cached runs (7x faster)
**Tradeoff**: Disk usage for cache (~10-20 MB per EPUB)

---

### 4. Incremental Processing

**Current**: All phases from scratch each run
**Opportunity**: Skip completed phases if inputs unchanged

**Implementation**:
```python
def should_run_phase(phase_num: int, report: Report) -> bool:
    """Check if phase needs re-running"""
    # Skip if:
    # 1. Phase not requested
    # 2. Previous phase failed
    # 3. Previous phase output unchanged
    # 4. Current phase output cached
    
    cache_path = get_cache_path(phase_num)
    if cache_path.exists():
        # Compare input hash with cached input
        if get_phase_input_hash(phase_num) == get_cached_input_hash(phase_num):
            # Skip and use cached output
            return False
    
    return True
```

**Expected Speed**: 3.6s → 0.8s for unchanged inputs (4.5x faster)

---

### 5. Memory-Efficient ZIP Streaming

**Current**: Extract entire EPUB to disk (memory + disk I/O)
**Opportunity**: Stream processing without full extraction

**Implementation**:
```python
from zipfile import ZipFile
from io import BytesIO

def process_zip_streaming(epub_path: str):
    """Process EPUB without full extraction"""
    with ZipFile(epub_path, 'r') as z_in:
        # Process directly from ZIP
        for file_info in z_in.filelist:
            if file_info.filename.endswith('.html'):
                content = z_in.read(file_info)
                # Process in-memory
                processed = process_html(content)
                # Store for repacking
```

**Expected Memory**: <100MB for all EPUBs
**Complexity**: Medium (ZIP architecture simplifications needed)

---

## 📈 Profiling Guide

### Identify Bottlenecks

```python
import cProfile
import pstats

# Profile full pipeline
profiler = cProfile.Profile()
profiler.enable()

# Run pipeline
python main.py around-the-world.epub

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

### Expected Output
```
ncalls  tottime  cumtime  filename:lineno(function)
  1000   0.5     2.3     parser.py:234(parse_html)
  500    0.3     1.2     phase2.py:145(detect_headings)
  42     0.1     0.8     utils.py:45(safe_read)
```

---

## 🔧 Optimization Checklist

- [ ] Profile current performance
- [ ] Identify top 3 bottlenecks
- [ ] Implement parallelization
- [ ] Add CSS minification
- [ ] Implement caching
- [ ] Benchmark improvements
- [ ] Update performance metrics
- [ ] Document new speeds

---

## 🎯 Targets

- **Target Execution**: <2 seconds (from 3.6s)
- **Target Memory**: <100 MB (from 200 MB)
- **Target Size**: -20% output EPUB size
- **Target Cache Hit**: <1 second for re-runs

---

**Related**: [Architecture](01-ARCHITECTURE.md) | [Contributing](16-CONTRIBUTING.md)
