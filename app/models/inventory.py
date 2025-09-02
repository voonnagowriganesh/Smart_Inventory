# app/models/inventory.py
"""
Pydantic schemas and helpers for Inventory Management (MongoDB + Motor async)
- Save as: app/models/inventory.py
- Category: REQUIRED (free-text)
- Batch-wise design with UTC-aware datetimes
"""
 
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal, Dict
from datetime import datetime, date, timezone
from uuid import uuid4
 
 
# -----------------------------
# Helpers
# -----------------------------
def utc_now() -> datetime:
    return datetime.now(timezone.utc)
 
 
def generate_batch_no(product_id: str, hub_id: str) -> str:
    """Generates a reasonably unique batch id."""
    ts = utc_now().strftime("%Y%m%d%H%M%S")
    return f"{product_id}-{hub_id}-{ts}-{uuid4().hex[:6]}"
 
 
# -----------------------------
# Request Schemas
# -----------------------------
class RegisterInventory(BaseModel):
    Hub_ID: str = Field(..., description="Hub identifier (must exist)")
    Product_ID: str = Field(..., description="Unique product SKU/ID")
    Product_Name: str = Field(..., description="Product name")
    Quantity: int = Field(..., gt=0, description="Quantity for this batch (must be > 0)")
    Value: float = Field(..., ge=0.0, description="Total purchase value for this batch (currency)")
    Selling_Price: float = Field(..., ge=0.0, description="Per-unit selling price")
    Category: str = Field(..., description="Category (required, free-text)")
    Product_Description: Optional[str] = Field(None, description="Optional description")
    Expiry_Date: date = Field(..., description="Expiry date YYYY-MM-DD for this batch")
    Brand: Optional[str] = Field(None, description="Brand name (optional)")
    Batch_No: Optional[str] = Field(None, description="Optional batch id; system generates if omitted")
    Purchase_Ref: Optional[str] = Field(None, description="Optional purchase reference (PO number)")
 
    @validator("Category")
    def category_required_and_strip(cls, v: str) -> str:
        if v is None or not isinstance(v, str) or not v.strip():
            raise ValueError("Category is required and cannot be empty")
        return v.strip()
 
    @validator("Product_ID", "Product_Name", "Hub_ID")
    def strip_mandatory_strings(cls, v: str) -> str:
        return v.strip()
 
    class Config:
        schema_extra = {
            "example": {
                "Hub_ID": "HUB_001",
                "Product_ID": "PROD_101",
                "Product_Name": "A1 Rice 25kg",
                "Quantity": 100,
                "Value": 4000.0,
                "Selling_Price": 45.0,
                "Category": "Grains",
                "Product_Description": "Premium rice 25kg pack",
                "Expiry_Date": "2026-01-01",
                "Brand": "GoodGrain",
                # "Batch_No": "optional-if-you-want"
            }
        }
 
 
class UpdateInventory(BaseModel):
    Hub_ID: str = Field(..., description="Hub identifier (must exist)")
    Product_ID: str = Field(..., description="Product SKU/ID to update")
    Product_Name: Optional[str] = Field(None, description="Optional master update")
    Quantity: Optional[int] = Field(None, gt=0, description="Quantity to ADD (if provided) - must be > 0")
    Value: Optional[float] = Field(None, ge=0.0, description="Purchase total for the added quantity")
    Selling_Price: Optional[float] = Field(None, ge=0.0)
    Category: Optional[str] = Field(None)
    Product_Description: Optional[str] = Field(None)
    Expiry_Date: Optional[date] = Field(None, description="Expiry date for this new stock (if present)")
    Brand: Optional[str] = Field(None)
    Batch_No: Optional[str] = Field(None, description="If matches existing batch -> merge; else create new")
 
    @validator("Category")
    def strip_category_if_present(cls, v):
        if v is None:
            return v
        s = v.strip()
        if s == "":
            raise ValueError("Category cannot be empty string")
        return s
 
    class Config:
        schema_extra = {
            "example": {
                "Hub_ID": "HUB_001",
                "Product_ID": "PROD_101",
                "Quantity": 50,
                "Value": 2000.0,
                "Expiry_Date": "2026-06-01",
            }
        }
 
 
class DispatchRequest(BaseModel):
    Product_ID: str = Field(..., description="Product SKU/ID to dispatch")
    Quantity: int = Field(..., gt=0, description="Quantity to dispatch (must be > 0)")
    From_Hub_ID: str = Field(..., description="Source hub")
    To_Hub_ID: str = Field(..., description="Destination hub")
    Product_Name: Optional[str] = None
    Request_Ref: Optional[str] = None
    Notes: Optional[str] = None
 
    @validator("Product_ID", "From_Hub_ID", "To_Hub_ID")
    def strip_ids(cls, v: str) -> str:
        return v.strip()
 
class DispatchReceiveRequest(BaseModel):
    dispatch_id: str
 
# -----------------------------
# Output / Response Schemas
# -----------------------------
class BatchOut(BaseModel):
    Product_ID: str
    Hub_ID: str
    Batch_No: str
    Quantity: int
    Expiry_Date: date
    Purchase_Value: float
    Purchase_Unit_Price: float
    Created_At: datetime
    Last_Updated: Optional[datetime] = None
    Status: Literal["active", "depleted", "archived"]
 
 
class ProductSummaryOut(BaseModel):
    Product_ID: str
    Product_Name: str
    Hub_ID: str
    Total_Quantity: int
    Category: str
    Brand: Optional[str]
    Nearest_Expiry: Optional[date]
    Batches_Count: int
 
 
class DispatchOut(BaseModel):
    dispatch_id: str
    Product_ID: str
    From_Hub_ID: str
    To_Hub_ID: str
    Quantity_Dispatched: int
    Batch_Consumption: List[Dict]  # list of { Batch_No, Qty, Unit_Cost }
    Vehicle_Assigned: Optional[str] = None
    Driver_Assigned: Optional[str] = None
    Status: Literal["In-Progress", "In-Transit", "Completed", "Cancelled"]
    Timestamp: datetime
 
 
class StockTransactionOut(BaseModel):
    transaction_id: str
    type: Literal["IN", "OUT", "ADJUSTMENT", "ARCHIVE"]
    Product_ID: str
    Hub_ID: str
    Batch_No: Optional[str]
    Quantity: int
    Unit_Price: Optional[float]
    Total_Value: Optional[float]
    reference: Optional[str]
    timestamp: datetime
    remarks: Optional[str]
 
