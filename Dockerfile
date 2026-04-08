FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables for Vertex AI
# Project and location MUST be overridden at deploy time via --set-env-vars
ENV GOOGLE_GENAI_USE_VERTEXAI=TRUE
ENV GOOGLE_CLOUD_PROJECT=""
ENV GOOGLE_CLOUD_LOCATION=""

# Expose port 8080 (Cloud Run default)
EXPOSE 8080

# Run ADK web server
CMD ["adk", "web", "--host", "0.0.0.0", "--port", "8080", "."]
