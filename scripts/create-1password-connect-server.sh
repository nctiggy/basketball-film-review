#!/bin/bash
# Setup 1Password Connect secrets for Kubernetes
#
# This script can either:
# 1. Create a new Connect server (--create-server)
# 2. Use existing credentials from 1Password vault (default)
#
# Prerequisites:
# - 1Password CLI installed and signed in (eval $(op signin))
# - kubectl configured with cluster access
# - KUBECONFIG environment variable set

set -e

NAMESPACE="${NAMESPACE:-film-review}"
CREATE_SERVER=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --create-server)
            CREATE_SERVER=true
            shift
            ;;
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--create-server] [--namespace <namespace>]"
            exit 1
            ;;
    esac
done

echo "Setting up 1Password Connect secrets in namespace: ${NAMESPACE}"

# Check if signed in
if ! op whoami > /dev/null 2>&1; then
    echo "Please sign in to 1Password first:"
    echo "  eval \$(op signin)"
    exit 1
fi

# Check if kubectl is configured
if ! kubectl cluster-info &>/dev/null; then
    echo "Error: kubectl is not configured. Set KUBECONFIG or configure kubectl."
    exit 1
fi

# Create namespace if it doesn't exist
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

if [ "$CREATE_SERVER" = true ]; then
    # Create new Connect server
    VAULT_NAME="k8s"
    SERVER_NAME="basketball-film-review-k8s"

    echo "Creating Connect server '${SERVER_NAME}'..."

    VAULT_ID=$(op vault get "${VAULT_NAME}" --format json | jq -r '.id')
    echo "Vault ID: ${VAULT_ID}"

    op connect server create "${SERVER_NAME}" --vaults "${VAULT_ID}" > ./1password-connect-server.json

    CREDS_BASE64=$(cat ./1password-connect-server.json | jq -r '.credentials' | base64)
    CONNECT_TOKEN=$(cat ./1password-connect-server.json | jq -r '.token')

    echo "✅ Connect server created successfully!"
else
    # Use existing credentials from 1Password
    echo "Fetching existing 1Password Connect credentials..."

    TEMP_CREDS=$(mktemp)
    op document get "homeops Credentials File" --vault Personal --out-file "${TEMP_CREDS}"

    # Base64 encode the credentials (required by 1Password Connect)
    CREDS_BASE64=$(cat "${TEMP_CREDS}" | base64)
    rm -f "${TEMP_CREDS}"

    echo "Fetching 1Password Connect token..."
    CONNECT_TOKEN=$(op item get "homeops Access Token: k8s operator" --vault Personal --fields credential)
fi

# Create the op-credentials secret
echo "Creating op-credentials secret..."
kubectl create secret generic op-credentials \
    --namespace ${NAMESPACE} \
    --from-literal=1password-credentials.json="${CREDS_BASE64}" \
    --dry-run=client -o yaml | kubectl apply -f -

# Create the onepassword-connect-token secret
echo "Creating onepassword-connect-token secret..."
kubectl create secret generic onepassword-connect-token \
    --namespace ${NAMESPACE} \
    --from-literal=token="${CONNECT_TOKEN}" \
    --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "✅ 1Password Connect secrets created in namespace ${NAMESPACE}"
echo ""
echo "To verify, run:"
echo "  kubectl get secrets -n ${NAMESPACE} | grep -E 'op-credentials|onepassword-connect-token'"
echo ""
echo "To restart 1Password Connect (if already deployed):"
echo "  kubectl rollout restart deployment/onepassword-connect -n ${NAMESPACE}"
