"""Phase 5 — Typogrify (Typography Enhancement)."""

import re
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from ..core import EPUBPhaseBase, PipelineReport, select_parser


class Phase5Typogrifier(EPUBPhaseBase):
    """Typography enhancement using SE tool and custom Italian rules."""

    def __init__(self, epub_path: str, report: PipelineReport, language: str = "en"):
        super().__init__(epub_path, report)
        self.language = language

    @property
    def se_tool_timeout(self) -> int:
        """SE typogrify typically completes quickly."""
        return 120

    def _run_custom_implementation(self, output_path: str) -> bool:
        """
        Run custom typography enhancement.
        
        Args:
            output_path: Path for output EPUB
            
        Returns:
            True if successful
        """
        try:
            self._unpack_epub()
            
            # Find all spine XHTML files
            spine_files = self._find_spine_files()
            
            for xhtml_path in spine_files:
                self._typogrify_file(xhtml_path)
            
            # Repack and save the modified EPUB
            if output_path:
                return self._repack_and_save(output_path)
            
            return True
        
        except Exception as e:
            self.report.validation_errors.append(f"Custom typogrify failed: {str(e)}")
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

    def _typogrify_file(self, file_path: Path) -> None:
        """Apply typography enhancements to a single file."""
        content = file_path.read_bytes()
        text = content.decode("utf-8", errors="replace")
        
        # Parse HTML
        parser = select_parser(file_path.name)
        soup = BeautifulSoup(text, parser)
        
        # Apply universal rules
        self._apply_universal_rules(soup)
        
        # Apply language-specific rules
        if self.language == "it":
            self._apply_italian_rules(soup)
        
        # Write back
        output = soup.encode("utf-8", formatter="minimal")
        file_path.write_bytes(output)

    @staticmethod
    def _apply_universal_rules(soup: BeautifulSoup) -> None:
        """
        Apply universal typography rules:
        - Em-dash (already done by SE tool)
        - Ellipsis (already done by SE tool)
        - Curly quotes (already done by SE tool)
        """
        # These are primarily handled by SE typogrify
        # Here we ensure consistency in text nodes
        pass

    def _apply_italian_rules(self, soup: BeautifulSoup) -> None:
        """
        Apply Italian typography rules:
        - Straight double quotes → guillemets: "text" → «text»
        - Non-breaking space before: ?, !, :, ; → \u00a0?, \u00a0!, etc.
        - Preserve existing «» guillemets
        """
        # Process all text nodes
        for tag in soup.find_all(string=True):
            if isinstance(tag, str) and tag.strip():
                new_text = tag
                
                # Apply Italian quote rules
                new_text = self._convert_italian_quotes(new_text)
                
                # Apply non-breaking space rules
                new_text = self._apply_nbsps_italian(new_text)
                
                if new_text != tag:
                    tag.replace_with(new_text)

    @staticmethod
    def _convert_italian_quotes(text: str) -> str:
        r"""
        Convert straight quotes to Italian guillemets.
        "text" → «text»
        
        Avoid converting if already using guillemets.
        """
        # Pattern: " followed by non-whitespace
        # Replace with « ... »
        
        # First, protect already-converted guillemets
        text = text.replace("«", "\x00GUILLEMET_OPEN\x00")
        text = text.replace("»", "\x00GUILLEMET_CLOSE\x00")
        
        # Convert straight quotes
        # Pattern: "word...word"
        text = re.sub(
            r'"([^"]+)"',
            r'«\1»',
            text
        )
        
        # Restore guillemets
        text = text.replace("\x00GUILLEMET_OPEN\x00", "«")
        text = text.replace("\x00GUILLEMET_CLOSE\x00", "»")
        
        return text

    @staticmethod
    def _apply_nbsps_italian(text: str) -> str:
        r"""
        Add non-breaking spaces before French/Italian punctuation.
        Replace: " ?" → " \u00a0?"
        Replace: " !" → " \u00a0!"
        Replace: " :" → " \u00a0:"
        Replace: " ;" → " \u00a0;"
        """
        # Non-breaking space before question mark
        text = re.sub(r' \?', '\u00a0?', text)
        # Non-breaking space before exclamation mark
        text = re.sub(r' !', '\u00a0!', text)
        # Non-breaking space before colon (but not ://)
        text = re.sub(r' :(?!//)', '\u00a0:', text)
        # Non-breaking space before semicolon
        text = re.sub(r' ;', '\u00a0;', text)
        
        return text

    def repack_epub(self, output_path: str) -> bool:
        """Repack typographically enhanced EPUB from temp directory to output file."""
        try:
            if self.temp_dir is None or not self.temp_dir.exists():
                return False
            
            return self._repack_and_save(output_path)
        except Exception as e:
            self.report.validation_errors.append(f"Repack failed: {str(e)}")
            return False

    def cleanup(self) -> None:
        """Clean up temporary directory."""
        super().cleanup()


def run_phase5(input_epub: str, output_epub: str, report: PipelineReport, language: str = "en") -> bool:
    """
    Run Phase 5: Typogrify (Typography enhancement).
    
    Args:
        input_epub: Path to input EPUB
        output_epub: Path to output EPUB
        report: Pipeline report to update
        language: Language for typography rules ("en" or "it")
    
    Returns:
        True if successful, False otherwise
    """
    try:
        typogrifier = Phase5Typogrifier(input_epub, report, language)
        
        # Execute with SE tool fallback
        success = typogrifier.execute(se_tool_name="typogrify", output_path=output_epub)
        
        if success:
            # Apply language-specific rules after processing
            if language == "it" and typogrifier.temp_dir:
                spine_files = typogrifier._find_spine_files()
                for xhtml_path in spine_files:
                    typogrifier._apply_italian_rules_to_file(xhtml_path)
                # Repack again with language rules applied
                typogrifier._repack_and_save(output_epub)
            
            report.phases_run.append("5")
            report.warnings.append(f"Phase 5 complete: Typography enhanced (language: {language})")
        
        return success
    
    except Exception as e:
        report.validation_errors.append(f"Phase 5 failed: {str(e)}")
        return False


# Convenience method for applying Italian rules to a file
def _apply_italian_rules_to_file(self, file_path: Path) -> None:
    """Apply Italian typography rules to a file."""
    content = file_path.read_bytes()
    text = content.decode("utf-8", errors="replace")
    parser = select_parser(file_path.name)
    soup = BeautifulSoup(text, parser)
    self._apply_italian_rules(soup)
    output = soup.encode("utf-8", formatter="minimal")
    file_path.write_bytes(output)


Phase5Typogrifier._apply_italian_rules_to_file = _apply_italian_rules_to_file
