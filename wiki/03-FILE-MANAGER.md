# File Manager System

Comprehensive guide to file lifecycle management in TOC Fixer.

## 🆕 Batch Processing Support

The file manager now supports batch processing of multiple EPUBs:
- `BatchResult` — Results for individual EPUB processing
- `BatchProcessor` — Main batch orchestration
- Batch report generation with summary statistics

## 🎯 Purpose

The file manager system provides:
- **Tracking** - Which phase created which files
- **Organization** - Intermediate files in tmp/ directory
- **Cleanup** - Auto-removal of tmp/ in normal mode
- **Debugging** - Preservation of all files with --debug-output flag

## 📁 Directory Structure

### Default Mode (Clean)

Minimal clutter:

```
project/
├── wild.epub              # Original input
├── wild_clean.epub        # Final output ← main result
└── reports/
    ├── wild_phase0_report.json
    └── wild_phase7_report.json
```

**Result**: 2-3 files, zero intermediate clutter

### Debug Mode (--debug-output)

Everything preserved for inspection:

```
project/
├── wild.epub              # Original input
├── wild_clean.epub        # Final output
├── tmp/                   # Preserved intermediate files
│   ├── wild_p1.epub       # Phase 1 output
│   ├── wild_p2.epub       # Phase 2 output
│   ├── wild_p4.epub       # Phase 4 output (Phase 3 skipped if no --realign-spine)
│   ├── wild_p5.epub       # Phase 5 output
│   └── wild_p6.epub       # Phase 6 output
└── reports/
    ├── wild_phase0_report.json
    └── wild_phase7_report.json
```

**Result**: 7+ files for phase-by-phase inspection

## 🛠️ Implementation

### FileManager Class

**Location**: `toc_fixer/core/file_manager.py`

**Responsibilities**:
- Track entry point (input EPUB path)
- Manage cleanup configuration
- Execute cleanup operations

### Usage in main.py

```python
from toc_fixer.core.file_manager import FileManager

file_manager = FileManager(
    entry_point=str(epub_path),
    keep_debug_output=args.debug_output
)

# ... run pipeline ...

# At end, clean up
bytes_freed = file_manager.finalize(
    final_output=str(output_path),
    tmp_dir=tmp_dir
)

print(f"Cleaned up: {bytes_freed / 1024 / 1024:.1f} MB")
```

### PipelineFileTracker Class

Tracks phase outputs for chaining:

```python
from toc_fixer.core.file_manager import PipelineFileTracker

tracker = PipelineFileTracker()

# Register Phase 1 output
tracker.register_phase_output(1, "tmp/wild_p1.epub")

# Get Phase 1 output as Phase 2 input
phase1_output = tracker.get_phase_input(2)  # → "tmp/wild_p1.epub"

# Get file status
status = tracker.get_status()
# {
#   "phase_1": {"path": "tmp/wild_p1.epub", "size_mb": 2.5},
#   "phase_2": {"path": "tmp/wild_p2.epub", "size_mb": 2.4},
# }
```

## 🔄 File Lifecycle

### 1. Phase Initialization

```python
# main.py sets up tmp directory
tmp_dir = Path("tmp")
tmp_dir.mkdir(exist_ok=True)
tracker = PipelineFileTracker()
```

### 2. Phase Execution

```python
# Phase N reads from previous phase or input
input_epub = tracker.get_phase_input(phase_num) or input_epub_path

# Phase N writes to tmp directory
output_epub = str(tmp_dir / f"{stem}_p{phase_num}.epub")

# Phase N runs
run_phase_n(input_epub, output_epub, report)

# Tracker registers output
tracker.register_phase_output(phase_num, output_epub)
```

### 3. Phase Chaining

```
Input EPUB
  ↓
Phase 1 → tmp/wild_p1.epub
  ↓
Phase 2 (input: tmp/wild_p1.epub) → tmp/wild_p2.epub
  ↓
Phase 3 (input: tmp/wild_p2.epub) → tmp/wild_p3.epub [skip if no --realign-spine]
  ↓
Phase 4 (input: tmp/wild_p2.epub or tmp/wild_p3.epub) → tmp/wild_p4.epub
  ↓
... etc ...
```

### 4. Finalization

```python
# Copy last valid phase output to final destination
last_phase_output = tracker.get_latest_output()
shutil.copy(last_phase_output, output_path)

# Save reports
save_report(phase0_report, reports_dir)
save_report(phase7_report, reports_dir)

# Clean up (unless --debug-output)
if not keep_debug:
    bytes_freed = cleanup_tmp_directory(tmp_dir)
    print(f"Removed intermediate files: {bytes_freed / 1024 / 1024:.1f} MB")
```

## 🧹 Cleanup Strategy

