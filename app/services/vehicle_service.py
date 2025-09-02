from datetime import datetime
from fastapi import HTTPException
from app.db.mongodb import db
from app.models.vehicle import VehicleCreate, VehicleUpdate, VehicleDelete
from app.utiles.logger import get_logger

logger = get_logger(__name__)

# Allowed statuses
VALID_STATUSES = ["Available", "Unavailable", "In-Transit", "Under-Maintenance"]

# ---------------- Service: Add Vehicle ----------------
async def add_vehicle_service(vehicle: VehicleCreate):
    """
    Register a new vehicle.
    - Checks duplicate Vehicle_ID / Vehicle_Number
    - Inserts into MongoDB with timestamps
    """

    logger.info("Attempting to add vehicle → ID=%s, Number=%s", vehicle.Vehicle_ID, vehicle.Vehicle_Number)
    
    # Check for duplicates
    exists = await db["vehicles"].find_one({
        "$or": [
            {"Vehicle_ID": vehicle.Vehicle_ID},
            {"Vehicle_Number": vehicle.Vehicle_Number}
        ]
    })
    if exists:
        logger.warning("Vehicle add failed: Duplicate Vehicle_ID or Vehicle_Number found (ID=%s, Number=%s)",
                       vehicle.Vehicle_ID, vehicle.Vehicle_Number)
        raise HTTPException(status_code=409, detail="Vehicle_ID or Vehicle_Number already exists")
    
    # Prepare document
    doc = vehicle.dict()
    doc["created_at"] = datetime.utcnow()
    doc["updated_at"] = datetime.utcnow()
    await db["vehicles"].insert_one(doc)
    logger.info("Vehicle registered successfully: Vehicle_ID=%s", vehicle.Vehicle_ID)
    return {"status": "success", "message": "Vehicle registered successfully"}

# ---------------- Service: Update Vehicle ----------------
async def update_vehicle_service(update: VehicleUpdate):
    """
    Update vehicle details.
    - Validates Status field
    - Updates MongoDB with new values and timestamp
    """

    logger.info("Updating vehicle → Vehicle_ID=%s", update.Vehicle_ID)

    # Status validation
    if update.Status and update.Status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid Status. Allowed: {VALID_STATUSES}")
    
    # Apply update
    result = await db["vehicles"].find_one_and_update(
        {"Vehicle_ID": update.Vehicle_ID},
        {"$set": {**update.dict(exclude_unset=True), "updated_at": datetime.utcnow()}},
    )
    if not result:
        logger.error("Vehicle update failed: Vehicle not found → Vehicle_ID=%s", update.Vehicle_ID)
        raise HTTPException(status_code=404, detail="Vehicle not found")
    logger.info("Vehicle updated successfully: Vehicle_ID=%s", update.Vehicle_ID)
    return {"status": "success", "message": "Vehicle status updated"}

# ---------------- Service: Delete Vehicle ----------------
async def delete_vehicle_service(req: VehicleDelete):
    """
    Soft-delete vehicle by moving it to ClosedVehicles collection.
    - Copies full document into ClosedVehicles
    - Deletes from active vehicles collection
    """
    logger.info("Deleting vehicle → Vehicle_ID=%s, Number=%s", req.Vehicle_ID, req.Vehicle_Number)
    # Verify existence
    vehicle = await db["vehicles"].find_one({
        "Vehicle_ID": req.Vehicle_ID, "Vehicle_Number": req.Vehicle_Number
    })

    if not vehicle:
        logger.error("Delete failed: Vehicle not found → Vehicle_ID=%s, Number=%s", req.Vehicle_ID, req.Vehicle_Number)
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # Move to ClosedVehicles
    vehicle["Closed_Date"] = datetime.utcnow()
    await db["ClosedVehicles"].insert_one(vehicle)
    await db["vehicles"].delete_one({"_id": vehicle["_id"]})

    logger.info("Vehicle deleted successfully → Vehicle_ID=%s, Number=%s", req.Vehicle_ID, req.Vehicle_Number)
    return {"message": f"Vehicle {req.Vehicle_Number} deleted successfully"}

# ---------------- Service: Search Vehicle ----------------
async def search_vehicle_service(Vehicle_ID: str = None, Vehicle_Number: str = None, Status: str = None):
    """
    Search vehicles based on criteria.
    - Supports search by Vehicle_ID, Vehicle_Number, Status
    - Returns up to 100 results
    """

    logger.debug("Searching vehicles → ID=%s, Number=%s, Status=%s", Vehicle_ID, Vehicle_Number, Status)

    query = {}
    if Vehicle_ID: query["Vehicle_ID"] = Vehicle_ID
    if Vehicle_Number: query["Vehicle_Number"] = Vehicle_Number
    if Status: query["Status"] = Status

    if not query:
        logger.warning("Search failed: No search criteria provided")
        raise HTTPException(status_code=400, detail="No search criteria provided")

    #vehicles = await db["vehicles"].find(query).to_list(100)
    vehicles = await db["vehicles"].find(query, {"_id": 0}).to_list(100)
    logger.info("Search completed. Found %s vehicles", len(vehicles))
    return {"Available_Vehicles": vehicles}

# ---------------- Service: Dispatch Vehicle ----------------
async def dispatch_vehicle_service():
    """
    Dispatch logic:
    - Checks if dispatch job exists
    - Assigns first available driver and vehicle
    - Updates status for driver, vehicle, and dispatch record
    """

    logger.info("Starting vehicle dispatch process...")

    # Find pending dispatch
    dispatch = await db["Dispatches"].find_one({"Status": "In-Progress"})
    if not dispatch:
        logger.info("No dispatch pending → No vehicle assigned")
        return {"message": "No need to dispatch vehicle"}
    
    # Find available driver
    driver = await db["drivers"].find_one({"status": "active"})
    if not driver:
        logger.warning("Dispatch pending but no driver available")
        return {"message": "Load is available for Dispatch but no driver available"}

    # Find available vehicle
    vehicle = await db["vehicles"].find_one({"Status": "Available"})
    if not vehicle:
        logger.warning("Dispatch pending but no vehicle available")
        return {"message": "Load is available for Dispatch but no vehicle available"}

    # Assign driver and vehicle
    await db["drivers"].update_one({"driver_id": driver["driver_id"]}, {"$set": {"status": "Assigned"}})
    await db["vehicles"].update_one({"Vehicle_ID": vehicle["Vehicle_ID"]}, {"$set": {"Status": "In-Transit"}})
    await db["Dispatches"].update_one(
        {"_id": dispatch["_id"]},
        {"$set": {
            "Status": "In-Transit",
            "Driver_Assigned": driver["driver_id"],
            "Vehicle_Assigned": vehicle["Vehicle_ID"]
        }}
    )

    logger.info("Dispatch assigned → Vehicle_ID=%s, Driver=%s", vehicle["Vehicle_ID"], driver["name"])
    return {"message": f"Vehicle {vehicle['Vehicle_ID']} and Driver {driver['name']} assigned successfully"}
