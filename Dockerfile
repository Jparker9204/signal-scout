FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY signal_scout ./signal_scout
RUN pip install --no-cache-dir . && useradd --create-home --uid 10001 scout \
    && mkdir -p /app/data && chown scout /app/data
USER scout

VOLUME ["/app/data"]
ENTRYPOINT ["signal-scout"]
CMD ["--config", "/app/config.yaml"]
