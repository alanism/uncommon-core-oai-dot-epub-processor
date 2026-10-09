"""Bounded, offline EPUB-to-text ingestion using only Python's standard library.

No archive members are extracted, no URLs are fetched, and no code is executed.
The reading order is the OPF spine (including ``linear=\"no\"`` entries). Text
is Unicode-whitespace-normalized per block, but is never length-truncated.
Locators are actual archive hrefs and existing XML IDs; CFIs are deliberately
left null. Parsing completeness and non-text content omissions are separate.
"""
from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import stat
import unicodedata
import zipfile
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET


class ReaderError(ValueError):
    """An EPUB is invalid, unsupported, or exceeds the reader's safety limits."""


MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_MEMBERS = 10_000
MAX_SPINE_ITEMS = 2_000
MAX_PASSAGES = 50_000
MAX_NAVIGATION_ENTRIES = 20_000
MAX_OUTPUT_CHARACTERS = 64 * 1024 * 1024
MAX_LABEL_CHARACTERS = 4_096
MAX_LOCATOR_CHARACTERS = 4_096
MAX_COMPRESSION_RATIO = 200
MAX_XML_ELEMENTS = 200_000
MAX_XML_DEPTH = 256
_XHTML_NS = "http://www.w3.org/1999/xhtml"
_XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
_LEGACY_HTML_DTDS = {
    ("-//W3C//DTD XHTML 1.1//EN", "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd"),
    ("-//W3C//DTD XHTML 1.0 Strict//EN", "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"),
    ("-//W3C//DTD XHTML 1.0 Transitional//EN", "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"),
    ("-//W3C//DTD XHTML 1.0 Frameset//EN", "http://www.w3.org/TR/xhtml1/DTD/xhtml1-frameset.dtd"),
}
_SUPPORTED_MEDIA = {"application/xhtml+xml"}
_BLOCKS = {
    "address", "article", "aside", "blockquote", "caption", "dd", "details",
    "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer", "form",
    "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main",
    "nav", "ol", "p", "pre", "section", "summary", "table", "tbody", "td",
    "tfoot", "th", "thead", "tr", "ul",
}
_SKIPPED = {"script", "style"}
_NON_TEXT = {"img", "svg", "math", "audio", "video", "object", "iframe", "embed", "canvas"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _stable_id(kind: str, *parts: Any) -> str:
    value = "\x00".join(str(part) for part in parts).encode("utf-8")
    return f"{kind}:{hashlib.sha256(value).hexdigest()}"


def _label(value: str, context: str) -> str:
    if len(value) > MAX_LABEL_CHARACTERS:
        raise ReaderError(f"EPUB {context} exceeds label length limit")
    return value


def _locator(value: str, context: str) -> str:
    if len(value) > MAX_LOCATOR_CHARACTERS:
        raise ReaderError(f"EPUB {context} exceeds locator length limit")
    return value


class _OutputBudget:
    def __init__(self):
        self.characters = 0

    def add(self, value: Any) -> None:
        # Count serialized characters, including escaping and repeated labels.
        # Counting some parent structures twice is deliberately conservative.
        encoder = json.JSONEncoder(ensure_ascii=False, separators=(",", ":"))
        for part in encoder.iterencode(value):
            self.characters += len(part)
            if self.characters > MAX_OUTPUT_CHARACTERS:
                raise ReaderError("EPUB serialized output exceeds safety limit")


def _member_name(name: str) -> str:
    _locator(name, "ZIP member name")
    # ZIP names are literal paths, not URLs. Also reject percent-encoded unsafe
    # variants so future URI consumers cannot reinterpret them as traversal.
    if not name or "\x00" in name or "\\" in name:
        raise ReaderError(f"Unsafe ZIP member name: {name!r}")
    for candidate in (name, unquote(name)):
        if candidate.startswith("/") or "\\" in candidate or "\x00" in candidate:
            raise ReaderError(f"Unsafe ZIP member name: {name!r}")
        parts = candidate.split("/")
        if ".." in parts or ":" in parts[0]:
            raise ReaderError(f"ZIP path traversal is not allowed: {name!r}")
    result = unicodedata.normalize("NFC", posixpath.normpath(name))
    if result in ("", "."):
        raise ReaderError(f"Unsafe ZIP member name: {name!r}")
    return result


def _resolve_href(base: str, href: str) -> str:
    _locator(href, "href")
    try:
        parts = urlsplit(href)
        path = unquote(parts.path, encoding="utf-8", errors="strict")
    except (ValueError, UnicodeError) as exc:
        raise ReaderError(f"Invalid resource href: {href!r}") from exc
    if (not path or parts.scheme or parts.netloc or parts.query or parts.fragment
            or path.startswith("/") or "\\" in path or "\x00" in path):
        raise ReaderError(f"Only local, whole-resource EPUB hrefs are supported: {href!r}")
    result = posixpath.normpath(posixpath.join(posixpath.dirname(base), path))
    if result == ".." or result.startswith("../") or ":" in result.split("/")[0]:
        raise ReaderError(f"Resource href escapes the EPUB archive: {href!r}")
    return unicodedata.normalize("NFC", result)


class _SafeTreeBuilder(ET.TreeBuilder):
    def __init__(self, href: str):
        super().__init__()
        self.href = href
        self.depth = 0
        self.count = 0

    def start(self, tag: str, attrs: dict[str, str]) -> ET.Element:
        self.depth += 1
        self.count += 1
        # Enforce bounds before asking TreeBuilder to allocate another node,
        # rather than constructing an unbounded tree and counting afterward.
        if self.depth > MAX_XML_DEPTH or self.count > MAX_XML_ELEMENTS:
            raise ReaderError(f"XML structure exceeds safety limits: {self.href}")
        return super().start(tag, attrs)

    def end(self, tag: str) -> ET.Element:
        node = super().end(tag)
        self.depth -= 1
        return node

    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        raise ReaderError("XML DTDs and entity declarations are not supported")


def _strip_inert_html_doctype(data: bytes, *, ncx: bool = False) -> bytes:
    """Remove only an exact known HTML declaration, never load a DTD.

    Internal subsets, ENTITY declarations, arbitrary PUBLIC/SYSTEM identifiers,
    and declarations in non-ASCII-compatible encodings remain forbidden. Legacy
    declarations are compatibility markers only; their named entities are not
    defined or expanded. XML's five built-in entities still work normally.
    """
    # Only strip a real declaration in the document prolog, never a literal
    # occurrence in CDATA, a comment, a PI, or book prose. Unrecognized prolog
    # layouts fail closed in _xml rather than rewriting source text.
    match = re.match(
        rb"\A(?:\xef\xbb\xbf)?\s*(?:<\?xml\s+[^?]*\?>\s*)?(<!DOCTYPE[^>]*>)",
        data,
    )
    if match is None or len(re.findall(rb"<!DOCTYPE", data)) != 1:
        return data
    declaration = match.group(1)
    if ncx:
        ncx_marker = re.fullmatch(
            rb"""<!DOCTYPE\s+ncx\s+PUBLIC\s+(["'])-//NISO//DTD ncx 2005-1//EN\1\s+(["'])http://www[.]daisy[.]org/z3986/2005/ncx-2005-1[.]dtd\2\s*>""",
            declaration,
        )
        if ncx_marker:
            return data[:match.start(1)] + data[match.end(1):]
        return data
    if re.fullmatch(rb"<!DOCTYPE\s+html\s*>", declaration):
        return data[:match.start(1)] + data[match.end(1):]
    legacy = re.fullmatch(
        rb"""<!DOCTYPE\s+html\s+PUBLIC\s+(["'])([^"']+)\1\s+(["'])([^"']+)\3\s*>""",
        declaration,
    )
    if legacy is not None:
        try:
            pair = (legacy.group(2).decode("ascii"), legacy.group(4).decode("ascii"))
        except UnicodeError:
            return data
        if pair in _LEGACY_HTML_DTDS:
            return data[:match.start(1)] + data[match.end(1):]
    return data


def _xml(data: bytes, href: str, *, allow_html_doctype: bool = False, allow_ncx_doctype: bool = False) -> ET.Element:
    if allow_html_doctype or allow_ncx_doctype:
        data = _strip_inert_html_doctype(data, ncx=allow_ncx_doctype)
    # The parser callback also catches UTF-16/32 or other XML encodings. This
    # early check avoids doing any DTD work for the usual encodings.
    scan = data.replace(b"\x00", b"").upper()
    if b"<!DOCTYPE" in scan or b"<!ENTITY" in scan:
        raise ReaderError(f"XML DTD/entity declarations are forbidden: {href}")
    try:
        root = ET.fromstring(data, parser=ET.XMLParser(target=_SafeTreeBuilder(href)))
    except (ET.ParseError, LookupError, ValueError) as exc:
        if isinstance(exc, ReaderError):
            raise
        raise ReaderError(f"Invalid XML in {href}: {exc}") from exc
    return root


class _Archive:
    def __init__(self, archive: zipfile.ZipFile):
        self.archive = archive
        self.members: dict[str, zipfile.ZipInfo] = {}
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ReaderError("EPUB archive has too many members")
        total = 0
        for info in infos:
            # ZipInfo.filename silently drops content after NUL; orig_filename
            # preserves it and must be checked before trusting the lookup key.
            name = _member_name(info.orig_filename)
            if name in self.members:
                raise ReaderError(f"Duplicate canonical ZIP member: {name}")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ReaderError(f"ZIP symlinks are forbidden: {name}")
            if info.flag_bits & 1:
                raise ReaderError(f"Encrypted ZIP members are unsupported: {name}")
            if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ReaderError(f"Unsupported ZIP compression for {name}")
            if info.file_size < 0 or info.file_size > MAX_MEMBER_BYTES:
                raise ReaderError(f"ZIP member exceeds size limit: {name}")
            total += info.file_size
            if total > MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise ReaderError("EPUB uncompressed size exceeds safety limit")
            if info.file_size and (
                info.compress_size == 0
                or info.file_size > info.compress_size * MAX_COMPRESSION_RATIO
            ):
                raise ReaderError(f"Suspicious ZIP compression ratio: {name}")
            self.members[name] = info

    def read(self, href: str) -> bytes:
        info = self.members.get(href)
        if info is None or info.is_dir():
            raise ReaderError(f"EPUB resource is missing: {href}")
        try:
            with self.archive.open(info, "r") as stream:
                data = stream.read(MAX_MEMBER_BYTES + 1)
            if len(data) > MAX_MEMBER_BYTES or len(data) != info.file_size:
                raise ReaderError(f"Invalid or oversized ZIP member: {href}")
            return data
        except (zipfile.BadZipFile, RuntimeError, OSError, EOFError, NotImplementedError) as exc:
            raise ReaderError(f"Cannot read EPUB resource {href}: {exc}") from exc


@dataclass
class _Block:
    text: str
    element_id: str | None
    section_id: str
    section: str


def _element_id(node: ET.Element) -> str | None:
    value = node.get("id") or node.get(_XML_ID)
    return _locator(value, "element ID") if value else None


def _content_elements(root: ET.Element):
    """Traverse content in document order without descending into code/styles."""
    stack = [root]
    while stack:
        node = stack.pop()
        if _local(node.tag) in _SKIPPED:
            continue
        yield node
        stack.extend(reversed(node))


def _visible_text(node: ET.Element) -> str:
    if _local(node.tag) in _SKIPPED:
        return ""
    parts = [node.text or ""]
    if _local(node.tag) == "img" and node.get("alt"):
        parts.append(node.get("alt", ""))
    for child in node:
        if _local(child.tag) == "br":
            parts.append(" ")
        parts.append(_visible_text(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _text_blocks(root: ET.Element, href: str, chapter_id: str,
                 chapter_label: str | None = None, fragment_labels: dict[str, str] | None = None,
                 budget: _OutputBudget | None = None) -> tuple[
    str, list[_Block], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    budget = budget or _OutputBudget()
    if root.tag not in ("html", f"{{{_XHTML_NS}}}html"):
        raise ReaderError(f"Spine resource is not XHTML: {href}")
    seen_ids: set[str] = set()
    for node in root.iter():
        anchor = _element_id(node)
        if anchor:
            if anchor in seen_ids:
                raise ReaderError(f"Duplicate XML element ID in {href}: {anchor!r}")
            seen_ids.add(anchor)
    bodies = [node for node in root if _local(node.tag) == "body"]
    if len(bodies) != 1:
        raise ReaderError(f"XHTML must have exactly one body: {href}")
    body = bodies[0]
    head = next((node for node in root if _local(node.tag) == "head"), None)
    head_title = ""
    if head is not None:
        title_node = next((node for node in head if _local(node.tag) == "title"), None)
        if title_node is not None:
            head_title = _normalize(_visible_text(title_node))
    h1 = next((node for node in _content_elements(body) if _local(node.tag) == "h1"), None)
    title = (_normalize(_visible_text(h1)) if h1 is not None else "")
    title = _label(chapter_label or title or head_title or posixpath.basename(href), "chapter title")
    fragment_labels = fragment_labels or {}
    sections: list[dict[str, Any]] = [{
        "id": _stable_id("section", chapter_id, 0), "title": title,
        "level": 0, "element_id": _element_id(body), "passage_ids": [],
    }]
    budget.add(sections[0])
    current_section = sections[0]
    heading_stack: list[tuple[int, str]] = []
    blocks: list[_Block] = []
    excluded: list[dict[str, Any]] = []
    omitted: list[dict[str, Any]] = []
    buffer: list[str] = []
    buffer_anchor: str | None = None
    buffer_section = current_section

    def flush() -> None:
        nonlocal buffer
        text = _normalize("".join(buffer))
        if text:
            if len(blocks) >= MAX_PASSAGES:
                raise ReaderError("EPUB text block count exceeds output safety limit")
            blocks.append(_Block(text, buffer_anchor, buffer_section["id"], buffer_section["title"]))
        buffer = []

    def append(text: str | None, anchor: str | None) -> None:
        nonlocal buffer_anchor, buffer_section
        if text is None:
            return
        # Anchor changes flush only at enclosing block boundaries, so an inline
        # ID never falsely claims to locate surrounding text outside that ID.
        if not buffer:
            buffer_anchor = anchor
            buffer_section = current_section
        buffer.append(text)

    def walk(node: ET.Element, parent_anchor: str | None) -> None:
        nonlocal current_section
        tag = _local(node.tag)
        if tag in _SKIPPED:
            excluded.append({"href": href, "element": tag, "element_id": _element_id(node),
                             "reason": f"{tag} content is not executed or treated as book prose",
                             "text_characters": len("".join(node.itertext()))})
            return
        nav_label = fragment_labels.get(_element_id(node) or "")
        is_block = tag in _BLOCKS or tag == "body" or bool(nav_label)
        anchor = (_element_id(node) or parent_anchor) if is_block else parent_anchor
        if is_block:
            flush()
        if re.fullmatch(r"h[1-6]", tag) or nav_label:
            heading = _label(nav_label or _normalize(_visible_text(node)), "section heading")
            if heading:
                level = int(tag[1]) if re.fullmatch(r"h[1-6]", tag) else 0
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, heading))
                current_section = {
                    "id": _stable_id("section", chapter_id, len(sections)),
                    "title": _label(" / ".join(label for _, label in heading_stack), "section title"),
                    "level": level, "element_id": _element_id(node), "passage_ids": [],
                }
                budget.add(current_section)
                if len(sections) >= MAX_PASSAGES:
                    raise ReaderError("EPUB section count exceeds output safety limit")
                sections.append(current_section)
        if tag in _NON_TEXT:
            omitted.append({"href": href, "element": tag, "element_id": _element_id(node),
                            "resource": _locator(node.get("src") or node.get("data") or "", "media reference") or None,
                            "reason": ("MathML layout/semantics are not interpreted; descendant text alone may be ambiguous"
                                       if tag == "math" else
                                       "Visual/media content is not decoded; available text or alt text is retained"),
                            "has_text_alternative": bool(node.get("alt") or _normalize(_visible_text(node)))})
        if tag == "br":
            append("\n", parent_anchor)
        if tag == "img" and node.get("alt"):
            append(node.get("alt"), anchor)
        append(node.text, anchor)
        for child in node:
            walk(child, anchor)
            append(child.tail, anchor)
        if is_block:
            flush()

    if head is not None:
        for node in head.iter():
            if _local(node.tag) in _SKIPPED:
                excluded.append({"href": href, "element": _local(node.tag),
                                 "element_id": _element_id(node),
                                 "reason": "Head script/style content is excluded from book prose",
                                 "text_characters": len("".join(node.itertext()))})
    walk(body, _element_id(body))
    flush()
    return title, blocks, sections, excluded, omitted


def _chunks(text: str, max_chars: int):
    """Partition text, retaining every character including split whitespace."""
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary + 1
        yield text[start:end]
        start = end


def _navigation_labels(archive: _Archive, manifest: dict[str, ET.Element],
                       opf_href: str, spine: ET.Element) -> tuple[
    dict[str, str], dict[str, dict[str, str]], list[dict[str, Any]], list[str]
]:
    """Read genuine EPUB 3 TOC / EPUB 2 NCX labels without following URLs."""
    titles: dict[str, str] = {}
    fragments: dict[str, dict[str, str]] = {}
    warnings: list[dict[str, Any]] = []
    parsed: list[str] = []
    candidates: list[tuple[ET.Element, bool]] = []
    nav = next((item for item in manifest.values() if "nav" in item.get("properties", "").split()), None)
    if nav is not None:
        candidates.append((nav, False))
    ncx = manifest.get(spine.get("toc", ""))
    if ncx is None:
        ncx = next((item for item in manifest.values() if item.get("media-type") == "application/x-dtbncx+xml"), None)
    if ncx is not None:
        candidates.append((ncx, True))
    entry_count = 0
    for item, is_ncx in candidates:
        href = _resolve_href(opf_href, item.get("href", ""))
        root = _xml(archive.read(href), href,
                    allow_html_doctype=not is_ncx, allow_ncx_doctype=is_ncx)
        parsed.append(href)
        links: list[tuple[str, str]] = []
        if is_ncx:
            if _local(root.tag) != "ncx":
                raise ReaderError(f"Navigation resource is not NCX: {href}")
            for point in root.iter():
                if _local(point.tag) != "navPoint":
                    continue
                label = next((node for node in point if _local(node.tag) == "navLabel"), None)
                content = next((node for node in point if _local(node.tag) == "content"), None)
                if label is not None and content is not None:
                    links.append((content.get("src", ""), _normalize("".join(label.itertext()))))
        else:
            for node in _content_elements(root):
                if _local(node.tag) != "nav":
                    continue
                types = node.get("{http://www.idpf.org/2007/ops}type", "").split()
                if "toc" not in types and node.get("role") != "doc-toc":
                    continue
                for link in _content_elements(node):
                    if _local(link.tag) == "a":
                        links.append((link.get("href", ""), _normalize(_visible_text(link))))
        for target, label in links:
            entry_count += 1
            if entry_count > MAX_NAVIGATION_ENTRIES:
                raise ReaderError("EPUB navigation exceeds entry limit")
            if not label:
                continue
            _label(label, "navigation label")
            _locator(target, "navigation target")
            try:
                parts = urlsplit(target)
                plain = parts._replace(fragment="").geturl()
                if not parts.path and not parts.scheme and not parts.netloc:
                    plain = posixpath.basename(href)
                resolved = _resolve_href(href, plain)
                fragment = unquote(parts.fragment, encoding="utf-8", errors="strict")
            except (ReaderError, ValueError, UnicodeError):
                warnings.append({"navigation_href": href, "target": target,
                                 "reason": "Navigation target is not a supported local EPUB reference"})
                continue
            if fragment:
                fragments.setdefault(resolved, {}).setdefault(fragment, label)
            else:
                titles.setdefault(resolved, label)
    return titles, fragments, warnings, parsed


def _ingest(archive: _Archive, book_id: str, max_chars: int) -> dict[str, Any]:
    if archive.read("mimetype").strip() != b"application/epub+zip":
        raise ReaderError("EPUB mimetype must be application/epub+zip")
    container = _xml(archive.read("META-INF/container.xml"), "META-INF/container.xml")
    rootfiles = [node for node in container.iter() if _local(node.tag) == "rootfile"
                 and node.get("media-type") == "application/oebps-package+xml"]
    if not rootfiles:
        raise ReaderError("EPUB container has no supported OPF rootfile")
    opf_href = _resolve_href("", rootfiles[0].get("full-path", ""))
    opf = _xml(archive.read(opf_href), opf_href)
    if _local(opf.tag) != "package":
        raise ReaderError("EPUB package resource is not an OPF package")
    metadata = next((node for node in opf if _local(node.tag) == "metadata"), None)
    titles: list[str] = []
    authors: list[str] = []
    if metadata is not None:
        for node in metadata:
            kind = _local(node.tag)
            if kind not in ("title", "creator"):
                continue
            value = _label(_normalize("".join(node.itertext())), f"metadata {kind}")
            if value and kind == "title":
                titles.append(value)
            if value and kind == "creator":
                authors.append(value)
    manifest_node = next((node for node in opf if _local(node.tag) == "manifest"), None)
    spine = next((node for node in opf if _local(node.tag) == "spine"), None)
    if manifest_node is None or spine is None:
        raise ReaderError("EPUB package must contain a manifest and spine")
    manifest: dict[str, ET.Element] = {}
    for item in manifest_node:
        if _local(item.tag) != "item":
            continue
        item_id = item.get("id", "")
        if not item_id or item_id in manifest:
            raise ReaderError("Manifest item IDs must be present and unique")
        manifest[item_id] = item
    spine_items = [node for node in spine if _local(node.tag) == "itemref"]
    if not spine_items:
        raise ReaderError("EPUB spine is empty")
    if len(spine_items) > MAX_SPINE_ITEMS:
        raise ReaderError("EPUB spine exceeds resource limit")
    # Reject amplification before parsing any chapter. An archive resource may
    # appear only once, even under different manifest IDs or equivalent hrefs.
    seen_spine_hrefs: set[str] = set()
    seen_spine_ids: set[str] = set()
    for itemref in spine_items:
        idref = itemref.get("idref", "")
        if idref not in manifest:
            raise ReaderError(f"Spine references unknown manifest item: {idref!r}")
        href = _resolve_href(opf_href, manifest[idref].get("href", ""))
        if idref in seen_spine_ids or href in seen_spine_hrefs:
            raise ReaderError(f"Repeated spine resource is unsupported: {href}")
        seen_spine_ids.add(idref)
        seen_spine_hrefs.add(href)
    nav_titles, nav_fragments, nav_warnings, nav_resources = _navigation_labels(archive, manifest, opf_href, spine)

    passages: list[dict[str, Any]] = []
    budget = _OutputBudget()
    book_title = titles[0] if titles else "Untitled"
    book_author = _label("; ".join(authors), "combined author names")
    reading_order: list[dict[str, Any]] = []
    parsed_details: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    content_omissions: list[dict[str, Any]] = []
    spine_ids: set[str] = set()
    for chapter_ordinal, itemref in enumerate(spine_items):
        idref = itemref.get("idref", "")
        if idref not in manifest:
            raise ReaderError(f"Spine references unknown manifest item: {idref!r}")
        spine_ids.add(idref)
        item = manifest[idref]
        media_type = item.get("media-type", "")
        if media_type not in _SUPPORTED_MEDIA:
            raise ReaderError(f"Unsupported spine resource {idref!r}: {media_type!r}; no partial ingestion produced")
        href = _resolve_href(opf_href, item.get("href", ""))
        root = _xml(archive.read(href), href, allow_html_doctype=True)
        chapter_id = _stable_id("chapter", book_id, chapter_ordinal, href)
        available_ids = {_element_id(node) for node in _content_elements(root)}
        fragment_labels = {}
        for fragment, label in nav_fragments.get(href, {}).items():
            if fragment in available_ids:
                fragment_labels[fragment] = label
            else:
                nav_warnings.append({"href": href, "element_id": fragment,
                                     "reason": "Navigation fragment does not match an existing content element ID"})
        title, blocks, sections, skipped, omitted = _text_blocks(
            root, href, chapter_id, nav_titles.get(href), fragment_labels, budget)
        excluded.extend(skipped)
        content_omissions.extend(omitted)
        chapter_passages: list[str] = []
        section_map = {section["id"]: section for section in sections}
        chapter_chars = 0
        for block_ordinal, block in enumerate(blocks):
            chapter_chars += len(block.text)
            for chunk_ordinal, text in enumerate(_chunks(block.text, max_chars)):
                if len(passages) >= MAX_PASSAGES:
                    raise ReaderError("EPUB passage count exceeds output safety limit")
                passage_id = _stable_id("passage", chapter_id, block_ordinal, chunk_ordinal, text)
                passage = {
                    "id": passage_id, "book_id": book_id,
                    "book_title": book_title,
                    "book_author": book_author, "chapter": title,
                    "chapter_id": chapter_id, "section": block.section,
                    "section_id": block.section_id, "href": href,
                    "element_id": block.element_id, "cfi": None, "text": text,
                    "ordinal": len(passages), "block_ordinal": block_ordinal,
                    "chunk_ordinal": chunk_ordinal,
                }
                budget.add(passage)
                passages.append(passage)
                chapter_passages.append(passage_id)
                section_map[block.section_id]["passage_ids"].append(passage_id)
        reading_order.append({
            "id": chapter_id, "href": href, "title": title, "ordinal": chapter_ordinal,
            "linear": itemref.get("linear", "yes") != "no", "manifest_id": idref,
            "passage_ids": chapter_passages, "sections": sections,
        })
        budget.add(reading_order[-1])
        parsed_details.append({"href": href, "chapter_id": chapter_id,
                               "passages": len(chapter_passages), "normalized_text_characters": chapter_chars})
    non_spine = [{"manifest_id": item_id, "href": item.get("href"),
                  "media_type": item.get("media-type"),
                  "reason": "Manifest resource is outside the OPF spine"}
                 for item_id, item in manifest.items() if item_id not in spine_ids]
    text_chars = sum(len(passage["text"]) for passage in passages)
    document = {
        "schema_version": 1,
        "book": {"id": book_id, "title": book_title,
                 "author": book_author, "sha256": book_id.removeprefix("sha256:")},
        "reading_order": reading_order,
        "passages": passages,
        "coverage": {
            "scope": "All OPF spine XHTML body text, including non-linear entries; whitespace normalized per block",
            "resources_total": len(spine_items), "resources_parsed": len(reading_order),
            "resources_omitted": 0, "parsed_details": parsed_details, "omitted_details": [],
            "complete": True, "parsing_complete": True,
            "content_complete": not content_omissions,
            "content_omissions": content_omissions, "excluded_content": excluded,
            "non_spine_resources": non_spine,
            "navigation_resources_parsed": nav_resources, "navigation_warnings": nav_warnings,
            "normalized_text_characters": sum(item["normalized_text_characters"] for item in parsed_details),
            "passage_characters": text_chars,
            "passages_total": len(passages), "max_passage_characters": max_chars,
            "text_truncated": False,
        },
    }
    # Final bounded streaming serialization checks coverage and all envelope
    # fields as well, without constructing a second full JSON string in RAM.
    final_budget = _OutputBudget()
    final_budget.add(document)
    return document


def ingest_epub(path: str | os.PathLike[str], max_chars: int = 6000) -> dict[str, Any]:
    """Return a deterministic, JSON-serializable ledger for a local EPUB.

    Safety-limit and unsupported-spine failures raise :class:`ReaderError`;
    they never return a success-shaped partial ledger. ``max_chars`` must be
    at least two. Repeated spine IDs or resolved resources are rejected to
    prevent output amplification. XML depth/node limits apply during parsing;
    archive bytes, spine entries, passages, and output text are also bounded.
    Exact known XHTML/NCX doctype markers are removed without loading a DTD;
    custom entities and all other DTD declarations are forbidden. ``coverage.complete``
    describes spine parsing. ``coverage.content_complete`` is false when
    visual/media content cannot be represented by this plain-text reader.
    """
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 2:
        raise ReaderError("max_chars must be an integer of at least 2 to avoid whitespace-only passages")
    try:
        with open(path, "rb") as source:
            digest = hashlib.sha256()
            total = 0
            while True:
                data = source.read(1024 * 1024)
                if not data:
                    break
                total += len(data)
                if total > MAX_ARCHIVE_BYTES:
                    raise ReaderError("EPUB archive exceeds size limit")
                digest.update(data)
            source.seek(0)
            with zipfile.ZipFile(source) as archive:
                return _ingest(_Archive(archive), f"sha256:{digest.hexdigest()}", max_chars)
    except ReaderError:
        raise
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, EOFError) as exc:
        raise ReaderError(f"Cannot ingest EPUB: {exc}") from exc
