"""Phase 0 — EPUB Diagnosis and Analysis."""

import json
import posixpath
import re
import warnings
from pathlib import Path
from typing import Optional
from zipfile import ZipFile

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from ..core import (
    PipelineReport,
    SpineItem,
    build_zip_key,
    parse_ncx_entries,
    resolve_ncx_path,
    safe_read,
    select_parser,
)

# Suppress XML-as-HTML warnings (expected when parsing XML with lxml parser)
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


class Phase0Analyzer:
    """Diagnose EPUB structure and produce phase0_report.json"""

    def __init__(self, epub_path: str):
        self.epub_path = epub_path
        self.zip_file: Optional[ZipFile] = None
        self.report = PipelineReport(input=epub_path, output="")
        self.opf_path: str = ""
        self.opf_base: str = ""
        self.opf_soup: Optional[BeautifulSoup] = None
        self.ncx_entries: list[tuple[str, str]] = []

    def analyze(self) -> PipelineReport:
        """Run full Phase 0 analysis."""
        try:
            with ZipFile(self.epub_path, "r") as zf:
                self.zip_file = zf
                
                # Read container.xml to find OPF
                self._read_epub_version()
                self._detect_toc_format()
                self._read_language_and_direction()
                self._read_drm_status()
                self._read_spine_structure()
                self._read_markup_quality()
                self._determine_dominant_pattern()
                self._recommend_phases()
                
        except Exception as e:
            self.report.validation_errors.append(f"Phase 0 analysis failed: {str(e)}")
        
        return self.report

    def _read_epub_version(self) -> None:
        """Extract EPUB version and OPF path from container.xml"""
        try:
            container_bytes = self.zip_file.read("META-INF/container.xml")
            container_soup = BeautifulSoup(container_bytes, "lxml-xml")
            
            # Get OPF path
            rootfile = container_soup.find("rootfile")
            if rootfile:
                self.opf_path = rootfile.get("full-path", "content.opf")
                self.opf_base = posixpath.dirname(self.opf_path)
                
                # Read OPF
                opf_bytes = safe_read(self.zip_file, self.opf_path)
                if opf_bytes:
                    self.opf_soup = BeautifulSoup(opf_bytes, "lxml-xml")
                    
                    # Extract version
                    package = self.opf_soup.find("package")
                    if package:
                        version = package.get("version", "2.0")
                        # Normalize version (2.0 or 3.0)
                        if version.startswith("3"):
                            self.report.epub_version = "3.0"
                        else:
                            self.report.epub_version = "2.0"
                    
                    # Try to resolve NCX path
                    ncx_path = resolve_ncx_path(container_bytes, self.opf_path, self.zip_file)
                    if ncx_path:
                        ncx_bytes = safe_read(self.zip_file, ncx_path)
                        if ncx_bytes:
                            self.ncx_entries = parse_ncx_entries(ncx_bytes)
                            self.report.original_toc_entries = len(self.ncx_entries)
        except Exception as e:
            self.report.validation_errors.append(f"Could not read EPUB version: {str(e)}")

    def _detect_toc_format(self) -> None:
        """Detect original TOC format (NCX, nav.xhtml, both, or none)."""
        try:
            has_ncx = False
            has_nav = False
            
            # Check for NCX
            container_bytes = self.zip_file.read("META-INF/container.xml")
            ncx_path = resolve_ncx_path(container_bytes, self.opf_path, self.zip_file)
            if ncx_path and safe_read(self.zip_file, ncx_path):
                has_ncx = True
            
            # Check for nav.xhtml (EPUB3 navigation)
            # Look for files with epub:type="toc" in the manifest
            if self.opf_soup:
                # Check manifest for nav document
                nav_items = self.opf_soup.find_all("item", {"properties": re.compile(r"nav")})
                if nav_items:
                    for item in nav_items:
                        nav_href = item.get("href")
                        if nav_href:
                            nav_key = build_zip_key(self.opf_base, nav_href)
                            nav_content = safe_read(self.zip_file, nav_key)
                            if nav_content:
                                # Verify it contains nav epub:type="toc"
                                nav_soup = BeautifulSoup(nav_content, "lxml-xml")
                                if nav_soup.find("nav", {"epub:type": "toc"}) or nav_soup.find("nav", {"epub-type": "toc"}):
                                    has_nav = True
                                    break
            
            # Determine format
            if has_ncx and has_nav:
                self.report.original_toc_format = "both"
            elif has_nav:
                self.report.original_toc_format = "nav"
            elif has_ncx:
                self.report.original_toc_format = "ncx"
            else:
                self.report.original_toc_format = "none"
        
        except Exception as e:
            self.report.warnings.append(f"Could not detect TOC format: {str(e)}")

    def _read_language_and_direction(self) -> None:
        """Extract language and RTL status from OPF."""
        if not self.opf_soup:
            return
        
        try:
            # Language
            dc_lang = self.opf_soup.find("dc:language")
            if dc_lang:
                self.report.language = dc_lang.get_text(strip=True)
            
            # RTL
            spine = self.opf_soup.find("spine")
            if spine and spine.get("page-progression-direction") == "rtl":
                self.report.rtl = True
            
            # Fixed layout
            if self.opf_soup.find("meta", {"property": "rendition:layout"}):
                meta = self.opf_soup.find("meta", {"property": "rendition:layout"})
                if meta and "pre-paginated" in meta.get("content", ""):
                    self.report.fixed_layout = True
        except Exception as e:
            self.report.warnings.append(f"Could not read metadata: {str(e)}")

    def _read_drm_status(self) -> None:
        """Check for DRM protection on content items."""
        try:
            encryption_path = "META-INF/encryption.xml"
            if encryption_path in self.zip_file.namelist():
                encryption_bytes = self.zip_file.read(encryption_path)
                encryption_soup = BeautifulSoup(encryption_bytes, "lxml-xml")
                
                # Check for EncryptedData on content items (not just fonts)
                encrypted_data = encryption_soup.find_all("EncryptedData")
                for data in encrypted_data:
                    # If ANY content file (not font) is encrypted, flag DRM
                    # For simplicity, just flag if any EncryptedData exists
                    self.report.drm = True
                    self.report.validation_errors.append(
                        "EPUB contains DRM-protected content. Cannot process."
                    )
                    break
        except Exception:
            pass

    def _read_spine_structure(self) -> None:
        """Analyze spine structure: count files, extract manifest."""
        if not self.opf_soup:
            return
        
        try:
            spine = self.opf_soup.find("spine")
            manifest = self.opf_soup.find("manifest")
            
            if spine:
                spine_items = spine.find_all("itemref")
                self.report.spine_items = len(spine_items)
                
                # Build manifest dict
                manifest_dict = {}
                if manifest:
                    for item in manifest.find_all("item"):
                        item_id = item.get("id")
                        if item_id:
                            manifest_dict[item_id] = {
                                "href": item.get("href", ""),
                                "media-type": item.get("media-type", ""),
                            }
                
                # Scan each spine file for structure analysis
                semantic_headings = 0
                epub_type_tags = 0
                
                for itemref in spine_items:
                    idref = itemref.get("idref")
                    if idref and idref in manifest_dict:
                        item_href = manifest_dict[idref]["href"]
                        zip_key = build_zip_key(self.opf_base, item_href)
                        
                        content = safe_read(self.zip_file, zip_key)
                        if content:
                            parser = select_parser(item_href)
                            try:
                                soup = BeautifulSoup(content, parser)
                                
                                # Count semantic headings
                                h_tags = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
                                semantic_headings += len(h_tags)
                                
                                # Count epub:type attributes
                                epub_type_tags += len(soup.find_all(True, {"epub:type": True}))
                            except Exception:
                                pass
                
                self.report.semantic_headings_found = semantic_headings
                self.report.epub_type_tags_found = epub_type_tags
        except Exception as e:
            self.report.warnings.append(f"Could not read spine structure: {str(e)}")

    def _read_markup_quality(self) -> None:
        """Classify markup quality based on found elements."""
        if self.report.fixed_layout:
            self.report.markup_quality = "fixed_layout"
        elif self.report.semantic_headings_found > 0 and self.report.epub_type_tags_found > 0:
            self.report.markup_quality = "clean"
        elif self.report.semantic_headings_found > 0 or self.report.epub_type_tags_found > 0:
            self.report.markup_quality = "partial"
        elif self.report.original_toc_entries > 0:
            # Has NCX entries but flat markup
            self.report.markup_quality = "flat_calibre"
        else:
            self.report.markup_quality = "no_markup"

    def _count_chapter_patterns(self) -> int:
        """Count detected chapter patterns using regex."""
        if not self.opf_soup or self.report.spine_items == 0:
            return max(1, self.report.original_toc_entries)
        
        chapter_pattern = re.compile(
            r"(Capitolo|Chapter|CHAPTER|CAP\.)\s+[\dIVXLCivxlc]+",
            re.IGNORECASE
        )
        
        count = 0
        spine = self.opf_soup.find("spine")
        manifest = self.opf_soup.find("manifest")
        
        if spine and manifest:
            spine_items = spine.find_all("itemref")
            manifest_dict = {item.get("id"): item for item in manifest.find_all("item")}
            
            for itemref in spine_items:
                idref = itemref.get("idref")
                if idref and idref in manifest_dict:
                    item = manifest_dict[idref]
                    item_href = item.get("href", "")
                    zip_key = build_zip_key(self.opf_base, item_href)
                    
                    content = safe_read(self.zip_file, zip_key)
                    if content:
                        try:
                            text = content.decode("utf-8", errors="ignore")
                            if chapter_pattern.search(text):
                                count += 1
                        except Exception:
                            pass
        
        return max(count, self.report.original_toc_entries)

    def _determine_dominant_pattern(self) -> None:
        """Determine whether it's calibre_split, one_file_one_chapter, single_file, or fixed_layout."""
        if self.report.fixed_layout:
            self.report.dominant_pattern = "fixed_layout"
        elif self.report.spine_items == 1:
            self.report.dominant_pattern = "single_file"
        else:
            # Estimate chapters
            estimated = self._count_chapter_patterns()
            self.report.estimated_chapters = estimated
            
            # If spine_items ≈ estimated_chapters, it's one_file_one_chapter
            # Otherwise, it's calibre_split
            ratio = self.report.spine_items / max(1, estimated)
            if 0.8 <= ratio <= 1.5:
                self.report.dominant_pattern = "one_file_one_chapter"
            else:
                self.report.dominant_pattern = "calibre_split"

    def _recommend_phases(self) -> None:
        """Recommend which phases to run based on diagnostic."""
        # Default: run all phases
        recommended = ["1", "2", "3", "4", "5", "6", "7"]
        
        # If DRM, abort
        if self.report.drm:
            recommended = []
        # If clean markup with epub:type tags, skip 1, 2, 3
        elif self.report.markup_quality == "clean" and self.report.epub_type_tags_found > 0:
            recommended = ["4", "5", "6", "7"]
        # If fixed layout, simpler phases
        elif self.report.fixed_layout:
            recommended = ["1", "4", "7"]
        # If single file, skip 3 (spine realignment)
        elif self.report.dominant_pattern == "single_file":
            recommended = ["1", "2", "4", "5", "7"]
        
        self.report.recommended_phases = recommended


def run_phase0(epub_path: str, output_path: str = "phase0_report.json") -> PipelineReport:
    """
    Run Phase 0 analysis on an EPUB file.
    
    Args:
        epub_path: Path to input EPUB
        output_path: Path to output JSON report
    
    Returns:
        PipelineReport with diagnostic data
    """
    analyzer = Phase0Analyzer(epub_path)
    report = analyzer.analyze()
    
    # Write report as JSON
    report_dict = {
        "input": report.input,
        "output": report.output,
        "epub_version": report.epub_version,
        "language": report.language,
        "fixed_layout": report.fixed_layout,
        "rtl": report.rtl,
        "drm": report.drm,
        "dominant_pattern": report.dominant_pattern,
        "markup_quality": report.markup_quality,
        "spine_items": report.spine_items,
        "estimated_chapters": report.estimated_chapters,
        "semantic_headings_found": report.semantic_headings_found,
        "epub_type_tags_found": report.epub_type_tags_found,
        "original_toc_entries": report.original_toc_entries,
        "original_toc_format": report.original_toc_format,
        "recommended_phases": report.recommended_phases,
        "validation_errors": report.validation_errors,
        "warnings": report.warnings,
    }
    
    # Only write report if output_path is provided
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2)
    
    return report
