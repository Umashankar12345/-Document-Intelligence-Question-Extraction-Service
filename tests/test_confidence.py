from app.services.confidence import compute_confidence_and_status


def test_confidence_ok_status():
    # High OCR, structure clean, high answer confidence, no warnings
    score, status = compute_confidence_and_status(
        ocr_conf=0.95,
        structure_ok=True,
        answer_conf=0.9,
        warnings=[],
    )
    # 0.5*0.95 (0.475) + 0.3*1.0 (0.3) + 0.2*0.9 (0.18) = 0.955
    assert score >= 0.75
    assert status == "ok"


def test_confidence_partial_status():
    # Moderate OCR or minor structure issue without critical review warning
    score, status = compute_confidence_and_status(
        ocr_conf=0.7,
        structure_ok=True,
        answer_conf=0.0,
        warnings=[],
    )
    # 0.5*0.7 (0.35) + 0.3*1.0 (0.30) + 0.2*0.0 (0) = 0.65
    assert 0.45 <= score < 0.75
    assert status == "partial"


def test_confidence_needs_review_when_critical_warning():
    # Even if mathematical score is high, a warning like 'low_ocr' or 'missing_options' forces 'needs_review'
    score, status = compute_confidence_and_status(
        ocr_conf=0.4,
        structure_ok=False,
        answer_conf=0.2,
        warnings=["low_ocr"],
    )
    assert status == "needs_review"


def test_confidence_needs_review_when_low_score():
    score, status = compute_confidence_and_status(
        ocr_conf=0.2,
        structure_ok=False,
        answer_conf=0.0,
        warnings=[],
    )
    assert score < 0.45
    assert status == "needs_review"
