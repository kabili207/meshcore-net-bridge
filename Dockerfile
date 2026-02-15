FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY meshcore_bridge/ meshcore_bridge/

RUN pip install --no-cache-dir .

ENTRYPOINT ["meshcore-bridge"]
CMD ["-c", "/app/config.yaml"]
