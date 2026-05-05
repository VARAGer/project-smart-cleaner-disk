"""Pydantic v2 schemas for request/response validation."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ===== Authentication =====

class AuthRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Логин пользователя (3-50 символов)",
    )
    password: str = Field(
        ...,
        min_length=10,
        max_length=128,
        description="Пароль: минимум 10 символов, хотя бы одна буква и одна цифра",
    )

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace("_", "").isalnum():
            raise ValueError(
                "Логин может содержать только буквы, цифры и _"
            )
        return v

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        # Length is enforced by Field(min_length=10) above; here we require at
        # least one letter AND one digit. Cheap, predictable, and rejects the
        # most common weak passwords ("aaaaaaaaaa", "1234567890", "password").
        has_letter = any(c.isalpha() for c in v)
        has_digit = any(c.isdigit() for c in v)
        if not (has_letter and has_digit):
            raise ValueError(
                "Пароль должен содержать хотя бы одну букву и одну цифру"
            )
        return v


class AuthResponse(BaseModel):
    user_id: str
    username: str
    access_token: str
    token_type: str = "bearer"


# ===== File analysis =====

class FileMetadata(BaseModel):
    file_id: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Уникальный ID файла (MD5 хеш от пути)",
    )
    filename: str = Field(
        ...,
        max_length=500,
        description="Имя файла",
    )
    extension: str = Field(
        default="",
        max_length=20,
        description="Расширение файла (.docx, .exe и т.д.)",
    )
    size_bytes: int = Field(
        ...,
        ge=0,
        description="Размер файла в байтах",
    )
    modified_at: str = Field(
        ...,
        description="Дата последней модификации (ISO 8601)",
    )
    accessed_at: Optional[str] = Field(
        default=None,
        description="Дата последнего доступа (ISO 8601)",
    )
    parent_dir: str = Field(
        default="",
        max_length=1000,
        description="Родительская директория",
    )


class AnalysisRequest(BaseModel):
    scan_id: str = Field(
        ...,
        description="Идентификатор батча сканирования",
    )
    files: list[FileMetadata] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Список файлов для анализа (макс. 200)",
    )


class FileClassification(BaseModel):
    file_id: str
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Уверенность в безопасности удаления (0.0-1.0)",
    )
    category: str = Field(
        ...,
        description="Категория файла",
    )
    reason: str = Field(
        ...,
        description="Причина рекомендации на русском языке",
    )


class AnalysisResponse(BaseModel):
    scan_id: str
    classifications: list[FileClassification]
