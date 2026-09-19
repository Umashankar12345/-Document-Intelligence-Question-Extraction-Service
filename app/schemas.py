from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# Auth Schemas
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: Optional[str] = "user"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: str
    created_at: Optional[datetime] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None


# Document Group Schemas
class DocumentGroupCreate(BaseModel):
    name: Optional[str] = None


class DocumentGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    name: Optional[str]
    created_at: Optional[datetime]


# Question Schemas
class QuestionOption(BaseModel):
    label: str
    text: str


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    group_id: Optional[str] = None
    question_number: Optional[str] = None
    question_text: Optional[str] = None
    options: Optional[List[Dict[str, Any]]] = None
    question_type: str = "unknown"
    answer: Optional[str] = None
    answer_source: str = "none"
    answer_confidence: Optional[float] = None
    source_pages: List[int] = []
    bounding_boxes: Optional[Any] = None
    confidence: float
    status: str
    warnings: List[str] = []
    created_at: Optional[datetime] = None


class QuestionAnswerOut(BaseModel):
    question_id: str
    question_number: Optional[str]
    answer: Optional[str]
    answer_source: str
    answer_confidence: Optional[float]
    status: str


# Document Schemas
class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    group_id: Optional[str] = None
    role: str
    filename: str
    mime_type: str
    size_bytes: int
    storage_key: str
    checksum: Optional[str] = None
    status: str
    error: Optional[str] = None
    page_count: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DocumentUploadResponse(BaseModel):
    document_id: str
    task_id: Optional[str] = None
    filename: str
    status: str
    role: str
    group_id: Optional[str] = None


class DocumentStatusOut(BaseModel):
    document_id: str
    status: str
    page_count: Optional[int] = None
    error: Optional[str] = None
    updated_at: Optional[datetime] = None


class DocumentPageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    page_number: int
    image_key: Optional[str] = None
    raw_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    rotation_deg: int = 0


class QuestionWarningItem(BaseModel):
    question_id: str
    question_number: Optional[str]
    status: str
    confidence: float
    warnings: List[str]
    snippet: Optional[str] = None


class DocumentWarningsOut(BaseModel):
    document_id: str
    total_questions: int
    needs_review_count: int
    partial_count: int
    items: List[QuestionWarningItem]
