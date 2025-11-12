# src/tracking/manager.py (COMPLETE FILE)
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from collections import OrderedDict

from src.tracking.models import RequestTracker, RequestStatus

logger = logging.getLogger(__name__)


class RequestTrackingManager:
    """Manages request tracking with LRU cache"""

    def __init__(self, max_size: int = 1000, retention_hours: int = 24) -> None:
        self.requests: OrderedDict[str, RequestTracker] = OrderedDict()
        self.max_size = max_size
        self.retention_hours = retention_hours

    def create_request(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        client_ip: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """Create a new request tracker"""
        request_id = str(uuid.uuid4())
        
        tracker = RequestTracker(
            request_id=request_id,
            server_name=server_name,
            tool_name=tool_name,
            arguments=arguments,
            status=RequestStatus.PENDING,
            client_ip=client_ip,
            session_id=session_id
        )
        
        self.requests[request_id] = tracker
        self._cleanup_old_requests()
        
        logger.info(f"📝 Created request {request_id} for {server_name}/{tool_name}")
        return request_id

    def start_request(self, request_id: str) -> None:
        """Mark request as in progress"""
        if request_id in self.requests:
            tracker = self.requests[request_id]
            tracker.status = RequestStatus.IN_PROGRESS
            tracker.started_at = datetime.now(timezone.utc)
            logger.info(f"▶️  Started request {request_id}")

    def complete_request(self, request_id: str, result: Any) -> None:
        """Mark request as completed"""
        if request_id in self.requests:
            tracker = self.requests[request_id]
            tracker.status = RequestStatus.COMPLETED
            tracker.completed_at = datetime.now(timezone.utc)
            tracker.result = result
            
            if tracker.started_at:
                duration = (tracker.completed_at - tracker.started_at).total_seconds() * 1000
                tracker.duration_ms = duration
            
            logger.info(f"✅ Completed request {request_id} in {tracker.duration_ms}ms")

    def fail_request(self, request_id: str, error: str) -> None:
        """Mark request as failed"""
        if request_id in self.requests:
            tracker = self.requests[request_id]
            tracker.status = RequestStatus.FAILED
            tracker.completed_at = datetime.now(timezone.utc)
            tracker.error = error
            
            if tracker.started_at:
                duration = (tracker.completed_at - tracker.started_at).total_seconds() * 1000
                tracker.duration_ms = duration
            
            logger.error(f"❌ Failed request {request_id}: {error}")

    def get_request(self, request_id: str) -> Optional[RequestTracker]:
        """Get request by ID"""
        return self.requests.get(request_id)

    def get_all_requests(
        self,
        limit: int = 100,
        status: Optional[RequestStatus] = None,
        server_name: Optional[str] = None
    ) -> list[RequestTracker]:
        """Get all requests with optional filters"""
        requests = list(self.requests.values())
        
        if status:
            requests = [r for r in requests if r.status == status]
        
        if server_name:
            requests = [r for r in requests if r.server_name == server_name]
        
        # Return most recent first
        requests.reverse()
        return requests[:limit]

    def get_statistics(self) -> dict[str, Any]:
        """Get request statistics"""
        total = len(self.requests)
        by_status = {status: 0 for status in RequestStatus}
        by_server: dict[str, int] = {}
        total_duration = 0.0
        completed_count = 0
        
        for tracker in self.requests.values():
            by_status[tracker.status] += 1
            by_server[tracker.server_name] = by_server.get(tracker.server_name, 0) + 1
            
            # ONLY count requests with COMPLETED status (not FAILED)
            if tracker.status == RequestStatus.COMPLETED:
                if tracker.duration_ms is not None:
                    total_duration += tracker.duration_ms
                    completed_count += 1
        
        avg_duration = total_duration / completed_count if completed_count > 0 else 0
        
        return {
            "total_requests": total,
            "by_status": {status.value: count for status, count in by_status.items()},
            "by_server": by_server,
            "average_duration_ms": round(avg_duration, 2),
            "completed_requests": completed_count
        }

    def _cleanup_old_requests(self) -> None:
        """Remove old requests to maintain max_size and retention"""
        # Remove by age
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.retention_hours)
        to_remove = [
            req_id for req_id, tracker in self.requests.items()
            if tracker.created_at < cutoff
        ]
        
        for req_id in to_remove:
            del self.requests[req_id]
        
        # Remove by size (LRU)
        while len(self.requests) > self.max_size:
            self.requests.popitem(last=False)
        
        if to_remove:
            logger.info(f"🧹 Cleaned up {len(to_remove)} old requests")