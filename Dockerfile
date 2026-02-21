# ── Stage 1: build the React frontend ───────────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./

# VITE_* vars intentionally not set here — the frontend falls back to
# same-origin relative URLs which work when served by the backend.
RUN npm run build


# ── Stage 2: Python backend + bundled frontend ────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade --no-cache-dir pip

COPY backend/pyproject.toml .
RUN pip install --no-cache-dir \
        "fastapi>=0.110.0" \
        "uvicorn[standard]>=0.29.0" \
        "neo4j>=5.18.0" \
        "openai>=1.30.0" \
        "requests>=2.31.0" \
        "pydantic>=2.7.0" \
        "pydantic-settings>=2.2.0" \
        "websockets>=12.0" \
        "python-dotenv>=1.0.0"

COPY backend/src/ src/

# Copy the built frontend into /app/static — FastAPI serves it from there
COPY --from=frontend-build /frontend/dist/ static/

ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
