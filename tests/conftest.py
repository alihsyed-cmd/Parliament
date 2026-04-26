"""
Shared pytest fixtures for the Parliament test suite.

Pytest will automatically discover this file and make these fixtures
available to all tests in the tests/ directory.
"""

import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load environment variables before importing project modules
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Make the scripts/ directory importable
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


@pytest.fixture(scope="session")
def registry():
    """
    Load the JurisdictionRegistry once per test session.

    Using scope='session' means all tests share a single registry instance.
    Without this, every test would reload all boundary files (~5 seconds each).
    """
    from registry import JurisdictionRegistry
    return JurisdictionRegistry()
