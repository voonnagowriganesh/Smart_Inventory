from fastapi import APIRouter
from app.models.vehicle import VehicleCreate, VehicleUpdate, VehicleDelete
from app.services.vehicle_service import (
    add_vehicle_service,
    update_vehicle_service,
    delete_vehicle_service,
    search_vehicle_service,
    dispatch_vehicle_service
)
from app.utiles.decoratores import handle_exceptions
from app.utiles.logger import get_logger

# Initialize logger
logger = get_logger(__name__)

# APIRouter for vehicle management
router = APIRouter(prefix="/vehicles", tags=["Vehicle Management"])

# ======================================================
# Vehicle Routes
# Exposes REST endpoints for vehicle operations
# ======================================================

# ---------------- Register Vehicle ----------------
@handle_exceptions
@router.post("/register_vehicle", response_model=dict)
async def Register_vehicle(vehicle: VehicleCreate):
    """
    Endpoint: Register a new vehicle.
    Calls service layer → add_vehicle_service.
    """
    logger.info("API Request → Register Vehicle: ID=%s, Number=%s", vehicle.Vehicle_ID, vehicle.Vehicle_Number)
    response = await add_vehicle_service(vehicle)
    logger.info("API Response → Vehicle registered successfully: ID=%s", vehicle.Vehicle_ID)
    return response


# ---------------- Update Vehicle ----------------
@handle_exceptions
@router.put("/update_vehicle", response_model=dict)
async def update_vehicle(update: VehicleUpdate):
    """
    Endpoint: Update existing vehicle details.
    Calls service layer → update_vehicle_service.
    """
    logger.info("API Request → Update Vehicle: ID=%s", update.Vehicle_ID)
    response = await update_vehicle_service(update)
    logger.info("API Response → Vehicle updated successfully: ID=%s", update.Vehicle_ID)
    return response


# ---------------- Delete Vehicle ----------------
@handle_exceptions
@router.delete("/delete_vehicle", response_model=dict)
async def delete_vehicle(req: VehicleDelete):
    """
    Endpoint: Delete vehicle (soft delete).
    Moves vehicle record to ClosedVehicles.
    Calls service layer → delete_vehicle_service.
    """
    logger.info("API Request → Delete Vehicle: ID=%s, Number=%s", req.Vehicle_ID, req.Vehicle_Number)
    response = await delete_vehicle_service(req)
    logger.info("API Response → Vehicle deleted successfully: ID=%s, Number=%s", req.Vehicle_ID, req.Vehicle_Number)
    return response


# ---------------- Search Vehicle ----------------
@handle_exceptions
@router.get("/search_vehicle", response_model=dict)
async def search_vehicle(Vehicle_ID: str = None, Vehicle_Number: str = None, Status: str = None):
    """
    Endpoint: Search vehicles with optional filters.
    Calls service layer → search_vehicle_service.
    """
    logger.info("API Request → Search Vehicle (ID=%s, Number=%s, Status=%s)", Vehicle_ID, Vehicle_Number, Status)
    response = await search_vehicle_service(Vehicle_ID, Vehicle_Number, Status)
    logger.info("API Response → Search completed, found=%s vehicles", len(response.get("Available_Vehicles", [])))
    return response


# ---------------- Dispatch Vehicle ----------------
@handle_exceptions
@router.get("/dispatch_vehicle", response_model=dict)
async def dispatch_vehicle():
    """
    Endpoint: Dispatch a vehicle if a load is pending.
    - Assigns driver & vehicle.
    - Updates dispatch status.
    Calls service layer → dispatch_vehicle_service.
    """
    logger.info("API Request → Dispatch vehicle process initiated")
    response = await dispatch_vehicle_service()
    logger.info("API Response → Dispatch result: %s", response.get("message"))
    return response
