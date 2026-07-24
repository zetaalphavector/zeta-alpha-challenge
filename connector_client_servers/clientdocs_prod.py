# INTERVIEWER-ONLY — do NOT give this file to the candidate.
#
# Drop-in replacement for candidate/servers/clientdocs_mock.py: identical API and Swagger, but
# the data is "production messy" where the happy-path mock is clean. Swap this in on port 8002
# to see whether the candidate's connector — built against the tidy mock — survives reality.
#
# What's harder here than in the mock:
#
#   Delta feed (Part 2) — the change log repeats items: DOC-0003 changes twice and DOC-0011
#     is updated after having been deleted. Like the mock it's returned oldest-first, so a
#     straight in-order apply lands on the CORRECT end state (DOC-0003 -> "revised", DOC-0011
#     -> present) — but it does redundant work: DOC-0003 is upserted twice, and DOC-0011 is
#     deleted and then re-created (a wasted round-trip and a transient window where it's gone).
#     Collapsing to one op per item_id is the OPTIMIZATION; the mock's delta has one event per
#     item, so a candidate has no reason to reach for it there. This is not a correctness trap.
#
#   Content endpoint (Part 1) — the real correctness traps; two crawl documents misbehave:
#     - DOC-0007 — EMPTY content. The endpoint returns "" → the pipeline rejects it in
#       `failed` (EMPTY_CONTENT); a connector that ignores the failed list loses it silently.
#     - DOC-0013 — NO content. The endpoint 404s → the per-item content fetch fails and the
#       connector has to cope instead of crashing.
#
# Run it in place of clientdocs_mock:
#
#   uvicorn clientdocs_prod:app --port 8002

from typing import List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(
    title="ClientDocs API (mock)",
    version="1.0.0",
    description="The client source system. Open /docs for the live spec.",
)

DEPARTMENTS = ["finance", "legal", "engineering", "hr"]
SENSITIVITIES = ["public", "internal", "confidential"]


class DocumentMetadata(BaseModel):
    title: str
    item_sensitivity: str


class Document(BaseModel):
    item_id: str
    uri: str = Field(description="The document's file path in ClientDocs (derived from where the file lives in the folder tree).")
    metadata: DocumentMetadata


class DocumentContent(BaseModel):
    item_id: str
    content: str


def _dept(i: int) -> str:
    return DEPARTMENTS[i % len(DEPARTMENTS)]


def _uri(i: int) -> str:
    return f"client://docs/{_dept(i)}/document-{i:04d}.pdf"


def _meta(i: int, title: Optional[str] = None) -> DocumentMetadata:
    return DocumentMetadata(
        title=title or f"{_dept(i).capitalize()} Document {i}",
        item_sensitivity=SENSITIVITIES[i % len(SENSITIVITIES)],
    )


def _doc(i: int) -> Document:
    return Document(item_id=f"DOC-{i:04d}", uri=_uri(i), metadata=_meta(i))


def _content(i: int) -> str:
    # DOC-0007 has an empty body -> the pipeline rejects it (EMPTY_CONTENT).
    return "" if i == 7 else f"Body of {_dept(i)} document {i}. " * 8


CRAWL = {f"DOC-{i:04d}": _doc(i) for i in range(1, 25)}
CREATED = {f"DOC-{i:04d}": _doc(i) for i in (25, 26)}

CONTENT = {f"DOC-{i:04d}": _content(i) for i in range(1, 27)}
CONTENT["DOC-0003"] = "Body of hr document 3, revised. " * 8
# DOC-0013 has NO content at the source: the content endpoint 404s, so the connector's
# per-item content fetch fails and it must handle that.
del CONTENT["DOC-0013"]


class DeltaEvent(BaseModel):
    event_type: str = Field(description="One of: created | updated | deleted.")
    item_id: str = Field(description="Canonical id of the changed document.")
    uri: str = Field(description="The document's path — present on every event, including `deleted`.")
    metadata: Optional[DocumentMetadata] = Field(
        default=None,
        description="Title + sensitivity — present on `created` and `updated` events (absent on `deleted`). The body is not included; fetch it from `/documents/{item_id}/content`.",
    )


# (changed_at, event); returned oldest-first, timestamp server-side only (see clientdocs_mock).
# Repeats: DOC-0003 changed twice, DOC-0011 deleted @06-02 then updated @06-06.
CHANGES: List[Tuple[str, DeltaEvent]] = [
    ("2024-06-02T09:00:00", DeltaEvent(event_type="created", item_id="DOC-0025", uri=_uri(25), metadata=_meta(25))),
    ("2024-06-05T14:00:00", DeltaEvent(event_type="updated", item_id="DOC-0003", uri=_uri(3), metadata=_meta(3, "Hr Document 3 (revised)"))),
    ("2024-06-06T08:00:00", DeltaEvent(event_type="updated", item_id="DOC-0011", uri=_uri(11), metadata=_meta(11))),
    ("2024-06-02T09:05:00", DeltaEvent(event_type="created", item_id="DOC-0026", uri=_uri(26), metadata=_meta(26))),
    ("2024-06-04T08:00:00", DeltaEvent(event_type="deleted", item_id="DOC-0005", uri=_uri(5))),
    ("2024-06-03T10:00:00", DeltaEvent(event_type="updated", item_id="DOC-0003", uri=_uri(3), metadata=_meta(3, "Hr Document 3 (rev)"))),
    ("2024-06-02T07:00:00", DeltaEvent(event_type="deleted", item_id="DOC-0011", uri=_uri(11))),
]


class DocumentPage(BaseModel):
    documents: List[Document]
    page: int = Field(description="1-based page number of this response.")
    page_size: int = Field(description="Documents per page.")
    total: int = Field(description="Total documents in the listing. Keep paging while page * page_size < total.")


class DeltaPage(BaseModel):
    events: List[DeltaEvent]
    page: int = Field(description="1-based page number of this response.")
    page_size: int = Field(description="Events per page.")
    total: int = Field(description="Total change events after `since`. Keep paging while page * page_size < total.")


def _page(items: list, page: int, page_size: int) -> list:
    start = (page - 1) * page_size
    return items[start : start + page_size]


@app.get("/documents", response_model=DocumentPage)
def list_documents(
    page: int = Query(1, ge=1, description="1-based page number. Start at 1 and increment until page * page_size >= total."),
    page_size: int = Query(10, ge=1, description="Documents per page."),
) -> DocumentPage:
    items = list(CRAWL.values())
    return DocumentPage(
        documents=_page(items, page, page_size),
        page=page,
        page_size=page_size,
        total=len(items),
    )


@app.get("/documents/delta", response_model=DeltaPage)
def get_delta(
    since: str = Query(..., description="Return changes strictly after this ISO-8601 datetime — the point in time your last sync covered (for the first delta, the moment of your full crawl)."),
    page: int = Query(1, ge=1, description="1-based page number."),
    page_size: int = Query(10, ge=1, description="Events per page."),
) -> DeltaPage:
    matching = [ev for ts, ev in sorted(CHANGES, key=lambda c: c[0]) if ts > since]
    return DeltaPage(
        events=_page(matching, page, page_size),
        page=page,
        page_size=page_size,
        total=len(matching),
    )


@app.get("/documents/{item_id}/content", response_model=DocumentContent)
def get_content(item_id: str) -> DocumentContent:
    if item_id in CONTENT:
        return DocumentContent(item_id=item_id, content=CONTENT[item_id])
    raise HTTPException(status_code=404, detail="document not found")
