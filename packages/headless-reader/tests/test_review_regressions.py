"""Independent review regressions, using synthetic data only.

Host-model envelopes below are deliberately constructed test attestations. They
exercise validation branches and do not claim any actual model invocation.
"""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZIP_STORED, ZipFile

from ucc_headless.epub import ReaderError, ingest_epub
from ucc_headless.workflow import (
    ContractError, analysis_jobs, coverage, derived_job, digest,
    image_job, import_result, verify_job,
)


def make_epub(path, body='<p id="a">A synthetic statement.</p><p id="b">A second statement.</p>'):
    with ZipFile(path, 'w', compression=ZIP_STORED) as archive:
        archive.writestr('mimetype', 'application/epub+zip')
        archive.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="book.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        archive.writestr('book.opf', '<package><metadata><title>Synthetic review book</title></metadata><manifest><item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="chapter"/></spine></package>')
        archive.writestr('chapter.xhtml', '<html><body>' + body + '</body></html>')
    return path


def response(job, result, mode='test-fixture'):
    return {'job_id': job['id'], 'result': result, 'receipt': {
        'executor': 'independent-regression-test', 'model': 'synthetic',
        'execution_id': 'synthetic-regression', 'completed_at': '2026-10-09T12:00:00Z',
        'status': 'completed', 'mode': mode, 'job_hash': job['id'][4:],
        'result_hash': digest(result),
    }}


def result_for(job):
    return {'claims': [{'text': 'Synthetic source statement.',
        'source_ids': [p['id'] for p in job['sources']], 'kind': 'source',
        'uncertainty': ''}], 'disagreements': [], 'uncertainties': []}


class IndependentReviewRegressions(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'synthetic.epub'
        self.ledger = ingest_epub(make_epub(self.path))
        self.job = analysis_jobs(self.ledger)[0]

    def test_prompt_allowed_empty_uncertainty_imports(self):
        result = result_for(self.job)
        record = import_result(self.job, response(self.job, result))
        self.assertEqual(record['result']['claims'][0]['uncertainty'], '')
        self.assertEqual(coverage(self.ledger, [record])['analysed_passages'], 0)

    def test_receipt_rejects_unrequested_credential_fields(self):
        envelope = response(self.job, result_for(self.job))
        envelope['receipt']['api_key'] = 'synthetic-not-a-real-key'
        with self.assertRaisesRegex(ContractError, 'Unexpected receipt fields'):
            import_result(self.job, envelope)

    def test_nested_extra_metadata_is_rejected(self):
        result = result_for(self.job)
        result['claims'][0]['invented_source'] = {'href': 'https://example.invalid/fake'}
        with self.assertRaisesRegex(ContractError, 'unexpected fields'):
            import_result(self.job, response(self.job, result))

    def test_receipt_calendar_instant_is_validated(self):
        for instant in ['2026-99-99T99:99:99Z', '2026-02-30T00:00:00Z', '2026-10-09T12:00:00+99:00', '2026-10-09T12:00:00+00:99']:
            with self.subTest(instant=instant):
                envelope = response(self.job, result_for(self.job))
                envelope['receipt']['completed_at'] = instant
                with self.assertRaises(ContractError):
                    import_result(self.job, envelope)

    def test_partial_batch_expansion_is_explicit_and_hashed(self):
        self.assertEqual(len(self.job['sources']), 2)
        record = import_result(self.job, response(self.job, result_for(self.job), 'host-model'))
        requested = [self.job['sources'][0]['id']]
        derived = derived_job('outline', [self.ledger], [record], source_ids=requested)
        self.assertEqual(derived['scope']['requested_source_ids'], requested)
        self.assertTrue(derived['scope']['expanded_to_preserve_analysis_batches'])
        self.assertEqual(derived['scope']['selected_passages'], 2)
        verify_job(derived)
        derived['scope']['requested_source_ids'] = []
        with self.assertRaisesRegex(ContractError, 'hash mismatch'):
            verify_job(derived)

    def test_imported_outline_is_usable_by_image_prompt(self):
        record = import_result(self.job, response(self.job, result_for(self.job), 'host-model'))
        job = derived_job('outline', [self.ledger], [record])
        shape = {'meta': {'title': 'Test', 'layout': 'one_page_portrait', 'paper': 'blank'},
            'sections': [{'id': 's1', 'heading': 'Evidence', 'bullets': [
                {'text': 'A concise claim', 'source_ids': [self.job['sources'][0]['id']]}]}]}
        imported = import_result(job, response(job, shape, 'host-model'))
        self.assertEqual(image_job(imported)['outline_job_id'], job['id'])
        for invalid in ('length', 'sections'):
            bad = copy.deepcopy(shape)
            if invalid == 'length':
                bad['sections'][0]['bullets'][0]['text'] = 'x' * 120
            else:
                bad['sections'] = [{**copy.deepcopy(shape['sections'][0]), 'id': f's{i}'} for i in range(9)]
            with self.subTest(invalid=invalid), self.assertRaises(ContractError):
                import_result(job, response(job, bad, 'host-model'))

    def test_minimum_chunk_size_never_produces_an_unusable_ledger(self):
        make_epub(self.path, '<p>A B</p>')
        try:
            ledger = ingest_epub(self.path, max_chars=1)
        except ReaderError as error:
            self.assertIn('max_chars', str(error))
            return
        self.assertEqual(''.join(p['text'] for p in ledger['passages']), 'A B')
        jobs = analysis_jobs(ledger)
        self.assertEqual(''.join(p['text'] for job in jobs for p in job['sources']), 'A B')

    def test_mathml_structural_loss_is_reported(self):
        body = '<math xmlns="http://www.w3.org/1998/Math/MathML"><mfrac><mi>a</mi><mi>b</mi></mfrac></math>'
        ledger = ingest_epub(make_epub(self.path, body))
        self.assertFalse(ledger['coverage']['content_complete'])
        self.assertTrue(any(item['element'] == 'math' for item in ledger['coverage']['content_omissions']))

    def test_literal_doctype_in_cdata_is_never_silently_removed(self):
        text = 'Use <!DOCTYPE html> before the root.'
        make_epub(self.path, '<p><![CDATA[' + text + ']]></p>')
        try:
            ledger = ingest_epub(self.path)
        except ReaderError:
            # A conservative unsupported-markup rejection is preferable to
            # success-shaped output with altered source text.
            return
        self.assertEqual(ledger['passages'][0]['text'], text)

    def test_external_media_never_trigger_network_or_code_execution(self):
        body = '<p>Text<img src="https://example.invalid/image.png" alt="image"/></p><script>raise RuntimeError("do not execute")</script>'
        make_epub(self.path, body)
        with patch('socket.socket', side_effect=AssertionError('Network attempted')), \
             patch('subprocess.Popen', side_effect=AssertionError('Process execution attempted')):
            ledger = ingest_epub(self.path)
            jobs = analysis_jobs(ledger)
        self.assertEqual(len(jobs), 1)
        self.assertFalse(ledger['coverage']['content_complete'])
        self.assertNotIn('raise RuntimeError', jobs[0]['sources'][0]['text'])


if __name__ == '__main__':
    unittest.main()
