FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl fontconfig ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /repo/apps/pipeline
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY src ./src
RUN uv sync --frozen
ENV PATH="/opt/venv/bin:$PATH"
