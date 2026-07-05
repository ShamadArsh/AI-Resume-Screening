# ============================================================
# Dockerfile — AI Resume Screening Platform
# ============================================================
# Multi-stage build: slim Python image with all dependencies.
# ============================================================

FROM python:3.13-slim

# System deps for PyMuPDF, pdfplumber, chromadb
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmupdf-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create upload dir
RUN mkdir -p /app/uploads

EXPOSE 8000 8501

# Default: run FastAPI backend (override in docker-compose for other services)
CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
