# Troubleshooting Guide

Common issues and solutions when working with TOC Fixer.

## 🔴 Runtime Issues

### Issue: "FileNotFoundError: [Errno 2] No such file or directory"

**Symptoms**:
- Pipeline crashes during phase execution
- Error mentions missing .epub file
- Happens after Phase 6

**Root Cause**:
- Phase outputs wrong path (writes to input instead of output)
- Previous phase failed, leaving no input for next phase
- tmp/ directory corrupted or deleted

**Solutions**:

1. **Check phase success**:
   - Run with `--debug-output --verbose`
   - Inspect reports/\*_phase#_report.json
   - Look for error messages

2. **Verify file paths**:
   - Check if tmp/ directory exists
   - List tmp/ contents: `ls tmp/`
   - Verify phase outputs: `wild_p1.epub`, `wild_p2.epub`, etc.

3. **Re-run with debug**:
   ```bash
   python main.py problematic.epub \
     --debug-output \
     --phases 0,1,2 \
     --verbose
   ```

4. **Check file permissions**:
   - Ensure read/write access to tmp/
   - Windows: Check file locks (close other programs)

---

### Issue: "Zero TOC entries parsed"

**Symptoms**:
- phase0_report.json shows 0 original_toc_entries
- Rebuilt TOC is empty
- Phase 4 output has no TOC

**Root Cause** (Usually BUG-2 Related):
- NCX parsing failed (namespace issue)
- NCX file doesn't exist at resolved path
- lxml not installed or ncx parse error

**Solutions**:

1. **Verify lxml installed**:
   ```bash
   python -c "from lxml import etree; print('lxml OK')"
   ```
   If fails: `pip install lxml`

2. **Check NCX exists**:
   ```bash
   python main.py wild.epub --phases 0 --verbose
   ```
   Look for: "NCX resolved to: ..."

3. **Inspect the NCX file**:
   ```bash
   # Extract EPUB manually
   unzip wild.epub -d extracted/
   
   # Find NCX
   find extracted/ -name "*.ncx"
   
   # Check content
   cat extracted/OEBPS/toc.ncx | head -20
   ```

4. **Test NCX parsing**:
   ```python
   from toc_fixer.core.utils import parse_ncx_entries
   
   with open("extracted/OEBPS/toc.ncx", "rb") as f:
       entries = parse_ncx_entries(f.read())
       print(f"Parsed {len(entries)} entries")
   ```

---

### Issue: "Se tool not found" / "se command not found"

**Symptoms**:
- Phase fails with "se not found" or "command not found"
- Custom fallback unavailable for that phase
- Pipeline crashes instead of using Python implementation

**Root Cause**:
- Standard Ebooks tools not installed
- Not installed in PATH
- Wrong Python environment

**Solutions**:

1. **Install Standard Ebooks**:
   ```bash
   pipx install standardebooks
   ```

2. **Verify installation**:
   ```bash
   se --version
   which se  # Linux/macOS
   where se  # Windows PowerShell
   ```

3. **Use custom fallback**:
   - Pipeline should fall back automatically to Python implementation
   - If not, check logs for fallback errors
   - Report issue if fallback fails

4. **Alternative: Run without SE tools**:
   - Most phases have custom Python fallbacks
   - May be slightly slower or less comprehensive
   - Still produces valid output

---

### Issue: "Broken pipe" / "BrokenPipeError"

**Symptoms**:
- Pipeline crashes unexpectedly
- Broken pipe error in stderr
- Happens during subprocess call

**Root Cause**:
- SE tool subprocess crashed
- Timeout exceeded
- Out of memory

**Solutions**:

1. **Check subprocess timeout**:
   - Standard timeout: 300 seconds
   - Large EPUBs might need more time
   - Edit phase file to increase timeout if needed

2. **Monitor memory usage**:
   - Run on computer with more RAM
   - Close other applications
   - Use smaller test EPUBs first

3. **Use custom fallback only**:
   - Uninstall SE tools temporarily
   - Forces use of Python fallbacks
   - Tests robustness

---

## 🟡 Quality Issues

### Issue: "F1 Score too low" (< 0.90)

**Symptoms**:
- phase7_report.json shows f1_score: 0.75 or lower
- Rebuilt TOC has wrong headings
- Missing entries in final TOC

**Root Cause**:
- Phase 2 heading detection didn't find all headings
- 6-pass heuristic insufficient for this EPUB
- Custom CSS classes not recognized

**Solutions**:

1. **Analyze Phase 2 detection**:
   ```bash
   python main.py problem.epub --phases 0,1,2,7 --json-reports
   ```
   - Check phase0_report.json
   - Look at: semantic_headings_detected
   - Run Phase 2 specifically: `python main.py problem.epub --phases 2 --verbose`

2. **Improve heading detection**:
   - Check Phase 2 source code: `toc_fixer/pipeline/phase2.py`
   - May need new heuristic pass for this EPUB type
   - Add CSS class pattern to phase2.py if needed

3. **Manually inspect headings**:
   ```bash
   # Run Phase 2 with debug
   python main.py problem.epub --phases 1,2 --debug-output
   
   # Extract and inspect tmp/problem_p2.epub
   unzip tmp/problem_p2.epub -d p2_extracted/
   grep -n "<h1\|<h2\|<h3" p2_extracted/OEBPS/c*.html | head -20
   ```

4. **Compare with ground truth**:
   ```bash
   # If you have ground truth master:
   python main.py problem.epub \
     --ground-truth master.epub \
     --json-reports
   
   # See exactly which entries don't match
   ```

