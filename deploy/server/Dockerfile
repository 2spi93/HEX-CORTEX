FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY src /app/src
RUN python -m pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 hexcortex \
    && mkdir -p /data/.hex-cortex \
    && chown -R hexcortex:hexcortex /data /app

USER hexcortex
WORKDIR /data
EXPOSE 8765

CMD ["python", "-m", "hex_cortex.memory.cortex_server_api"]
