#!/usr/bin/env bash
# ==============================================================================
# CareerShield Mail - Firebase Hosting Deployment Script
# ==============================================================================
set -euo pipefail

PROJECT_ID="${FIREBASE_PROJECT_ID:-careershield-mail-prod}"

echo "=================================================================="
echo "DEPLOYING CAREERSHIELD DASHBOARD TO FIREBASE HOSTING"
echo "Project: ${PROJECT_ID}"
echo "=================================================================="

# Deploy static dashboard to Firebase Hosting
firebase deploy --only hosting --project="${PROJECT_ID}"

echo "=================================================================="
echo "SUCCESS! Firebase Hosting deployment complete."
echo "=================================================================="
