# EPUB Standards Reference

Quick reference for EPUB specifications and standards used in TOC Fixer.

## 📖 EPUB Structure

### Directory Layout

```
EPUB Root/
├── mimetype          # "application/epub+zip" (uncompressed, first in ZIP)
├── META-INF/
│   ├── container.xml # Manifest: rootfile→OPF path
│   └── .DS_Store     # (macOS only, ignore)
├── OEBPS/            # Content root (name varies)
│   ├── package.opf   # Manifest + metadata
│   ├── toc.ncx       # EPUB2 TOC (navigation)
│   ├── nav.xhtml     # EPUB3 TOC (navigation)
│   ├── styles/
│   │   └── style.css
│   ├── ch01.html     # Content file 1
│   ├── ch02.html     # Content file 2
│   └── images/
│       └── cover.jpg
└── [Other folders]
```

### File Roles

| File | Purpose | Format | Versions |
|------|---------|--------|----------|
| `mimetype` | ZIP type marker | Plain text | EPUB2, 3 |
| `container.xml` | Manifest | XML | EPUB2, 3 |
| `package.opf` | Metadata + spine | XML | EPUB2, 3 |
| `toc.ncx` | Navigation (EPUB2) | XML | EPUB2 (optional in EPUB3) |
| `nav.xhtml` | Navigation (EPUB3) | XHTML | EPUB3 |

---

## 📋 container.xml

Points to the OPF file containing metadata and spine.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" 
           xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfile full-path="OEBPS/package.opf" 
            media-type="application/oebps-package+xml"/>
</container>
```

**Key Elements**:
- `@version`: 1.0 only
- `rootfile@full-path`: Path to OPF file (relative to EPUB root)
- `rootfile@media-type`: Always "application/oebps-package+xml"

---

## 📄 package.opf

Main metadata file containing spine, manifest, and TOC reference.

### Metadata Section

```xml
<metadata>
  <dc:title>The Book Title</dc:title>
  <dc:creator>Author Name</dc:creator>
  <dc:language>en</dc:language>
  <dc:date>2023-01-01</dc:date>
  <dc:identifier id="uuid_id">urn:uuid:...</dc:identifier>
  <!-- Optional: -->
  <dc:publisher>Publisher</dc:publisher>
  <dc:rights>Copyright info</dc:rights>
  <meta name="cover" content="cover_image_id"/>
</metadata>
```

### Manifest Section

References all files in EPUB:

```xml
<manifest>
  <item id="ncx" href="toc.ncx" 
        media-type="application/x-dtbncx+xml"/>
  <item id="nav" href="nav.xhtml" 
        media-type="application/xhtml+xml" 
        properties="nav"/>
  <item id="ch01" href="OEBPS/ch01.html" 
        media-type="text/html"/>
  <item id="style" href="OEBPS/styles/style.css" 
        media-type="text/css"/>
  <item id="cover" href="OEBPS/images/cover.jpg" 
        media-type="image/jpeg"/>
</manifest>
```

**Key Attributes**:
- `@id`: Unique identifier
- `@href`: File path (relative to OPF)
- `@media-type`: MIME type
- `@properties`: Optional (EPUB3): nav, mathml, svg, switch, scripted

### Spine Section

Ordered list of content files (reading order):

```xml
<spine toc="ncx">
  <!-- Reading order - must match manifest ID -->
  <itemref idref="ch01"/>
  <itemref idref="ch02"/>
  <itemref idref="ch03"/>
  <!-- Optional EPUB3 attributes: -->
  <!-- <itemref idref="ch01" linear="yes" properties="page-spread-left"/> -->
</spine>
```

**Key Attributes**:
- `@toc`: EPUB2 NCX ID (required for EPUB2)
- `itemref@idref`: Manifest ID
- `itemref@linear`: (EPUB3) "yes"/"no" (skip in reader?)
- `itemref@properties`: (EPUB3) page-spread-*, rendition:* (deprecated)

### OPF Example (EPUB2)

```xml
<?xml version="1.0"?>
<package version="2.0" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Around the World in Eighty Days</dc:title>
    <dc:creator>Jules Verne</dc:creator>
    <dc:language>en</dc:language>
    <dc:identifier id="uuid">urn:uuid:...</dc:identifier>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="ch01" href="ch01.html" media-type="text/html"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="ch01"/>
  </spine>
