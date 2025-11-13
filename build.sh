#!/bin/bash

# Build script for Basketball Film Review application
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_REGISTRY="${IMAGE_REGISTRY:-localhost:5000}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
BACKEND_IMAGE="${IMAGE_REGISTRY}/basketball-film-review-backend:${IMAGE_TAG}"
FRONTEND_IMAGE="${IMAGE_REGISTRY}/basketball-film-review-frontend:${IMAGE_TAG}"

echo -e "${GREEN}Building Basketball Film Review Application${NC}"
echo "Registry: ${IMAGE_REGISTRY}"
echo "Tag: ${IMAGE_TAG}"
echo ""

# Build backend
echo -e "${YELLOW}Building backend image...${NC}"
docker build -t "${BACKEND_IMAGE}" ./backend
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Backend image built successfully${NC}"
else
    echo -e "${RED}✗ Failed to build backend image${NC}"
    exit 1
fi

# Build frontend
echo -e "${YELLOW}Building frontend image...${NC}"
docker build -t "${FRONTEND_IMAGE}" ./frontend
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Frontend image built successfully${NC}"
else
    echo -e "${RED}✗ Failed to build frontend image${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Build completed successfully!${NC}"
echo ""
echo "Images built:"
echo "  - ${BACKEND_IMAGE}"
echo "  - ${FRONTEND_IMAGE}"
echo ""

# Ask if user wants to push images
read -p "Do you want to push images to registry? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Pushing images...${NC}"
    docker push "${BACKEND_IMAGE}"
    docker push "${FRONTEND_IMAGE}"
    echo -e "${GREEN}✓ Images pushed successfully${NC}"
else
    echo "Skipping push to registry"
fi

echo ""
echo "To use these images with Helm, update values.yaml:"
echo ""
echo "backend:"
echo "  image:"
echo "    repository: ${IMAGE_REGISTRY}/basketball-film-review-backend"
echo "    tag: ${IMAGE_TAG}"
echo ""
echo "frontend:"
echo "  image:"
echo "    repository: ${IMAGE_REGISTRY}/basketball-film-review-frontend"
echo "    tag: ${IMAGE_TAG}"
