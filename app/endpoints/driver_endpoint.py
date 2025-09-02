# endpoints/driver_endpoints.py

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from app.models.driver import DriverCreate, DriverUpdate, DriverOut, DriverIdRequest
from app.services import driver_service
from app.utiles.decoratores import handle_exceptions
from app.utiles.logger import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

# APIRouter for driver management
router = APIRouter(prefix="/drivers", tags=["Drivers"])

# ======================================================
# Driver Routes
# Exposes REST API endpoints for driver operations
# ======================================================


# ---------------- Create Driver ----------------
@handle_exceptions
@router.post("/register_driver", response_model=DriverOut)
async def create_driver(driver: DriverCreate):
    """
    Endpoint: Register a new driver.
    Calls service layer → driver_service.create_driver.
    """
    logger.info("API Request → Register Driver: name=%s, license=%s", driver.name, driver.license_number)
    result = await driver_service.create_driver(driver)
    logger.info("API Response → Driver registered successfully: driver_id=%s", result.driver_id)
    return result


# ---------------- Get Driver by ID ----------------
@handle_exceptions
@router.get("/get_driver_by_id", response_model=DriverOut)
async def get_driver(payload: DriverIdRequest):
    """
    Endpoint: Get driver details by ID.
    Calls service layer → driver_service.get_driver_by_id.
    """
    logger.info("API Request → Get Driver by ID: driver_id=%s", payload.driver_id)
    driver = await driver_service.get_driver_by_id(payload.driver_id)

    if not driver:
        logger.warning("API Response → Driver not found: driver_id=%s", payload.driver_id)
        raise HTTPException(status_code=404, detail="Driver not found")

    logger.info("API Response → Driver found: driver_id=%s", payload.driver_id)
    return driver


# ---------------- Search Drivers ----------------
@handle_exceptions
@router.get("/search_driver", response_model=List[DriverOut])
async def search_drivers(
    name: Optional[str] = None,
    license_number: Optional[str] = None,
    status: Optional[str] = None,
    hub_id: Optional[str] = None,
    limit: int = 10,
    skip: int = 0
):
    """
    Endpoint: Search drivers with optional filters.
    Calls service layer → driver_service.search_drivers.
    """
    logger.info(
        "API Request → Search Drivers: name=%s, license=%s, status=%s, hub_id=%s, limit=%s, skip=%s",
        name, license_number, status, hub_id, limit, skip
    )

    results = await driver_service.search_drivers(name, license_number, status, hub_id, limit, skip)
    logger.info("API Response → Search completed. Found %s drivers", len(results))
    return results


# ---------------- Update Driver ----------------
@handle_exceptions
@router.put("/update_driver", response_model=DriverOut)
async def update_driver(driver: DriverUpdate):
    """
    Endpoint: Update driver details.
    Calls service layer → driver_service.update_driver.
    """
    logger.info("API Request → Update Driver: driver_id=%s", driver.driver_id)
    updated = await driver_service.update_driver(driver)

    if not updated:
        logger.warning("API Response → Driver not found or deleted: driver_id=%s", driver.driver_id)
        raise HTTPException(status_code=404, detail="Driver not found or deleted")

    logger.info("API Response → Driver updated successfully: driver_id=%s", driver.driver_id)
    return updated


# ---------------- Delete Driver (Soft Delete) ----------------
@handle_exceptions
@router.delete("/delete_driver")
async def delete_driver(payload: DriverIdRequest):
    """
    Endpoint: Delete driver (soft delete).
    Calls service layer → driver_service.delete_driver.
    """
    logger.info("API Request → Delete Driver: driver_id=%s", payload.driver_id)
    success = await driver_service.delete_driver(payload.driver_id)

    if not success:
        logger.warning("API Response → Driver not found or already deleted: driver_id=%s", payload.driver_id)
        raise HTTPException(status_code=404, detail="Driver not found or already deleted")

    logger.info("API Response → Driver deleted successfully: driver_id=%s", payload.driver_id)
    return {"message": "Driver deleted successfully"}


# ---------------- Retirement Audit ----------------
@handle_exceptions
@router.post("/retire-audit")
async def retire_audit():
    """
    Endpoint: Retire drivers (batch job).
    - Retires drivers age > 50.
    - Updates status to 'retired'.
    Calls service layer → driver_service.retire_old_drivers.
    """
    logger.info("API Request → Retirement Audit started")
    count = await driver_service.retire_old_drivers()
    logger.info("API Response → Retirement Audit completed. Retired %s drivers", count)
    return {"retired_count": count}
