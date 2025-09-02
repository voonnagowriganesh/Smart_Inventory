# app/services/vehicle_inventory_service.py

from app.utiles.logger import get_logger
from fastapi import HTTPException
from datetime import datetime
from typing import Dict, Any
from app.db.mongodb import db
from app.utiles.custom_helpers import _now_utc, _gen_transaction_id   


# Collection names (centralized for consistency)
COL_DISPATCHES = "Dispatches"
COL_INV_BATCHES = "InventoryBatches"
COL_STOCK_TX = "StockTransactions"
COL_VEHICLES = "vehicles"
COL_DRIVERS = "drivers"

# Configure logger
logger = get_logger(__name__)

async def mark_dispatch_received_service(dispatch_id: str) -> Dict[str, Any]:
    """
    Marks a dispatch as received at the destination hub:
    - Updates stock in the destination hub.
    - Records stock IN transaction.
    - Resets driver and vehicle availability.
    - Updates dispatch record as Completed.
    """

    logger.info(f"Processing received dispatch: {dispatch_id}")

    # 1. Fetch dispatch
    dispatch = await db[COL_DISPATCHES].find_one({"dispatch_id": dispatch_id})
    print(dispatch)
    if not dispatch:
        logger.error(f"Dispatch {dispatch_id} not found")
        raise HTTPException(status_code=404, detail="Dispatch not found")

    if dispatch["Status"] != "In-Transit":
        logger.warning(f"Dispatch {dispatch_id} is not in transit. Current status: {dispatch['Status']}")
        raise HTTPException(status_code=400, detail="Dispatch is not in-transit")

    now = _now_utc()
    product_id = dispatch["Product_ID"]
    to_hub = dispatch["To_Hub_ID"]

    logger.info(f"Updating inventory at destination hub {to_hub} for product {product_id}")

    # 2. Update inventory at destination hub
    for batch in dispatch["Batch_Consumption"]:
        qty = batch["Qty"]
        unit_cost = batch["Unit_Cost"]
        batch_no = batch["Batch_No"]

        logger.debug(f"Processing batch {batch_no}: Qty={qty}, Unit_Cost={unit_cost}")

        # Insert stock transaction (IN)
        txn = {
            "transaction_id": _gen_transaction_id(),
            "type": "IN",
            "Product_ID": product_id,
            "Hub_ID": to_hub,
            "Batch_No": batch_no,  # keep same batch number
            "Quantity": qty,
            "Unit_Price": unit_cost,
            "Total_Value": float(unit_cost * qty),
            "reference": dispatch_id,
            "timestamp": now,
            "remarks": f"Received from {dispatch['From_Hub_ID']}"
        }
        await db[COL_STOCK_TX].insert_one(txn)
        logger.debug(f"Stock transaction inserted for batch {batch_no}")

        # Upsert into inventory batches at destination hub
        await db[COL_INV_BATCHES].update_one(
            {"Product_ID": product_id, "Hub_ID": to_hub, "Batch_No": batch_no},
            {"$inc": {"Quantity": qty}, "$set": {"status": "active", "last_updated": now}},
            upsert=True
        )
        logger.debug(f"Batch {batch_no} updated in InventoryBatches for hub {to_hub}")

    # 3. Reset driver & vehicle
    await db[COL_DRIVERS].update_one(
        {"driver_id": dispatch["Driver_Assigned"]},
        {"$set": {"status": "active"}}
    )
    logger.info(f"Driver {dispatch['Driver_Assigned']} reset to active")

    await db[COL_VEHICLES].update_one(
        {"Vehicle_ID": dispatch["Vehicle_Assigned"]},
        {"$set": {"Status": "Available"}}
    )
    logger.info(f"Vehicle {dispatch['Vehicle_Assigned']} reset to Available")

    # 4. Update dispatch record
    await db[COL_DISPATCHES].update_one(
        {"dispatch_id": dispatch_id},
        {"$set": {"Status": "Completed", "Arrival_Time": now}}
    )
    logger.info(f"Dispatch {dispatch_id} marked as Completed at {to_hub}")

    return {
        "message": f"Dispatch {dispatch_id} received at {to_hub} and inventory updated",
        "dispatch_id": dispatch_id,
        "status": "Completed",
        "hub": to_hub,
        "arrival_time": now
    }
