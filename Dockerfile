# TODO(PR #3 review): container runs as root; add a non-root user. Owner: person 4.
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first so we can cache dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . /app

# Expose the FastAPI port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "src.app.infrastructure.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
