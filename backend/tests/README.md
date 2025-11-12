# Backend Tests

This directory contains unit and integration tests for the Basketball Film Review backend API.

## Test Structure

- `test_api.py` - Integration tests for API endpoints
- `test_units.py` - Unit tests for utility functions
- `conftest.py` - Pytest fixtures and configuration

## Running Tests

### Run all tests
```bash
pytest
```

### Run with verbose output
```bash
pytest -v
```

### Run only unit tests
```bash
pytest -m unit
```

### Run only integration tests
```bash
pytest -m integration
```

### Run specific test file
```bash
pytest tests/test_api.py
```

### Run specific test class or function
```bash
pytest tests/test_api.py::TestGameOperations::test_create_game
```

### Run with coverage report
```bash
pytest --cov=app --cov-report=html
```

## CI/CD Integration

These tests are designed to run in CI/CD pipelines. Make sure:
1. PostgreSQL database is running and accessible
2. MinIO is running and accessible
3. Environment variables are set correctly

The tests will use the same database and MinIO as the application. For isolated testing in CI, consider using separate test instances.

## Adding New Tests

1. Add integration tests to `test_api.py` for new API endpoints
2. Add unit tests to `test_units.py` for new utility functions
3. Add fixtures to `conftest.py` if you need shared test setup
4. Mark tests appropriately with `@pytest.mark.unit` or `@pytest.mark.integration`
