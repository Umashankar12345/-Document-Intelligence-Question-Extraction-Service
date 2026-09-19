from app.services.extractor import extract_questions_from_pages, PageText


def test_basic_question_and_options_extraction():
    text = """
    1. What is the capital of France?
    (A) Berlin
    (B) Madrid
    (C) Paris
    (D) Rome

    2. Explain the second law of thermodynamics.
    """
    pages = [PageText(number=1, text=text)]
    questions = extract_questions_from_pages(pages)

    assert len(questions) == 2
    
    # Check question 1
    q1 = questions[0]
    assert q1.number == "1"
    assert "capital of France" in q1.text
    assert q1.question_type == "mcq"
    assert len(q1.options) == 4
    assert q1.options[0]["label"] == "A"
    assert q1.options[0]["text"] == "Berlin"
    assert q1.options[2]["label"] == "C"
    assert q1.options[2]["text"] == "Paris"
    assert q1.source_pages == [1]
    assert "split_across_pages" not in q1.warnings

    # Check question 2
    q2 = questions[1]
    assert q2.number == "2"
    assert "second law of thermodynamics" in q2.text
    assert q2.question_type in ("short", "long")
    assert len(q2.options) == 0


def test_cross_page_question_stitching():
    # Question 3 starts at bottom of page 1, options are on page 2
    page1 = PageText(
        number=1,
        text="""
        1. Simple MCQ
        (A) Yes
        (B) No

        2. Which protocol ensures reliable byte streams across networks?
        """,
    )
    page2 = PageText(
        number=2,
        text="""
        (A) UDP
        (B) TCP
        (C) ICMP
        (D) ARP

        3. Next Question
        """,
    )

    questions = extract_questions_from_pages([page1, page2])
    assert len(questions) == 3

    # Verify Question 2 crossed page 1 into page 2
    q2 = questions[1]
    assert q2.number == "2"
    assert "reliable byte streams" in q2.text
    assert q2.question_type == "mcq"
    assert len(q2.options) == 4
    assert q2.source_pages == [1, 2]
    assert "split_across_pages" in q2.warnings


def test_missing_options_warning():
    text = """
    1. Broken question with only one option
    (A) Lone Option
    """
    questions = extract_questions_from_pages([PageText(number=1, text=text)])
    assert len(questions) == 1
    assert "missing_options" in questions[0].warnings
