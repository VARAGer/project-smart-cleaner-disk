from __future__ import annotations

import os
import re
from dataclasses import dataclass


REVIEW_CONFIDENCE_CAP = 0.49
LOCAL_PROTECTION_PREFIX = "Локальная защита"

HIGH_RISK_EXTENSIONS = {
    ".bak",
    ".config",
    ".crt",
    ".cs",
    ".cpp",
    ".db",
    ".env",
    ".ini",
    ".java",
    ".js",
    ".key",
    ".kdbx",
    ".pem",
    ".pfx",
    ".py",
    ".sql",
    ".sqlite",
    ".ts",
    ".wallet",
    ".yaml",
    ".yml",
}

HIGH_RISK_CATEGORIES = {
    "code",
    "config",
    "database",
}

HIGH_RISK_KEYWORDS = {
    "bank",
    "birthday",
    "certificate",
    "contract",
    "cv",
    "diploma",
    "family",
    "final",
    "important",
    "invoice",
    "key",
    "license",
    "medical",
    "passport",
    "personal",
    "photo",
    "project",
    "receipt",
    "report",
    "restore",
    "resume",
    "salary",
    "seed",
    "tax",
    "thesis",
    "wallet",
    "wedding",
    "work",
    "банк",
    "важно",
    "восстановление",
    "деньги",
    "диплом",
    "договор",
    "зарплата",
    "ключ",
    "кошелек",
    "кошелёк",
    "курсовая",
    "лицензия",
    "медицина",
    "налог",
    "отчет",
    "отчёт",
    "паспорт",
    "проект",
    "работа",
    "резерв",
    "сертификат",
    "семья",
    "счет",
    "счёт",
    "фото",
    "финал",
}

HIGH_RISK_PHRASES = {
    "рабочий стол",
    "seed phrase",
}

RISKY_PARENT_TOKENS = {
    "desktop",
    "documents",
    "docs",
    "finance",
    "medical",
    "projects",
    "source",
    "src",
    "study",
    "university",
    "work",
    "документы",
    "проекты",
    "работа",
    "стол",
    "учеба",
    "учёба",
}

PARENT_SENSITIVE_CATEGORIES = {
    "code",
    "config",
    "database",
    "document",
    "media",
    "other",
}


@dataclass(frozen=True)
class RiskDecision:
    max_confidence: float
    reason: str


def apply_deterministic_risk_downgrades(
    files: list[dict],
    classifications: list[dict],
) -> list[dict]:
    files_by_id = {str(file_info.get("file_id", "")): file_info for file_info in files}
    return [
        apply_deterministic_risk_downgrade(
            files_by_id.get(str(classification.get("file_id", "")), {}),
            classification,
        )
        for classification in classifications
    ]


def apply_deterministic_risk_downgrade(
    file_info: dict,
    classification: dict,
) -> dict:
    decision = evaluate_file_risk(file_info, classification)
    if decision is None:
        return dict(classification)

    adjusted = dict(classification)
    confidence = _safe_float(adjusted.get("confidence"), default=0.5)
    adjusted["confidence"] = min(confidence, decision.max_confidence)
    adjusted["reason"] = _append_local_reason(
        str(adjusted.get("reason", "")),
        decision.reason,
    )
    return adjusted


def evaluate_file_risk(
    file_info: dict,
    classification: dict,
) -> RiskDecision | None:
    extension = _normalize_extension(
        file_info.get("extension") or classification.get("extension") or ""
    )
    category = str(classification.get("category", "")).strip().lower()
    filename = str(file_info.get("filename") or classification.get("filename") or "")
    parent_dir = str(file_info.get("parent_dir") or classification.get("parent_dir") or "")

    if extension in HIGH_RISK_EXTENSIONS:
        return RiskDecision(
            REVIEW_CONFIDENCE_CAP,
            f"расширение {extension} требует ручной проверки",
        )

    if category in HIGH_RISK_CATEGORIES:
        return RiskDecision(
            REVIEW_CONFIDENCE_CAP,
            f"категория {category} не должна удаляться автоматически",
        )

    file_text = _normalized_text(filename)
    if _contains_high_risk_keyword(file_text):
        return RiskDecision(
            REVIEW_CONFIDENCE_CAP,
            "имя файла похоже на личный, учебный, рабочий или юридически важный файл",
        )

    parent_tokens = _tokens(parent_dir)
    if category in PARENT_SENSITIVE_CATEGORIES and parent_tokens & RISKY_PARENT_TOKENS:
        return RiskDecision(
            REVIEW_CONFIDENCE_CAP,
            "файл находится в папке, где часто лежат важные пользовательские данные",
        )

    return None


def _append_local_reason(reason: str, local_reason: str) -> str:
    reason = reason.strip()
    suffix = f"{LOCAL_PROTECTION_PREFIX}: {local_reason}."
    if not reason:
        return suffix
    if suffix in reason:
        return reason
    return f"{reason} {suffix}"


def _contains_high_risk_keyword(text: str) -> bool:
    if any(phrase in text for phrase in HIGH_RISK_PHRASES):
        return True
    return bool(_tokens(text) & HIGH_RISK_KEYWORDS)


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-zа-яё0-9]+", _normalized_text(value)))


def _normalized_text(value: str) -> str:
    return value.lower().replace("ё", "е").replace("_", " ")


def _normalize_extension(value: str) -> str:
    extension = str(value).strip().lower()
    if not extension:
        return ""
    if not extension.startswith("."):
        extension = os.path.splitext(extension)[1] or f".{extension}"
    return extension


def _safe_float(value, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
