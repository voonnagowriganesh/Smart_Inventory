# services/driver_service.py
from pymongo import ReturnDocument
from datetime import datetime
from uuid import uuid4
from typing import List, Optional
from app.models.driver import DriverCreate, DriverUpdate, DriverOut
from app.db.mongodb import db  # your MongoDB/Motor async client
import uuid
from fastapi import HTTPException
from app.utiles.logger import get_logger

logger = get_logger(__name__)

# ------------------------
# Create Driver
# ------------------------
async def create_driver(driver: DriverCreate) -> DriverOut:
    """
    Create a new driver record.
    Validates age, assigns UUID, and inserts into MongoDB.
    """
    logger.info("Creating new driver with name=%s, license=%s", driver.name, driver.license_number)

    # Business validation → Age should be less than 50
    if driver.age > 50:
        logger.warning("Driver creation failed: Age %s is greater than 50", driver.age)
        raise HTTPException(status_code=400, detail="Age should be less than 50")

    driver_id = str(uuid4()) # Generate unique driver_id
    driver_doc = {
        "driver_id": driver_id,
        "name": driver.name,
        "license_number": driver.license_number,
        "age": driver.age,
        "status": "active",
        "hub_id": driver.hub_id,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "retired_reason": None
    }

    await db.drivers.insert_one(driver_doc)
    logger.info("Driver created successfully: driver_id=%s", driver_id)
    return DriverOut(**driver_doc)


# ------------------------
# Get Driver by ID
# ------------------------
async def get_driver_by_id(driver_id: str) -> Optional[DriverOut]:
    """
    Fetch a driver by driver_id, ignoring deleted drivers.
    """
    logger.debug("Fetching driver by ID: %s", driver_id)
    # Query only non-deleted drivers
    doc = await db.drivers.find_one({"driver_id": str(driver_id), "status": {"$ne": "deleted"}})
    if doc:
        logger.info("Driver found: driver_id=%s", driver_id)
        return DriverOut(**doc)

    logger.warning("Driver not found: driver_id=%s", driver_id)
    return None


# ------------------------
# Search Drivers
# ------------------------
async def search_drivers(
    name: Optional[str] = None,
    license_number: Optional[str] = None,
    status: Optional[str] = None,
    hub_id: Optional[str] = None,
    limit: int = 10,
    skip: int = 0
) -> List[DriverOut]:
    """
    Search drivers with optional filters (name, license_number, status, hub_id).
    Supports pagination via limit/skip.
    """
    logger.debug("Searching drivers with filters: name=%s, license=%s, status=%s, hub_id=%s",
                 name, license_number, status, hub_id)

    query = {"status": {"$ne": "deleted"}}
    if name:
        query["name"] = {"$regex": name, "$options": "i"}
    if license_number:
        query["license_number"] = license_number
    if status:
        query["status"] = status
    if hub_id:
        query["hub_id"] = hub_id

    cursor = db.drivers.find(query).skip(skip).limit(limit)
    results = [DriverOut(**doc) async for doc in cursor]

    logger.info("Search completed. Found %s drivers", len(results))
    return results


# ------------------------
# Update Driver
# ------------------------
async def update_driver(driver_update: DriverUpdate) -> Optional[DriverOut]:
    """
    Update driver details by driver_id.
    Skips deleted drivers, updates timestamps, converts UUID fields to str.
    """
    logger.info("Updating driver: driver_id=%s", driver_update.driver_id)

    # Prepare update fields
    update_data = {}
    for k, v in driver_update.dict(exclude_unset=True).items():
        if isinstance(v, uuid.UUID):  # Convert UUID → string
            update_data[k] = str(v)
        else:
            update_data[k] = v
    update_data["updated_at"] = datetime.utcnow()

    driver_id_str = str(driver_update.driver_id)

    result = await db.drivers.find_one_and_update(
        {"driver_id": driver_id_str, "status": {"$ne": "deleted"}},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER
    )

    if result:
        logger.info("Driver updated successfully: driver_id=%s", driver_id_str)
        return DriverOut(**result)

    logger.warning("Driver update failed: driver_id=%s not found or deleted", driver_id_str)
    return None


# ------------------------
# Delete Driver (Soft Delete)
# ------------------------
async def delete_driver(driver_id: str) -> bool:
    """
    Soft delete a driver by marking status as 'deleted'.
    """
    logger.info("Deleting driver (soft delete): driver_id=%s", driver_id)

    result = await db.drivers.update_one(
        {"driver_id": str(driver_id), "status": {"$ne": "deleted"}},
        {"$set": {
            "status": "deleted",
            "retired_reason": "Deleted",
            "updated_at": datetime.utcnow()
        }}
    )

    if result.modified_count > 0:
        logger.info("Driver soft deleted successfully: driver_id=%s", driver_id)
        return True

    logger.warning("Driver deletion failed: driver_id=%s not found or already deleted", driver_id)
    return False


# ------------------------
# Retire Old Drivers (Batch Audit)
# ------------------------
async def retire_old_drivers() -> int:
    """
    Retire all drivers whose age > 50 and status is active.
    Returns the count of retired drivers.
    """
    logger.info("Running batch retirement for drivers age > 50")

    result = await db.drivers.update_many(
        {"age": {"$gt": 50}, "status": "active"},
        {"$set": {
            "status": "retired",
            "retired_reason": "Age > 50",
            "updated_at": datetime.utcnow()
        }}
    )

    logger.info("Retired %s drivers due to age > 50", result.modified_count)
    return result.modified_count
