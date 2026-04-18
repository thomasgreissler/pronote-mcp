FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir build && \
    python -m build --wheel

# ---

FROM python:3.12-slim

# Create non-root user
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app

# Install the wheel
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

USER app

ENV MCP_HTTP_HOST=0.0.0.0 \
    MCP_HTTP_PORT=8765 \
    PYTHONUNBUFFERED=1

EXPOSE 8765

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3)" || exit 1

CMD ["pronote-mcp-http"]
