# tests/test_tracking/test_tracking_api.py (COMPLETE CLEAN VERSION)
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestTrackingAPI:
    """Test tracking API endpoints"""

    async def test_get_tracking_requests(self, test_client: AsyncClient) -> None:
        """Test GET /api/tracking/requests"""
        response = await test_client.get("/api/tracking/requests")
        assert response.status_code == 200
        data = response.json()
        assert "requests" in data
        assert isinstance(data["requests"], list)

    async def test_get_tracking_requests_with_filters(self, test_client: AsyncClient) -> None:
        """Test GET /api/tracking/requests with filters"""
        response = await test_client.get(
            "/api/tracking/requests",
            params={"limit": 10, "status": "completed", "server": "test-server"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "requests" in data

    async def test_get_tracking_statistics(self, test_client: AsyncClient) -> None:
        """Test GET /api/tracking/statistics"""
        response = await test_client.get("/api/tracking/statistics")
        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data
        assert "by_status" in data
        assert "by_server" in data
        assert "average_duration_ms" in data

    async def test_get_tracking_request_by_id(self, test_client: AsyncClient) -> None:
        """Test GET /api/tracking/request/{request_id}"""
        response = await test_client.get("/api/tracking/request/non-existent-id")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data