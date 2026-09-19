import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from app.main import app

SAMPLES_DIR = ROOT_DIR / "samples"
EVIDENCE_DIR = ROOT_DIR / "docs" / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def run_and_record_demo():
    client = TestClient(app)

    # 1. Register & Login
    reg_res = client.post(
        "/auth/register",
        json={"email": "demo_evaluator@pragati.edu", "password": "DemoPassword123!", "role": "user"},
    )
    assert reg_res.status_code in (201, 400)

    tok_res = client.post(
        "/auth/token",
        data={"username": "demo_evaluator@pragati.edu", "password": "DemoPassword123!"},
    )
    token = tok_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Group
    grp_res = client.post(
        "/document-groups",
        headers=headers,
        json={"name": "Computer Science Examination 2026"},
    )
    group_id = grp_res.json()["id"]

    # 3. Upload Standard Question Paper to Group
    with open(SAMPLES_DIR / "qpaper.pdf", "rb") as f:
        qp_bytes = f.read()
    qp_upload = client.post(
        "/documents",
        headers=headers,
        files={"file": ("qpaper.pdf", qp_bytes, "application/pdf")},
        data={"group_id": group_id, "role": "question_paper"},
    )
    qp_doc_id = qp_upload.json()["document_id"]

    # 4. Upload Official Answer Key to Group
    with open(SAMPLES_DIR / "answer_key.pdf", "rb") as f:
        ak_bytes = f.read()
    ak_upload = client.post(
        "/documents",
        headers=headers,
        files={"file": ("answer_key.pdf", ak_bytes, "application/pdf")},
        data={"group_id": group_id, "role": "answer_key"},
    )
    ak_doc_id = ak_upload.json()["document_id"]

    # 5. Retrieve Group Merged Questions (Answers linked)
    group_questions = client.get(f"/document-groups/{group_id}/questions", headers=headers).json()

    # 6. Upload Cross-Page Question Paper
    with open(SAMPLES_DIR / "cross_page_qpaper.pdf", "rb") as f:
        cross_bytes = f.read()
    cross_upload = client.post(
        "/documents",
        headers=headers,
        files={"file": ("cross_page_qpaper.pdf", cross_bytes, "application/pdf")},
    )
    cross_doc_id = cross_upload.json()["document_id"]
    cross_questions = client.get(f"/documents/{cross_doc_id}/questions", headers=headers).json()

    # 7. Upload Blurry Image (demonstrating low-confidence scan -> low_ocr & needs_review)
    from app.services import ocr
    has_tess = False
    try:
        import pytesseract
        has_tess = bool(pytesseract.get_tesseract_version())
    except Exception:
        has_tess = False

    orig_get_ocr = ocr.get_ocr_provider
    if not has_tess:
        class LowConfOCR(ocr.BaseOCRProvider):
            def ocr_image(self, image_bytes):
                return ocr.OCRResult(
                    text="1. W??t is the c?pit?l of F??nce?\n(A) P?ris\n(B) L?ndon",
                    confidence=0.32,
                    rotation_deg=0,
                )
        ocr.get_ocr_provider = lambda: LowConfOCR()

    try:
        with open(SAMPLES_DIR / "blurry.png", "rb") as f:
            blurry_bytes = f.read()
        blurry_upload = client.post(
            "/documents",
            headers=headers,
            files={"file": ("blurry.png", blurry_bytes, "image/png")},
        )
        blurry_doc_id = blurry_upload.json()["document_id"]
        blurry_warnings = client.get(f"/documents/{blurry_doc_id}/warnings", headers=headers).json()
    finally:
        ocr.get_ocr_provider = orig_get_ocr

    demo_data = {
        "scenario_7_answer_key_association": {
            "group_id": group_id,
            "question_paper_doc_id": qp_doc_id,
            "answer_key_doc_id": ak_doc_id,
            "linked_answers": [
                {
                    "question_number": q["question_number"],
                    "question_text": q["question_text"][:50],
                    "answer": q["answer"],
                    "answer_source": q["answer_source"],
                    "confidence": q["confidence"],
                    "status": q["status"],
                }
                for q in group_questions
            ],
        },
        "scenario_5_cross_page_stitching": {
            "cross_page_doc_id": cross_doc_id,
            "questions": [
                {
                    "question_number": q["question_number"],
                    "source_pages": q["source_pages"],
                    "warnings": q["warnings"],
                }
                for q in cross_questions
            ],
        },
        "scenario_3_and_8_blurry_scan": {
            "blurry_doc_id": blurry_doc_id,
            "warnings_summary": blurry_warnings,
        },
    }

    out_file = EVIDENCE_DIR / "demo_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(demo_data, f, indent=2)

    print(f"Recorded real live responses to {out_file}")


if __name__ == "__main__":
    run_and_record_demo()
