FROM python:3.11-slim

# Prevent Python from writing .pyc files & enable logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies (needed for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# 1. Create a non-root user
RUN useradd -m myuser

# Install Python dependencies first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# 2. Switch to that user
USER myuser

# 3. Add a Healthcheck (Checkov loves this)
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

# Flask environment
ENV FLASK_APP=api.index
ENV FLASK_ENV=production
ENV PORT=5000

EXPOSE 5000

# Start Flask
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5000"]
