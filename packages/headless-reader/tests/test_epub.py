"""Synthetic EPUB fixtures: no private books and no network dependencies."""
import hashlib
import json
import stat
import struct
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from ucc_headless import epub
from ucc_headless.epub import ReaderError, ingest_epub


CONTAINER = b'''<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0"><rootfiles><rootfile full-path="OPS/package.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'''


def xhtml(body, title="A chapter", namespace=True):
    ns = ' xmlns="http://www.w3.org/1999/xhtml"' if namespace else ""
    return f'<?xml version="1.0"?><html{ns}><head><title>{escape(title)}</title></head><body>{body}</body></html>'.encode()


def package(manifest=None, spine=None):
    manifest = manifest if manifest is not None else [
        '<item id="first" href="first.xhtml" media-type="application/xhtml+xml"/>',
        '<item id="second" href="second.xhtml" media-type="application/xhtml+xml"/>',
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
    ]
    spine = spine if spine is not None else ['<itemref idref="second"/>', '<itemref idref="first" linear="no"/>']
    return ('''<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Synthetic &amp; Safe</dc:title><dc:creator>A. Tester</dc:creator><dc:creator>B. Tester</dc:creator></metadata><manifest>'''
            + ''.join(manifest) + '</manifest><spine>' + ''.join(spine) + '</spine></package>').encode()


def make_epub(path, replacements=None, additions=None, compression=ZIP_STORED):
    entries = {
        "mimetype": b"application/epub+zip", "META-INF/container.xml": CONTAINER,
        "OPS/package.opf": package(),
        "OPS/first.xhtml": xhtml('<h1 id="first-heading">First</h1><p id="first-p">ALPHA prose.</p>'),
        "OPS/second.xhtml": xhtml('<h1 id="second-heading">Second</h1><p id="second-p">BETA prose.</p>'),
        "OPS/nav.xhtml": xhtml('<nav><p>Navigation only</p></nav>'),
    }
    entries.update(replacements or {})
    with ZipFile(path, "w", compression=compression) as archive:
        for name, content in entries.items():
            if content is not None:
                archive.writestr(name, content)
        for name, content in additions or []:
            archive.writestr(name, content)
    return path


class EpubTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.epub"

    def ingest(self, **kwargs):
        return ingest_epub(make_epub(self.path, **kwargs))

    def test_reading_order_metadata_and_actual_anchors(self):
        doc = self.ingest()
        self.assertEqual(doc["schema_version"], 1)
        self.assertEqual(doc["book"]["title"], "Synthetic & Safe")
        self.assertEqual(doc["book"]["author"], "A. Tester; B. Tester")
        self.assertEqual(doc["book"]["id"], "sha256:" + hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual([chapter["href"] for chapter in doc["reading_order"]], ["OPS/second.xhtml", "OPS/first.xhtml"])
        self.assertFalse(doc["reading_order"][1]["linear"])
        self.assertEqual([passage["text"] for passage in doc["passages"]], ["Second", "BETA prose.", "First", "ALPHA prose."])
        self.assertEqual(doc["passages"][1]["element_id"], "second-p")
        self.assertTrue(all(p["book_title"] == doc["book"]["title"] for p in doc["passages"]))
        self.assertTrue(all(p["book_author"] == doc["book"]["author"] for p in doc["passages"]))
        self.assertTrue(all(passage["cfi"] is None for passage in doc["passages"]))
        self.assertEqual([passage["ordinal"] for passage in doc["passages"]], list(range(4)))
        self.assertTrue(doc["coverage"]["complete"])
        self.assertEqual(doc["coverage"]["resources_total"], 2)
        self.assertEqual(doc["coverage"]["resources_parsed"], 2)
        self.assertEqual(doc["coverage"]["resources_omitted"], 0)
        self.assertEqual(doc["coverage"]["non_spine_resources"][0]["manifest_id"], "nav")
        json.dumps(doc)  # Entire ledger is JSON serializable.

    def test_repeat_ingestion_has_identical_ids_and_document(self):
        path = make_epub(self.path)
        self.assertEqual(ingest_epub(path), ingest_epub(path))

    def test_namespace_free_xhtml_and_unicode(self):
        doc = self.ingest(replacements={"OPS/second.xhtml": xhtml('<p>α β 中文 café &amp; tea</p>', namespace=False)})
        self.assertEqual(doc["passages"][0]["text"], "α β 中文 café & tea")
        self.assertIsNone(doc["passages"][0]["element_id"])

    def test_chunking_retains_all_normalized_characters(self):
        text = ' '.join(f"word{index}" for index in range(5000)) + ' ' + ('漢' * 401)
        make_epub(self.path, replacements={"OPS/second.xhtml": xhtml('<p id="large">' + text + '</p>')})
        doc = ingest_epub(self.path, max_chars=37)
        passages = [p for p in doc["passages"] if p["href"] == "OPS/second.xhtml"]
        self.assertGreater(len(passages), 100)
        self.assertEqual(''.join(p["text"] for p in passages), text)
        self.assertTrue(all(0 < len(p["text"]) <= 37 for p in passages))
        self.assertEqual(len({p["id"] for p in passages}), len(passages))
        self.assertEqual(doc["coverage"]["normalized_text_characters"], sum(len(p["text"]) for p in doc["passages"]))
        self.assertFalse(doc["coverage"]["text_truncated"])

    def test_smallest_supported_chunks_do_not_drop_spaces_or_emit_whitespace(self):
        make_epub(self.path, replacements={"OPS/second.xhtml": xhtml('<p>A B</p>')})
        doc = ingest_epub(self.path, max_chars=2)
        self.assertEqual(''.join(p["text"] for p in doc["passages"] if p["href"] == "OPS/second.xhtml"), 'A B')
        self.assertTrue(all(p["text"].strip() and len(p["text"]) <= 2 for p in doc["passages"]))

    def test_text_inline_tails_nested_blocks_and_breaks_appear_once(self):
        body = '<div id="parent">Before<p>Some <em id="em">inline</em> text<br/>continues.</p>Between<div>Nested</div>After</div>'
        doc = self.ingest(replacements={"OPS/second.xhtml": xhtml(body)})
        passages = [p for p in doc["passages"] if p["href"] == "OPS/second.xhtml"]
        self.assertEqual([p["text"] for p in passages], ['Before', 'Some inline text continues.', 'Between', 'Nested', 'After'])
        self.assertEqual({p["element_id"] for p in passages}, {"parent"})

    def test_sections_and_xml_ids_are_real_and_stable(self):
        body = '<h1 id="ch">Main</h1><p>Lead</p><h2 xml:id="detail">Detail</h2><p>Fact</p><h2>Next</h2><p>End</p>'
        doc = self.ingest(replacements={"OPS/second.xhtml": xhtml(body)})
        passages = [p for p in doc["passages"] if p["href"] == "OPS/second.xhtml"]
        self.assertEqual(passages[3]["section"], "Main / Detail")
        self.assertEqual(passages[2]["element_id"], "detail")
        self.assertEqual(passages[-1]["section"], "Main / Next")
        self.assertIsNone(passages[-1]["element_id"])
        self.assertIn(passages[3]["section_id"], {s["id"] for s in doc["reading_order"][0]["sections"]})

    def test_script_and_style_are_explicitly_excluded_and_tails_preserved(self):
        body = '<p>Before<script>steal()</script> after<style>.secret { display:none }</style> end</p>'
        doc = self.ingest(replacements={"OPS/second.xhtml": xhtml(body)})
        self.assertEqual(doc["passages"][0]["text"], 'Before after end')
        self.assertEqual([entry["element"] for entry in doc["coverage"]["excluded_content"]], ["script", "style"])
        self.assertTrue(doc["coverage"]["parsing_complete"])

    def test_skipped_code_cannot_supply_chapter_heading(self):
        body = '<script><h1>Fake heading in code</h1></script><h1>Actual heading</h1><p>Actual prose</p>'
        doc = self.ingest(replacements={"OPS/second.xhtml": xhtml(body)})
        self.assertEqual(doc['reading_order'][0]['title'], 'Actual heading')
        self.assertNotIn('Fake', ' '.join(p['text'] for p in doc['passages']))

    def test_head_script_is_reported_but_not_in_prose(self):
        payload = xhtml('<p>Actual prose</p>').replace(b'</head>', b'<script>head_code()</script></head>')
        doc = self.ingest(replacements={"OPS/second.xhtml": payload})
        self.assertEqual(doc['passages'][0]['text'], 'Actual prose')
        self.assertEqual(doc['coverage']['excluded_content'][0]['element'], 'script')

    def test_nontext_omissions_do_not_claim_content_completeness(self):
        body = '<p>Caption <img id="figure" src="figure.png" alt="a triangle"/></p><svg xmlns="http://www.w3.org/2000/svg"><text>SVG label</text></svg>'
        doc = self.ingest(replacements={"OPS/second.xhtml": xhtml(body)})
        self.assertTrue(doc["coverage"]["complete"])
        self.assertFalse(doc["coverage"]["content_complete"])
        self.assertEqual([o["element"] for o in doc["coverage"]["content_omissions"]], ['img', 'svg'])
        self.assertEqual(doc["passages"][0]["text"], 'Caption a triangle')
        self.assertIn('SVG label', [p["text"] for p in doc["passages"]])

    def test_mathml_flattening_is_explicitly_incomplete(self):
        body = '<math xmlns="http://www.w3.org/1998/Math/MathML"><mfrac><mi>a</mi><mi>b</mi></mfrac></math>'
        doc = self.ingest(replacements={'OPS/second.xhtml': xhtml(body)})
        self.assertEqual(doc['passages'][0]['text'], 'ab')
        self.assertTrue(doc['coverage']['parsing_complete'])
        self.assertFalse(doc['coverage']['content_complete'])
        omission = doc['coverage']['content_omissions'][0]
        self.assertEqual(omission['element'], 'math')
        self.assertIn('ambiguous', omission['reason'])

    def test_epub3_navigation_titles_and_exact_fragment_sections(self):
        nav = xhtml('<nav xmlns:epub="http://www.idpf.org/2007/ops" epub:type="toc"><ol><li><a href="second.xhtml">Useful chapter title</a><ol><li><a href="second.xhtml#real">Genuine section title</a></li><li><a href="second.xhtml#missing">Never fabricate this</a></li></ol></li></ol></nav>')
        doc = self.ingest(replacements={'OPS/nav.xhtml': nav, 'OPS/second.xhtml': xhtml('<p id="real">Source text</p>')})
        self.assertEqual(doc['reading_order'][0]['title'], 'Useful chapter title')
        self.assertEqual(doc['passages'][0]['chapter'], 'Useful chapter title')
        self.assertEqual(doc['passages'][0]['section'], 'Genuine section title')
        self.assertEqual(doc['passages'][0]['element_id'], 'real')
        self.assertEqual(doc['coverage']['navigation_warnings'][0]['element_id'], 'missing')
        self.assertNotIn('Never fabricate', ' '.join(p['section'] for p in doc['passages']))

    def test_epub2_ncx_title_and_exact_known_inert_ncx_declaration(self):
        ncx = b'<?xml version="1.0"?><!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd"><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/"><navMap><navPoint><navLabel><text>NCX chapter title</text></navLabel><content src="second.xhtml"/></navPoint></navMap></ncx>'
        items = ['<item id="second" href="second.xhtml" media-type="application/xhtml+xml"/>', '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>']
        opf = package(items, ['<itemref idref="second"/>']).replace(b'<spine>', b'<spine toc="ncx">')
        doc = self.ingest(replacements={'OPS/package.opf': opf}, additions=[('OPS/toc.ncx', ncx)])
        self.assertEqual(doc['passages'][0]['chapter'], 'NCX chapter title')
        self.assertEqual(doc['coverage']['navigation_resources_parsed'], ['OPS/toc.ncx'])
        bad_ncx = ncx.replace(b'http://www.daisy.org/z3986/2005/ncx-2005-1.dtd', b'https://evil.invalid/evil.dtd')
        with self.assertRaisesRegex(ReaderError, 'DTD'):
            self.ingest(replacements={'OPS/package.opf': opf}, additions=[('OPS/toc.ncx', bad_ncx)])

    def test_external_navigation_targets_are_not_fetched_or_used_as_labels(self):
        nav = xhtml('<nav xmlns:epub="http://www.idpf.org/2007/ops" epub:type="toc"><a href="https://evil.invalid/second.xhtml">Untrusted</a></nav>')
        doc = self.ingest(replacements={'OPS/nav.xhtml': nav})
        self.assertEqual(doc['passages'][0]['chapter'], 'Second')
        self.assertEqual(len(doc['coverage']['navigation_warnings']), 1)

    def test_image_only_spine_is_reported_as_incomplete_content(self):
        doc = self.ingest(replacements={"OPS/second.xhtml": xhtml('<img src="cover.jpg"/>')})
        self.assertEqual(doc["reading_order"][0]["passage_ids"], [])
        self.assertTrue(doc["coverage"]["parsing_complete"])
        self.assertFalse(doc["coverage"]["content_complete"])

    def test_href_parent_segments_and_percent_encoding_are_resolved_locally(self):
        opf = package(['<item id="ch" href="../Text/chapter%20one.xhtml" media-type="application/xhtml+xml"/>'], ['<itemref idref="ch"/>'])
        doc = self.ingest(replacements={"OPS/package.opf": opf}, additions=[('Text/chapter one.xhtml', xhtml('<p>Found</p>'))])
        self.assertEqual(doc["passages"][0]["href"], 'Text/chapter one.xhtml')

    def test_duplicate_spine_entries_cannot_amplify_output(self):
        with self.assertRaisesRegex(ReaderError, 'Repeated spine resource'):
            self.ingest(replacements={"OPS/package.opf": package(spine=['<itemref idref="first"/>'] * 1000)})

    def test_aliased_spine_hrefs_cannot_amplify_output(self):
        items = ['<item id="a" href="first.xhtml" media-type="application/xhtml+xml"/>', '<item id="b" href="./first.xhtml" media-type="application/xhtml+xml"/>']
        with self.assertRaisesRegex(ReaderError, 'Repeated spine resource'):
            self.ingest(replacements={"OPS/package.opf": package(items, ['<itemref idref="a"/>', '<itemref idref="b"/>'])})

    def test_spine_and_passage_output_budgets_are_enforced(self):
        make_epub(self.path)
        for constant, limit in [('MAX_SPINE_ITEMS', 1), ('MAX_PASSAGES', 3), ('MAX_OUTPUT_CHARACTERS', 10)]:
            with self.subTest(constant=constant), patch.object(epub, constant, limit), self.assertRaises(ReaderError):
                ingest_epub(self.path)

    def test_unsupported_spine_media_fails_instead_of_partial_success(self):
        opf = package(['<item id="ch" href="page.svg" media-type="image/svg+xml"/>'], ['<itemref idref="ch"/>'])
        with self.assertRaisesRegex(ReaderError, 'Unsupported spine resource'):
            self.ingest(replacements={"OPS/package.opf": opf})

    def test_missing_spine_resource_fails(self):
        with self.assertRaisesRegex(ReaderError, 'resource is missing'):
            self.ingest(replacements={"OPS/first.xhtml": None})

    def test_unknown_spine_id_and_duplicate_manifest_ids_fail(self):
        for opf in [package(spine=['<itemref idref="unknown"/>']), package(['<item id="x"/>', '<item id="x"/>'])]:
            with self.subTest(opf=opf), self.assertRaises(ReaderError):
                self.ingest(replacements={"OPS/package.opf": opf})

    def test_empty_spine_fails(self):
        with self.assertRaisesRegex(ReaderError, 'spine is empty'):
            self.ingest(replacements={"OPS/package.opf": package(spine=[])})

    def test_external_and_escaping_spine_hrefs_fail_without_fetching(self):
        for href in ['https://example.invalid/book.xhtml', '//example.invalid/ch.xhtml', '../../outside.xhtml', '/absolute.xhtml', 'file:///etc/passwd', 'first.xhtml#fragment', 'first.xhtml?query', '%2f%2fexample.invalid/x']:
            with self.subTest(href=href), self.assertRaises(ReaderError):
                self.ingest(replacements={"OPS/package.opf": package([f'<item id="x" href="{href}" media-type="application/xhtml+xml"/>'], ['<itemref idref="x"/>'])})

    def test_bad_container_mimetype_and_html_are_errors(self):
        for replacements in [{'mimetype': b'text/plain'}, {'META-INF/container.xml': b'<container/>'}, {'OPS/first.xhtml': b'<html><body><p>unclosed</body></html>'}, {'OPS/first.xhtml': b'<html/>'}, {'OPS/first.xhtml': b'<not-html><body>Text</body></not-html>'}]:
            with self.subTest(replacements=replacements), self.assertRaises(ReaderError):
                self.ingest(replacements=replacements)

    def test_xml_dtd_and_entities_rejected_in_all_document_layers(self):
        for name in ['META-INF/container.xml', 'OPS/package.opf', 'OPS/first.xhtml']:
            for payload in [b'<!DOCTYPE arbitrary><html/>', b'<!DOCTYPE x [<!ENTITY bad SYSTEM "file:///etc/passwd">]><x>&bad;</x>', '<!DOCTYPE html><html/>'.encode('utf-16')]:
                with self.subTest(name=name, payload=payload), self.assertRaisesRegex(ReaderError, 'DTD|entity'):
                    self.ingest(replacements={name: payload})

    def test_exact_known_html_doctypes_are_inert_compatibility_markers(self):
        for declaration in [b'<!DOCTYPE html>', b'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"\n "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">', b"<!DOCTYPE html PUBLIC '-//W3C//DTD XHTML 1.0 Strict//EN' 'http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd'>"]:
            payload = xhtml('<p>Still safe &amp; offline</p>').replace(b'?>', b'?>' + declaration, 1)
            with self.subTest(declaration=declaration):
                doc = self.ingest(replacements={'OPS/second.xhtml': payload})
                self.assertEqual(doc['passages'][0]['text'], 'Still safe & offline')

    def test_known_doctype_does_not_allow_entities_or_arbitrary_external_dtd(self):
        declarations = [
            b'<!DOCTYPE html SYSTEM "file:///etc/passwd">',
            b'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "https://evil.invalid/evil.dtd">',
            b'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd" [<!ENTITY x "expanded">]>',
            b'<!DOCTYPE html><!ENTITY x "expanded">',
            b'<!DOCTYPE html><!DOCTYPE html>',
        ]
        for declaration in declarations:
            payload = xhtml('<p>Text</p>').replace(b'?>', b'?>' + declaration, 1)
            with self.subTest(declaration=declaration), self.assertRaises(ReaderError):
                self.ingest(replacements={'OPS/second.xhtml': payload})
        with self.assertRaises(ReaderError):
            self.ingest(replacements={'OPS/second.xhtml': xhtml('<p>&nbsp;</p>').replace(b'?>', b'?><!DOCTYPE html>', 1)})

    def test_literal_doctype_in_cdata_is_never_silently_removed(self):
        payload = xhtml('<p><![CDATA[Use <!DOCTYPE html> before the root.]]></p>')
        # This strict reader may fail closed on declaration-like literals. It
        # must not return a complete document with words silently removed.
        with self.assertRaisesRegex(ReaderError, 'DTD'):
            self.ingest(replacements={'OPS/second.xhtml': payload})

    def test_oversized_metadata_heading_and_locator_are_rejected(self):
        giant_label = 'x' * (epub.MAX_LABEL_CHARACTERS + 1)
        giant_locator = 'x' * (epub.MAX_LOCATOR_CHARACTERS + 1)
        replacements = [
            {'OPS/package.opf': package().replace(b'Synthetic &amp; Safe', giant_label.encode())},
            {'OPS/package.opf': package().replace(b'A. Tester', giant_label.encode())},
            {'OPS/second.xhtml': xhtml('<h1>' + giant_label + '</h1>')},
            {'OPS/second.xhtml': xhtml('<p id="' + giant_locator + '">Text</p>')},
            {'OPS/second.xhtml': xhtml('<img src="' + giant_locator + '"/>')},
        ]
        for replacement in replacements:
            with self.subTest(resource=list(replacement)), self.assertRaisesRegex(ReaderError, 'length limit'):
                self.ingest(replacements=replacement)

    def test_combined_author_names_are_bounded(self):
        # Each author is under the per-label limit; the concatenated field also
        # needs a limit because it is copied into every passage.
        opf = package().replace(b'A. Tester', b'a' * 3000).replace(b'B. Tester', b'b' * 3000)
        with self.assertRaisesRegex(ReaderError, 'combined author names'):
            self.ingest(replacements={'OPS/package.opf': opf})

    def test_output_budget_counts_json_escaping_and_repetition(self):
        budget = epub._OutputBudget()
        with patch.object(epub, 'MAX_OUTPUT_CHARACTERS', 7):
            budget.add('aaa')  # Five serialized characters, including quotes.
            with self.assertRaisesRegex(ReaderError, 'serialized output'):
                budget.add('b')  # Repetition adds another three characters.
        budget = epub._OutputBudget()
        with patch.object(epub, 'MAX_OUTPUT_CHARACTERS', 3), self.assertRaises(ReaderError):
            budget.add('\\')  # Four characters once escaped and quoted.

    def test_duplicate_xml_ids_fail_instead_of_ambiguous_citations(self):
        with self.assertRaisesRegex(ReaderError, 'Duplicate XML element ID'):
            self.ingest(replacements={'OPS/first.xhtml': xhtml('<p id="dup">One</p><p id="dup">Two</p>')})

    def test_xml_element_budget_is_enforced_during_tree_construction(self):
        # Root + two children fit; the fourth start event must fail before it
        # allocates another element, without waiting for a complete document.
        builder = epub._SafeTreeBuilder('synthetic.xml')
        with patch.object(epub, 'MAX_XML_ELEMENTS', 3):
            builder.start('root', {})
            builder.start('one', {})
            builder.end('one')
            builder.start('two', {})
            builder.end('two')
            with self.assertRaisesRegex(ReaderError, 'structure exceeds'):
                builder.start('three', {})
        with patch.object(epub, 'MAX_XML_ELEMENTS', 20), self.assertRaisesRegex(ReaderError, 'structure exceeds'):
            self.ingest(replacements={'OPS/first.xhtml': xhtml('<p>text</p>' * 30)})

    def test_deep_xml_fails_safely(self):
        body = '<div>' * (epub.MAX_XML_DEPTH + 1) + 'Text' + '</div>' * (epub.MAX_XML_DEPTH + 1)
        with self.assertRaisesRegex(ReaderError, 'structure exceeds'):
            self.ingest(replacements={'OPS/first.xhtml': xhtml(body)})

    def test_zip_path_traversal_and_ambiguous_names_rejected(self):
        names = ['../escape', 'OPS/../../escape', '/absolute', 'C:/drive', 'OPS\\escape', 'OPS/%2e%2e/escape']
        for name in names:
            with self.subTest(name=name), self.assertRaises(ReaderError):
                self.ingest(additions=[(name, b'evil')])

    def test_duplicate_canonical_members_rejected(self):
        for name in ['OPS/first.xhtml', 'OPS/./first.xhtml', 'OPS//first.xhtml']:
            with self.subTest(name=name), warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                with self.assertRaisesRegex(ReaderError, 'Duplicate canonical'):
                    self.ingest(additions=[(name, xhtml('<p>collision</p>'))])

    def test_unicode_equivalent_zip_names_are_duplicate_canonical_names(self):
        with self.assertRaisesRegex(ReaderError, 'Duplicate canonical'):
            self.ingest(additions=[('caf\u00e9.txt', b'one'), ('cafe\u0301.txt', b'two')])

    def test_zip_nul_in_original_filename_is_rejected(self):
        make_epub(self.path, additions=[('bad!name.txt', b'evil')])
        self.path.write_bytes(self.path.read_bytes().replace(b'bad!name.txt', b'bad\x00name.txt'))
        with self.assertRaisesRegex(ReaderError, 'Unsafe ZIP member'):
            ingest_epub(self.path)

    def test_zip_symlink_is_rejected_even_if_not_in_spine(self):
        info = ZipInfo('dangerous-link')
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaisesRegex(ReaderError, 'symlinks'):
            self.ingest(additions=[(info, b'/etc/passwd')])

    def test_zip_encryption_flag_rejected(self):
        make_epub(self.path)
        data = bytearray(self.path.read_bytes())
        for signature, flag_offset in [(b'PK\x03\x04', 6), (b'PK\x01\x02', 8)]:
            location = data.index(signature)
            flags = struct.unpack_from('<H', data, location + flag_offset)[0]
            struct.pack_into('<H', data, location + flag_offset, flags | 1)
        self.path.write_bytes(data)
        with self.assertRaisesRegex(ReaderError, 'Encrypted'):
            ingest_epub(self.path)

    def test_zip_compression_bomb_rejected(self):
        with self.assertRaisesRegex(ReaderError, 'compression ratio'):
            self.ingest(additions=[('bomb.txt', b'0' * 100_000)], compression=ZIP_DEFLATED)

    def test_zip_size_and_member_limits(self):
        make_epub(self.path)
        for constant, value in [('MAX_ARCHIVE_BYTES', 10), ('MAX_MEMBER_BYTES', 30), ('MAX_TOTAL_UNCOMPRESSED_BYTES', 100), ('MAX_MEMBERS', 2)]:
            with self.subTest(limit=constant), patch.object(epub, constant, value), self.assertRaises(ReaderError):
                ingest_epub(self.path)

    def test_corrupted_crc_does_not_produce_partial_document(self):
        make_epub(self.path)
        self.path.write_bytes(self.path.read_bytes().replace(b'ALPHA prose.', b'BLPHA prose.'))
        with self.assertRaisesRegex(ReaderError, 'CRC'):
            ingest_epub(self.path)

    def test_invalid_max_chars_rejected(self):
        make_epub(self.path)
        for value in [0, 1, -1, 1.2, True, '20', None]:
            with self.subTest(value=value), self.assertRaisesRegex(ReaderError, 'integer of at least 2'):
                ingest_epub(self.path, value)

    def test_missing_and_nonzip_files_wrapped_as_reader_errors(self):
        with self.assertRaises(ReaderError):
            ingest_epub(self.path)
        self.path.write_bytes(b'not an EPUB')
        with self.assertRaises(ReaderError):
            ingest_epub(self.path)


if __name__ == '__main__':
    unittest.main()
