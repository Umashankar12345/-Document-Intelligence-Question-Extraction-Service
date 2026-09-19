import hashlib
import io
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Query, Response
from sqlalchemy.orm import Session
import fitz
from PIL import Image

from app.db import get_db
from app.models import User, Document, DocumentPage, Question, DocumentGroup
from app.schemas import (
    DocumentOut,
    DocumentUploadResponse,
    DocumentStatusOut,
    DocumentPageOut,
    QuestionOut,
    DocumentWarningsOut,
    QuestionWarningItem,
)
from app.auth import get_current_user
from app.storage import storage
from app.config import settings
from app.workers.tasks import dispatch_processing

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/jpg",
}

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def validate_file_integrity(filename: str, content: bytes, mime_type: str):
    """Check that the uploaded file is not corrupted."""
    ext = "." + filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS or mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {mime_type} ({ext}). Allowed: PDF, JPG, PNG",
        )

    if ext == ".pdf" or mime_type == "application/pdf":
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            if len(doc) == 0:
                raise ValueError("PDF has 0 pages")
            doc.close()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Corrupted or invalid PDF file: {str(e)}",
            )
    else:
        try:
            img = Image.open(io.BytesIO(content))
            img.verify()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Corrupted or invalid image file: {str(e)}",
            )


@router.post("", response_model=DocumentUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    group_id: Optional[str] = Form(None),
    role: str = Form("question_paper"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify group ownership if group_id is provided
    if group_id:
        group = db.query(DocumentGroup).filter(DocumentGroup.id == group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Document group not found")
        if current_user.role != "admin" and group.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to attach to this group")

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Size limit validation
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.max_upload_mb} MB",
        )

    # Content integrity and MIME validation
    mime = file.content_type or "application/octet-stream"
    validate_file_integrity(file.filename, content, mime)

    # Calculate checksum
    checksum = hashlib.sha256(content).hexdigest()

    # Create Document record
    doc_role = role.lower() if role.lower() in ("question_paper", "answer_key") else "unknown"
    doc = Document(
        owner_id=current_user.id,
        group_id=group_id,
        role=doc_role,
        filename=file.filename,
        mime_type=mime,
        size_bytes=file_size,
        storage_key="",
        checksum=checksum,
        status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Save to object store with user and doc isolation
    storage_key = storage.save(current_user.id, doc.id, file.filename, content)
    doc.storage_key = storage_key
    db.commit()

    # Trigger processing pipeline
    task_id = dispatch_processing(doc.id)

    return DocumentUploadResponse(
        document_id=doc.id,
        task_id=task_id,
        filename=doc.filename,
        status=doc.status,
        role=doc.role,
        group_id=doc.group_id,
    )


@router.get("", response_model=List[DocumentOut])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == "admin":
        return db.query(Document).order_by(Document.created_at.desc()).all()
    return db.query(Document).filter(Document.owner_id == current_user.id).order_by(Document.created_at.desc()).all()


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if current_user.role != "admin" and doc.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")
    return doc


@router.get("/{doc_id}/status", response_model=DocumentStatusOut)
def get_document_status(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if current_user.role != "admin" and doc.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")
    return DocumentStatusOut(
        document_id=doc.id,
        status=doc.status,
        page_count=doc.page_count,
        error=doc.error,
        updated_at=doc.updated_at,
    )


@router.get("/{doc_id}/pages/{page_number}")
def get_document_page(
    doc_id: str,
    page_number: int,
    as_image: bool = Query(False, description="Set to true to stream rendered PNG image"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if current_user.role != "admin" and doc.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")

    page = db.query(DocumentPage).filter(
        DocumentPage.document_id == doc_id,
        DocumentPage.page_number == page_number
    ).first()

    if not page:
        raise HTTPException(status_code=404, detail=f"Page {page_number} not found for document")

    if as_image:
        if not page.image_key:
            raise HTTPException(status_code=404, detail="Page render image not available")
        img_bytes = storage.load(page.image_key)
        return Response(content=img_bytes, media_type="image/png")

    return DocumentPageOut.from_orm(page)


@router.get("/{doc_id}/pages/{page_number}/image")
def get_document_page_image_stream(
    doc_id: str,
    page_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Direct stream of page PNG image for reviewer viewing."""
    return get_document_page(doc_id, page_number, as_image=True, current_user=current_user, db=db)


@router.get("/{doc_id}/questions", response_model=List[QuestionOut])
def get_document_questions(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if current_user.role != "admin" and doc.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")

    questions = db.query(Question).filter(Question.document_id == doc_id).order_by(Question.created_at.asc()).all()
    return questions


@router.get("/{doc_id}/warnings", response_model=DocumentWarningsOut)
def get_document_warnings(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if current_user.role != "admin" and doc.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")

    all_qs = db.query(Question).filter(Question.document_id == doc_id).all()
    review_items = []
    needs_review_count = 0
    partial_count = 0

    for q in all_qs:
        if q.status == "needs_review":
            needs_review_count += 1
        elif q.status == "partial":
            partial_count += 1

        if q.status in ("needs_review", "partial") or (q.warnings and len(q.warnings) > 0):
            snippet = q.question_text[:120] if q.question_text else ""
            review_items.append(
                QuestionWarningItem(
                    question_id=q.id,
                    question_number=q.question_number,
                    status=q.status,
                    confidence=q.confidence,
                    warnings=q.warnings or [],
                    snippet=snippet,
                )
            )

    return DocumentWarningsOut(
        document_id=doc.id,
        total_questions=len(all_qs),
        needs_review_count=needs_review_count,
        partial_count=partial_count,
        items=review_items,
    )


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if current_user.role != "admin" and doc.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Clean up files on storage backend
    storage.delete_document_artifacts(doc.owner_id, doc.id)

    db.delete(doc)
    db.commit()
    return None
