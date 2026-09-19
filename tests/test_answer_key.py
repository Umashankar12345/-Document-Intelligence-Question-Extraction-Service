from app.services.answer_key import normalize_number, parse_answer_key_text, link_answers_to_questions
from app.services.extractor import RawQuestion


def test_normalize_number():
    assert normalize_number("1.") == "1"
    assert normalize_number("Q. 1") == "1"
    assert normalize_number("Question 12a") == "12a"
    assert normalize_number("1(b)") == "1b"
    assert normalize_number("Ans 4:") == "4"


def test_parse_answer_key_formats():
    text = """
    Answer Key
    1. B
    2. (C)
    Q3: A
    Question 4 - D
    5. True
    """
    answers = parse_answer_key_text(text)
    assert answers["1"] == ["B"]
    assert answers["2"] == ["C"]
    assert answers["3"] == ["A"]
    assert answers["4"] == ["D"]
    assert answers["5"] == ["True"]


def test_link_answers_success_and_unmatched():
    questions = [
        RawQuestion(number="1", text="Question 1"),
        RawQuestion(number="2", text="Question 2"),
        RawQuestion(number="3", text="Question 3 without key"),
    ]

    key_text = """
    1. A
    2. B
    """

    matched, unmatched = link_answers_to_questions(questions, key_text, source_type="external")
    assert matched == 2
    assert unmatched == 1

    assert questions[0].answer == "A"
    assert questions[0].answer_source == "external"
    assert questions[0].answer_confidence == 0.95

    assert questions[1].answer == "B"
    assert questions[1].answer_source == "external"

    assert questions[2].answer is None
    assert questions[2].answer_source == "none"
    assert "unmatched_answer" in questions[2].warnings


def test_ambiguous_duplicate_answers():
    questions = [RawQuestion(number="1", text="Question 1")]
    # Duplicate answer for question 1 in key
    key_text = """
    1. A
    1. C
    """
    matched, unmatched = link_answers_to_questions(questions, key_text)
    assert matched == 0
    assert unmatched == 1
    assert questions[0].answer is None
    assert "ambiguous_answer_match" in questions[0].warnings
