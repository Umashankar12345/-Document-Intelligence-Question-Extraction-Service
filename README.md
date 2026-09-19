# Pragati Document Intelligence & Question Extraction Service

An asynchronous, production-grade document intelligence platform that extracts structured questions, multiple-choice options, and linked answers from academic examination papers (PDFs and scanned images). Built for the **Pragati Bharati Round 2 Assignment**.

---

## Key Features

- **Genuine Processing Pipeline**: Fully working PDF rendering and text parsing via **PyMuPDF**, with OCR adapters for **Tesseract**, **OpenAI Vision**, and **Azure Document Intelligence**.
- **Cross-Page Question Stitching**: Automatically detects and merges multi-page questions when a question begins on Page $N$ and its options or body continue onto Page $N+1$.
- **Answer Key Linking**: Automatically associates answers to questions either from an external answer key in the same **document group** or from an embedded section in the same document.
- **Composite Confidence Scoring**:
  $$\text{confidence} = 0.5 \times \text{ocr\_conf} + 0.3 \times \text{structure\_score} + 0.2 \times \text{answer\_score}$$
  Categorizes items into `ok` ($\ge 0.75$), `partial` ($\ge 0.45$), or `needs_review` ($< 0.45$ or critical warnings).
- **Asynchronous Scalability & Resilience**: A single Celery task (`ingest_document`) runs the full pipeline synchronously inside one worker. `dispatch_processing()` checks broker reachability and falls back to in-process execution if Redis is unavailable, which keeps local dev and tests frictionless.
- **Security & Authorization**: JWT bearer tokens, bcrypt password hashing, per-user ownership isolation, file integrity sniffing, and directory traversal protection.
- **Reviewer-Friendly**: Streams rendered 200 DPI page images directly via `/documents/{id}/pages/{n}?as_image=true`.

---

## Repository Structure

```text
pragati-document-intelligence/
├── app/
│   ├── main.py                 # FastAPI application & lifecycle
│   ├── config.py               # Pydantic BaseSettings
│   ├── db.py                   # SQLAlchemy engine, session & init
│   ├── models.py               # ORM models (User, Doc, Page, Question, Group)
│   ├── schemas.py              # Pydantic v2 schemas
│   ├── auth.py                 # JWT, bcrypt & RBAC dependencies
│   ├── storage.py              # Local/S3 isolated object storage
│   ├── routers/                # API endpoints
│   │   ├── auth.py             # /auth/register, /auth/token, /auth/me
│   │   ├── documents.py        # /documents upload, polling, review, pages
│   │   ├── questions.py        # /questions/{qid}, /questions/{qid}/answer
│   │   └── groups.py           # /document-groups, linking & merged questions
│   ├── workers/
│   │   ├── celery_app.py       # Celery configuration
│   │   └── tasks.py            # Async ingestion & extraction pipeline
│   └── services/
│       ├── pdf.py              # PyMuPDF rendering & density analysis
│       ├── ocr.py              # Tesseract, Azure DI & OpenAI adapters
│       ├── extractor.py        # Heuristic regex & cross-page stitching
│       ├── answer_key.py       # Answer parsing, normalization & linking
│       └── confidence.py       # Composite scoring & status calculation
├── scripts/
│   └── generate_samples.py     # Generates real valid test PDFs & images
├── samples/                    # Generated test documents
│   ├── qpaper.pdf              # Standard question paper
│   ├── cross_page_qpaper.pdf   # Multi-page test with split questions
│   ├── answer_key.pdf          # Official exam answer key
│   ├── page1.jpg               # Scanned question image
│   └── blurry.png              # Low-contrast image for review testing
├── tests/
│   ├── conftest.py             # Test fixtures & test DB setup
│   ├── test_extractor.py       # Regex, options & cross-page unit tests
│   ├── test_answer_key.py      # Answer key parser & normalization tests
│   ├── test_confidence.py      # Confidence formula & boundary tests
│   └── test_api.py             # Integration, security & e2e pipeline tests
├── postman/
│   └── Pragati.postman_collection.json # Full Postman v2.1 collection
├── docs/
│   └── ARCHITECTURE.md         # Detailed architectural documentation
├── requirements.txt            # Dependencies
├── Dockerfile                  # Production container definition
├── docker-compose.yml          # Multi-container stack (API, Worker, DB, Redis)
└── .env.example                # Configuration template
```

