# app/schemas/vehicle.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class VehicleBase(BaseModel):
    Vehicle_ID: str = Field(..., example="V001")
    Vehicle_Number: str = Field(..., example="AP-01-1234")
    Capacity: int = Field(..., gt=0)
    Status: str = Field(default="Available")

class VehicleCreate(VehicleBase):
    pass

class VehicleUpdate(BaseModel):
    Vehicle_ID: str
    Vehicle_Number: Optional[str] = None
    Status: Optional[str] = None

class VehicleDelete(BaseModel):
    Vehicle_ID: str
    Vehicle_Number: str

class VehicleOut(VehicleBase):
    created_at: datetime
    updated_at: datetime
