"""
Pytest configuration and fixtures for backend tests.
"""
import pytest
import asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient
import sys
import os

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
async def async_client():
    """Create an async test client for the FastAPI app."""
    async with AsyncClient(app=app, base_url="http://test", follow_redirects=True) as ac:
        yield ac
