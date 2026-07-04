#!/usr/bin/env python3
"""Verify Vertex AI connectivity via Application Default Credentials."""

from __future__ import annotations

import os
import sys

from google import genai
from pydantic import BaseModel, Field

DEFAULT_PROJECT = "rag-demos-501323"
DEFAULT_REGION = "us-central1"
DEFAULT_MODEL = "gemini-2.5-flash"


class SmokeTestResult(BaseModel):
    status: str = Field(description="Connection status, e.g. SUCCESS")
    message: str = Field(description="Short greeting from the model")


def main() -> int:
    project = os.environ.get("GCP_PROJECT_ID", DEFAULT_PROJECT)
    region = os.environ.get("GCP_REGION", DEFAULT_REGION)
    model = os.environ.get("VERTEX_GEMINI_MODEL", DEFAULT_MODEL)
    creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "(ADC default)")

    print(f"Project:     {project}")
    print(f"Region:      {region}")
    print(f"Model:       {model}")
    print(f"Credentials: {creds}")
    print()

    client = genai.Client(vertexai=True, project=project, location=region)
    try:
        response = client.models.generate_content(
            model=model,
            contents=(
                "Respond with status SUCCESS and a short greeting confirming "
                "Vertex AI authentication works."
            ),
            config={
                "response_mime_type": "application/json",
                "response_schema": SmokeTestResult,
                "temperature": 0.0,
            },
        )
        result = SmokeTestResult.model_validate_json(response.text)
    except Exception as exc:
        print("CONNECTION FAILED")
        print(f"Error: {exc}")
        return 1

    print("CONNECTION SUCCESSFUL")
    print(f"Status:  {result.status}")
    print(f"Message: {result.message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