### What Gets Cleaned?
- All tmp/{name}_p*.epub files (intermediate phase outputs)
- Empty tmp/ directory itself
- Temporary extraction directories

### What Gets Preserved?
- Input EPUB (wild.epub)
- Final output EPUB (wild_clean.epub)
- Reports/ directory and all reports

### When?
- **Always by default** (clean mode, production use)
- **Only with --debug-output flag** for debugging/inspection

### Space Savings

Typical EPUB cleaning:
```
Input:          ~2.5 MB
Phase 1 output: ~2.4 MB
Phase 2 output: ~2.4 MB
Phase 4 output: ~2.4 MB
Phase 5 output: ~2.4 MB
Phase 6 output: ~2.4 MB

Intermediate total: ~12.0 MB
After cleanup:      ~2.5 MB (input + output)

Savings: ~79% disk space (4 intermediate files removed)
```

## 🔗 Integration Points

### Phase Implementations

Each phase assumes:
1. Input file at tracker-provided path
2. Output file at `tmp/{stem}_p{n}.epub`
3. Tracker registration after success

```python
# In each phase0-7.py:
from toc_fixer.core.file_manager import PipelineFileTracker

class PhaseN:
    def run(self, input_epub: str, output_epub: str):
        # Read, process, write
        # ...
        return True  # success

# In main.py:
success = run_phaseN(input_epub, output_epub, report)
if success:
    tracker.register_phase_output(n, output_epub)
```

### Report Management

```python
from pathlib import Path

reports_dir = Path("reports")
reports_dir.mkdir(exist_ok=True)

# Report naming uses input EPUB stem
report_path = reports_dir / f"{epub_path.stem}_phase{n}_report.json"
report.save_json(report_path)
```

## 🚀 Best Practices

### For Contributors

1. **Always use PipelineFileTracker** in main.py
   - Don't hardcode file paths
   - Use tracker.register_phase_output()

2. **Create tmp/ directory early**
   - Before any phase execution
   - Check existence with Path.mkdir(exist_ok=True)

3. **Save reports with input name prefix**
   - {stem}_phase0_report.json
   - {stem}_phase7_report.json

4. **Handle missing intermediate files gracefully**
   - Phase failure → skip subsequent phases
   - Signal "use input EPUB as fallback"

5. **Test with --debug-output locally**
   - Preserve intermediate files during development
   - Inspect phase outputs
   - Debug failures

### For Users

1. **Use default mode for production**
   - Automatic cleanup keeps workspace clean
   - No manual file management needed

2. **Use --debug-output for troubleshooting**
   - Inspect intermediate EPUB files
   - Test individual phases
   - Understand transformation steps

3. **Check reports/ directory for results**
   - phase0_report.json has structure analysis
   - phase7_report.json has validation results
   - Both include recommendations

## 🧪 Testing File Management

### Test Cleanup

```python
def test_cleanup_removes_tmp():
    tmp_dir = Path("test_tmp")
    tmp_dir.mkdir()
    
    # Create test files
    (tmp_dir / "test_p1.epub").write_text("test")
    (tmp_dir / "test_p2.epub").write_text("test")
    
    # Cleanup
    import shutil
    shutil.rmtree(tmp_dir)
    
    assert not tmp_dir.exists()
```

### Test Debug Preservation

```python
def test_debug_preserves_files():
    tracker = PipelineFileTracker()
    tracker.debug_mode = True
    
    tracker.register_phase_output(1, "tmp/test_p1.epub")
    tracker.register_phase_output(2, "tmp/test_p2.epub")
    
    status = tracker.get_status()
    assert len(status) == 2  # Both files preserved
```

## 🐛 Common Issues

### Issue: "tmp directory not empty after cleanup"
**Solution**: Check --debug-output flag, manual inspection, ensure phase failures handled

### Issue: "Phase input file not found"
**Solution**: Verify previous phase succeeded, check tracker.get_phase_input(), examine reports

### Issue: "Different file sizes between runs"
**Solution**: Normal (compression varies), compare F1 scores, check phase7_report.json

## 📊 File Size Monitoring

The system tracks file sizes for diagnostics:

```python
status = tracker.get_status()
# {
#   "phase_1": {"size_mb": 2.4},
#   "phase_2": {"size_mb": 2.45},
#   ...
# }

# Identify large intermediate files
for phase, info in status.items():
    size_mb = info["size_mb"]
    if size_mb > 5:
        print(f"⚠️  {phase} is large: {size_mb:.1f} MB")
```

## 🔗 Related Documentation

- [Architecture](01-ARCHITECTURE.md) — System overview
- [Contributing Guide](17-CONTRIBUTING.md) — How to implement phases
- [Troubleshooting](18-TROUBLESHOOTING.md) — Common file issues

---

**Next**: Read [Pipeline Overview](04-PIPELINE-OVERVIEW.md) to understand phase patterns.
