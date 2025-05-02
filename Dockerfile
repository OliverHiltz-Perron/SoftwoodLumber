# Use a multi-stage build for a smaller final image
FROM python:3.10-slim AS builder

# Set working directory
WORKDIR /app

# Set environment variables to reduce Python bytecode and ensure pip doesn't use cache
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements file first for better caching
COPY requirements.txt .

# Install dependencies into a virtual environment
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Install dependencies with CPU-only flag for PyTorch
RUN pip install --no-cache-dir -r requirements.txt \
    && find /app/venv -name "*.pyc" -delete \
    && find /app/venv -name "__pycache__" -delete

# Final production image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /app/venv /app/venv

# Update PATH to use the virtual environment
ENV PATH="/app/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy application code and necessary files
COPY src/ /app/src/
COPY prompts/ /app/prompts/
COPY propositions_rows.csv /app/propositions_rows.csv
COPY SLB-LOGO.png /app/SLB-LOGO.png
COPY .env.template /app/.env

# Create non-root user for security
RUN groupadd -r app && useradd -r -g app -d /app app \
    && chown -R app:app /app

# Switch to non-root user
USER app

# Expose the Streamlit port
EXPOSE 8501

# Set the entrypoint to run the Streamlit app
CMD ["streamlit", "run", "src/app.py", "--server.address", "0.0.0.0"]