---

### Issue: "Too many linting errors" (> 5 errors)

**Symptoms**:
- phase7_report.json shows multiple se_lint_errors
- Output EPUB doesn't validate
- "Undefined type" or "Missing DOCTYPE" errors

**Root Cause**:
- Phase 1 or Phase 6 didn't clean properly
- Missing metadata elements
- Broken XHTML structure

**Solutions**:

1. **Check lint errors**:
   ```bash
   # Run Phase 7 only (validates without modifying)
   python main.py output.epub --phases 7 --verbose
   
   # See actual errors
   cat reports/*_phase7_report.json | jq '.se_lint_errors'
   ```

2. **Re-run Phase 1**:
   ```bash
   # Phase 1 normalizes HTML/XHTML
   python main.py problem.epub --phases 1 --debug-output
   
   # Verify cleaned output
   python main.py tmp/problem_p1.epub --phases 7
   ```

3. **Run Phase 6 CSS cleanup**:
   ```bash
   # Phase 6 standardizes CSS and metadata
   python main.py problem.epub --phases 1,2,6,7 --debug-output
   ```

4. **Manual validation**:
   ```bash
   # Use epubcheck directly
   epubcheck output.epub
   ```

---

## 🔧 File Management Issues

### Issue: "tmp directory not cleaned up"

**Symptoms**:
- tmp/ directory still exists after normal pipeline run
- Contains old phase output files
- Wastes disk space

**Root Cause**:
- Phase failures leave incomplete files
- Manual debug run with intermediate files
- Cleanup not called or failed

**Solutions**:

1. **Manual cleanup**:
   ```bash
   rm -rf tmp/
   ```

2. **Verify --debug-output not set**:
   ```bash
   # Check command used
   history | grep "python main.py"
   
   # Run without --debug-output
   python main.py wild.epub  # Not: --debug-output
   ```

3. **Check file permissions**:
   - Ensure tmp/ is writable
   - Try cleanup manually: `rmdir tmp/`
   - On Windows: close any open file handles

---

### Issue: "Reports directory doesn't exist or is empty"

**Symptoms**:
- reports/ directory missing
- No phase0_report.json or phase7_report.json
- `--json-reports` flag not working

**Root Cause**:
- `--json-reports` flag not used
- Reports directory creation failed
- Permission issue

**Solutions**:

1. **Use --json-reports flag**:
   ```bash
   # Without flag: no reports (default behavior)
   python main.py wild.epub
   
   # With flag: generates reports
   python main.py wild.epub --json-reports
   ```

2. **Check reports directory**:
   ```bash
   ls -la reports/
   ```

3. **Create reports directory manually**:
   ```bash
   mkdir -p reports/
   python main.py wild.epub --json-reports
   ```

---

## 🐛 Specific Phase Issues

### Phase 1: HTML Cleanup

**Issue**: Boilerplate not removed

```bash
# Run Phase 1 only
python main.py wild.epub --phases 1 --debug-output

# Check output
unzip tmp/wild_p1.epub -d p1/
grep -n "Gutenberg" p1/OEBPS/*.html  # Should be empty
```

**Solution**: Update Gutenberg pattern matching in phase1.py

---

### Phase 2: Heading Detection

**Issue**: Headings not detected

```bash
# Analyze with --verbose
python main.py wild.epub --phases 2 --verbose

# Check what headings were found
unzip tmp/wild_p2.epub -d p2/
grep "<h[1-6]" p2/OEBPS/*.html | wc -l
```

**Solution**: Add new heuristic pass to phase2.py for this EPUB type

---

### Phase 4: TOC Rebuild

**Issue**: rebuilt_toc_entries is 0

```bash
# Phase 4 depends on Phase 2 headings
python main.py wild.epub --phases 1,2,4,7 --json-reports

# Check Phase 2 output for headings
# If headings exist, Phase 4 should find them
```

**Solution**: Verify Phase 2 ran successfully with `--debug-output`

---

### Phase 7: Validation

**Issue**: F1 score calculation fails

```bash
# Requires ground truth
python main.py wild.epub \
  --ground-truth master.epub \
  --json-reports
```

**Solution**: Provide valid ground truth (Standard Ebooks EPUB)

---

## 📊 Diagnostic Commands

### Check EPUB Structure
```bash
python main.py wild.epub --phases 0 --json-reports
# Read reports/wild_phase0_report.json
```

### Test Specific Phase
```bash
python main.py wild.epub --phases 2 --debug-output --verbose
# Inspect tmp/wild_p2.epub and logs
```

### Score Against Ground Truth
```bash
python main.py wild.epub \
  --ground-truth master.epub \
  --json-reports
# Read phase7_report.json for F1 score
```

### Full Validation
```bash
python main.py wild.epub --validate --json-reports --verbose
# Runs epubcheck and se lint
```

### Manual EPUB Inspection
```bash
unzip wild.epub -d extracted/
ls extracted/
cat extracted/META-INF/container.xml
cat extracted/content.opf | head -50
head -20 extracted/OEBPS/toc.ncx
```

---

## 📚 Getting Help

1. **Check the wiki**: Look for your issue in [Home](00-HOME.md)
2. **Read relevant guide**: Phase guide, core utilities, architecture
3. **Run diagnostics**: Use commands above to gather information
4. **Check logs**: Look at phase reports (JSON)
5. **Search issues**: GitHub issues for similar problems
6. **Ask for help**: Create detailed issue with test EPUB

---

**Next**: If you're stuck, [Contact Support](#contact) or [Check API Reference](14-API-REFERENCE.md).
