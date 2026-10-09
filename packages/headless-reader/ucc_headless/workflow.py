"""Deterministic jobs; explicit, validated host result imports. No network or auth."""
from __future__ import annotations
import copy
from datetime import datetime
import hashlib
import json
import re
from . import prompts


class ContractError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ContractError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def config(value=None):
    result = {"lens": "philosopher", "focus": "Expert", "depth": "MBA"}
    if value:
        require(isinstance(value, dict) and set(value) <= set(result), "Unknown configuration fields")
        result.update(value)
    require(all(nonempty(v) and len(v) <= 100 for v in result.values()), "Invalid configuration")
    return result


def validate_ledger(ledger):
    require(isinstance(ledger, dict) and ledger.get("schema_version") == 1, "Unsupported ledger")
    require(isinstance(ledger.get("passages"), list) and ledger["passages"], "Ledger has no passages")
    seen = set()
    for p in ledger["passages"]:
        require(isinstance(p, dict), "Invalid passage")
        require(nonempty(p.get("id")) and p["id"] not in seen, "Duplicate or missing passage ID")
        require(nonempty(p.get("text")) and p.get("book_id") == ledger.get("book", {}).get("id"), "Invalid passage provenance")
        require(p.get("cfi") is None, "EPUB ingestion never fabricates CFIs; external selections need a separate verified adapter")
        seen.add(p["id"])
    return ledger


def make_job(kind, passages, analyses, configuration, question=None, model_preference="Luna"):
    require(nonempty(model_preference) and len(model_preference) <= 100, "Invalid model preference")
    require(kind in {"analysis", "outline", "synthesis", "image"}, "Unknown job kind")
    body = {"schema_version": 1, "kind": kind, "execution_mode": "host-oai-dot",
            "config": configuration, "sources": passages, "analyses": analyses,
            "processing_preference": {"model_label": "host-image-tool" if kind == "image" else model_preference, "cost_tier": "host-image-limits" if kind == "image" else "fast-low-cost", "api_model_id": None, "allow_heavier_fallback": False},
            "security": {"source_is_untrusted": True, "network_allowed": False,
                         "tools_allowed": [], "credentials_requested": False}}
    if kind == "analysis":
        body["prompt"] = prompts.analysis_prompt(passages, configuration)
    elif kind == "outline":
        body["prompt"] = prompts.outline_prompt(passages, analyses, configuration)
    elif kind == "synthesis":
        require(nonempty(question), "Synthesis question is required")
        body["question"] = question
        body["prompt"] = prompts.synthesis_prompt(passages, analyses, question)
    body["id"] = "job:" + digest(body)
    return body


def verify_job(job):
    require(isinstance(job, dict), "Invalid job")
    body = {k: v for k, v in job.items() if k != "id"}
    require(job.get("id") == "job:" + digest(body), "Job content hash mismatch")
    require(job.get("kind") in {"analysis", "outline", "synthesis", "image"}, "Unknown job kind")
    return job


def analysis_jobs(ledger, configuration=None, max_input_chars=6000, model_preference="Luna"):
    validate_ledger(ledger)
    require(isinstance(max_input_chars, int) and not isinstance(max_input_chars, bool) and max_input_chars > 0, "max_input_chars must be positive")
    cfg = config(configuration)
    jobs, batch, chars, chapter = [], [], 0, None
    for passage in ledger["passages"]:
        size = len(passage["text"])
        require(size <= max_input_chars, "Passage exceeds job budget; re-ingest with smaller --max-chars, never truncate")
        current = passage.get("chapter_id", passage["chapter"])
        if batch and (chars + size > max_input_chars or current != chapter):
            jobs.append(make_job("analysis", batch, [], cfg, model_preference=model_preference))
            batch, chars = [], 0
        batch.append(passage)
        chars += size
        chapter = current
    if batch: jobs.append(make_job("analysis", batch, [], cfg, model_preference=model_preference))
    return jobs


def citations(value, allowed):
    require(isinstance(value, list) and value and all(nonempty(v) for v in value), "Citations required")
    require(len(value) == len(set(value)) and set(value) <= allowed, "Unknown or duplicate source citation")


