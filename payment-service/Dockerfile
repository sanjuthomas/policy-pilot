FROM python:3.12-slim

WORKDIR /app

COPY shared/platform_auth/pyproject.toml shared/platform_auth/pyproject.toml
COPY shared/platform_auth/src shared/platform_auth/src
RUN pip install --no-cache-dir ./shared/platform_auth

COPY shared/sequence_client/pyproject.toml shared/sequence_client/pyproject.toml
COPY shared/sequence_client/src shared/sequence_client/src
RUN pip install --no-cache-dir ./shared/sequence_client

COPY shared/authz_client/pyproject.toml shared/authz_client/pyproject.toml
COPY shared/authz_client/src shared/authz_client/src
RUN pip install --no-cache-dir ./shared/authz_client

COPY shared/telemetry/pyproject.toml shared/telemetry/pyproject.toml
COPY shared/telemetry/src shared/telemetry/src
RUN pip install --no-cache-dir ./shared/telemetry

COPY payment-service/pyproject.toml .
COPY payment-service/src ./src

RUN pip install --no-cache-dir .

EXPOSE 8093

CMD ["uvicorn", "ps.main:app", "--host", "0.0.0.0", "--port", "8093"]
