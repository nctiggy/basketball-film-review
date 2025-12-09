# Test Suite for Basketball Film Review

Comprehensive test suite covering unit, integration, and security testing for the Basketball Film Review application.

## Overview

This test suite ensures:
- Authentication and authorization work correctly
- Users can only access data they should have access to
- Input validation and sanitization prevent common vulnerabilities
- All API endpoints function as expected
- Role-based access control is enforced

## Test Structure

```
tests/
├── conftest.py              # Pytest configuration and fixtures
├── utils.py                 # Test helper functions
├── unit/                    # Unit tests for individual functions
│   ├── test_auth.py         # JWT and password hashing tests
│   └── test_validators.py   # Pydantic model validation tests
├── integration/             # API endpoint tests
│   ├── test_auth_api.py     # Authentication endpoints
│   ├── test_teams_api.py    # Team management endpoints
│   ├── test_assignments_api.py  # Clip assignment endpoints
│   ├── test_player_api.py   # Player-specific endpoints
│   └── test_parent_api.py   # Parent-specific endpoints
└── security/                # Security and access control tests
    ├── test_access_control.py   # Authorization tests (CRITICAL)
    └── test_input_validation.py # Input sanitization tests
```

## Running Tests

### Prerequisites

1. Install dependencies:
```bash
pip install -r backend/requirements.txt
pip install pytest pytest-asyncio httpx pytest-timeout
```

2. Set up test database:
```bash
# Create test database
createdb filmreview_test

# Or use Docker Compose
docker-compose up -d postgres
```

3. Set environment variables:
```bash
export TEST_DATABASE_URL="postgresql://filmreview:filmreview@localhost:5432/filmreview_test"
export JWT_SECRET="test-secret-key"
export MINIO_ENDPOINT="localhost:9000"
export MINIO_ACCESS_KEY="minioadmin"
export MINIO_SECRET_KEY="minioadmin"
```

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test Suites

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Security tests only (CRITICAL)
pytest tests/security/ -v

# Run by marker
pytest -m unit
pytest -m integration
pytest -m security
```

### Run with Coverage

```bash
pytest tests/ --cov=backend --cov-report=html --cov-report=term-missing
```

Open `htmlcov/index.html` in a browser to view coverage report.

### Run Specific Tests

```bash
# Run a specific test file
pytest tests/security/test_access_control.py -v

# Run a specific test class
pytest tests/security/test_access_control.py::TestPlayerAccessControl -v

# Run a specific test
pytest tests/security/test_access_control.py::TestPlayerAccessControl::test_player_cannot_access_other_player_clips -v
```

## Test Fixtures

Common fixtures defined in `conftest.py`:

- `db_pool` - Database connection pool
- `async_client` - AsyncClient for API testing
- `test_coach`, `test_player`, `test_parent` - Test user accounts
- `coach_token`, `player_token`, `parent_token` - JWT tokens
- `test_team` - Test team with coach
- `test_game`, `test_video`, `test_clip` - Test game data
- `player_on_team` - Links player to team
- `clip_assignment` - Assigns clip to player
- `parent_child_link` - Links parent to child

## Critical Security Tests

The tests in `tests/security/test_access_control.py` are CRITICAL and must all pass. They verify:

1. **Player Isolation**: Players can only access clips assigned to them
2. **Parent Restrictions**: Parents can only access their linked children's data
3. **Coach Boundaries**: Coaches can only access teams they manage
4. **Token Validation**: Expired and invalid tokens are rejected
5. **ID Guessing Protection**: Random IDs don't grant access

### Security Test Examples

```python
# Player A cannot access Player B's clips
async def test_player_cannot_access_other_player_clips(...)

# Parent cannot access non-linked child's data
async def test_parent_cannot_access_non_linked_child_clips(...)

# Expired tokens are rejected
async def test_expired_token_rejected(...)

# Random IDs don't grant access
async def test_cannot_guess_clip_ids(...)
```

## Test Markers

Tests are marked for organization:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.security` - Security tests
- `@pytest.mark.slow` - Slow-running tests
- `@pytest.mark.db` - Tests requiring database

## CI/CD Integration

Tests run automatically on:
- Push to main or develop branch
- Pull requests

See `.github/workflows/test.yml` for CI configuration.

## Writing New Tests

### Unit Test Template

```python
import pytest

@pytest.mark.unit
class TestMyFeature:
    """Test my feature."""

    def test_something(self):
        """Test something specific."""
        # Arrange
        input_data = "test"

        # Act
        result = my_function(input_data)

        # Assert
        assert result == expected_output
```

### Integration Test Template

```python
import pytest

@pytest.mark.integration
@pytest.mark.asyncio
class TestMyAPI:
    """Test my API endpoint."""

    async def test_endpoint(self, async_client, coach_token):
        """Test API endpoint."""
        response = await async_client.get(
            "/my-endpoint",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "expected_field" in data
```

### Security Test Template

```python
import pytest

@pytest.mark.security
@pytest.mark.asyncio
class TestMySecurityFeature:
    """Test security boundary."""

    async def test_unauthorized_access(self, async_client, player_token, test_resource):
        """Test that unauthorized users cannot access resource."""
        response = await async_client.get(
            f"/restricted/{test_resource['id']}",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        assert response.status_code == 403
```

## Best Practices

1. **Independence**: Each test should be independent and not rely on other tests
2. **Cleanup**: Use fixtures with autouse for database cleanup
3. **Determinism**: Tests should not be flaky or depend on timing
4. **Clear Names**: Test names should describe what they test
5. **AAA Pattern**: Arrange, Act, Assert structure
6. **Fast Execution**: Keep tests fast; use mocks for external services
7. **Comprehensive Coverage**: Test both happy paths and error cases

## Troubleshooting

### Tests Fail with Database Connection Error

```bash
# Ensure PostgreSQL is running
docker-compose up -d postgres

# Verify connection
psql postgresql://filmreview:filmreview@localhost:5432/filmreview_test
```

### Tests Fail with "Table does not exist"

The application creates tables on startup. Ensure the test database is clean and the app lifespan event runs.

### Async Tests Fail

Ensure `pytest-asyncio` is installed and `asyncio_mode = auto` is set in `pytest.ini`.

### Tests are Slow

Run with `-n auto` for parallel execution:
```bash
pip install pytest-xdist
pytest tests/ -n auto
```

## Test Coverage Goals

- **Unit Tests**: > 90% coverage
- **Integration Tests**: All endpoints tested
- **Security Tests**: All access control paths tested
- **Overall**: > 80% coverage

## Continuous Improvement

As new features are added:
1. Write tests first (TDD)
2. Ensure security tests cover new access control
3. Update fixtures as needed
4. Maintain test documentation

## Support

For questions or issues with tests:
1. Check this README
2. Review test examples in the codebase
3. Check CI logs for failure details
