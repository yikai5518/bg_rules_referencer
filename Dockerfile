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

# Pre-download and cache Docling model weights during build to prevent runtime latency
RUN python -c "\
from docling.datamodel.pipeline_options import PdfPipelineOptions; \
from docling.document_converter import DocumentConverter, PdfFormatOption; \
from docling.datamodel.base_models import InputFormat, DocumentStream; \
import io, fitz; \
opts = PdfPipelineOptions(); \
opts.do_ocr = False; \
opts.do_table_structure = False; \
conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}); \
doc = fitz.open(); \
doc.new_page().insert_text((50, 50), 'Warmup'); \
conv.convert(DocumentStream(name='warmup.pdf', stream=io.BytesIO(doc.tobytes())))"

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
