"""Phase 4 — TOC Rebuild (NCX and nav.xhtml generation)."""

import re
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from ..core import EPUBPhaseBase, NavNode, PipelineReport, TocEntry, build_zip_key, safe_read, select_parser


class Phase4TOCBuilder(EPUBPhaseBase):
    """TOC rebuild using SE tool or custom NCX/nav.xhtml generation."""

    def __init__(self, epub_path: str, report: PipelineReport, keep_toc_format: bool = False):
        """
        Initialize Phase 4 TOC builder.
        
        Args:
            epub_path: Path to the EPUB file
            report: PipelineReport instance
            keep_toc_format: If True, preserve original TOC format (NCX OR nav, not both)
        """
        super().__init__(epub_path, report)
        self.keep_toc_format = keep_toc_format
        self.epub_uid = ""
        self.epub_title = ""
        self.toc_entries: list[TocEntry] = []
        self.spine_items: dict[str, dict] = {}

    @property
    def se_tool_timeout(self) -> int:
        """SE build-toc can take a while."""
        return 120

    def _run_custom_implementation(self, output_path: str) -> bool:
        """
        Run custom TOC generation (NCX + nav.xhtml).
        
        Args:
            output_path: Path for output EPUB
            
        Returns:
            True if successful
        """
        try:
            self._unpack_epub()
            self._parse_opf()
            
            # Scan spine files for headings
            self._extract_toc_entries()
            
            # Track which formats were generated
            generated_ncx = False
            generated_nav = False
            
            # Generate TOC files based on format preference
            if self.keep_toc_format:
                # Preserve original format
                toc_format = self.report.original_toc_format
                
                if toc_format in ("ncx", "both"):
                    self._generate_ncx()
                    generated_ncx = True
                
                if toc_format in ("nav", "both"):
                    self._generate_nav_xhtml()
                    generated_nav = True
                
                if toc_format == "none":
                    # No original TOC, generate both
                    self._generate_ncx()
                    self._generate_nav_xhtml()
                    generated_ncx = True
                    generated_nav = True
                    self.report.warnings.append("Original TOC format unknown, generated both NCX and nav.xhtml")
            else:
                # Generate both formats (default behavior)
                self._generate_ncx()
                self._generate_nav_xhtml()
                generated_ncx = True
                generated_nav = True
            
            # Update manifest with generated TOC entries
            if generated_nav:
                self._update_manifest_for_nav_xhtml()
            
            # Write updated OPF back to disk
            self._write_opf()
            
            # Update report
            self.report.rebuilt_toc_entries = len(self.toc_entries)
            
            # Repack and save
            return self._repack_and_save(output_path)
        
        except Exception as e:
            self.report.validation_errors.append(f"Custom TOC generation failed: {str(e)}")
            return False

    def run_custom_generation(self) -> bool:
        """
        Run custom TOC generation (NCX + nav.xhtml).
        
        Returns:
            True if successful
        """
        try:
            if self.temp_dir is None:
                self.temp_dir = Path(tempfile.mkdtemp(prefix="epub_"))
                
                # Unpack EPUB
                with ZipFile(self.epub_path, "r") as zf:
                    zf.extractall(self.temp_dir)
            
            # Parse OPF and extract metadata
            self._parse_opf()
            
            # Scan spine files for headings
            self._extract_toc_entries()
            
            # Track which formats were generated
            generated_ncx = False
            generated_nav = False
            
            # Generate TOC files based on format preference
            if self.keep_toc_format:
                # Preserve original format
                toc_format = self.report.original_toc_format
                
                if toc_format in ("ncx", "both"):
                    self._generate_ncx()
                    generated_ncx = True
                
                if toc_format in ("nav", "both"):
                    self._generate_nav_xhtml()
                    generated_nav = True
                
                if toc_format == "none":
                    # No original TOC, generate both
                    self._generate_ncx()
                    self._generate_nav_xhtml()
                    generated_ncx = True
                    generated_nav = True
                    self.report.warnings.append("Original TOC format unknown, generated both NCX and nav.xhtml")
            else:
                # Generate both formats (default behavior)
                self._generate_ncx()
                self._generate_nav_xhtml()
                generated_ncx = True
                generated_nav = True
            
            # Update manifest with generated TOC entries
            if generated_nav:
                self._update_manifest_for_nav_xhtml()
            
            # Write updated OPF back to disk
            self._write_opf()
            
            # Update report
            self.report.rebuilt_toc_entries = len(self.toc_entries)
            
            return True
        
        except Exception as e:
            self.report.validation_errors.append(f"Custom TOC generation failed: {str(e)}")
            return False

    def _parse_opf(self) -> None:
        """Parse OPF to extract metadata and spine."""
        try:
            opf_files = list(self.temp_dir.glob("**/*.opf"))
            if not opf_files:
                raise ValueError("No OPF file found")
            
            self.opf_path = opf_files[0]
            self.opf_base = str(self.opf_path.parent.relative_to(self.temp_dir))
            
            with open(self.opf_path, "r", encoding="utf-8", errors="replace") as f:
                opf_content = f.read()
            
            self.opf_soup = BeautifulSoup(opf_content, "lxml-xml")
            
            # Extract UID
            package = self.opf_soup.find("package")
            if package:
                self.epub_uid = package.get("unique-identifier", "")
                if not self.epub_uid:
                    # Try to find the unique-identifier
                    uid_elem = self.opf_soup.find("dc:identifier", id=True)
                    if uid_elem:
                        self.epub_uid = uid_elem.get_text(strip=True)
            
            # Extract title
            title_elem = self.opf_soup.find("dc:title")
            if title_elem:
                self.epub_title = title_elem.get_text(strip=True)
            
            if not self.epub_uid:
                self.epub_uid = "unknown-uid"
            if not self.epub_title:
                self.epub_title = "Table of Contents"
        
        except Exception as e:
            self.report.warnings.append(f"Failed to parse OPF metadata: {str(e)}")

    def _extract_toc_entries(self) -> None:
        """Extract TOC entries from spine files."""
        try:
            # Use cached soup from _parse_opf
            spine = self.opf_soup.find("spine")
            
            if not spine:
                return
            
            play_order = 1
            
            for itemref in spine.find_all("itemref"):
                item_id = itemref.get("idref", "")
                
                # Find corresponding manifest item
                item = self.opf_soup.find("item", id=item_id)
                if not item:
                    continue
                
                href = item.get("href", "")
                if not href:
                    continue
                
                # Extract headings from this file
                headings = self._extract_headings_from_file(href)
                
                # Add to TOC entries
                for heading in headings:
                    entry = TocEntry(
                        title=heading["text"],
                        href=f"{href}#{heading['anchor']}" if heading.get("anchor") else href,
                        file_part=href.split("#")[0],
                        anchor=heading.get("anchor"),
                        level=heading["level"],
                        source="toc_rebuild",
                        confidence=0.95
                    )
                    self.toc_entries.append(entry)
                    play_order += 1
        
        except Exception as e:
            self.report.warnings.append(f"Failed to extract TOC entries: {str(e)}")

    def _extract_headings_from_file(self, href: str) -> list[dict]:
        """
        Extract headings from a spine file.
        
        Args:
            href: Relative href from OPF
            
        Returns:
            List of heading dictionaries with text, anchor, level
        """
        try:
            zip_key = build_zip_key(self.opf_base, href)
            content_bytes = safe_read(ZipFile(self.epub_path), zip_key)
            
            if not content_bytes:
                # Try from temp directory
                file_path = self.temp_dir / zip_key
                if not file_path.exists():
                    return []
                with open(file_path, "rb") as f:
                    content_bytes = f.read()
            
            content = content_bytes.decode("utf-8", errors="replace")
            parser = select_parser(href.split(".")[-1])
            soup = BeautifulSoup(content, parser)
            
            headings = []
            
            # Extract h1-h6 tags
            for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
                # Extract clean text without footnotes
                text = self._extract_clean_heading_text(tag)
                if not text:
                    continue
                
                level = int(tag.name[1])
                anchor = tag.get("id")
                
                # If no anchor, use first part of text
                if not anchor:
                    anchor = re.sub(r"[^\w\-]", "", text.lower().replace(" ", "-"))[:50]
                
                headings.append({
                    "text": text,
                    "anchor": anchor,
                    "level": level,
                    "file": href
                })
            
            return headings
        
        except Exception as e:
            self.report.warnings.append(f"Failed to extract headings from {href}: {str(e)}")
            return []
    
    def _extract_clean_heading_text(self, tag: "Tag") -> str:
        """
        Extract heading text while removing footnote references.
        
        Args:
            tag: BeautifulSoup tag to extract text from
            
        Returns:
            Clean text without footnote superscripts
        """
        try:
            # Clone the tag to avoid modifying original
            from bs4 import BeautifulSoup as BS
            tag_copy = BS(str(tag), 'html.parser').contents[0]
            
            # Remove footnote anchors (typically have href="#footnote-*" or href="footnote*.xhtml")
            for link in tag_copy.find_all('a'):
                href = link.get('href', '')
                if 'footnote' in href.lower() or '#fn' in href.lower():
                    link.decompose()
            
            # Extract clean text
            return tag_copy.get_text(separator=" ", strip=True)
        except Exception:
            # Fallback to direct extraction if cloning fails
            return tag.get_text(separator=" ", strip=True)

    def _generate_ncx(self) -> None:
        """Generate NCX file (EPUB2 + EPUB3 compatible)."""
        try:
            # Create root element
            ncx = ET.Element("ncx")
            ncx.set("xmlns", "http://www.daisy.org/z3986/2005/ncx/")
            ncx.set("version", "2005-1")
            
            # Create head section
            head = ET.SubElement(ncx, "head")
            
            # Add metadata
            uid_meta = ET.SubElement(head, "meta")
            uid_meta.set("name", "dtb:uid")
            uid_meta.set("content", self.epub_uid)
            
            depth_meta = ET.SubElement(head, "meta")
            depth_meta.set("name", "dtb:depth")
            depth_meta.set("content", str(self._calculate_depth()))
            
            page_count_meta = ET.SubElement(head, "meta")
            page_count_meta.set("name", "dtb:totalPageCount")
            page_count_meta.set("content", "0")
            
            max_page_meta = ET.SubElement(head, "meta")
            max_page_meta.set("name", "dtb:maxPageNumber")
            max_page_meta.set("content", "0")
            
            # Create docTitle
            doc_title = ET.SubElement(ncx, "docTitle")
            doc_title_text = ET.SubElement(doc_title, "text")
            doc_title_text.text = self.epub_title
            
            # Create navMap
            nav_map = ET.SubElement(ncx, "navMap")
            
            # Build navigation points
            play_order = 1
            for entry in self.toc_entries:
                play_order = self._add_nav_point(nav_map, entry, play_order)
            
            # Write NCX file
            ncx_path = self.temp_dir / self.opf_base / "toc.ncx"
            ncx_path.parent.mkdir(parents=True, exist_ok=True)
            
            tree = ET.ElementTree(ncx)
            ET.indent(tree, space="  ")
            tree.write(
                str(ncx_path),
                encoding="utf-8",
                xml_declaration=True
            )
            
            self.report.warnings.append(f"Generated NCX at {ncx_path.relative_to(self.temp_dir)}")
        
        except Exception as e:
            self.report.validation_errors.append(f"Failed to generate NCX: {str(e)}")

    def _add_nav_point(self, parent: ET.Element, entry: TocEntry, play_order: int) -> int:
        """
        Add a navPoint element to NCX.
        
        Args:
            parent: Parent XML element
            entry: TOC entry
            play_order: Current play order
            
        Returns:
            Updated play order
        """
        nav_point = ET.SubElement(parent, "navPoint")
        nav_point.set("id", f"navPoint-{play_order}")
        nav_point.set("playOrder", str(play_order))
        
        # Add navLabel
        nav_label = ET.SubElement(nav_point, "navLabel")
        nav_label_text = ET.SubElement(nav_label, "text")
        nav_label_text.text = entry.title
        
        # Add content src
        content = ET.SubElement(nav_point, "content")
        content.set("src", entry.href)
        
        play_order += 1
        
        # Add children recursively
        for child in entry.children:
            play_order = self._add_nav_point(nav_point, child, play_order)
        
        return play_order

    def _generate_nav_xhtml(self) -> None:
        """Generate nav.xhtml file (EPUB3) with proper nested hierarchy."""
        try:
            # Build tree from all TOC entries (includes all levels h1-h6)
            nav_tree = self._build_nav_tree(self.toc_entries)
            
            # Emit nested HTML from tree
            nav_content = self._emit_nav_html(nav_tree)
            
            # Wrap in nav structure
            html_content = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>Navigation</title>
