FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip first so it can read modern pyproject.toml dependency tables
RUN pip install --upgrade --no-cache-dir pip

# Copy the dependency manifest and install runtime dependencies only.
# We intentionally do NOT do `pip install -e .` to avoid needing
# a modern setuptools inside the image.  PYTHONPATH makes the `app`
# package importable without any install step.
COPY pyproject.toml .
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

# Copy source
COPY src/ src/

# Make the `app` package importable
ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
