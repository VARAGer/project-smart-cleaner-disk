"""
Shared per-IP rate limiter.

Uses slowapi's in-memory backend — no Redis required. The same limiter
instance is imported by every router and wired into the FastAPI app in
`main.py`. The limiter is auto-disabled under ENV=test so the test suite
isn't slowed down by per-IP throttling.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from config import IS_TEST

limiter = Limiter(
    key_func=get_remote_address,
    enabled=not IS_TEST,
    # The default backend is `memory:`, single-process. Fine for one uvicorn
    # worker; under multi-worker deployment, swap to `memcached://...` or
    # `redis://...` via storage_uri.
)
