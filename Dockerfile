FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system saju \
    && useradd --system --gid saju --home-dir /srv/saju-caldav saju

WORKDIR /srv/saju-caldav
COPY pyproject.toml uv.lock README.md ./
COPY app ./app
COPY radicale ./radicale
COPY scripts ./scripts
RUN python -m pip install --no-cache-dir . \
    && mkdir -p /data/app /data/radicale \
    && chown -R saju:saju /srv/saju-caldav /data

USER saju
EXPOSE 8000 5232

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
