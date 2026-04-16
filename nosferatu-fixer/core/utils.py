"""Utilities for EPUB processing."""

import posixpath
import re
from typing import Optional
from zipfile import ZipFile

from bs4 import BeautifulSoup
from lxml import etree


def resolve_ncx_path(container_xml_bytes: bytes, opf_path: str, zip_file: ZipFile) -> Optional[str]:
    """
    Resolve NCX file path with 3-method fallback.
    
    BUG-1 FIX: NCX path must be resolved relative to OPF directory, not used as literal string.
    
    Args:
        container_xml_bytes: Content of META-INF/container.xml
        opf_path: Path to OPF file (e.g., "OEBPS/content.opf")
        zip_file: Open ZipFile object
    
    Returns:
        Resolved NCX path in ZIP, or None if not found
    """
    opf_base = posixpath.dirname(opf_path)  # e.g., "OEBPS"
    
    # Parse OPF to find NCX reference
    try:
        opf_content = zip_file.read(opf_path)
        opf_soup = BeautifulSoup(opf_content, "lxml-xml")
    except Exception:
        return None
    
    # METHOD A: From spine toc="<id>" attribute
    spine = opf_soup.find("spine")
    if spine and spine.get("toc"):
        ncx_id = spine.get("toc")
        manifest = opf_soup.find("manifest")
        if manifest:
            item = manifest.find("item", {"id": ncx_id})
            if item and item.get("href"):
                ncx_href = item["href"]
                ncx_path = posixpath.normpath(posixpath.join(opf_base, ncx_href))
                if _safe_zip_exists(zip_file, ncx_path):
                    return ncx_path
    
    # METHOD B: By media-type from manifest
    manifest = opf_soup.find("manifest")
    if manifest:
        for item in manifest.find_all("item"):
            if item.get("media-type") == "application/x-dtbncx+xml":
                ncx_href = item.get("href")
                if ncx_href:
                    ncx_path = posixpath.normpath(posixpath.join(opf_base, ncx_href))
                    if _safe_zip_exists(zip_file, ncx_path):
                        return ncx_path
    
    # METHOD C: Heuristic filename search (last resort)
    for name in zip_file.namelist():
        if name.lower().endswith("toc.ncx"):
            return name
    
    return None


def _safe_zip_exists(z: ZipFile, zip_key: str) -> bool:
    """Check if a file exists in ZIP (case-insensitive fallback)."""
    try:
        z.getinfo(zip_key)
        return True
    except KeyError:
        # Case-insensitive fallback for Linux compatibility
        for name in z.namelist():
            if name.lower() == zip_key.lower():
                return True
    return False


def build_zip_key(opf_base: str, item_href: str) -> str:
    """
    Build ZIP key from OPF base and item href.
    
    BUG-3 FIX: Never use spine href directly as ZIP key.
    Always resolve relative to OPF base directory.
    
    Args:
        opf_base: Directory containing OPF file (e.g., "OEBPS")
        item_href: Relative href from manifest (e.g., "../Text/chapter01.html")
    
    Returns:
        Normalized ZIP key
    """
    return posixpath.normpath(posixpath.join(opf_base, item_href))


def safe_read(z: ZipFile, zip_key: str) -> Optional[bytes]:
    """
    Read file from ZIP with case-insensitive fallback.
    
    Args:
        z: Open ZipFile
        zip_key: Path within ZIP
    
    Returns:
        File content, or None if not found
    """
    try:
        return z.read(zip_key)
    except KeyError:
        # Case-insensitive fallback for Linux compatibility
        for name in z.namelist():
            if name.lower() == zip_key.lower():
                return z.read(name)
    return None


def select_parser(filename: str) -> str:
    """
    Select appropriate BeautifulSoup parser based on file extension.
    
    BUG-3 FIX: Calibre generates .html files that are NOT valid XHTML.
    Using "lxml-xml" on them crashes or returns empty DOM trees.
    
    Args:
        filename: Name or path of file
    
    Returns:
        Parser name: "lxml-xml" for .xhtml, "lxml" for .html
    """
    if filename.lower().endswith(".xhtml"):
        return "lxml-xml"
    return "lxml"


def parse_ncx_entries(ncx_bytes: bytes) -> list[tuple[str, str]]:
    """
    Parse NCX file to extract navPoint entries.
    
    BUG-2 FIX: Use lxml.etree with explicit namespace instead of BeautifulSoup,
    which fails to handle the DAISY default namespace correctly.
    
    Args:
        ncx_bytes: Content of NCX file
    
    Returns:
        List of (label, src) tuples
    """
    NCX_NS = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
    
    try:
        root = etree.fromstring(ncx_bytes)
    except Exception:
        return []
    
    entries = []
    navpoints = root.findall(".//ncx:navPoint", NCX_NS)
    
    for np in navpoints:
        label_elem = np.find("ncx:navLabel/ncx:text", NCX_NS)
        content_elem = np.find("ncx:content", NCX_NS)
        
        if label_elem is not None and content_elem is not None:
            label = label_elem.text or ""
            src = content_elem.get("src", "")
            if src:
                entries.append((label, src))
    
    return entries
