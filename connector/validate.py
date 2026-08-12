#!/usr/bin/env python3
"""Validate the Pipeline Service against the expected end-state of a crawl.

This is an INDEPENDENT oracle. It does not look at your connector at all: it
reads the ClientDocs source directly, works out what the pipeline *should*
contain after a crawl, and diffs that against what your connector actually
ingested. A mismatch means your connector dropped, duplicated, or mis-synced
something.

It reads whichever source is currently running on :8002, so the SAME command
validates both the clean `mock` and the messy `prod` source — you just tell it
which phase you're checking.

Expected-state rules (what a correct connector must end up with):
  * Full crawl  -> every document in `GET /documents` whose body is fetchable
                   and non-empty. (A 404 body is skipped; an empty body is
                   rejected by the pipeline, so it must NOT appear.)
  * Delta crawl -> the full-crawl state with `GET /documents/delta` applied in
                   order: created/updated upsert the item, deleted removes it.
                   Identity is the stable `item_id`, so a moved document (same
                   item_id, new uri) ends up as ONE document at its new uri.

Usage:
    python3 validate.py --phase full
    python3 validate.py --phase delta --since 2024-06-01T00:00:00
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

DEFAULT_SOURCE_URL = "http://localhost:8002"
DEFAULT_PIPELINE_URL = "http://localhost:8001"
DEFAULT_SINCE = "2024-06-01T00:00:00"


# ---------------------------------------------------------------------------
# Small HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------


def _get(url: str, params: Optional[dict] = None) -> Tuple[int, Optional[dict]]:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, None


# ---------------------------------------------------------------------------
# Expected state, derived from the SOURCE (the ground truth)
# ---------------------------------------------------------------------------


class Expected:
    """A document we expect to find in the pipeline, keyed internally by item_id."""

    def __init__(self, item_id: str, uri: str, title: str, sensitivity: str, content: str):
        self.item_id = item_id
        self.uri = uri
        self.title = title
        self.sensitivity = sensitivity
        self.content = content


def _content_or_none(source: str, item_id: str) -> Optional[str]:
    """Return the body, or None if the source has no content for the item (404)."""
    status, body = _get(f"{source}/documents/{item_id}/content")
    if status == 404 or body is None:
        return None
    return body.get("content", "")


def _list_documents(source: str) -> List[dict]:
    docs: List[dict] = []
    page = 1
    while True:
        _, body = _get(f"{source}/documents", {"page": page, "page_size": 100})
        batch = (body or {}).get("documents", [])
        docs.extend(batch)
        total = (body or {}).get("total", 0)
        if not batch or len(docs) >= total:
            break
        page += 1
    return docs


def _list_delta(source: str, since: str) -> List[dict]:
    events: List[dict] = []
    page = 1
    while True:
        _, body = _get(f"{source}/documents/delta", {"since": since, "page": page, "page_size": 100})
        batch = (body or {}).get("events", [])
        events.extend(batch)
        total = (body or {}).get("total", 0)
        if not batch or len(events) >= total:
            break
        page += 1
    return events


def expected_after_full(source: str) -> Dict[str, Expected]:
    """Every listed document with a fetchable, non-empty body."""
    result: Dict[str, Expected] = {}
    for d in _list_documents(source):
        item_id = d["item_id"]
        content = _content_or_none(source, item_id)
        if content is None or content.strip() == "":
            continue  # 404 -> skipped; empty -> pipeline rejects it
        meta = d.get("metadata") or {}
        result[item_id] = Expected(item_id, d["uri"], meta.get("title", ""),
                                    meta.get("item_sensitivity", ""), content)
    return result


def expected_after_delta(source: str, since: str) -> Dict[str, Expected]:
    """Full-crawl state with the delta applied in feed order (oldest-first)."""
    state = expected_after_full(source)
    for e in _list_delta(source, since):
        item_id = e["item_id"]
        if e["event_type"] == "deleted":
            state.pop(item_id, None)
            continue
        # created / updated: re-fetch the (current) body and upsert.
        content = _content_or_none(source, item_id)
        if content is None or content.strip() == "":
            state.pop(item_id, None)  # can't ingest an empty/missing body
            continue
        meta = e.get("metadata") or {}
        state[item_id] = Expected(item_id, e["uri"], meta.get("title", ""),
                                  meta.get("item_sensitivity", ""), content)
    return state


# ---------------------------------------------------------------------------
# Actual state, read back from the PIPELINE
# ---------------------------------------------------------------------------


def actual_documents(pipeline: str) -> List[dict]:
    """Full ingested documents (list endpoint is a summary, so read each back)."""
    _, summaries = _get(f"{pipeline}/ingestion/documents")
    docs: List[dict] = []
    for s in summaries or []:
        _, full = _get(f"{pipeline}/ingestion/documents/{s['document_id']}")
        if full is not None:
            docs.append(full)
    return docs


# ---------------------------------------------------------------------------
# Diff + report
# ---------------------------------------------------------------------------


def validate(source: str, pipeline: str, phase: str, since: str) -> bool:
    expected = (expected_after_full(source) if phase == "full"
                else expected_after_delta(source, since))
    expected_by_uri = {e.uri: e for e in expected.values()}

    actual = actual_documents(pipeline)
    actual_by_uri: Dict[str, List[dict]] = {}
    for d in actual:
        actual_by_uri.setdefault(d["document_uri"], []).append(d)

    print(f"\nSource   : {source}")
    print(f"Pipeline : {pipeline}")
    print(f"Phase    : {phase} crawl" + (f"  (since {since})" if phase == "delta" else ""))

    print(f"\nExpected {len(expected)} document(s):")
    for e in sorted(expected.values(), key=lambda x: x.item_id):
        print(f"  {e.item_id}  {e.uri}  | {e.title}")
    print(f"\nPipeline holds {len(actual)} document(s).")

    missing, mismatched, extra, duplicates = [], [], [], []

    for uri, e in expected_by_uri.items():
        rows = actual_by_uri.get(uri, [])
        if not rows:
            missing.append(e)
            continue
        if len(rows) > 1:
            duplicates.append((uri, len(rows)))
        a = rows[0]
        problems = []
        if a.get("title") != e.title:
            problems.append(f"title {a.get('title')!r} != {e.title!r}")
        csm = a.get("client_specific_metadata") or {}
        if csm.get("item_id") != e.item_id:
            problems.append(f"item_id {csm.get('item_id')!r} != {e.item_id!r}")
        if csm.get("item_sensitivity") != e.sensitivity:
            problems.append(f"sensitivity {csm.get('item_sensitivity')!r} != {e.sensitivity!r}")
        if (a.get("document_content") or "") != e.content:
            problems.append("content differs")
        if problems:
            mismatched.append((e, problems))

    for uri, rows in actual_by_uri.items():
        if uri not in expected_by_uri:
            for r in rows:
                extra.append(r)

    print()
    if missing:
        print(f"MISSING ({len(missing)}) — expected, but not in the pipeline:")
        for e in missing:
            print(f"  - {e.item_id}  {e.uri}  | {e.title}")
    if extra:
        print(f"UNEXPECTED ({len(extra)}) — in the pipeline, but should not be:")
        for r in extra:
            iid = (r.get('client_specific_metadata') or {}).get('item_id')
            print(f"  + {iid}  {r.get('document_uri')}  | {r.get('title')}")
    if duplicates:
        print(f"DUPLICATED ({len(duplicates)}) — more than one pipeline doc for a uri:")
        for uri, n in duplicates:
            print(f"  x {uri}  ({n} copies)")
    if mismatched:
        print(f"MISMATCHED ({len(mismatched)}) — present but wrong:")
        for e, problems in mismatched:
            print(f"  ~ {e.item_id}  {e.uri}: {'; '.join(problems)}")

    ok = not (missing or extra or duplicates or mismatched)
    print("\nRESULT: " + ("PASS ✅  pipeline matches the expected end-state."
                          if ok else "FAIL ❌  see the differences above."))
    return ok


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--phase", required=True, choices=["full", "delta"],
                   help="Which checkpoint to validate: after the full crawl, or after the delta crawl.")
    p.add_argument("--since", default=DEFAULT_SINCE, help=f"Delta `since` (default {DEFAULT_SINCE}).")
    p.add_argument("--source-url", default=DEFAULT_SOURCE_URL, help=f"ClientDocs base URL (default {DEFAULT_SOURCE_URL}).")
    p.add_argument("--pipeline-url", default=DEFAULT_PIPELINE_URL, help=f"Pipeline base URL (default {DEFAULT_PIPELINE_URL}).")
    args = p.parse_args(argv)

    ok = validate(args.source_url.rstrip("/"), args.pipeline_url.rstrip("/"), args.phase, args.since)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
