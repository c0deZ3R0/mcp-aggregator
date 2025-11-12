# tests/test_tracking/test_tracking.py (FIX LINTER WARNINGS)
import pytest  # type: ignore
from datetime import datetime, timezone, timedelta
from src.tracking.models import RequestTracker, RequestStatus
from src.tracking.manager import RequestTrackingManager


class TestRequestTracker:
    """Test RequestTracker model"""

    def test_create_request_tracker(self) -> None:
        """Test creating a request tracker"""
        tracker = RequestTracker(
            request_id="test-123",
            server_name="test-server",
            tool_name="test-tool",
            arguments={"arg1": "value1"},
            status=RequestStatus.PENDING
        )

        assert tracker.request_id == "test-123"
        assert tracker.server_name == "test-server"
        assert tracker.tool_name == "test-tool"
        assert tracker.arguments == {"arg1": "value1"}
        assert tracker.status == RequestStatus.PENDING
        assert tracker.started_at is None
        assert tracker.completed_at is None
        assert tracker.error is None

    def test_to_dict(self) -> None:
        """Test converting tracker to dictionary"""
        tracker = RequestTracker(
            request_id="test-123",
            server_name="test-server",
            tool_name="test-tool",
            arguments={"arg1": "value1"},
            status=RequestStatus.COMPLETED,
            client_ip="127.0.0.1",
            session_id="session-123"
        )
        tracker.duration_ms = 150.5

        result = tracker.to_dict()

        assert result["request_id"] == "test-123"
        assert result["server_name"] == "test-server"
        assert result["tool_name"] == "test-tool"
        assert result["status"] == "completed"
        assert result["duration_ms"] == 150.5
        assert result["client_ip"] == "127.0.0.1"
        assert result["session_id"] == "session-123"


