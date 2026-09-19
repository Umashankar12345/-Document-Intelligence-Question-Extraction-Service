import re
from typing import List, Dict, Any, Optional


class RawQuestion:
    def __init__(
        self,
        number: str,
        text: str,
        options: Optional[List[Dict[str, str]]] = None,
        source_pages: Optional[List[int]] = None,
        question_type: str = "unknown",
        warnings: Optional[List[str]] = None,
        bounding_boxes: Optional[List[Dict[str, Any]]] = None,
    ):
        self.number = number
        self.text = text.strip()
        self.options = options or []
        self.source_pages = source_pages or []
        self.question_type = question_type
        self.warnings = warnings or []
        self.bounding_boxes = bounding_boxes or []


class PageText:
    def __init__(self, number: int, text: str, blocks: Optional[List[Dict[str, Any]]] = None):
        self.number = number
        self.text = text
        self.blocks = blocks or []


# Matches: "1.", "1)", "1 -", "Q1.", "Q.1", "Question 1:", "IV.", "12a."
QUESTION_START_RE = re.compile(
    r"^\s*(?:Question\s+|Q\.?\s*)?(\d{1,3}[a-z]?|[IVXLCDM]{1,6})[\.\:\)\-]\s+(.*)$",
    re.IGNORECASE,
)

# Matches options: "(A) option", "A. option", "A) option", "(1) option", "1) option"
OPTION_RE = re.compile(
    r"^\s*(?:\(([A-Da-d1-4])\)|([A-Da-d1-4])[\.\)])\s+(.*)$"
)


def extract_questions_from_pages(pages: List[PageText]) -> List[RawQuestion]:
    """
    Extract structured questions, options, and cross-page splits from multi-page document text.
    """
    questions: List[RawQuestion] = []
    current_q: Optional[RawQuestion] = None

    for p in pages:
        lines = p.text.splitlines()
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # Check if line indicates an Answer Key header — stop question extraction if section reached
            if re.match(r"^\s*(?:Answer\s*Key|Answers|Solution\s*Key)[\s\:]*$", line, re.IGNORECASE):
                # Don't treat answer key header as question
                break

            q_match = QUESTION_START_RE.match(line)
            if q_match:
                # If a question was being collected, close and save it
                if current_q:
                    _finalize_question(current_q)
                    questions.append(current_q)

                q_num = q_match.group(1).strip()
                q_body = q_match.group(2).strip()

                current_q = RawQuestion(
                    number=q_num,
                    text=q_body,
                    options=[],
                    source_pages=[p.number],
                    warnings=[],
                )
                continue

            if current_q:
                # Check if this line is an option
                opt_match = OPTION_RE.match(line)
                if opt_match:
                    label = (opt_match.group(1) or opt_match.group(2)).upper()
                    opt_text = opt_match.group(3).strip()
                    current_q.options.append({"label": label, "text": opt_text})
                    current_q.question_type = "mcq"
                else:
                    # It's a continuation of the question text or a multiline option
                    if current_q.options:
                        # Append to the last option
                        current_q.options[-1]["text"] += " " + line
                    else:
                        # Append to question statement
                        current_q.text += " " + line

                if p.number not in current_q.source_pages:
                    current_q.source_pages.append(p.number)

    if current_q:
        _finalize_question(current_q)
        questions.append(current_q)

    # Cross-page checks and flags
    for q in questions:
        if len(q.source_pages) > 1:
            if "split_across_pages" not in q.warnings:
                q.warnings.append("split_across_pages")

    return questions


def _finalize_question(q: RawQuestion):
    """Refine classification and validate question structure."""
    if q.options:
        q.question_type = "mcq"
        if len(q.options) < 2:
            q.warnings.append("missing_options")
    else:
        # Check text length / keywords for short vs long
        word_count = len(q.text.split())
        if word_count > 40 or any(w in q.text.lower() for w in ["explain", "describe", "elaborate", "discuss"]):
            q.question_type = "long"
        else:
            q.question_type = "short"

    if len(q.text.strip()) < 5 and not q.options:
        q.warnings.append("low_content")
