FROM python:3.12-slim

WORKDIR /app

COPY upload_policies.py wait_for_policies.py validate_policy_catalog.py /app/

ENTRYPOINT ["python", "/app/wait_for_policies.py"]
