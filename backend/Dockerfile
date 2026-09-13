FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy packaging and setup files
COPY pyproject.toml SETUP.md ./
COPY backend ./backend

# Install the package and its dependencies
RUN pip install --no-cache-dir .

WORKDIR /app/backend

# Create a volume mount point for data
RUN mkdir -p data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
