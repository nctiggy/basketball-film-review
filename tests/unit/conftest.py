"""
Minimal conftest for unit tests that don't require database or app imports.
"""

import os
import pytest

# Set test environment variables
os.environ["JWT_SECRET"] = "test-secret-key-do-not-use-in-production"
