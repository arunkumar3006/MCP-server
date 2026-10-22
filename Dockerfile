# Lightweight Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application code
COPY . .

# Default port
ENV PORT=5000
EXPOSE 5000

# Run the FastAPI Web Dashboard & Background Scheduler
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
