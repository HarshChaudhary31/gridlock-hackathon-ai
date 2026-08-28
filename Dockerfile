FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

COPY . .

RUN mkdir -p /app/weights /app/uploads /app/outputs /app/reports /app/logs /app/data

ENV PYTHONPATH=/app
ENV DEVICE=cpu
ENV YOLO_CONFIG_DIR=/tmp/Ultralytics

EXPOSE 8000

CMD ["sh", "-c", "python main.py backend --host 0.0.0.0 --api-port ${PORT:-8000}"]
