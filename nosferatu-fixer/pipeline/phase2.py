"""Phase 2 — Semantic Upgrade (6-pass heading detection)."""

import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Optional
from zipfile import ZipFile

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from ..core import EPUBPhaseBase, PipelineReport, TocEntry, build_zip_key, safe_read, select_parser


class Phase2Analyzer(EPUBPhaseBase):
    """Semantic upgrade using 6-pass heading detection."""

    # Regex for heading class heuristic
    HEADING_CLASS_PATTERN = re.compile(
        r"(chapter|heading|title|caption|cap|titolo|sezione"
        r"|section|part|parte|h[1-6]|head)", re.IGNORECASE
    )
    
    # Regex for uppercase heuristic
    CHAPTER_PATTERN = re.compile(
        r"(Capitolo|Chapter|CHAPTER|CAP\.)\s+[\dIVXLCivxlc]+", re.IGNORECASE
    )

    def __init__(self, epub_path: str, report: PipelineReport, ncx_entries: Optional[dict] = None):
        """
        Initialize Phase 2 analyzer.
        
        Args:
            epub_path: Path to the EPUB file
            report: PipelineReport instance
            ncx_entries: Dict mapping spine file -> [TocEntry] from original NCX
        """
        super().__init__(epub_path, report)
        self.ncx_entries = ncx_entries or {}
        self.spine_items: dict[str, dict] = {}
        self.detected_headings: dict[str, list[TocEntry]] = {}
        self.existing_ids: set[str] = set()

    @property
    def se_tool_timeout(self) -> int:
        """SE semanticate can take a while."""
        return 120

    def _run_custom_implementation(self, output_path: str) -> bool:
        """
        Run custom 6-pass heading detection.
        
        Args:
            output_path: Path for output EPUB
            
        Returns:
            True if successful
        """
        try:
            self._unpack_epub()
            self._parse_opf()
            
            # Scan all spine files with 6-pass detection
            spine_files = self._get_spine_files()
            
            for spine_item in spine_files:
                file_path = self._get_file_path(spine_item["href"])
                if file_path:
                    headings = self._detect_headings_in_file(
                        file_path, spine_item["href"]
                    )
                    if headings:
                        self.detected_headings[spine_item["href"]] = headings
                        # Inject semantic markup
                        self._inject_semantic_markup(file_path, headings)
            
            # Update report stats
            total_detected = sum(
                len(entries) for entries in self.detected_headings.values()
            )
            self.report.rebuilt_toc_entries = max(
                self.report.rebuilt_toc_entries, total_detected
            )
            
            # Repack and save
            return self._repack_and_save(output_path)
        
        except Exception as e:
            self.report.validation_errors.append(f"Custom analysis failed: {str(e)}")
            return False
    
    def _parse_opf(self) -> None:
        """Parse OPF file to extract spine items and manifest."""
        try:
            # Call parent to set opf_path, opf_base, opf_soup
            super()._parse_opf()
            
            if not self.opf_soup:
                return
            
            # Get all manifest items
            manifest = {}
            for item in self.opf_soup.find_all("item"):
                manifest[item.get("id", "")] = {
                    "href": item.get("href", ""),
                    "media_type": item.get("media-type", "")
                }
            
            # Get spine order
            spine = self.opf_soup.find("spine")
            if spine:
                for itemref in spine.find_all("itemref"):
                    item_id = itemref.get("idref", "")
                    if item_id in manifest:
                        self.spine_items[item_id] = manifest[item_id]
        
        except Exception as e:
            self.report.warnings.append(f"Failed to parse OPF: {str(e)}")

    def _get_spine_files(self) -> list[dict]:
        """Get spine files in order."""
        return list(self.spine_items.values())

    def _get_file_path(self, href: str) -> Optional[Path]:
        """
        Resolve spine item href to actual file path.
        
        Args:
            href: Relative href from OPF
            
        Returns:
            Absolute path to file in temp_dir, or None if not found
        """
        try:
            zip_key = build_zip_key(self.opf_base, href)
            file_path = self.temp_dir / zip_key
            
            if file_path.exists():
                return file_path
            
            # Case-insensitive fallback
            for candidate in self.temp_dir.glob("**/*"):
                if candidate.is_file() and str(candidate.relative_to(self.temp_dir)).lower() == zip_key.lower():
                    return candidate
            
            return None
        
        except Exception:
            return None

    def _detect_headings_in_file(self, file_path: Path, href: str) -> list[TocEntry]:
        """
        Run 6-pass heading detection on a single file.
        
        Passes (in order, stop at first match per file):
        1. Semantic heading tags (h1-h6) — confidence 1.0
        2. CSS class heuristic — confidence 0.85
        3. Bold-as-heading — confidence 0.7
        4. Uppercase heuristic — confidence 0.55
        5. Document <title> fallback — confidence 0.4
        6. NCX title fallback — confidence 0.3
        
        Args:
            file_path: Path to XHTML file
            href: Original href for NCX lookups
            
        Returns:
            List of TocEntry objects found
        """
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            parser = select_parser(file_path.name)
            soup = BeautifulSoup(content, parser)
            
            # PASS 1: Semantic heading tags
            headings = self._pass_semantic_tags(soup, href)
            if headings:
                self.report.detection_sources["semantic_heading"] = \
                    self.report.detection_sources.get("semantic_heading", 0) + len(headings)
                return headings
            
            # PASS 2: CSS class heuristic
            headings = self._pass_css_class(soup, href)
            if headings:
                self.report.detection_sources["css_class"] = \
                    self.report.detection_sources.get("css_class", 0) + len(headings)
                return headings
            
            # PASS 3: Bold-as-heading
            headings = self._pass_bold_heading(soup, href)
            if headings:
                self.report.detection_sources["bold_paragraph"] = \
                    self.report.detection_sources.get("bold_paragraph", 0) + len(headings)
                return headings
            
            # PASS 4: Uppercase heuristic
            headings = self._pass_uppercase_heuristic(soup, href)
            if headings:
                self.report.detection_sources["uppercase_heuristic"] = \
                    self.report.detection_sources.get("uppercase_heuristic", 0) + len(headings)
                return headings
            
            # PASS 5: Document <title> fallback
            headings = self._pass_document_title(soup, href)
            if headings:
                return headings
            
            # PASS 6: NCX title fallback
            headings = self._pass_ncx_fallback(soup, href)
            if headings:
                self.report.detection_sources["ncx_fallback"] = \
                    self.report.detection_sources.get("ncx_fallback", 0) + len(headings)
                return headings
            
            return []
        
        except Exception as e:
            self.report.warnings.append(f"Heading detection failed for {href}: {str(e)}")
            return []

    def _extract_clean_heading_text(self, tag: Tag) -> str:
        """
        Extract heading text while removing footnote references and other noise.
        
        Args:
            tag: BeautifulSoup tag to extract text from
            
        Returns:
            Clean text without footnote superscripts or references
        """
        # Clone the tag to avoid modifying original
        try:
            # Create a copy of the tag
            tag_copy = BeautifulSoup(str(tag), 'html.parser').contents[0]
            
            # Remove footnote anchors and their content
            # These typically have href="#footnote-*" or href="footnote*.xhtml#*"
            for link in tag_copy.find_all('a'):
                href = link.get('href', '')
                # Check if this is a footnote link
                if 'footnote' in href.lower() or '#fn' in href.lower():
                    # Remove the link (decompose)
                    link.decompose()
            
            # Extract text from the modified tag
            text = tag_copy.get_text(separator=" ", strip=True)
            return text
        except Exception:
            # Fallback to direct extraction if cloning fails
            return tag.get_text(separator=" ", strip=True)

    def _pass_semantic_tags(self, soup: BeautifulSoup, href: str) -> list[TocEntry]:
        """PASS 1: Find semantic <h1>-<h6> tags."""
        headings = []
        
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            # Filter out headings inside excluded tags
            if self._is_excluded_context(tag):
                continue
            
            # Filter out hidden headings
            if tag.get("aria-hidden") == "true":
                continue
            
            text = self._extract_clean_heading_text(tag)
            if not text:
                continue
            
            level = int(tag.name[1])
            anchor = self._extract_anchor(tag)
            
            headings.append(TocEntry(
                title=text,
                href=f"{href}#{anchor}" if anchor else href,
                file_part=href.split("#")[0],
                anchor=anchor,
                level=level,
                source="semantic_heading",
                confidence=1.0
            ))
        
        return headings

    def _extract_calibre_font_classes(self, soup: BeautifulSoup) -> dict[str, float]:
        """Extract Calibre CSS classes with largest font-size (likely headings).
        
        Calibre generates: .calibre1 { font-size: 1.5em; }
        We want to identify which class sizes suggest headings.
        
        Returns:
            Dict mapping class_name -> font_size_value (as float in em/px)
        """
        class_to_size = {}
        
        # Find all style tags
        for style_tag in soup.find_all("style"):
            if not style_tag.string:
                continue
            
            # Match: .calibreN { ... font-size: XXX ... }
            pattern = r'\.calibre(\d+)\s*\{[^}]*font-size\s*:\s*([^;]+)'
            matches = re.findall(pattern, style_tag.string)
            
            for class_num, size_str in matches:
                class_name = f"calibre{class_num}"
                # Extract numeric value (1.5em → 1.5, 16px → 16, etc)
                try:
                    size_value = float(re.search(r'[\d.]+', size_str).group())
                    class_to_size[class_name] = size_value
                except (AttributeError, ValueError):
                    pass
        
        return class_to_size
    
    def _pass_css_class(self, soup: BeautifulSoup, href: str) -> list[TocEntry]:
        """PASS 2: Find tags with heading-like CSS classes (semantic + Calibre).
        
        Checks:
        - Standard semantic classes (chapter, heading, title, etc)
        - Calibre classes by font-size heuristic (largest classes likely headings)
        """
        headings = []
        first_match = True
        
        # Extract Calibre class font sizes for this file
        calibre_classes = self._extract_calibre_font_classes(soup)
        
        # Identify largest Calibre class (assume that's headings/titles)
        largest_calibre_class = None
        if calibre_classes:
            largest_calibre_class = max(calibre_classes, key=lambda c: calibre_classes[c])
        
        for tag in soup.find_all(["p", "div", "span"]):
            classes = tag.get("class", [])
            if isinstance(classes, str):
                classes = [classes]
            
            class_str = " ".join(classes)
            
            # Check 1: Semantic heading classes (original logic)
            is_semantic = self.HEADING_CLASS_PATTERN.search(class_str)
            
            # Check 2: Calibre largest-font class (new logic)
            is_largest_calibre = (largest_calibre_class and 
                                 largest_calibre_class in classes)
            
            if not (is_semantic or is_largest_calibre):
                continue
            
            text = self._extract_clean_heading_text(tag)
            if not text or len(text) > 150:
                continue
            
            # Estimate level from class suffix (e.g., "heading2" → level 2)
            level = self._extract_level_from_class(class_str)
            anchor = self._extract_anchor(tag)
            
            headings.append(TocEntry(
                title=text,
                href=f"{href}#{anchor}" if anchor else href,
                file_part=href.split("#")[0],
                anchor=anchor,
                level=level,
                source="css_class",
                confidence=0.85
            ))
            
            first_match = False
        
        return headings

    def _is_mostly_bold(self, element: Tag) -> tuple[bool, float]:
        """Check if element has bold/strong content at 40%+ ratio (allows nesting).
        
        Handles cases like: <i><b>text</b></i>, <span><b>text</b></span>
        
        Returns:
            Tuple of (is_mostly_bold, ratio) where ratio is boldness percentage
        """
        text_content = element.get_text(strip=True)
        if not text_content:
            return False, 0.0
        
        # Find all bold/strong tags
        bold_tags = element.find_all(["b", "strong"])
        if not bold_tags:
            return False, 0.0
        
        # Calculate total bold text length
        bold_text_total = sum(len(tag.get_text()) for tag in bold_tags)
        bold_ratio = bold_text_total / len(text_content)
        
        # Criteria: 40%+ bold content is "mostly bold"
        return bold_ratio >= 0.4, bold_ratio
    
    def _pass_bold_heading(self, soup: BeautifulSoup, href: str) -> list[TocEntry]:
        """PASS 3: Find bold-as-heading patterns including nested formatting.
        
        Handles:
        - Simple: <p><b>text</b></p>
        - Nested: <p><i><b>text</b></i></p>
        - Wrapped: <p><span><b>text</b></span></p>
        - Top-level: <i><b>text</b></i> (outside <p>)
        
        Criteria: 40%+ bold content, <150 chars, isolated
        """
        headings = []
        
        # First pass: check regular <p> tags
        for tag in soup.find_all("p"):
            text = self._extract_clean_heading_text(tag)
            
            # Filter: must be short and contain some text
            if not text or len(text) > 150:
                continue
            
            # Check for mostly-bold content (flexible nesting)
            is_bold, ratio = self._is_mostly_bold(tag)
            if not is_bold:
                continue  # Not mostly bold
            
            anchor = self._extract_anchor(tag)
            
            # Confidence decreases with nesting depth (more markup = less certain it's a heading)
            confidence = 0.75 if ratio >= 0.8 else 0.70 if ratio >= 0.6 else 0.65
            
            headings.append(TocEntry(
                title=text,
                href=f"{href}#{anchor}" if anchor else href,
                file_part=href.split("#")[0],
                anchor=anchor,
                level=2,
                source="bold_paragraph",
                confidence=confidence
            ))
        
        # If found headings in <p>, return them
        if headings:
            return headings
        
        # Second pass: check top-level formatting (outside <p>) at document start
        # Handles: <i><b>Title</b></i> before any <p> tags
        body = soup.find("body")
        if body:
            # Look at first few direct children of body (before content)
            for idx, child in enumerate(body.children):
                # Stop after first 3 elements or if we hit a <p>
                if idx > 3 or (isinstance(child, Tag) and child.name == "p"):
                    break
                
                if not isinstance(child, Tag):
                    continue
                
                # Skip if not a container-like element
                if child.name not in ["i", "em", "b", "strong", "span", "div"]:
                    continue
                
                text = self._extract_clean_heading_text(child)
                if not text or len(text) > 150:
                    continue
                
                # Check if mostly bold
                is_bold, ratio = self._is_mostly_bold(child)
                if not is_bold and child.name not in ["b", "strong"]:
                    continue
                
                # This looks like a heading
                confidence = 0.72 if ratio >= 0.6 else 0.65
                
                headings.append(TocEntry(
                    title=text,
                    href=href,
                    file_part=href.split("#")[0],
                    anchor=None,
                    level=1,  # Top-level formatting likely title
                    source="bold_paragraph_toplevel",
                    confidence=confidence
                ))
        
        return headings

    def _is_title_case(self, text: str) -> bool:
        """Check if text is title case or title-like.
        
        Examples:
        - "The Duke And I" → True (all words capitalized, multiple words)
        - "Prologo" → True (single word, capitalized)
        - "the duke and i" → False (mostly lowercase)
        - "THIS IS ALL CAPS" → False (not title case, too uniform)
        
        Args:
            text: Text to check
            
        Returns:
            True if text appears to be title cased
        """
        if not text:
            return False
        
        words = text.split()
        if not words:
            return False
        
        # Single word: must be capitalized + not all caps
        if len(words) == 1:
            is_capitalized = words[0] and words[0][0].isupper()
            is_all_caps = words[0].isupper() and len(words[0]) > 1
            return is_capitalized and not is_all_caps
        
        # Multiple words check 1: 70%+ words are capitalized
        capitalized_count = sum(1 for w in words if w and w[0].isupper())
        capitalized_ratio = capitalized_count / len(words)
        
        if capitalized_ratio >= 0.7:
            # Multiple words, mostly capitalized: it's title-like
            # This catches "The Duke And I" and "A Short Title"
            
            # Additional check: shouldn't be ALL CAPS (that's screaming text, not a title)
            fully_uppercase_words = sum(1 for w in words if w.isupper() and len(w) > 1)
            fully_uppercase_ratio = fully_uppercase_words / len(words) if words else 0
            
            # Allow if not more than 30% all-caps words
            if fully_uppercase_ratio < 0.3:
                return True
        
        return False
    
    def _pass_uppercase_heuristic(self, soup: BeautifulSoup, href: str) -> list[TocEntry]:
        """PASS 4: First paragraph with ALL-CAPS or Title Case as heading.
        
        Detects:
        - ALL UPPERCASE text (>70% uppercase letters)
        - Title Case ("The Duke And I", "Prologo")
        """
        for tag in soup.find_all("p"):
            
            # Filter out very long candidates
            text = self._extract_clean_heading_text(tag)
            if not text or len(text) > 120:
                continue
            
            # Check 1: ALL-CAPS heuristic (original)
            alpha_chars = [c for c in text if c.isalpha()]
            if alpha_chars:
                uppercase_count = sum(1 for c in alpha_chars if c.isupper())
                uppercase_ratio = uppercase_count / len(alpha_chars)
                
                if uppercase_ratio > 0.70:
                    anchor = self._extract_anchor(tag)
                    return [TocEntry(
                        title=text,
                        href=f"{href}#{anchor}" if anchor else href,
                        file_part=href.split("#")[0],
                        anchor=anchor,
                        level=2,
                        source="uppercase_heuristic",
                        confidence=0.55
                    )]
            
            # Check 2: Title Case heuristic (new)
            if self._is_title_case(text):
                anchor = self._extract_anchor(tag)
                return [TocEntry(
                    title=text,
                    href=f"{href}#{anchor}" if anchor else href,
                    file_part=href.split("#")[0],
                    anchor=anchor,
                    level=2,
                    source="title_case_heuristic",
                    confidence=0.50  # Title case lower confidence than uppercase
                )]
        
        return []

    def _pass_document_title(self, soup: BeautifulSoup, href: str) -> list[TocEntry]:
        """PASS 5: Use document <title> tag as fallback."""
        # Extract title text
        title_tag = soup.find("title")
        if not title_tag:
            return []
        
        text = self._extract_clean_heading_text(title_tag)
        if not text:
            return []
        
        return [TocEntry(
            title=text,
            href=href,
            file_part=href.split("#")[0],
            anchor=None,
            level=2,
            source="document_title",
            confidence=0.4
        )]

    def _pass_ncx_fallback(self, soup: BeautifulSoup, href: str) -> list[TocEntry]:
        """PASS 6: Use original NCX entries for this file as fallback."""
        # Look up this file in NCX entries
        for ncx_file, ncx_headings in self.ncx_entries.items():
            if ncx_file.endswith(href) or href.endswith(ncx_file):
                headings = []
                for ncx_entry in ncx_headings:
                    heading = TocEntry(
                        title=ncx_entry.title,
                        href=href,
                        file_part=href.split("#")[0],
                        anchor=None,
                        level=2,
                        source="ncx_fallback",
                        confidence=0.3
                    )
                    headings.append(heading)
                
                if headings:
                    return headings
        
        return []

    def _is_excluded_context(self, tag: Tag) -> bool:
        """Check if tag is inside excluded container."""
        excluded_tags = ["aside", "figure", "footer", "script", "nav"]
        
        for parent in tag.parents:
            if parent.name in excluded_tags:
                return True
        
        return False

    def _extract_level_from_class(self, class_str: str) -> int:
        """Extract heading level from CSS class string."""
        match = re.search(r"h(\d)|heading(\d)|caption(\d)", class_str, re.IGNORECASE)
        
        if match:
            for group in match.groups():
                if group:
                    try:
                        level = int(group)
                        if 1 <= level <= 6:
                            return level
                    except ValueError:
                        pass
        
        return 2  # Default to h2 if unclear

    def _extract_anchor(self, tag: Tag) -> Optional[str]:
        """
        Extract anchor ID from tag.
        
        Priority:
        1. Calibre anchor (<a id="calibre_toc_N">)
        2. Direct id attribute
        3. Generate and inject slug
        
        Args:
            tag: BeautifulSoup Tag
            
        Returns:
            Anchor ID string, or None if not found
        """
        # Method 1: Calibre anchor
        calibre_anchor = tag.find("a", id=re.compile(r"calibre_toc_\d+"))
        if calibre_anchor:
            anchor_id = calibre_anchor.get("id")
            self.existing_ids.add(anchor_id)
            return anchor_id
        
        # Method 2: Direct id on tag
        if tag.get("id"):
            anchor_id = tag.get("id")
            self.existing_ids.add(anchor_id)
            return anchor_id
        
        # Method 3: Generate slug and inject
        text = self._extract_clean_heading_text(tag)
        anchor = self._slugify(text, self.existing_ids)
        tag["id"] = anchor
        self.existing_ids.add(anchor)
        
        return anchor

    def _slugify(self, text: str, existing_ids: set[str]) -> str:
        """
        Convert text to URL-safe slug.
        
        Args:
            text: Text to slugify
            existing_ids: Set of already-used IDs (to avoid collisions)
            
        Returns:
            Unique slug
        """
        # Normalize Unicode
        slug = unicodedata.normalize("NFKD", text)
        slug = "".join(c for c in slug if not unicodedata.combining(c))
        
        # Convert to lowercase, remove non-alphanumeric
        slug = re.sub(r"[^\w\s-]", "", slug.lower())
        slug = re.sub(r"[-\s]+", "-", slug).strip("-")
        
        # Avoid collisions
        base_slug = slug or "heading"
        slug = base_slug
        counter = 1
        while slug in existing_ids:
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        return slug

    def _inject_semantic_markup(self, file_path: Path, headings: list[TocEntry]) -> None:
        """
        Inject semantic structure with epub:type attributes.
        
        For headings from pass 5 (title) or pass 6 (NCX), create h1 at document start.
        For headings found in body, convert existing elements to semantic tags.
        
        Args:
            file_path: Path to XHTML file
            headings: List of detected headings
        """
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            parser = select_parser(file_path.name)
            soup = BeautifulSoup(content, parser)
            
            # For each heading, either convert existing element or create new h-tag
            for heading in headings:
                heading_tag = None
                
                # Only try to find existing elements for headings detected in body
                if heading.source in ["bold_paragraph", "css_class", "uppercase_heuristic", "semantic_heading", "bold_paragraph_toplevel"]:
                    # Try to find by anchor
                    if heading.anchor:
                        heading_tag = soup.find(id=heading.anchor)
                    
                    # Try to find by text
                    if not heading_tag:
                        for candidate in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "span", "i", "em", "b", "strong"]):
                            candidate_text = self._extract_clean_heading_text(candidate)
                            if candidate_text == heading.title:
                                heading_tag = candidate
                                break
                
                # If found existing element, convert it
                if heading_tag:
                    # Determine epub:type
                    epub_type = self._determine_epub_type(heading.title)
                    
                    # For top-level formatting elements (i, em, b, strong, span), wrap with h1
                    if heading_tag.name in ["i", "em", "b", "strong", "span"]:
                        new_heading = soup.new_tag(f"h{heading.level}")
                        new_heading.string = heading_tag.get_text()
                        
                        if heading_tag.get("id"):
                            new_heading["id"] = heading_tag["id"]
                        
                        # Use replace_with() - correct BeautifulSoup method!
                        heading_tag.replace_with(new_heading)
                        heading_tag = new_heading
                    
                    # Wrap in section if not already wrapped
                    if heading_tag.parent.name != "section":
                        section = soup.new_tag("section")
                        section["epub:type"] = epub_type
                        heading_tag.wrap(section)
                    
                    # Convert to semantic heading if needed
                    if heading_tag.name not in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                        new_heading = soup.new_tag(f"h{heading.level}")
                        new_heading.string = heading_tag.get_text()
                        if heading_tag.get("id"):
                            new_heading["id"] = heading_tag["id"]
                        heading_tag.replace_with(new_heading)
                
                else:
                    # Heading from non-body source (document_title, ncx_fallback):
                    # Create an h1 at start of body
                    body = soup.find("body")
                    if body and heading.source in ["document_title", "ncx_fallback"]:
                        new_heading = soup.new_tag(f"h{heading.level}")
                        new_heading.string = heading.title
                        
                        # Generate anchor if needed
                        anchor = self._slugify(heading.title, self.existing_ids)
                        new_heading["id"] = anchor
                        self.existing_ids.add(anchor)
                        
                        # Insert at start of body (after any empty text nodes)
                        first_elem = None
                        for child in body.children:
                            if isinstance(child, Tag):
                                first_elem = child
                                break
                        
                        if first_elem:
                            new_heading.insert_before(first_elem)
                        else:
                            body.append(new_heading)
            
            # Write back to file
            with open(file_path, "wb") as f:
                f.write(soup.encode("utf-8"))
        
        except Exception as e:
            self.report.warnings.append(f"Failed to inject semantic markup in {file_path.name}: {str(e)}")

    def _determine_epub_type(self, text: str) -> str:
        """
        Determine epub:type from heading text pattern.
        
        Args:
            text: Heading text
            
        Returns:
            epub:type value (e.g., "chapter", "part", "appendix")
        """
        text_lower = text.lower()
        
        if re.search(r"(capitolo|chapter)\s+\d+", text_lower):
            return "chapter"
        elif re.search(r"(parte|part)\s+\d+", text_lower):
            return "part"
        elif re.search(r"appendice|appendix", text_lower):
            return "appendix"
        elif re.search(r"introduzione|introduction|preface|prefazione", text_lower):
            return "preface"
        elif re.search(r"dedica|dedication", text_lower):
            return "dedication"
        elif re.search(r"note|notes|endnote", text_lower):
            return "endnotes"
        else:
            return "chapter"  # Default to chapter

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


def run_phase2(
    input_epub: str,
    output_epub: str,
    report: PipelineReport,
    ncx_entries: Optional[dict] = None
) -> bool:
    """
    Run Phase 2: Semantic Upgrade with 6-pass heading detection.
    
    Args:
        input_epub: Path to input EPUB
        output_epub: Path to output EPUB
        report: PipelineReport instance
        ncx_entries: Original NCX entries from Phase 0
        
    Returns:
        True if successful, False otherwise
    """
    try:
        analyzer = Phase2Analyzer(input_epub, report, ncx_entries)
        report.phases_run.append("2")
        
        # Execute with SE tool fallback
        success = analyzer.execute(se_tool_name="semanticate", output_path=output_epub)
        
        return success
    
    except Exception as e:
        report.validation_errors.append(f"Phase 2 failed: {str(e)}")
        return False
