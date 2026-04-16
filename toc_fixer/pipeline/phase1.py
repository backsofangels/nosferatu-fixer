"""Phase 1 — HTML Cleanup."""

import re
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from chardet import detect

from ..core import EPUBPhaseBase, PipelineReport, select_parser


class Phase1Cleaner(EPUBPhaseBase):
    """HTML cleanup using SE tool or custom implementation."""

    def __init__(self, epub_path: str, report: PipelineReport):
        super().__init__(epub_path, report)

    @property
    def se_tool_timeout(self) -> int:
        """SE clean typically completes quickly."""
        return 60

    def _run_custom_implementation(self, output_path: str) -> bool:
        """
        Run custom HTML cleanup on EPUB files.
        
        Args:
            output_path: Path for output EPUB
            
        Returns:
            True if successful
        """
        try:
            self._unpack_epub()
            
            # Find all spine XHTML files and clean them
            spine_files = self._find_spine_files()
            
            for xhtml_path in spine_files:
                self._clean_file(xhtml_path)
            
            # Repack and save
            return self._repack_and_save(output_path)
        
        except Exception as e:
            self.report.validation_errors.append(f"Custom cleanup failed: {str(e)}")
            return False

    def _find_spine_files(self) -> list[Path]:
        """Find all XHTML/HTML spine files in unpacked EPUB."""
        spine_files = []
        
        # Read OPF to get spine
        opf_files = list(self.temp_dir.glob("**/*.opf"))
        if not opf_files:
            return spine_files
        
        opf_path = opf_files[0]
        opf_content = opf_path.read_bytes()
        opf_soup = BeautifulSoup(opf_content, "lxml-xml")
        
        spine = opf_soup.find("spine")
        manifest = opf_soup.find("manifest")
        
        if spine and manifest:
            spine_items = spine.find_all("itemref")
            manifest_dict = {item.get("id"): item for item in manifest.find_all("item")}
            
            for itemref in spine_items:
                idref = itemref.get("idref")
                if idref and idref in manifest_dict:
                    item = manifest_dict[idref]
                    href = item.get("href", "")
                    media_type = item.get("media-type", "")
                    
                    # Only process HTML/XHTML files
                    if "html" in media_type or href.endswith((".html", ".xhtml")):
                        file_path = opf_path.parent / href
                        if file_path.exists():
                            spine_files.append(file_path)
        
        return spine_files

    def _clean_file(self, file_path: Path) -> None:
        """
        Clean a single XHTML file.
        
        Tasks:
        - Strip Gutenberg boilerplate
        - Remove Calibre noise
        - Normalize encoding
        - Convert entities
        - Normalize whitespace
        - Convert <br><br> to <p> tags
        """
        content = file_path.read_bytes()
        
        # 1. Normalize encoding
        content = self._normalize_encoding(content)
        text = content.decode("utf-8", errors="replace")
        
        # 2. Strip Gutenberg boilerplate
        text = self._strip_gutenberg_boilerplate(text)
        
        # 3. Parse HTML
        parser = select_parser(file_path.name)
        soup = BeautifulSoup(text, parser)
        
        # 4. Remove Calibre noise
        self._remove_calibre_noise(soup)
        
        # 5. Remove empty tags
        self._remove_empty_tags(soup)
        
        # 6. Convert br tags to paragraphs
        self._convert_br_to_paragraphs(soup)
        
        # 7. Normalize whitespace
        self._normalize_whitespace(soup)
        
        # 8. Convert entities to Unicode (BeautifulSoup does this automatically)
        
        # Write back
        output = soup.encode("utf-8", formatter="minimal")
        file_path.write_bytes(output)

    @staticmethod
    def _normalize_encoding(content: bytes) -> bytes:
        """
        Detect encoding and convert to UTF-8.
        Strip UTF-8 BOM if present.
        """
        # Strip UTF-8 BOM
        if content.startswith(b"\xef\xbb\xbf"):
            content = content[3:]
        
        # Detect encoding
        detection = detect(content)
        detected_encoding = detection.get("encoding", "utf-8")
        
        if detected_encoding and detected_encoding.lower() != "utf-8":
            try:
                text = content.decode(detected_encoding, errors="replace")
                content = text.encode("utf-8")
            except Exception:
                pass  # Keep original encoding
        
        return content

    @staticmethod
    def _strip_gutenberg_boilerplate(text: str) -> str:
        """
        Remove Project Gutenberg header and footer.
        
        Header: everything before `*** START OF THE PROJECT GUTENBERG EBOOK ***`
        Footer: everything after `*** END OF THE PROJECT GUTENBERG EBOOK ***`
        """
        start_marker = "*** START OF THE PROJECT GUTENBERG EBOOK"
        end_marker = "*** END OF THE PROJECT GUTENBERG EBOOK"
        
        start_idx = text.find(start_marker)
        end_idx = text.find(end_marker)
        
        if start_idx != -1:
            # Keep content after start marker
            start_idx = text.find("\n", start_idx)
            if start_idx != -1:
                text = text[start_idx + 1:]
        
        if end_idx != -1:
            # Keep content before end marker
            text = text[:end_idx]
        
        return text

    @staticmethod
    def _remove_calibre_noise(soup: BeautifulSoup) -> None:
        r"""
        Remove Calibre-generated noise:
        - Classes matching r"calibre\d+"
        - Inline styles that are just spacing (move to CSS later)
        """
        calibre_class_pattern = re.compile(r"calibre\d+", re.IGNORECASE)
        
        for tag in soup.find_all(True):
            # Remove calibre classes
            if tag.get("class"):
                classes = [c for c in tag.get("class", [])
                          if not calibre_class_pattern.match(c)]
                if classes:
                    tag["class"] = classes
                else:
                    del tag["class"]
            
            # Track inline styles for later (Phase 6), but don't remove yet
            # This allows Phase 2 to still work if needed
            if tag.get("style"):
                # Keep it for now - Phase 6 will handle CSS
                pass

    @staticmethod
    def _remove_empty_tags(soup: BeautifulSoup) -> None:
        """
        Remove empty div and p tags used as spacers.
        Keep only if they contain significant content or have meaningful attributes.
        """
        for tag in soup.find_all(["div", "p"]):
            # Check if truly empty or just whitespace
            text = tag.get_text(strip=True)
            
            # Remove if empty and no meaningful attributes
            if not text:
                meaningful_attrs = {k: v for k, v in tag.attrs.items()
                                   if k not in ["class", "style"] and v}
                if not meaningful_attrs:
                    tag.decompose()

    @staticmethod
    def _convert_br_to_paragraphs(soup: BeautifulSoup) -> None:
        """
        Convert <br><br> and similar patterns to proper <p> tags.
        """
        # Find patterns of multiple br tags
        for br in soup.find_all("br"):
            # Check if followed by another br
            next_sibling = br.next_sibling
            while next_sibling and isinstance(next_sibling, str) and next_sibling.strip() == "":
                next_sibling = next_sibling.next_sibling
            
            if next_sibling and getattr(next_sibling, "name", None) == "br":
                # This is a double break - potential paragraph separator
                # Mark for processing
                br["_processing"] = "double_break"

    @staticmethod
    def _normalize_whitespace(soup: BeautifulSoup) -> None:
        """
        Normalize whitespace:
        - Collapse multiple spaces to single space
        - Remove non-breaking spaces used for indentation (\u00a0)
        - Trim whitespace at start/end of tags
        """
        for string in soup.stripped_strings:
            pass  # BeautifulSoup handles this, but we can add custom logic
        
        # Remove non-breaking spaces that are visual indentation
        for tag in soup.find_all(True):
            if tag.string and isinstance(tag.string, str):
                # Collapse multiple spaces
                text = re.sub(r" +", " ", tag.string)
                # Remove leading non-breaking spaces (visual indentation)
                text = re.sub(r"^[\u00a0 ]+", "", text)
                if text != tag.string:
                    tag.string = text

    def repack_epub(self, output_path: str) -> bool:
        """Repack cleaned EPUB from temp directory to output file."""
        try:
            if self.temp_dir is None or not self.temp_dir.exists():
                return False
            
            # Add mimetype file first (uncompressed)
            from ..core.epub_utils import EPUBRepackager
            EPUBRepackager.repack_from_temp_dir(self.temp_dir, output_path)
            
            return True
        except Exception as e:
            self.report.validation_errors.append(f"Repack failed: {str(e)}")
            return False

    def cleanup(self) -> None:
        """Clean up temporary directory."""
        super().cleanup()


def run_phase1(input_epub: str, output_epub: str, report: PipelineReport) -> bool:
    """
    Run Phase 1: HTML Cleanup.
    
    Args:
        input_epub: Path to input EPUB
        output_epub: Path to output EPUB
        report: Pipeline report to update
    
    Returns:
        True if successful, False otherwise
    """
    try:
        cleaner = Phase1Cleaner(input_epub, report)
        
        # Execute with SE tool fallback
        success = cleaner.execute(se_tool_name="clean", output_path=output_epub)
        
        if success:
            report.phases_run.append("1")
            report.warnings.append(f"Phase 1 complete: HTML cleanup finished")
        
        return success
    
    except Exception as e:
        report.validation_errors.append(f"Phase 1 failed: {str(e)}")
        return False
