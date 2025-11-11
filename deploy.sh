#!/bin/bash

# Deployment helper script for Basketball Film Review
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
NAMESPACE="${NAMESPACE:-film-review}"
RELEASE_NAME="${RELEASE_NAME:-basketball-film-review}"
VALUES_FILE="${VALUES_FILE:-values-custom.yaml}"

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

function check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl not found. Please install kubectl."
        exit 1
    fi
    print_success "kubectl found"
    
    # Check helm
    if ! command -v helm &> /dev/null; then
        print_error "helm not found. Please install Helm 3."
        exit 1
    fi
    print_success "helm found"
    
    # Check cluster access
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot access Kubernetes cluster. Check your kubeconfig."
        exit 1
    fi
    print_success "Kubernetes cluster accessible"
    
    echo ""
}

function update_dependencies() {
    print_header "Updating Helm Dependencies"
    
    cd helm
    helm dependency update
    cd ..
    
    print_success "Dependencies updated"
    echo ""
}

function create_namespace() {
    print_header "Creating Namespace"
    
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        print_warning "Namespace $NAMESPACE already exists"
    else
        kubectl create namespace "$NAMESPACE"
        print_success "Namespace $NAMESPACE created"
    fi
    
    echo ""
}

function install_application() {
    print_header "Installing Application"
    
    if [ ! -f "helm/$VALUES_FILE" ]; then
        print_error "Values file helm/$VALUES_FILE not found!"
        echo "Please create it from helm/values-production-example.yaml"
        exit 1
    fi
    
    helm install "$RELEASE_NAME" ./helm \
        -f "./helm/$VALUES_FILE" \
        --namespace "$NAMESPACE" \
        --wait \
        --timeout 10m
    
    print_success "Application installed"
    echo ""
}

function upgrade_application() {
    print_header "Upgrading Application"
    
    if [ ! -f "helm/$VALUES_FILE" ]; then
        print_error "Values file helm/$VALUES_FILE not found!"
        exit 1
    fi
    
    helm upgrade "$RELEASE_NAME" ./helm \
        -f "./helm/$VALUES_FILE" \
        --namespace "$NAMESPACE" \
        --wait \
        --timeout 10m
    
    print_success "Application upgraded"
    echo ""
}

function uninstall_application() {
    print_header "Uninstalling Application"
    
    helm uninstall "$RELEASE_NAME" --namespace "$NAMESPACE"
    
    print_success "Application uninstalled"
    echo ""
    
    read -p "Do you want to delete the namespace $NAMESPACE? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl delete namespace "$NAMESPACE"
        print_success "Namespace deleted"
    fi
}

function show_status() {
    print_header "Application Status"
    
    echo "Helm Release:"
    helm list -n "$NAMESPACE"
    echo ""
    
    echo "Pods:"
    kubectl get pods -n "$NAMESPACE"
    echo ""
    
    echo "Services:"
    kubectl get svc -n "$NAMESPACE"
    echo ""
    
    echo "PVCs:"
    kubectl get pvc -n "$NAMESPACE"
    echo ""
}

function show_logs() {
    print_header "Application Logs"
    
    echo "Select component:"
    echo "1) Backend"
    echo "2) Frontend"
    read -p "Choice: " choice
    
    case $choice in
        1)
            kubectl logs -n "$NAMESPACE" -l component=backend -f --tail=100
            ;;
        2)
            kubectl logs -n "$NAMESPACE" -l component=frontend -f --tail=100
            ;;
        *)
            print_error "Invalid choice"
            ;;
    esac
}

function get_access_info() {
    print_header "Access Information"
    
    SERVICE_TYPE=$(kubectl get svc "$RELEASE_NAME-frontend" -n "$NAMESPACE" -o jsonpath='{.spec.type}')
    
    echo "Service Type: $SERVICE_TYPE"
    echo ""
    
    if [ "$SERVICE_TYPE" = "LoadBalancer" ]; then
        echo "Waiting for LoadBalancer IP..."
        EXTERNAL_IP=""
        while [ -z "$EXTERNAL_IP" ]; do
            EXTERNAL_IP=$(kubectl get svc "$RELEASE_NAME-frontend" -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
            if [ -z "$EXTERNAL_IP" ]; then
                EXTERNAL_IP=$(kubectl get svc "$RELEASE_NAME-frontend" -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
            fi
            [ -z "$EXTERNAL_IP" ] && sleep 5
        done
        echo "Access URL: http://$EXTERNAL_IP"
    elif [ "$SERVICE_TYPE" = "NodePort" ]; then
        NODE_PORT=$(kubectl get svc "$RELEASE_NAME-frontend" -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].nodePort}')
        NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="ExternalIP")].address}')
        if [ -z "$NODE_IP" ]; then
            NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
        fi
        echo "Access URL: http://$NODE_IP:$NODE_PORT"
    else
        echo "Service type is ClusterIP. Use port-forward:"
        echo "kubectl port-forward -n $NAMESPACE svc/$RELEASE_NAME-frontend 8080:80"
        echo "Then access: http://localhost:8080"
    fi
    
    echo ""
    print_success "Application is ready!"
}

# Main menu
function show_menu() {
    echo ""
    print_header "Basketball Film Review - Deployment Helper"
    echo "1) Install (fresh installation)"
    echo "2) Upgrade (update existing installation)"
    echo "3) Uninstall"
    echo "4) Status"
    echo "5) Logs"
    echo "6) Get Access Info"
    echo "7) Exit"
    echo ""
    read -p "Select an option: " choice
    
    case $choice in
        1)
            check_prerequisites
            update_dependencies
            create_namespace
            install_application
            get_access_info
            ;;
        2)
            check_prerequisites
            update_dependencies
            upgrade_application
            get_access_info
            ;;
        3)
            uninstall_application
            ;;
        4)
            show_status
            show_menu
            ;;
        5)
            show_logs
            show_menu
            ;;
        6)
            get_access_info
            show_menu
            ;;
        7)
            exit 0
            ;;
        *)
            print_error "Invalid option"
            show_menu
            ;;
    esac
}

# Run
show_menu