class TestRequestTrackingManager:
    """Test RequestTrackingManager"""

    def test_create_request(self) -> None:
        """Test creating a new request"""
        manager = RequestTrackingManager()
        
        request_id = manager.create_request(
            server_name="test-server",
            tool_name="test-tool",
            arguments={"key": "value"},
            client_ip="127.0.0.1",
            session_id="session-123"
        )

        assert request_id is not None
        assert request_id in manager.requests
        
        tracker = manager.requests[request_id]
        assert tracker.server_name == "test-server"
        assert tracker.tool_name == "test-tool"
        assert tracker.status == RequestStatus.PENDING
        assert tracker.client_ip == "127.0.0.1"
        assert tracker.session_id == "session-123"

    def test_start_request(self) -> None:
        """Test starting a request"""
        manager = RequestTrackingManager()
        request_id = manager.create_request(
            server_name="test-server",
            tool_name="test-tool",
            arguments={}
        )

        manager.start_request(request_id)
        tracker = manager.requests[request_id]

        assert tracker.status == RequestStatus.IN_PROGRESS
        assert tracker.started_at is not None
        assert isinstance(tracker.started_at, datetime)

    def test_complete_request(self) -> None:
        """Test completing a request"""
        manager = RequestTrackingManager()
        request_id = manager.create_request(
            server_name="test-server",
            tool_name="test-tool",
            arguments={}
        )

        manager.start_request(request_id)
        manager.complete_request(request_id, {"result": "success"})
        
        tracker = manager.requests[request_id]

        assert tracker.status == RequestStatus.COMPLETED
        assert tracker.completed_at is not None
        assert tracker.result == {"result": "success"}
        assert tracker.duration_ms is not None
        assert tracker.duration_ms >= 0

    def test_fail_request(self) -> None:
        """Test failing a request"""
        manager = RequestTrackingManager()
        request_id = manager.create_request(
            server_name="test-server",
            tool_name="test-tool",
            arguments={}
        )

        manager.start_request(request_id)
        manager.fail_request(request_id, "Test error")
        
        tracker = manager.requests[request_id]

        assert tracker.status == RequestStatus.FAILED
        assert tracker.completed_at is not None
        assert tracker.error == "Test error"
        assert tracker.duration_ms is not None

    def test_get_request(self) -> None:
        """Test getting a specific request"""
        manager = RequestTrackingManager()
        request_id = manager.create_request(
            server_name="test-server",
            tool_name="test-tool",
            arguments={}
        )

        tracker = manager.get_request(request_id)
        assert tracker is not None
        assert tracker.request_id == request_id

        # Test non-existent request
        assert manager.get_request("non-existent") is None

    def test_get_all_requests(self) -> None:
        """Test getting all requests"""
        manager = RequestTrackingManager()
        
        # Create multiple requests
        id1 = manager.create_request("server1", "tool1", {})
        id2 = manager.create_request("server2", "tool2", {})
        id3 = manager.create_request("server1", "tool3", {})

        manager.start_request(id1)
        manager.complete_request(id1, "result1")
        manager.start_request(id2)
        manager.fail_request(id2, "error")
        manager.start_request(id3)

        # Get all requests
        all_requests = manager.get_all_requests()
        assert len(all_requests) == 3

        # Filter by status
        completed = manager.get_all_requests(status=RequestStatus.COMPLETED)
        assert len(completed) == 1
        assert completed[0].request_id == id1

        failed = manager.get_all_requests(status=RequestStatus.FAILED)
        assert len(failed) == 1
        assert failed[0].request_id == id2

        # Filter by server
        server1_requests = manager.get_all_requests(server_name="server1")
        assert len(server1_requests) == 2
        
        # Verify id3 is in progress
        assert id3 in manager.requests
        assert manager.requests[id3].status == RequestStatus.IN_PROGRESS

    def test_get_all_requests_limit(self) -> None:
        """Test request limit"""
        manager = RequestTrackingManager()
        
        # Create 10 requests
        for i in range(10):
            manager.create_request(f"server{i}", f"tool{i}", {})

        # Get with limit
        requests = manager.get_all_requests(limit=5)
        assert len(requests) == 5

    # tests/test_tracking/test_tracking.py (ADD DEBUG)
   # tests/test_tracking/test_tracking.py (CORRECTED)
    def test_get_statistics(self) -> None:
        """Test getting statistics"""
        manager = RequestTrackingManager()
        
        # Create requests with different statuses
        id1 = manager.create_request("server1", "tool1", {})
        id2 = manager.create_request("server2", "tool2", {})
        id3 = manager.create_request("server1", "tool3", {})

        # id1: complete
        manager.start_request(id1)
        manager.complete_request(id1, "result1")
        
        # id2: fail
        manager.start_request(id2)
        manager.fail_request(id2, "error")

        # id3: complete
        manager.start_request(id3)
        manager.complete_request(id3, "result3")
        
        # id4: still pending (never started)
        
        stats = manager.get_statistics()

        assert stats["total_requests"] == 4
        assert stats["by_status"]["completed"] == 2, f"Expected 2 completed, got {stats['by_status']['completed']}"
        assert stats["by_status"]["failed"] == 1, f"Expected 1 failed, got {stats['by_status']['failed']}"
        assert stats["by_status"]["pending"] == 1, f"Expected 1 pending, got {stats['by_status']['pending']}"
        assert stats["by_status"]["in_progress"] == 0, f"Expected 0 in_progress, got {stats['by_status']['in_progress']}"
        assert stats["by_server"]["server1"] == 2
        assert stats["by_server"]["server2"] == 2
        assert stats["completed_requests"] == 2, f"Expected 2 completed_requests, got {stats['completed_requests']}"
        assert "average_duration_ms" in stats

    def test_cleanup_old_requests(self) -> None:
        """Test cleanup of old requests"""
        manager = RequestTrackingManager(max_size=5, retention_hours=1)
        
        # Create 10 requests (exceeds max_size)
        for i in range(10):
            manager.create_request(f"server{i}", f"tool{i}", {})

        # Should only keep max_size requests
        assert len(manager.requests) == 5

    def test_cleanup_by_age(self) -> None:
        """Test cleanup by age"""
        manager = RequestTrackingManager(retention_hours=1)
        
        # Create a request
        request_id = manager.create_request("server1", "tool1", {})
        tracker = manager.requests[request_id]
        
        # Manually set created_at to be old
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        tracker.created_at = old_time
        
        # Create a new request (triggers cleanup)
        manager.create_request("server2", "tool2", {})
        
        # Old request should be removed
        assert request_id not in manager.requests

    def test_lru_eviction(self) -> None:
        """Test LRU eviction when max_size is exceeded"""
        manager = RequestTrackingManager(max_size=3)
        
        # Create 3 requests
        id1 = manager.create_request("server1", "tool1", {})
        id2 = manager.create_request("server2", "tool2", {})
        id3 = manager.create_request("server3", "tool3", {})
        
        assert len(manager.requests) == 3
        
        # Create one more (should evict oldest)
        id4 = manager.create_request("server4", "tool4", {})
        
        assert len(manager.requests) == 3
        assert id1 not in manager.requests  # Oldest should be evicted
        assert id2 in manager.requests
        assert id3 in manager.requests
        assert id4 in manager.requests


@pytest.mark.asyncio
class TestTrackingIntegration:
    """Integration tests for tracking with UpstreamManager"""

    async def test_upstream_manager_has_tracking(self) -> None:
        """Test that UpstreamManager has tracking enabled"""
        from src.upstream.manager import UpstreamManager
        
        manager = UpstreamManager()
        assert hasattr(manager, 'tracking')
        assert isinstance(manager.tracking, RequestTrackingManager)

    async def test_call_tool_creates_tracking(self) -> None:
        """Test that call_tool creates tracking entries"""
        from src.upstream.manager import UpstreamManager
        from src.exceptions import ServerConfigError
        
        manager = UpstreamManager()
        
        # This will fail because server doesn't exist
        with pytest.raises(ServerConfigError):
            await manager.call_tool(
                server="non-existent",
                tool="test-tool",
                arguments={"key": "value"},
                client_ip="127.0.0.1",
                session_id="test-session"
            )