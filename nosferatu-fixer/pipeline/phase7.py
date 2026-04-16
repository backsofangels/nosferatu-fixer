"""Phase 7 — Validation (se lint, epubcheck, F1 scoring)."""

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from zipfile import ZipFile

from bs4 import BeautifulSoup

from ..core import PipelineReport, TocEntry, build_zip_key, safe_read, select_parser


class Phase7Validator:
    """Validation using se lint, epubcheck, and F1 scoring."""

    def __init__(self, epub_path: str, report: PipelineReport, ground_truth_path: Optional[str] = None):
        """
        Initialize Phase 7 validator.
        
        Args:
            epub_path: Path to the EPUB file to validate
            report: PipelineReport instance
            ground_truth_path: Optional path to ground truth EPUB for F1 scoring
        """
        self.epub_path = epub_path
        self.report = report
        self.ground_truth_path = ground_truth_path
        self.rebuilt_toc: list[TocEntry] = []
        self.ground_truth_toc: list[TocEntry] = []

    def run_validation(self) -> bool:
        """
        Run all validation steps.
        
        Returns:
            True if validation completed successfully
        """
        try:
            # Extract rebuilt TOC from EPUB
            self._extract_builttoc()
            
            # Run se lint
            self._run_se_lint()
            
            # Run epubcheck if requested
            self._run_epubcheck()
            
            # Compute F1 score if ground truth available
            if self.ground_truth_path:
                self._compute_f1_score()
            
            return True
        
        except Exception as e:
            self.report.validation_errors.append(f"Phase 7 validation failed: {str(e)}")
            return False

    def _extract_builttoc(self) -> None:
        """Extract TOC entries from built EPUB."""
        try:
            with ZipFile(self.epub_path, "r") as zf:
                # Try multiple file name patterns for nav/toc in XHTML format
                nav_candidates = [n for n in zf.namelist() if any(x in n.lower() for x in ["nav.xhtml", "toc.xhtml", "navigation.xhtml"])]
                
                if nav_candidates:
                    nav_content = zf.read(nav_candidates[0]).decode("utf-8", errors="replace")
                    soup = BeautifulSoup(nav_content, "lxml-xml")
                    
                    # Find toc navigation element
                    toc_nav = soup.find("nav", attrs={"epub:type": re.compile(r"toc", re.IGNORECASE)})
                    if toc_nav:
                        self._extract_toc_from_nav(toc_nav)
                
                # Fallback: try NCX
                if not self.rebuilt_toc:
                    ncx_candidates = [n for n in zf.namelist() if n.endswith(".ncx")]
                    if ncx_candidates:
                        ncx_content = zf.read(ncx_candidates[0]).decode("utf-8", errors="replace")
                        self._extract_toc_from_ncx(ncx_content)
        
        except Exception as e:
            self.report.warnings.append(f"Failed to extract built TOC: {str(e)}")

    def _extract_toc_from_nav(self, nav_element) -> None:
        """Extract TOC entries from nav.xhtml element."""
        try:
            ol = nav_element.find("ol")
            if ol:
                for li in ol.find_all("li", recursive=False):
                    self._extract_nav_entry(li)
        
        except Exception as e:
            self.report.warnings.append(f"Failed to parse nav.xhtml: {str(e)}")

    def _extract_nav_entry(self, li_element) -> None:
        """Recursively extract nav entries."""
        try:
            a = li_element.find("a", recursive=False)
            if a:
                href = a.get("href", "")
                text = a.get_text(separator=" ", strip=True)
                
                if href and text:
                    # Extract file_part (remove anchor)
                    file_part = href.split("#")[0]
                    anchor = href.split("#")[1] if "#" in href else None
                    
                    entry = TocEntry(
                        title=text,
                        href=href,
                        file_part=file_part,
                        anchor=anchor,
                        level=1,
                        source="validation",
                        confidence=1.0
                    )
                    self.rebuilt_toc.append(entry)
            
            # Recursively process nested ol
            nested_ol = li_element.find("ol")
            if nested_ol:
                for nested_li in nested_ol.find_all("li", recursive=False):
                    self._extract_nav_entry(nested_li)
        
        except Exception as e:
            self.report.warnings.append(f"Failed to extract nav entry: {str(e)}")

    def _extract_toc_from_ncx(self, ncx_content: str) -> None:
        """Extract TOC entries from NCX file."""
        try:
            soup = BeautifulSoup(ncx_content, "lxml-xml")
            NCX_NS = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
            
            nav_map = soup.find("navmap", recursive=False)
            if nav_map:
                for nav_point in nav_map.findall(".//ncx:navPoint", NCX_NS):
                    self._extract_ncx_entry(nav_point, NCX_NS)
        
        except Exception as e:
            self.report.warnings.append(f"Failed to parse NCX: {str(e)}")

    def _extract_ncx_entry(self, nav_point, ncx_ns) -> None:
        """Recursively extract NCX entries."""
        try:
            label_elem = nav_point.find("ncx:navLabel", namespaces=ncx_ns)
            content_elem = nav_point.find("ncx:content", namespaces=ncx_ns)
            
            if label_elem and content_elem:
                text = label_elem.findtext("ncx:text", namespaces=ncx_ns)
                src = content_elem.get("src", "")
                
                if text and src:
                    file_part = src.split("#")[0]
                    anchor = src.split("#")[1] if "#" in src else None
                    
                    entry = TocEntry(
                        title=text,
                        href=src,
                        file_part=file_part,
                        anchor=anchor,
                        level=1,
                        source="validation",
                        confidence=1.0
                    )
                    self.rebuilt_toc.append(entry)
        
        except Exception as e:
            self.report.warnings.append(f"Failed to extract NCX entry: {str(e)}")

    def _run_se_lint(self) -> None:
        """Run se lint on the EPUB."""
        try:
            with tempfile.TemporaryDirectory(prefix="epub_") as temp_dir:
                temp_path = Path(temp_dir)
                
                # Unpack EPUB
                with ZipFile(self.epub_path, "r") as zf:
                    zf.extractall(temp_path)
                
                # Run se lint
                result = subprocess.run(
                    ["se", "lint", str(temp_path)],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                # Parse output for errors and warnings
                self._parse_se_lint_output(result.stdout, result.stderr)
        
        except FileNotFoundError:
            self.report.warnings.append("se lint tool not found, skipping lint validation")
        except subprocess.TimeoutExpired:
            self.report.warnings.append("se lint timed out")
        except Exception as e:
            self.report.warnings.append(f"se lint error: {str(e)}")

    def _parse_se_lint_output(self, stdout: str, stderr: str) -> None:
        """Parse se lint output for errors and warnings."""
        try:
            output = stdout + stderr
            
            # Extract error lines (se lint format: "path/file: error message")
            error_pattern = re.compile(r"^([^:]+):(\d+):(\d+):\s*error:\s*(.+)$", re.MULTILINE)
            warning_pattern = re.compile(r"^([^:]+):(\d+):(\d+):\s*warning:\s*(.+)$", re.MULTILINE)
            
            errors = error_pattern.findall(output)
            warnings = warning_pattern.findall(output)
            
            for error in errors:
                self.report.validation_errors.append(f"{error[0]}:{error[1]} - {error[3]}")
            
            for warning in warnings:
                self.report.warnings.append(f"{warning[0]}:{warning[1]} - {warning[3]}")
            
            if errors:
                self.report.warnings.append(f"se lint found {len(errors)} errors")
            if warnings:
                self.report.warnings.append(f"se lint found {len(warnings)} warnings")
        
        except Exception as e:
            self.report.warnings.append(f"Failed to parse se lint output: {str(e)}")

    def _run_epubcheck(self) -> None:
        """Run epubcheck validation (optional, requires Java)."""
        try:
            result = subprocess.run(
                ["java", "-jar", "epubcheck.jar", self.epub_path],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Parse output for errors
            error_pattern = re.compile(r"ERROR\(.*?\):\s*(.+)")
            errors = error_pattern.findall(result.stdout + result.stderr)
            
            for error in errors:
                self.report.validation_errors.append(f"epubcheck: {error}")
            
            if errors:
                self.report.warnings.append(f"epubcheck found {len(errors)} errors")
        
        except FileNotFoundError:
            self.report.warnings.append("epubcheck or Java not found, skipping epubcheck validation")
        except subprocess.TimeoutExpired:
            self.report.warnings.append("epubcheck timed out")
        except Exception as e:
            self.report.warnings.append(f"epubcheck error: {str(e)}")

    def _compute_f1_score(self) -> None:
        """Compute F1 score by comparing rebuilt TOC against ground truth."""
        try:
            # Extract ground truth TOC
            self._extract_ground_truth_toc()
            
            if not self.ground_truth_toc:
                self.report.warnings.append("Could not extract ground truth TOC")
                return
            
            # Compute F1
            f1 = self._compute_f1(self.rebuilt_toc, self.ground_truth_toc)
            self.report.f1_score = f1
            
            self.report.warnings.append(f"F1 score computed: {f1:.3f}")
        
        except Exception as e:
            self.report.warnings.append(f"Failed to compute F1 score: {str(e)}")

    def _extract_ground_truth_toc(self) -> None:
        """Extract TOC entries from ground truth EPUB."""
        try:
            with ZipFile(self.ground_truth_path, "r") as zf:
                # Try multiple file name patterns for nav/toc in XHTML format
                nav_candidates = [n for n in zf.namelist() if any(x in n.lower() for x in ["nav.xhtml", "toc.xhtml", "navigation.xhtml"])]
                
                if nav_candidates:
                    nav_content = zf.read(nav_candidates[0]).decode("utf-8", errors="replace")
                    soup = BeautifulSoup(nav_content, "lxml-xml")
                    
                    toc_nav = soup.find("nav", attrs={"epub:type": re.compile(r"toc", re.IGNORECASE)})
                    if toc_nav:
                        self._extract_toc_from_nav_for_ground_truth(toc_nav)
                
                # Fallback to NCX
                if not self.ground_truth_toc:
                    ncx_candidates = [n for n in zf.namelist() if n.endswith(".ncx")]
                    if ncx_candidates:
                        ncx_content = zf.read(ncx_candidates[0]).decode("utf-8", errors="replace")
                        self._extract_toc_from_ncx_for_ground_truth(ncx_content)
        
        except Exception as e:
            self.report.warnings.append(f"Failed to extract ground truth TOC: {str(e)}")

    def _extract_toc_from_nav_for_ground_truth(self, nav_element) -> None:
        """Extract TOC entries from ground truth nav.xhtml element."""
        try:
            ol = nav_element.find("ol")
            if ol:
                for li in ol.find_all("li", recursive=False):
                    self._extract_nav_entry_for_ground_truth(li)
        
        except Exception as e:
            self.report.warnings.append(f"Failed to parse ground truth nav.xhtml: {str(e)}")

    def _extract_nav_entry_for_ground_truth(self, li_element) -> None:
        """Recursively extract ground truth nav entries."""
        try:
            a = li_element.find("a", recursive=False)
            if a:
                href = a.get("href", "")
                text = a.get_text(separator=" ", strip=True)
                
                if href and text:
                    file_part = href.split("#")[0]
                    anchor = href.split("#")[1] if "#" in href else None
                    
                    entry = TocEntry(
                        title=text,
                        href=href,
                        file_part=file_part,
                        anchor=anchor,
                        level=1,
                        source="ground_truth",
                        confidence=1.0
                    )
                    self.ground_truth_toc.append(entry)
            
            nested_ol = li_element.find("ol")
            if nested_ol:
                for nested_li in nested_ol.find_all("li", recursive=False):
                    self._extract_nav_entry_for_ground_truth(nested_li)
        
        except Exception as e:
            self.report.warnings.append(f"Failed to extract ground truth nav entry: {str(e)}")

    def _extract_toc_from_ncx_for_ground_truth(self, ncx_content: str) -> None:
        """Extract TOC entries from ground truth NCX file."""
        try:
            soup = BeautifulSoup(ncx_content, "lxml-xml")
            NCX_NS = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
            
            nav_map = soup.find("navmap", recursive=False)
            if nav_map:
                for nav_point in nav_map.findall(".//ncx:navPoint", NCX_NS):
                    self._extract_ncx_entry_for_ground_truth(nav_point, NCX_NS)
        
        except Exception as e:
            self.report.warnings.append(f"Failed to parse ground truth NCX: {str(e)}")

    def _extract_ncx_entry_for_ground_truth(self, nav_point, ncx_ns) -> None:
        """Recursively extract ground truth NCX entries."""
        try:
            label_elem = nav_point.find("ncx:navLabel", namespaces=ncx_ns)
            content_elem = nav_point.find("ncx:content", namespaces=ncx_ns)
            
            if label_elem and content_elem:
                text = label_elem.findtext("ncx:text", namespaces=ncx_ns)
                src = content_elem.get("src", "")
                
                if text and src:
                    file_part = src.split("#")[0]
                    anchor = src.split("#")[1] if "#" in src else None
                    
                    entry = TocEntry(
                        title=text,
                        href=src,
                        file_part=file_part,
                        anchor=anchor,
                        level=1,
                        source="ground_truth",
                        confidence=1.0
                    )
                    self.ground_truth_toc.append(entry)
        
        except Exception as e:
            self.report.warnings.append(f"Failed to extract ground truth NCX entry: {str(e)}")

    def _compute_f1(self, rebuilt: list[TocEntry], ground_truth: list[TocEntry]) -> float:
        """
        Compute F1 score by comparing file_part references.
        
        Args:
            rebuilt: Rebuilt TOC entries
            ground_truth: Ground truth TOC entries
            
        Returns:
            F1 score (0.0 to 1.0)
        """
        rebuilt_files = {e.file_part for e in rebuilt if e.file_part}
        gt_files = {e.file_part for e in ground_truth if e.file_part}
        
        true_positives = len(rebuilt_files & gt_files)
        
        if not rebuilt_files and not gt_files:
            return 1.0  # Both empty = perfect match
        
        if not rebuilt_files or not gt_files:
            return 0.0  # One empty, other not = no match
        
        precision = true_positives / len(rebuilt_files) if rebuilt_files else 0.0
        recall = true_positives / len(gt_files) if gt_files else 0.0
        
        if precision + recall == 0:
            return 0.0
        
        f1 = 2 * precision * recall / (precision + recall)
        
        return f1

    def generate_report(self, output_path: str) -> None:
        """
        Generate phase7_report.json.
        
        Args:
            output_path: Path where report should be written (optional)
        """
        # Only generate if output_path is provided
        if not output_path:
            return
        
        try:
            report_data = {
                "input": self.report.input,
                "output": self.report.output or str(Path(self.epub_path).stem) + "_clean.epub",
                "epub_version": self.report.epub_version,
                "phases_run": self.report.phases_run,
                "original_toc_entries": self.report.original_toc_entries,
                "rebuilt_toc_entries": self.report.rebuilt_toc_entries,
                "injected_anchors": self.report.injected_anchors,
                "detection_sources": self.report.detection_sources,
                "spine_files_without_toc_entry": self.report.spine_files_without_toc_entry,
                "se_lint_errors": [e for e in self.report.validation_errors if not e.startswith("epubcheck")],
                "epubcheck_errors": [e for e in self.report.validation_errors if e.startswith("epubcheck")],
                "f1_score": self.report.f1_score,
                "warnings": self.report.warnings[:5],  # Include top 5 warnings
                "timestamp": str(Path(__file__).parent)
            }
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2)
            
            self.report.warnings.append(f"Phase 7 report written to {output_path}")
        
        except Exception as e:
            self.report.validation_errors.append(f"Failed to generate Phase 7 report: {str(e)}")


def run_phase7(
    input_epub: str,
    report_path: str,
    report: PipelineReport,
    ground_truth_path: Optional[str] = None
) -> bool:
    """
    Run Phase 7: Validation and F1 scoring.
    
    Args:
        input_epub: Path to EPUB file to validate
        report_path: Path where phase7_report.json should be written
        report: PipelineReport instance
        ground_truth_path: Optional path to ground truth EPUB for F1 scoring
        
    Returns:
        True if validation completed successfully
    """
    try:
        validator = Phase7Validator(input_epub, report, ground_truth_path)
        report.phases_run.append("7")
        
        # Run validation
        if not validator.run_validation():
            return False
        
        # Generate report
        validator.generate_report(report_path)
        
        return True
    
    except Exception as e:
        report.validation_errors.append(f"Phase 7 failed: {str(e)}")
        return False
