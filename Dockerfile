# Use an official Python lightweight image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Kolkata

# Set the working directory
WORKDIR /app

# Install system dependencies required for cryptography, mysql, etc.
RUN apt-get update && apt-get install -y \
    build-essential \
    libmariadb-dev \
    pkg-config \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the project files into the container
COPY . /app

# Expose the port that the app runs on
EXPOSE 8000

# Run the FastAPI application with dynamic port for Railway
CMD gunicorn app.main:app \
     -w 1 \
     -k uvicorn.workers.UvicornWorker \
     -b 0.0.0.0:${PORT:-8000} \
     --log-level debug \
     --access-logfile /dev/null \
     --error-logfile -

