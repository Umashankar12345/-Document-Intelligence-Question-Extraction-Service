from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, DocumentGroup, Document, Question, DocumentPage
from app.schemas import DocumentGroupCreate, DocumentGroupOut, QuestionOut, DocumentOut
from app.auth import get_current_user
from app.services.answer_key import link_answers_to_questions
from app.services.confidence import compute_confidence_and_status

router = APIRouter(prefix="/document-groups", tags=["Document Groups"])


@router.post("", response_model=DocumentGroupOut, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: DocumentGroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = DocumentGroup(
        owner_id=current_user.id,
        name=payload.name or "Untitled Group",
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.get("", response_model=List[DocumentGroupOut])
def list_groups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == "admin":
        return db.query(DocumentGroup).order_by(DocumentGroup.created_at.desc()).all()
    return db.query(DocumentGroup).filter(DocumentGroup.owner_id == current_user.id).order_by(DocumentGroup.created_at.desc()).all()


@router.post("/{gid}/documents/{did}", response_model=DocumentOut)
def attach_document_to_group(
    gid: str,
    did: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = db.query(DocumentGroup).filter(DocumentGroup.id == gid).first()
    if not group:
        raise HTTPException(status_code=404, detail="Document group not found")
    if current_user.role != "admin" and group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied on group")

    doc = db.query(Document).filter(Document.id == did).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if current_user.role != "admin" and doc.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied on document")

    doc.group_id = gid
    db.commit()

    # If the document or another document in the group is an answer key, trigger cross-linking
    answer_keys = db.query(Document).filter(
        Document.group_id == gid,
        Document.role == "answer_key"
    ).all()

    question_papers = db.query(Document).filter(
        Document.group_id == gid,
        Document.role == "question_paper"
    ).all()

    if answer_keys and question_papers:
        # Aggregate all answer key text
        all_ans_text = ""
        for ak in answer_keys:
            pages = db.query(DocumentPage).filter(DocumentPage.document_id == ak.id).order_by(DocumentPage.page_number).all()
            all_ans_text += "\n" + "\n".join([p.raw_text or "" for p in pages])

        if all_ans_text.strip():
            for qp in question_papers:
                qs = db.query(Question).filter(Question.document_id == qp.id).all()
                if qs:
                    link_answers_to_questions(qs, all_ans_text, source_type="external")
                    for q in qs:
                        q.group_id = gid
                        structure_ok = len([w for w in q.warnings if w != "unmatched_answer"]) == 0
                        score, q_status = compute_confidence_and_status(
                            ocr_conf=q.confidence,
                            structure_ok=structure_ok,
                            answer_conf=q.answer_confidence,
                            warnings=q.warnings,
                        )
                        q.confidence = score
                        q.status = q_status
                    db.commit()

    db.refresh(doc)
    return doc


@router.get("/{gid}/questions", response_model=List[QuestionOut])
def get_group_questions(
    gid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = db.query(DocumentGroup).filter(DocumentGroup.id == gid).first()
    if not group:
        raise HTTPException(status_code=404, detail="Document group not found")
    if current_user.role != "admin" and group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")

    questions = db.query(Question).filter(Question.group_id == gid).order_by(Question.created_at.asc()).all()
    return questions
