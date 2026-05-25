from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from database import get_pool
from auth_routes import get_current_user
import storage

router = APIRouter(tags=["documents"])

MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB


class UploadRequest(BaseModel):
    name: str
    content_type: str
    size_bytes: int
    property_id: Optional[int] = None


class RecordDocument(BaseModel):
    name: str
    s3_key: str
    content_type: str
    size_bytes: int
    property_id: Optional[int] = None


def _verify_property(property_id: int, user_id: int):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM flowmint.properties WHERE id = %s AND user_id = %s",
                (property_id, user_id)
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Property not found")


@router.get("/documents")
def list_documents(
    property_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    conditions = ["d.user_id = %s"]
    params: list = [current_user["id"]]
    if property_id is not None:
        conditions.append("d.property_id = %s")
        params.append(property_id)

    where = " AND ".join(conditions)
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT d.id, d.name, d.s3_key, d.content_type, d.size_bytes,
                           d.uploaded_at, d.property_id, p.address AS property_address
                    FROM flowmint.documents d
                    LEFT JOIN flowmint.properties p ON d.property_id = p.id
                    WHERE {where}
                    ORDER BY d.uploaded_at DESC""",
                params
            )
            rows = cur.fetchall()
    return [
        {
            "id": r[0], "name": r[1], "s3_key": r[2], "content_type": r[3],
            "size_bytes": r[4], "uploaded_at": r[5].isoformat(),
            "property_id": r[6], "property_address": r[7],
        }
        for r in rows
    ]


@router.post("/documents/upload-url")
def get_upload_url(body: UploadRequest, current_user: dict = Depends(get_current_user)):
    if body.size_bytes > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit")
    if body.property_id:
        _verify_property(body.property_id, current_user["id"])

    s3_key = storage.make_s3_key(current_user["id"], body.name)
    upload_url = storage.presigned_upload_url(s3_key, body.content_type)
    return {"upload_url": upload_url, "s3_key": s3_key}


@router.post("/documents", status_code=201)
def record_document(body: RecordDocument, current_user: dict = Depends(get_current_user)):
    if body.property_id:
        _verify_property(body.property_id, current_user["id"])
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO flowmint.documents
                       (user_id, property_id, name, s3_key, content_type, size_bytes)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id, uploaded_at""",
                (current_user["id"], body.property_id, body.name,
                 body.s3_key, body.content_type, body.size_bytes)
            )
            row = cur.fetchone()
            conn.commit()
    return {"id": row[0], "uploaded_at": row[1].isoformat(), **body.model_dump()}


@router.get("/documents/{doc_id}/download-url")
def get_download_url(doc_id: int, current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, s3_key FROM flowmint.documents WHERE id = %s AND user_id = %s",
                (doc_id, current_user["id"])
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    url = storage.presigned_download_url(row[1], row[0])
    return {"download_url": url, "expires_in": 900}


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: int, current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT s3_key FROM flowmint.documents WHERE id = %s AND user_id = %s",
                (doc_id, current_user["id"])
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Document not found")
            cur.execute("DELETE FROM flowmint.documents WHERE id = %s", (doc_id,))
            conn.commit()
    storage.delete_object(row[0])
