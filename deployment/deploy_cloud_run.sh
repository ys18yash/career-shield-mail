#!/usr/bin/env bash
# ==============================================================================
# CareerShield Mail - Google Cloud Run Deployment Script
# ==============================================================================
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-careershield-mail-prod}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="careershield-backend"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

echo "=================================================================="
echo "DEPLOYING CAREERSHIELD ML BACKEND TO GOOGLE CLOUD RUN"
echo "Project : ${PROJECT_ID}"
echo "Region  : ${REGION}"
echo "Service : ${SERVICE_NAME}"
echo "=================================================================="

# 1. Build container image via Google Cloud Build
echo ">>> [1/3] Building container image via Google Cloud Build..."
gcloud builds submit --project="${PROJECT_ID}" --tag="${IMAGE_NAME}" .

# 2. Deploy to Cloud Run
echo ">>> [2/3] Deploying container to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
    --project="${PROJECT_ID}" \
    --image="${IMAGE_NAME}" \
    --platform=managed \
    --region="${REGION}" \
    --allow-unauthenticated \
    --memory=1Gi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=10 \
    --port=8080 \
    --set-env-vars="PORT=8080,CORS_ORIGINS=*"

# 3. Retrieve service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --project="${PROJECT_ID}" --region="${REGION}" --format="value(status.url)")
echo "=================================================================="
echo "SUCCESS! Cloud Run Service deployed at: ${SERVICE_URL}"
echo "Health Check: ${SERVICE_URL}/api/health"
echo "=================================================================="
