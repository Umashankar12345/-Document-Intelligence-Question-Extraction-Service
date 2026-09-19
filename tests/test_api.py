import os
from pathlib import Path
import pytest
from app.config import settings

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def test_auth_registration_and_login(client):
    # Register new user
    reg_resp = client.post(
        "/auth/register",
        json={"email": "newstudent@pragati.edu", "password": "SecurePassword123!", "role": "user"},
    )
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()
    assert user_data["email"] == "newstudent@pragati.edu"
    assert "id" in user_data

    # Duplicate registration should fail with 400
    dup_resp = client.post(
        "/auth/register",
        json={"email": "newstudent@pragati.edu", "password": "SecurePassword123!"},
    )
    assert dup_resp.status_code == 400

    # Login and obtain JWT token
    login_resp = client.post(
        "/auth/token",
        data={"username": "newstudent@pragati.edu", "password": "SecurePassword123!"},
    )
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"


def test_file_upload_validations(client, user_headers):
    # 1. Unsupported media type (e.g. .exe or .txt) -> 415
    resp_415 = client.post(
        "/documents",
        headers=user_headers,
        files={"file": ("malicious.exe", b"MZ fake executable data", "application/x-msdownload")},
    )
    assert resp_415.status_code == 415

    # 2. Corrupt PDF -> 400
    resp_400 = client.post(
        "/documents",
        headers=user_headers,
        files={"file": ("broken.pdf", b"%PDF-corrupted-binary-trash", "application/pdf")},
    )
    assert resp_400.status_code == 400

    # 3. Oversized file -> 413
    old_limit = settings.max_upload_mb
    settings.max_upload_mb = 1  # 1 MB temporary limit for test
    try:
        large_bytes = b"0" * (2 * 1024 * 1024)
        resp_413 = client.post(
            "/documents",
            headers=user_headers,
            files={"file": ("large.pdf", large_bytes, "application/pdf")},
        )
        assert resp_413.status_code == 413
    finally:
        settings.max_upload_mb = old_limit


def test_end_to_end_question_paper_extraction(client, user_headers):
    qpaper_path = SAMPLES_DIR / "qpaper.pdf"
    assert qpaper_path.exists(), "samples/qpaper.pdf must exist"

    with open(qpaper_path, "rb") as f:
        file_bytes = f.read()

    # Upload question paper
    upload_resp = client.post(
        "/documents",
        headers=user_headers,
        files={"file": ("qpaper.pdf", file_bytes, "application/pdf")},
        data={"role": "question_paper"},
    )
    assert upload_resp.status_code == 202
    doc_id = upload_resp.json()["document_id"]
    assert doc_id

    # Check status polling endpoint
    status_resp = client.get(f"/documents/{doc_id}/status", headers=user_headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] == "completed"
    assert status_data["page_count"] == 1

    # Fetch extracted questions
    q_resp = client.get(f"/documents/{doc_id}/questions", headers=user_headers)
    assert q_resp.status_code == 200
    questions = q_resp.json()
    assert len(questions) >= 5

    # Verify MCQ options are populated
    q1 = next((q for q in questions if q["question_number"] == "1"), None)
    assert q1 is not None
    assert q1["question_type"] == "mcq"
    assert len(q1["options"]) == 4
    assert q1["options"][1]["label"] == "B"

    # Verify single question endpoint
    single_q_resp = client.get(f"/questions/{q1['id']}", headers=user_headers)
    assert single_q_resp.status_code == 200
    assert single_q_resp.json()["id"] == q1["id"]

    # Verify warnings endpoint
    warn_resp = client.get(f"/documents/{doc_id}/warnings", headers=user_headers)
    assert warn_resp.status_code == 200
    warn_data = warn_resp.json()
    assert "total_questions" in warn_data
    assert warn_data["total_questions"] == len(questions)


def test_cross_page_extraction_e2e(client, user_headers):
    cross_path = SAMPLES_DIR / "cross_page_qpaper.pdf"
    assert cross_path.exists(), "samples/cross_page_qpaper.pdf must exist"

    with open(cross_path, "rb") as f:
        file_bytes = f.read()

    upload_resp = client.post(
        "/documents",
        headers=user_headers,
        files={"file": ("cross_page_qpaper.pdf", file_bytes, "application/pdf")},
    )
    assert upload_resp.status_code == 202
    doc_id = upload_resp.json()["document_id"]

    q_resp = client.get(f"/documents/{doc_id}/questions", headers=user_headers)
    assert q_resp.status_code == 200
    questions = q_resp.json()

    # Question 3 spanned page 1 and page 2
    q3 = next((q for q in questions if q["question_number"] == "3"), None)
    assert q3 is not None
    assert "split_across_pages" in q3["warnings"]
    assert 1 in q3["source_pages"] and 2 in q3["source_pages"]
    assert len(q3["options"]) == 4


