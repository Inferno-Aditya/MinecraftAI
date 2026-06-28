import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional

@dataclass
class GameplayEvent:
    event_type: str
    subtype: str
    dimension: str
    x: float
    y: float
    z: float
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    session_id: Optional[str] = None
    event_uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    importance: int = 1
    source: str = "PLAYER"
    parent_event_uuid: Optional[str] = None
    parent_session_uuid: Optional[str] = None
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_uuid": self.event_uuid,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "subtype": self.subtype,
            "dimension": self.dimension,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "importance": self.importance,
            "source": self.source,
            "parent_event_uuid": self.parent_event_uuid,
            "parent_session_uuid": self.parent_session_uuid,
            "data": self.data
        }

@dataclass
class SessionMetadata:
    session_id: str
    game_version: Optional[str] = None
    mod_version: Optional[str] = None
    backend_version: Optional[str] = "1.0.0"
    world_seed: Optional[str] = None
    world_name: Optional[str] = None
    start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    end_time: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "game_version": self.game_version,
            "mod_version": self.mod_version,
            "backend_version": self.backend_version,
            "world_seed": self.world_seed,
            "world_name": self.world_name,
            "start_time": self.start_time,
            "end_time": self.end_time
        }
