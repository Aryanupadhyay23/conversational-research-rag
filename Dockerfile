# ==============================================================================
# Stage 1: Build Stage (compile C-extensions & install python wheels)
# ==============================================================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build tools needed to compile native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies into isolated /install prefix
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-compile --prefix=/install -r requirements.txt && \
    find /install -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /install -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /install -type f -name "*.pyc" -delete || true

# ==============================================================================
# Stage 2: Minimal Runtime Stage (production image)
# ==============================================================================
FROM python:3.12-slim AS runner

WORKDIR /app

# Install minimal runtime dependencies (curl for healthcheck) and clean apt cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

# Copy pre-compiled dependencies from builder stage into system PATH
COPY --from=builder /install /usr/local

# Copy application source code
COPY . .

# Ensure entrypoint script is executable
RUN chmod +x entrypoint.sh

# Configure Python and Streamlit runtime environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_PORT=7860 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false \
    STREAMLIT_SERVER_ENABLE_CORS=false \
    BACKEND_URL=http://localhost:8000

# Mount this location in production for the SQLite registry. Qdrant Cloud is
# selected automatically with QDRANT_CLUSTER_ENDPOINT and QDRANT_API_KEY; the
# local /app/data/qdrant directory is only a fallback when no endpoint is set.
VOLUME ["/app/data"]

# Expose Streamlit (7860) and FastAPI (8000) ports
EXPOSE 7860 8000

# Container healthcheck for AWS EC2 self-healing
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["./entrypoint.sh"]
