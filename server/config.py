import os
import sys

from dotenv import load_dotenv

load_dotenv()

# ===== Environment =====
# "development" | "production" | "test". Controls fail-fast checks below.
ENV = os.getenv("ENV", "development").lower()
IS_PROD = ENV == "production"
IS_TEST = ENV == "test"


# ===== AI providers =====
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-1.5-flash:generateContent"
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")


# ===== JWT =====
JWT_SECRET = os.getenv("JWT_SECRET", "CHANGE-ME-IN-PRODUCTION")
JWT_ALGORITHM = "HS256"
# Short-lived access token (1 hour) — limits the blast radius of a leaked token.
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "60"))


# ===== Database =====
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./data/app.db",
)


# ===== CORS =====
CORS_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()
]


# ===== Limits =====
MAX_FILES_PER_REQUEST = 200
AI_TIMEOUT_SECONDS = 60
AI_TEMPERATURE = 0.1

# 1 MiB cap on request body — 200 file metadata records fit comfortably under this.
MAX_REQUEST_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(1024 * 1024)))


# ===== Password hashing =====
# 13 rounds: ~250-400ms per verify on a modern laptop. Higher than the
# passlib default of 12, but kept reasonable so login stays interactive
# even on slow hardware. Combine with rate limiting on /login.
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "13"))


# ===== Rate limits (per-IP, in-memory) =====
# Format follows slowapi/limits library: "<count>/<period>".
RATE_LIMIT_LOGIN = os.getenv("RATE_LIMIT_LOGIN", "5/minute")
RATE_LIMIT_REGISTER = os.getenv("RATE_LIMIT_REGISTER", "3/minute")
RATE_LIMIT_ANALYZE = os.getenv("RATE_LIMIT_ANALYZE", "30/minute")


# ===== Fail-fast hardening checks =====
# These run at import time (i.e. process startup). The goal is to refuse to
# boot with a known-insecure configuration in production rather than silently
# accept it. In dev/test we stay permissive so the demo "just works".
def _fatal(msg: str) -> None:
    sys.stderr.write(f"[config] FATAL: {msg}\n")
    raise SystemExit(2)


_INSECURE_JWT_DEFAULTS = {
    "",
    "CHANGE-ME-IN-PRODUCTION",
    "replace-me-with-a-32-byte-random-hex-string",
}

if IS_PROD:
    if JWT_SECRET in _INSECURE_JWT_DEFAULTS or len(JWT_SECRET) < 32:
        _fatal(
            "JWT_SECRET must be set to a strong random value (>=32 chars) in "
            "production. Generate with: openssl rand -hex 32"
        )
    if "*" in CORS_ORIGINS or not CORS_ORIGINS:
        _fatal(
            "CORS_ORIGINS must list explicit origins in production "
            "(e.g. CORS_ORIGINS=https://app.example.com)"
        )
    if DATABASE_URL.startswith("sqlite"):
        _fatal(
            "SQLite is not supported in production. "
            "Set DATABASE_URL to a PostgreSQL URL."
        )
    if not GEMINI_API_KEY and AI_PROVIDER == "gemini":
        _fatal("GEMINI_API_KEY is required when AI_PROVIDER=gemini in production")
    if not GROQ_API_KEY and AI_PROVIDER == "groq":
        _fatal("GROQ_API_KEY is required when AI_PROVIDER=groq in production")
