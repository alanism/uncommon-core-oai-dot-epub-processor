"""CLI pipeline over synthetic EPUBs; model content is an explicit fixture."""
import json
import tempfile
import unittest
from pathlib import Path
from test_epub import make_epub
from test_workflow import response, claims
from ucc_headless.__main__ import main


class IntegrationTests(unittest.TestCase):
    def test_epub_to_jobs_import_coverage_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            epub = make_epub(root / "book.epub")
            ledger, jobs = root / "ledger.json", root / "jobs.json"
            self.assertEqual(main(["ingest", str(epub), str(ledger)]), 0)
            self.assertEqual(main(["jobs", str(ledger), str(jobs)]), 0)
            job_data = json.loads(jobs.read_text())
            records = []
            for index, job in enumerate(job_data):
                job_file, response_file, record_file = [root / (name + str(index) + ".json") for name in ("job", "response", "record")]
                job_file.write_text(json.dumps(job))
                response_file.write_text(json.dumps(response(job, claims(job["sources"][0]["id"]))))
                self.assertEqual(main(["import", str(job_file), str(response_file), str(record_file)]), 0)
                records.append(json.loads(record_file.read_text()))
            record_list = root / "records.json"; record_list.write_text(json.dumps(records))
            cov, md = root / "coverage.json", root / "ledger.md"
            self.assertEqual(main(["coverage", str(ledger), str(record_list), str(cov)]), 0)
            self.assertFalse(json.loads(cov.read_text())["complete"])
            self.assertEqual(json.loads(cov.read_text())["fixture_passages"], 4)
            self.assertEqual(main(["markdown", str(ledger), str(record_list), str(md)]), 0)
            self.assertIn("TEST FIXTURE", md.read_text())
            self.assertIn("BETA prose", md.read_text())

    def test_empty_claims_are_an_explicit_insufficient_evidence_result(self):
        from ucc_headless.workflow import analysis_jobs, import_result, ContractError
        from test_workflow import ledger
        job = analysis_jobs(ledger())[0]
        result = {"claims": [], "disagreements": [], "uncertainties": ["Passage has no analyzable assertion"]}
        self.assertEqual(import_result(job, response(job, result))["result"], result)
        result["uncertainties"] = []
        with self.assertRaises(ContractError): import_result(job, response(job, result))

    def test_batching_keeps_all_sources_and_refuses_oversized_passages(self):
        from ucc_headless.workflow import analysis_jobs, ContractError
        from test_workflow import ledger
        book = ledger(); book["passages"].append({**book["passages"][0], "id": "a:2"})
        self.assertEqual(len(analysis_jobs(book)), 1)
        self.assertEqual(len(analysis_jobs(book)[0]["sources"]), 2)
        with self.assertRaises(ContractError): analysis_jobs(book, max_input_chars=2)

    def test_image_aliases_are_deterministic_reversible_and_do_not_mutate(self):
        import copy
        from ucc_headless.prompts import image_source_aliases, image_prompt
        shape = {"meta": {"title": "Evidence", "layout": "one_page_portrait", "paper": "blank"}, "sections": [{"id": "one", "heading": "Observe", "bullets": [{"text": "Compare", "source_ids": ["z", "a"]}, {"text": "Again", "source_ids": ["a"]}]}]}
        before = copy.deepcopy(shape)
        self.assertEqual(image_source_aliases(shape), {"S1": "a", "S2": "z"})
        prompt = image_prompt(shape)
        self.assertIn('"citation_labels"', prompt)
        self.assertIn('"S1": "a"', prompt)
        self.assertEqual(shape, before)

    def test_model_preference_is_configurable_and_hashed(self):
        from ucc_headless.workflow import analysis_jobs
        from test_workflow import ledger
        fast = analysis_jobs(ledger())[0]
        alternate = analysis_jobs(ledger(), model_preference="User-selected fast model")[0]
        self.assertNotEqual(fast["id"], alternate["id"])
        self.assertEqual(alternate["processing_preference"]["model_label"], "User-selected fast model")
        self.assertFalse(alternate["processing_preference"]["allow_heavier_fallback"])
