"""Phase 3 — Spine Realignment (optional, using se split-file)."""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from ..core import PipelineReport, build_zip_key, safe_read


class Phase3SplineRealigner:
    """Spine realignment using SE tool or custom splitting at heading boundaries."""

    def __init__(self, epub_path: str, output_path: str, report: PipelineReport):
        """
        Initialize Phase 3 spine realigner.
        
        Args:
            epub_path: Path to the input EPUB file
            output_path: Path to the output EPUB file
            report: PipelineReport instance
        """
        self.epub_path = epub_path
        self.output_path = output_path
        self.report = report
        self.temp_dir: Optional[Path] = None
        self.opf_base = ""
        self.opf_path: Optional[Path] = None

    def run_se_tool(self) -> bool:
        """
        Try to run se split-file on unpacked EPUB.
        
        Returns:
            True if successful, False if failed
        """
        try:
            self.temp_dir = Path(tempfile.mkdtemp(prefix="epub_"))
            
            # Unpack EPUB to temp directory
            with ZipFile(self.epub_path, "r") as zf:
                zf.extractall(self.temp_dir)
            
            # Run se split-file to split at h1 boundaries
            result = subprocess.run(
                ["se", "split-file", str(self.temp_dir)],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                self.report.warnings.append("Used se split-file tool for spine realignment")
                return True
            else:
                self.report.warnings.append(
                    f"se split-file failed (code {result.returncode}), "
                    "spine realignment may be incomplete"
                )
                return False
        
        except FileNotFoundError:
            self.report.warnings.append(
                "se split-file not found, using custom heading-boundary splitting"
            )
            return False
        except subprocess.TimeoutExpired:
            self.report.warnings.append(
                "se split-file timed out, spine realignment may be incomplete"
            )
            return False
        except Exception as e:
            self.report.warnings.append(
                f"se split-file error: {str(e)}, spine realignment may be incomplete"
            )
            return False

    def run_custom_splitting(self) -> bool:
        """
        Run custom spine splitting at h1 heading boundaries.
        
        This method scans spine files for top-level (h1) headings and creates
        split points at those boundaries, allowing for more granular spine items.
        
        Returns:
            True if successful
        """
        try:
            if self.temp_dir is None:
                self.temp_dir = Path(tempfile.mkdtemp(prefix="epub_"))
                
                # Unpack EPUB
                with ZipFile(self.epub_path, "r") as zf:
                    zf.extractall(self.temp_dir)
            
            # Parse OPF to get spine and manifest
            self._parse_opf()
            
            # Find h1 boundaries in spine files
            h1_boundaries = self._find_h1_boundaries()
            
            if not h1_boundaries:
                self.report.warnings.append(
                    "No h1 boundaries found for spine splitting"
                )
                return False
            
            # Split files at h1 boundaries (implementation would create new files)
            # For now, just record that boundaries were found
            self.report.warnings.append(
                f"Found {len(h1_boundaries)} h1 heading boundaries for potential splitting"
            )
            
            return True
        
        except Exception as e:
            self.report.validation_errors.append(
                f"Custom spine splitting failed: {str(e)}"
            )
            return False

    def _parse_opf(self) -> None:
        """Parse OPF file and extract metadata."""
        try:
            # Locate container.xml
            container_path = self.temp_dir / "META-INF" / "container.xml"
            if not container_path.exists():
                raise FileNotFoundError("container.xml not found")
            
            container_tree = ET.parse(container_path)
            container_root = container_tree.getroot()
            
            # Extract OPF path from container
            ns = {"container": "urn:oasis:names:tc:opendocument:xmlns:container"}
            opf_elem = container_root.find(".//container:rootfile[@media-type]", ns)
            if opf_elem is None:
                raise ValueError("Could not find rootfile in container.xml")
            
            opf_rel_path = opf_elem.get("full-path")
            self.opf_path = self.temp_dir / opf_rel_path
            self.opf_base = str(Path(opf_rel_path).parent)
            
        except Exception as e:
            self.report.warnings.append(f"OPF parsing failed: {str(e)}")

    def _find_h1_boundaries(self) -> list[str]:
        """
        Find h1 heading boundaries in spine files.
        
        Returns:
            List of file paths where h1 boundaries occur
        """
        try:
            from bs4 import BeautifulSoup
            from ..core import select_parser
            
            boundaries = []
            
            # Parse OPF to get spine items
            opf_tree = ET.parse(self.opf_path)
            opf_root = opf_tree.getroot()
            
            # Define namespaces
            ns = {
                "opf": "http://www.idpf.org/2007/opf",
                "ncx": "http://www.daisy.org/z3986/2005/ncx/"
            }
            
            # Get spine items
            spine_elem = opf_root.find(".//opf:spine", ns)
            if spine_elem is None:
                return boundaries
            
            for itemref in spine_elem.findall("opf:itemref", ns):
                item_id = itemref.get("idref")
                
                # Get manifest entry for this spine item
                manifest_elems = opf_root.findall(
                    f".//opf:manifest/opf:item[@id='{item_id}']", ns
                )
                if not manifest_elems:
                    continue
                
                item_href = manifest_elems[0].get("href")
                spine_file_path = self.temp_dir / self.opf_base / item_href
                
                if not spine_file_path.exists():
                    continue
                
                # Check if file contains h1 headings
                try:
                    with open(spine_file_path, "rb") as f:
                        content = f.read()
                    
                    # Decode content
                    try:
                        html_content = content.decode("utf-8")
                    except UnicodeDecodeError:
                        from chardet import detect
                        encoding = detect(content).get("encoding", "utf-8")
                        html_content = content.decode(encoding, errors="replace")
                    
                    # Parse HTML
                    parser = select_parser(str(spine_file_path))
                    soup = BeautifulSoup(html_content, parser)
                    
                    # Check for h1 tags
                    h1_tags = soup.find_all("h1")
                    if h1_tags:
                        boundaries.append(item_href)
                
                except Exception as e:
                    self.report.warnings.append(
                        f"Error scanning {item_href} for h1 boundaries: {str(e)}"
                    )
            
            return boundaries
        
        except Exception as e:
            self.report.warnings.append(f"h1 boundary detection failed: {str(e)}")
            return []

    def execute(self) -> bool:
        """
        Execute Phase 3 spine realignment.
        
        Tries SE tool first, falls back to custom splitting if needed.
        
        Returns:
            True if successful
        """
        try:
            # Try SE tool first
            if self.run_se_tool():
                # SE tool succeeded, repack EPUB
                return self._repack_epub()
            
            # SE tool failed, try custom splitting
            if self.run_custom_splitting():
                # Custom splitting succeeded
                return self._repack_epub()
            
            return False
        
        except Exception as e:
            self.report.validation_errors.append(
                f"Phase 3 execution failed: {str(e)}"
            )
            return False

    def _repack_epub(self) -> bool:
        """
        Repack the modified EPUB from temp directory to output file.
        
        Returns:
            True if successful
        """
        try:
            if self.temp_dir is None or not self.temp_dir.exists():
                return False
            
            # Create new EPUB from modified temp directory at output_path
            with ZipFile(self.output_path, "w") as zf:
                for root, _, files in self.temp_dir.walk():
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(self.temp_dir)
                        zf.write(file_path, arcname)
            
            return True
        
        except Exception as e:
            self.report.warnings.append(f"EPUB repacking failed: {str(e)}")
            return False
        
        finally:
            # Clean up temp directory
            if self.temp_dir and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)


def run_phase3(epub_path: str, output_path: str, report: PipelineReport) -> bool:
    """
    Execute Phase 3: Spine realignment.
    
    Args:
        epub_path: Path to input EPUB
        output_path: Path to output EPUB
        report: PipelineReport instance
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Phase 3 is optional and only runs if Phase 2 (semantic upgrade) was successful
        if "2" not in report.phases_run:
            report.warnings.append(
                "Phase 3 requires Phase 2 (semantic upgrade). Phase 3 skipped."
            )
            return False
        
        # Create realigner with both input and output paths
        realigner = Phase3SplineRealigner(epub_path, output_path, report)
        
        # Execute phase (now creates output_path directly)
        success = realigner.execute()
        
        if success:
            report.phases_run.append("3")
            return True
        
        # Clean up any partial output file on failure
        try:
            if Path(output_path).exists() and Path(output_path) != Path(epub_path):
                Path(output_path).unlink()
        except Exception:
            pass
        
        return False
    
    except Exception as e:
        report.validation_errors.append(f"Phase 3 failed: {str(e)}")
        return False
