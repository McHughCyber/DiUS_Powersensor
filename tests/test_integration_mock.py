"""Integration tests against the mock Powersensor server."""

import pytest


@pytest.mark.integration
async def test_mock_powersensor_integration():
    """Placeholder until the mock server is wired into promotion CI."""
    pytest.skip("mock server not wired")