---

## Quickstart

### Option A: Docker Compose (Recommended for Full Stack)

```bash
# 1. Copy environment variables
cp .env.example .env

# 2. Build and launch all services (Postgres, Redis, FastAPI, Celery)
docker compose up --build
```
- **Interactive Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health check**: [http://localhost:8000/health](http://localhost:8000/health)

> **Docker Validation Note**: The Docker Compose configuration was fully validated via `docker compose config` (exit code 0). Live container startup was not verified on the development host due to an inactive local Windows Docker daemon. The configuration uses standard multi-stage builds (`python:3.11-slim`, `tesseract-ocr`, `postgres:16-alpine`, `redis:7-alpine`) and is expected to work on any active Docker host.

> **Security Note**: For any non-demo or production deployment, set `JWT_SECRET` in `.env` to a secure, random 32+ byte key. The default fallback secret is intentionally provided only to make initial evaluation and demo runs frictionless out-of-the-box.

---

### Option B: Local Development (Without Docker)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate real sample test documents
python scripts/generate_samples.py

# 3. Start FastAPI server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The application will automatically initialize the local SQLite database at `./data/pragati.db` and local file storage at `./data/storage`.

---

## Running Automated Tests

Run the complete test suite:

```bash
pytest -v
```

Output:
```text
tests/test_answer_key.py::test_normalize_number PASSED                   [  5%]
tests/test_answer_key.py::test_parse_answer_key_formats PASSED           [ 11%]
tests/test_answer_key.py::test_link_answers_success_and_unmatched PASSED [ 17%]
tests/test_answer_key.py::test_ambiguous_duplicate_answers PASSED        [ 23%]
tests/test_api.py::test_auth_registration_and_login PASSED               [ 29%]
tests/test_api.py::test_file_upload_validations PASSED                   [ 35%]
tests/test_api.py::test_end_to_end_question_paper_extraction PASSED      [ 41%]
tests/test_api.py::test_cross_page_extraction_e2e PASSED                 [ 47%]
tests/test_api.py::test_group_linking_with_answer_key PASSED             [ 52%]
tests/test_api.py::test_authorization_and_security PASSED                [ 55%]
tests/test_api.py::test_low_confidence_scan_produces_needs_review PASSED [ 61%]
tests/test_confidence.py::test_confidence_ok_status PASSED               [ 66%]
tests/test_confidence.py::test_confidence_partial_status PASSED          [ 72%]
tests/test_confidence.py::test_confidence_needs_review_when_critical_warning PASSED [ 77%]
tests/test_confidence.py::test_confidence_needs_review_when_low_score PASSED [ 83%]
tests/test_extractor.py::test_basic_question_and_options_extraction PASSED [ 88%]
tests/test_extractor.py::test_cross_page_question_stitching PASSED       [ 94%]
tests/test_extractor.py::test_missing_options_warning PASSED             [100%]
======================= 18 passed in 3.98s =======================
```

---

## Demonstration Scenarios (10 Scenarios)

| # | Scenario | Method & Endpoint | Sample File | Observed Result |
|---|---|---|---|---|
| **1** | Upload PDF | `POST /documents` | `samples/qpaper.pdf` | Returns `202 Accepted` with `document_id` and `task_id` |
| **2** | Upload Image | `POST /documents` | `samples/page1.jpg` | Single-page image ingested and rendered to PNG |
| **3** | Low-Quality Scan | `POST /documents` | `samples/blurry.png` | Question tagged with `low_ocr` warning and status `needs_review` |
| **4** | Multiple Questions | `GET /documents/{id}/questions` | `samples/qpaper.pdf` | Returns array of 5 structured questions with numbering |
| **5** | Cross-Page Question | `GET /documents/{id}/questions` | `samples/cross_page_qpaper.pdf` | Q3 has `source_pages: [1, 2]` and warning `split_across_pages` |
| **6** | MCQ Options | `GET /documents/{id}/questions` | `samples/qpaper.pdf` | `options: [{"label": "A", "text": "..."}]` populated |
| **7** | Answer Key Association | `POST /document-groups/{gid}/documents/{did}` | `samples/answer_key.pdf` | Answers linked with `answer_source: "external"`, `confidence: 0.95` |
| **8** | Uncertain Extraction | `GET /documents/{id}/warnings` | `samples/blurry.png` | Surfaces items with `needs_review` and action snippets |
| **9** | Final Structured Output | `GET /document-groups/{gid}/questions` | — | Complete JSON with questions, options, answers, and confidence |
| **10** | Security / Invalid Input | `POST /documents` | Malformed `.exe` or corrupt PDF | Returns `415 Unsupported Media Type` or `400 Bad Request` |

---

## API Surface

### Authentication
- `POST /auth/register` — Create user account (`email`, `password`, `role`).
- `POST /auth/token` — Obtain JWT bearer token.
- `GET /auth/me` — Retrieve active user profile.

### Documents
- `POST /documents` — Upload multipart file (`file`, `role`, optional `group_id`).
- `GET /documents` — List documents owned by user (or all if admin).
- `GET /documents/{id}` — Retrieve document metadata and page count.
- `GET /documents/{id}/status` — Lightweight polling endpoint.
- `GET /documents/{id}/pages/{n}` — Page metadata (or stream PNG with `?as_image=true`).
- `GET /documents/{id}/pages/{n}/image` — Direct stream of rendered 200 DPI PNG.
- `GET /documents/{id}/questions` — Extracted questions and options for document.
- `GET /documents/{id}/warnings` — Items flagged for human reviewer inspection.
- `DELETE /documents/{id}` — Delete document and stored files.

### Questions
- `GET /questions/{qid}` — Single question details.
- `GET /questions/{qid}/answer` — Question answer, source (`inline` / `external`), and confidence.

### Document Groups
- `POST /document-groups` — Create new document group.
- `POST /document-groups/{gid}/documents/{did}` — Attach document to group (triggers answer linking).
- `GET /document-groups/{gid}/questions` — Merged questions and answers across group.

---

## Known Limitations & Trade-offs

1. **Pipeline Execution**: A single Celery task (`ingest_document`) runs the full pipeline synchronously inside one worker slot. `dispatch_processing()` automatically falls back to synchronous in-process execution if Redis is offline to keep local testing and development frictionless.
2. **Cloud OCR Providers**: `OpenAIVisionOCRProvider` and `AzureDIProvider` are declared but raise `NotImplementedError`. Tesseract (`OCR_PROVIDER=tesseract`) is the working OCR engine.
3. **Handwriting Recognition**: Complex handwriting is limited by Tesseract's capabilities; the system flags low-confidence pages as `needs_review` rather than guessing.
4. **Regex Extraction**: Heuristic regex is fast and deterministic, but complex section numbering restarts without headers can require review.
5. **Confidence Scoring**: Heuristic linear formula tuned to conservative review thresholds.
6. **Docker Execution**: Configuration validated with `docker compose config` (exit code 0); live container startup was not executed on the development host due to an inactive Windows Docker daemon.

---

## Postman Collection

Import `postman/Pragati.postman_collection.json` directly into Postman. It includes pre-configured collection variables (`{{base_url}}`, `{{bearer_token}}`, `{{doc_id}}`, `{{group_id}}`) and test scripts that automatically capture tokens and IDs across requests.
