import uuid
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="Pipeline Service - Self-Service Ingestion API (mock)",
    version="1.0.0",
    description="Ingest documents into the search index. Open /docs for the live spec.",
)
app.state.store = {}


class ClientSpecificMetadata(BaseModel):
    item_id: str
    item_sensitivity: str  # public | internal | confidential


class DocumentIngestionForm(BaseModel):
    document_id: Optional[str] = Field(
        default=None,
        description=(
            "Optional. When provided it MUST be a UUID (e.g. "
            "`123e4567-e89b-12d3-a456-426614174000`); non-UUID values are rejected. If "
            "omitted, the service generates it as `uuid5(CLIENT_NAME, document_uri)` — "
            "namespaced by the client's name, `CLIENT_NAME = \"myclient\"` (precisely, the "
            "namespace is `uuid5(NAMESPACE_DNS, CLIENT_NAME)`) — so ids are scoped per client "
            "and deterministic from the uri. Send the same document_id on later "
            "upserts/deletes to target the same document."
        ),
    )
    document_uri: str = Field(
        description=(
            "Required. The document's URI — the natural key from which `document_id` is "
            "derived when you omit `document_id`."
        )
    )
    title: str = Field(description="Document title; embedded for search.")
    document_content: str = Field(
        description="Document body; embedded for search. Required — empty content is rejected (returned in `failed`)."
    )
    client_specific_metadata: Optional[ClientSpecificMetadata] = Field(
        default=None,
        description="Client-specific metadata stored with the document (e.g. the source item_id and sensitivity).",
    )


class DocumentBatch(BaseModel):
    documents: List[DocumentIngestionForm]


class DeleteDocumentBatch(BaseModel):
    document_ids: List[str] = Field(
        description=(
            "Pipeline document_ids to delete. Deletion is by document_id only — the value "
            "returned at ingest (or the one you supplied)."
        )
    )


class IngestedDocument(BaseModel):
    document_id: str
    document_uri: str
    title: str
    document_content: str
    client_specific_metadata: Optional[ClientSpecificMetadata] = None


class IngestedDocumentSummary(BaseModel):
    document_id: str
    document_uri: str
    title: str


class SucceededDoc(BaseModel):
    document_id: str = Field(
        description="The stored document_id — the value you supplied, or the one generated from `document_uri` when omitted."
    )


class RejectedDoc(BaseModel):
    document_uri: Optional[str] = None
    document_id: Optional[str] = None
    error_code: str = Field(description="e.g. EMPTY_CONTENT or INVALID_DOCUMENT_ID (ingest), NOT_FOUND (delete).")
    error_message: str


class BatchResponse(BaseModel):
    succeeded: List[SucceededDoc] = Field(description="Documents ingested / upserted (or deleted).")
    failed: List[RejectedDoc] = Field(description="Documents rejected — e.g. empty content or a non-UUID document_id on ingest, or NOT_FOUND on delete.")


# document_ids are namespaced per client: each client has a unique name, so the same uri
# under a different client yields a different id.
CLIENT_NAME = "myclient"
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, CLIENT_NAME)


def document_id_from_uri(document_uri: str) -> str:
    return str(uuid.uuid5(NAMESPACE, document_uri))


def is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


@app.post("/ingestion/documents/document-batches", response_model=BatchResponse)
def create_document_batch(batch: DocumentBatch) -> BatchResponse:
    succeeded: List[SucceededDoc] = []
    failed: List[RejectedDoc] = []
    for doc in batch.documents:
        if not doc.document_content.strip():
            failed.append(
                RejectedDoc(
                    document_uri=doc.document_uri,
                    document_id=doc.document_id,
                    error_code="EMPTY_CONTENT",
                    error_message="document_content is empty; nothing to embed",
                )
            )
            continue
        if doc.document_id is not None and not is_uuid(doc.document_id):
            failed.append(
                RejectedDoc(
                    document_uri=doc.document_uri,
                    document_id=doc.document_id,
                    error_code="INVALID_DOCUMENT_ID",
                    error_message="document_id must be a UUID",
                )
            )
            continue
        document_id = doc.document_id or document_id_from_uri(doc.document_uri)
        app.state.store[document_id] = IngestedDocument(
            document_id=document_id,
            document_uri=doc.document_uri,
            title=doc.title,
            document_content=doc.document_content,
            client_specific_metadata=doc.client_specific_metadata,
        )
        succeeded.append(SucceededDoc(document_id=document_id))
    return BatchResponse(succeeded=succeeded, failed=failed)


@app.post("/ingestion/documents/delete-document-batches", response_model=BatchResponse)
def delete_document_batch(batch: DeleteDocumentBatch) -> BatchResponse:
    succeeded: List[SucceededDoc] = []
    failed: List[RejectedDoc] = []
    for document_id in batch.document_ids:
        if document_id in app.state.store:
            del app.state.store[document_id]
            succeeded.append(SucceededDoc(document_id=document_id))
        else:
            failed.append(
                RejectedDoc(
                    document_id=document_id,
                    error_code="NOT_FOUND",
                    error_message="no document with this document_id",
                )
            )
    return BatchResponse(succeeded=succeeded, failed=failed)


@app.get("/ingestion/documents", response_model=List[IngestedDocumentSummary])
def list_documents() -> List[IngestedDocumentSummary]:
    return [
        IngestedDocumentSummary(
            document_id=doc.document_id,
            document_uri=doc.document_uri,
            title=doc.title,
        )
        for doc in app.state.store.values()
    ]


@app.get("/ingestion/documents/{document_id}", response_model=IngestedDocument)
def get_document(document_id: str) -> IngestedDocument:
    if document_id not in app.state.store:
        raise HTTPException(status_code=404, detail="document not found")
    return app.state.store[document_id]
