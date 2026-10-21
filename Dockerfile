# Production Dockerfile for Google Cloud Run
FROM python:3.13-slim

# Install system dependencies required for Docling, PyMuPDF, and graphics
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary for rapid dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency specifications first for Docker layer caching
COPY pyproject.toml uv.lock ./

# Install all dependencies into the system python environment
RUN uv pip install --system -e .

# Copy project files
COPY . .

# Ensure entrypoint script is executable
RUN chmod +x /app/entrypoint.sh

# Google Cloud Run default port and Streamlit environment configuration
ENV PORT=8080
ENV STREAMLIT_SERVER_PORT=8080
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
