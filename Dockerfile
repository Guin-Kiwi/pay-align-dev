FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements first so we can cache dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . /app

RUN groupadd --gid 10001 payalign \
    && useradd --uid 10001 --gid payalign --no-create-home --shell /usr/sbin/nologin payalign \
    && install -d -m 0750 -o payalign -g payalign /app/data

USER payalign:payalign

# Expose the FastAPI port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "src.app.infrastructure.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
