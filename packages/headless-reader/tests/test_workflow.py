import copy
import json
import tempfile
import unittest
from pathlib import Path
from ucc_headless.workflow import *


def ledger(book="a"):
    return {"schema_version": 1, "book": {"id": "sha256:"+book, "title": "Synthetic "+book}, "coverage": {"complete": True}, "passages": [{"id": book+":1", "book_id": "sha256:"+book, "chapter": "Chapter", "section": "Section", "href": "chapter.xhtml", "element_id": "p1", "cfi": None, "text": "Observe past actions rather than promises.", "ordinal": 0}]}


def claims(source):
    return {"claims": [{"text": "Actions provide evidence.", "source_ids": [source], "kind": "interpretation", "uncertainty": "Limited to supplied passage"}], "disagreements": [], "uncertainties": ["One passage only"]}


def response(job, result, mode="test-fixture"):
    return {"job_id": job["id"], "result": result, "receipt": {"executor": "unit-test", "model": "synthetic-fixture", "execution_id": "test-001", "completed_at": "2026-10-09T00:00:00Z", "status": "completed", "mode": mode, "job_hash": job["id"][4:], "result_hash": digest(result)}}


class WorkflowTests(unittest.TestCase):
    def test_determinism_and_preference(self):
        jobs = analysis_jobs(ledger())
        self.assertEqual(jobs, analysis_jobs(ledger()))
        self.assertEqual(jobs[0]["processing_preference"]["model_label"], "Luna")
        self.assertFalse(jobs[0]["processing_preference"]["allow_heavier_fallback"])
        self.assertIn("Observe", canonical(jobs[0]))

    def test_tamper_rejected(self):
        job = analysis_jobs(ledger())[0]
        response_value = response(job, claims("a:1"))
        altered = copy.deepcopy(job); altered["sources"][0]["text"] = "changed"
        with self.assertRaises(ContractError): import_result(altered, response_value)
        response_value["result"]["claims"][0]["text"] = "changed"
        with self.assertRaises(ContractError): import_result(job, response_value)

    def test_unknown_citation_and_incomplete_receipts(self):
        job = analysis_jobs(ledger())[0]
        with self.assertRaises(ContractError): import_result(job, response(job, claims("invented")))
        value = response(job, claims("a:1")); value["receipt"]["status"] = "running"
        with self.assertRaises(ContractError): import_result(job, value)
        value = response(job, claims("a:1")); del value["receipt"]["model"]
        with self.assertRaises(ContractError): import_result(job, value)

    def test_fixture_never_complete(self):
        book = ledger(); job = analysis_jobs(book)[0]
        record = import_result(job, response(job, claims("a:1")))
        report = coverage(book, [record])
        self.assertFalse(report["complete"]); self.assertEqual(report["fixture_passages"], 1)
        with self.assertRaises(ContractError): derived_job("outline", [book], [record])
        self.assertIn("TEST FIXTURE", markdown(book, [record]))

    def test_analysis_does_not_claim_uncovered_sources(self):
        book = ledger(); book["passages"].append({**book["passages"][0], "id": "a:2"})
        job = analysis_jobs(book, max_input_chars=len(book["passages"][0]["text"]))[0]
        record = import_result(job, response(job, claims("a:1"), "host-model"))
        self.assertEqual(coverage(book, [record])["missing_source_ids"], ["a:2"])
        with self.assertRaises(ContractError): derived_job("outline", [book], [record])
        partial = derived_job("outline", [book], [record], source_ids=["a:1"])
        self.assertEqual(partial["scope"]["available_passages"], 2)
        self.assertEqual(partial["scope"]["selected_passages"], 1)

    def test_crossbook_and_image_contract(self):
        books = [ledger("a"), ledger("b")]
        records = []
        for book in books:
            job = analysis_jobs(book)[0]
            # Deliberate host-attestation test input; no real model call is claimed.
            records.append(import_result(job, response(job, claims(book["passages"][0]["id"]), "host-model")))
        synthesis = derived_job("synthesis", books, records, question="Compare evidence")
        result = claims("a:1"); result["claims"][0]["source_ids"].append("b:1")
        result["key_message"] = {"text": "Compare evidence", "source_ids": ["a:1", "b:1"]}
        result["disagreements"] = [{"text": "Different contexts remain", "source_ids": ["a:1", "b:1"]}]
        record = import_result(synthesis, response(synthesis, result))
        self.assertEqual(len(record["result"]["disagreements"]), 1)
        outline = derived_job("outline", books, records)
        shape = {"meta": {"title": "Evidence", "layout": "one_page_portrait", "paper": "blank"}, "sections": [{"id": "s1", "heading": "Observe", "bullets": [{"text": "Past actions", "source_ids": ["a:1", "b:1"]}]}]}
        image = image_job(import_result(outline, response(outline, shape, "host-model")))
        self.assertFalse(image["host_tool_contract"]["execute_automatically"])
        self.assertEqual(image["outline_job_id"], outline["id"])
        artifact = {"artifact_ref": "host-artifact:example", "mime_type": "image/png", "sha256": "0"*64}
        image_record = import_result(image, response(image, artifact, "host-image"))
        self.assertEqual(image_record["receipt_verification"], "host-attestation-only")
        revision = image_revision_job(image_record, "Correct the illegible label, preserve all meaning.")
        self.assertEqual(revision["input_artifact"]["sha256"], "0"*64)
        self.assertEqual(revision["previous_image_job_id"], image["id"])
        self.assertEqual(revision["source_aliases"], image["source_aliases"])
        verify_job(revision)

    def test_foreign_sources_and_duplicate_records(self):
        book = ledger(); job = analysis_jobs(book)[0]
        record = import_result(job, response(job, claims("a:1")))
        with self.assertRaises(ContractError): coverage(book, [record, record])
        foreign = copy.deepcopy(book); foreign["passages"][0]["text"] = "different"
        with self.assertRaises(ContractError): coverage(foreign, [record])

    def test_cli_refuses_overwrite(self):
        from ucc_headless.__main__ import write
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"out.json"
            write(output, {"a": 1})
            with self.assertRaises(FileExistsError): write(output, {"b": 2})
            self.assertEqual(json.loads(output.read_text()), {"a": 1})


if __name__ == "__main__": unittest.main()
