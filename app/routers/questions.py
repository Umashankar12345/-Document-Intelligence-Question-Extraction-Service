from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, Question, Document
from app.schemas import QuestionOut, QuestionAnswerOut
from app.auth import get_current_user

router = APIRouter(prefix="/questions", tags=["Questions"])


@router.get("/{qid}", response_model=QuestionOut)
def get_question(
    qid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Question).filter(Question.id == qid).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    doc = db.query(Document).filter(Document.id == q.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Associated document not found")

    if current_user.role != "admin" and doc.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")

    return q


@router.get("/{qid}/answer", response_model=QuestionAnswerOut)
def get_question_answer(
    qid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Question).filter(Question.id == qid).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    doc = db.query(Document).filter(Document.id == q.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Associated document not found")

    if current_user.role != "admin" and doc.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")

    return QuestionAnswerOut(
        question_id=q.id,
        question_number=q.question_number,
        answer=q.answer,
        answer_source=q.answer_source or "none",
        answer_confidence=q.answer_confidence,
        status=q.status,
    )