def test_group_linking_with_answer_key(client, user_headers):
    # 1. Create a document group
    grp_resp = client.post(
        "/document-groups",
        headers=user_headers,
        json={"name": "Midterm Exam 2026"},
    )
    assert grp_resp.status_code == 201
    group_id = grp_resp.json()["id"]

    # 2. Upload Question Paper attached to group
    with open(SAMPLES_DIR / "qpaper.pdf", "rb") as f:
        qp_bytes = f.read()

    qp_resp = client.post(
        "/documents",
        headers=user_headers,
        files={"file": ("qpaper.pdf", qp_bytes, "application/pdf")},
        data={"role": "question_paper", "group_id": group_id},
    )
    qp_doc_id = qp_resp.json()["document_id"]

    # 3. Upload Answer Key attached to group
    with open(SAMPLES_DIR / "answer_key.pdf", "rb") as f:
        ak_bytes = f.read()

    ak_resp = client.post(
        "/documents",
        headers=user_headers,
        files={"file": ("answer_key.pdf", ak_bytes, "application/pdf")},
        data={"role": "answer_key", "group_id": group_id},
    )
    ak_doc_id = ak_resp.json()["document_id"]

    # 4. Query group questions to confirm answers matched
    group_q_resp = client.get(f"/document-groups/{group_id}/questions", headers=user_headers)
    assert group_q_resp.status_code == 200
    group_qs = group_q_resp.json()
    assert len(group_qs) >= 5

    # Check that answers are populated
    q1 = next((q for q in group_qs if q["question_number"] == "1"), None)
    assert q1 is not None
    assert q1["answer"] == "B"
    assert q1["answer_source"] == "external"

    q2 = next((q for q in group_qs if q["question_number"] == "2"), None)
    assert q2 is not None
    assert q2["answer"] == "C"

    # Query single question answer endpoint
    ans_resp = client.get(f"/questions/{q1['id']}/answer", headers=user_headers)
    assert ans_resp.status_code == 200
    ans_data = ans_resp.json()
    assert ans_data["answer"] == "B"
    assert ans_data["answer_source"] == "external"


def test_authorization_and_security(client, user_headers, other_headers, admin_headers):
    # User A uploads a document
    with open(SAMPLES_DIR / "qpaper.pdf", "rb") as f:
        qp_bytes = f.read()

    doc_resp = client.post(
        "/documents",
        headers=user_headers,
        files={"file": ("private_paper.pdf", qp_bytes, "application/pdf")},
    )
    doc_id = doc_resp.json()["document_id"]

    # User B tries to view User A's document -> 403 Forbidden
    resp_forbidden = client.get(f"/documents/{doc_id}", headers=other_headers)
    assert resp_forbidden.status_code == 403

    # User B tries to delete User A's document -> 403 Forbidden
    del_forbidden = client.delete(f"/documents/{doc_id}", headers=other_headers)
    assert del_forbidden.status_code == 403

    # Admin user CAN view User A's document -> 200 OK
    admin_view = client.get(f"/documents/{doc_id}", headers=admin_headers)
    assert admin_view.status_code == 200
    assert admin_view.json()["id"] == doc_id

    # Unauthenticated request -> 401 Unauthorized
    unauth = client.get(f"/documents/{doc_id}")
    assert unauth.status_code == 401

    # Owner deletes document -> 204 No Content
    owner_delete = client.delete(f"/documents/{doc_id}", headers=user_headers)
    assert owner_delete.status_code == 204

    # Confirm it is deleted
    assert client.get(f"/documents/{doc_id}", headers=user_headers).status_code == 404


def test_low_confidence_scan_produces_needs_review(client, user_headers, monkeypatch):
    """Simulates OCR returning low confidence on a real image upload."""
    from app.services import ocr

    # Monkeypatch the OCR provider to return low-confidence extraction
    class LowConfOCR(ocr.BaseOCRProvider):
        def ocr_image(self, image_bytes):
            return ocr.OCRResult(
                text="1. W??t is the c?pit?l of F??nce?\n(A) P?ris\n(B) L?ndon",
                confidence=0.32,
                rotation_deg=0,
            )

    monkeypatch.setattr(ocr, "get_ocr_provider", lambda: LowConfOCR())
    with open(SAMPLES_DIR / "blurry.png", "rb") as f:
        r = client.post(
            "/documents",
            headers=user_headers,
            files={"file": ("blurry.png", f, "image/png")},
        )
    assert r.status_code == 202
    doc_id = r.json()["document_id"]
    r = client.get(f"/documents/{doc_id}/warnings", headers=user_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) > 0
    assert any("low_ocr" in i["warnings"] for i in items), \
        "Expected at least one low_ocr warning"
    assert any(i["status"] == "needs_review" for i in items), \
        "Expected at least one needs_review question"

