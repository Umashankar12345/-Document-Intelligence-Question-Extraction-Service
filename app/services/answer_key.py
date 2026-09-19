import re
from typing import Dict, List, Optional, Tuple


# Regex to extract key-value answer pairs from answer key documents or text sections
# Matches:
# "1. A", "1) B", "1-C", "Q1: A", "Q.1 - (B)", "Question 1: C", "1. (b)", "Ans 1: A", "IV. D"
ANSWER_PATTERN = re.compile(
    r"(?:(?:Question|Ans|Q)\.?\s*)?(\d{1,3}[a-z]?|[IVXLCDM]{1,6})\s*[\.\:\)\-]+\s*\(?([A-Da-d1-4]|True|False|[A-Za-z0-9\s,\-]{1,25})\)?",
    re.IGNORECASE,
)

ANSWER_KEY_HEADER_RE = re.compile(
    r"(?:^|\n)\s*(?:Answer\s*Key|Answers|Solution\s*Key|Key\s*Answers)[\s\:\-]*\n",
    re.IGNORECASE,
)


def normalize_number(raw: Optional[str]) -> str:
    """Normalize question numbers by stripping whitespace, punctuation, leading Q/Ans, and lowercase."""
    if not raw:
        return ""
    s = raw.strip().lower()
    s = re.sub(r"^(?:question|ans|q)\.?\s*", "", s)
    s = re.sub(r"[\(\)\[\]\.\:\-\s]", "", s)
    return s


def parse_answer_key_text(text: str) -> Dict[str, List[str]]:
    """
    Parse free-text answer key into a mapping of normalized question numbers to detected answers.
    Returns dict: {normalized_q_number: [answer1, answer2]} (to detect duplicates/ambiguity).
    """
    results: Dict[str, List[str]] = {}
    
    # Check if there is an explicit Answer Key section
    header_match = ANSWER_KEY_HEADER_RE.search(text)
    section_text = text[header_match.end():] if header_match else text

    for match in ANSWER_PATTERN.finditer(section_text):
        q_raw = match.group(1)
        ans_raw = match.group(2).strip().strip("()")
        norm_key = normalize_number(q_raw)
        if norm_key:
            if norm_key not in results:
                results[norm_key] = []
            results[norm_key].append(ans_raw.upper() if len(ans_raw) == 1 else ans_raw)

    return results


def link_answers_to_questions(
    questions: list,
    answer_text: str,
    source_type: str = "external",  # "external" or "inline"
) -> Tuple[int, int]:
    """
    Given a list of Question model objects or RawQuestion objects, and the raw text of an answer key,
    matches and assigns answers, answer_source, answer_confidence, and warnings.
    Returns (matched_count, unmatched_count).
    """
    answer_map = parse_answer_key_text(answer_text)
    matched_count = 0
    unmatched_count = 0

    for q in questions:
        raw_num = getattr(q, "question_number", getattr(q, "number", None))
        norm_q = normalize_number(raw_num)
        if not norm_q or norm_q not in answer_map:
            # No answer found
            if not getattr(q, "answer", None):
                q.answer = None
                q.answer_source = "none"
                q.answer_confidence = 0.0
                if "unmatched_answer" not in q.warnings:
                    q.warnings.append("unmatched_answer")
            unmatched_count += 1
            continue

        candidate_answers = answer_map[norm_q]
        if len(candidate_answers) == 1:
            q.answer = candidate_answers[0]
            q.answer_source = source_type
            q.answer_confidence = 0.95 if len(q.answer.strip()) <= 2 else 0.85
            matched_count += 1
            # Remove unmatched_answer warning if it was previously set
            if "unmatched_answer" in q.warnings:
                q.warnings.remove("unmatched_answer")
        else:
            # Ambiguous (duplicate entries in answer key)
            q.answer = None
            q.answer_source = "none"
            q.answer_confidence = 0.2
            if "ambiguous_answer_match" not in q.warnings:
                q.warnings.append("ambiguous_answer_match")
            unmatched_count += 1

    return matched_count, unmatched_count
