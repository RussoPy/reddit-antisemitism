# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and source code
COPY reddit_analyzer/requirements.txt ./
COPY reddit_analyzer/ ./reddit_analyzer/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy .env if present (optional, for local dev)
# COPY .env .

# Set environment variables for production via Docker/Render dashboard

# Run the main script
CMD ["python", "reddit_analyzer/reddit_fetcher.py"]
