from pydantic import BaseModel, Field
from typing import List, Optional

class DestinationUpdateSchema(BaseModel):
    dest_id: int
    status: Optional[str] = None
    limit: Optional[int] = None
    is_optimizer: Optional[int] = None

class DeviceToggleMuteSchema(BaseModel):
    device_id: str
    is_muted: bool

class DeviceInfoUpdateSchema(BaseModel):
    device_id: str
    install_place: Optional[str] = None
    install_count: Optional[int] = None
    network_type: Optional[str] = None
    hostname: Optional[str] = None

class DeviceGroupUpdateSchema(BaseModel):
    device_ids: List[str]
    install_place: Optional[str] = None
    install_count: Optional[int] = None
    network_type: Optional[str] = None
