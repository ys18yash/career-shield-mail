#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${FIREBASE_PROJECT_ID:-careershield-mail-prod}"

echo "=================================================================="
echo "DEPLOYING CAREERSHIELD DASHBOARD TO FIREBASE HOSTING"
echo "Project: ${PROJECT_ID}"
echo "=================================================================="

firebase deploy --only hosting --project="${PROJECT_ID}"

echo "=================================================================="
echo "SUCCESS! Firebase Hosting deployment complete."
echo "=================================================================="
