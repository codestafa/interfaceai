FROM node:22-bookworm-slim AS frontend

WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/index.html web/tsconfig.json web/vite.config.ts ./
COPY web/src ./src
COPY web/public ./public
RUN npm run build

FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    KNOWLEDGE_SNAPSHOTS=/data/snapshots

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 knowledge \
    && useradd --uid 10001 --gid knowledge --no-create-home knowledge

COPY --chown=10001:10001 harness/contract.py ./harness/contract.py
COPY --chown=10001:10001 submission ./submission
COPY --chown=10001:10001 server ./server
COPY --chown=10001:10001 scripts/import_kit.py ./scripts/import_kit.py
COPY --from=frontend --chown=10001:10001 /build/web/dist ./web/dist

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 \
    CMD ["python", "-c", "import json, urllib.request; response = json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/status', timeout=3)); raise SystemExit(0 if response.get('state') == 'ready' else 1)"]
CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