</head>
<body>
    <nav epub:type="toc" id="toc" role="doc-toc">
        <h2>Table of Contents</h2>
""" + nav_content + """    </nav>

    <nav epub:type="landmarks" id="landmarks" role="doc-landmarks" hidden="hidden">
        <h2>Landmarks</h2>
        <ol>
            <li><a epub:type="toc" href="nav.xhtml#toc">Table of Contents</a></li>
            <li><a epub:type="bodymatter" href="Text/chapter-1.xhtml">Begin Reading</a></li>
        </ol>
    </nav>
</body>
</html>
"""
            
            # Write nav.xhtml file
            nav_dir = self.temp_dir / self.opf_base
            nav_dir.mkdir(parents=True, exist_ok=True)
            nav_path = nav_dir / "nav.xhtml"
            
            with open(nav_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            self.report.warnings.append(f"Generated hierarchical nav.xhtml at {nav_path.relative_to(self.temp_dir)}")
        
        except Exception as e:
            self.report.validation_errors.append(f"Failed to generate nav.xhtml: {str(e)}")

    def _build_nav_tree(self, entries: list[TocEntry]) -> NavNode:
        """
        Build tree structure from flat TOC entries using stack-based algorithm.
        
        Args:
            entries: Flat list of TOC entries (with level information)
            
        Returns:
            Root NavNode with all entries organized as a tree
        """
        # Create virtual root (level 0)
        root = NavNode(level=0, entry=None)
        stack = [root]
        
        for entry in entries:
            # Create new node for this entry
            node = NavNode(level=entry.level, entry=entry)
            
            # Pop stack until we find the correct parent
            # (current parent must have level < new node level)
            while len(stack) > 1 and stack[-1].level >= node.level:
                stack.pop()
            
            # Add as child of current parent
            stack[-1].add_child(node)
            # Push onto stack so it becomes parent for future entries
            stack.append(node)
        
        return root

    def _emit_nav_html(self, node: NavNode, depth: int = 0) -> str:
        """
        Recursively emit nested <ol> HTML from tree structure.
        
        Args:
            node: NavNode (tree root or subtree)
            depth: Current nesting depth (for indentation)
            
        Returns:
            HTML string with nested <ol> and <li> elements
        """
        # Leaf nodes have no output
        if not node.children:
            return ""
        
        # Indentation: adjust based on depth
        indent = "        " if depth == 0 else "            " * depth
        html = indent + "<ol>\n"
        
        # Process each child
        for child in node.children:
            child_indent = indent + "  "
            html += child_indent + f'<li><a href="{child.entry.href}">{child.entry.title}</a>'
            
            # Recursively emit nested children
            nested = self._emit_nav_html(child, depth + 1)
            if nested:
                html += "\n" + nested + child_indent
            
            html += "</li>\n"
        
        html += indent + "</ol>\n"
        return html



    def _calculate_depth(self) -> int:
        """Calculate maximum depth of TOC hierarchy."""
        if not self.toc_entries:
            return 1
        
        max_level = 1
        for entry in self.toc_entries:
            max_level = max(max_level, entry.level)
        
        return max(2, max_level)  # Minimum 2 for compatibility

    def _update_manifest_for_nav_xhtml(self) -> None:
        """
        Add nav.xhtml entry to OPF manifest with nav property.
        
        EPUB3 requires nav.xhtml to be registered with:
        - media-type: application/xhtml+xml
        - properties: nav
        """
        try:
            if not self.opf_soup:
                return
            
            # Find or create manifest element
            manifest = self.opf_soup.find("manifest")
            if not manifest:
                # Create manifest if it doesn't exist (unusual case)
                package = self.opf_soup.find("package")
                if package:
                    manifest = self.opf_soup.new_tag("manifest")
                    package.insert(0, manifest)
                else:
                    return
            
            # Check if nav.xhtml already exists in manifest
            existing_nav = manifest.find("item", {"href": "nav.xhtml"})
            if existing_nav:
                # Update existing entry to ensure nav property is set
                existing_nav["properties"] = "nav"
                return
            
            # Create new item element for nav.xhtml
            nav_item = self.opf_soup.new_tag(
                "item",
                id="nav",
                href="nav.xhtml",
                attrs={
                    "media-type": "application/xhtml+xml",
                    "properties": "nav"
                }
            )
            
            # Add to manifest (usually after other items but before spine)
            manifest.append(nav_item)
            self.report.warnings.append("Added nav.xhtml to OPF manifest with nav property")
        
        except Exception as e:
            self.report.validation_errors.append(f"Failed to update manifest for nav.xhtml: {str(e)}")

    def _write_opf(self) -> None:
        """
        Write updated OPF back to disk.
        
        Serializes the modified self.opf_soup back to the OPF file.
        """
        try:
            if not self.opf_soup or not self.opf_path:
                return
            
            # Serialize soup back to string
            opf_content = str(self.opf_soup.prettify())
            
            # Write to file
            with open(self.opf_path, "w", encoding="utf-8") as f:
                f.write(opf_content)
            
            self.report.warnings.append(f"Updated OPF manifest at {self.opf_path.relative_to(self.temp_dir)}")
        
        except Exception as e:
            self.report.validation_errors.append(f"Failed to write updated OPF: {str(e)}")

    def repack_epub(self, output_path: str) -> None:
        """
        Repack modified EPUB from temp directory.
        
        Args:
            output_path: Path where output EPUB should be written
        """
        self._repack_and_save(output_path)

    def cleanup(self) -> None:
        """Clean up temporary directory."""
        super().cleanup()


def run_phase4(
    input_epub: str,
    output_epub: str,
    report: PipelineReport,
    keep_toc_format: bool = False
) -> bool:
    """
    Run Phase 4: TOC Rebuild (NCX and nav.xhtml generation).
    
    Args:
        input_epub: Path to input EPUB
        output_epub: Path to output EPUB
        report: PipelineReport instance
        keep_toc_format: If True, preserve original TOC format
        
    Returns:
        True if successful, False otherwise
    """
    try:
        builder = Phase4TOCBuilder(input_epub, report, keep_toc_format=keep_toc_format)
        report.phases_run.append("4")
        
        # Execute with SE tool fallback
        success = builder.execute(se_tool_name="build-toc", output_path=output_epub)
        
        return success
    
    except Exception as e:
        report.validation_errors.append(f"Phase 4 failed: {str(e)}")
        return False
