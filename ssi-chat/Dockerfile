FROM python:3.12-slim

WORKDIR /app

COPY shared/vertex_client/pyproject.toml shared/vertex_client/pyproject.toml
COPY shared/vertex_client/src shared/vertex_client/src
RUN pip install --no-cache-dir ./shared/vertex_client

COPY shared/cypher_gen/pyproject.toml shared/cypher_gen/pyproject.toml
COPY shared/cypher_gen/src shared/cypher_gen/src
RUN pip install --no-cache-dir ./shared/cypher_gen

COPY shared/telemetry/pyproject.toml shared/telemetry/pyproject.toml
COPY shared/telemetry/src shared/telemetry/src
RUN pip install --no-cache-dir ./shared/telemetry

COPY ssi-chat/pyproject.toml .
COPY ssi-chat/src ./src

RUN pip install --no-cache-dir .

EXPOSE 8092

CMD ["ssi-chat"]
