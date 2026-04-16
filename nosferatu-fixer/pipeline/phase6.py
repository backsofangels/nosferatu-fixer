"""Phase 6 — CSS Rewrite (consolidation and Standard Ebooks standardization)."""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from ..core import PipelineReport, build_zip_key, safe_read, select_parser


class Phase6CSSRewriter:
    """CSS consolidation and standardization to Standard Ebooks style."""

    # Standard Ebooks CSS variables and conventions
    SE_CSS_TEMPLATE = """/* Standard Ebooks CSS */
@supports (background: var(--color-accent)) {
    :root {
        --color-accent: #b3811e;
        --color-link: #0096ff;
        --color-link-underline: #7fb3ff;
    }
}

/* Core typography */
html {
    font-family: "Libertinus Serif", "Liberation Serif", "Noto Serif", serif;
    font-size: 1em;
    line-height: 1.5;
    -webkit-hyphenate-character: "​";
    hyphenate-character: "​";
}

body {
    margin: 0;
    background-color: #fafafa;
}

/* Block-level elements */
p {
    margin: 0;
    text-align: justify;
}

/* Headings */
h1, h2, h3, h4, h5, h6 {
    margin: 1em 0 0.5em 0;
    font-weight: bold;
    line-height: 1.25;
}

h1 { font-size: 1.5em; }
h2 { font-size: 1.3em; }
h3 { font-size: 1.1em; }
h4, h5, h6 { font-size: 1em; }

/* Inline styling */
strong, b {
    font-weight: bold;
}

em, i {
    font-style: italic;
}

/* Lists */
ol, ul {
    margin: 1em 0;
    padding-left: 2em;
}

li {
    margin: 0.5em 0;
}

/* Links */
a {
    color: inherit;
    text-decoration: underline;
}

/* Blockquotes */
blockquote {
    margin: 1em 0 1em 1em;
    padding-left: 1em;
    border-left: 3px solid;
}

/* Code blocks and preformatted text */
code, kbd, pre, samp {
    font-family: "Libertinus Mono", "Liberation Mono", "DejaVu Sans Mono", monospace;
    font-size: 0.875em;
}

pre {
    margin: 1em 0;
    padding: 1em;
    overflow-x: auto;
}

/* Semantic/accessibility classes */
.elision {
    font-style: italic;
}

.no-hyphens {
    -webkit-hyphens: none;
    hyphens: none;
}

.roman {
    font-variant: small-caps;
}

.small-caps {
    font-variant: small-caps;
}

.full-page {
    page-break-before: always;
}

/* EPUB-specific */
@media (prefers-color-scheme: dark) {
    html {
        background-color: #000;
        color: #e0e0e0;
    }
    
    a {
        color: #0096ff;
    }
}

/* Print styles */
@media print {
    body {
        background-color: white;
    }
}
"""

    def __init__(self, epub_path: str, output_path: str, report: PipelineReport, minify_css: bool = True):
        """
        Initialize Phase 6 CSS rewriter.
        
        Args:
            epub_path: Path to the input EPUB file
            output_path: Path to the output EPUB file
            report: PipelineReport instance
            minify_css: Whether to minify CSS output
        """
        self.epub_path = epub_path
        self.output_path = output_path
        self.report = report
        self.temp_dir: Optional[Path] = None
        self.opf_base = ""
        self.opf_path: Optional[Path] = None
        self.collected_css: dict[str, list[str]] = {}  # group -> rules
        self.minify_css = minify_css

    def execute(self) -> bool:
        """
        Execute Phase 6 CSS rewriting.
        
        Returns:
            True if successful
        """
        try:
            # Unpack EPUB
            self.temp_dir = Path(tempfile.mkdtemp(prefix="epub_"))
            with ZipFile(self.epub_path, "r") as zf:
                zf.extractall(self.temp_dir)
            
            # Parse OPF
            self._parse_opf()
            
            # Extract CSS from spine files and stylesheets
            self._extract_css()
            
            # Consolidate CSS into standard stylesheet
            self._consolidate_css()
            
            # Rewrite CSS in spine files
            self._rewrite_spine_css()
            
            # Repack EPUB
            return self._repack_epub()
        
        except Exception as e:
            self.report.validation_errors.append(f"Phase 6 execution failed: {str(e)}")
            return False
        
        finally:
            # Clean up temp directory
            if self.temp_dir and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _parse_opf(self) -> None:
        """Parse OPF file and extract metadata."""
        try:
            from bs4 import BeautifulSoup
            
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

    def _extract_css(self) -> None:
        """
        Extract CSS from spine files and stylesheets.
        
        Scans all spine items and linked CSS files to collect CSS rules.
        """
        try:
            from bs4 import BeautifulSoup
            
            # Parse OPF to get manifest and spine
            opf_tree = ET.parse(self.opf_path)
            opf_root = opf_tree.getroot()
            
            ns = {
                "opf": "http://www.idpf.org/2007/opf",
                "ncx": "http://www.daisy.org/z3986/2005/ncx/"
            }
            
            # Find all CSS files in manifest
            css_files = []
            for item in opf_root.findall(".//opf:item", ns):
                media_type = item.get("media-type", "")
                if media_type == "text/css":
                    css_files.append(item.get("href"))
            
            # Extract CSS from stylesheet files
            for css_file in css_files:
                css_path = self.temp_dir / self.opf_base / css_file
                if css_path.exists():
                    try:
                        with open(css_path, "r", encoding="utf-8") as f:
                            css_content = f.read()
                        
                        # Parse and collect CSS rules
                        self._parse_css_rules(css_content, "stylesheets")
                    
                    except Exception as e:
                        self.report.warnings.append(
                            f"Error reading CSS file {css_file}: {str(e)}"
                        )
            
            # Extract inline CSS from spine files
            spine_elem = opf_root.find(".//opf:spine", ns)
            if spine_elem:
                for itemref in spine_elem.findall("opf:itemref", ns):
                    item_id = itemref.get("idref")
                    manifest_items = opf_root.findall(
                        f".//opf:manifest/opf:item[@id='{item_id}']", ns
                    )
                    
                    if manifest_items:
                        item_href = manifest_items[0].get("href")
                        spine_file = self.temp_dir / self.opf_base / item_href
                        
                        if spine_file.exists():
                            try:
                                with open(spine_file, "rb") as f:
                                    content = f.read()
                                
                                # Decode content
                                try:
                                    html_content = content.decode("utf-8")
                                except UnicodeDecodeError:
                                    from chardet import detect
                                    encoding = detect(content).get("encoding", "utf-8")
                                    html_content = content.decode(encoding, errors="replace")
                                
                                # Parse and extract inline styles
                                parser = select_parser(str(spine_file))
                                soup = BeautifulSoup(html_content, parser)
                                
                                # Collect style tags
                                for style_tag in soup.find_all("style"):
                                    if style_tag.string:
                                        self._parse_css_rules(
                                            style_tag.string, f"inline:{item_href}"
                                        )
                            
                            except Exception as e:
                                self.report.warnings.append(
                                    f"Error extracting CSS from {item_href}: {str(e)}"
                                )
            
            self.report.warnings.append(
                f"Extracted CSS from {len(css_files)} stylesheet files"
            )
        
        except Exception as e:
            self.report.warnings.append(f"CSS extraction failed: {str(e)}")

    def _parse_css_rules(self, css_content: str, source: str) -> None:
        """
        Parse CSS rules from content.
        
        Args:
            css_content: CSS text content
            source: Source identifier (file path or "inline:...")
        """
        try:
            # Simple CSS rule extraction (remove comments and whitespace)
            # This is a basic implementation; a full CSS parser would be ideal
            
            # Remove comments
            css_content = re.sub(r"/\*[^*]*\*+(?:[^/*][^*]*\*+)*/", "", css_content)
            
            # Split by closing braces to find rule blocks
            rules = re.split(r"}\s*", css_content)
            
            for i, rule in enumerate(rules):
                if "{" in rule:
                    selector_part, property_part = rule.rsplit("{", 1)
                    selector = selector_part.strip()
                    properties = property_part.strip()
                    
                    if selector and properties:
                        if source not in self.collected_css:
                            self.collected_css[source] = []
                        
                        self.collected_css[source].append(
                            f"{selector} {{\n    {properties.replace(';', '; ')}\n}}"
                        )
        
        except Exception as e:
            self.report.warnings.append(f"CSS rule parsing failed: {str(e)}")

    def _consolidate_css(self) -> None:
        """
        Consolidate CSS into standard stylesheet.
        
        Creates or updates the main CSS file with Standard Ebooks conventions.
        Optionally minifies CSS to reduce file size.
        """
        try:
            # Create CSS directory if it doesn't exist
            css_dir = self.temp_dir / self.opf_base / "css"
            css_dir.mkdir(parents=True, exist_ok=True)
            
            # Write consolidated CSS file
            css_file = css_dir / "style.css"
            
            # Start with SE template
            css_content = self.SE_CSS_TEMPLATE
            css_content += "\n\n/* Custom extracted rules */\n"
            
            # Add extracted rules (deduplicated)
            seen_rules = set()
            for source, rules in self.collected_css.items():
                for rule in rules:
                    # Normalize rule for deduplication
                    normalized = rule.replace("\n", "").replace("  ", " ")
                    if normalized not in seen_rules:
                        seen_rules.add(normalized)
                        css_content += f"\n{rule}\n"
            
            # Minify if enabled
            if self.minify_css:
                css_content = self._minify_css(css_content)
            
            with open(css_file, "w", encoding="utf-8") as f:
                f.write(css_content)
            
            self.report.warnings.append(f"Created consolidated stylesheet: css/style.css")
        
        except Exception as e:
            self.report.warnings.append(f"CSS consolidation failed: {str(e)}")

    def _rewrite_spine_css(self) -> None:
        """
        Rewrite CSS references in spine files.
        
        Updates all style tags and CSS links to point to consolidated stylesheet.
        """
        try:
            from bs4 import BeautifulSoup
            
            # Parse OPF to get spine items
            opf_tree = ET.parse(self.opf_path)
            opf_root = opf_tree.getroot()
            
            ns = {"opf": "http://www.idpf.org/2007/opf"}
            
            spine_elem = opf_root.find(".//opf:spine", ns)
            if not spine_elem:
                return
            
            for itemref in spine_elem.findall("opf:itemref", ns):
                item_id = itemref.get("idref")
                manifest_items = opf_root.findall(
                    f".//opf:manifest/opf:item[@id='{item_id}']", ns
                )
                
                if manifest_items:
                    item_href = manifest_items[0].get("href")
                    spine_file = self.temp_dir / self.opf_base / item_href
                    
                    if spine_file.exists():
                        try:
                            with open(spine_file, "rb") as f:
                                content = f.read()
                            
                            # Decode
                            try:
                                html_content = content.decode("utf-8")
                            except UnicodeDecodeError:
                                from chardet import detect
                                encoding = detect(content).get("encoding", "utf-8")
                                html_content = content.decode(encoding, errors="replace")
                            
                            # Parse
                            parser = select_parser(str(spine_file))
                            soup = BeautifulSoup(html_content, parser)
                            
                            # Remove inline style tags (consolidate with stylesheet)
                            for style_tag in soup.find_all("style"):
                                style_tag.decompose()
                            
                            # Update or add CSS link to consolidated stylesheet
                            head = soup.find("head")
                            if head:
                                # Remove existing CSS links
                                for link in head.find_all("link", rel="stylesheet"):
                                    link.decompose()
                                
                                # Add link to consolidated stylesheet (relative path)
                                # Compute relative path from spine file to CSS
                                spine_depth = len(Path(item_href).parts) - 1
                                css_rel_path = "/".join(
                                    [".."] * spine_depth + ["css", "style.css"]
                                )
                                
                                new_link = soup.new_tag(
                                    "link",
                                    rel="stylesheet",
                                    type="text/css",
                                    href=css_rel_path
                                )
                                head.append(new_link)
                            
                            # Write back
                            with open(spine_file, "wb") as f:
                                if "xml" in parser.lower():
                                    # XHTML
                                    f.write(str(soup).encode("utf-8"))
                                else:
                                    # HTML
                                    f.write(str(soup).encode("utf-8"))
                        
                        except Exception as e:
                            self.report.warnings.append(
                                f"Error rewriting CSS in {item_href}: {str(e)}"
                            )
        
        except Exception as e:
            self.report.warnings.append(f"CSS rewriting in spine files failed: {str(e)}")

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

    def _minify_css(self, css_content: str) -> str:
        """
        Minify CSS to reduce file size.
        
        Args:
            css_content: Original CSS
        
        Returns:
            Minified CSS
        """
        # Remove comments
        css = re.sub(r"/\*[^*]*\*+(?:[^/*][^*]*\*+)*/", "", css_content)
        
        # Remove newlines
        css = re.sub(r"\n", "", css)
        
        # Remove unnecessary whitespace
        css = re.sub(r"\s+", " ", css)
        css = re.sub(r"\s*([{}:;,>+~])\s*", r"\1", css)
        
        # Remove trailing semicolon before closing brace
        css = re.sub(r";}", "}", css)
        
        # Remove space before opening brace
        css = re.sub(r"\s+{", "{", css)
        
        return css.strip()


def run_phase6(epub_path: str, output_path: str, report: PipelineReport, minify_css: bool = True) -> bool:
    """
    Execute Phase 6: CSS Rewriting and consolidation.
    
    Args:
        epub_path: Path to input EPUB
        output_path: Path to output EPUB
        report: PipelineReport instance
        minify_css: Whether to minify CSS output (default True)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create CSS rewriter with both input and output paths
        rewriter = Phase6CSSRewriter(epub_path, output_path, report, minify_css=minify_css)
        
        # Execute phase (now creates output_path directly)
        success = rewriter.execute()
        
        if success:
            report.phases_run.append("6")
            return True
        
        # Clean up any partial output file on failure
        try:
            if Path(output_path).exists() and Path(output_path) != Path(epub_path):
                Path(output_path).unlink()
        except Exception:
            pass
        
        return False
    
    except Exception as e:
        report.validation_errors.append(f"Phase 6 failed: {str(e)}")
        return False
