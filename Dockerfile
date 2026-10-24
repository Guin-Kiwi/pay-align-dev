FROM python:3.12.15-slim-trixie@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704

# Set working directory
WORKDIR /app

# Copy requirements first so we can cache dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.txt

COPY src/ /app/src/
COPY LICENSE /app/LICENSE

RUN groupadd --gid 10001 payalign \
    && useradd --uid 10001 --gid payalign --no-create-home --shell /usr/sbin/nologin payalign \
    && install -d -m 0750 -o payalign -g payalign /app/data

USER payalign:payalign

# Expose the FastAPI port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "src.app.infrastructure.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
