from typing import Tuple, List, Optional
from app.config import settings


def compute_confidence_and_status(
    ocr_conf: float,
    structure_ok: bool,
    answer_conf: Optional[float] = None,
    warnings: Optional[List[str]] = None,
) -> Tuple[float, str]:
    """
    Compute composite confidence score:
      confidence = 0.5 * ocr_conf + 0.3 * structure_score + 0.2 * answer_score
    Status determination:
      confidence >= confidence_ok AND no critical warnings -> "ok"
      confidence >= confidence_partial                    -> "partial"
      otherwise                                           -> "needs_review"
    """
    warnings = warnings or []

    # Structure score: 1.0 if clean, 0.4 if structural issues/warnings present
    structure_score = 1.0 if structure_ok else 0.4

    # Answer score: use answer confidence if available, else baseline 0.5 (neutral)
    ans_score = answer_conf if answer_conf is not None else 0.5

    # Composite formula
    score = (0.5 * ocr_conf) + (0.3 * structure_score) + (0.2 * ans_score)
    score = round(max(0.0, min(1.0, score)), 3)

    # Status classification
    # If there are review-forcing warnings (e.g. low_ocr, low_content, missing_options, split_across_pages),
    # cannot be unconditionally 'ok'
    has_critical_warning = any(
        w in warnings for w in ["low_ocr", "missing_options", "low_content", "ambiguous_answer_match"]
    )

    if score >= settings.confidence_ok and not has_critical_warning:
        status = "ok"
    elif score >= settings.confidence_partial:
        status = "partial"
    else:
        status = "needs_review"

    return score, status