</package>
```

### OPF Example (EPUB3)

```xml
<?xml version="1.0"?>
<package version="3.0" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Around the World in Eighty Days</dc:title>
    <dc:creator>Jules Verne</dc:creator>
    <dc:language>en</dc:language>
    <dc:identifier>urn:uuid:...</dc:identifier>
  </metadata>
  <manifest>
    <!-- NCX optional in EPUB3, but often included for compatibility -->
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <!-- EPUB3 nav document (required) -->
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" 
          properties="nav"/>
    <item id="ch01" href="ch01.html" media-type="text/html"/>
  </manifest>
  <spine>
    <itemref idref="ch01"/>
  </spine>
</package>
```

---

## 🗂️ toc.ncx (EPUB2 Navigation)

EPUB2 table of contents file (DAISY format).

```xml
<?xml version="1.0"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"
 "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:..."/>
    <meta name="dtb:depth" content="2"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle>
    <text>Around the World in Eighty Days</text>
  </docTitle>
  <navMap>
    <navPoint id="navPoint1" playOrder="1">
      <navLabel>
        <text>Chapter 1: Departure</text>
      </navLabel>
      <content src="ch01.html"/>
    </navPoint>
    <navPoint id="navPoint2" playOrder="2">
      <navLabel>
        <text>Chapter 2: The Challenge</text>
      </navLabel>
      <content src="ch02.html"/>
      <!-- Nested nav points -->
      <navPoint id="navPoint2a" playOrder="3">
        <navLabel>
          <text>Section 2.1: First Steps</text>
        </navLabel>
        <content src="ch02.html#section1"/>
      </navPoint>
    </navPoint>
  </navMap>
</ncx>
```

**Key Elements**:
- `ncx@version`: "2005-1" (only version)
- `head/meta@name="dtb:uid"`: Document UUID
- `head/meta@name="dtb:depth"`: Max heading level (usually 2-3)
- `docTitle/text`: Book title
- `navMap/navPoint`: TOC entries (can nest)
- `navPoint@playOrder`: Reading order (sequential)
- `navLabel/text`: Display title
- `content@src`: Target file (+ optional anchor)

---

## 📰 nav.xhtml (EPUB3 Navigation)

EPUB3 table of contents (standard XHTML with special markup).

```xml
<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml" 
      xmlns:epub="http://www.idpf.org/2007/ops">
  <head>
    <title>Table of Contents</title>
  </head>
  <body>
    <nav epub:type="toc" id="toc">
      <h1>Contents</h1>
      <ol>
        <li><a href="ch01.html">Chapter 1: Departure</a></li>
        <li><a href="ch02.html">Chapter 2: The Challenge</a>
          <ol>
            <li><a href="ch02.html#section1">Section 2.1: First Steps</a></li>
            <li><a href="ch02.html#section2">Section 2.2: The Race</a></li>
          </ol>
        </li>
        <li><a href="ch03.html">Chapter 3: Conclusion</a></li>
      </ol>
    </nav>
  </body>
</html>
```

**Key Elements**:
- `nav@epub:type="toc"`: Identifies TOC navigation
- `h1`: TOC title ("Table of Contents" or "Contents")
- `ol`: Ordered list structure (can nest)
- `li/a@href`: Links to content (file + optional anchor)

---

## 📑 Content Files (HTML/XHTML)

### HTML (Calibre style)

```html
<!DOCTYPE html>
<html>
<head>
  <title>Chapter 1</title>
  <link rel="stylesheet" type="text/css" href="../styles/style.css"/>
</head>
<body>
  <h1 id="ch1">Chapter 1: Departure</h1>
  <p>The story begins...</p>
  
  <h2 id="ch1s1">Section 1.1: Setting</h2>
  <p>More content...</p>
</body>
</html>
```

**Characteristics**:
- Looser DOCTYPE
- May use HTML entities not valid in XHTML
- Easier for Calibre to generate
- Less strict namespace handling

### XHTML (Standard Ebooks style)

```xml
<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>Chapter 1</title>
  <link rel="stylesheet" type="text/css" href="../styles/style.css"/>