def validate_schema(value, schema, path="result"):
    """Validate the deliberately small JSON Schema subset emitted by prompts."""
    kind = schema["type"]
    expected = {"object": dict, "array": list, "string": str}
    require(isinstance(value, expected[kind]), path + " has wrong type")
    if "enum" in schema:
        require(value in schema["enum"], path + " has unsupported value")
    if kind == "object":
        properties = schema.get("properties", {})
        require(set(schema.get("required", [])) <= set(value), path + " has missing fields")
        if schema.get("additionalProperties") is False:
            require(set(value) <= set(properties), path + " has unexpected fields")
        for key, child in value.items():
            if key in properties: validate_schema(child, properties[key], path + "." + key)
    elif kind == "array":
        require(len(value) >= schema.get("minItems", 0) and len(value) <= schema.get("maxItems", 1000000), path + " has invalid length")
        if schema.get("uniqueItems"):
            require(len({canonical(item) for item in value}) == len(value), path + " has duplicate items")
        for index, child in enumerate(value): validate_schema(child, schema["items"], path + "[" + str(index) + "]")
    else:
        require(len(value) >= schema.get("minLength", 0) and len(value) <= schema.get("maxLength", 1000000), path + " has invalid string length")


def validate_claims(result, allowed):
    require(isinstance(result, dict), "Result must be an object")
    require(isinstance(result.get("claims"), list), "Claims array required")
    for claim in result["claims"]:
        require(isinstance(claim, dict) and nonempty(claim.get("text")), "Claim text required")
        citations(claim.get("source_ids"), allowed)
        require(claim.get("kind") in {"source", "interpretation", "application"}, "Claim kind required")
        require(isinstance(claim.get("uncertainty"), str), "Explicit uncertainty field required for every claim")
    require(bool(result["claims"]) or bool(result.get("uncertainties")), "Empty claims require an explicit uncertainty explaining insufficient evidence")
    require(isinstance(result.get("disagreements"), list), "Explicit disagreements array required")
    for item in result["disagreements"]:
        require(isinstance(item, dict) and nonempty(item.get("text")), "Invalid disagreement")
        citations(item.get("source_ids"), allowed)
    require(isinstance(result.get("uncertainties"), list) and all(nonempty(x) for x in result["uncertainties"]), "Explicit uncertainties array required")


def validate_outline(result, allowed):
    require(isinstance(result, dict), "Invalid outline")
    meta = result.get("meta", {})
    require(isinstance(meta, dict) and nonempty(meta.get("title")) and meta.get("layout") == "one_page_portrait" and meta.get("paper") == "blank", "Invalid outline metadata")
    sections = result.get("sections")
    require(isinstance(sections, list) and 1 <= len(sections) <= 8, "Outline needs 1–8 sections")
    ids = set()
    for section in sections:
        require(isinstance(section, dict) and nonempty(section.get("id")) and section["id"] not in ids and nonempty(section.get("heading")), "Invalid outline section")
        ids.add(section["id"])
        require(isinstance(section.get("bullets"), list) and section["bullets"], "Outline bullets required")
        for bullet in section["bullets"]:
            require(isinstance(bullet, dict) and nonempty(bullet.get("text")), "Invalid outline bullet")
            citations(bullet.get("source_ids"), allowed)


