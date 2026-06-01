# syntax=docker/dockerfile:1

# ---- Builder stage: compile/install deps into a venv ----
FROM python:3.12-slim AS builder

# Build deps for asyncpg / grpc (OTel exporter) wheels if no prebuilt wheel exists.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create an isolated virtualenv we can copy wholesale into the runtime image.
ENV VENV=/opt/venv
RUN python -m venv $VENV
ENV PATH="$VENV/bin:$PATH"

# Install deps first for layer caching — only re-runs when requirements change.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# ---- Runtime stage: slim image with only the venv + app code ----
FROM python:3.12-slim AS runtime

# Faster, cleaner Python in containers.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

# Run as a non-root user (Cloud Run doesn't require it, but it's good hygiene).
RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app

# Copy the prebuilt venv from the builder — no build toolchain in the final image.
COPY --from=builder /opt/venv /opt/venv

# Copy application source.
COPY . .

USER app

# Cloud Run injects PORT (defaults to 8080). Bind 0.0.0.0 so the platform can reach it.
# Single uvicorn worker — Cloud Run scales by adding instances, not workers.
# ws_max_size is set in main.py's uvicorn.run(); the CMD path below uses the CLI flag
# so it applies whether you run via `python main.py` or this CMD.
EXPOSE 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --ws-max-size 6291456 --log-config /dev/null"]