FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/tmp

WORKDIR /srv/saju-caldav
COPY pyproject.toml uv.lock requirements.lock README.md ./
COPY app ./app
COPY radicale ./radicale
COPY scripts ./scripts
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock \
    && mkdir -p /data/app /data/radicale \
    && chown -R 10001:10001 /srv/saju-caldav /data

USER 10001:10001
EXPOSE 8000 5232

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