def import_result(job, envelope):
    """Validate provenance and host attestation, not truth or cryptographic host identity."""
    verify_job(job)
    require(isinstance(envelope, dict) and envelope.get("job_id") == job["id"], "Wrong result job")
    result = envelope.get("result")
    receipt = envelope.get("receipt")
    require(isinstance(receipt, dict), "Execution receipt required")
    require(set(receipt) <= {"executor", "model", "execution_id", "completed_at", "status", "mode", "job_hash", "result_hash"}, "Unexpected receipt fields; never include credentials or private auth material")
    for field in ("executor", "model", "execution_id", "completed_at"):
        require(nonempty(receipt.get(field)), "Receipt missing " + field)
    require(receipt.get("status") == "completed", "Only completed host executions can be imported")
    require(receipt.get("mode") in {"host-model", "host-image", "test-fixture"}, "Unsupported execution mode")
    require(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)", receipt["completed_at"]) is not None, "Receipt timestamp must be ISO 8601 with timezone")
    try:
        datetime.fromisoformat(receipt["completed_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("Receipt timestamp is not a valid calendar instant") from exc
    require(receipt.get("job_hash") == job["id"][4:], "Receipt job hash mismatch")
    require(receipt.get("result_hash") == digest(result), "Receipt result hash mismatch")
    allowed = {p["id"] for p in job["sources"]}
    if job["kind"] in {"analysis", "outline", "synthesis"}:
        validate_schema(result, {"analysis": prompts.ANALYSIS_SCHEMA, "outline": prompts.OUTLINE_SCHEMA, "synthesis": prompts.SYNTHESIS_SCHEMA}[job["kind"]])
    if job["kind"] in {"analysis", "synthesis"}:
        require(receipt["mode"] != "host-image", "Wrong execution mode")
        validate_claims(result, allowed)
        if job["kind"] == "synthesis":
            require(isinstance(result.get("key_message"), dict) and nonempty(result["key_message"].get("text")), "Synthesis key_message required")
            citations(result["key_message"].get("source_ids"), allowed)
    elif job["kind"] == "outline":
        require(receipt["mode"] != "host-image", "Wrong execution mode")
        validate_outline(result, allowed)
    else:
        require(receipt["mode"] in {"host-image", "test-fixture"}, "Image needs a host-image receipt")
        require(isinstance(result, dict) and nonempty(result.get("artifact_ref")), "Image artifact reference required")
        require(result.get("mime_type") in {"image/png", "image/jpeg", "image/webp"}, "Unsupported image MIME")
        require(re.fullmatch(r"[a-f0-9]{64}", result.get("sha256", "")) is not None, "Image byte checksum required")
    # Unknown response fields could carry invented source metadata or unexpected payloads.
    fields = {"claims", "disagreements", "uncertainties"}
    if job["kind"] == "synthesis": fields.add("key_message")
    if job["kind"] == "outline": fields = {"meta", "sections"}
    if job["kind"] == "image": fields = {"artifact_ref", "mime_type", "sha256"}
    require(set(result) == fields, "Unexpected result fields")
    return {"schema_version": 1, "job": copy.deepcopy(job), "result": copy.deepcopy(result),
            "receipt": copy.deepcopy(receipt), "receipt_verification": "host-attestation-only",
            "is_test_fixture": receipt["mode"] == "test-fixture"}


def verified_records(records):
    require(isinstance(records, list), "Records must be a list")
    checked = []
    seen = set()
    for record in records:
        require(isinstance(record, dict), "Invalid record")
        validated = import_result(record.get("job"), {"job_id": record.get("job", {}).get("id"), "result": record.get("result"), "receipt": record.get("receipt")})
        require(validated["job"]["id"] not in seen, "Duplicate result job")
        seen.add(validated["job"]["id"])
        checked.append(validated)
    return checked


def coverage(ledger, records):
    validate_ledger(ledger)
    source_map = {p["id"]: p for p in ledger["passages"]}
    expected = set(source_map)
    done, fixtures = set(), set()
    for record in verified_records(records):
        if record["job"]["kind"] != "analysis": continue
        for source in record["job"]["sources"]:
            if source["id"] in expected:
                actual = source_map[source["id"]]
                require(source == actual, "Analysis source differs from ledger")
                (fixtures if record["is_test_fixture"] else done).add(source["id"])
    return {"total_passages": len(expected), "analysed_passages": len(done),
            "fixture_passages": len(fixtures), "missing_source_ids": sorted(expected - done),
            "complete": expected == done and bool(ledger.get("coverage", {}).get("complete")),
            "ingestion": ledger.get("coverage", {})}


def derived_job(kind, ledgers, records, configuration=None, question=None, source_ids=None, model_preference="Luna"):
    require(kind in {"outline", "synthesis"}, "Expected outline or synthesis")
    passages = []
    for ledger in ledgers:
        validate_ledger(ledger)
        passages.extend(ledger["passages"])
    require(len({p["id"] for p in passages}) == len(passages), "Duplicate book/passage input")
    all_sources = {p["id"]: p for p in passages}
    checked_records = verified_records(records)
    requested = list(source_ids) if source_ids is not None else list(all_sources)
    if source_ids is not None:
        require(isinstance(source_ids, list) and source_ids and all(isinstance(x, str) for x in source_ids) and set(source_ids) <= set(all_sources), "Unknown selected sources")
        # A batched analysis may reason across all its passages. Expand selection
        # to whole overlapping batches instead of dropping evidence or citations.
        selected = set(source_ids)
        changed = True
        while changed:
            before = len(selected)
            for record in checked_records:
                if record["job"]["kind"] != "analysis": continue
                ids = {p["id"] for p in record["job"]["sources"]}
                if ids & selected:
                    require(ids <= set(all_sources), "Selected analysis batch depends on a ledger not supplied")
                    selected.update(ids)
            changed = len(selected) != before
        passages = [p for p in passages if p["id"] in selected]
    allowed = {p["id"]: p for p in passages}
    analyses = []
    covered = set()
    for record in checked_records:
        if record["job"]["kind"] != "analysis": continue
        require(not record["is_test_fixture"], "Test fixture analyses cannot feed production derived jobs")
        sources = record["job"]["sources"]
        if all(p["id"] in allowed for p in sources):
            require(all(p == allowed[p["id"]] for p in sources), "Mismatched analysis source")
            analyses.append({"job_id": record["job"]["id"], "result": record["result"], "receipt": record["receipt"]})
            covered.update(p["id"] for p in sources)
    require(set(allowed) == covered, "Every selected passage needs imported analysis before outline/synthesis")
    job = make_job(kind, passages, analyses, config(configuration), question, model_preference=model_preference)
    # Explicit selection scope is included before final hash; never suggests whole-book completion.
    job.pop("id")
    job["scope"] = {"selected_passages": len(passages), "available_passages": sum(len(x["passages"]) for x in ledgers), "selected_source_ids": [p["id"] for p in passages], "requested_source_ids": requested, "expanded_to_preserve_analysis_batches": set(requested) != set(allowed)}
    job["id"] = "job:" + digest(job)
    return job


def image_job(outline_record):
    record = verified_records([outline_record])[0]
    require(record["job"]["kind"] == "outline" and not record["is_test_fixture"], "A completed production outline is required")
    job = make_job("image", record["job"]["sources"], [], record["job"]["config"])
    job.pop("id")
    job["outline"] = record["result"]
    job["outline_job_id"] = record["job"]["id"]
    job["source_aliases"] = prompts.image_source_aliases(record["result"])
    job["prompt"] = prompts.image_prompt(record["result"])
    job["host_tool_contract"] = {"tool": "image-generation", "availability": "host-dependent", "billing": "host limits; never fallback to paid API", "execute_automatically": False}
    job["id"] = "job:" + digest(job)
    return job


def image_revision_job(image_record, edit_prompt):
    """Record a host image correction without hiding the original generation."""
    record = verified_records([image_record])[0]
    require(record["job"]["kind"] == "image" and not record["is_test_fixture"], "A completed production image is required")
    require(nonempty(edit_prompt), "Exact image edit prompt is required")
    job = copy.deepcopy(record["job"])
    job.pop("id")
    job["previous_image_job_id"] = record["job"]["id"]
    job["input_artifact"] = copy.deepcopy(record["result"])
    job["prompt"] = edit_prompt
    job["id"] = "job:" + digest(job)
    return job


def markdown(ledger, records):
    cov = coverage(ledger, records)
    # Escape raw HTML and markdown links in untrusted text; this is a data report.
    def safe(value):
        return str(value).replace("\\", "\\\\").replace("`", "\\`").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("[", "\\[").replace("]", "\\]")
    lines = ["# " + safe(ledger["book"]["title"]) + " — Headless Knowledge Ledger", "",
             "Book hash: " + ledger["book"]["id"], "",
             f"Analysis coverage: {cov['analysed_passages']}/{cov['total_passages']} passages. Complete: {cov['complete']}",
             "Imported receipts are host attestations, not cryptographic verification.", ""]
    for p in ledger["passages"]:
        lines += ["## " + safe(p["chapter"]), "", "Source ID: " + p["id"], "Location: " + safe(p["href"]),
                  "Section: " + safe(p["section"]), "Element ID: " + safe(p.get("element_id") or "unavailable"),
                  "CFI: " + safe(p.get("cfi") or "unavailable (not fabricated)"), "", safe(p["text"]), ""]
    ledger_ids = {p["id"] for p in ledger["passages"]}
    for record in verified_records(records):
        if record["job"]["kind"] != "analysis": continue
        source_ids = {p["id"] for p in record["job"]["sources"]}
        if not source_ids & ledger_ids: continue
        require(source_ids <= ledger_ids, "Markdown selection must include whole analysis batches")
        lines += ["## Analysis" + (" (TEST FIXTURE)" if record["is_test_fixture"] else ""),
                  "Config: " + safe(canonical(record["job"]["config"])),
                  "Requested model: " + safe(record["job"]["processing_preference"]["model_label"]),
                  "Actual model: " + safe(record["receipt"]["model"]),
                  "Execution: " + safe(record["receipt"]["execution_id"]), ""]
        for c in record["result"]["claims"]:
            lines += ["- " + safe(c["text"]) + " [" + c["kind"] + "; uncertainty: " + safe(c["uncertainty"] or "none identified") + "]",
                      "  Sources: " + ", ".join(c["source_ids"])]
        lines += ["Disagreements: " + safe(canonical(record["result"]["disagreements"])),
                  "Uncertainties: " + safe(canonical(record["result"]["uncertainties"])), ""]
    return "\n".join(lines)
