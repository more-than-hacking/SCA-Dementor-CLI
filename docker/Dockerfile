# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p REPOSITORIES reports config core parsers utils

# Make scripts executable
RUN chmod +x dementor-cli
RUN chmod +x core/*.py

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Set the entrypoint to the dementor-cli script
ENTRYPOINT ["python3", "dementor-cli"]

# Default command (show help)
CMD ["--help"] 