import logging
from celery import chain
from sqlalchemy.orm import Session

from app.config import settings
from app.workers.celery_app import celery_app
from app.db import SessionLocal
from app.models import Document, DocumentPage, Question
from app.storage import storage
from app.services.pdf import process_pdf, process_image
from app.services import ocr
from app.services.extractor import extract_questions_from_pages, PageText
from app.services.answer_key import link_answers_to_questions
from app.services.confidence import compute_confidence_and_status

logger = logging.getLogger(__name__)


def run_pipeline(doc_id: str):
    """Synchronous pipeline runner executing all stages sequentially."""
    db: Session = SessionLocal()
    try:
        # Step 1: Ingest
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            logger.error(f"Document {doc_id} not found")
            return

        doc.status = "processing"
        db.commit()

        file_data = storage.load(doc.storage_key)
        is_pdf = doc.mime_type == "application/pdf" or doc.filename.lower().endswith(".pdf")

        if is_pdf:
            pages_info = process_pdf(file_data)
        else:
            pages_info = process_image(file_data)

        doc.page_count = len(pages_info)

        # Clear existing pages if re-processing
        db.query(DocumentPage).filter(DocumentPage.document_id == doc_id).delete()
        db.commit()

        ocr_provider = ocr.get_ocr_provider()
        page_texts: list[PageText] = []

        for p in pages_info:
            # Save PNG render
            img_key = storage.save_page_image(doc.owner_id, doc.id, p.page_number, p.png_bytes)
            
            # Step 2: OCR if scanned or low text
            raw_text = p.raw_text
            ocr_conf = 1.0  # Native digital text has high confidence
            rotation = p.rotation_deg

            if p.is_scanned or len(raw_text.split()) < 15:
                ocr_res = ocr_provider.ocr_image(p.png_bytes)
                if ocr_res.text:
                    raw_text = ocr_res.text
                ocr_conf = ocr_res.confidence
                rotation = ocr_res.rotation_deg

            page_rec = DocumentPage(
                document_id=doc.id,
                page_number=p.page_number,
                image_key=img_key,
                raw_text=raw_text,
                ocr_confidence=ocr_conf,
                rotation_deg=rotation,
            )
            db.add(page_rec)
            page_texts.append(PageText(number=p.page_number, text=raw_text, blocks=p.blocks))

        db.commit()

        # If document role is answer_key, we also check if there's an associated question paper in group
        if doc.role == "answer_key":
            if doc.group_id:
                # Find question papers in the same group and re-link answers
                qpapers = db.query(Document).filter(
                    Document.group_id == doc.group_id,
                    Document.role == "question_paper",
                    Document.id != doc.id
                ).all()
                all_ans_text = "\n".join([pt.text for pt in page_texts])
                for qp in qpapers:
                    existing_qs = db.query(Question).filter(Question.document_id == qp.id).all()
                    if existing_qs:
                        link_answers_to_questions(existing_qs, all_ans_text, source_type="external")
                        qp_pages = db.query(DocumentPage).filter(DocumentPage.document_id == qp.id).all()
                        qp_conf_map = {
                            p.page_number: (p.ocr_confidence if p.ocr_confidence is not None else 1.0)
                            for p in qp_pages
                        }
                        for q in existing_qs:
                            if q.source_pages:
                                q_ocr_avg = sum(qp_conf_map.get(pn, 1.0) for pn in q.source_pages) / len(q.source_pages)
                            else:
                                q_ocr_avg = 1.0
                            structure_ok = len([w for w in q.warnings if w != "unmatched_answer"]) == 0
                            score, status = compute_confidence_and_status(
                                q_ocr_avg, structure_ok, q.answer_confidence, q.warnings
                            )
                            q.warnings = list(q.warnings)
                            q.confidence = score
                            q.status = status
                        db.commit()

            doc.status = "completed"
            db.commit()
            return

        # Step 3: Extract questions for question papers
        raw_questions = extract_questions_from_pages(page_texts)

        # Clear existing questions if re-processing
        db.query(Question).filter(Question.document_id == doc_id).delete()
        db.commit()

        question_records: list[Question] = []
        for rq in raw_questions:
            q_model = Question(
                document_id=doc.id,
                group_id=doc.group_id,
                question_number=rq.number,
                question_text=rq.text,
                options=rq.options,
                question_type=rq.question_type,
                source_pages=rq.source_pages,
                warnings=list(rq.warnings),
                confidence=0.5,
                status="partial",
            )
            db.add(q_model)
            question_records.append(q_model)

        db.commit()

        # Step 4: Link answers
        linked_external = False
        if doc.group_id:
            # Check for answer key document in group
            ans_doc = db.query(Document).filter(
                Document.group_id == doc.group_id,
                Document.role == "answer_key"
            ).first()
            if ans_doc:
                ans_pages = db.query(DocumentPage).filter(DocumentPage.document_id == ans_doc.id).order_by(DocumentPage.page_number).all()
                ans_text = "\n".join([ap.raw_text or "" for ap in ans_pages])
                if ans_text.strip():
                    link_answers_to_questions(question_records, ans_text, source_type="external")
                    linked_external = True

        if not linked_external:
            # Scan current doc for inline answer key
            combined_text = "\n".join([pt.text for pt in page_texts])
            if "answer key" in combined_text.lower() or "solution key" in combined_text.lower():
                link_answers_to_questions(question_records, combined_text, source_type="inline")
            else:
                for q in question_records:
                    if not q.answer:
                        q.answer_source = "none"
                        q.answer_confidence = 0.0

        # Step 5: Score & finalize
        # Build map of page ocr_confidence
        page_conf_map = {
            p.page_number: (p.ocr_confidence if p.ocr_confidence is not None else 1.0)
            for p in db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).all()
        }

        for q in question_records:
            # Calculate average OCR confidence for source pages
            if q.source_pages:
                ocr_avg = sum(page_conf_map.get(pn, 1.0) for pn in q.source_pages) / len(q.source_pages)
            else:
                ocr_avg = 1.0

            new_warns = list(q.warnings or [])
            if ocr_avg < 0.6 and "low_ocr" not in new_warns:
                new_warns.append("low_ocr")
            q.warnings = new_warns

            structure_ok = len([w for w in q.warnings if w != "unmatched_answer"]) == 0
            score, q_status = compute_confidence_and_status(
                ocr_conf=ocr_avg,
                structure_ok=structure_ok,
                answer_conf=q.answer_confidence,
                warnings=q.warnings,
            )
            q.confidence = score
            q.status = q_status

        doc.status = "completed"
        doc.error = None
        db.commit()

    except Exception as e:
        logger.exception(f"Error processing document {doc_id}: {str(e)}")
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.status = "failed"
            doc.error = str(e)
            db.commit()
    finally:
        db.close()


@celery_app.task(name="ingest_document")
def ingest_document(doc_id: str):
    run_pipeline(doc_id)
    return doc_id


@celery_app.task(name="process_document", bind=True)
def process_document_task(self, doc_id: str):
    run_pipeline(doc_id)
    return doc_id


import socket
from urllib.parse import urlparse


def _is_broker_reachable(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def dispatch_processing(doc_id: str) -> str:
    """Dispatches document to Celery if available, or falls back to synchronous processing."""
    is_eager = bool(int(getattr(settings, "celery_task_always_eager", 0)))
    if is_eager or not _is_broker_reachable(settings.redis_url):
        run_pipeline(doc_id)
        return f"sync-{doc_id}"

    try:
        res = ingest_document.apply_async(args=[doc_id])
        return str(res.id)
    except Exception as e:
        logger.info(f"Celery dispatch failed ({str(e)}). Executing pipeline synchronously.")
        run_pipeline(doc_id)
        return f"sync-{doc_id}"
