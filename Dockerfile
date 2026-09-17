FROM python:3.12-slim

# Install uv from its official image
COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# 1. Install dependencies only (cached unless pyproject/uv.lock change)
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# 2. Copy the code and data, then install the project itself
COPY README.md ./
COPY src ./src
COPY app ./app
COPY data ./data
RUN uv sync --locked --no-dev

# Run as a non-root user
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8501

HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]