# Use the official Python slim image
FROM python:3.14-slim

# Set the working directory
WORKDIR /app

# Prevent Python from creating .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Display Python logs immediately
ENV PYTHONUNBUFFERED=1

# Provide Turnstile settings at runtime; do not bake credentials into the image.
ENV TURNSTILE_SITE_KEY="" \
    TURNSTILE_SECRET_KEY="" \
    TURNSTILE_EXPECTED_HOSTNAME=""

# Install Python dependencies first for better build caching
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall --yes pip

# Copy application source code
COPY app/ ./app/

# Create a non-root user
RUN useradd --system --no-create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

# FastAPI application port
EXPOSE 8088

# Start the web application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8088"]