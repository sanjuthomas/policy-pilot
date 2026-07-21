FROM python:3.12-slim

WORKDIR /app

COPY shared/telemetry/pyproject.toml shared/telemetry/pyproject.toml
COPY shared/telemetry/src shared/telemetry/src
RUN pip install --no-cache-dir ./shared/telemetry

COPY shared/cypher_builder/pyproject.toml shared/cypher_builder/pyproject.toml
COPY shared/cypher_builder/src shared/cypher_builder/src
RUN pip install --no-cache-dir ./shared/cypher_builder

COPY cypher-builder-svc/pyproject.toml .
COPY cypher-builder-svc/src ./src

RUN pip install --no-cache-dir .

EXPOSE 8097

CMD ["uvicorn", "cbs.main:app", "--host", "0.0.0.0", "--port", "8097"]
