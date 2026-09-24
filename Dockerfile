# Phase 2: FastAPI only. Phase 4 adds a Node build stage for web/ ahead of
# this, copying its dist/ output in below, per CLAUDE.md Section 11.
FROM python:3.11-slim
WORKDIR /app
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY server/ server/
CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
