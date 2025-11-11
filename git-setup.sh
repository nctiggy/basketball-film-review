#!/bin/bash

# Git Repository Setup Script for Basketball Film Review
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

function print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

function print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

function print_error() {
    echo -e "${RED}✗ $1${NC}"
}

function print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_header "Git Repository Setup"

# Check if git is installed
if ! command -v git &> /dev/null; then
    print_error "git not found. Please install git first."
    exit 1
fi
print_success "git found"

echo ""
echo "This script will help you push the Basketball Film Review project to GitHub."
echo ""

# Get repository URL
read -p "Enter your GitHub repository URL (e.g., https://github.com/username/basketball-film-review.git): " REPO_URL

if [ -z "$REPO_URL" ]; then
    print_error "Repository URL is required"
    exit 1
fi

echo ""
print_header "Initializing Git Repository"

# Initialize git if not already done
if [ ! -d ".git" ]; then
    git init
    print_success "Git repository initialized"
else
    print_warning "Git repository already initialized"
fi

# Add all files
git add .
print_success "Files staged"

# Create initial commit
if git rev-parse HEAD >/dev/null 2>&1; then
    # Repository has commits
    read -p "Create a new commit? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter commit message: " COMMIT_MSG
        git commit -m "$COMMIT_MSG"
        print_success "New commit created"
    fi
else
    # First commit
    git commit -m "Initial commit: Basketball Film Review application

- Complete FastAPI backend with video processing
- HTML/CSS/JS frontend
- Full Helm chart with PostgreSQL and MinIO dependencies
- Docker Compose for local development
- Build and deployment scripts
- Comprehensive documentation"
    print_success "Initial commit created"
fi

# Add remote
if git remote get-url origin >/dev/null 2>&1; then
    print_warning "Remote 'origin' already exists"
    read -p "Update remote URL? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git remote set-url origin "$REPO_URL"
        print_success "Remote URL updated"
    fi
else
    git remote add origin "$REPO_URL"
    print_success "Remote 'origin' added"
fi

# Set main branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
    git branch -M main
    print_success "Branch renamed to 'main'"
fi

echo ""
print_header "Ready to Push"
echo "Repository: $REPO_URL"
echo "Branch: main"
echo ""

read -p "Push to GitHub now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    print_warning "You may be prompted for GitHub credentials"
    echo ""
    
    git push -u origin main
    
    if [ $? -eq 0 ]; then
        echo ""
        print_success "Successfully pushed to GitHub!"
        echo ""
        echo "Your repository is now available at:"
        echo "$REPO_URL"
        echo ""
        echo "Next steps:"
        echo "1. Go to your GitHub repository"
        echo "2. Add a description and topics"
        echo "3. Consider adding:"
        echo "   - GitHub Actions for CI/CD"
        echo "   - Branch protection rules"
        echo "   - Issue templates"
    else
        echo ""
        print_error "Push failed. Common issues:"
        echo "  - Repository doesn't exist (create it on GitHub first)"
        echo "  - Authentication failed (check your credentials)"
        echo "  - No permission (check repository access)"
        echo ""
        echo "To retry manually:"
        echo "  git push -u origin main"
    fi
else
    echo ""
    print_warning "Push skipped. To push later, run:"
    echo "  git push -u origin main"
fi

echo ""
print_header "Git Setup Complete"
