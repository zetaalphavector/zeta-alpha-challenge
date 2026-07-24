# ClientDocs Connector — Candidate Brief

You're one of **our** forward-deployed engineers, working on our engagement with the
client **MyClient**. MyClient runs an internal document system, **ClientDocs**, exposed over a REST API. Your job is to build a **connector** in a Python script that can:
1. crawl ClientDocs and ingest them into **our Pipeline Service**
2. crawl updates of documents, since the client may modify documents on a daily basis


## The two APIs

**Pipeline Service (ingestion)** ships with this project. Start it from the `connector`
folder, in its own terminal:

```bash
./run_pipeline.sh
```

It serves at **http://localhost:8001/docs**.

**ClientDocs (source)** is already running for you at **http://localhost:8002/docs**.

The Swagger UI at `/docs` is the spec for each — read the endpoints and field descriptions there.

## ClientDocs (source) — what you crawl

| Endpoint | Purpose |
|---|---|
| `GET /documents?page=&page_size=` | Paginated listing (`documents`, `page`, `page_size`, `total`). |
| `GET /documents/{item_id}/content` | The document body (content) for an item, e.g. `DOC-0001`. |
| `GET /documents/delta?since=<datetime>&page=&page_size=` | All document changes since a timestamp: `created`, `updated`, `deleted` events. |

Each document has `item_id` and `uri` at the top level, plus `metadata` (`title`,
`item_sensitivity`). The `uri` is dependent on the document's file path in ClientDocs.
The body is **not** included; fetch it per item from `GET /documents/{item_id}/content`.

In the delta, **every event (`created`, `updated` and `deleted`) carries `item_id` and `uri`**; `created`/`updated` also carry `metadata`.

**Paging & incremental sync.** Both endpoints page with `page` / `page_size`. The full crawl
returns the **current state** of every document; the delta takes a `since` datetime and
returns whatever changed after it.


## Pipeline Service (ingestion) — where you write

| Endpoint | Purpose |
|---|---|
| `POST /ingestion/documents/document-batches` | Upsert a batch of documents. |
| `POST /ingestion/documents/delete-document-batches` | Delete a batch by `document_ids`. |
| `GET /ingestion/documents` | List what you've ingested (to verify). |
| `GET /ingestion/documents/{document_id}` | Read one back (to verify). |

Ingestion document fields:
- `document_id` (optional — when set, it **must be a UUID**; if omitted, the pipeline generates it as `uuid5(CLIENT_NAME, document_uri)`,
- `document_uri`, `title`, `document_content`, `client_specific_metadata { item_id, item_sensitivity }`.
The batch response is `{ succeeded, failed }`, e.g.:

```json
{
  "succeeded": [{ "document_id": "3f2504e0-4f89-51d3-9a0c-0305e82c3301" }],
  "failed": [
    { "document_uri": "client://docs/legal/document-0002.pdf", "document_id": "not-a-uuid",
      "error_code": "INVALID_DOCUMENT_ID", "error_message": "document_id must be a UUID" }
  ]
}
```

## Part 1 — Full crawl

Full-crawl ClientDocs, fetch each document's content, and ingest every document into the
pipeline.
(This environment simulates a point in the past, so full crawl will give you all 
documents until that point)

## Part 2 — Delta crawl

Consume `GET /documents/delta?since=<datetime>` to fetch what changed after your crawl —
ingest the `created`/`updated` docs and **apply the `deleted` events**. Use
**`since=2024-06-01T00:00:00`** (the crawl's point in time) to pick up everything that
changed after it.

## Part 3 — Discussion (no code)

- **Scaling.** There are millions of documents in the ClientDocs side. How can you scale the ingestion?
- **Fast sync.** The client wants updates synced very fast (e.g. within a minute). How would you approach it?
- **Ingestion failures.** The pipeline may report that some docs failed to ingest — how would you handle it?
- **Deletion failures.** The pipeline may report that a deletion failed — how would you handle it?

