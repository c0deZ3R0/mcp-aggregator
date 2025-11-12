# src/tracking/models.py
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from enum import Enum


class RequestStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RequestTracker:
    request_id: str
    server_name: str
    tool_name: str
    arguments: dict[str, Any]
    status: RequestStatus
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    client_ip: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "server_name": self.server_name,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "client_ip": self.client_ip,
            "session_id": self.session_id
        }