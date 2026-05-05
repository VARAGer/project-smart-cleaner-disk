"""POST /api/analyze — file classification endpoint (JWT-protected)."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import RATE_LIMIT_ANALYZE
from models.schemas import AnalysisRequest, AnalysisResponse
from rate_limit import limiter
from services.ai_service import classify_files
from services.auth_service import audit_logger, decode_token

router = APIRouter(prefix="/api", tags=["analysis"])
# auto_error=False so we can emit our own audit log line on missing/bad
# headers instead of FastAPI's default 403.
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    ip = request.client.host if request.client else "-"
    if credentials is None:
        audit_logger.info("auth_rejected ip=%s reason=missing_bearer", ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    user_id = decode_token(credentials.credentials)
    if not user_id:
        audit_logger.info("auth_rejected ip=%s reason=invalid_token", ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return user_id


@router.post("/analyze", response_model=AnalysisResponse)
@limiter.limit(RATE_LIMIT_ANALYZE)
async def analyze_files(
    request: Request,
    payload: AnalysisRequest,
    user_id: str = Depends(get_current_user),
):
    files_for_ai = [
        {
            "file_id": f.file_id,
            "filename": f.filename,
            "extension": f.extension,
            "size_bytes": f.size_bytes,
            "modified_at": f.modified_at,
            "accessed_at": f.accessed_at or "",
            "parent_dir": f.parent_dir,
        }
        for f in payload.files
    ]

    classifications = await classify_files(files_for_ai)

    return AnalysisResponse(
        scan_id=payload.scan_id,
        classifications=classifications,
    )
