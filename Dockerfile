FROM python:3.10-slim

# Install system dependencies
# ffmpeg for media processing
# curl for potential download operations or health checks
RUN apt-get update && \
    apt-get install -y ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py processor.py ./

# Create directories for temp files and outputs
RUN mkdir -p /outputs /tmp && chmod 777 /outputs /tmp

# Environment variables
ENV BASE_URL=""
ENV OUTPUT_TTL_HOURS="6"

# Expose FastAPI default port
EXPOSE 8000

# Start command
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
