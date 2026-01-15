FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ .

# Copy evaluator modules from repo root (required for imports)
COPY evaluator.py .
COPY llm_evaluator.py .
COPY SYSTEM_PROMPT.md .

# Copy startup script
COPY backend/start.sh /start.sh
RUN chmod +x /start.sh

# Expose port
EXPOSE 8000

# Run the application
CMD ["/start.sh"]
