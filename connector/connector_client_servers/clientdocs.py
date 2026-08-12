# Data-driven ClientDocs source server.
#
# The mock and the prod source are the SAME server — they differ only in data. This script
# loads a scenario from a JSON file (path in the CLIENTDOCS_DATA env var) and serves the exact
# same API as before. Point it at data/mock.json for the clean happy-path source, or
# data/prod.json for the "production messy" source with the traps.
#
#   uvicorn clientdocs:app --port 8002                          # defaults to data/mock.json
#   CLIENTDOCS_DATA=data/prod.json uvicorn clientdocs:app --port 8002
#
# Scenario JSON shape:
#   {
#     "crawl":   [ {"item_id","uri","metadata":{"title","item_sensitivity"}}, ... ],   # full-crawl listing
#     "content": { "DOC-0001": "body...", "DOC-0003": "", "DOC-0004": null, ... },      # body per item_id
#     "delta":   [ {"changed_at","event_type","item_id","uri","metadata"?}, ... ]       # change log
#   }
#
# Content semantics: a string is the body; "" is an EMPTY body (the pipeline rejects it); null
# (or a missing key) means NO body — the content endpoint 404s. `metadata` is present on
# `created`/`updated` delta events and omitted on `deleted`. A "moved" document is simply an
# `updated` event whose `uri` differs from the crawl `uri` (the item_id stays the same).

import json
import os
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field


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


class DeltaEvent(BaseModel):
    event_type: str = Field(description="One of: created | updated | deleted.")
    item_id: str = Field(description="Canonical id of the changed document.")
    uri: str = Field(description="The document's path — present on every event, including `deleted`.")
    metadata: Optional[DocumentMetadata] = Field(
        default=None,
        description="Title + sensitivity — present on `created` and `updated` events (absent on `deleted`). The body is not included; fetch it from `/documents/{item_id}/content`.",
    )


# --- Scenario file (the JSON loaded at startup) ------------------------------


class DeltaEntry(BaseModel):
    changed_at: str  # server-side only: used to honor `since` and to sort oldest-first
    event_type: str
    item_id: str
    uri: str
    metadata: Optional[DocumentMetadata] = None


class Scenario(BaseModel):
    crawl: List[Document]
    content: Dict[str, Optional[str]]
    delta: List[DeltaEntry] = []


# Default scenario when CLIENTDOCS_DATA is unset: the clean mock source. Resolved relative to
# this file so it works regardless of the current working directory.
DEFAULT_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "mock.json")


def _load_scenario() -> Scenario:
    path = os.environ.get("CLIENTDOCS_DATA") or DEFAULT_DATA
    if not os.path.exists(path):
        raise RuntimeError(f"Scenario file not found: {path}")
    with open(path) as f:
        return Scenario(**json.load(f))


SCENARIO = _load_scenario()


app = FastAPI(
    title="ClientDocs API (mock)",
    version="1.0.0",
    description="The client source system. Open /docs for the live spec.",
)


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
    items = SCENARIO.crawl
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
    matching = [
        DeltaEvent(event_type=d.event_type, item_id=d.item_id, uri=d.uri, metadata=d.metadata)
        for d in sorted(SCENARIO.delta, key=lambda c: c.changed_at)
        if d.changed_at > since
    ]
    return DeltaPage(
        events=_page(matching, page, page_size),
        page=page,
        page_size=page_size,
        total=len(matching),
    )


@app.get("/documents/{item_id}/content", response_model=DocumentContent)
def get_content(item_id: str) -> DocumentContent:
    body = SCENARIO.content.get(item_id)
    if body is None:  # missing key or explicit null -> no body at source
        raise HTTPException(status_code=404, detail="document not found")
    return DocumentContent(item_id=item_id, content=body)
