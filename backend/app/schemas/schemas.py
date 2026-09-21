from datetime import datetime
from pydantic import BaseModel, Field


class BuildingOut(BaseModel):
    id: int
    name: str
    floors: int
    model_config = {"from_attributes": True}


class CarOut(BaseModel):
    id: int
    building_id: int
    label: str
    floor: int
    direction: str
    load: int
    capacity: int
    model_config = {"from_attributes": True}


class CallOut(BaseModel):
    id: int
    building_id: int
    floor: int
    direction: str
    passengers: int
    status: str
    assigned_car_id: int | None
    score: str
    created_at: datetime
    model_config = {"from_attributes": True}


class CallCreate(BaseModel):
    building_id: int
    floor: int = Field(ge=1)
    direction: str
    passengers: int = Field(ge=1, le=8)


class DispatchRequest(BaseModel):
    call_id: int


class LogOut(BaseModel):
    id: int
    call_id: int
    car_id: int | None
    detail: str
    created_at: datetime
    model_config = {"from_attributes": True}


class CongestionFloor(BaseModel):
    floor: int
    # 候梯中人数（现网口径，保留为独立一列）
    waiting: int = 0
    # 派工成功、尚未取消或清客前，仍按候梯层占用的人数
    assigned: int = 0
    # 两列合计
    total: int = 0
