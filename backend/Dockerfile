# stage 1
FROM python:3.11-slim AS builder
 
WORKDIR /www

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --progress-bar off --upgrade pip && \
        pip install --no-cache-dir --progress-bar off -r requirements.txt

# stage 2
FROM python:3.11-slim AS runtime
WORKDIR /www
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY src/ .

RUN apt-get update \
    && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 app && chown -R app /www
USER app

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:5000", "main:app"]