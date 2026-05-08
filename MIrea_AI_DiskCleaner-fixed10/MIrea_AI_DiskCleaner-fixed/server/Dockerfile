FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cached layer) before copying source.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source.
COPY . .

# Create the data directory and a non-root user that owns the working tree.
# Running as a dedicated unprivileged user limits the blast radius if the
# process is ever exploited.
RUN mkdir -p /app/data && \
    groupadd --system app && \
    useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app && \
    chown -R app:app /app
USER app

EXPOSE 8000

# Healthcheck via stdlib urllib so it doesn't depend on httpx being importable
# and fails (exit 1) on any non-200 response or network error.
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import sys, urllib.request; r = urllib.request.urlopen('http://localhost:8000/health', timeout=5); sys.exit(0 if r.status == 200 else 1)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
