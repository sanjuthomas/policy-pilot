FROM python:3.12-slim

WORKDIR /app

COPY shared/platform_auth/pyproject.toml shared/platform_auth/pyproject.toml
COPY shared/platform_auth/src shared/platform_auth/src
RUN pip install --no-cache-dir ./shared/platform_auth

COPY shared/telemetry/pyproject.toml shared/telemetry/pyproject.toml
COPY shared/telemetry/src shared/telemetry/src
RUN pip install --no-cache-dir ./shared/telemetry

COPY authorization-service/pyproject.toml .
COPY authorization-service/src ./src

RUN pip install --no-cache-dir .

EXPOSE 8094

CMD ["uvicorn", "authz.main:app", "--host", "0.0.0.0", "--port", "8094"]