</head>
<body>
  <h1 id="ch1">Chapter 1: Departure</h1>
  <p>The story begins...</p>
  
  <h2 id="ch1s1">Section 1.1: Setting</h2>
  <p>More content...</p>
</body>
</html>
```

**Characteristics**:
- Strict XML declarations
- Namespace declarations required
- All tags properly closed (`<br/>` not `<br>`)
- More validation-friendly

---

## 🔄 Namespace Declarations

### HTML Namespace

```xml
<html xmlns="http://www.w3.org/1999/xhtml">
```

### EPUB 3 OPS Namespace

```xml
<html xmlns="http://www.w3.org/1999/xhtml" 
      xmlns:epub="http://www.idpf.org/2007/ops">
```

Used for:
- `epub:type` attributes (semantic markup)
- `epub:switch` elements (EPUB-specific fallbacks)

### DAISY NCX Namespace

```xml
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
```

### Dublin Core Namespace (Metadata)

```xml
<package xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Title</dc:title>
    <dc:creator>Author</dc:creator>
  </metadata>
</package>
```

---

## 🏷️ Semantic Markup (epub:type)

Common `epub:type` values for semantic structure:

| Type | Usage | Example |
|------|-------|---------|
| `document` | Document root | `<body epub:type="document">` |
| `part` | Major section | `<section epub:type="part">` |
| `chapter` | Chapter | `<section epub:type="chapter">` |
| `section` | Subsection | `<section epub:type="section">` |
| `foreword` | Foreword | `<section epub:type="foreword">` |
| `introduction` | Introduction | `<section epub:type="introduction">` |
| `conclusion` | Conclusion | `<article epub:type="conclusion">` |
| `appendix` | Appendix | `<section epub:type="appendix">` |
| `glossary` | Glossary | `<section epub:type="glossary">` |
| `bibliography` | Bibliography | `<section epub:type="bibliography">` |
| `indexterm` | Index term | `<a epub:type="indexterm">` |

**Usage**:
```xml
<section epub:type="chapter" id="ch01">
  <h1>Chapter 1</h1>
  <section epub:type="section" id="ch01s1">
    <h2>Section 1.1</h2>
  </section>
</section>
```

---

## 📐 MIME Types

Common MIME types in EPUBs:

| Extension | MIME Type | Use |
|-----------|-----------|-----|
| .html | text/html | Flexible HTML content |
| .xhtml | application/xhtml+xml | Strict XHTML content |
| .css | text/css | Stylesheets |
| .jpg | image/jpeg | JPEG images |
| .png | image/png | PNG images |
| .svg | image/svg+xml | Scalable vector graphics |
| .gif | image/gif | GIF images (discouraged) |
| .ncx | application/x-dtbncx+xml | EPUB2 TOC |
| .xml | application/xml | Generic XML |
| .otf | font/opentype | OpenType fonts |
| .ttf | font/ttf | TrueType fonts |
| .woff | font/woff | WOFF fonts |

---

## ✅ EPUB Validation

### se lint (Standard Ebooks)

```bash
se lint /path/to/epub
```

Checks:
- EPUB structure (container.xml, package.opf, etc)
- Semantic markup consistency
- Accessibility (alt text, landmarks)
- Typography (smart quotes, em-dashes, etc)
- HTML/XHTML well-formedness
- CSS validity

### epubcheck (W3C)

```bash
java -jar epubcheck.jar /path/to/epub
```

Checks:
- EPUB spec compliance (EPUB 2 or 3)
- ZIP structure integrity
- XML validity
- Referenced file existence
- Media type compatibility
- Font licensing declarations

### Calibre EPUB Editor

GUI validation:
1. Open EPUB in Calibre
2. Double-click book to open editor
3. Tools → Check book

---

## 🔗 Related Documentation

- [EPUB 3.0 Spec](https://www.w3.org/TR/epub-33/) (W3C)
- [EPUB 2.0 Spec](http://www.idpf.org/epub) (IDPF, legacy)
- [Standard Ebooks](https://standardebooks.org/) (High-quality EPUBs)
- [Calibre Manual](https://manual.calibre-ebook.com/) (EPUB tools)

---

**Categories**: [EPUB Structure](#-epub-structure) | [Standards](#-files) | [Namespaces](#-namespace-declarations) | [Semantic Markup](#-semantic-markup-epubtype)
