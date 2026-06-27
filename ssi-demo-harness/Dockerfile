FROM python:3.12-slim

WORKDIR /app

COPY shared/platform_auth/pyproject.toml shared/platform_auth/pyproject.toml
COPY shared/platform_auth/src shared/platform_auth/src
RUN pip install --no-cache-dir ./shared/platform_auth

COPY ssi-demo-harness/pyproject.toml .
COPY ssi-demo-harness/src ./src

RUN pip install --no-cache-dir .

EXPOSE 8091

CMD ["ssi-demo-harness-ui"]
