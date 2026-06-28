FROM python:3.12-slim

WORKDIR /app

COPY shared/telemetry/pyproject.toml shared/telemetry/pyproject.toml
COPY shared/telemetry/src shared/telemetry/src
RUN pip install --no-cache-dir ./shared/telemetry

COPY sequence-service/pyproject.toml .
COPY sequence-service/src ./src

RUN pip install --no-cache-dir .

EXPOSE 8095

CMD ["uvicorn", "seq.main:app", "--host", "0.0.0.0", "--port", "8095"]
