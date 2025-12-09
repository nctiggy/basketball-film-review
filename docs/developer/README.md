# Developer Guide

This guide helps developers set up, understand, and contribute to the Basketball Film Review application.

## Table of Contents

- [Getting Started](#getting-started)
- [Architecture Overview](#architecture-overview)
- [Local Development](#local-development)
- [Testing](#testing)
- [Contributing](#contributing)

## Getting Started

### Prerequisites

- **Docker** and **Docker Compose** (20.10+)
- **Python** 3.11+ (for local development without Docker)
- **Node.js** 16+ (optional, for frontend tooling)
- **Git**

### Quick Start

```bash
# Clone the repository
git clone https://github.com/your-org/basketball-film-review.git
cd basketball-film-review

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Access the application
open http://localhost:8080
```

## Architecture Overview

See [Architecture Documentation](architecture.md) for detailed system design.

### Technology Stack

**Backend:**
- FastAPI (Python web framework)
- PostgreSQL (database)
- asyncpg (async database driver)
- MinIO (S3-compatible object storage)
- ffmpeg (video processing)
- Kubernetes (orchestration)

**Frontend:**
- Vanilla HTML/CSS/JavaScript
- Nginx (web server)
- Fabric.js (canvas annotations)
- MediaRecorder API (audio recording)

**Authentication:**
- JWT tokens
- Google OAuth 2.0 (coaches)
- Bcrypt password hashing (players/parents)

### Project Structure

```
basketball-film-review/
├── backend/                    # FastAPI application
│   ├── app.py                  # Main application entry point
│   ├── auth/                   # Authentication module
│   │   ├── jwt.py              # JWT token utilities
│   │   ├── oauth.py            # Google OAuth handlers
│   │   ├── password.py         # Password hashing
│   │   └── dependencies.py     # FastAPI auth dependencies
│   ├── middleware/             # Middleware
│   │   └── auth.py             # Rate limiting, security headers
│   ├── routes/                 # API route modules
│   │   ├── auth.py             # Authentication endpoints
│   │   ├── teams.py            # Team management
│   │   ├── players.py          # Player-specific endpoints
│   │   ├── parent.py           # Parent-specific endpoints
│   │   ├── invites.py          # Invite management
│   │   ├── clips.py            # Clip management (legacy)
│   │   ├── assignments.py      # Clip assignments
│   │   ├── annotations.py      # Clip annotations
│   │   └── stats.py            # Statistics
│   ├── models/                 # Pydantic models
│   │   ├── user.py             # User models
│   │   ├── team.py             # Team models
│   │   ├── clip.py             # Clip models
│   │   └── stats.py            # Stats models
│   ├── utils/                  # Utilities
│   │   ├── db.py               # Database helpers
│   │   └── audit_log.py        # Audit logging
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile              # Backend container image
├── frontend/                   # Web frontend
│   ├── index.html              # Main SPA entry point
│   ├── player-parent.html      # Player/parent SPA
│   ├── nginx.conf              # Nginx configuration
│   └── Dockerfile              # Frontend container image
├── helm/                       # Kubernetes deployment
│   ├── Chart.yaml              # Helm chart definition
│   ├── values.yaml             # Default configuration
│   └── templates/              # Kubernetes manifests
├── tests/                      # Test suite
│   ├── conftest.py             # Pytest fixtures
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── security/               # Security tests
├── docs/                       # Documentation
├── docker-compose.yml          # Local development setup
└── README.md                   # Project overview
```

## Local Development

### Using Docker Compose (Recommended)

Docker Compose provides all services (PostgreSQL, MinIO, backend, frontend) with minimal setup.

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Restart a service after code changes
docker-compose restart backend

# Rebuild after dependency changes
docker-compose up -d --build backend

# Stop all services
docker-compose down

# Stop and remove volumes (clean state)
docker-compose down -v
```

### Access Points

- **Frontend**: http://localhost:8080
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

### Running Backend Locally (Without Docker)

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://filmreview:filmreview@localhost:5432/filmreview"
export MINIO_ENDPOINT="localhost:9000"
export MINIO_ACCESS_KEY="minioadmin"
export MINIO_SECRET_KEY="minioadmin"
export MINIO_SECURE="false"
export JWT_SECRET="your-secret-key-for-development"

# Run the application
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Note: You'll still need PostgreSQL and MinIO running (use docker-compose for just those services).

### Database Access

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U filmreview -d filmreview

# Run SQL queries
filmreview=# SELECT * FROM users;
filmreview=# \dt  # List tables
filmreview=# \d users  # Describe users table
filmreview=# \q  # Quit
```

### MinIO Access

Access the MinIO console at http://localhost:9001:
- Username: `minioadmin`
- Password: `minioadmin`

Browse buckets, view uploaded files, and manage objects.

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=html

# Run specific test file
pytest tests/integration/test_auth_api.py

# Run specific test
pytest tests/integration/test_auth_api.py::test_login_success

# Run tests matching a pattern
pytest -k "test_player"

# Verbose output
pytest -v
```

### Test Structure

Tests are organized by type:
- **Unit tests** (`tests/unit/`): Test individual functions and classes
- **Integration tests** (`tests/integration/`): Test API endpoints and database operations
- **Security tests** (`tests/security/`): Test access control and input validation

See [tests/README.md](/Users/craigsmith/code/basketball-film-review/tests/README.md) for detailed testing documentation.

### Writing Tests

Example test:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_team(async_client: AsyncClient, coach_token: str):
    """Test creating a new team"""
    response = await async_client.post(
        "/teams",
        json={"name": "Test Team", "season": "Fall 2024"},
        headers={"Authorization": f"Bearer {coach_token}"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Team"
    assert data["season"] == "Fall 2024"
    assert "id" in data
```

## Contributing

### Code Style

- **Python**: Follow PEP 8
  - Use `black` for formatting: `black backend/`
  - Use `flake8` for linting: `flake8 backend/`
  - Use `mypy` for type checking: `mypy backend/`

- **JavaScript**: Use consistent formatting
  - 2-space indentation
  - Single quotes
  - Semicolons required

### Git Workflow

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and commit:
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

   Use conventional commit messages:
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `test:` - Test changes
   - `refactor:` - Code refactoring
   - `chore:` - Maintenance tasks

3. Push your branch:
   ```bash
   git push origin feature/your-feature-name
   ```

4. Create a Pull Request

### Pull Request Process

1. **Write tests** for new features
2. **Update documentation** if needed
3. **Run tests locally**: `pytest`
4. **Check code style**: `black backend/ && flake8 backend/`
5. **Create PR** with clear description
6. **Address review feedback**
7. **Squash commits** if needed

### Adding New Endpoints

1. **Define Pydantic models** in `backend/models/`
2. **Create route handler** in `backend/routes/`
3. **Add authentication** using `get_current_user` or `require_coach()`
4. **Implement authorization** checks
5. **Add tests** in `tests/integration/`
6. **Update API documentation** in `docs/api/endpoints.md`

Example:

```python
# backend/routes/example.py
from fastapi import APIRouter, Depends
from backend.auth import get_current_user, require_coach
from backend.models.example import ExampleRequest, ExampleResponse

router = APIRouter(prefix="/examples", tags=["Examples"])

@router.post("", response_model=ExampleResponse)
async def create_example(
    request: ExampleRequest,
    current_user: dict = Depends(require_coach())
):
    """Create a new example (coach only)"""
    # Implementation here
    pass
```

## Common Development Tasks

### Adding a Database Migration

Currently, schema changes are manual:

1. Update table creation in `backend/app.py` (in `lifespan()` function)
2. For existing deployments, run ALTER statements manually:
   ```sql
   ALTER TABLE users ADD COLUMN new_field TEXT;
   ```
3. Test migration locally before deploying

### Adding a New User Role

1. Update `users` table CHECK constraint
2. Add role to authentication logic
3. Create role-specific routes if needed
4. Add authorization checks
5. Update frontend to handle new role
6. Write tests for role access

### Debugging

**Backend debugging:**
```python
# Add breakpoints
import pdb; pdb.set_trace()

# Or use ipdb for better experience
import ipdb; ipdb.set_trace()

# Print debug logs
import logging
logger = logging.getLogger(__name__)
logger.debug("Debug message here")
```

**Database debugging:**
```bash
# Check connection
docker-compose exec postgres psql -U filmreview -d filmreview -c "SELECT 1;"

# View recent logs
docker-compose logs postgres | tail -n 50
```

**MinIO debugging:**
```bash
# List all objects in bucket
docker-compose exec minio mc ls local/basketball-clips

# Check bucket policy
docker-compose exec minio mc policy get local/basketball-clips
```

## Performance Considerations

### Database

- Use indexes on frequently queried columns
- Use connection pooling (already configured)
- Avoid N+1 queries (use JOINs)
- Monitor slow queries

### Video Processing

- Clip processing is asynchronous (background tasks)
- ffmpeg runs with optimized settings
- Consider queue system for high volume (not yet implemented)

### API

- Rate limiting is enabled (see `backend/middleware/auth.py`)
- Use pagination for large result sets (not yet implemented)
- Cache frequently accessed data (not yet implemented)

## Troubleshooting

### Backend won't start

```bash
# Check logs
docker-compose logs backend

# Common issues:
# - Database not ready: Wait a few seconds and restart
# - Port already in use: Change port in docker-compose.yml
# - Missing dependencies: Rebuild with --no-cache
```

### Database connection errors

```bash
# Verify database is running
docker-compose ps postgres

# Check connection from backend
docker-compose exec backend python -c "import asyncpg; print('OK')"

# Reset database (WARNING: destroys data)
docker-compose down -v
docker-compose up -d
```

### Video processing fails

```bash
# Check ffmpeg is available
docker-compose exec backend ffmpeg -version

# Check MinIO connectivity
docker-compose exec backend python -c "from minio import Minio; print('OK')"

# View clip processing logs
docker-compose logs backend | grep "process_clip"
```

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [MinIO Documentation](https://min.io/docs/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)

## Next Steps

- [Architecture Documentation](architecture.md)
- [Contributing Guidelines](contributing.md)
- [AI-Assisted Development](ai-development.md)
- [API Documentation](../api/README.md)
- [Operations Guide](../operations/README.md)
