from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass

import httpx

from client.config import (
    ANALYSIS_BATCH_SIZE,
    API_TIMEOUT_SECONDS,
    BACKEND_URLS,
    DB_PATH,
)


DEFAULT_API_HEADERS: dict[str, str] = {}


@dataclass(frozen=True)
class AuthSession:
    user_id: str
    username: str
    access_token: str
    token_type: str = "bearer"


@dataclass(frozen=True)
class AnalysisResult:
    scan_id: str
    classifications: list[dict]


class ApiClientError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def sanitize_file_metadata(file_info: dict) -> dict:
    parent_dir = str(file_info.get("parent_dir") or "")
    safe_parent_dir = os.path.basename(os.path.normpath(parent_dir))
    if safe_parent_dir in {".", os.curdir, os.pardir}:
        safe_parent_dir = ""

    return {
        "file_id": str(file_info.get("file_id", "")),
        "filename": str(file_info.get("filename", "")),
        "extension": str(file_info.get("extension", "")),
        "size_bytes": int(file_info.get("size_bytes") or 0),
        "modified_at": str(file_info.get("modified_at", "")),
        "accessed_at": str(file_info.get("accessed_at") or ""),
        "parent_dir": safe_parent_dir,
    }


class SmartCleanerApiClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        base_urls: Iterable[str] | None = None,
        timeout_seconds: float = API_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ):
        if base_urls is not None:
            resolved_urls = _normalize_backend_urls(base_urls)
        elif base_url is not None:
            resolved_urls = _normalize_backend_urls([base_url])
        else:
            resolved_urls = _normalize_backend_urls(BACKEND_URLS)

        self._base_urls = resolved_urls
        self.base_url = resolved_urls[0]
        self.session: AuthSession | None = None
        self._client = httpx.Client(
            timeout=timeout_seconds,
            transport=transport,
            headers=DEFAULT_API_HEADERS,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SmartCleanerApiClient:
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def set_session(self, session: AuthSession | None) -> None:
        self.session = session

    def login(self, username: str, password: str) -> AuthSession:
        session = self._auth_request("/api/auth/login", username, password)
        self.set_session(session)
        return session

    def register(self, username: str, password: str) -> AuthSession:
        session = self._auth_request("/api/auth/register", username, password)
        self.set_session(session)
        return session

    def analyze_files(
        self,
        scan_id: str,
        files: Iterable[dict],
    ) -> AnalysisResult:
        if self.session is None:
            raise ApiClientError("Not authenticated")

        sanitized = [sanitize_file_metadata(file_info) for file_info in files]
        if not sanitized:
            return AnalysisResult(scan_id=scan_id, classifications=[])

        classifications: list[dict] = []
        for chunk in _chunks(sanitized, ANALYSIS_BATCH_SIZE):
            response = self._request_json(
                "POST",
                "/api/analyze",
                json_payload={"scan_id": scan_id, "files": chunk},
                headers={
                    "Authorization": (
                        f"{self.session.token_type.title()} "
                        f"{self.session.access_token}"
                    )
                },
            )
            classifications.extend(_validated_classifications(response, chunk))

        return AnalysisResult(scan_id=scan_id, classifications=classifications)

    def _auth_request(
        self,
        path: str,
        username: str,
        password: str,
    ) -> AuthSession:
        data = self._request_json(
            "POST",
            path,
            json_payload={"username": username, "password": password},
        )
        return AuthSession(
            user_id=str(data["user_id"]),
            username=str(data["username"]),
            access_token=str(data["access_token"]),
            token_type=str(data.get("token_type", "bearer")),
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_payload: dict,
        headers: dict | None = None,
    ) -> dict:
        response = None
        last_request_error: httpx.RequestError | None = None

        for base_url in self._base_urls:
            url = f"{base_url}{path}"
            try:
                response = self._client.request(
                    method,
                    url,
                    json=json_payload,
                    headers=headers,
                )
            except httpx.RequestError as e:
                last_request_error = e
                continue

            self._promote_base_url(base_url)
            break
        else:
            raise ApiClientError("Backend is unavailable") from last_request_error

        if response is None:
            raise ApiClientError("Backend is unavailable")

        if response.status_code >= 400:
            raise ApiClientError(
                _extract_error_detail(response),
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except ValueError as e:
            raise ApiClientError("Backend returned invalid JSON") from e

        if not isinstance(data, dict):
            raise ApiClientError("Backend returned unexpected response")
        return data

    def _promote_base_url(self, base_url: str) -> None:
        if self._base_urls[0] == base_url:
            self.base_url = base_url
            return
        self._base_urls = [base_url] + [
            existing for existing in self._base_urls if existing != base_url
        ]
        self.base_url = base_url


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return f"Backend request failed with HTTP {response.status_code}"

    detail = data.get("detail") if isinstance(data, dict) else None
    if isinstance(detail, str) and detail:
        return detail
    return f"Backend request failed with HTTP {response.status_code}"


def _normalize_backend_urls(urls: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for raw_url in urls:
        url = str(raw_url).strip().rstrip("/")
        if url and url not in normalized:
            normalized.append(url)
    if not normalized:
        raise ValueError("At least one backend URL is required")
    return normalized


def _chunks(items: list[dict], size: int):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def _validated_classifications(response: dict, requested_files: list[dict]) -> list[dict]:
    classifications = response.get("classifications")
    if not isinstance(classifications, list):
        raise ApiClientError("Backend response missing classifications")

    requested_ids = {item["file_id"] for item in requested_files}
    received_ids = {
        item.get("file_id")
        for item in classifications
        if isinstance(item, dict)
    }
    if requested_ids != received_ids:
        raise ApiClientError("Backend response missing classifications")

    for item in classifications:
        if not isinstance(item, dict):
            raise ApiClientError("Backend returned invalid classification")
        for field in ("file_id", "confidence", "category", "reason"):
            if field not in item:
                raise ApiClientError("Backend returned invalid classification")
    return classifications


def analyze_and_cache_files(
    api_client: SmartCleanerApiClient,
    scan_id: str,
    files: Iterable[dict],
    *,
    db_path: str = DB_PATH,
) -> AnalysisResult:
    from client.database.local_db import cache_analysis_results
    from client.safety import apply_deterministic_risk_downgrades

    file_list = list(files)
    result = api_client.analyze_files(scan_id, file_list)
    adjusted_classifications = apply_deterministic_risk_downgrades(
        file_list,
        result.classifications,
    )
    cache_analysis_results(adjusted_classifications, db_path=db_path)
    return AnalysisResult(
        scan_id=result.scan_id,
        classifications=adjusted_classifications,
    )
