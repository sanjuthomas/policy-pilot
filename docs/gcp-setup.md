# GCP and Vertex AI setup

Run Policy Pilot and the indexer locally with Vertex embeddings and Gemini generation.

**ssi-indexer** and **ssi-chat-j** call Vertex for embeddings (`text-embedding-004`) and Gemini (routing/synthesis; indexer also uses graph-plan extraction). The rest of the stack (MongoDB, Kafka, Neo4j, OPA, ZITADEL) runs entirely in Docker and does not require GCP.

## Prerequisites

| Tool | Purpose |
|------|---------|
| [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/docs/install) | Create project resources and download a service account key |
| Docker + Docker Compose | Run the full stack (`docker compose up -d`) |
| Python 3.12+ | Run `scripts/vertex_smoke_test.py` and optional local service dev |

You also need **billing enabled** on the GCP project. Vertex AI calls are metered; typical dev usage is low cost, but a billing account must be attached.

## 1. Create a GCP project

In the [Google Cloud Console](https://console.cloud.google.com/) create a new project (or pick an existing one). Note the **project ID** (not the display name).

```bash
gcloud config set project YOUR_PROJECT_ID
```

## 2. Enable the Vertex AI API

```bash
gcloud services enable aiplatform.googleapis.com
```

## 3. Create a service account

```bash
gcloud iam service-accounts create vertex-client \
  --display-name="Vertex AI client (local dev)"
```

Grant the roles the demo needs:

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:vertex-client@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:vertex-client@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/serviceusage.serviceUsageConsumer"
```

- **`roles/aiplatform.user`** — call Vertex embeddings and Gemini models.
- **`roles/serviceusage.serviceUsageConsumer`** — allow the service account to consume enabled APIs.

## 4. Download a JSON key

```bash
mkdir -p ~/.config/gcloud
gcloud iam service-accounts keys create \
  ~/.config/gcloud/YOUR_PROJECT_ID-vertex-client-key.json \
  --iam-account=vertex-client@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

Treat this file like a password. Do not commit it or paste it into issues.

## 5. Configure this repository

```bash
cp .env.example .env
```

Edit `.env`:

```bash
GCP_PROJECT_ID=YOUR_PROJECT_ID
GCP_REGION=us-central1
GCP_SA_KEY_PATH=/absolute/path/to/YOUR_PROJECT_ID-vertex-client-key.json
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/YOUR_PROJECT_ID-vertex-client-key.json
```

| Variable | Used by | Notes |
|----------|---------|-------|
| `GCP_PROJECT_ID` | ssi-indexer, ssi-chat-j, smoke test | Must match the project where Vertex AI is enabled |
| `GCP_REGION` | ssi-indexer, ssi-chat-j | Default `us-central1` |
| `GCP_SA_KEY_PATH` | Docker Compose | Host path mounted read-only at `/run/secrets/gcp-sa.json` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Local Python runs, smoke test | Same JSON file |

Optional overrides: `VERTEX_EMBEDDING_MODEL`, `VERTEX_GEMINI_MODEL`, `EMBEDDING_DIMENSION` — see `.env.example`.

## 6. Verify Vertex connectivity

```bash
pip install google-genai pydantic
export $(grep -v '^#' .env | xargs)
python scripts/vertex_smoke_test.py
```

You should see `CONNECTION SUCCESSFUL` and a short greeting from Gemini.

Common failures:

| Symptom | Likely fix |
|---------|------------|
| `403` / `Permission denied` | Confirm `roles/aiplatform.user` and matching `GCP_PROJECT_ID` |
| `API not enabled` | Re-run `gcloud services enable aiplatform.googleapis.com` |
| `Could not automatically determine credentials` | Set `GOOGLE_APPLICATION_CREDENTIALS` to absolute path of JSON key |
| Model not found in region | Set `GCP_REGION=us-central1` or choose a supported region |

## 7. Start the stack

Once the smoke test passes, follow [Quick start](how-it-works.md#quick-start): clean slate (or compose up), seed ZITADEL users, run scenarios in the harness, then open Policy Pilot.

Unit/CI for chat does not call Vertex (Spring AI is mocked in tests). Live golden prove against a warm stack needs Vertex credentials for routing/synthesis.
