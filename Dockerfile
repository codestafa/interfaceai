FROM node:22-bookworm-slim AS frontend

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src ./src
COPY frontend/public ./public
RUN npm run build

FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    KNOWLEDGE_SNAPSHOTS=/data/snapshots

WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && groupadd --gid 10001 knowledge \
    && useradd --uid 10001 --gid knowledge --no-create-home knowledge

COPY --chown=10001:10001 harness/contract.py ./harness/contract.py
COPY --chown=10001:10001 backend/__init__.py ./backend/__init__.py
COPY --chown=10001:10001 backend/submission ./backend/submission
COPY --chown=10001:10001 backend/server ./backend/server
COPY --chown=10001:10001 scripts/import_kit.py ./scripts/import_kit.py
COPY --from=frontend --chown=10001:10001 /build/frontend/dist ./frontend/dist

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 \
    CMD ["python", "-c", "import json, urllib.request; response = json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/status', timeout=3)); raise SystemExit(0 if response.get('state') == 'ready' else 1)"]
CMD ["python", "-m", "uvicorn", "backend.server.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
